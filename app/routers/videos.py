from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.database import get_db
from app.deps import require_role
from app.models.user import User
from app.models.video import Video
from app.schemas.season_episode_video import VideoCreate, VideoResponse

router = APIRouter()


@router.get("/episodes/{episode_id}/videos", response_model=list[VideoResponse])
async def get_episode_videos(episode_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Video).where(Video.episode_id == episode_id))
    return result.scalars().all()


@router.post("/episodes/{episode_id}/videos", response_model=VideoResponse, status_code=201)
async def add_episode_video(
    episode_id: uuid.UUID,
    data: VideoCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    video = Video(**data.model_dump(), episode_id=episode_id)
    db.add(video)
    await db.commit()
    await db.refresh(video)
    return video


@router.put("/episodes/{episode_id}/videos/{video_id}", response_model=VideoResponse)
async def update_video(
    episode_id: uuid.UUID,
    video_id: uuid.UUID,
    data: VideoCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.episode_id == episode_id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo non trouvée")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(video, key, value)
    await db.commit()
    await db.refresh(video)
    return video


@router.delete("/episodes/{episode_id}/videos/{video_id}", status_code=204)
async def delete_video(
    episode_id: uuid.UUID,
    video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.episode_id == episode_id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo non trouvée")
    await db.delete(video)
    await db.commit()