"""
Document MongoDB — collection 'watch_history'

Un document par (user_id × video_id) — index unique.
Volume très élevé : idéal pour MongoDB plutôt que PostgreSQL.

Référence vers PostgreSQL :
  - user_id     → users.id
  - content_id  → contents.id  (optionnel, pour filtres rapides)
  - concert_id  → concerts.id  (optionnel, pour filtres rapides)
Référence vers MongoDB :
  - video_id    → videos._id (ObjectId string)
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class WatchHistoryDocument(BaseModel):
    """Schéma d'un document de la collection 'watch_history'."""

    # Références
    user_id: str                        # UUID string → users.id (PostgreSQL)
    video_id: str                       # ObjectId string → videos._id (MongoDB)
    content_id: Optional[str] = None    # UUID string → contents.id (PostgreSQL)
    concert_id: Optional[str] = None    # UUID string → concerts.id (PostgreSQL)

    # Progression de lecture
    watched_seconds: int = Field(default=0, ge=0)
    total_seconds: Optional[int] = None
    completed: bool = False

    # Position de reprise (pour le bouton "Continuer à regarder")
    last_position_sec: int = Field(default=0, ge=0)

    # Qualité choisie : "480p", "720p", "1080p"
    quality_watched: Optional[str] = None

    last_watched_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
