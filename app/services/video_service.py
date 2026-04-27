import uuid
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import HTTPException

from app.db.mongo.documents.video import VideoDocument
from app.schemas.video import VideoCreate


class VideoService:

    @staticmethod
    def _serialize(doc: dict) -> dict:
        doc["id"] = str(doc.pop("_id"))
        return doc

    @staticmethod
    def _oid(video_id: str) -> ObjectId:
        try:
            return ObjectId(video_id)
        except Exception:
            raise HTTPException(status_code=400, detail="ID vidéo invalide")

    @staticmethod
    async def get_videos_for_content(content_id: uuid.UUID, mongo: AsyncIOMotorDatabase) -> list:
        cursor = mongo["videos"].find({"content_id": str(content_id)}).sort("sort_order", 1)
        return [VideoService._serialize(doc) async for doc in cursor]

    @staticmethod
    async def get_videos_for_episode(episode_id: uuid.UUID, mongo: AsyncIOMotorDatabase) -> list:
        cursor = mongo["videos"].find({"episode_id": str(episode_id)}).sort("sort_order", 1)
        return [VideoService._serialize(doc) async for doc in cursor]

    @staticmethod
    async def get_video(video_id: str, mongo: AsyncIOMotorDatabase) -> dict:
        doc = await mongo["videos"].find_one({"_id": VideoService._oid(video_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Vidéo non trouvée")
        return VideoService._serialize(doc)

    @staticmethod
    async def _insert(base: dict, data: VideoCreate, mongo: AsyncIOMotorDatabase) -> dict:
        payload = data.model_dump()
        doc = {
            **base,
            "transcode_status": "done" if payload.get("hls_url") else "pending",
            "transcode_progress": 100 if payload.get("hls_url") else 0,
            "hls_480p_url": None,
            "hls_720p_url": None, "hls_1080p_url": None,
            "raw_s3_key": None, "file_size_bytes": None, "original_filename": None,
            "subtitles": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            **payload,
        }
        result = await mongo["videos"].insert_one(doc)
        doc["_id"] = result.inserted_id
        return VideoService._serialize(doc)

    @staticmethod
    async def create_video_for_content(content_id: uuid.UUID, data: VideoCreate, mongo: AsyncIOMotorDatabase) -> dict:
        return await VideoService._insert({"content_id": str(content_id), "episode_id": None}, data, mongo)

    @staticmethod
    async def create_video_for_episode(episode_id: uuid.UUID, data: VideoCreate, mongo: AsyncIOMotorDatabase) -> dict:
        return await VideoService._insert({"content_id": None, "episode_id": str(episode_id)}, data, mongo)

    @staticmethod
    async def update_video(video_id: str, data: VideoCreate, mongo: AsyncIOMotorDatabase) -> dict:
        updated = await mongo["videos"].find_one_and_update(
            {"_id": VideoService._oid(video_id)},
            {"$set": {**data.model_dump(exclude_unset=True), "updated_at": datetime.utcnow()}},
            return_document=True,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Vidéo non trouvée")
        return VideoService._serialize(updated)

    @staticmethod
    async def delete_video(video_id: str, mongo: AsyncIOMotorDatabase) -> None:
        result = await mongo["videos"].delete_one({"_id": VideoService._oid(video_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Vidéo non trouvée")
