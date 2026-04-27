import uuid
import logging
from sqlalchemy import select, or_, and_, join
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.models.activity import Activity, ActivityType
from app.db.postgres.models.follow import Follow
from app.db.postgres.models.user import User
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)

_NOTIF_BODY: dict[ActivityType, str] = {
    ActivityType.follow:           "{actor} a commencé à vous suivre.",
    ActivityType.reaction:         "{actor} a réagi à votre contenu.",
    ActivityType.comment:          "{actor} a commenté votre contenu.",
    ActivityType.mention:          "{actor} vous a mentionné.",
    ActivityType.profile_view:     "{actor} a visité votre profil.",
    ActivityType.story_view:       "{actor} a vu votre story.",
    ActivityType.concert_created:  "{actor} a créé un nouveau concert.",
    ActivityType.event_created:    "{actor} a créé un nouvel événement.",
    ActivityType.concert_going:    "{actor} va à un concert.",
    ActivityType.event_going:      "{actor} va à un événement.",
    ActivityType.community_joined: "{actor} a rejoint une communauté.",
    ActivityType.reel_posted:      "{actor} a posté un nouveau reel.",
    ActivityType.subscription:     "{actor} s'est abonné à votre compte.",
    ActivityType.welcome:          "Bienvenue sur FoliX ! Explorez la musique, les concerts et les événements.",
}

_NOTIFY_TYPES = {
    ActivityType.follow,
    ActivityType.reaction,
    ActivityType.comment,
    ActivityType.mention,
    ActivityType.profile_view,
    ActivityType.story_view,
    ActivityType.subscription,
    ActivityType.welcome,
    ActivityType.concert_created,
    ActivityType.event_created,
}

# Ces types sont bloqués si la cible a désactivé privacy_show_activity
_ACTIVITY_BLOCKED_BY_SHOW_ACTIVITY = {
    ActivityType.profile_view,
    ActivityType.story_view,
}

# Ces types sont bloqués si l'acteur a désactivé privacy_show_online
_ACTIVITY_BLOCKED_BY_SHOW_ONLINE = {
    ActivityType.profile_view,
}


class ActivityService:

    @staticmethod
    async def log(
        actor_id: uuid.UUID,
        activity_type: ActivityType,
        db: AsyncSession,
        target_user_id: uuid.UUID | None = None,
        ref_id: str | None = None,
        summary: str | None = None,
        actor_name: str | None = None,
    ) -> Activity:

        # Vérifier les settings privacy avant de notifier
        if target_user_id and target_user_id != actor_id:
            # Charger les settings du destinataire ET de l'acteur en une requête
            rows = await db.execute(
                select(User.id, User.privacy_show_activity, User.privacy_show_online)
                .where(User.id.in_([target_user_id, actor_id]))
            )
            privacy_map = {str(r.id): r for r in rows}

            target_priv = privacy_map.get(str(target_user_id))
            actor_priv  = privacy_map.get(str(actor_id))

            # La cible a désactivé "afficher l'activité" → pas de notif profile_view/story_view
            if (target_priv and not target_priv.privacy_show_activity
                    and activity_type in _ACTIVITY_BLOCKED_BY_SHOW_ACTIVITY):
                return Activity(actor_id=actor_id, activity_type=activity_type)  # fantôme, non persisté

            # L'acteur a désactivé "afficher le statut en ligne" → pas de notif profile_view
            if (actor_priv and not actor_priv.privacy_show_online
                    and activity_type in _ACTIVITY_BLOCKED_BY_SHOW_ONLINE):
                return Activity(actor_id=actor_id, activity_type=activity_type)

        activity = Activity(
            actor_id=actor_id,
            target_user_id=target_user_id,
            activity_type=activity_type,
            ref_id=ref_id,
            summary=summary,
        )
        db.add(activity)
        await db.commit()
        await db.refresh(activity)

        actor = activity.actor  # selectin déjà chargé
        actor_display = actor_name or (
            (actor.display_name or actor.username) if actor else "Quelqu'un"
        )

        if target_user_id and target_user_id != actor_id:
            try:
                ws_payload: dict = {
                    "type":          "activity",
                    "id":            str(activity.id),
                    "activity_type": activity_type.value,
                    "actor_id":      str(actor_id),
                    "actor": {
                        "id":           str(actor.id),
                        "username":     actor.username,
                        "display_name": actor.display_name,
                        "avatar_url":   actor.avatar_url,
                    } if actor else None,
                    "ref_id":        ref_id,
                    "summary":       summary or _NOTIF_BODY.get(activity_type, "").format(actor=actor_display),
                    "created_at":    activity.created_at.isoformat(),
                }
                await manager.send_to_user(str(target_user_id), ws_payload)
            except Exception:
                logger.debug("WS push failed → user %s", target_user_id)

            if activity_type in _NOTIFY_TYPES:
                try:
                    from app.services.notification_service import NotificationService
                    from app.db.postgres.models.notification import NotificationType
                    body = summary or _NOTIF_BODY.get(activity_type, "Nouvelle notification.").format(
                        actor=actor_display,
                    )
                    notif_type_val = activity_type.value
                    try:
                        notif_type = NotificationType(notif_type_val)
                    except ValueError:
                        notif_type = NotificationType.system
                    await NotificationService.create(
                        user_id=target_user_id,
                        notification_type=notif_type,
                        body=body,
                        db=db,
                        actor_id=actor_id,
                        ref_id=ref_id,
                    )
                except Exception:
                    logger.debug("Notification persistante échouée → user %s", target_user_id)

        return activity

    @staticmethod
    async def log_welcome(user_id: uuid.UUID, db: AsyncSession) -> None:
        try:
            from app.services.notification_service import NotificationService
            from app.db.postgres.models.notification import NotificationType
            await NotificationService.create(
                user_id=user_id,
                notification_type=NotificationType.welcome,
                body="Bienvenue sur FoliX ! Découvrez des concerts, événements et reels exclusifs.",
                db=db,
                title="Bienvenue sur FoliX 🎉",
            )
        except Exception:
            logger.debug("Welcome notification failed for user %s", user_id)

    @staticmethod
    async def get_feed(
        user_id: uuid.UUID, db: AsyncSession,
        page: int = 1, limit: int = 30,
    ) -> list[Activity]:
        """
        Fil d'activité :
        - Activités publiques des gens que je suis (respecte leur privacy_show_activity)
        - Activités qui me ciblent directement
        """
        offset = (page - 1) * limit
        following_ids = select(Follow.following_id).where(Follow.follower_id == user_id)

        # Sous-requête : IDs des gens que je suis ET qui ont privacy_show_activity = true
        visible_actors = (
            select(User.id)
            .where(
                User.id.in_(following_ids),
                User.privacy_show_activity.is_(True),
            )
        )

        result = await db.execute(
            select(Activity)
            .where(
                or_(
                    # Activités publiques des gens que je suis, seulement si show_activity activé
                    and_(
                        Activity.actor_id.in_(visible_actors),
                        Activity.target_user_id.is_(None),
                    ),
                    # Activités me ciblant directement (toujours visibles)
                    Activity.target_user_id == user_id,
                )
            )
            .order_by(Activity.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()
