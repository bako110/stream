from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime


# ─── Création / mise à jour ───────────────────────────────────────────────────

class SeasonCreate(BaseModel):
    number: int
    title: Optional[str] = None
    synopsis: Optional[str] = None
    year: Optional[int] = None


class SeasonUpdate(BaseModel):
    title: Optional[str] = None
    synopsis: Optional[str] = None
    year: Optional[int] = None
    thumbnail_url: Optional[str] = None


# ─── Réponse ──────────────────────────────────────────────────────────────────

class SeasonResponse(BaseModel):
    id: UUID4
    content_id: UUID4
    number: int
    title: Optional[str] = None
    synopsis: Optional[str] = None
    year: Optional[int] = None
    thumbnail_url: Optional[str] = None
    total_episodes: int
    created_at: datetime

    model_config = {"from_attributes": True}
