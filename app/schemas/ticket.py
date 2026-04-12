from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime
from decimal import Decimal

from app.db.postgres.models.ticket import TicketStatus


# ─── Création ─────────────────────────────────────────────────────────────────

class TicketCreate(BaseModel):
    concert_id: UUID4
    includes_replay: bool = True


# ─── Réponse ──────────────────────────────────────────────────────────────────

class TicketResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    concert_id: UUID4
    payment_id: Optional[UUID4] = None
    status: TicketStatus
    price_paid: Decimal
    currency: str
    access_code: str
    includes_replay: bool
    used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
