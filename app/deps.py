from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.database import get_db
from app.models.user import User, UserRole
from app.utils.jwt import decode_access_token

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte désactivé")

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user


def require_role(*roles: UserRole):
    """Décorateur de rôle : require_role('admin') ou require_role('admin', 'artist')"""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
             detail=f"Accès réservé aux rôles : {', '.join(roles)}",
            )
        return current_user
    return role_checker


# Raccourcis pratiques
get_admin_user = require_role(UserRole.admin)
get_artist_user = require_role(UserRole.artist, UserRole.admin)