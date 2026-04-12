from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime


# ─── Création / mise à jour ───────────────────────────────────────────────────

class EpisodeCreate(BaseModel):
    number: int
    title: str
    synopsis: Optional[str] = None
    is_free: bool = False


class EpisodeUpdate(BaseModel):
    title: Optional[str] = None
    synopsis: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_sec: Optional[int] = None
    is_free: Optional[bool] = None
    is_published: Optional[bool] = None


# ─── Réponse ──────────────────────────────────────────────────────────────────

class EpisodeResponse(BaseModel):
    id: UUID4
    season_id: UUID4
    number: int
    title: str
    synopsis: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_sec: Optional[int] = None
    is_free: bool
    is_published: bool
    view_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
