from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.services.search_service import SearchService

router = APIRouter()


@router.get("")
async def search(q: str = Query(..., min_length=1), type: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    return await SearchService.search(q, type, db)


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
