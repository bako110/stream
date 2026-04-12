from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime
from decimal import Decimal

from app.db.postgres.models.subscription import PlanType, SubscriptionStatus


# ─── Création ─────────────────────────────────────────────────────────────────

class SubscriptionCreate(BaseModel):
    plan: PlanType
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    current_period_start: Optional[datetime] = None
    current_period_end: datetime


# ─── Réponse ──────────────────────────────────────────────────────────────────

class SubscriptionResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    plan: PlanType
    status: SubscriptionStatus
    price_paid: Decimal
    current_period_start: datetime
    current_period_end: datetime
    cancelled_at: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    downloads_used: int
    # Propriétés calculées — exposées explicitement
    is_active: bool
    max_downloads: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PlanDetail(BaseModel):
    """Détail d'un plan d'abonnement (endpoint /plans)."""
    plan: str
    monthly: float
    annual: float
    screens: int
    quality: str
    downloads: int
