import uuid
from datetime import datetime
from sqlalchemy import String, Float, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres.session import Base


class UserInterest(Base):
    """Intérêts utilisateur — catégories avec score dynamique mis à jour par les interactions."""
    __tablename__ = "user_interests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_user_interest_category"),
        Index("ix_user_interests_user_id", "user_id"),
        Index("ix_user_interests_category", "category"),
    )

    def __repr__(self):
        return f"<UserInterest user={self.user_id} cat={self.category} score={self.score}>"
