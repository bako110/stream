"""
Service social : commentaires, réactions (like/dislike), partages.
"""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from fastapi import HTTPException

from app.db.postgres.models.comment import Comment
from app.db.postgres.models.reaction import Reaction, ReactionType
from app.db.postgres.models.share import Share
from app.db.postgres.models.reel import Reel
from app.db.postgres.models.content import Content
from app.db.postgres.models.concert import Concert
from app.db.postgres.models.event import Event
from app.db.postgres.models.user import User
from app.schemas.social import CommentCreate, CommentUpdate, ReactionCreate, ShareCreate


# ── Clés cibles valides ───────────────────────────────────────────────────────

_TARGET_KEYS = ["reel_id", "content_id", "concert_id", "event_id"]
_ALL_TARGET_KEYS = _TARGET_KEYS + ["comment_id"]

_MODEL_MAP: dict = {
    "reel_id":     Reel,
    "content_id":  Content,
    "concert_id":  Concert,
    "event_id":    Event,
}


def _extract_targets(data_dict: dict, include_comment: bool = False) -> dict:
    """Retourne {clé: valeur} pour les champs cible non-None."""
    keys = _ALL_TARGET_KEYS if include_comment else _TARGET_KEYS
    return {k: data_dict[k] for k in keys if data_dict.get(k) is not None}


def _single_target(data_dict: dict) -> tuple[str, uuid.UUID]:
    """Vérifie qu'exactement une cible principale est fournie. Retourne (clé, valeur)."""
    found = [(k, data_dict[k]) for k in _TARGET_KEYS if data_dict.get(k) is not None]
    if len(found) != 1:
        raise HTTPException(
            status_code=400,
            detail="Précisez exactement une cible : reel_id, content_id, concert_id ou event_id",
        )
    return found[0]


async def _adjust_counter(target_key: str, target_id: uuid.UUID, delta: int, field: str, db: AsyncSession) -> None:
    """Incrémente/décrémente `field` sur l'objet cible identifié par (target_key, target_id)."""
    Model = _MODEL_MAP.get(target_key)
    if not Model:
        return
    result = await db.execute(select(Model).where(Model.id == target_id))
    obj = result.scalar_one_or_none()
    if obj and hasattr(obj, field):
        setattr(obj, field, max(0, getattr(obj, field) + delta))


# ── Commentaires ─────────────────────────────────────────────────────────────

class CommentService:

    @staticmethod
    async def list_comments(
        reel_id: uuid.UUID | None,
        content_id: uuid.UUID | None,
        concert_id: uuid.UUID | None,
        event_id: uuid.UUID | None,
        page: int,
        limit: int,
        db: AsyncSession,
    ) -> list:
        """Commentaires racine (sans parent) d'une cible, paginés."""
        query = select(Comment).where(Comment.parent_id.is_(None))

        if reel_id:
            query = query.where(Comment.reel_id == reel_id)
        elif content_id:
            query = query.where(Comment.content_id == content_id)
        elif concert_id:
            query = query.where(Comment.concert_id == concert_id)
        elif event_id:
            query = query.where(Comment.event_id == event_id)
        else:
            raise HTTPException(status_code=400, detail="Précisez une cible")

        query = query.order_by(Comment.created_at.desc()).offset((page - 1) * limit).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_replies(comment_id: uuid.UUID, db: AsyncSession) -> list:
        """Réponses directes à un commentaire."""
        result = await db.execute(
            select(Comment)
            .where(Comment.parent_id == comment_id)
            .order_by(Comment.created_at)
        )
        return result.scalars().all()

    @staticmethod
    async def create_comment(data: CommentCreate, user: User, db: AsyncSession) -> Comment:
        d = data.model_dump()

        if data.parent_id:
            # Réponse à un commentaire — hérite la cible du parent
            parent_result = await db.execute(select(Comment).where(Comment.id == data.parent_id))
            parent = parent_result.scalar_one_or_none()
            if not parent:
                raise HTTPException(status_code=404, detail="Commentaire parent non trouvé")
            # Hériter la cible du parent
            target_key = next((k for k in _TARGET_KEYS if getattr(parent, k) is not None), None)
            target_id = getattr(parent, target_key) if target_key else None
            comment = Comment(
                user_id=user.id,
                body=data.body,
                parent_id=data.parent_id,
                **({target_key: target_id} if target_key else {}),
            )
        else:
            target_key, target_id = _single_target(d)
            comment = Comment(
                user_id=user.id,
                body=data.body,
                **{target_key: target_id},
            )
            await _adjust_counter(target_key, target_id, +1, "comment_count", db)

        db.add(comment)
        await db.commit()
        await db.refresh(comment)
        return comment

    @staticmethod
    async def update_comment(comment_id: uuid.UUID, data: CommentUpdate, user: User, db: AsyncSession) -> Comment:
        result = await db.execute(select(Comment).where(Comment.id == comment_id))
        comment = result.scalar_one_or_none()
        if not comment:
            raise HTTPException(status_code=404, detail="Commentaire non trouvé")
        if comment.user_id != user.id:
            raise HTTPException(status_code=403, detail="Accès refusé")
        comment.body = data.body
        comment.is_edited = True
        await db.commit()
        await db.refresh(comment)
        return comment

    @staticmethod
    async def delete_comment(comment_id: uuid.UUID, user: User, db: AsyncSession) -> None:
        result = await db.execute(select(Comment).where(Comment.id == comment_id))
        comment = result.scalar_one_or_none()
        if not comment:
            raise HTTPException(status_code=404, detail="Commentaire non trouvé")
        if comment.user_id != user.id and user.role.value != "admin":
            raise HTTPException(status_code=403, detail="Accès refusé")

        # Décrémenter le compteur si commentaire racine
        if not comment.parent_id:
            target_key = next((k for k in _TARGET_KEYS if getattr(comment, k) is not None), None)
            if target_key:
                await _adjust_counter(target_key, getattr(comment, target_key), -1, "comment_count", db)

        await db.delete(comment)
        await db.commit()


# ── Réactions ─────────────────────────────────────────────────────────────────

class ReactionService:

    @staticmethod
    async def toggle_reaction(data: ReactionCreate, user: User, db: AsyncSession) -> dict:
        """
        Toggle réaction (like/dislike) sur une cible.
        - Même réaction → supprimée
        - Réaction opposée → changée
        - Pas de réaction → créée
        """
        d = data.model_dump()

        # Accepte aussi comment_id comme cible
        all_targets = _extract_targets(d, include_comment=True)
        if not all_targets:
            raise HTTPException(status_code=400, detail="Précisez une cible")

        # Trouver la cible principale (hors comment_id pour les compteurs)
        main_key = next((k for k in _TARGET_KEYS if d.get(k) is not None), None)
        main_id = d.get(main_key) if main_key else None

        # Chercher une réaction existante sur cette cible précise
        target_key, target_id = list(all_targets.items())[0]
        existing_result = await db.execute(
            select(Reaction).where(
                Reaction.user_id == user.id,
                getattr(Reaction, target_key) == target_id,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            if existing.reaction_type == data.reaction_type:
                # Annuler
                if main_key:
                    await _adjust_counter(main_key, main_id, -1, f"{data.reaction_type.value}_count", db)
                await db.delete(existing)
                await db.commit()
                return {"action": "removed", "reaction_type": data.reaction_type}
            else:
                # Changer
                old_type = existing.reaction_type
                if main_key:
                    await _adjust_counter(main_key, main_id, -1, f"{old_type.value}_count", db)
                    await _adjust_counter(main_key, main_id, +1, f"{data.reaction_type.value}_count", db)
                existing.reaction_type = data.reaction_type
                await db.commit()
                return {"action": "changed", "reaction_type": data.reaction_type}

        # Créer
        reaction = Reaction(user_id=user.id, reaction_type=data.reaction_type, **all_targets)
        db.add(reaction)
        if main_key:
            await _adjust_counter(main_key, main_id, +1, f"{data.reaction_type.value}_count", db)
        await db.commit()
        return {"action": "added", "reaction_type": data.reaction_type}

    @staticmethod
    async def get_my_reaction(
        user: User,
        reel_id: uuid.UUID | None,
        content_id: uuid.UUID | None,
        concert_id: uuid.UUID | None,
        event_id: uuid.UUID | None,
        db: AsyncSession,
    ) -> ReactionType | None:
        target_key, target_id = None, None
        for k, v in [("reel_id", reel_id), ("content_id", content_id),
                     ("concert_id", concert_id), ("event_id", event_id)]:
            if v is not None:
                target_key, target_id = k, v
                break
        if not target_key:
            return None
        result = await db.execute(
            select(Reaction).where(
                Reaction.user_id == user.id,
                getattr(Reaction, target_key) == target_id,
            )
        )
        r = result.scalar_one_or_none()
        return r.reaction_type if r else None

    @staticmethod
    async def get_counts(
        reel_id: uuid.UUID | None = None,
        content_id: uuid.UUID | None = None,
        concert_id: uuid.UUID | None = None,
        event_id: uuid.UUID | None = None,
        db: AsyncSession = None,
    ) -> dict:
        """Compteurs likes/dislikes pour une cible."""
        target_key, target_id = None, None
        for k, v in [("reel_id", reel_id), ("content_id", content_id),
                     ("concert_id", concert_id), ("event_id", event_id)]:
            if v is not None:
                target_key, target_id = k, v
                break
        if not target_key:
            return {"likes": 0, "dislikes": 0}

        col = getattr(Reaction, target_key)
        likes = await db.scalar(
            select(Reaction).where(col == target_id, Reaction.reaction_type == ReactionType.like).with_only_columns(
                __import__("sqlalchemy").func.count()
            )
        )
        dislikes = await db.scalar(
            select(Reaction).where(col == target_id, Reaction.reaction_type == ReactionType.dislike).with_only_columns(
                __import__("sqlalchemy").func.count()
            )
        )
        return {"likes": likes or 0, "dislikes": dislikes or 0}


# ── Partages ──────────────────────────────────────────────────────────────────

class ShareService:

    @staticmethod
    async def share(data: ShareCreate, user: User, db: AsyncSession) -> Share:
        """Enregistre un partage. Pas de déduplication — un user peut partager plusieurs fois."""
        d = data.model_dump()
        target_key, target_id = _single_target(d)

        share = Share(user_id=user.id, platform=data.platform, **{target_key: target_id})
        db.add(share)
        await _adjust_counter(target_key, target_id, +1, "share_count", db)
        await db.commit()
        await db.refresh(share)
        return share

    @staticmethod
    async def get_share_counts(
        reel_id: uuid.UUID | None = None,
        content_id: uuid.UUID | None = None,
        concert_id: uuid.UUID | None = None,
        event_id: uuid.UUID | None = None,
        db: AsyncSession = None,
    ) -> dict:
        """Compteur de partages par plateforme pour une cible."""
        from sqlalchemy import func
        target_key, target_id = None, None
        for k, v in [("reel_id", reel_id), ("content_id", content_id),
                     ("concert_id", concert_id), ("event_id", event_id)]:
            if v is not None:
                target_key, target_id = k, v
                break
        if not target_key:
            return {"total": 0, "by_platform": {}}

        col = getattr(Share, target_key)
        result = await db.execute(
            select(Share.platform, func.count().label("n"))
            .where(col == target_id)
            .group_by(Share.platform)
        )
        by_platform = {row.platform: row.n for row in result.all()}
        return {"total": sum(by_platform.values()), "by_platform": by_platform}
