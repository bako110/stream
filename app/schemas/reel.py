from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime

from app.db.postgres.models.reel import ReelStatus


class ReelCreate(BaseModel):
    caption: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_sec: Optional[int] = None
    ref_content_id: Optional[UUID4] = None
    ref_concert_id: Optional[UUID4] = None
    ref_event_id: Optional[UUID4] = None


class ReelUpdate(BaseModel):
    caption: Optional[str] = None
    thumbnail_url: Optional[str] = None
    video_url: Optional[str] = None
    status: Optional[ReelStatus] = None


class ReelResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    caption: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_sec: Optional[int] = None
    status: ReelStatus
    view_count: int
    like_count: int
    dislike_count: int
    comment_count: int
    share_count: int
    is_featured: bool
    ref_content_id: Optional[UUID4] = None
    ref_concert_id: Optional[UUID4] = None
    ref_event_id: Optional[UUID4] = None
    created_at: datetime

    model_config = {"from_attributes": True}
