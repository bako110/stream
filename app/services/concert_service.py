import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, cast, Float, literal, String
from sqlalchemy.orm import selectinload
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import HTTPException

from app.db.postgres.models.user import User
from app.db.postgres.models.concert import Concert, ConcertStatus
from app.schemas.concert import ConcertCreate, ConcertUpdate
from app.utils.cache import cache_invalidate_prefix  # noqa: F401
from app.services.local_storage_service import delete_media


class ConcertService:

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        from math import radians, sin, cos, sqrt, atan2
        R = 6371.0
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        return R * 2 * atan2(sqrt(a), sqrt(1 - a))

    @staticmethod
    async def list_concerts(
        page: int, limit: int, genre: Optional[str], db: AsyncSession,
        user_lat: float | None = None, user_lon: float | None = None,
        following_ids: list | None = None,
    ) -> dict:
        now = datetime.utcnow()
        follow_ids_str = [str(fid) for fid in (following_ids or [])]

        # Filtres WHERE
        filters = []
        if genre:
            filters.append(Concert.genre == genre)

        # Compter le total avec filtres
        count_q = select(func.count()).select_from(select(Concert).where(*filters).subquery())
        total = await db.scalar(count_q)

        # Score SQL : follow boost + featured + live + fraîcheur date
        follow_boost = (
            case((Concert.artist_id.cast(String).in_(follow_ids_str), cast(1000.0, Float)), else_=cast(0.0, Float))
            if follow_ids_str else cast(0.0, Float)
        )
        featured_boost = case((Concert.is_featured == True, cast(200.0, Float)), else_=cast(0.0, Float))
        live_boost = case((Concert.status == ConcertStatus.live, cast(300.0, Float)), else_=cast(0.0, Float))
        time_penalty = func.abs(
            func.extract("epoch", Concert.scheduled_at) - func.extract("epoch", literal(now))
        ) / 86400.0
        score_col = (follow_boost + featured_boost + live_boost - time_penalty).label("score")

        # Tri entièrement en SQL — page exacte, pas de ×3
        result = await db.execute(
            select(Concert)
            .options(selectinload(Concert.artist))
            .where(*filters)
            .order_by(score_col.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        items = result.scalars().all()

        return {"items": items, "total": total, "page": page, "limit": limit}

    @staticmethod
    async def get_live_concerts(db: AsyncSession) -> list:
        result = await db.execute(
            select(Concert)
            .options(selectinload(Concert.artist))
            .where(Concert.status == ConcertStatus.live)
        )
        return result.scalars().all()

    @staticmethod
    async def get_upcoming_concerts(db: AsyncSession) -> list:
        result = await db.execute(
            select(Concert)
            .options(selectinload(Concert.artist))
            .where(Concert.status == ConcertStatus.published, Concert.scheduled_at > datetime.utcnow())
            .order_by(Concert.scheduled_at).limit(20)
        )
        return result.scalars().all()

    @staticmethod
    async def get_concert(concert_id: uuid.UUID, db: AsyncSession) -> Concert:
        result = await db.execute(
            select(Concert)
            .options(selectinload(Concert.artist))
            .where(Concert.id == concert_id)
        )
        concert = result.scalar_one_or_none()
        if not concert:
            raise HTTPException(status_code=404, detail="Concert non trouvé")
        return concert

    @staticmethod
    async def create_concert(data: ConcertCreate, artist: User, db: AsyncSession, mongo: AsyncIOMotorDatabase) -> Concert:
        dump = data.model_dump(exclude_none=True)
        # Strip timezone pour les colonnes TIMESTAMP WITHOUT TIME ZONE
        if "scheduled_at" in dump and dump["scheduled_at"].tzinfo is not None:
            dump["scheduled_at"] = dump["scheduled_at"].replace(tzinfo=None)
        concert = Concert(**dump, artist_id=artist.id)
        db.add(concert)
        await db.commit()
        await db.refresh(concert)
        # Recharger avec la relation artist pour ConcertResponse
        result = await db.execute(
            select(Concert).options(selectinload(Concert.artist)).where(Concert.id == concert.id)
        )
        concert = result.scalar_one()
        await mongo["concert_streams"].insert_one({
            "concert_id": str(concert.id),
            "rtmp_key": None, "rtmp_url": None, "live_hls_url": None,
            "replay_video_id": None,
            "peak_viewers": 0, "current_viewers": 0, "total_view_time_sec": 0,
            "viewer_snapshots": [],
            "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
        })
        await cache_invalidate_prefix("concerts:")
        return concert

    @staticmethod
    def _check_owner(concert: Concert, user: User) -> None:
        role = user.role.value if hasattr(user.role, 'value') else user.role
        if concert.artist_id != user.id and role != "admin":
            raise HTTPException(status_code=403, detail="Accès refusé")

    @staticmethod
    async def update_concert(concert_id: uuid.UUID, data: ConcertUpdate, user: User, db: AsyncSession) -> Concert:
        result = await db.execute(select(Concert).where(Concert.id == concert_id))
        concert = result.scalar_one_or_none()
        if not concert:
            raise HTTPException(status_code=404, detail="Concert non trouvé")
        ConcertService._check_owner(concert, user)
        for key, value in data.model_dump(exclude_unset=True).items():
            if key == "scheduled_at" and value is not None and value.tzinfo is not None:
                value = value.replace(tzinfo=None)
            setattr(concert, key, value)
        await db.commit()
        # Recharger avec la relation artist pour ConcertResponse
        result = await db.execute(
            select(Concert).options(selectinload(Concert.artist)).where(Concert.id == concert.id)
        )
        concert = result.scalar_one()
        await cache_invalidate_prefix("concerts:")
        return concert

    @staticmethod
    async def delete_concert(concert_id: uuid.UUID, user: User, db: AsyncSession, mongo: AsyncIOMotorDatabase) -> None:
        result = await db.execute(select(Concert).where(Concert.id == concert_id))
        concert = result.scalar_one_or_none()
        if not concert:
            raise HTTPException(status_code=404, detail="Concert non trouvé")
        ConcertService._check_owner(concert, user)
        video_url = concert.video_url
        thumbnail_url = concert.thumbnail_url
        banner_url = concert.banner_url
        await db.delete(concert)
        await db.commit()
        await mongo["concert_streams"].delete_one({"concert_id": str(concert_id)})
        await delete_media(video_url)
        await delete_media(thumbnail_url)
        await delete_media(banner_url)
        await cache_invalidate_prefix("concerts:")

    @staticmethod
    async def publish_concert(concert_id: uuid.UUID, user: User, db: AsyncSession) -> Concert:
        result = await db.execute(select(Concert).where(Concert.id == concert_id))
        concert = result.scalar_one_or_none()
        if not concert:
            raise HTTPException(status_code=404, detail="Concert non trouvé")
        ConcertService._check_owner(concert, user)
        concert.status = ConcertStatus.published
        concert.published_at = datetime.utcnow()
        await db.commit()
        result = await db.execute(
            select(Concert).options(selectinload(Concert.artist)).where(Concert.id == concert_id)
        )
        await cache_invalidate_prefix("concerts:")
        return result.scalar_one()

    @staticmethod
    async def set_live_status(concert_id: uuid.UUID, new_status: ConcertStatus, user: User, db: AsyncSession) -> Concert:
        result = await db.execute(select(Concert).where(Concert.id == concert_id))
        concert = result.scalar_one_or_none()
        if not concert:
            raise HTTPException(status_code=404, detail="Concert non trouvé")
        ConcertService._check_owner(concert, user)
        concert.status = new_status
        await db.commit()
        await db.refresh(concert)
        await cache_invalidate_prefix("concerts:")
        return concert
