from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime
from decimal import Decimal
from app.models.subscription import PlanType, SubscriptionStatus
from app.models.payment import PaymentType, PaymentStatus
from app.models.ticket import TicketStatus


# ─── Subscription ────────────────────────────────────────────────────────────

class SubscriptionCreate(BaseModel):
    plan: PlanType
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    current_period_start: datetime
    current_period_end: datetime


class SubscriptionResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    plan: PlanType
    status: SubscriptionStatus
    price_paid: Decimal
    current_period_start: datetime
    current_period_end: datetime
    cancelled_at: Optional[datetime] = None
    downloads_used: int
    max_downloads: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Payment ─────────────────────────────────────────────────────────────────

class PaymentResponse(BaseModel):
    id: UUID4
    user_id: Optional[UUID4] = None
    payment_type: PaymentType
    status: PaymentStatus
    amount: Decimal
    currency: str
    stripe_payment_intent_id: Optional[str] = None
    reference_id: Optional[UUID4] = None
    reference_type: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Ticket ──────────────────────────────────────────────────────────────────

class TicketCreate(BaseModel):
    concert_id: UUID4
    includes_replay: bool = True


class TicketResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    concert_id: UUID4
    status: TicketStatus
    price_paid: Decimal
    currency: str
    access_code: str
    includes_replay: bool
    expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Stripe ──────────────────────────────────────────────────────────────────

class CheckoutSessionCreate(BaseModel):
    """Pour créer une session Stripe Checkout"""
    plan: Optional[PlanType] = None       # pour abonnement
    concert_id: Optional[UUID4] = None    # pour billet
    content_id: Optional[UUID4] = None    # pour VOD


class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str