from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.db.postgres.models.subscription import Subscription, PlanType, SubscriptionStatus, PLAN_CONFIG
from app.db.postgres.models.user import User
from app.schemas.subscription import SubscriptionCreate


class SubscriptionService:

    PLANS = [
        {"plan": "basic",   "monthly": 5.99,  "annual": 59.99,  "screens": 1, "quality": "720p",  "downloads": 0},
        {"plan": "premium", "monthly": 9.99,  "annual": 99.99,  "screens": 2, "quality": "1080p", "downloads": 10},
        {"plan": "family",  "monthly": 14.99, "annual": 149.99, "screens": 5, "quality": "4K",    "downloads": 30},
    ]

    @staticmethod
    def get_plans() -> list:
        return SubscriptionService.PLANS

    @staticmethod
    async def get_active_subscription(user: User, db: AsyncSession) -> Subscription | None:
        result = await db.execute(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.trialing]),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_subscription(data: SubscriptionCreate, user: User, db: AsyncSession) -> Subscription:
        plan_cfg = PLAN_CONFIG.get(data.plan)
        if not plan_cfg:
            raise HTTPException(status_code=400, detail="Plan invalide")
        now = datetime.utcnow()
        sub = Subscription(
            user_id=user.id,
            plan=data.plan,
            status=SubscriptionStatus.active,
            price_paid=plan_cfg["price"],
            stripe_subscription_id=data.stripe_subscription_id,
            stripe_customer_id=data.stripe_customer_id,
            current_period_start=data.current_period_start or now,
            current_period_end=data.current_period_end,
        )
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
        return sub

    @staticmethod
    async def cancel_subscription(user: User, db: AsyncSession) -> Subscription:
        sub = await SubscriptionService.get_active_subscription(user, db)
        if not sub:
            raise HTTPException(status_code=404, detail="Aucun abonnement actif")
        sub.status = SubscriptionStatus.cancelled
        sub.cancelled_at = datetime.utcnow()
        await db.commit()
        await db.refresh(sub)
        return sub
