import uuid
import enum
from datetime import datetime, date
from sqlalchemy import String, Boolean, Enum, DateTime, Date, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres.session import Base


class UserRole(str, enum.Enum):
    user = "user"
    artist = "artist"
    admin = "admin"


class Gender(str, enum.Enum):
    male = "male"
    female = "female"
    other = "other"
    prefer_not_to_say = "prefer_not_to_say"


class OAuthProvider(str, enum.Enum):
    google = "google"
    facebook = "facebook"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # username optionnel — peut se connecter avec email ou username
    username: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)

    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="userrole"), default=UserRole.user, nullable=False)

    # ── Identité ───────────────────────────────────────────────────────────────
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # ── Profil ─────────────────────────────────────────────────────────────────
    bio: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Informations personnelles ──────────────────────────────────────────────
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(Enum(Gender, name="gender"), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)    # ville, pays
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── OAuth ──────────────────────────────────────────────────────────────────
    oauth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    oauth_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oauth_access_token: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # ── Confidentialité ────────────────────────────────────────────────────────
    privacy_profile_public:  Mapped[bool] = mapped_column(Boolean, default=True)
    privacy_show_activity:   Mapped[bool] = mapped_column(Boolean, default=True)
    privacy_show_location:   Mapped[bool] = mapped_column(Boolean, default=True)
    privacy_allow_messages:  Mapped[bool] = mapped_column(Boolean, default=True)
    privacy_show_online:     Mapped[bool] = mapped_column(Boolean, default=True)
    privacy_show_phone:      Mapped[bool] = mapped_column(Boolean, default=False)
    privacy_show_birthday:   Mapped[bool] = mapped_column(Boolean, default=True)

    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_username", "username"),
        Index("ix_users_role", "role"),
        Index("ix_users_is_active", "is_active"),
        Index("ix_users_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
