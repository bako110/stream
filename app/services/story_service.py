import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.db.postgres.models.story import Story, StoryView
from app.db.postgres.models.user import User
from app.db.postgres.models.follow import Follow
from app.schemas.story import StoryCreate, StoryUpdate, StoryResponse, StoryGroupResponse, StoryAuthor, StoryViewerResponse
from app.services.ws_manager import manager as ws_manager


class StoryService:

    # ── Créer une story ───────────────────────────────────────────────────────

    @staticmethod
    async def create(user_id: uuid.UUID, data: StoryCreate, db: AsyncSession) -> Story:
        story = Story(
            user_id=user_id,
            media_url=data.media_url,
            media_type=data.media_type,
            thumbnail_url=data.thumbnail_url,
            caption=data.caption,
            duration_sec=data.duration_sec,
            background_color=data.background_color,
            audio_url=data.audio_url,
            font_style=data.font_style,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        db.add(story)
        await db.commit()
        await db.refresh(story, attribute_names=["id", "user_id", "media_url", "media_type",
            "thumbnail_url", "caption", "duration_sec", "view_count", "is_active",
            "expires_at", "created_at"])
        # Eager-load author for StoryResponse serialization
        result = await db.execute(
            select(Story)
            .where(Story.id == story.id)
            .options(selectinload(Story.author))
        )
        story = result.scalar_one()

        # Broadcast new story to all connected users via WebSocket
        author = story.author
        await ws_manager.broadcast_all({
            "type": "new_story",
            "story": {
                "id": str(story.id),
                "user_id": str(story.user_id),
                "media_type": story.media_type.value,
                "caption": story.caption,
                "created_at": story.created_at.isoformat(),
            },
            "author": {
                "id": str(author.id),
                "username": author.username,
                "display_name": author.display_name,
                "avatar_url": author.avatar_url,
            } if author else None,
        })

        return story

    # ── Feed stories (groupé par user, comme WhatsApp) ────────────────────────

    @staticmethod
    async def get_feed(current_user_id: uuid.UUID, db: AsyncSession) -> list[StoryGroupResponse]:
        now = datetime.utcnow()

        # IDs des utilisateurs suivis + ceux qui me suivent (séquentiel — même session)
        following_result = await db.execute(
            select(Follow.following_id).where(Follow.follower_id == current_user_id)
        )
        followers_result = await db.execute(
            select(Follow.follower_id).where(Follow.following_id == current_user_id)
        )
        allowed_ids = (
            set(following_result.scalars().all())
            | set(followers_result.scalars().all())
            | {current_user_id}
        )

        result = await db.execute(
            select(Story)
            .options(selectinload(Story.author), selectinload(Story.views))
            .where(
                Story.is_active == True,
                Story.expires_at > now,
                Story.user_id.in_(allowed_ids),
            )
            .order_by(Story.created_at.asc())
        )
        stories = result.scalars().all()

        # IDs des stories déjà vues par cet utilisateur
        viewed_result = await db.execute(
            select(StoryView.story_id)
            .where(StoryView.viewer_id == current_user_id)
        )
        viewed_ids = set(viewed_result.scalars().all())

        # Grouper par user
        groups: dict[uuid.UUID, dict] = {}
        for story in stories:
            uid = story.user_id
            if uid not in groups:
                groups[uid] = {"user": story.author, "stories": [], "has_unseen": False}
            viewed = story.id in viewed_ids
            story_resp = StoryResponse(
                id=story.id,
                user_id=story.user_id,
                media_url=story.media_url,
                media_type=story.media_type,
                thumbnail_url=story.thumbnail_url,
                caption=story.caption,
                duration_sec=story.duration_sec,
                view_count=story.view_count,
                is_active=story.is_active,
                expires_at=story.expires_at,
                created_at=story.created_at,
                background_color=story.background_color,
                audio_url=story.audio_url,
                author=StoryAuthor.model_validate(story.author) if story.author else None,
                viewed_by_me=viewed,
            )
            groups[uid]["stories"].append(story_resp)
            if not viewed:
                groups[uid]["has_unseen"] = True

        # Tri : stories avec non-vues en premier, puis par date de la dernière story
        sorted_groups = sorted(
            groups.values(),
            key=lambda g: (not g["has_unseen"], -g["stories"][-1].created_at.timestamp())
        )

        return [
            StoryGroupResponse(
                user=StoryAuthor.model_validate(g["user"]),
                stories=g["stories"],
                has_unseen=g["has_unseen"],
            )
            for g in sorted_groups
        ]

    # ── Mes stories ───────────────────────────────────────────────────────────

    @staticmethod
    async def get_my_stories(user_id: uuid.UUID, db: AsyncSession) -> list[Story]:
        now = datetime.utcnow()
        result = await db.execute(
            select(Story)
            .options(selectinload(Story.views), selectinload(Story.author))
            .where(Story.user_id == user_id, Story.expires_at > now)
            .order_by(Story.created_at.desc())
        )
        return result.scalars().all()

    # ── Marquer vue ───────────────────────────────────────────────────────────

    @staticmethod
    async def mark_viewed(story_id: uuid.UUID, viewer_id: uuid.UUID, db: AsyncSession) -> None:
        # Vérifier si déjà vue
        existing = await db.execute(
            select(StoryView).where(
                StoryView.story_id == story_id,
                StoryView.viewer_id == viewer_id,
            )
        )
        if existing.scalar_one_or_none():
            return

        view = StoryView(story_id=story_id, viewer_id=viewer_id)
        db.add(view)

        # Incrémenter compteur
        story = await db.get(Story, story_id)
        if story:
            story.view_count += 1

        await db.commit()

    # ── Modifier une story ─────────────────────────────────────────────────────

    @staticmethod
    async def update(story_id: uuid.UUID, user_id: uuid.UUID, data: StoryUpdate, db: AsyncSession) -> Story:
        story = await db.get(Story, story_id)
        if not story:
            raise HTTPException(status_code=404, detail="Story introuvable")
        if story.user_id != user_id:
            raise HTTPException(status_code=403, detail="Action non autorisée")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(story, field, value)
        await db.commit()
        result = await db.execute(
            select(Story).where(Story.id == story.id).options(selectinload(Story.author))
        )
        return result.scalar_one()

    # ── Supprimer une story ───────────────────────────────────────────────────

    @staticmethod
    async def delete(story_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> None:
        story = await db.get(Story, story_id)
        if not story:
            raise HTTPException(status_code=404, detail="Story introuvable")
        if story.user_id != user_id:
            raise HTTPException(status_code=403, detail="Action non autorisée")
        await db.delete(story)
        await db.commit()

    # ── Viewers d'une story (seulement pour le propriétaire) ─────────────────

    @staticmethod
    async def get_viewers(story_id: uuid.UUID, requesting_user_id: uuid.UUID, db: AsyncSession) -> list[StoryViewerResponse]:
        story = await db.get(Story, story_id)
        if not story:
            raise HTTPException(status_code=404, detail="Story introuvable")
        if story.user_id != requesting_user_id:
            raise HTTPException(status_code=403, detail="Accès non autorisé")

        result = await db.execute(
            select(StoryView, User)
            .join(User, User.id == StoryView.viewer_id)
            .where(StoryView.story_id == story_id)
            .order_by(StoryView.viewed_at.desc())
        )
        rows = result.all()
        return [
            StoryViewerResponse(
                id=user.id,
                username=user.username,
                display_name=user.display_name,
                avatar_url=user.avatar_url,
                viewed_at=view.viewed_at,
            )
            for view, user in rows
        ]

    # ── Nettoyage stories expirées (tâche périodique) ─────────────────────────

    @staticmethod
    async def cleanup_expired(db: AsyncSession) -> int:
        result = await db.execute(
            delete(Story).where(Story.expires_at <= datetime.utcnow())
        )
        await db.commit()
        return result.rowcount
