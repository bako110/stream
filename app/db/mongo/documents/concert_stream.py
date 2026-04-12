"""
Document MongoDB — collection 'concert_streams'

Données de streaming live d'un concert, séparées de PostgreSQL car :
  - schéma variable selon le type (live RTMP, replay VOD, hybride)
  - analytics en temps réel (snapshots fréquents)
  - lien vers la vidéo de replay (MongoDB ObjectId)

Référence vers PostgreSQL :
  - concert_id → concerts.id  (index unique)
Référence vers MongoDB :
  - replay_video_id → videos._id (ObjectId string)
"""
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ViewerSnapshot(BaseModel):
    """Snapshot périodique du nombre de spectateurs (analytics live)."""
    timestamp: datetime
    viewers: int
    bitrate_kbps: Optional[int] = None


class ConcertStreamDocument(BaseModel):
    """Schéma d'un document de la collection 'concert_streams'."""

    concert_id: str                     # UUID string → concerts.id (PostgreSQL), index unique

    # ── Ingest RTMP (live) ───────────────────────────────────────────────────
    rtmp_key: Optional[str] = None      # clé secrète de stream (OBS, etc.)
    rtmp_url: Optional[str] = None      # URL rtmp://...

    # ── Diffusion HLS (live) ─────────────────────────────────────────────────
    live_hls_url: Optional[str] = None  # URL du manifest HLS live

    # ── Replay (après le live) ────────────────────────────────────────────────
    replay_video_id: Optional[str] = None   # ObjectId → videos._id (MongoDB)

    # ── Analytics ─────────────────────────────────────────────────────────────
    peak_viewers: int = 0
    current_viewers: int = 0
    total_view_time_sec: int = 0
    viewer_snapshots: list[ViewerSnapshot] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
