from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime

from app.db.postgres.models.story import StoryMediaType


class StoryCreate(BaseModel):
    media_url: Optional[str] = None
    media_type: StoryMediaType = StoryMediaType.image
    thumbnail_url: Optional[str] = None
    caption: Optional[str] = None
    duration_sec: int = 5
    background_color: Optional[str] = None
    audio_url: Optional[str] = None
    font_style: Optional[str] = None


class StoryUpdate(BaseModel):
    caption: Optional[str] = None
    background_color: Optional[str] = None
    duration_sec: Optional[int] = None
    font_style: Optional[str] = None


class StoryAuthor(BaseModel):
    id: UUID4
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

    model_config = {"from_attributes": True}


class StoryResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    media_url: Optional[str] = None
    media_type: StoryMediaType
    thumbnail_url: Optional[str] = None
    caption: Optional[str] = None
    duration_sec: int
    view_count: int
    is_active: bool
    expires_at: datetime
    created_at: datetime
    background_color: Optional[str] = None
    audio_url: Optional[str] = None
    font_style: Optional[str] = None
    author: Optional[StoryAuthor] = None
    viewed_by_me: bool = False  # injecté par le service

    model_config = {"from_attributes": True}


class StoryGroupResponse(BaseModel):
    """Groupe de stories d'un utilisateur (comme WhatsApp)"""
    user: StoryAuthor
    stories: list[StoryResponse]
    has_unseen: bool  # au moins une story non vue


class StoryViewerResponse(BaseModel):
    id: UUID4
    username: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    viewed_at: datetime

    model_config = {"from_attributes": True}
