import uuid
from sqlalchemy import String, Integer, Boolean, Enum, ForeignKey, DateTime, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import enum

from app.database import Base


class VideoVersion(str, enum.Enum):
    vo = "vo"
    vf = "vf"
    vost = "vost"
    extended = "extended"


class TranscodeStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    error = "error"


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Lié soit à un film (Content), soit à un épisode
    content_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contents.id", ondelete="CASCADE"), nullable=True
    )
    episode_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=True
    )

    label: Mapped[str] = mapped_column(String(100), nullable=False)  # "Version VO", "VF"...
    version: Mapped[VideoVersion | None] = mapped_column(Enum(VideoVersion), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_free: Mapped[bool] = mapped_column(Boolean, default=False)

    # Fichier source
    raw_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # HLS après transcoding
    hls_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hls_480p_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hls_720p_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hls_1080p_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)

    transcode_status: Mapped[TranscodeStatus] = mapped_column(
        Enum(TranscodeStatus), default=TranscodeStatus.pending
    )
    transcode_error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Sous-titres : [{"lang": "fr", "label": "Français", "url_vtt": "..."}]
    subtitles: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relations
    content: Mapped["Content"] = relationship("Content", back_populates="videos")
    episode: Mapped["Episode"] = relationship("Episode", back_populates="videos")

    def __repr__(self):
        return f"<Video {self.label} [{self.transcode_status}]>"