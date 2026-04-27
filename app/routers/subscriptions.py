from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import get_current_active_user
from app.db.postgres.models.user import User
from app.schemas.subscription import SubscriptionCreate, SubscriptionResponse
from app.services.subscription_service import SubscriptionService
from app.services.notification_service import NotificationService
from app.db.postgres.models.notification import NotificationType

router = APIRouter()


@router.get("/plans")
async def get_plans():
    return SubscriptionService.get_plans()


@router.get("/subscriptions/me", response_model=SubscriptionResponse | None)
async def get_my_subscription(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return await SubscriptionService.get_active_subscription(current_user, db)


@router.post("/subscriptions", response_model=SubscriptionResponse, status_code=201)
async def create_subscription(data: SubscriptionCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    sub = await SubscriptionService.create_subscription(data, current_user, db)
    try:
        plan_label = data.plan_type if isinstance(data.plan_type, str) else data.plan_type.value
        await NotificationService.create(
            user_id=current_user.id,
            notification_type=NotificationType.subscription,
            title="Abonnement activé ✓",
            body=f"Votre abonnement {plan_label} est actif. Profitez de FoliX sans limite !",
            db=db,
        )
    except Exception:
        pass
    return sub


@router.delete("/subscriptions/me", response_model=SubscriptionResponse)
async def cancel_subscription(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return await SubscriptionService.cancel_subscription(current_user, db)
