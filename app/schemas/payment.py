from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime
from decimal import Decimal

from app.db.postgres.models.payment import PaymentType, PaymentStatus


# ─── Réponse ──────────────────────────────────────────────────────────────────

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
    failure_reason: Optional[str] = None
    refunded_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Stripe Checkout ──────────────────────────────────────────────────────────

class CheckoutSessionCreate(BaseModel):
    """Corps de requête pour créer une session Stripe Checkout."""
    plan: Optional[str] = None              # pour un abonnement
    concert_id: Optional[UUID4] = None      # pour un billet de concert
    content_id: Optional[UUID4] = None      # pour un achat VOD


class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str
