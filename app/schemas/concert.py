from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime
from decimal import Decimal

from app.db.postgres.models.concert import ConcertType, AccessType, ConcertStatus
from app.schemas.user import UserPublic


# ─── Création / mise à jour ───────────────────────────────────────────────────

class ConcertCreate(BaseModel):
    title: str
    description: Optional[str] = None
    genre: Optional[str] = None
    venue_name: Optional[str] = None
    venue_city: Optional[str] = None
    venue_country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    scheduled_at: datetime
    duration_min: Optional[int] = None
    concert_type: ConcertType
    access_type: AccessType = AccessType.free
    ticket_price: Optional[Decimal] = None
    max_viewers: Optional[int] = None
    thumbnail_url: Optional[str] = None
    banner_url: Optional[str] = None
    video_url: Optional[str] = None


class ConcertUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    venue_name: Optional[str] = None
    venue_city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    scheduled_at: Optional[datetime] = None
    duration_min: Optional[int] = None
    ticket_price: Optional[Decimal] = None
    max_viewers: Optional[int] = None
    thumbnail_url: Optional[str] = None
    banner_url: Optional[str] = None
    video_url: Optional[str] = None
    status: Optional[ConcertStatus] = None


# ─── Réponses ─────────────────────────────────────────────────────────────────

class ConcertResponse(BaseModel):
    """Réponse complète d'un concert."""
    id: UUID4
    artist_id: UUID4
    title: str
    description: Optional[str] = None
    genre: Optional[str] = None
    venue_name: Optional[str] = None
    venue_city: Optional[str] = None
    venue_country: Optional[str] = None
    scheduled_at: datetime
    duration_min: Optional[int] = None
    concert_type: ConcertType
    access_type: AccessType
    status: ConcertStatus
    ticket_price: Optional[Decimal] = None
    max_viewers: Optional[int] = None
    current_viewers: int
    view_count: int
    thumbnail_url: Optional[str] = None
    banner_url: Optional[str] = None
    video_url: Optional[str] = None
    is_featured: bool
    published_at: Optional[datetime] = None
    created_at: datetime
    artist: Optional["UserPublic"] = None

    model_config = {"from_attributes": True}


class ConcertListItem(BaseModel):
    """Item dans une liste paginée de concerts — champs essentiels seulement."""
    id: UUID4
    artist_id: UUID4
    title: str
    description: Optional[str] = None
    genre: Optional[str] = None
    venue_name: Optional[str] = None
    venue_city: Optional[str] = None
    venue_country: Optional[str] = None
    scheduled_at: datetime
    concert_type: ConcertType
    access_type: AccessType
    status: ConcertStatus
    ticket_price: Optional[Decimal] = None
    thumbnail_url: Optional[str] = None
    is_featured: bool
    created_at: datetime
    artist: Optional["UserPublic"] = None

    model_config = {"from_attributes": True}


class ConcertListResponse(BaseModel):
    """Réponse paginée pour les listes de concerts."""
    items: list[ConcertListItem]
    total: int
    page: int
    limit: int
