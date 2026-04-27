"""
NotificationService — création, lecture et suppression des notifications persistantes.
Chaque notification est sauvegardée en base ET poussée en temps réel via WebSocket.
"""
import uuid
import logging
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.models.notification import Notification, NotificationType
from app.db.postgres.models.device_token import DeviceToken
from app.services.ws_manager import manager
from app.services.fcm_service import send_push_multicast

logger = logging.getLogger(__name__)

# Titres par défaut pour chaque type
_TITLES: dict[NotificationType, str] = {
    NotificationType.follow:           "Nouvel abonné",
    NotificationType.reaction:         "Nouvelle réaction",
    NotificationType.comment:          "Nouveau commentaire",
    NotificationType.mention:          "Vous avez été mentionné",
    NotificationType.profile_view:     "Visite de profil",
    NotificationType.story_view:       "Vue sur votre story",
    NotificationType.concert_created:  "Nouveau concert",
    NotificationType.event_created:    "Nouvel événement",
    NotificationType.concert_going:    "Concert — billet confirmé",
    NotificationType.event_going:      "Événement — inscription confirmée",
    NotificationType.community_joined: "Communauté",
    NotificationType.reel_posted:      "Nouveau reel",
    NotificationType.subscription:     "Abonnement",
    NotificationType.welcome:          "Bienvenue sur FoliX 🎉",
    NotificationType.ticket:           "Confirmation de billet",
    NotificationType.system:           "Notification système",
}


class NotificationService:

    @staticmethod
    async def create(
        user_id: uuid.UUID,
        notification_type: NotificationType,
        body: str,
        db: AsyncSession,
        *,
        actor_id: uuid.UUID | None = None,
        title: str | None = None,
        ref_id: str | None = None,
        ref_type: str | None = None,
    ) -> Notification:
        """Crée une notification persistante et la pousse en WS au destinataire."""
        notif = Notification(
            user_id=user_id,
            actor_id=actor_id,
            notification_type=notification_type,
            title=title or _TITLES.get(notification_type, "Notification"),
            body=body,
            ref_id=ref_id,
            ref_type=ref_type,
            is_read=False,
        )
        db.add(notif)
        await db.commit()
        await db.refresh(notif)

        # Push WS temps réel
        try:
            actor = notif.actor
            ws_payload: dict = {
                "type":              "notification",
                "notification_type": notification_type.value,
                "id":                str(notif.id),
                "title":             notif.title,
                "body":              notif.body,
                "ref_id":            ref_id,
                "ref_type":          ref_type,
                "created_at":        notif.created_at.isoformat(),
                "actor": {
                    "id":           str(actor.id),
                    "username":     actor.username,
                    "display_name": actor.display_name,
                    "avatar_url":   actor.avatar_url,
                } if actor else None,
            }
            await manager.send_to_user(str(user_id), ws_payload)
        except Exception:
            logger.debug("WS push failed for notification %s", notif.id)

        # FCM push — toujours envoyé (background/quit reçoit via setBackgroundMessageHandler,
        # foreground filtré par onMessage côté app pour éviter le double affichage)
        try:
            tokens_result = await db.execute(
                select(DeviceToken.token).where(DeviceToken.user_id == user_id)
            )
            tokens = tokens_result.scalars().all()
            if tokens:
                fcm_data = {
                    "type":              "notification",
                    "notif_id":          str(notif.id),
                    "notification_type": notification_type.value,
                }
                if ref_id:
                    fcm_data["ref_id"] = ref_id
                if ref_type:
                    fcm_data["ref_type"] = ref_type
                await send_push_multicast(list(tokens), notif.title, notif.body, fcm_data)
        except Exception:
            logger.debug("FCM push failed for notification %s", notif.id)

        return notif

    @staticmethod
    async def get_for_user(
        user_id: uuid.UUID,
        db: AsyncSession,
        page: int = 1,
        limit: int = 30,
        unread_only: bool = False,
    ) -> list[Notification]:
        q = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            q = q.where(Notification.is_read.is_(False))
        q = q.order_by(Notification.created_at.desc()).offset((page - 1) * limit).limit(limit)
        result = await db.execute(q)
        return result.scalars().all()

    @staticmethod
    async def unread_count(user_id: uuid.UUID, db: AsyncSession) -> int:
        result = await db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        )
        return result.scalar_one() or 0

    @staticmethod
    async def mark_read(notif_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> None:
        await db.execute(
            update(Notification)
            .where(Notification.id == notif_id, Notification.user_id == user_id)
            .values(is_read=True)
        )
        await db.commit()

    @staticmethod
    async def mark_all_read(user_id: uuid.UUID, db: AsyncSession) -> int:
        result = await db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True)
        )
        await db.commit()
        return result.rowcount

    @staticmethod
    async def delete(notif_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> None:
        await db.execute(
            delete(Notification).where(
                Notification.id == notif_id, Notification.user_id == user_id,
            )
        )
        await db.commit()

    @staticmethod
    async def delete_all(user_id: uuid.UUID, db: AsyncSession) -> None:
        await db.execute(delete(Notification).where(Notification.user_id == user_id))
        await db.commit()
