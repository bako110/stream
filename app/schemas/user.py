from pydantic import BaseModel, EmailStr, UUID4, field_validator
from typing import Optional
from datetime import datetime
from app.models.user import UserRole


# ─── Création ────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    role: UserRole = UserRole.user
    artist_name: Optional[str] = None
    bio: Optional[str] = None

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v):
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Le username ne peut contenir que des lettres, chiffres, _ et -")
        if len(v) < 3:
            raise ValueError("Le username doit faire au moins 3 caractères")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Le mot de passe doit faire au moins 8 caractères")
        return v


class UserUpdate(BaseModel):
    username: Optional[str] = None
    bio: Optional[str] = None
    artist_name: Optional[str] = None
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None


# ─── Réponses ────────────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: UUID4
    email: EmailStr
    username: str
    role: UserRole
    artist_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None
    is_verified: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserPublic(BaseModel):
    """Version publique sans email (pour les profils artistes)"""
    id: UUID4
    username: str
    role: UserRole
    artist_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None

    model_config = {"from_attributes": True}


# ─── Auth ─────────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Le mot de passe doit faire au moins 8 caractères")
        return v
