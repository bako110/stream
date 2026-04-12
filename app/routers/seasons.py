import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import require_role
from app.db.postgres.models.user import User
from app.schemas.season import SeasonCreate, SeasonUpdate, SeasonResponse
from app.services.season_episode_service import SeasonService

router = APIRouter()


@router.get("/series/{content_id}/seasons", response_model=list[SeasonResponse])
async def get_seasons(content_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await SeasonService.list_seasons(content_id, db)


@router.get("/series/{content_id}/seasons/{number}", response_model=SeasonResponse)
async def get_season(content_id: uuid.UUID, number: int, db: AsyncSession = Depends(get_db)):
    return await SeasonService.get_season(content_id, number, db)


@router.post("/series/{content_id}/seasons", response_model=SeasonResponse, status_code=201)
async def create_season(content_id: uuid.UUID, data: SeasonCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("admin"))):
    return await SeasonService.create_season(content_id, data, db)


@router.put("/series/{content_id}/seasons/{number}", response_model=SeasonResponse)
async def update_season(content_id: uuid.UUID, number: int, data: SeasonUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("admin"))):
    return await SeasonService.update_season(content_id, number, data, db)


@router.delete("/series/{content_id}/seasons/{number}", status_code=204)
async def delete_season(content_id: uuid.UUID, number: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("admin"))):
    await SeasonService.delete_season(content_id, number, db)
