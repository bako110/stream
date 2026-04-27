import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Enum, DateTime, ForeignKey, UniqueConstraint, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres.session import Base


class ReminderRefType(str, enum.Enum):
    event   = "event"
    concert = "concert"


class ContentReminder(Base):
    """Rappel programmé : l'utilisateur demande une notif push avant un event/concert."""
    __tablename__ = "content_reminders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ref_id:   Mapped[str] = mapped_column(String(36), nullable=False)
    ref_type: Mapped[ReminderRefType] = mapped_column(
        Enum(ReminderRefType, name="reminderreftype"), nullable=False
    )
    # Date de l'événement — pour calculer quand envoyer la notif
    event_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Titre affiché dans la notif
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # True une fois la notif push envoyée
    fired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "ref_id", "ref_type", name="uq_reminder_user_ref"),
        Index("ix_reminders_user_id",   "user_id"),
        Index("ix_reminders_fired",     "fired"),
        Index("ix_reminders_event_date","event_date"),
    )
