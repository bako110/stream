import uuid
import enum
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Enum, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres.session import Base


class InviteStatus(str, enum.Enum):
    pending  = "pending"
    accepted = "accepted"
    declined = "declined"


class PlanningInvite(Base):
    __tablename__ = "planning_invites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("planning_entries.id", ondelete="CASCADE"), nullable=False,
    )
    inviter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    invitee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    status: Mapped[InviteStatus] = mapped_column(
        Enum(InviteStatus, name="invitestatus"), default=InviteStatus.pending, nullable=False,
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    entry   = relationship("PlanningEntry", foreign_keys=[entry_id], lazy="selectin")
    inviter = relationship("User", foreign_keys=[inviter_id], lazy="selectin")
    invitee = relationship("User", foreign_keys=[invitee_id], lazy="selectin")

    __table_args__ = (
        Index("ix_planning_invites_entry_id",   "entry_id"),
        Index("ix_planning_invites_invitee_id", "invitee_id"),
        Index("ix_planning_invites_inviter_id", "inviter_id"),
    )
