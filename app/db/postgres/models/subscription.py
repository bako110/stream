import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Boolean, Enum, ForeignKey, DateTime, Numeric, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres.session import Base


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


PLAN_CONFIG = {
    PlanType.free:    {"price": 0.00,  "screens": 1, "profiles": 1, "downloads": 0,  "quality": "480p"},
    PlanType.basic:   {"price": 5.99,  "screens": 1, "profiles": 1, "downloads": 0,  "quality": "720p"},
    PlanType.premium: {"price": 9.99,  "screens": 2, "profiles": 3, "downloads": 10, "quality": "1080p"},
    PlanType.family:  {"price": 14.99, "screens": 5, "profiles": 6, "downloads": 30, "quality": "4k"},
}


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan: Mapped[PlanType] = mapped_column(Enum(PlanType), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus), default=SubscriptionStatus.active)
    price_paid: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    trial_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    downloads_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("ix_subscriptions_user_id", "user_id"),
        Index("ix_subscriptions_plan", "plan"),
        Index("ix_subscriptions_status", "status"),
        Index("ix_subscriptions_stripe_subscription_id", "stripe_subscription_id"),
        Index("ix_subscriptions_current_period_end", "current_period_end"),
        Index("ix_subscriptions_created_at", "created_at"),
        Index("ix_subscriptions_user_status", "user_id", "status"),
    )

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
