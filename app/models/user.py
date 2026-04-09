import uuid
from sqlalchemy import String, Boolean, Enum, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import enum

from app.database import Base


class UserRole(str, enum.Enum):
    user = "user"
    artist = "artist"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.user, nullable=False
    )
    artist_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    oauth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    oauth_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"