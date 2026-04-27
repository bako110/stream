import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Enum, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres.session import Base


class ActivityType(str, enum.Enum):
    follow = "follow"                      # X t'a suivi
    event_created = "event_created"        # X a créé un événement
    concert_created = "concert_created"    # X a créé un concert
    event_going = "event_going"            # X va à un événement (billet acheté)
    concert_going = "concert_going"        # X va à un concert (billet acheté)
    community_joined = "community_joined"  # X a rejoint une communauté
    reel_posted = "reel_posted"            # X a posté un reel
    comment = "comment"                    # X a commenté ton contenu
    reaction = "reaction"                  # X a réagi à ton contenu
    profile_view = "profile_view"          # X a visité ton profil
    story_view = "story_view"              # X a vu ta story
    mention = "mention"                    # X t'a mentionné
    welcome = "welcome"                    # Bienvenue sur la plateforme
    subscription = "subscription"          # X s'est abonné à ton compte


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # L'utilisateur qui a fait l'action
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )

    # L'utilisateur concerné (qui verra cette activité dans son feed)
    # NULL = activité publique visible par les followers de l'acteur
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True,
    )

    activity_type: Mapped[ActivityType] = mapped_column(Enum(ActivityType, name="activitytype"), nullable=False)

    # Référence vers l'objet concerné (event_id, concert_id, community_id, reel_id...)
    ref_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Texte résumé (ex: "va au concert Afro Nation", "a rejoint la communauté Hip-Hop")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    actor = relationship("User", foreign_keys=[actor_id], lazy="selectin")

    __table_args__ = (
        Index("ix_activities_actor_id", "actor_id"),
        Index("ix_activities_target_user_id", "target_user_id"),
        Index("ix_activities_type", "activity_type"),
        Index("ix_activities_created_at", "created_at"),
    )
