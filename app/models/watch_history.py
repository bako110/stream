import uuid
from sqlalchemy import Integer, Boolean, ForeignKey, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from app.database import Base


class WatchHistory(Base):
    __tablename__ = "watch_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    # Référence optionnelle au contenu parent pour faciliter les requêtes
    content_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contents.id", ondelete="SET NULL"), nullable=True
    )
    concert_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concerts.id", ondelete="SET NULL"), nullable=True
    )

    # Progression
    watched_seconds: Mapped[int] = mapped_column(Integer, default=0)
    total_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Qualité choisie par l'utilisateur
    quality_watched: Mapped[str | None] = mapped_column(String(10), nullable=True)  # "480p", "720p"...

    # Dernier timestamp de lecture (pour reprendre)
    last_position_sec: Mapped[int] = mapped_column(Integer, default=0)

    last_watched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relations
    user: Mapped["User"] = relationship("User")
    video: Mapped["Video"] = relationship("Video")

    def __repr__(self):
        return f"<WatchHistory user={self.user_id} video={self.video_id} {self.watched_seconds}s>"