from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime


# ─── Season ──────────────────────────────────────────────────────────────────

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


# ─── Episode ─────────────────────────────────────────────────────────────────

class EpisodeCreate(BaseModel):
    number: int
    title: str
    synopsis: Optional[str] = None
    is_free: bool = False


class EpisodeUpdate(BaseModel):
    title: Optional[str] = None
    synopsis: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_free: Optional[bool] = None
    is_published: Optional[bool] = None


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


# ─── Video ───────────────────────────────────────────────────────────────────

class VideoCreate(BaseModel):
    label: str
    version: Optional[str] = None
    is_default: bool = False
    sort_order: int = 0
    is_free: bool = False


class VideoResponse(BaseModel):
    id: UUID4
    label: str
    version: Optional[str] = None
    hls_url: Optional[str] = None
    hls_480p_url: Optional[str] = None
    hls_720p_url: Optional[str] = None
    hls_1080p_url: Optional[str] = None
    duration_sec: Optional[int] = None
    transcode_status: str
    subtitles: Optional[list] = None
    is_default: bool
    is_free: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SubtitleTrack(BaseModel):
    lang: str
    label: str
    url_vtt: str