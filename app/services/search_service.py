from typing import Optional
import uuid as _uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.db.postgres.models.content import Content, ContentStatus, ContentType
from app.db.postgres.models.concert import Concert, ConcertStatus
from app.db.postgres.models.event import Event, EventStatus
from app.db.postgres.models.reel import Reel, ReelStatus
from app.db.postgres.models.user import User
from app.db.postgres.models.user_block import UserBlock
from app.utils.cache import cache_get, cache_set


class SearchService:

    @staticmethod
    async def search(
        q: str,
        type_filter: Optional[str],
        db: AsyncSession,
        page: int = 1,
        limit: int = 10,
        current_user_id: Optional[str] = None,
    ) -> dict:
        limit = min(limit, 50)
        offset = (page - 1) * limit

        cache_key = f"search:{q}:{type_filter}:{page}:{limit}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        results: dict = {"users": [], "films": [], "series": [], "concerts": [], "events": [], "reels": []}

        if not type_filter or type_filter == "user":
            user_query = select(User).where(
                User.is_active == True,
                or_(
                    User.username.ilike(f"%{q}%"),
                    User.display_name.ilike(f"%{q}%"),
                    User.first_name.ilike(f"%{q}%"),
                    User.last_name.ilike(f"%{q}%"),
                ),
            )
            # Exclure les utilisateurs bloqués (dans les deux sens)
            if current_user_id:
                uid = _uuid.UUID(current_user_id)
                blocked_ids_q = select(UserBlock.blocked_id).where(UserBlock.blocker_id == uid)
                blocker_ids_q = select(UserBlock.blocker_id).where(UserBlock.blocked_id == uid)
                user_query = user_query.where(
                    User.id.not_in(blocked_ids_q),
                    User.id.not_in(blocker_ids_q),
                )
            user_result = await db.execute(user_query.offset(offset).limit(limit))
            results["users"] = [
                {
                    "id": str(u.id),
                    "username": u.username,
                    "display_name": u.display_name,
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "avatar_url": u.avatar_url,
                    "bio": u.bio,
                }
                for u in user_result.scalars().all()
            ]

        if not type_filter or type_filter in ("film", "serie"):
            content_result = await db.execute(
                select(Content).where(
                    Content.status == ContentStatus.published,
                    or_(Content.title.ilike(f"%{q}%"), Content.synopsis.ilike(f"%{q}%")),
                ).offset(offset).limit(limit)
            )
            for item in content_result.scalars().all():
                key = "films" if item.type == ContentType.film else "series"
                results[key].append({
                    "id": str(item.id), "title": item.title,
                    "type": item.type, "year": item.year,
                    "thumbnail_url": item.thumbnail_url,
                })

        if not type_filter or type_filter == "concert":
            concert_result = await db.execute(
                select(Concert).where(
                    Concert.status == ConcertStatus.published,
                    Concert.title.ilike(f"%{q}%"),
                ).offset(offset).limit(limit)
            )
            results["concerts"] = [
                {"id": str(c.id), "title": c.title, "genre": c.genre,
                 "scheduled_at": c.scheduled_at.isoformat() if c.scheduled_at else None}
                for c in concert_result.scalars().all()
            ]

        if not type_filter or type_filter == "event":
            event_result = await db.execute(
                select(Event).where(
                    Event.status == EventStatus.published,
                    or_(Event.title.ilike(f"%{q}%"), Event.description.ilike(f"%{q}%")),
                ).offset(offset).limit(limit)
            )
            results["events"] = [
                {
                    "id": str(e.id), "title": e.title, "type": e.event_type,
                    "starts_at": e.starts_at.isoformat() if e.starts_at else None,
                    "thumbnail_url": e.thumbnail_url,
                }
                for e in event_result.scalars().all()
            ]

        if not type_filter or type_filter == "reel":
            reel_result = await db.execute(
                select(Reel).where(
                    Reel.status == ReelStatus.published,
                    Reel.caption.ilike(f"%{q}%"),
                ).offset(offset).limit(limit)
            )
            results["reels"] = [
                {
                    "id": str(r.id), "caption": r.caption,
                    "thumbnail_url": r.thumbnail_url,
                    "view_count": r.view_count,
                }
                for r in reel_result.scalars().all()
            ]

        results["page"] = page
        results["limit"] = limit
        await cache_set(cache_key, results, ttl=1800)  # 30 min
        return results

    @staticmethod
    async def get_trending(db: AsyncSession) -> list:
        result = await db.execute(
            select(Content).where(Content.status == ContentStatus.published)
            .order_by(Content.view_count.desc()).limit(10)
        )
        return [
            {"id": str(c.id), "title": c.title, "view_count": c.view_count, "thumbnail_url": c.thumbnail_url}
            for c in result.scalars().all()
        ]

    @staticmethod
    async def get_trending_reels(db: AsyncSession) -> list:
        from app.services.local_storage_service import get_h264_url
        result = await db.execute(
            select(Reel).where(Reel.status == ReelStatus.published)
            .order_by(Reel.view_count.desc()).limit(20)
        )
        reels = result.scalars().all()
        return [
            {"id": str(r.id), "caption": r.caption, "thumbnail_url": r.thumbnail_url,
             "video_url": get_h264_url(r.video_url) if r.video_url else None,
             "view_count": r.view_count, "like_count": r.like_count}
            for r in reels
        ]

    @staticmethod
    async def get_new(db: AsyncSession) -> list:
        result = await db.execute(
            select(Content).where(Content.status == ContentStatus.published)
            .order_by(Content.created_at.desc()).limit(10)
        )
        return [
            {"id": str(c.id), "title": c.title, "created_at": c.created_at.isoformat(), "thumbnail_url": c.thumbnail_url}
            for c in result.scalars().all()
        ]

    @staticmethod
    async def get_upcoming_events(db: AsyncSession) -> list:
        from sqlalchemy import func
        result = await db.execute(
            select(Event).where(
                Event.status == EventStatus.published,
                Event.starts_at >= func.now(),
            ).order_by(Event.starts_at).limit(10)
        )
        return [
            {"id": str(e.id), "title": e.title, "type": e.event_type,
             "starts_at": e.starts_at.isoformat() if e.starts_at else None,
             "thumbnail_url": e.thumbnail_url}
            for e in result.scalars().all()
        ]
