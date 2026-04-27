import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import require_role
from app.db.postgres.models.user import User
from app.schemas.season import SeasonCreate, SeasonUpdate, SeasonResponse
from app.services.season_episode_service import SeasonService
from app.utils.cache import cache_get, cache_set, cache_invalidate_prefix

router = APIRouter()


@router.get("/series/{content_id}/seasons", response_model=list[SeasonResponse])
async def get_seasons(content_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    ck = f"seasons:{content_id}"
    if (cached := await cache_get(ck)) is not None:
        return cached
    data = await SeasonService.list_seasons(content_id, db)
    serialized = [SeasonResponse.model_validate(s).model_dump(mode="json") for s in data]
    await cache_set(ck, serialized, ttl=3600)  # 1h — données statiques
    return data


@router.get("/series/{content_id}/seasons/{number}", response_model=SeasonResponse)
async def get_season(content_id: uuid.UUID, number: int, db: AsyncSession = Depends(get_db)):
    ck = f"season:{content_id}:n{number}"
    if (cached := await cache_get(ck)) is not None:
        return cached
    data = await SeasonService.get_season(content_id, number, db)
    await cache_set(ck, SeasonResponse.model_validate(data).model_dump(mode="json"), ttl=3600)
    return data


@router.post("/series/{content_id}/seasons", response_model=SeasonResponse, status_code=201)
async def create_season(content_id: uuid.UUID, data: SeasonCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("admin"))):
    result = await SeasonService.create_season(content_id, data, db)
    await cache_invalidate_prefix(f"seasons:{content_id}")
    return result


@router.put("/series/{content_id}/seasons/{number}", response_model=SeasonResponse)
async def update_season(content_id: uuid.UUID, number: int, data: SeasonUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("admin"))):
    result = await SeasonService.update_season(content_id, number, data, db)
    await cache_invalidate_prefix(f"seasons:{content_id}")
    await cache_invalidate_prefix(f"season:{content_id}:n{number}")
    return result


@router.delete("/series/{content_id}/seasons/{number}", status_code=204)
async def delete_season(content_id: uuid.UUID, number: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("admin"))):
    await SeasonService.delete_season(content_id, number, db)
    await cache_invalidate_prefix(f"seasons:{content_id}")
    await cache_invalidate_prefix(f"season:{content_id}:n{number}")
