import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, Enum, ForeignKey, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres.session import Base


class TargetType(str, enum.Enum):
    reel = "reel"
    content = "content"
    concert = "concert"
    event = "event"


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Cible polymorphique — un seul de ces champs est rempli
    reel_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("reels.id", ondelete="CASCADE"), nullable=True)
    content_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contents.id", ondelete="CASCADE"), nullable=True)
    concert_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("concerts.id", ondelete="CASCADE"), nullable=True)
    event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=True)

    # Réponse à un commentaire parent
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)

    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    dislike_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    author: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    reel: Mapped["Reel"] = relationship("Reel", foreign_keys=[reel_id], back_populates="comments")
    replies: Mapped[list] = relationship("Comment", foreign_keys=[parent_id])

    __table_args__ = (
        Index("ix_comments_user_id", "user_id"),
        Index("ix_comments_reel_id", "reel_id"),
        Index("ix_comments_content_id", "content_id"),
        Index("ix_comments_event_id", "event_id"),
        Index("ix_comments_concert_id", "concert_id"),
        Index("ix_comments_parent_id", "parent_id"),
        Index("ix_comments_created_at", "created_at"),
        Index("ix_comments_parent_created", "parent_id", "created_at"),
    )

    def __repr__(self):
        return f"<Comment user={self.user_id} reel={self.reel_id}>"
