import uuid
import enum
from datetime import datetime
from sqlalchemy import Enum as SAEnum, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres.session import Base


class ReactionType(str, enum.Enum):
    like = "like"
    dislike = "dislike"


class Reaction(Base):
    """Like / Dislike polymorphique — reel, contenu, concert ou événement."""
    __tablename__ = "reactions"
    __table_args__ = (
        # Un seul like/dislike par (user, cible)
        UniqueConstraint("user_id", "reel_id",    name="uq_reaction_user_reel"),
        UniqueConstraint("user_id", "content_id", name="uq_reaction_user_content"),
        UniqueConstraint("user_id", "concert_id", name="uq_reaction_user_concert"),
        UniqueConstraint("user_id", "event_id",   name="uq_reaction_user_event"),
        UniqueConstraint("user_id", "comment_id", name="uq_reaction_user_comment"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reaction_type: Mapped[ReactionType] = mapped_column(SAEnum(ReactionType), nullable=False)

    # Cible polymorphique
    reel_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("reels.id", ondelete="CASCADE"), nullable=True)
    content_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contents.id", ondelete="CASCADE"), nullable=True)
    concert_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("concerts.id", ondelete="CASCADE"), nullable=True)
    event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=True)
    comment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User")
    reel: Mapped["Reel"] = relationship("Reel", foreign_keys=[reel_id], back_populates="reactions")

    def __repr__(self):
        return f"<Reaction {self.reaction_type} user={self.user_id}>"
