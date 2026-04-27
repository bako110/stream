import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, Enum, ForeignKey, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres.session import Base


class StoryMediaType(str, enum.Enum):
    image = "image"
    video = "video"
    text = "text"
    audio = "audio"
    voice = "voice"


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    media_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    media_type: Mapped[StoryMediaType] = mapped_column(Enum(StoryMediaType), default=StoryMediaType.image)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_sec: Mapped[int] = mapped_column(Integer, default=5)  # durée d'affichage
    background_color: Mapped[str | None] = mapped_column(String(50), nullable=True)  # couleur fond story texte
    audio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # musique/audio associé
    font_style: Mapped[str | None] = mapped_column(String(50), nullable=True)  # police pour stories texte

    view_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Expiration automatique après 24h (comme WhatsApp)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    author: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    views: Mapped[list["StoryView"]] = relationship("StoryView", back_populates="story", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_stories_user_id", "user_id"),
        Index("ix_stories_expires_at", "expires_at"),
        Index("ix_stories_user_active", "user_id", "is_active"),
    )

    def __repr__(self):
        return f"<Story user={self.user_id} expires={self.expires_at}>"


class StoryView(Base):
    __tablename__ = "story_views"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    viewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    story: Mapped["Story"] = relationship("Story", back_populates="views")
    viewer: Mapped["User"] = relationship("User", foreign_keys=[viewer_id])

    __table_args__ = (
        Index("ix_story_views_story_id", "story_id"),
        Index("ix_story_views_viewer_story", "viewer_id", "story_id", unique=True),
    )
