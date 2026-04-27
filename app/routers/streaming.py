"""
Streaming router — LiveKit live concerts + VOD manifests.
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime

from app.db.postgres.session import get_db
from app.db.mongo.session import get_mongo
from app.deps import get_current_active_user
from app.db.postgres.models.user import User
from app.db.postgres.models.concert import Concert, ConcertStatus
from app.services.streaming_service import StreamingService
from app.services.livekit_service import LiveKitService
from app.utils.cache import cache_invalidate_prefix

router = APIRouter()


# ── VOD (existant) ────────────────────────────────────────────────────────────

@router.get("/{video_id}/manifest")
async def get_manifest(
    video_id: str,
    mongo: AsyncIOMotorDatabase = Depends(get_mongo),
    current_user: User = Depends(get_current_active_user),
):
    return await StreamingService.get_manifest(video_id, mongo)


@router.post("/{video_id}/progress")
async def save_progress(
    video_id: str,
    progress_sec: int,
    mongo: AsyncIOMotorDatabase = Depends(get_mongo),
    current_user: User = Depends(get_current_active_user),
):
    return await StreamingService.save_progress(video_id, progress_sec, current_user, mongo)


@router.get("/{video_id}/progress")
async def get_progress(
    video_id: str,
    mongo: AsyncIOMotorDatabase = Depends(get_mongo),
    current_user: User = Depends(get_current_active_user),
):
    return await StreamingService.get_progress(video_id, current_user, mongo)


# ── LiveKit — Concert live ────────────────────────────────────────────────────

@router.post("/{concert_id}/start")
async def start_stream(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo),
    current_user: User = Depends(get_current_active_user),
):
    """Artiste démarre le live : crée la room + renvoie un token publisher."""
    concert = await _get_owned_concert(concert_id, current_user, db)

    # Créer la room LiveKit
    room_info = await LiveKitService.create_room(
        str(concert_id),
        max_participants=concert.max_viewers or 0,
    )

    # Passer le concert en live
    concert.status = ConcertStatus.live
    await db.commit()

    # Mettre à jour MongoDB
    await mongo["concert_streams"].update_one(
        {"concert_id": str(concert_id)},
        {"$set": {
            "livekit_room": room_info["room_name"],
            "started_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }},
    )

    await cache_invalidate_prefix("concerts:")

    # Générer le token publisher pour l'artiste
    token = LiveKitService.generate_token(
        str(concert_id),
        str(current_user.id),
        current_user.display_name or current_user.username,
        is_publisher=True,
    )

    return {
        "token": token,
        "room_name": room_info["room_name"],
        "livekit_url": _ws_url(),
    }


@router.post("/{concert_id}/stop")
async def stop_stream(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo),
    current_user: User = Depends(get_current_active_user),
):
    """Artiste arrête le live : supprime la room, passe le concert en ended."""
    concert = await _get_owned_concert(concert_id, current_user, db)

    # Supprimer la room LiveKit
    try:
        await LiveKitService.delete_room(str(concert_id))
    except Exception:
        pass  # room peut déjà être fermée

    concert.status = ConcertStatus.ended
    await db.commit()

    await mongo["concert_streams"].update_one(
        {"concert_id": str(concert_id)},
        {"$set": {"ended_at": datetime.utcnow(), "updated_at": datetime.utcnow()}},
    )

    await cache_invalidate_prefix("concerts:")
    return {"status": "ended"}


@router.get("/{concert_id}/token")
async def get_viewer_token(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Viewer demande un token subscriber pour rejoindre le live."""
    result = await db.execute(select(Concert).where(Concert.id == concert_id))
    concert = result.scalar_one_or_none()
    if not concert:
        raise HTTPException(status_code=404, detail="Concert non trouvé")
    if concert.status != ConcertStatus.live:
        raise HTTPException(status_code=400, detail="Ce concert n'est pas en live")

    is_artist = concert.artist_id == current_user.id
    token = LiveKitService.generate_token(
        str(concert_id),
        str(current_user.id),
        current_user.display_name or current_user.username,
        is_publisher=is_artist,
    )

    return {
        "token": token,
        "room_name": f"concert-{concert_id}",
        "livekit_url": _ws_url(),
    }


@router.get("/{concert_id}/status")
async def get_stream_status(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo),
):
    """Statut du live : is_live, viewers, etc."""
    result = await db.execute(select(Concert).where(Concert.id == concert_id))
    concert = result.scalar_one_or_none()
    if not concert:
        raise HTTPException(status_code=404, detail="Concert non trouvé")

    current_viewers = 0
    if concert.status == ConcertStatus.live:
        try:
            current_viewers = await LiveKitService.list_participants(str(concert_id))
        except Exception:
            pass
        # Update viewer count in PG
        await db.execute(
            update(Concert)
            .where(Concert.id == concert_id)
            .values(current_viewers=current_viewers)
        )
        await db.commit()

    stream_doc = await mongo["concert_streams"].find_one({"concert_id": str(concert_id)})

    return {
        "is_live": concert.status == ConcertStatus.live,
        "current_viewers": current_viewers,
        "started_at": stream_doc.get("started_at") if stream_doc else None,
        "livekit_url": _ws_url() if concert.status == ConcertStatus.live else None,
    }


@router.get("/{concert_id}/analytics")
async def get_stream_analytics(
    concert_id: uuid.UUID,
    mongo: AsyncIOMotorDatabase = Depends(get_mongo),
    current_user: User = Depends(get_current_active_user),
):
    """Analytics du stream (artiste)."""
    doc = await mongo["concert_streams"].find_one({"concert_id": str(concert_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Données de streaming non trouvées")
    return {
        "peak_viewers": doc.get("peak_viewers", 0),
        "total_view_time_sec": doc.get("total_view_time_sec", 0),
        "viewer_snapshots": doc.get("viewer_snapshots", []),
        "started_at": doc.get("started_at"),
        "ended_at": doc.get("ended_at"),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_owned_concert(concert_id: uuid.UUID, user: User, db: AsyncSession) -> Concert:
    result = await db.execute(select(Concert).where(Concert.id == concert_id))
    concert = result.scalar_one_or_none()
    if not concert:
        raise HTTPException(status_code=404, detail="Concert non trouvé")
    role = user.role.value if hasattr(user.role, 'value') else user.role
    if concert.artist_id != user.id and role != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé")
    return concert


def _ws_url() -> str:
    """Convertit l'URL HTTP LiveKit en WSS pour le client."""
    url = settings.LIVEKIT_URL
    if url.startswith("https://"):
        return url.replace("https://", "wss://")
    if url.startswith("http://"):
        return url.replace("http://", "ws://")
    return url


from app.config import settings
