from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.watch_history import WatchHistory
from app.schemas.user import UserResponse, UserUpdate

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(current_user, key, value)
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/me/history")
async def get_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(WatchHistory)
        .where(WatchHistory.user_id == current_user.id)
        .order_by(WatchHistory.watched_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    return user