from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.database import get_db
from app.deps import require_role
from app.models.user import User
from app.models.content import Content, ContentType
from app.models.season import Season
from app.schemas.season_episode_video import (
    SeasonCreate, SeasonUpdate, SeasonResponse
)

router = APIRouter()


@router.get("/series/{content_id}/seasons", response_model=list[SeasonResponse])
async def get_seasons(content_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Season)
        .where(Season.content_id == content_id)
        .order_by(Season.number)
    )
    return result.scalars().all()


@router.post("/series/{content_id}/seasons", response_model=SeasonResponse, status_code=201)
async def create_season(
    content_id: uuid.UUID,
    data: SeasonCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await db.execute(
        select(Content).where(
            Content.id == content_id,
            Content.type == ContentType.serie,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Série non trouvée")

    season = Season(**data.model_dump(), content_id=content_id)
    db.add(season)
    await db.commit()
    await db.refresh(season)
    return season


@router.get("/series/{content_id}/seasons/{number}", response_model=SeasonResponse)
async def get_season(
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
    return season


@router.put("/series/{content_id}/seasons/{number}", response_model=SeasonResponse)
async def update_season(
    content_id: uuid.UUID,
    number: int,
    data: SeasonUpdate,
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

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(season, key, value)

    await db.commit()
    await db.refresh(season)
    return season


@router.delete("/series/{content_id}/seasons/{number}", status_code=204)
async def delete_season(
    content_id: uuid.UUID,
    number: int,
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
    await db.delete(season)
    await db.commit()