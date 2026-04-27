import re
from pydantic import BaseModel, EmailStr, UUID4, field_validator, model_validator
from typing import Optional
from datetime import datetime, date

from app.db.postgres.models.user import UserRole, Gender


# ─── Inscription ──────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    """
    Inscription classique.
    - first_name, last_name, password : obligatoires
    - email OU phone : au moins l'un des deux requis
    - username : optionnel (auto-généré si absent)
    """
    first_name: str
    last_name:  str
    email:      Optional[EmailStr] = None
    phone:      Optional[str]      = None
    password:   str
    username:   Optional[str]      = None

    @field_validator("first_name", "last_name")
    @classmethod
    def name_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Doit faire au moins 2 caractères")
        return v

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        digits = re.sub(r"\D", "", v)
        if len(digits) < 8:
            raise ValueError("Numéro de téléphone invalide (8 chiffres minimum)")
        return digits

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

    def model_post_init(self, __context: object) -> None:
        if not self.email and not self.phone:
            raise ValueError("Email ou numéro de téléphone requis")


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
    created_at: Optional[datetime] = None

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


class UserPublicProfile(UserPublic):
    """Profil public enrichi avec compteurs follow."""
    followers_count:  int = 0
    following_count:  int = 0
    is_followed:      bool = False
    is_verified:      bool = False
    phone:            Optional[str] = None
    date_of_birth:    Optional[date] = None
    gender:           Optional[str] = None
    created_at:       Optional[datetime] = None


# ─── Confidentialité ──────────────────────────────────────────────────────────

class PrivacySettings(BaseModel):
    privacy_profile_public:  bool = True
    privacy_show_activity:   bool = True
    privacy_show_location:   bool = True
    privacy_allow_messages:  bool = True
    privacy_show_online:     bool = True
    privacy_show_phone:      bool = False
    privacy_show_birthday:   bool = True

    model_config = {"from_attributes": True}


# ─── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """
    Connexion avec email, username OU numéro de téléphone + mot de passe.
    - identifier : email, username ou numéro de téléphone
    """
    identifier: str      # email, username ou phone
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResponse(Token):
    """Réponse login = tokens + user (évite un appel /me supplémentaire)."""
    user: UserResponse


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


# ─── Forgot / Reset password ─────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    """Au moins un identifiant parmi email, phone, username."""
    email:    Optional[str] = None
    phone:    Optional[str] = None
    username: Optional[str] = None

    def model_post_init(self, __context: object) -> None:
        if not self.email and not self.phone and not self.username:
            raise ValueError("Email, téléphone ou nom d'utilisateur requis")


class ResetPasswordRequest(BaseModel):
    token:        str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Le mot de passe doit faire au moins 8 caractères")
        return v


# ─── QR Auth ──────────────────────────────────────────────────────────────────

class QRGenerateResponse(BaseModel):
    token: str
    expires_at: str
    ttl_seconds: int


class QRVerifyRequest(BaseModel):
    token: str


class QRStatusResponse(BaseModel):
    status: str          # "pending" | "scanned" | "expired"
    ttl_seconds: Optional[int] = None


class QRLoginResponse(Token):
    """Réponse scan QR = tokens + user."""
    user: UserResponse
