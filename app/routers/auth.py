from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import get_current_user
from app.db.postgres.models.user import User
from app.schemas.user import (
    UserRegister, UserResponse, LoginRequest, Token,
    TokenRefresh, PasswordChange, OAuthLoginRequest,
)
from app.services.auth_service import AuthService
from app.services.oauth_service import OAuthService

router = APIRouter()


# ── Inscription ───────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    """
    Inscription classique.
    - Champs obligatoires : first_name, last_name, email, password
    - username optionnel (auto-généré prénom+nom si absent)
    """
    return await AuthService.register(payload, db)


# ── Connexion ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=Token)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Connexion avec email OU username + mot de passe.
    - identifier : adresse email ou username
    """
    return Token(**await AuthService.login(payload, db))


@router.post("/refresh", response_model=Token)
async def refresh_token(payload: TokenRefresh, db: AsyncSession = Depends(get_db)):
    return Token(**await AuthService.refresh(payload.refresh_token, db))


# ── OAuth Google / Facebook ───────────────────────────────────────────────────

@router.post("/oauth/google", response_model=Token)
async def oauth_google(payload: OAuthLoginRequest, db: AsyncSession = Depends(get_db)):
    """Connexion / inscription via Google (access_token depuis SDK Google)."""
    return Token(**await OAuthService.google_login(payload.access_token, db))


@router.post("/oauth/facebook", response_model=Token)
async def oauth_facebook(payload: OAuthLoginRequest, db: AsyncSession = Depends(get_db)):
    """Connexion / inscription via Facebook (access_token depuis SDK Facebook)."""
    return Token(**await OAuthService.facebook_login(payload.access_token, db))


# ── Profil courant ────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await AuthService.change_password(payload.current_password, payload.new_password, current_user, db)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: User = Depends(get_current_user)):
    pass  # JWT stateless — côté client : supprimer le token
