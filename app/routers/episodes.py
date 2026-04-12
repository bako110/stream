import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import require_role
from app.db.postgres.models.user import User
from app.schemas.episode import EpisodeCreate, EpisodeUpdate, EpisodeResponse
from app.services.season_episode_service import EpisodeService

router = APIRouter()


@router.get("/content/series/{content_id}/seasons/{number}/episodes", response_model=list[EpisodeResponse])
async def get_episodes(content_id: uuid.UUID, number: int, db: AsyncSession = Depends(get_db)):
    return await EpisodeService.list_episodes(content_id, number, db)


@router.post("/content/series/{content_id}/seasons/{number}/episodes", response_model=EpisodeResponse, status_code=201)
async def create_episode(content_id: uuid.UUID, number: int, data: EpisodeCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("admin"))):
    return await EpisodeService.create_episode(content_id, number, data, db)


@router.get("/episodes/{episode_id}", response_model=EpisodeResponse)
async def get_episode(episode_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await EpisodeService.get_episode(episode_id, db)


@router.put("/episodes/{episode_id}", response_model=EpisodeResponse)
async def update_episode(episode_id: uuid.UUID, data: EpisodeUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("admin"))):
    return await EpisodeService.update_episode(episode_id, data, db)


@router.delete("/episodes/{episode_id}", status_code=204)
async def delete_episode(episode_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("admin"))):
    await EpisodeService.delete_episode(episode_id, db)
