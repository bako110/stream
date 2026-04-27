import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Enum as SAEnum, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres.session import Base


class SharePlatform(str, enum.Enum):
    internal = "internal"   # partage dans l'appli (story, message)
    external = "external"   # lien copié / réseau social
    whatsapp = "whatsapp"
    instagram = "instagram"
    tiktok = "tiktok"
    twitter = "twitter"
    facebook = "facebook"


class Share(Base):
    __tablename__ = "shares"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[SharePlatform] = mapped_column(SAEnum(SharePlatform), default=SharePlatform.external)

    # Cible polymorphique
    reel_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("reels.id", ondelete="CASCADE"), nullable=True)
    content_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contents.id", ondelete="CASCADE"), nullable=True)
    concert_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("concerts.id", ondelete="CASCADE"), nullable=True)
    event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("ix_shares_user_id", "user_id"),
        Index("ix_shares_platform", "platform"),
        Index("ix_shares_reel_id", "reel_id"),
        Index("ix_shares_content_id", "content_id"),
        Index("ix_shares_concert_id", "concert_id"),
        Index("ix_shares_event_id", "event_id"),
        Index("ix_shares_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<Share {self.platform} user={self.user_id}>"
