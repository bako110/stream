import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Enum, ForeignKey, DateTime, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres.session import Base
from app.db.postgres.models.ticket import TicketStatus


class EventTicket(Base):
    __tablename__ = "event_tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=True)
    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus), default=TicketStatus.valid)
    price_paid: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    access_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: uuid.uuid4().hex)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User")
    event: Mapped["Event"] = relationship("Event", back_populates="tickets")
    payment: Mapped["Payment"] = relationship("Payment")

    def __repr__(self):
        return f"<EventTicket event={self.event_id} user={self.user_id} [{self.status}]>"
