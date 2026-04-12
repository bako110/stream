import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import HTTPException

from app.db.postgres.models.user import User
from app.db.postgres.models.concert import Concert, ConcertStatus
from app.schemas.concert import ConcertCreate, ConcertUpdate


class ConcertService:

    @staticmethod
    async def list_concerts(page: int, limit: int, genre: Optional[str], db: AsyncSession) -> dict:
        query = select(Concert).where(Concert.status == ConcertStatus.published)
        if genre:
            query = query.where(Concert.genre == genre)
        total = await db.scalar(select(func.count()).select_from(query.subquery()))
        result = await db.execute(query.offset((page - 1) * limit).limit(limit))
        return {"items": result.scalars().all(), "total": total, "page": page, "limit": limit}

    @staticmethod
    async def get_live_concerts(db: AsyncSession) -> list:
        result = await db.execute(select(Concert).where(Concert.status == ConcertStatus.live))
        return result.scalars().all()

    @staticmethod
    async def get_upcoming_concerts(db: AsyncSession) -> list:
        result = await db.execute(
            select(Concert)
            .where(Concert.status == ConcertStatus.published, Concert.scheduled_at > datetime.utcnow())
            .order_by(Concert.scheduled_at).limit(20)
        )
        return result.scalars().all()

    @staticmethod
    async def get_concert(concert_id: uuid.UUID, db: AsyncSession) -> Concert:
        result = await db.execute(select(Concert).where(Concert.id == concert_id))
        concert = result.scalar_one_or_none()
        if not concert:
            raise HTTPException(status_code=404, detail="Concert non trouvé")
        return concert

    @staticmethod
    async def create_concert(data: ConcertCreate, artist: User, db: AsyncSession, mongo: AsyncIOMotorDatabase) -> Concert:
        concert = Concert(**data.model_dump(exclude_none=True), artist_id=artist.id)
        db.add(concert)
        await db.commit()
        await db.refresh(concert)
        await mongo["concert_streams"].insert_one({
            "concert_id": str(concert.id),
            "rtmp_key": None, "rtmp_url": None, "live_hls_url": None,
            "replay_video_id": None,
            "peak_viewers": 0, "current_viewers": 0, "total_view_time_sec": 0,
            "viewer_snapshots": [],
            "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
        })
        return concert

    @staticmethod
    def _check_owner(concert: Concert, user: User) -> None:
        if concert.artist_id != user.id and user.role.value != "admin":
            raise HTTPException(status_code=403, detail="Accès refusé")

    @staticmethod
    async def update_concert(concert_id: uuid.UUID, data: ConcertUpdate, user: User, db: AsyncSession) -> Concert:
        result = await db.execute(select(Concert).where(Concert.id == concert_id))
        concert = result.scalar_one_or_none()
        if not concert:
            raise HTTPException(status_code=404, detail="Concert non trouvé")
        ConcertService._check_owner(concert, user)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(concert, key, value)
        await db.commit()
        await db.refresh(concert)
        return concert

    @staticmethod
    async def delete_concert(concert_id: uuid.UUID, user: User, db: AsyncSession, mongo: AsyncIOMotorDatabase) -> None:
        result = await db.execute(select(Concert).where(Concert.id == concert_id))
        concert = result.scalar_one_or_none()
        if not concert:
            raise HTTPException(status_code=404, detail="Concert non trouvé")
        ConcertService._check_owner(concert, user)
        await db.delete(concert)
        await db.commit()
        await mongo["concert_streams"].delete_one({"concert_id": str(concert_id)})

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
        await db.refresh(concert)
        return concert

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
        return concert
