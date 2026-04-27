import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import HTTPException

from app.db.postgres.models.user import User, UserRole
from app.db.postgres.models.follow import Follow
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
    async def list_users(page: int, limit: int, role: Optional[str], db: AsyncSession, verification_status: Optional[str] = None) -> list:
        query = select(User)
        if role:
            query = query.where(User.role == role)
        if verification_status:
            from app.db.postgres.models.user import VerificationStatus as VS
            try:
                query = query.where(User.verification_status == VS(verification_status))
            except ValueError:
                pass
        query = query.order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def update_me(data: UserUpdate, user: User, db: AsyncSession) -> User:
        # Re-fetch user within this session to ensure it's persistent
        db_user = await db.get(User, user.id)
        if not db_user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

        # Vérif unicité username si changé
        if data.username and data.username != db_user.username:
            from sqlalchemy import select as _select
            existing = (await db.execute(
                _select(User).where(User.username == data.username)
            )).scalar_one_or_none()
            if existing:
                raise HTTPException(status_code=400, detail="Username déjà utilisé")

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(db_user, key, value)

        # Recalcul display_name si prénom/nom changé et display_name non explicitement fourni
        if (data.first_name or data.last_name) and data.display_name is None:
            fn = data.first_name or db_user.first_name or ""
            ln = data.last_name or db_user.last_name or ""
            if fn or ln:
                db_user.display_name = f"{fn} {ln}".strip()

        await db.commit()
        await db.refresh(db_user)
        return db_user

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
    async def soft_delete(user_id: uuid.UUID, db: AsyncSession) -> None:
        """Désactivation + marquage supprimé (initié par l'utilisateur lui-même)."""
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        user.is_active  = False
        user.is_deleted = True
        user.deleted_at = datetime.utcnow()
        await db.commit()

    @staticmethod
    async def hard_delete(user_id: uuid.UUID, db: AsyncSession) -> None:
        """Suppression physique définitive (admin uniquement)."""
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        await db.delete(user)
        await db.commit()

    @staticmethod
    async def delete(user_id: uuid.UUID, db: AsyncSession) -> None:
        """Alias pour hard_delete — compatibilité route admin existante."""
        await UserService.hard_delete(user_id, db)

    @staticmethod
    async def suggest_users(
        current_user_id: uuid.UUID,
        db: AsyncSession,
        limit: int = 10,
        offset: int = 0,
    ) -> list:
        """
        Suggestions : amis de mes amis en priorité, puis utilisateurs actifs aléatoires.
        Exclut les utilisateurs déjà suivis et soi-même.
        Supporte la pagination via offset.
        """
        already_following = select(Follow.following_id).where(Follow.follower_id == current_user_id)

        # 1re requête : amis de mes amis (avec score = nombre de connexions communes)
        foaf_result = await db.execute(
            select(User, func.count(Follow.id).label("mutual"))
            .join(Follow, Follow.following_id == User.id)
            .where(
                User.id != current_user_id,
                User.is_active == True,
                User.id.notin_(already_following),
                Follow.follower_id.in_(already_following),
            )
            .group_by(User.id)
            .order_by(func.count(Follow.id).desc())
            .offset(offset)
            .limit(limit)
        )
        foaf_users = [row[0] for row in foaf_result.all()]
        foaf_ids = {u.id for u in foaf_users}

        # Compléter avec des users aléatoires si pas assez de foaf
        remaining = limit - len(foaf_users)
        random_users = []
        if remaining > 0:
            rand_result = await db.execute(
                select(User)
                .where(
                    User.id != current_user_id,
                    User.is_active == True,
                    User.id.notin_(already_following),
                    User.id.notin_(list(foaf_ids)) if foaf_ids else True,
                )
                .order_by(func.random())
                .offset(max(0, offset - (offset - remaining)))
                .limit(remaining)
            )
            random_users = rand_result.scalars().all()

        return foaf_users + random_users
