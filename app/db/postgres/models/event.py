import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, Enum, ForeignKey, DateTime, Numeric, Text, Index, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres.session import Base


class EventType(str, enum.Enum):
    concert = "concert"
    birthday = "birthday"
    festival = "festival"
    conference = "conference"
    sport = "sport"
    theater = "theater"
    exhibition = "exhibition"
    other = "other"


class EventStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    cancelled = "cancelled"
    completed = "completed"


class EventAccessType(str, enum.Enum):
    free = "free"
    ticket = "ticket"
    invite_only = "invite_only"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organizer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)
    status: Mapped[EventStatus] = mapped_column(Enum(EventStatus), default=EventStatus.draft)
    access_type: Mapped[EventAccessType] = mapped_column(Enum(EventAccessType), default=EventAccessType.free)

    # Lieu
    venue_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    venue_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    venue_city: Mapped[str] = mapped_column(String(100), nullable=False)
    venue_country: Mapped[str] = mapped_column(String(100), nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    online_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Dates
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Billets
    ticket_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    max_attendees: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_attendees: Mapped[int] = mapped_column(Integer, default=0)

    # Médias
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    gallery_urls: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizer: Mapped["User"] = relationship("User", foreign_keys=[organizer_id])
    tickets: Mapped[list] = relationship("EventTicket", back_populates="event", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_events_status",              "status"),
        Index("ix_events_starts_at",           "starts_at"),
        Index("ix_events_event_type",          "event_type"),
        Index("ix_events_organizer_id",        "organizer_id"),
        Index("ix_events_venue_city",          "venue_city"),
        Index("ix_events_status_starts_at",    "status", "starts_at"),
        Index("ix_events_event_type_city",     "event_type", "venue_city"),
        # Feed : status publié + tri created_at
        Index("ix_events_status_created_at",   "status", "created_at"),
        # Feed : organizer_id + status pour filtres contacts
        Index("ix_events_organizer_status",    "organizer_id", "status"),
    )

    def __repr__(self):
        return f"<Event {self.title} [{self.event_type}] {self.starts_at}>"
