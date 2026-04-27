from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import get_current_active_user, get_optional_user
from app.db.postgres.models.user import User
from app.services.search_service import SearchService
from app.services.feed_service import FeedService
from app.utils.cache import cache_get, cache_set

router = APIRouter()


@router.get("")
async def search(
    q: str = Query(..., min_length=1, max_length=100),
    type: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    # Recherche personnalisée — pas de cache (résultats dépendent du user)
    return await SearchService.search(
        q, type, db, page=page, limit=limit,
        current_user_id=str(current_user.id) if current_user else None,
    )


@router.get("/trending")
async def get_trending(db: AsyncSession = Depends(get_db)):
    ck = "search:trending"
    if (cached := await cache_get(ck)) is not None:
        return cached
    data = await SearchService.get_trending(db)
    await cache_set(ck, data, ttl=300)  # 5 min — change peu souvent
    return data


@router.get("/new")
async def get_new(db: AsyncSession = Depends(get_db)):
    ck = "search:new"
    if (cached := await cache_get(ck)) is not None:
        return cached
    data = await SearchService.get_new(db)
    await cache_set(ck, data, ttl=120)  # 2 min
    return data


@router.get("/trending/reels")
async def get_trending_reels(db: AsyncSession = Depends(get_db)):
    ck = "search:trending:reels"
    if (cached := await cache_get(ck)) is not None:
        return cached
    data = await SearchService.get_trending_reels(db)
    await cache_set(ck, data, ttl=120)  # 2 min
    return data


@router.get("/upcoming/events")
async def get_upcoming_events(db: AsyncSession = Depends(get_db)):
    ck = "search:upcoming:events"
    if (cached := await cache_get(ck)) is not None:
        return cached
    data = await SearchService.get_upcoming_events(db)
    await cache_set(ck, data, ttl=300)  # 5 min
    return data


@router.get("/feed")
async def get_feed(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    """Fil algorithmique — personnalisé si connecté, général sinon."""
    if current_user:
        ck = f"fil_utilisateur:{current_user.id}:p{page}:l{limit}"
        if (cached := await cache_get(ck)) is not None:
            return cached
        data = await FeedService.get_feed(current_user.id, page, limit, db)
        await cache_set(ck, data, ttl=60)
        return data
    else:
        ck = f"fil_anonymous:p{page}:l{limit}"
        if (cached := await cache_get(ck)) is not None:
            return cached
        data = await FeedService.get_feed_anonymous(page, limit, db)
        await cache_set(ck, data, ttl=120)
        return data
