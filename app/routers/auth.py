from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.database import get_db 
from app.models.user import User, UserRole  
from app.schemas.user import (
    UserCreate, UserResponse, LoginRequest,
    Token, TokenRefresh, PasswordChange,
)
from app.utils.password import hash_password, verify_password
from app.utils.jwt import create_access_token, create_refresh_token, decode_refresh_token
from app.deps import get_current_user

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    # Vérifier unicité email
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    # Vérifier unicité username
    result = await db.execute(select(User).where(User.username == payload.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username déjà utilisé")

    user = User(
        email=payload.email,
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        artist_name=payload.artist_name,
        bio=payload.bio,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")

    # Mettre à jour last_login_at
    user.last_login_at = datetime.utcnow()
    await db.commit()

    token_data = {"sub": str(user.id), "role": user.role.value}
    return Token(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(payload: TokenRefresh, db: AsyncSession = Depends(get_db)):
    decoded = decode_refresh_token(payload.refresh_token)
    if not decoded:
        raise HTTPException(status_code=401, detail="Refresh token invalide ou expiré")

    user_id = decoded.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable ou inactif")

    token_data = {"sub": str(user.id), "role": user.role.value}
    return Token(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")

    current_user.password_hash = hash_password(payload.new_password)
    await db.commit()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: User = Depends(get_current_user)):
    # Avec JWT stateless, le logout côté serveur est géré par le client
    # (suppression du token en mémoire + cookie HttpOnly)
    # Pour une blacklist Redis, ajouter ici : redis.setex(token, ttl, "blacklisted")
    pass