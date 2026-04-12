import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import HTTPException

from app.db.postgres.models.user import User, UserRole
from app.schemas.user import UserUpdate


class UserService:

    @staticmethod
    async def get_by_id(user_id: uuid.UUID, db: AsyncSession) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        return user

    @staticmethod
    async def list_users(page: int, limit: int, role: Optional[str], db: AsyncSession) -> list:
        query = select(User)
        if role:
            query = query.where(User.role == role)
        query = query.order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def update_me(data: UserUpdate, user: User, db: AsyncSession) -> User:
        # Vérif unicité username si changé
        if data.username and data.username != user.username:
            from sqlalchemy import select as _select
            existing = (await db.execute(
                _select(User).where(User.username == data.username)
            )).scalar_one_or_none()
            if existing:
                raise HTTPException(status_code=400, detail="Username déjà utilisé")

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(user, key, value)

        # Recalcul display_name si prénom/nom changé et display_name non explicitement fourni
        if (data.first_name or data.last_name) and data.display_name is None:
            fn = data.first_name or user.first_name or ""
            ln = data.last_name or user.last_name or ""
            if fn or ln:
                user.display_name = f"{fn} {ln}".strip()

        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def get_watch_history(user: User, mongo: AsyncIOMotorDatabase) -> list:
        cursor = (
            mongo["watch_history"]
            .find({"user_id": str(user.id)})
            .sort("last_watched_at", -1)
            .limit(50)
        )
        history = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            history.append(doc)
        return history

    @staticmethod
    async def change_role(user_id: uuid.UUID, role: UserRole, db: AsyncSession) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        user.role = role
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def set_active(user_id: uuid.UUID, is_active: bool, db: AsyncSession) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        user.is_active = is_active
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def delete(user_id: uuid.UUID, db: AsyncSession) -> None:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        await db.delete(user)
        await db.commit()
