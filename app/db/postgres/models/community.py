import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Text, Enum, DateTime, ForeignKey, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres.session import Base


class CommunityRole(str, enum.Enum):
    member = "member"
    moderator = "moderator"
    admin = "admin"


class Community(Base):
    __tablename__ = "communities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    creator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    creator = relationship("User", foreign_keys=[creator_id], lazy="selectin")

    members_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=datetime.utcnow, nullable=True)


class CommunityMember(Base):
    __tablename__ = "community_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    community_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[CommunityRole] = mapped_column(Enum(CommunityRole, name="communityrole"), default=CommunityRole.member)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    community = relationship("Community", foreign_keys=[community_id], lazy="selectin")
    user = relationship("User", foreign_keys=[user_id], lazy="selectin")


class CommunityBlockedMember(Base):
    __tablename__ = "community_blocked_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    community_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    blocked_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    blocked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    community = relationship("Community", foreign_keys=[community_id], lazy="selectin")
    user = relationship("User", foreign_keys=[user_id], lazy="selectin")


class CommunityMessage(Base):
    __tablename__ = "community_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    community_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False)
    sender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    community = relationship("Community", foreign_keys=[community_id], lazy="selectin")
    sender = relationship("User", foreign_keys=[sender_id], lazy="selectin")
