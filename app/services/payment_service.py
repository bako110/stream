import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.db.postgres.models.payment import Payment, PaymentType, PaymentStatus
from app.db.postgres.models.user import User


class PaymentService:

    @staticmethod
    async def get_user_payments(user: User, db: AsyncSession) -> list:
        result = await db.execute(
            select(Payment).where(Payment.user_id == user.id).order_by(Payment.created_at.desc()).limit(50)
        )
        return result.scalars().all()

    @staticmethod
    async def get_payment(payment_id: uuid.UUID, user: User, db: AsyncSession) -> Payment:
        result = await db.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()
        if not payment:
            raise HTTPException(status_code=404, detail="Paiement non trouvé")
        if payment.user_id != user.id and user.role.value != "admin":
            raise HTTPException(status_code=403, detail="Accès refusé")
        return payment

    @staticmethod
    async def create_payment(
        user_id: uuid.UUID, payment_type: PaymentType, amount: float, currency: str,
        stripe_payment_intent_id: str | None, reference_id: uuid.UUID | None,
        reference_type: str | None, db: AsyncSession,
    ) -> Payment:
        payment = Payment(
            user_id=user_id, payment_type=payment_type, status=PaymentStatus.pending,
            amount=amount, currency=currency,
            stripe_payment_intent_id=stripe_payment_intent_id,
            reference_id=reference_id, reference_type=reference_type,
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)
        return payment

    @staticmethod
    async def update_payment_status(stripe_pi_id: str, new_status: PaymentStatus, db: AsyncSession) -> Payment | None:
        result = await db.execute(select(Payment).where(Payment.stripe_payment_intent_id == stripe_pi_id))
        payment = result.scalar_one_or_none()
        if payment:
            payment.status = new_status
            await db.commit()
        return payment
