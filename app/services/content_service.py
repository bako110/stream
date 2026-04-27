import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.db.postgres.models.content import Content, ContentType, ContentStatus
from app.schemas.content import ContentCreate, ContentUpdate


class ContentService:

    @staticmethod
    async def list_films(page: int, limit: int, year: Optional[int], language: Optional[str], db: AsyncSession) -> dict:
        query = select(Content).where(Content.type == ContentType.film, Content.status == ContentStatus.published)
        if year:
            query = query.where(Content.year == year)
        if language:
            query = query.where(Content.language == language)
        total = await db.scalar(select(func.count()).select_from(query.subquery()))
        result = await db.execute(query.offset((page - 1) * limit).limit(limit))
        return {"items": result.scalars().all(), "total": total, "page": page, "limit": limit}

    @staticmethod
    async def get_film(content_id: uuid.UUID, db: AsyncSession) -> Content:
        result = await db.execute(
            select(Content)
            .options(selectinload(Content.seasons))
            .where(Content.id == content_id, Content.type == ContentType.film)
        )
        film = result.scalar_one_or_none()
        if not film:
            raise HTTPException(status_code=404, detail="Film non trouvé")
        return film

    @staticmethod
    async def create_film(data: ContentCreate, added_by: uuid.UUID, db: AsyncSession) -> Content:
        film = Content(**data.model_dump(), type=ContentType.film, added_by=added_by)
        db.add(film)
        await db.commit()
        await db.refresh(film)
        return film

    @staticmethod
    async def list_series(page: int, limit: int, db: AsyncSession) -> dict:
        query = select(Content).where(Content.type == ContentType.serie, Content.status == ContentStatus.published)
        total = await db.scalar(select(func.count()).select_from(query.subquery()))
        result = await db.execute(query.offset((page - 1) * limit).limit(limit))
        return {"items": result.scalars().all(), "total": total, "page": page, "limit": limit}

    @staticmethod
    async def get_serie(content_id: uuid.UUID, db: AsyncSession) -> Content:
        result = await db.execute(
            select(Content)
            .options(selectinload(Content.seasons).selectinload(Season.episodes))
            .where(Content.id == content_id, Content.type == ContentType.serie)
        )
        serie = result.scalar_one_or_none()
        if not serie:
            raise HTTPException(status_code=404, detail="Série non trouvée")
        return serie

    @staticmethod
    async def create_serie(data: ContentCreate, added_by: uuid.UUID, db: AsyncSession) -> Content:
        serie = Content(**data.model_dump(), type=ContentType.serie, added_by=added_by)
        db.add(serie)
        await db.commit()
        await db.refresh(serie)
        return serie

    @staticmethod
    async def update_content(content_id: uuid.UUID, data: ContentUpdate, db: AsyncSession) -> Content:
        result = await db.execute(select(Content).where(Content.id == content_id))
        content = result.scalar_one_or_none()
        if not content:
            raise HTTPException(status_code=404, detail="Contenu non trouvé")
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(content, key, value)
        await db.commit()
        await db.refresh(content)
        return content

    @staticmethod
    async def delete_content(content_id: uuid.UUID, db: AsyncSession) -> None:
        result = await db.execute(select(Content).where(Content.id == content_id))
        content = result.scalar_one_or_none()
        if not content:
            raise HTTPException(status_code=404, detail="Contenu non trouvé")
        await db.delete(content)
        await db.commit()

    @staticmethod
    async def toggle_publish(content_id: uuid.UUID, db: AsyncSession) -> Content:
        result = await db.execute(select(Content).where(Content.id == content_id))
        content = result.scalar_one_or_none()
        if not content:
            raise HTTPException(status_code=404, detail="Contenu non trouvé")
        content.status = (
            ContentStatus.draft if content.status == ContentStatus.published else ContentStatus.published
        )
        await db.commit()
        await db.refresh(content)
        return content
