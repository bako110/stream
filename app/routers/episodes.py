import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import require_role
from app.db.postgres.models.user import User
from app.schemas.episode import EpisodeCreate, EpisodeUpdate, EpisodeResponse
from app.services.season_episode_service import EpisodeService
from app.utils.cache import cache_get, cache_set, cache_invalidate_prefix

router = APIRouter()


@router.get("/content/series/{content_id}/seasons/{number}/episodes", response_model=list[EpisodeResponse])
async def get_episodes(content_id: uuid.UUID, number: int, db: AsyncSession = Depends(get_db)):
    ck = f"episodes:{content_id}:s{number}"
    if (cached := await cache_get(ck)) is not None:
        return cached
    data = await EpisodeService.list_episodes(content_id, number, db)
    serialized = [EpisodeResponse.model_validate(e).model_dump(mode="json") for e in data]
    await cache_set(ck, serialized, ttl=3600)  # 1h — données statiques
    return data


@router.post("/content/series/{content_id}/seasons/{number}/episodes", response_model=EpisodeResponse, status_code=201)
async def create_episode(content_id: uuid.UUID, number: int, data: EpisodeCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("admin"))):
    return await EpisodeService.create_episode(content_id, number, data, db)


@router.get("/episodes/{episode_id}", response_model=EpisodeResponse)
async def get_episode(episode_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    ck = f"episode:{episode_id}"
    if (cached := await cache_get(ck)) is not None:
        return cached
    data = await EpisodeService.get_episode(episode_id, db)
    await cache_set(ck, EpisodeResponse.model_validate(data).model_dump(mode="json"), ttl=3600)
    return data


@router.put("/episodes/{episode_id}", response_model=EpisodeResponse)
async def update_episode(episode_id: uuid.UUID, data: EpisodeUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("admin"))):
    result = await EpisodeService.update_episode(episode_id, data, db)
    await cache_invalidate_prefix("episodes:")
    await cache_invalidate_prefix(f"episode:{episode_id}")
    return result


@router.delete("/episodes/{episode_id}", status_code=204)
async def delete_episode(episode_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("admin"))):
    await EpisodeService.delete_episode(episode_id, db)
    await cache_invalidate_prefix("episodes:")
    await cache_invalidate_prefix(f"episode:{episode_id}")
