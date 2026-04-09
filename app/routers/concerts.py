from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import datetime
import uuid

from app.database import get_db
from app.deps import get_current_active_user, require_role
from app.models.user import User
from app.models.concert import Concert, ConcertStatus
from app.schemas.concert import (
    ConcertCreate, ConcertUpdate, ConcertResponse, ConcertList
)

router = APIRouter()


@router.get("", response_model=ConcertList)
async def get_concerts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    genre: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Concert).where(Concert.status == ConcertStatus.published)
    if genre:
        query = query.where(Concert.genre == genre)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    return {"items": result.scalars().all(), "total": total, "page": page, "limit": limit}


@router.get("/live", response_model=list[ConcertResponse])
async def get_live_concerts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Concert).where(Concert.status == ConcertStatus.live)
    )
    return result.scalars().all()


@router.get("/upcoming", response_model=list[ConcertResponse])
async def get_upcoming_concerts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Concert)
        .where(
            Concert.status == ConcertStatus.published,
            Concert.scheduled_at > datetime.utcnow(),
        )
        .order_by(Concert.scheduled_at)
        .limit(20)
    )
    return result.scalars().all()


@router.get("/{concert_id}", response_model=ConcertResponse)
async def get_concert(concert_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Concert).where(Concert.id == concert_id))
    concert = result.scalar_one_or_none()
    if not concert:
        raise HTTPException(status_code=404, detail="Concert non trouvé")
    return concert


@router.post("", response_model=ConcertResponse, status_code=201)
async def create_concert(
    data: ConcertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("artist", "admin")),
):
    concert = Concert(**data.model_dump(), artist_id=current_user.id)
    db.add(concert)
    await db.commit()
    await db.refresh(concert)
    return concert


@router.put("/{concert_id}", response_model=ConcertResponse)
async def update_concert(
    concert_id: uuid.UUID,
    data: ConcertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(select(Concert).where(Concert.id == concert_id))
    concert = result.scalar_one_or_none()
    if not concert:
        raise HTTPException(status_code=404, detail="Concert non trouvé")
    if concert.artist_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(concert, key, value)

    await db.commit()
    await db.refresh(concert)
    return concert


@router.delete("/{concert_id}", status_code=204)
async def delete_concert(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(select(Concert).where(Concert.id == concert_id))
    concert = result.scalar_one_or_none()
    if not concert:
        raise HTTPException(status_code=404, detail="Concert non trouvé")
    if concert.artist_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")
    await db.delete(concert)
    await db.commit()


@router.patch("/{concert_id}/publish", response_model=ConcertResponse)
async def publish_concert(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(select(Concert).where(Concert.id == concert_id))
    concert = result.scalar_one_or_none()
    if not concert:
        raise HTTPException(status_code=404, detail="Concert non trouvé")
    if concert.artist_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")
    concert.status = ConcertStatus.published
    concert.published_at = datetime.utcnow()
    await db.commit()
    await db.refresh(concert)
    return concert


@router.patch("/{concert_id}/start-live", response_model=ConcertResponse)
async def start_live(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(select(Concert).where(Concert.id == concert_id))
    concert = result.scalar_one_or_none()
    if not concert:
        raise HTTPException(status_code=404, detail="Concert non trouvé")
    if concert.artist_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")
    concert.status = ConcertStatus.live
    await db.commit()
    await db.refresh(concert)
    return concert


@router.patch("/{concert_id}/end-live", response_model=ConcertResponse)
async def end_live(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(select(Concert).where(Concert.id == concert_id))
    concert = result.scalar_one_or_none()
    if not concert:
        raise HTTPException(status_code=404, detail="Concert non trouvé")
    if concert.artist_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")
    concert.status = ConcertStatus.ended
    await db.commit()
    await db.refresh(concert)
    return concert