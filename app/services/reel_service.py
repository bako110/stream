import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException

from app.db.postgres.models.reel import Reel, ReelStatus
from app.db.postgres.models.user import User
from app.schemas.reel import ReelCreate, ReelUpdate


class ReelService:

    @staticmethod
    async def list_reels(page: int, limit: int, db: AsyncSession) -> dict:
        query = select(Reel).where(Reel.status == ReelStatus.published).order_by(Reel.created_at.desc())
        total = await db.scalar(select(func.count()).select_from(query.subquery()))
        result = await db.execute(query.offset((page - 1) * limit).limit(limit))
        return {"items": result.scalars().all(), "total": total, "page": page, "limit": limit}

    @staticmethod
    async def get_reel(reel_id: uuid.UUID, db: AsyncSession) -> Reel:
        result = await db.execute(select(Reel).where(Reel.id == reel_id))
        reel = result.scalar_one_or_none()
        if not reel:
            raise HTTPException(status_code=404, detail="Reel non trouvé")
        return reel

    @staticmethod
    async def create_reel(data: ReelCreate, user: User, db: AsyncSession) -> Reel:
        reel = Reel(
            **data.model_dump(exclude_none=True),
            user_id=user.id,
            status=ReelStatus.published if data.video_url else ReelStatus.processing,
        )
        db.add(reel)
        await db.commit()
        await db.refresh(reel)
        return reel

    @staticmethod
    async def update_reel(reel_id: uuid.UUID, data: ReelUpdate, user: User, db: AsyncSession) -> Reel:
        result = await db.execute(select(Reel).where(Reel.id == reel_id))
        reel = result.scalar_one_or_none()
        if not reel:
            raise HTTPException(status_code=404, detail="Reel non trouvé")
        if reel.user_id != user.id and user.role.value != "admin":
            raise HTTPException(status_code=403, detail="Accès refusé")
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(reel, key, value)
        await db.commit()
        await db.refresh(reel)
        return reel

    @staticmethod
    async def delete_reel(reel_id: uuid.UUID, user: User, db: AsyncSession) -> None:
        result = await db.execute(select(Reel).where(Reel.id == reel_id))
        reel = result.scalar_one_or_none()
        if not reel:
            raise HTTPException(status_code=404, detail="Reel non trouvé")
        if reel.user_id != user.id and user.role.value != "admin":
            raise HTTPException(status_code=403, detail="Accès refusé")
        await db.delete(reel)
        await db.commit()

    @staticmethod
    async def get_user_reels(user_id: uuid.UUID, db: AsyncSession) -> list:
        result = await db.execute(
            select(Reel)
            .where(Reel.user_id == user_id, Reel.status == ReelStatus.published)
            .order_by(Reel.created_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def increment_view(reel_id: uuid.UUID, db: AsyncSession) -> None:
        result = await db.execute(select(Reel).where(Reel.id == reel_id))
        reel = result.scalar_one_or_none()
        if reel:
            reel.view_count += 1
            await db.commit()
