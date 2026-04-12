import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, Enum, ForeignKey, DateTime, Numeric, Text
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

    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizer: Mapped["User"] = relationship("User", foreign_keys=[organizer_id])
    tickets: Mapped[list] = relationship("EventTicket", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Event {self.title} [{self.event_type}] {self.starts_at}>"
