"""
Orange Money — paiement d'abonnement (mode simulation).
En production, remplacer _simulate_payment() par l'appel API Orange Money réel.
"""
import uuid
import re
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.postgres.session import get_db
from app.deps import get_current_active_user
from app.db.postgres.models.user import User
from app.db.postgres.models.subscription import (
    Subscription, PlanType, SubscriptionStatus, PLAN_CONFIG,
)
from app.db.postgres.models.payment import Payment, PaymentType, PaymentStatus
from app.services.notification_service import NotificationService
from app.db.postgres.models.notification import NotificationType

router = APIRouter()

PLAN_LABELS = {
    PlanType.basic:   "Basic",
    PlanType.premium: "Premium",
    PlanType.family:  "Family",
}

# ── Schémas ───────────────────────────────────────────────────────────────────

class OrangeMoneyPayRequest(BaseModel):
    phone:    str       # ex: "0712345678" ou "+22507xxxxxxx"
    otp:      str       # code OTP saisi par l'utilisateur
    plan:     PlanType  # basic | premium | family
    billing:  str = "monthly"  # monthly | annual

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) < 8:
            raise ValueError("Numéro de téléphone invalide")
        return digits

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("OTP requis")
        return v.strip()

    @field_validator("billing")
    @classmethod
    def validate_billing(cls, v: str) -> str:
        if v not in ("monthly", "annual"):
            raise ValueError("billing doit être monthly ou annual")
        return v


class OrangeMoneyPayResponse(BaseModel):
    success:          bool
    message:          str
    transaction_id:   str
    plan:             str
    amount:           float
    currency:         str
    period_end:       datetime
    subscription_id:  str


# ── Simulation paiement ───────────────────────────────────────────────────────

def _simulate_payment(phone: str, otp: str, amount: float) -> tuple[bool, str]:
    """
    Mode TEST — accepte toujours sauf OTP = "0000" (simuler un échec).
    En production : appel API Orange Money ici.
    """
    if otp == "0000":
        return False, "Solde insuffisant ou OTP incorrect"
    # Générer un faux transaction ID Orange Money
    txn_id = f"OM-TEST-{uuid.uuid4().hex[:12].upper()}"
    return True, txn_id


# ── Route principale ──────────────────────────────────────────────────────────

@router.post("/pay", response_model=OrangeMoneyPayResponse)
async def orange_money_pay(
    data: OrangeMoneyPayRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = PLAN_CONFIG.get(data.plan)
    if not cfg or data.plan == PlanType.free:
        raise HTTPException(status_code=400, detail="Plan invalide pour Orange Money")

    # Calcul montant
    prices = {
        PlanType.basic:   {"monthly": 5.99,  "annual": 59.99},
        PlanType.premium: {"monthly": 9.99,  "annual": 99.99},
        PlanType.family:  {"monthly": 14.99, "annual": 149.99},
    }
    amount   = prices[data.plan][data.billing]
    currency = "EUR"  # remplacer par "XOF" en prod

    # Simulation du paiement Orange Money
    ok, result = _simulate_payment(data.phone, data.otp, amount)
    if not ok:
        raise HTTPException(status_code=402, detail=result)

    txn_id = result
    now    = datetime.utcnow()
    days   = 30 if data.billing == "monthly" else 365
    end    = now + timedelta(days=days)

    # Annuler l'abonnement actif existant si présent
    existing = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.trialing]),
        )
    )
    old_sub = existing.scalar_one_or_none()
    if old_sub:
        old_sub.status = SubscriptionStatus.cancelled
        old_sub.cancelled_at = now

    # Créer le nouvel abonnement
    sub = Subscription(
        user_id              = current_user.id,
        plan                 = data.plan,
        status               = SubscriptionStatus.active,
        price_paid           = amount,
        stripe_subscription_id = txn_id,   # on réutilise ce champ pour l'ID Orange Money
        stripe_customer_id   = data.phone,  # numéro OM comme "customer"
        current_period_start = now,
        current_period_end   = end,
    )
    db.add(sub)

    # Enregistrer le paiement
    payment = Payment(
        user_id                   = current_user.id,
        amount                    = amount,
        currency                  = currency,
        payment_type              = PaymentType.subscription,
        status                    = PaymentStatus.succeeded,
        stripe_payment_intent_id  = txn_id,   # ID transaction Orange Money
        extra_data                = {
            "provider": "orange_money",
            "phone":    data.phone,
            "billing":  data.billing,
            "plan":     data.plan.value,
        },
    )
    db.add(payment)

    await db.commit()
    await db.refresh(sub)

    # Notification
    try:
        plan_label = PLAN_LABELS.get(data.plan, data.plan.value)
        await NotificationService.create(
            user_id           = current_user.id,
            notification_type = NotificationType.subscription,
            title             = "Abonnement active !",
            body              = f"Votre abonnement {plan_label} est actif via Orange Money. Profitez de FoliX !",
            db                = db,
        )
    except Exception:
        pass

    return OrangeMoneyPayResponse(
        success         = True,
        message         = f"Paiement confirme via Orange Money",
        transaction_id  = txn_id,
        plan            = data.plan.value,
        amount          = amount,
        currency        = currency,
        period_end      = end,
        subscription_id = str(sub.id),
    )


# ── Route : vérifier statut OTP (optionnelle, pour UX "envoyer OTP") ─────────

@router.post("/send-otp")
async def send_otp(
    body: dict,
    current_user: User = Depends(get_current_active_user),
):
    """
    Mode TEST — simule l'envoi d'un OTP.
    En production : déclencher l'API Orange Money USSD/OTP ici.
    """
    phone = body.get("phone", "")
    if not phone:
        raise HTTPException(status_code=400, detail="Numéro requis")
    # En test : on retourne juste un succès
    return {
        "sent":    True,
        "message": f"OTP envoye au {phone} (mode test — utilisez n'importe quel code sauf 0000)",
        "test_mode": True,
    }
