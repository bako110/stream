from fastapi import APIRouter, Depends, status, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import get_current_user
from app.db.postgres.models.user import User
from app.schemas.user import (
    UserRegister, UserResponse, LoginRequest, Token,
    TokenRefresh, PasswordChange, OAuthLoginRequest, LoginResponse,
    QRGenerateResponse, QRVerifyRequest, QRStatusResponse, QRLoginResponse,
)
from app.services.auth_service import AuthService
from app.services.oauth_service import OAuthService
from app.services.qr_auth_service import QRAuthService

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


# ── Inscription ───────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(request: Request, payload: UserRegister, db: AsyncSession = Depends(get_db)):
    """
    Inscription classique.
    - Champs obligatoires : first_name, last_name, email, password
    - username optionnel (auto-généré prénom+nom si absent)
    - Limité à 10 inscriptions/minute par IP
    """
    user = await AuthService.register(payload, db)
    try:
        from app.services.activity_service import ActivityService
        from app.tasks.notification_tasks import send_welcome_email
        await ActivityService.log_welcome(user.id, db)
        send_welcome_email.delay(user.email, user.display_name or user.username)
    except Exception:
        pass
    return user


# ── Connexion ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(request: Request, payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Connexion avec email OU username + mot de passe.
    - identifier : adresse email ou username
    - Retourne tokens + user (évite un appel /me supplémentaire)
    - Limité à 5 tentatives/minute par IP (anti brute-force)
    """
    return LoginResponse(**await AuthService.login(payload, db))


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


# ── QR Code Auth ──────────────────────────────────────────────────────────────

@router.post("/qr/generate", response_model=QRGenerateResponse)
async def qr_generate(current_user: User = Depends(get_current_user)):
    """
    Génère un token QR temporaire (120s, usage unique).
    Nécessite d'être connecté — le QR encode l'identité de l'utilisateur.
    """
    return await QRAuthService.generate(current_user)


@router.post("/qr/verify", response_model=QRLoginResponse)
async def qr_verify(payload: QRVerifyRequest, db: AsyncSession = Depends(get_db)):
    """
    Échange un token QR valide contre des JWT d'accès.
    Le token est invalidé immédiatement après usage (usage unique).
    """
    return await QRAuthService.verify(payload.token, db)


@router.get("/qr/status/{token}", response_model=QRStatusResponse)
async def qr_status(token: str):
    """
    Polling : retourne l'état du token QR.
    - pending  : en attente de scan
    - scanned  : scanné, tokens émis sur l'autre appareil
    - expired  : expiré ou inexistant
    """
    return await QRAuthService.status(token)
