from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.db.postgres.models.content import Content, ContentStatus, ContentType
from app.db.postgres.models.concert import Concert, ConcertStatus
from app.db.postgres.models.event import Event, EventStatus
from app.db.postgres.models.reel import Reel, ReelStatus


class SearchService:

    @staticmethod
    async def search(q: str, type_filter: Optional[str], db: AsyncSession) -> dict:
        results: dict = {"films": [], "series": [], "concerts": [], "events": [], "reels": []}

        if not type_filter or type_filter in ("film", "serie"):
            content_result = await db.execute(
                select(Content).where(
                    Content.status == ContentStatus.published,
                    or_(Content.title.ilike(f"%{q}%"), Content.synopsis.ilike(f"%{q}%")),
                ).limit(10)
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
                ).limit(10)
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
                ).limit(10)
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
                ).limit(10)
            )
            results["reels"] = [
                {
                    "id": str(r.id), "caption": r.caption,
                    "thumbnail_url": r.thumbnail_url,
                    "view_count": r.view_count,
                }
                for r in reel_result.scalars().all()
            ]

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
        result = await db.execute(
            select(Reel).where(Reel.status == ReelStatus.published)
            .order_by(Reel.view_count.desc()).limit(20)
        )
        return [
            {"id": str(r.id), "caption": r.caption, "thumbnail_url": r.thumbnail_url,
             "view_count": r.view_count, "like_count": r.like_count}
            for r in result.scalars().all()
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
