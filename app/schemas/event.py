from pydantic import BaseModel, UUID4, field_validator
from typing import Optional, Union, List
from datetime import datetime
from decimal import Decimal

from app.db.postgres.models.event import EventType, EventStatus, EventAccessType
from app.db.postgres.models.ticket import TicketStatus
from app.schemas.user import UserPublic


# ─── Événement ────────────────────────────────────────────────────────────────

class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    event_type: EventType
    access_type: EventAccessType = EventAccessType.free
    venue_name: Optional[str] = None
    venue_address: Optional[str] = None
    venue_city: str
    venue_country: str
    is_online: bool = False
    online_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    starts_at: Union[datetime, str]
    ends_at: Optional[Union[datetime, str]] = None
    ticket_price: Optional[Decimal] = None
    max_attendees: Optional[int] = None
    thumbnail_url: Optional[str] = None
    banner_url: Optional[str] = None
    gallery_urls: Optional[List[str]] = None
    video_url: Optional[str] = None

    @field_validator('starts_at', 'ends_at', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.replace(tzinfo=None) if v.tzinfo else v
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
                return dt.replace(tzinfo=None)
            except ValueError:
                raise ValueError(f'Invalid datetime format: {v}')
        return v


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    venue_name: Optional[str] = None
    venue_address: Optional[str] = None
    venue_city: Optional[str] = None
    venue_country: Optional[str] = None
    is_online: Optional[bool] = None
    online_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    ticket_price: Optional[Decimal] = None
    max_attendees: Optional[int] = None
    thumbnail_url: Optional[str] = None
    banner_url: Optional[str] = None
    gallery_urls: Optional[List[str]] = None
    video_url: Optional[str] = None
    status: Optional[EventStatus] = None


class EventResponse(BaseModel):
    id: UUID4
    organizer_id: UUID4
    title: str
    description: Optional[str] = None
    event_type: EventType
    status: EventStatus
    access_type: EventAccessType
    venue_name: Optional[str] = None
    venue_address: Optional[str] = None
    venue_city: str
    venue_country: str
    is_online: bool
    online_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    starts_at: datetime
    ends_at: Optional[datetime] = None
    ticket_price: Optional[Decimal] = None
    max_attendees: Optional[int] = None
    current_attendees: int
    thumbnail_url: Optional[str] = None
    banner_url: Optional[str] = None
    gallery_urls: Optional[List[str]] = None
    video_url: Optional[str] = None
    is_featured: bool
    published_at: Optional[datetime] = None
    created_at: datetime
    organizer: Optional["UserPublic"] = None

    model_config = {"from_attributes": True}


class EventListItem(BaseModel):
    id: UUID4
    organizer_id: UUID4
    title: str
    description: Optional[str] = None
    event_type: EventType
    status: EventStatus
    access_type: EventAccessType
    venue_name: Optional[str] = None
    venue_city: str
    venue_country: str
    is_online: bool
    online_url: Optional[str] = None
    starts_at: datetime
    ends_at: Optional[datetime] = None
    ticket_price: Optional[Decimal] = None
    current_attendees: int
    max_attendees: Optional[int] = None
    thumbnail_url: Optional[str] = None
    banner_url: Optional[str] = None
    gallery_urls: Optional[List[str]] = None
    is_featured: bool
    created_at: datetime
    organizer: Optional["UserPublic"] = None

    model_config = {"from_attributes": True}


# ─── Billet événement ─────────────────────────────────────────────────────────

class EventTicketCreate(BaseModel):
    event_id: UUID4


class EventTicketResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    event_id: UUID4
    payment_id: Optional[UUID4] = None
    status: TicketStatus
    price_paid: Decimal
    currency: str
    access_code: str
    used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
