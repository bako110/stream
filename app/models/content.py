import uuid
from sqlalchemy import String, Boolean, Integer, Numeric, Text, Enum, ForeignKey, DateTime, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import enum

from app.database import Base


class ContentType(str, enum.Enum):
    film = "film"
    serie = "serie"


class ContentStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class Content(Base):
    __tablename__ = "contents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    type: Mapped[ContentType] = mapped_column(Enum(ContentType), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_synopsis: Mapped[str | None] = mapped_column(String(500), nullable=True)
    director: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cast: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    trailer_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[ContentStatus] = mapped_column(
        Enum(ContentStatus), default=ContentStatus.draft
    )
    total_seasons: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    average_rating: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relations
    seasons: Mapped[list] = relationship("Season", back_populates="content")
    videos: Mapped[list] = relationship("Video", back_populates="content")

    def __repr__(self):
        return f"<Content {self.title} ({self.type})>"