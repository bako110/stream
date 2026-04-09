import uuid
from sqlalchemy import String, Integer, Boolean, Enum, ForeignKey, DateTime, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import enum

from app.database import Base


class ConcertType(str, enum.Enum):
    live = "live"
    replay = "replay"
    live_and_replay = "live_and_replay"


class AccessType(str, enum.Enum):
    free = "free"
    subscription = "subscription"
    ticket = "ticket"
    ppv = "ppv"


class ConcertStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    live = "live"
    ended = "ended"
    archived = "archived"


class Concert(Base):
    __tablename__ = "concerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True)

    venue_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    venue_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    venue_country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)

    concert_type: Mapped[ConcertType] = mapped_column(Enum(ConcertType), nullable=False)
    access_type: Mapped[AccessType] = mapped_column(
        Enum(AccessType), default=AccessType.free
    )
    status: Mapped[ConcertStatus] = mapped_column(
        Enum(ConcertStatus), default=ConcertStatus.draft
    )

    ticket_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    max_viewers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_viewers: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)

    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Stream live (RTMP → HLS)
    rtmp_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    live_hls_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Replay (upload après le live)
    replay_video_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id"), nullable=True
    )

    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relations
    artist: Mapped["User"] = relationship("User", foreign_keys=[artist_id])
    tickets: Mapped[list] = relationship(
        "Ticket", back_populates="concert", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Concert {self.title} [{self.status}]>"