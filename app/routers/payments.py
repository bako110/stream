import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import get_current_active_user
from app.db.postgres.models.user import User
from app.schemas.payment import PaymentResponse
from app.services.payment_service import PaymentService

router = APIRouter()


@router.get("/me", response_model=list[PaymentResponse])
async def get_my_payments(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return await PaymentService.get_user_payments(current_user, db)


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return await PaymentService.get_payment(payment_id, current_user, db)
