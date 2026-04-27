from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import get_current_active_user, get_optional_user
from app.db.postgres.models.user import User
from app.services.search_service import SearchService
from app.services.feed_service import FeedService

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
    return await SearchService.search(
        q, type, db, page=page, limit=limit,
        current_user_id=str(current_user.id) if current_user else None,
    )


@router.get("/trending")
async def get_trending(db: AsyncSession = Depends(get_db)):
    return await SearchService.get_trending(db)


@router.get("/new")
async def get_new(db: AsyncSession = Depends(get_db)):
    return await SearchService.get_new(db)


@router.get("/trending/reels")
async def get_trending_reels(db: AsyncSession = Depends(get_db)):
    return await SearchService.get_trending_reels(db)


@router.get("/upcoming/events")
async def get_upcoming_events(db: AsyncSession = Depends(get_db)):
    return await SearchService.get_upcoming_events(db)


@router.get("/feed")
async def get_feed(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    """
    Fil algorithmique v1.0 — contenus classés par score personnalisé.
    Utilisateur non connecté = fil général sans personnalisation.
    """
    if current_user:
        return await FeedService.get_feed(current_user.id, page, limit, db)
    else:
        # Fil anonyme : tri par fraîcheur + engagement simple
        return await FeedService.get_feed_anonymous(page, limit, db)
