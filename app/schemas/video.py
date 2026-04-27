"""
Schémas Pydantic pour les vidéos stockées dans MongoDB.

- VideoCreate  : données saisies par l'admin pour créer/mettre à jour une vidéo
- VideoResponse: ce que l'API renvoie (inclut l'_id MongoDB converti en 'id' string)
- SubtitleTrack: piste de sous-titres VTT
- TranscodeStatusUpdate : mise à jour du statut de transcodage (webhook Celery)
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.db.mongo.documents.video import VideoVersion, TranscodeStatus


# ─── Sous-schémas ─────────────────────────────────────────────────────────────

class SubtitleTrack(BaseModel):
    lang: str           # "fr", "en", "es"
    label: str          # "Français", "English"
    url_vtt: str        # URL publique du fichier WebVTT


# ─── Création ─────────────────────────────────────────────────────────────────

class VideoCreate(BaseModel):
    label: str                              # "Version VO", "VF", "Director's Cut"
    version: Optional[VideoVersion] = None
    is_default: bool = False
    sort_order: int = 0
    is_free: bool = False
    hls_url: Optional[str] = None
    duration_sec: Optional[int] = None


# ─── Mise à jour partielle ────────────────────────────────────────────────────

class VideoUpdate(BaseModel):
    label: Optional[str] = None
    version: Optional[VideoVersion] = None
    is_default: Optional[bool] = None
    sort_order: Optional[int] = None
    is_free: Optional[bool] = None
    hls_url: Optional[str] = None
    hls_480p_url: Optional[str] = None
    hls_720p_url: Optional[str] = None
    hls_1080p_url: Optional[str] = None
    duration_sec: Optional[int] = None
    subtitles: Optional[list[SubtitleTrack]] = None


# ─── Mise à jour transcodage (webhook Celery / worker) ───────────────────────

class TranscodeStatusUpdate(BaseModel):
    transcode_status: TranscodeStatus
    transcode_progress: int = Field(default=0, ge=0, le=100)
    transcode_error: Optional[str] = None
    hls_url: Optional[str] = None
    hls_480p_url: Optional[str] = None
    hls_720p_url: Optional[str] = None
    hls_1080p_url: Optional[str] = None
    duration_sec: Optional[int] = None


# ─── Réponse ──────────────────────────────────────────────────────────────────

class VideoResponse(BaseModel):
    """
    Réponse API pour une vidéo MongoDB.
    'id' est l'ObjectId MongoDB converti en string par le service.
    """
    id: str                                 # ObjectId MongoDB → string

    content_id: Optional[str] = None        # UUID string → contents.id (PostgreSQL)
    episode_id: Optional[str] = None        # UUID string → episodes.id (PostgreSQL)

    label: str
    version: Optional[VideoVersion] = None
    is_default: bool
    sort_order: int
    is_free: bool

    # S3
    raw_s3_key: Optional[str] = None
    file_size_bytes: Optional[int] = None
    original_filename: Optional[str] = None

    # HLS
    hls_url: Optional[str] = None
    hls_480p_url: Optional[str] = None
    hls_720p_url: Optional[str] = None
    hls_1080p_url: Optional[str] = None
    duration_sec: Optional[int] = None

    # Transcodage
    transcode_status: TranscodeStatus
    transcode_progress: int
    transcode_error: Optional[str] = None

    subtitles: list[SubtitleTrack] = []

    created_at: datetime
    updated_at: datetime
