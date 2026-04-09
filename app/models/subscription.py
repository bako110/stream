import uuid
from sqlalchemy import String, Boolean, Enum, ForeignKey, DateTime, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import enum

from app.database import Base


class PlanType(str, enum.Enum):
    free = "free"
    basic = "basic"
    premium = "premium"
    family = "family"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    cancelled = "cancelled"
    expired = "expired"
    past_due = "past_due"
    trialing = "trialing"


# Tarifs et limites par plan
PLAN_CONFIG = {
    PlanType.free:    {"price": 0.00,  "screens": 1, "profiles": 1, "downloads": 0,  "quality": "480p"},
    PlanType.basic:   {"price": 5.99,  "screens": 1, "profiles": 1, "downloads": 0,  "quality": "720p"},
    PlanType.premium: {"price": 9.99,  "screens": 2, "profiles": 3, "downloads": 10, "quality": "1080p"},
    PlanType.family:  {"price": 14.99, "screens": 5, "profiles": 6, "downloads": 30, "quality": "4k"},
}


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    plan: Mapped[PlanType] = mapped_column(Enum(PlanType), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), default=SubscriptionStatus.active
    )
    price_paid: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    # Stripe
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    current_period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    trial_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Compteur téléchargements offline
    downloads_used: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relations
    user: Mapped["User"] = relationship("User")

    @property
    def is_active(self) -> bool:
        return (
            self.status in (SubscriptionStatus.active, SubscriptionStatus.trialing)
            and self.current_period_end > datetime.utcnow()
        )

    @property
    def max_downloads(self) -> int:
        return PLAN_CONFIG[self.plan]["downloads"]

    def __repr__(self):
        return f"<Subscription {self.plan} [{self.status}] user={self.user_id}>"