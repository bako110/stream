import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres.session import Base


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contents.id", ondelete="CASCADE"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    total_episodes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    content: Mapped["Content"] = relationship("Content", back_populates="seasons")
    episodes: Mapped[list] = relationship("Episode", back_populates="season", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_seasons_content_id", "content_id"),
        Index("ix_seasons_number", "number"),
        Index("ix_seasons_created_at", "created_at"),
        Index("ix_seasons_content_number", "content_id", "number"),
    )

    def __repr__(self):
        return f"<Season S{self.number} content={self.content_id}>"
