from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import uuid

from app.database import get_db
from app.deps import require_role
from app.models.user import User
from app.models.content import Content, ContentType, ContentStatus
from app.schemas.content import (
    ContentCreate, ContentUpdate, ContentResponse, ContentListResponse
)

router = APIRouter()


@router.get("/films", response_model=ContentListResponse)
async def get_films(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    year: Optional[int] = None,
    language: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Content).where(
        Content.type == ContentType.film,
        Content.status == ContentStatus.published,
    )
    if year:
        query = query.where(Content.year == year)
    if language:
        query = query.where(Content.language == language)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    films = result.scalars().all()

    return {"items": films, "total": total, "page": page, "limit": limit}


@router.get("/films/{content_id}", response_model=ContentResponse)
async def get_film(content_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Content).where(
            Content.id == content_id,
            Content.type == ContentType.film,
        )
    )
    film = result.scalar_one_or_none()
    if not film:
        raise HTTPException(status_code=404, detail="Film non trouvé")
    return film


@router.post("/films", response_model=ContentResponse, status_code=201)
async def create_film(
    data: ContentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    film_data = data.model_dump()
    film = Content(**film_data, type=ContentType.film, added_by=current_user.id)
    db.add(film)
    await db.commit()
    await db.refresh(film)
    return film


@router.put("/films/{content_id}", response_model=ContentResponse)
async def update_film(
    content_id: uuid.UUID,
    data: ContentUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await db.execute(select(Content).where(Content.id == content_id))
    film = result.scalar_one_or_none()
    if not film:
        raise HTTPException(status_code=404, detail="Film non trouvé")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(film, key, value)

    await db.commit()
    await db.refresh(film)
    return film


@router.delete("/films/{content_id}", status_code=204)
async def delete_film(
    content_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await db.execute(select(Content).where(Content.id == content_id))
    film = result.scalar_one_or_none()
    if not film:
        raise HTTPException(status_code=404, detail="Film non trouvé")
    await db.delete(film)
    await db.commit()


@router.patch("/films/{content_id}/publish", response_model=ContentResponse)
async def publish_film(
    content_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await db.execute(select(Content).where(Content.id == content_id))
    film = result.scalar_one_or_none()
    if not film:
        raise HTTPException(status_code=404, detail="Film non trouvé")

    if film.status == ContentStatus.published:
        film.status = ContentStatus.draft
    else:
        film.status = ContentStatus.published

    await db.commit()
    await db.refresh(film)
    return film


@router.get("/series", response_model=ContentListResponse)
async def get_series(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Content).where(
        Content.type == ContentType.serie,
        Content.status == ContentStatus.published,
    )

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    series = result.scalars().all()

    return {"items": series, "total": total, "page": page, "limit": limit}


@router.get("/series/{content_id}", response_model=ContentResponse)
async def get_serie(content_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Content).where(
            Content.id == content_id,
            Content.type == ContentType.serie,
        )
    )
    serie = result.scalar_one_or_none()
    if not serie:
        raise HTTPException(status_code=404, detail="Série non trouvée")
    return serie


@router.post("/series", response_model=ContentResponse, status_code=201)
async def create_serie(
    data: ContentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    serie_data = data.model_dump()
    serie = Content(**serie_data, type=ContentType.serie, added_by=current_user.id)
    db.add(serie)
    await db.commit()
    await db.refresh(serie)
    return serie