"""
FeedService — Algorithme de classement des contenus v1.0

Pipeline :
  1. récupérer_candidats  (events + concerts + reels publiés, max 500)
  2. calculer_scores      (intérêt, engagement, fraîcheur, relation)
  3. appliquer_diversité  (pénalités même créateur / même catégorie)
  4. trier_par_score      (décroissant)
  5. mettre_en_cache      (Redis TTL 300s)
  6. retourner_fil

Formule score final :
  score = (intérêt × 3) + (engagement × 2) + (fraîcheur × 2) + (relation × 1.5) + pénalité_diversité
"""
import uuid
import math
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, union_all, literal_column, and_, case, String
from sqlalchemy.orm import selectinload

from app.db.postgres.models.event import Event, EventStatus
from app.db.postgres.models.concert import Concert, ConcertStatus
from app.db.postgres.models.reel import Reel, ReelStatus
from app.db.postgres.models.follow import Follow
from app.db.postgres.models.user_block import UserBlock
from app.db.postgres.models.user_interest import UserInterest
from app.db.postgres.models.reaction import Reaction
from app.db.postgres.models.comment import Comment
from app.db.postgres.models.share import Share
from app.utils.cache import cache_get, cache_set, cache_invalidate_prefix

logger = logging.getLogger(__name__)

# ── Constantes de l'algorithme ────────────────────────────────────────────────

WEIGHTS = {
    "interest":    3.0,
    "engagement":  2.0,
    "freshness":   2.0,
    "relation":    1.5,
}

ENGAGEMENT_WEIGHTS = {"like": 1, "comment": 2, "share": 3, "view": 0.5}

FRESHNESS_LAMBDA = 0.1  # décroissance exponentielle

RELATION_SCORES = {"friend": 1.5, "following": 1.2, "unknown": 1.0}

DIVERSITY = {
    "active": True,
    "same_creator_penalty": -0.3,
    "same_category_penalty": -0.2,
    "max_consecutive_same_creator": 2,
}

CANDIDATE_LIMIT = 500

INTEREST_UPDATE_DELTAS = {
    "like": 0.1,
    "comment": 0.2,
    "share": 0.3,
    "long_view": 0.3,
    "click": 0.1,
}

CACHE_TTL = 300  # 5 min


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class FeedItem:
    """Item du fil avec score calculé."""
    kind: str           # "event" | "concert" | "reel"
    id: str
    creator_id: str
    category: str       # event_type / genre / caption-based
    created_at: datetime
    data: dict = field(default_factory=dict)
    score: float = 0.0

    # sous-scores pour debug
    score_interest: float = 0.0
    score_engagement: float = 0.0
    score_freshness: float = 0.0
    score_relation: float = 0.0
    score_diversity: float = 0.0


# ── Service ───────────────────────────────────────────────────────────────────

class FeedService:

    # ── 1. Récupérer les candidats ────────────────────────────────────────────

    @staticmethod
    async def _fetch_candidates(db: AsyncSession) -> list[FeedItem]:
        """Récupère les contenus publiés récents (events + concerts + reels)."""
        items: list[FeedItem] = []

        # Events publiés
        ev_res = await db.execute(
            select(Event)
            .options(selectinload(Event.organizer))
            .where(Event.status == EventStatus.published)
            .order_by(Event.created_at.desc())
            .limit(200)
        )
        for e in ev_res.scalars().all():
            items.append(FeedItem(
                kind="event",
                id=str(e.id),
                creator_id=str(e.organizer_id),
                category=e.event_type.value if e.event_type else "other",
                created_at=e.created_at,
                data={
                    "id": str(e.id),
                    "title": e.title,
                    "description": e.description,
                    "event_type": e.event_type.value if e.event_type else None,
                    "status": e.status.value if e.status else None,
                    "access_type": e.access_type.value if e.access_type else None,
                    "venue_name": e.venue_name,
                    "venue_city": e.venue_city,
                    "venue_country": e.venue_country,
                    "is_online": e.is_online,
                    "online_url": e.online_url,
                    "starts_at": e.starts_at.isoformat() if e.starts_at else None,
                    "ends_at": e.ends_at.isoformat() if e.ends_at else None,
                    "ticket_price": float(e.ticket_price) if e.ticket_price else None,
                    "max_attendees": e.max_attendees,
                    "current_attendees": e.current_attendees,
                    "thumbnail_url": e.thumbnail_url,
                    "banner_url": e.banner_url,
                    "gallery_urls": e.gallery_urls,
                    "is_featured": e.is_featured,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                    "organizer": {
                        "id": str(e.organizer.id),
                        "username": e.organizer.username,
                        "display_name": e.organizer.display_name,
                        "avatar_url": e.organizer.avatar_url,
                    } if e.organizer else None,
                },
            ))

        # Concerts publiés
        co_res = await db.execute(
            select(Concert)
            .options(selectinload(Concert.artist))
            .where(Concert.status.in_([ConcertStatus.published, ConcertStatus.live]))
            .order_by(Concert.created_at.desc())
            .limit(200)
        )
        for c in co_res.scalars().all():
            items.append(FeedItem(
                kind="concert",
                id=str(c.id),
                creator_id=str(c.artist_id),
                category=c.genre or "music",
                created_at=c.created_at,
                data={
                    "id": str(c.id),
                    "title": c.title,
                    "description": c.description,
                    "genre": c.genre,
                    "venue_name": c.venue_name,
                    "venue_city": c.venue_city,
                    "venue_country": c.venue_country,
                    "scheduled_at": c.scheduled_at.isoformat() if c.scheduled_at else None,
                    "duration_min": c.duration_min,
                    "concert_type": c.concert_type.value if c.concert_type else None,
                    "access_type": c.access_type.value if c.access_type else None,
                    "status": c.status.value if c.status else None,
                    "ticket_price": float(c.ticket_price) if c.ticket_price else None,
                    "max_viewers": c.max_viewers,
                    "current_viewers": c.current_viewers,
                    "view_count": c.view_count,
                    "thumbnail_url": c.thumbnail_url,
                    "banner_url": c.banner_url,
                    "is_featured": c.is_featured,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "artist": {
                        "id": str(c.artist.id),
                        "username": c.artist.username,
                        "display_name": c.artist.display_name,
                        "avatar_url": c.artist.avatar_url,
                    } if c.artist else None,
                },
            ))

        # Reels publiés
        re_res = await db.execute(
            select(Reel)
            .options(selectinload(Reel.author))
            .where(Reel.status == ReelStatus.published)
            .order_by(Reel.created_at.desc())
            .limit(100)
        )
        for r in re_res.scalars().all():
            items.append(FeedItem(
                kind="reel",
                id=str(r.id),
                creator_id=str(r.user_id),
                category="reel",
                created_at=r.created_at,
                data={
                    "id": str(r.id),
                    "caption": r.caption,
                    "video_url": r.video_url,
                    "thumbnail_url": r.thumbnail_url,
                    "duration_sec": r.duration_sec,
                    "view_count": r.view_count,
                    "like_count": r.like_count,
                    "comment_count": r.comment_count,
                    "share_count": r.share_count,
                    "is_featured": r.is_featured,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "author": {
                        "id": str(r.author.id),
                        "username": r.author.username,
                        "display_name": r.author.display_name,
                        "avatar_url": r.author.avatar_url,
                    } if r.author else None,
                },
            ))

        return items[:CANDIDATE_LIMIT]

    # ── 2. Calculer les scores ────────────────────────────────────────────────

    @staticmethod
    async def _get_user_interests(user_id: uuid.UUID, db: AsyncSession) -> dict[str, float]:
        """Récupère les intérêts de l'utilisateur."""
        res = await db.execute(
            select(UserInterest).where(UserInterest.user_id == user_id)
        )
        return {ui.category: ui.score for ui in res.scalars().all()}

    @staticmethod
    async def _get_following_ids(user_id: uuid.UUID, db: AsyncSession) -> set[str]:
        """IDs des utilisateurs suivis."""
        res = await db.execute(
            select(Follow.following_id).where(Follow.follower_id == user_id)
        )
        return {str(r[0]) for r in res.all()}

    @staticmethod
    async def _get_all_engagement_counts(
        items: list["FeedItem"], db: AsyncSession
    ) -> dict[str, dict[str, int]]:
        """
        Récupère les compteurs engagement pour TOUS les items en 3 requêtes (batch),
        au lieu de 3 requêtes × N items.
        Retourne {item_id: {"likes": x, "comments": y, "shares": z}}.
        """
        event_ids   = [i.id for i in items if i.kind == "event"]
        concert_ids = [i.id for i in items if i.kind == "concert"]
        reel_ids    = [i.id for i in items if i.kind == "reel"]

        counts: dict[str, dict[str, int]] = {i.id: {"likes": 0, "comments": 0, "shares": 0} for i in items}

        # ── Likes batch ────────────────────────────────────────────────────────
        like_queries = []
        if event_ids:
            like_queries.append(
                select(
                    Reaction.event_id.cast(String).label("item_id"),
                    func.count().label("n"),
                ).where(Reaction.event_id.in_(event_ids), Reaction.reaction_type == "like")
                .group_by(Reaction.event_id)
            )
        if concert_ids:
            like_queries.append(
                select(
                    Reaction.concert_id.cast(String).label("item_id"),
                    func.count().label("n"),
                ).where(Reaction.concert_id.in_(concert_ids), Reaction.reaction_type == "like")
                .group_by(Reaction.concert_id)
            )
        if reel_ids:
            like_queries.append(
                select(
                    Reaction.reel_id.cast(String).label("item_id"),
                    func.count().label("n"),
                ).where(Reaction.reel_id.in_(reel_ids), Reaction.reaction_type == "like")
                .group_by(Reaction.reel_id)
            )
        for q in like_queries:
            rows = (await db.execute(q)).all()
            for row in rows:
                if row.item_id in counts:
                    counts[row.item_id]["likes"] = row.n

        # ── Comments batch ─────────────────────────────────────────────────────
        comment_queries = []
        if event_ids:
            comment_queries.append(
                select(Comment.event_id.cast(String).label("item_id"), func.count().label("n"))
                .where(Comment.event_id.in_(event_ids)).group_by(Comment.event_id)
            )
        if concert_ids:
            comment_queries.append(
                select(Comment.concert_id.cast(String).label("item_id"), func.count().label("n"))
                .where(Comment.concert_id.in_(concert_ids)).group_by(Comment.concert_id)
            )
        if reel_ids:
            comment_queries.append(
                select(Comment.reel_id.cast(String).label("item_id"), func.count().label("n"))
                .where(Comment.reel_id.in_(reel_ids)).group_by(Comment.reel_id)
            )
        for q in comment_queries:
            rows = (await db.execute(q)).all()
            for row in rows:
                if row.item_id in counts:
                    counts[row.item_id]["comments"] = row.n

        # ── Shares batch ───────────────────────────────────────────────────────
        share_queries = []
        if event_ids:
            share_queries.append(
                select(Share.event_id.cast(String).label("item_id"), func.count().label("n"))
                .where(Share.event_id.in_(event_ids)).group_by(Share.event_id)
            )
        if concert_ids:
            share_queries.append(
                select(Share.concert_id.cast(String).label("item_id"), func.count().label("n"))
                .where(Share.concert_id.in_(concert_ids)).group_by(Share.concert_id)
            )
        if reel_ids:
            share_queries.append(
                select(Share.reel_id.cast(String).label("item_id"), func.count().label("n"))
                .where(Share.reel_id.in_(reel_ids)).group_by(Share.reel_id)
            )
        for q in share_queries:
            rows = (await db.execute(q)).all()
            for row in rows:
                if row.item_id in counts:
                    counts[row.item_id]["shares"] = row.n

        return counts

    @staticmethod
    async def _get_user_reactions_batch(
        user_id: uuid.UUID,
        items: list["FeedItem"],
        db: AsyncSession,
    ) -> dict[str, str | None]:
        """
        Une seule requête pour toutes les réactions de l'utilisateur sur les items du fil.
        Retourne {item_id: "like" | "dislike" | None}.
        """
        event_ids   = [uuid.UUID(i.id) for i in items if i.kind == "event"]
        concert_ids = [uuid.UUID(i.id) for i in items if i.kind == "concert"]
        reel_ids    = [uuid.UUID(i.id) for i in items if i.kind == "reel"]

        from sqlalchemy import or_
        conditions = []
        if event_ids:
            conditions.append(Reaction.event_id.in_(event_ids))
        if concert_ids:
            conditions.append(Reaction.concert_id.in_(concert_ids))
        if reel_ids:
            conditions.append(Reaction.reel_id.in_(reel_ids))

        if not conditions:
            return {}

        res = await db.execute(
            select(Reaction).where(
                Reaction.user_id == user_id,
                or_(*conditions),
            )
        )
        reactions = res.scalars().all()

        result: dict[str, str | None] = {}
        for r in reactions:
            target_id = r.event_id or r.concert_id or r.reel_id
            if target_id:
                result[str(target_id)] = r.reaction_type.value
        return result

    @staticmethod
    def _calc_engagement(counts: dict, view_count: int = 0) -> float:
        """log(1 + likes*1 + comments*2 + shares*3 + views*0.5)"""
        raw = (
            counts["likes"] * ENGAGEMENT_WEIGHTS["like"]
            + counts["comments"] * ENGAGEMENT_WEIGHTS["comment"]
            + counts["shares"] * ENGAGEMENT_WEIGHTS["share"]
            + view_count * ENGAGEMENT_WEIGHTS["view"]
        )
        return math.log1p(raw)

    @staticmethod
    def _calc_freshness(created_at: datetime) -> float:
        """exp(-lambda * age_heures)"""
        age_hours = max((datetime.utcnow() - created_at).total_seconds() / 3600, 0)
        return math.exp(-FRESHNESS_LAMBDA * age_hours)

    @staticmethod
    def _calc_relation(creator_id: str, following_ids: set[str]) -> float:
        """Score basé sur la relation utilisateur-créateur."""
        if creator_id in following_ids:
            return RELATION_SCORES["following"]
        return RELATION_SCORES["unknown"]

    @staticmethod
    def _calc_interest(category: str, user_interests: dict[str, float]) -> float:
        """Score basé sur l'intérêt de l'utilisateur pour la catégorie."""
        return user_interests.get(category, 0.0)

    async def _score_items(
        self,
        items: list[FeedItem],
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> list[FeedItem]:
        """Calcule tous les sous-scores pour chaque item."""
        user_interests = await self._get_user_interests(user_id, db)
        following_ids = await self._get_following_ids(user_id, db)

        # Batch : 1 seule série de requêtes agrégées pour tous les items
        all_counts = await self._get_all_engagement_counts(items, db)

        # Batch : réaction de l'utilisateur sur chaque item (évite N+1 reactions/me)
        user_reactions = await self._get_user_reactions_batch(user_id, items, db)

        for item in items:
            counts = all_counts.get(item.id, {"likes": 0, "comments": 0, "shares": 0})
            view_count = item.data.get("view_count", 0) or 0
            item.score_engagement = self._calc_engagement(counts, view_count)

            # Injecter les compteurs dans data pour la sérialisation
            item.data["like_count"] = counts["likes"]
            item.data["comment_count"] = counts["comments"]
            item.data["share_count"] = counts["shares"]

            # Injecter la réaction de l'utilisateur (null | "like" | "dislike")
            item.data["user_reaction"] = user_reactions.get(item.id)

            # Fraîcheur
            item.score_freshness = self._calc_freshness(item.created_at)

            # Relation
            item.score_relation = self._calc_relation(item.creator_id, following_ids)

            # Intérêt
            item.score_interest = self._calc_interest(item.category, user_interests)

            # Score final (sans diversité encore)
            item.score = (
                item.score_interest * WEIGHTS["interest"]
                + item.score_engagement * WEIGHTS["engagement"]
                + item.score_freshness * WEIGHTS["freshness"]
                + item.score_relation * WEIGHTS["relation"]
            )

        return items

    # ── 3. Appliquer la diversité ─────────────────────────────────────────────

    @staticmethod
    def _apply_diversity(items: list[FeedItem]) -> list[FeedItem]:
        """Pénalise les items consécutifs du même créateur ou même catégorie."""
        if not DIVERSITY["active"]:
            return items

        consecutive_creator = 0
        last_creator_id: Optional[str] = None
        last_category: Optional[str] = None

        for item in items:
            # Pénalité même créateur
            if item.creator_id == last_creator_id:
                consecutive_creator += 1
                if consecutive_creator > DIVERSITY["max_consecutive_same_creator"]:
                    item.score_diversity += DIVERSITY["same_creator_penalty"]
            else:
                consecutive_creator = 1

            # Pénalité même catégorie
            if item.category == last_category:
                item.score_diversity += DIVERSITY["same_category_penalty"]

            # Appliquer la pénalité au score final
            item.score += item.score_diversity

            last_creator_id = item.creator_id
            last_category = item.category

        return items

    # ── 4. Trier ──────────────────────────────────────────────────────────────

    @staticmethod
    def _sort_by_score(items: list[FeedItem]) -> list[FeedItem]:
        return sorted(items, key=lambda i: i.score, reverse=True)

    # ── Pipeline principal ────────────────────────────────────────────────────

    @staticmethod
    async def _get_blocked_ids(user_id: uuid.UUID, db: AsyncSession) -> set[str]:
        """IDs des utilisateurs bloqués par user_id (dans les deux sens)."""
        res = await db.execute(
            select(UserBlock.blocked_id).where(UserBlock.blocker_id == user_id)
        )
        blocked = {str(r[0]) for r in res.all()}
        # Aussi exclure ceux qui m'ont bloqué
        res2 = await db.execute(
            select(UserBlock.blocker_id).where(UserBlock.blocked_id == user_id)
        )
        blocked |= {str(r[0]) for r in res2.all()}
        return blocked

    @staticmethod
    async def get_feed(
        user_id: uuid.UUID,
        page: int,
        limit: int,
        db: AsyncSession,
    ) -> dict:
        """
        Pipeline complet : candidats → scores → diversité → tri → cache → retour.
        """
        # Vérifier le cache Redis
        cache_key = f"fil_utilisateur:{user_id}:p{page}:l{limit}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        service = FeedService()

        # 1. Récupérer les candidats
        items = await service._fetch_candidates(db)

        # Filtrer les utilisateurs bloqués
        blocked_ids = await service._get_blocked_ids(user_id, db)
        if blocked_ids:
            items = [i for i in items if i.creator_id not in blocked_ids]

        # Filtrer par intérêts utilisateur si possible
        user_interests = await service._get_user_interests(user_id, db)
        if user_interests:
            pass

        # 2. Calculer les scores
        items = await service._score_items(items, user_id, db)

        # 3. Appliquer la diversité
        items = service._apply_diversity(items)

        # 4. Trier par score
        items = service._sort_by_score(items)

        # Pagination
        total = len(items)
        start = (page - 1) * limit
        page_items = items[start:start + limit]

        # Sérialiser
        result_items = []
        for fi in page_items:
            entry = {"kind": fi.kind, "score": round(fi.score, 4)}
            entry.update(fi.data)
            result_items.append(entry)

        result = {
            "items": result_items,
            "total": total,
            "page": page,
            "limit": limit,
        }

        # 5. Mettre en cache
        await cache_set(cache_key, result, ttl=CACHE_TTL)

        return result

    # ── Mise à jour des intérêts ──────────────────────────────────────────────

    @staticmethod
    async def update_user_interest(
        user_id: uuid.UUID,
        category: str,
        action: str,
        db: AsyncSession,
    ) -> None:
        """
        Met à jour le score d'intérêt d'un utilisateur pour une catégorie.
        action : "like" | "comment" | "share" | "long_view" | "click"
        """
        delta = INTEREST_UPDATE_DELTAS.get(action, 0.0)
        if delta == 0.0:
            return

        # Upsert : trouver l'existant ou créer
        res = await db.execute(
            select(UserInterest).where(
                UserInterest.user_id == user_id,
                UserInterest.category == category,
            )
        )
        ui = res.scalar_one_or_none()

        if ui:
            ui.score = min(ui.score + delta, 10.0)  # plafond à 10
            ui.updated_at = datetime.utcnow()
        else:
            ui = UserInterest(
                user_id=user_id,
                category=category,
                score=min(delta, 10.0),
            )
            db.add(ui)

        await db.commit()

        # Invalider le cache du fil pour cet utilisateur
        await cache_invalidate_prefix(f"fil_utilisateur:{user_id}:")

    # ── Fil anonyme (sans personnalisation) ───────────────────────────────────

    @staticmethod
    async def get_feed_anonymous(page: int, limit: int, db: AsyncSession) -> dict:
        """Fil pour utilisateur non connecté : fraîcheur + engagement simple."""
        cache_key = f"fil_anonymous:p{page}:l{limit}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        service = FeedService()
        items = await service._fetch_candidates(db)

        # Score simple : engagement + fraîcheur (sans intérêt ni relation)
        for item in items:
            counts = await service._get_engagement_counts(item.kind, item.id, db)
            view_count = item.data.get("view_count", 0) or 0
            item.score_engagement = service._calc_engagement(counts, view_count)
            item.score_freshness = service._calc_freshness(item.created_at)
            item.score = (
                item.score_engagement * WEIGHTS["engagement"]
                + item.score_freshness * WEIGHTS["freshness"]
            )

        items = service._apply_diversity(items)
        items = service._sort_by_score(items)

        total = len(items)
        start = (page - 1) * limit
        page_items = items[start:start + limit]

        result_items = []
        for fi in page_items:
            entry = {"kind": fi.kind, "score": round(fi.score, 4)}
            entry.update(fi.data)
            result_items.append(entry)

        result = {"items": result_items, "total": total, "page": page, "limit": limit}
        await cache_set(cache_key, result, ttl=CACHE_TTL)
        return result
