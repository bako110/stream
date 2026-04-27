import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, and_, not_, cast, Float, update as sa_update
from sqlalchemy.orm import selectinload, make_transient
from fastapi import HTTPException

from app.db.postgres.models.reel import Reel, ReelStatus, ReelView
from app.db.postgres.models.reaction import Reaction
from app.db.postgres.models.follow import Follow
from app.db.postgres.models.user import User
from app.schemas.reel import ReelCreate, ReelUpdate
from app.services.local_storage_service import get_h264_url, delete_media
from app.utils.cache import cache_invalidate_prefix


class ReelService:

    @staticmethod
    def _transform_reel_urls(reels: list[Reel]) -> list[Reel]:
        for reel in reels:
            make_transient(reel)
            if reel.video_url:
                reel.video_url = get_h264_url(reel.video_url)
        return reels

    @staticmethod
    def _transform_single_reel_url(reel: Reel) -> Reel:
        make_transient(reel)
        if reel.video_url:
            reel.video_url = get_h264_url(reel.video_url)
        return reel

    # ── Feed intelligent (utilisateur connecté) ────────────────────────────
    @staticmethod
    async def get_feed(user_id: uuid.UUID, page: int, limit: int, db: AsyncSession) -> dict:
        """
        Algorithme de feed dynamique — score composite :

        score = freshness * engagement_rate * watch_boost * following_boost * featured_boost + noise

        - freshness    : décroissance exponentielle (demi-vie 6h)
        - engagement   : (likes + comments*2 + shares*3) / max(views, 1) — taux relatif
        - velocity     : boost si beaucoup d'engagement dans les 2 dernières heures
        - watch_boost  : basé sur le watch_ratio moyen des viewers
        - following    : x1.4 si je suis l'auteur
        - featured     : x1.2
        - noise        : ±10% pour la diversité
        """
        now = datetime.utcnow()

        # Reels déjà bien vus (>60% regardé) — exclus
        seen_subq = (
            select(ReelView.reel_id)
            .where(
                ReelView.viewer_id == user_id,
                ReelView.watch_ratio > 0.6,
            )
            .scalar_subquery()
        )

        # Créateurs suivis
        following_subq = (
            select(Follow.following_id)
            .where(Follow.follower_id == user_id)
            .scalar_subquery()
        )

        # ── Fraîcheur : décroissance exponentielle, demi-vie = 6h ────────────
        # score = 100 * 0.5^(age_h / 6)  ≈ 100 * exp(-0.1155 * age_h)
        hours_age = func.greatest(0.01, func.extract("epoch", now - Reel.created_at) / 3600.0)
        freshness = 100.0 * func.pow(cast(0.5, Float), hours_age / 6.0)

        # ── Taux d'engagement relatif (pas absolu) ───────────────────────────
        raw_views = func.greatest(Reel.view_count, 1)
        engagement_rate = func.least(
            100.0,
            (Reel.like_count + Reel.comment_count * 2.5 + Reel.share_count * 4.0) * 100.0 / raw_views
        )

        # ── Vélocité : reels récents (<2h) avec beaucoup d'engagement ────────
        velocity_boost = case(
            (
                func.extract("epoch", now - Reel.created_at) < 7200,
                func.least(30.0, (Reel.like_count + Reel.comment_count * 2) * 1.0)
            ),
            else_=0.0,
        )

        # ── Watch ratio moyen (qualité du contenu) ───────────────────────────
        # Approximé via view_count vs like_count : si beaucoup de likes/views → bon contenu
        watch_quality = func.least(
            20.0,
            func.greatest(0.0, (Reel.like_count * 100.0 / raw_views) - 1.0)
        )

        # ── Boosts multiplicateurs ───────────────────────────────────────────
        following_mult = case(
            (Reel.user_id.in_(following_subq), cast(1.4, Float)),
            else_=cast(1.0, Float),
        )
        featured_mult = case(
            (Reel.is_featured == True, cast(1.2, Float)),
            else_=cast(1.0, Float),
        )

        # ── Score final ──────────────────────────────────────────────────────
        total_score = (
            (freshness * 0.4 + engagement_rate * 0.4 + velocity_boost + watch_quality)
            * following_mult
            * featured_mult
            + func.random() * 10.0  # bruit ±10% pour la diversité
        )

        query = (
            select(Reel)
            .options(selectinload(Reel.author))
            .where(
                Reel.status == ReelStatus.published,
                Reel.id.not_in(seen_subq),
            )
            .order_by(total_score.desc())
        )

        total = await db.scalar(select(func.count()).select_from(query.subquery()))
        result = await db.execute(query.offset((page - 1) * limit).limit(limit))

        return {
            "items": ReelService._transform_reel_urls(result.scalars().all()),
            "total": total or 0,
            "page": page,
            "limit": limit,
            "has_more": ((page - 1) * limit + limit) < (total or 0),
        }

    # ── Feed simple (non connecté / fallback) ──────────────────────────────
    @staticmethod
    async def list_reels(page: int, limit: int, db: AsyncSession) -> dict:
        query = select(Reel).options(selectinload(Reel.author)).where(Reel.status == ReelStatus.published).order_by(Reel.created_at.desc())
        total = await db.scalar(select(func.count()).select_from(query.subquery()))
        result = await db.execute(query.offset((page - 1) * limit).limit(limit))
        return {"items": ReelService._transform_reel_urls(result.scalars().all()), "total": total, "page": page, "limit": limit}

    # ── Enregistrer une vue ────────────────────────────────────────────────
    @staticmethod
    async def record_view(reel_id: uuid.UUID, viewer_id: uuid.UUID, watch_ratio: float, db: AsyncSession) -> None:
        """
        Enregistre/met à jour une vue individuelle + incrémente le compteur global.
        watch_ratio : 0.0 (vu 0%) → 1.0 (vu 100%)
        """
        watch_ratio = max(0.0, min(1.0, watch_ratio))

        # Check existing view
        result = await db.execute(
            select(ReelView.id, ReelView.watch_ratio).where(
                ReelView.reel_id == reel_id,
                ReelView.viewer_id == viewer_id,
            )
        )
        existing = result.first()

        if existing:
            best_ratio = max(existing.watch_ratio, watch_ratio)
            await db.execute(
                sa_update(ReelView)
                .where(ReelView.id == existing.id)
                .values(watch_ratio=best_ratio, view_count=ReelView.view_count + 1, viewed_at=datetime.utcnow())
            )
        else:
            db.add(ReelView(reel_id=reel_id, viewer_id=viewer_id, watch_ratio=watch_ratio))
            # Atomic increment — no SELECT needed
            await db.execute(
                sa_update(Reel).where(Reel.id == reel_id).values(view_count=Reel.view_count + 1)
            )

        await db.commit()

    @staticmethod
    async def get_reel(reel_id: uuid.UUID, db: AsyncSession) -> Reel:
        result = await db.execute(
            select(Reel)
            .options(selectinload(Reel.author))
            .where(Reel.id == reel_id)
        )
        reel = result.scalar_one_or_none()
        if not reel:
            raise HTTPException(status_code=404, detail="Reel non trouvé")
        return ReelService._transform_single_reel_url(reel)

    @staticmethod
    async def create_reel(data: ReelCreate, user: User, db: AsyncSession) -> Reel:
        reel = Reel(
            **data.model_dump(exclude_none=True),
            user_id=user.id,
            status=ReelStatus.published,
        )
        db.add(reel)
        await db.commit()
        # Invalider le cache du feed pour que le reel apparaisse immediatement
        await cache_invalidate_prefix("fil_utilisateur:")
        await cache_invalidate_prefix("fil_anonymous:")
        # Recharger avec la relation author
        result = await db.execute(
            select(Reel).options(selectinload(Reel.author)).where(Reel.id == reel.id)
        )
        return result.scalar_one()

    @staticmethod
    async def update_reel(reel_id: uuid.UUID, data: ReelUpdate, user: User, db: AsyncSession) -> Reel:
        result = await db.execute(select(Reel).where(Reel.id == reel_id))
        reel = result.scalar_one_or_none()
        if not reel:
            raise HTTPException(status_code=404, detail="Reel non trouvé")
        role = user.role.value if hasattr(user.role, 'value') else user.role
        if reel.user_id != user.id and role != "admin":
            raise HTTPException(status_code=403, detail="Accès refusé")
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(reel, key, value)
        await db.commit()
        # Recharger avec la relation author
        result2 = await db.execute(
            select(Reel).options(selectinload(Reel.author)).where(Reel.id == reel_id)
        )
        return result2.scalar_one()

    @staticmethod
    async def delete_reel(reel_id: uuid.UUID, user: User, db: AsyncSession) -> None:
        result = await db.execute(select(Reel).where(Reel.id == reel_id))
        reel = result.scalar_one_or_none()
        if not reel:
            raise HTTPException(status_code=404, detail="Reel non trouvé")
        role = user.role.value if hasattr(user.role, 'value') else user.role
        if reel.user_id != user.id and role != "admin":
            raise HTTPException(status_code=403, detail="Accès refusé")
        video_url = reel.video_url
        thumbnail_url = reel.thumbnail_url
        await db.delete(reel)
        await db.commit()
        await delete_media(video_url)
        await delete_media(thumbnail_url)

    @staticmethod
    async def get_user_reels(user_id: uuid.UUID, db: AsyncSession) -> list:
        result = await db.execute(
            select(Reel)
            .where(Reel.user_id == user_id, Reel.status == ReelStatus.published)
            .options(selectinload(Reel.author))
            .order_by(Reel.created_at.desc())
        )
        return ReelService._transform_reel_urls(result.scalars().all())
