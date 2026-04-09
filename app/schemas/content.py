from pydantic import BaseModel, UUID4
from typing import Optional, Any
from datetime import datetime
from app.models.content import ContentType, ContentStatus


class ContentCreate(BaseModel):
    title: str
    original_title: Optional[str] = None
    year: int
    synopsis: Optional[str] = None
    short_synopsis: Optional[str] = None
    director: Optional[str] = None
    cast: Optional[Any] = None
    language: str = "fr"
    country: Optional[str] = None
    rating: Optional[str] = None
    is_premium: bool = False
    price: Optional[float] = None
    status: ContentStatus = ContentStatus.draft


class ContentUpdate(BaseModel):
    title: Optional[str] = None
    synopsis: Optional[str] = None
    short_synopsis: Optional[str] = None
    director: Optional[str] = None
    cast: Optional[Any] = None
    rating: Optional[str] = None
    is_premium: Optional[bool] = None
    price: Optional[float] = None
    status: Optional[ContentStatus] = None
    thumbnail_url: Optional[str] = None
    banner_url: Optional[str] = None
    trailer_url: Optional[str] = None


class ContentResponse(BaseModel):
    id: UUID4
    type: ContentType
    title: str
    original_title: Optional[str] = None
    year: int
    synopsis: Optional[str] = None
    short_synopsis: Optional[str] = None
    director: Optional[str] = None
    cast: Optional[Any] = None
    language: str
    country: Optional[str] = None
    rating: Optional[str] = None
    thumbnail_url: Optional[str] = None
    banner_url: Optional[str] = None
    trailer_url: Optional[str] = None
    is_premium: bool
    price: Optional[float] = None
    status: ContentStatus
    total_seasons: int
    view_count: int
    average_rating: Optional[float] = None
    published_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ContentListResponse(BaseModel):
    items: list[ContentResponse]
    total: int
    page: int
    limit: int  