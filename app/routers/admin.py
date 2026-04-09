from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import uuid

from app.database import get_db
from app.deps import require_role
from app.models.user import User, UserRole
from app.models.content import Content
from app.models.concert import Concert
from app.models.payment import Payment
from app.schemas.user import UserResponse

router = APIRouter()


@router.get("/dashboard")
async def admin_dashboard(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    total_users = await db.scalar(select(func.count(User.id)))
    total_content = await db.scalar(select(func.count(Content.id)))
    total_concerts = await db.scalar(select(func.count(Concert.id)))
    return {
        "total_users": total_users,
        "total_content": total_content,
        "total_concerts": total_concerts,
    }


@router.get("/users", response_model=list[UserResponse])
async def get_all_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await db.execute(
        select(User).offset((page - 1) * limit).limit(limit)
    )
    return result.scalars().all()


@router.put("/users/{user_id}/role")
async def change_user_role(
    user_id: uuid.UUID,
    role: UserRole,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    user.role = role
    await db.commit()
    return {"message": f"Rôle mis à jour : {role}"}


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    await db.delete(user)
    await db.commit()


@router.get("/content")
async def get_all_content(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await db.execute(select(Content).order_by(Content.created_at.desc()).limit(50))
    return [{"id": str(c.id), "title": c.title, "type": c.type, "status": c.status}
            for c in result.scalars().all()]


@router.get("/concerts")
async def get_all_concerts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await db.execute(select(Concert).order_by(Concert.created_at.desc()).limit(50))
    return [{"id": str(c.id), "title": c.title, "status": c.status}
            for c in result.scalars().all()]