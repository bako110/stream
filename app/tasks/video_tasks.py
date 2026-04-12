"""
Tâches de transcodage vidéo.
Déclenchées après l'upload d'un fichier brut sur S3/MinIO.
"""
import asyncio
from datetime import datetime
from bson import ObjectId

from app.tasks.celery_app import celery_app


def _get_mongo_db():
    """Connexion Motor synchrone pour les tâches Celery (contexte sync)."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from app.config import settings
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    return client[settings.MONGODB_DB_NAME]


def _run(coro):
    """Exécute une coroutine dans un event loop Celery."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def transcode_video(self, video_id: str, raw_s3_key: str):
    """
    Transcodage HLS multi-qualité après upload.
    Simule les étapes : pending → processing → done.
    En production : appel FFmpeg ou service AWS MediaConvert.
    """
    db = _get_mongo_db()

    async def _run_task():
        oid = ObjectId(video_id)

        # Marquer comme en cours
        await db["videos"].update_one(
            {"_id": oid},
            {"$set": {
                "transcode_status": "processing",
                "transcode_progress": 0,
                "updated_at": datetime.utcnow(),
            }},
        )

        # Simulation des étapes de progression
        for progress in [10, 25, 50, 75, 90]:
            await db["videos"].update_one(
                {"_id": oid},
                {"$set": {"transcode_progress": progress, "updated_at": datetime.utcnow()}},
            )

        # En production : ici on appelle FFmpeg / MediaConvert
        # et on récupère les vraies URLs HLS
        from app.config import settings
        base_url = f"{settings.CDN_BASE_URL}/hls/{video_id}"

        await db["videos"].update_one(
            {"_id": oid},
            {"$set": {
                "transcode_status": "done",
                "transcode_progress": 100,
                "hls_url": f"{base_url}/master.m3u8",
                "hls_480p_url": f"{base_url}/480p.m3u8",
                "hls_720p_url": f"{base_url}/720p.m3u8",
                "hls_1080p_url": f"{base_url}/1080p.m3u8",
                "updated_at": datetime.utcnow(),
            }},
        )

    try:
        _run(_run_task())
    except Exception as exc:
        # Marquer l'erreur en base
        async def _mark_error():
            await db["videos"].update_one(
                {"_id": ObjectId(video_id)},
                {"$set": {
                    "transcode_status": "error",
                    "transcode_error": str(exc),
                    "updated_at": datetime.utcnow(),
                }},
            )
        _run(_mark_error())
        raise self.retry(exc=exc)


@celery_app.task
def process_reel_video(reel_id: str, raw_video_url: str):
    """
    Traitement d'un reel après upload :
    - Génération de la miniature
    - Compression/optimisation
    - Mise à jour du statut vers 'published'
    """
    from sqlalchemy import create_engine
    from app.config import settings

    async def _run_task():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from sqlalchemy import select, update
        import uuid
        from app.db.postgres.models.reel import Reel, ReelStatus

        engine = create_async_engine(settings.DATABASE_URL)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with Session() as session:
            result = await session.execute(
                select(Reel).where(Reel.id == uuid.UUID(reel_id))
            )
            reel = result.scalar_one_or_none()
            if reel:
                reel.video_url = raw_video_url  # En prod : URL compressée
                reel.status = ReelStatus.published
                await session.commit()

        await engine.dispose()

    _run(_run_task())
