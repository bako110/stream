import uuid
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo.session import get_mongo
from app.deps import require_role, get_current_active_user
from app.db.postgres.models.user import User
from app.schemas.video import VideoCreate
from app.services.video_service import VideoService

router = APIRouter()


@router.get("/content/{content_id}/videos")
async def get_content_videos(content_id: uuid.UUID, mongo: AsyncIOMotorDatabase = Depends(get_mongo)):
    return await VideoService.get_videos_for_content(content_id, mongo)


@router.post("/content/{content_id}/videos", status_code=201)
async def add_content_video(content_id: uuid.UUID, data: VideoCreate, mongo: AsyncIOMotorDatabase = Depends(get_mongo), _: User = Depends(require_role("admin"))):
    return await VideoService.create_video_for_content(content_id, data, mongo)


@router.get("/episodes/{episode_id}/videos")
async def get_episode_videos(episode_id: uuid.UUID, mongo: AsyncIOMotorDatabase = Depends(get_mongo)):
    return await VideoService.get_videos_for_episode(episode_id, mongo)


@router.post("/episodes/{episode_id}/videos", status_code=201)
async def add_episode_video(episode_id: uuid.UUID, data: VideoCreate, mongo: AsyncIOMotorDatabase = Depends(get_mongo), _: User = Depends(require_role("admin"))):
    return await VideoService.create_video_for_episode(episode_id, data, mongo)


@router.get("/videos/{video_id}")
async def get_video(video_id: str, mongo: AsyncIOMotorDatabase = Depends(get_mongo), _: User = Depends(get_current_active_user)):
    return await VideoService.get_video(video_id, mongo)


@router.put("/videos/{video_id}")
async def update_video(video_id: str, data: VideoCreate, mongo: AsyncIOMotorDatabase = Depends(get_mongo), _: User = Depends(require_role("admin"))):
    return await VideoService.update_video(video_id, data, mongo)


@router.delete("/videos/{video_id}", status_code=204)
async def delete_video(video_id: str, mongo: AsyncIOMotorDatabase = Depends(get_mongo), _: User = Depends(require_role("admin"))):
    await VideoService.delete_video(video_id, mongo)
