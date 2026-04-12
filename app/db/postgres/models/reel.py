import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, Enum, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres.session import Base


class ReelStatus(str, enum.Enum):
    processing = "processing"
    published = "published"
    archived = "archived"


class Reel(Base):
    __tablename__ = "reels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Contenu
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)          # légende / description
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True) # URL vidéo finale (après upload)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[ReelStatus] = mapped_column(Enum(ReelStatus), default=ReelStatus.processing)

    # Référence optionnelle à un contenu ou concert
    ref_content_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contents.id", ondelete="SET NULL"), nullable=True)
    ref_concert_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("concerts.id", ondelete="SET NULL"), nullable=True)
    ref_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL"), nullable=True)

    # Statistiques
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    dislike_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    share_count: Mapped[int] = mapped_column(Integer, default=0)

    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    author: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    comments: Mapped[list] = relationship("Comment", foreign_keys="Comment.reel_id", back_populates="reel", cascade="all, delete-orphan")
    reactions: Mapped[list] = relationship("Reaction", foreign_keys="Reaction.reel_id", back_populates="reel", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Reel user={self.user_id} [{self.status}]>"
