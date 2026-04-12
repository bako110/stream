import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.db.postgres.models.content import Content, ContentType
from app.db.postgres.models.season import Season
from app.db.postgres.models.episode import Episode
from app.schemas.season import SeasonCreate, SeasonUpdate
from app.schemas.episode import EpisodeCreate, EpisodeUpdate


class SeasonService:

    @staticmethod
    async def list_seasons(content_id: uuid.UUID, db: AsyncSession) -> list:
        result = await db.execute(select(Season).where(Season.content_id == content_id).order_by(Season.number))
        return result.scalars().all()

    @staticmethod
    async def get_season(content_id: uuid.UUID, number: int, db: AsyncSession) -> Season:
        result = await db.execute(select(Season).where(Season.content_id == content_id, Season.number == number))
        season = result.scalar_one_or_none()
        if not season:
            raise HTTPException(status_code=404, detail="Saison non trouvée")
        return season

    @staticmethod
    async def create_season(content_id: uuid.UUID, data: SeasonCreate, db: AsyncSession) -> Season:
        result = await db.execute(select(Content).where(Content.id == content_id, Content.type == ContentType.serie))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Série non trouvée")
        season = Season(**data.model_dump(), content_id=content_id)
        db.add(season)
        await db.commit()
        await db.refresh(season)
        return season

    @staticmethod
    async def update_season(content_id: uuid.UUID, number: int, data: SeasonUpdate, db: AsyncSession) -> Season:
        result = await db.execute(select(Season).where(Season.content_id == content_id, Season.number == number))
        season = result.scalar_one_or_none()
        if not season:
            raise HTTPException(status_code=404, detail="Saison non trouvée")
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(season, key, value)
        await db.commit()
        await db.refresh(season)
        return season

    @staticmethod
    async def delete_season(content_id: uuid.UUID, number: int, db: AsyncSession) -> None:
        result = await db.execute(select(Season).where(Season.content_id == content_id, Season.number == number))
        season = result.scalar_one_or_none()
        if not season:
            raise HTTPException(status_code=404, detail="Saison non trouvée")
        await db.delete(season)
        await db.commit()


class EpisodeService:

    @staticmethod
    async def list_episodes(content_id: uuid.UUID, season_number: int, db: AsyncSession) -> list:
        result = await db.execute(select(Season).where(Season.content_id == content_id, Season.number == season_number))
        season = result.scalar_one_or_none()
        if not season:
            raise HTTPException(status_code=404, detail="Saison non trouvée")
        result = await db.execute(select(Episode).where(Episode.season_id == season.id).order_by(Episode.number))
        return result.scalars().all()

    @staticmethod
    async def get_episode(episode_id: uuid.UUID, db: AsyncSession) -> Episode:
        result = await db.execute(select(Episode).where(Episode.id == episode_id))
        episode = result.scalar_one_or_none()
        if not episode:
            raise HTTPException(status_code=404, detail="Épisode non trouvé")
        return episode

    @staticmethod
    async def create_episode(content_id: uuid.UUID, season_number: int, data: EpisodeCreate, db: AsyncSession) -> Episode:
        result = await db.execute(select(Season).where(Season.content_id == content_id, Season.number == season_number))
        season = result.scalar_one_or_none()
        if not season:
            raise HTTPException(status_code=404, detail="Saison non trouvée")
        episode = Episode(**data.model_dump(), season_id=season.id)
        db.add(episode)
        await db.commit()
        await db.refresh(episode)
        return episode

    @staticmethod
    async def update_episode(episode_id: uuid.UUID, data: EpisodeUpdate, db: AsyncSession) -> Episode:
        result = await db.execute(select(Episode).where(Episode.id == episode_id))
        episode = result.scalar_one_or_none()
        if not episode:
            raise HTTPException(status_code=404, detail="Épisode non trouvé")
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(episode, key, value)
        await db.commit()
        await db.refresh(episode)
        return episode

    @staticmethod
    async def delete_episode(episode_id: uuid.UUID, db: AsyncSession) -> None:
        result = await db.execute(select(Episode).where(Episode.id == episode_id))
        episode = result.scalar_one_or_none()
        if not episode:
            raise HTTPException(status_code=404, detail="Épisode non trouvé")
        await db.delete(episode)
        await db.commit()
