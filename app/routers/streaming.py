from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo.session import get_mongo
from app.deps import get_current_active_user
from app.db.postgres.models.user import User
from app.services.streaming_service import StreamingService

router = APIRouter()


@router.get("/{video_id}/manifest")
async def get_manifest(video_id: str, mongo: AsyncIOMotorDatabase = Depends(get_mongo), current_user: User = Depends(get_current_active_user)):
    return await StreamingService.get_manifest(video_id, mongo)


@router.post("/{video_id}/progress")
async def save_progress(video_id: str, progress_sec: int = Query(..., ge=0), mongo: AsyncIOMotorDatabase = Depends(get_mongo), current_user: User = Depends(get_current_active_user)):
    return await StreamingService.save_progress(video_id, progress_sec, current_user, mongo)


@router.get("/{video_id}/progress")
async def get_progress(video_id: str, mongo: AsyncIOMotorDatabase = Depends(get_mongo), current_user: User = Depends(get_current_active_user)):
    return await StreamingService.get_progress(video_id, current_user, mongo)
