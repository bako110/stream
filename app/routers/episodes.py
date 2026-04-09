from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.database import get_db
from app.deps import require_role
from app.models.user import User
from app.models.season import Season
from app.models.episode import Episode
from app.schemas.season_episode_video import (
    EpisodeCreate, EpisodeUpdate, EpisodeResponse
)

router = APIRouter()


@router.get("/content/series/{content_id}/seasons/{number}/episodes", response_model=list[EpisodeResponse])
async def get_episodes(
    content_id: uuid.UUID,
    number: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Season).where(
            Season.content_id == content_id,
            Season.number == number,
        )
    )
    season = result.scalar_one_or_none()
    if not season:
        raise HTTPException(status_code=404, detail="Saison non trouvée")

    result = await db.execute(
        select(Episode)
        .where(Episode.season_id == season.id)
        .order_by(Episode.number)
    )
    return result.scalars().all()


@router.post("/content/series/{content_id}/seasons/{number}/episodes", response_model=EpisodeResponse, status_code=201)
async def create_episode(
    content_id: uuid.UUID,
    number: int,
    data: EpisodeCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await db.execute(
        select(Season).where(
            Season.content_id == content_id,
            Season.number == number,
        )
    )
    season = result.scalar_one_or_none()
    if not season:
        raise HTTPException(status_code=404, detail="Saison non trouvée")

    episode = Episode(**data.model_dump(), season_id=season.id)
    db.add(episode)
    await db.commit()
    await db.refresh(episode)
    return episode


@router.get("/episodes/{episode_id}", response_model=EpisodeResponse)
async def get_episode(episode_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="Épisode non trouvé")
    return episode


@router.put("/episodes/{episode_id}", response_model=EpisodeResponse)
async def update_episode(
    episode_id: uuid.UUID,
    data: EpisodeUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="Épisode non trouvé")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(episode, key, value)

    await db.commit()
    await db.refresh(episode)
    return episode


@router.delete("/episodes/{episode_id}", status_code=204)
async def delete_episode(
    episode_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="Épisode non trouvé")
    await db.delete(episode)
    await db.commit()