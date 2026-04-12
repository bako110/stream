import uuid
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import HTTPException

from app.db.postgres.models.user import User


class StreamingService:

    @staticmethod
    def _oid(video_id: str) -> ObjectId:
        try:
            return ObjectId(video_id)
        except Exception:
            raise HTTPException(status_code=400, detail="ID vidéo invalide")

    @staticmethod
    async def get_manifest(video_id: str, mongo: AsyncIOMotorDatabase) -> dict:
        doc = await mongo["videos"].find_one({"_id": StreamingService._oid(video_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Vidéo non trouvée")
        if not doc.get("hls_url"):
            raise HTTPException(status_code=404, detail="Vidéo non disponible (transcodage en cours)")
        return {
            "manifest_url": doc["hls_url"],
            "hls_480p_url": doc.get("hls_480p_url"),
            "hls_720p_url": doc.get("hls_720p_url"),
            "hls_1080p_url": doc.get("hls_1080p_url"),
            "duration_sec": doc.get("duration_sec"),
            "subtitles": doc.get("subtitles", []),
        }

    @staticmethod
    async def save_progress(video_id: str, progress_sec: int, user: User, mongo: AsyncIOMotorDatabase) -> dict:
        now = datetime.utcnow()
        await mongo["watch_history"].update_one(
            {"user_id": str(user.id), "video_id": video_id},
            {
                "$set": {"last_position_sec": progress_sec, "last_watched_at": now},
                "$setOnInsert": {
                    "user_id": str(user.id), "video_id": video_id,
                    "watched_seconds": 0, "completed": False,
                    "quality_watched": None, "created_at": now,
                },
            },
            upsert=True,
        )
        return {"status": "saved", "progress_sec": progress_sec}

    @staticmethod
    async def get_progress(video_id: str, user: User, mongo: AsyncIOMotorDatabase) -> dict:
        doc = await mongo["watch_history"].find_one({"user_id": str(user.id), "video_id": video_id})
        return {"progress_sec": doc["last_position_sec"] if doc else 0}
