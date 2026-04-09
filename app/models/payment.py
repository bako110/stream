import uuid
from sqlalchemy import String, Enum, ForeignKey, DateTime, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import enum

from app.database import Base


class PaymentType(str, enum.Enum):
    subscription = "subscription"
    vod = "vod"           # Achat à l'unité d'un film/série
    ticket = "ticket"     # Billet concert
    ppv = "ppv"           # Pay-per-view


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    refunded = "refunded"
    disputed = "disputed"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    payment_type: Mapped[PaymentType] = mapped_column(Enum(PaymentType), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.pending
    )

    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)

    # Stripe
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    stripe_charge_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Référence vers l'objet payé (content, concert, ticket...)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Métadonnées Stripe (webhook payload, etc.)
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relations
    user: Mapped["User"] = relationship("User")

    def __repr__(self):
        return f"<Payment {self.payment_type} {self.amount}{self.currency} [{self.status}]>"