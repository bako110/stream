from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.video import Video
from app.models.watch_history import WatchHistory

router = APIRouter()


@router.get("/{video_id}/manifest")
async def get_manifest(
    video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo non trouvée")
    if not video.hls_url:
        raise HTTPException(status_code=404, detail="Vidéo non disponible")
    return {"manifest_url": video.hls_url}


@router.post("/{video_id}/progress")
async def save_progress(
    video_id: uuid.UUID,
    progress_sec: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(WatchHistory).where(
            WatchHistory.video_id == video_id,
            WatchHistory.user_id == current_user.id,
        )
    )
    history = result.scalar_one_or_none()
    if history:
        history.progress_sec = progress_sec
    else:
        history = WatchHistory(
            user_id=current_user.id,
            video_id=video_id,
            progress_sec=progress_sec,
        )
        db.add(history)
    await db.commit()
    return {"status": "saved", "progress_sec": progress_sec}


@router.get("/{video_id}/progress")
async def get_progress(
    video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(WatchHistory).where(
            WatchHistory.video_id == video_id,
            WatchHistory.user_id == current_user.id,
        )
    )
    history = result.scalar_one_or_none()
    return {"progress_sec": history.progress_sec if history else 0}