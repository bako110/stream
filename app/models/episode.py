import uuid
from sqlalchemy import String, Integer, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from app.database import Base


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_free: Mapped[bool] = mapped_column(Boolean, default=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relations
    season: Mapped["Season"] = relationship("Season", back_populates="episodes")
    videos: Mapped[list] = relationship(
        "Video", back_populates="episode", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Episode E{self.number} - {self.title}>"
