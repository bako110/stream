from pydantic import BaseModel, EmailStr, UUID4, field_validator, HttpUrl
from typing import Optional
from datetime import datetime, date

from app.db.postgres.models.user import UserRole, Gender


# ─── Inscription ──────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    """
    Inscription classique.
    - first_name, last_name, email, password : obligatoires
    - username : optionnel (auto-généré depuis email si absent)
    """
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    username: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def name_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Doit faire au moins 2 caractères")
        return v

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Le username doit faire au moins 3 caractères")
        if not v.replace("_", "").replace("-", "").replace(".", "").isalnum():
            raise ValueError("Le username ne peut contenir que des lettres, chiffres, _, - et .")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Le mot de passe doit faire au moins 8 caractères")
        return v


# Alias pour compatibilité
UserCreate = UserRegister


# ─── Mise à jour profil ───────────────────────────────────────────────────────

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    location: Optional[str] = None
    website: Optional[str] = None

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Le username doit faire au moins 3 caractères")
        if not v.replace("_", "").replace("-", "").replace(".", "").isalnum():
            raise ValueError("Le username ne peut contenir que des lettres, chiffres, _, - et .")
        return v


# ─── OAuth ────────────────────────────────────────────────────────────────────

class OAuthLoginRequest(BaseModel):
    provider: str
    access_token: str


# ─── Réponses ─────────────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: UUID4
    email: EmailStr
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    role: UserRole
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    location: Optional[str] = None
    website: Optional[str] = None
    is_verified: bool
    is_active: bool
    oauth_provider: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserPublic(BaseModel):
    """Profil public — sans email ni données sensibles."""
    id: UUID4
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    role: UserRole
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None

    model_config = {"from_attributes": True}


# ─── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """
    Connexion avec email OU username + mot de passe.
    - identifier : email ou username
    """
    identifier: str      # email ou username
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Le mot de passe doit faire au moins 8 caractères")
        return v
