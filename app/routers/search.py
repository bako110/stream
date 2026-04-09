from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import Optional

from app.database import get_db
from app.models.content import Content, ContentStatus
from app.models.concert import Concert, ConcertStatus
from app.schemas.content import ContentResponse

router = APIRouter()


@router.get("")
async def search(
    q: str = Query(..., min_length=1),
    type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    results = {"films": [], "series": [], "concerts": []}

    if not type or type in ("film", "serie"):
        content_query = select(Content).where(
            Content.status == ContentStatus.published,
            or_(
                Content.title.ilike(f"%{q}%"),
                Content.synopsis.ilike(f"%{q}%"),
            ),
        )
        content_result = await db.execute(content_query.limit(10))
        for item in content_result.scalars().all():
            key = "films" if item.type == "film" else "series"
            results[key].append({"id": str(item.id), "title": item.title, "type": item.type})

    if not type or type == "concert":
        concert_query = select(Concert).where(
            Concert.status == ConcertStatus.published,
            Concert.title.ilike(f"%{q}%"),
        )
        concert_result = await db.execute(concert_query.limit(10))
        results["concerts"] = [
            {"id": str(c.id), "title": c.title}
            for c in concert_result.scalars().all()
        ]

    return results


@router.get("/trending")
async def get_trending(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Content)
        .where(Content.status == ContentStatus.published)
        .order_by(Content.view_count.desc())
        .limit(10)
    )
    return [{"id": str(c.id), "title": c.title, "view_count": c.view_count}
            for c in result.scalars().all()]


@router.get("/new")
async def get_new(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Content)
        .where(Content.status == ContentStatus.published)
        .order_by(Content.created_at.desc())
        .limit(10)
    )
    return [{"id": str(c.id), "title": c.title, "created_at": str(c.created_at)}
            for c in result.scalars().all()]