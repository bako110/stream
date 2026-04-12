"""
Document MongoDB — collection 'videos'

Stocke les données lourdes liées à une vidéo :
  - URLs HLS multi-qualité (480p / 720p / 1080p)
  - Clé S3 du fichier source brut
  - Statut et progression du transcodage
  - Pistes de sous-titres (VTT)

Référence vers PostgreSQL :
  - content_id  → contents.id  (film ou série)
  - episode_id  → episodes.id  (épisode d'une série)
"""
import enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class VideoVersion(str, enum.Enum):
    vo = "vo"
    vf = "vf"
    vost = "vost"
    extended = "extended"


class TranscodeStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    error = "error"


class SubtitleTrack(BaseModel):
    lang: str                   # "fr", "en"...
    label: str                  # "Français", "English"
    url_vtt: str                # URL publique du fichier VTT


class VideoDocument(BaseModel):
    """Schéma d'un document de la collection 'videos'."""

    # Référence parent PostgreSQL (l'un ou l'autre, jamais les deux)
    content_id: Optional[str] = None    # UUID string → contents.id
    episode_id: Optional[str] = None    # UUID string → episodes.id

    label: str                           # "Version VO", "VF Director's Cut"...
    version: Optional[VideoVersion] = None
    is_default: bool = False
    sort_order: int = 0
    is_free: bool = False

    # Fichier source (S3/MinIO)
    raw_s3_key: Optional[str] = None
    file_size_bytes: Optional[int] = None
    original_filename: Optional[str] = None

    # Sorties HLS après transcodage
    hls_url: Optional[str] = None        # manifest maître
    hls_480p_url: Optional[str] = None
    hls_720p_url: Optional[str] = None
    hls_1080p_url: Optional[str] = None
    duration_sec: Optional[int] = None

    # Transcodage
    transcode_status: TranscodeStatus = TranscodeStatus.pending
    transcode_error: Optional[str] = None
    transcode_progress: int = Field(default=0, ge=0, le=100)  # %

    # Sous-titres
    subtitles: list[SubtitleTrack] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"use_enum_values": True}
