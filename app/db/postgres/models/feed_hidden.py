import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres.session import Base


class FeedHidden(Base):
    """Contenu masqué par l'utilisateur ("Pas intéressé")."""
    __tablename__ = "feed_hidden"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ref_id:   Mapped[str] = mapped_column(String(36), nullable=False)
    ref_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "event"|"concert"

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "ref_id", "ref_type", name="uq_feed_hidden_user_ref"),
        Index("ix_feed_hidden_user_id", "user_id"),
    )
