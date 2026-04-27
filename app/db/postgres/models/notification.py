import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Enum, DateTime, ForeignKey, Text, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres.session import Base


class NotificationType(str, enum.Enum):
    follow       = "follow"
    reaction     = "reaction"
    comment      = "comment"
    mention      = "mention"
    profile_view = "profile_view"
    story_view   = "story_view"
    concert_created = "concert_created"
    event_created   = "event_created"
    concert_going   = "concert_going"
    event_going     = "event_going"
    community_joined = "community_joined"
    reel_posted  = "reel_posted"
    subscription = "subscription"
    welcome      = "welcome"
    ticket       = "ticket"
    system       = "system"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Destinataire
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )

    # Auteur de l'action (null pour les notifs système / welcome)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notificationtype"), nullable=False,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body:  Mapped[str] = mapped_column(Text, nullable=False)

    # Référence vers l'objet concerné (concert_id, event_id, reel_id…)
    ref_id:   Mapped[str | None] = mapped_column(String(36), nullable=True)
    ref_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "concert"|"event"|"reel"…

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relations
    user  = relationship("User", foreign_keys=[user_id], lazy="noload")
    actor = relationship("User", foreign_keys=[actor_id], lazy="selectin")

    __table_args__ = (
        Index("ix_notifications_user_id",    "user_id"),
        Index("ix_notifications_is_read",    "is_read"),
        Index("ix_notifications_created_at", "created_at"),
        Index("ix_notifications_user_unread", "user_id", "is_read"),
    )
