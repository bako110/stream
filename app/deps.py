import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.postgres.session import get_db
from app.db.postgres.models.user import User
from app.utils.jwt import decode_access_token
from app.utils.cache import cache_get, cache_set

bearer_scheme = HTTPBearer()

_USER_CACHE_TTL = 300  # 5 minutes


def _user_to_cache(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "display_name": user.display_name,
        "role": user.role.value if user.role else None,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "banner_url": user.banner_url,
        "location": user.location,
        "website": user.website,
        "phone": user.phone,
        "date_of_birth": str(user.date_of_birth) if user.date_of_birth else None,
        "gender": user.gender.value if user.gender else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "privacy_profile_public": user.privacy_profile_public,
        "privacy_show_activity": user.privacy_show_activity,
        "privacy_show_location": user.privacy_show_location,
        "privacy_allow_messages": user.privacy_allow_messages,
        "privacy_show_online": user.privacy_show_online,
        "privacy_show_phone": user.privacy_show_phone,
        "privacy_show_birthday": user.privacy_show_birthday,
    }


async def _load_user_from_db(user_id: str, db: AsyncSession) -> User | None:
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    return result.scalar_one_or_none()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

    # Essayer le cache Redis d'abord
    cache_key = f"user:{user_id}"
    cached = await cache_get(cache_key)
    if cached is not None:
        # Reconstruire l'objet User sans toucher la DB
        # Convertir id en UUID pour que les comparaisons fonctionnent
        cached_data = {k: v for k, v in cached.items() if hasattr(User, k)}
        if "id" in cached_data and isinstance(cached_data["id"], str):
            cached_data["id"] = uuid.UUID(cached_data["id"])
        user = User(**cached_data)
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte désactivé")
        return user

    user = await _load_user_from_db(user_id, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte désactivé")

    # Mettre en cache (champs sérialisables uniquement)
    try:
        await cache_set(cache_key, _user_to_cache(user), ttl=_USER_CACHE_TTL)
    except Exception:
        pass  # cache en échec ne doit pas bloquer la requête

    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Retourne l'utilisateur connecté ou None (pas d'erreur 401).

    Priorité cache → DB.  La session DB n'est ouverte que si le token est
    valide ET que l'utilisateur n'est pas en cache.
    """
    if not credentials:
        return None
    payload = decode_access_token(credentials.credentials)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None

    cache_key = f"user:{user_id}"
    cached = await cache_get(cache_key)
    if cached is not None:
        user = User(**{k: v for k, v in cached.items() if hasattr(User, k)})
        return user if user.is_active else None

    user = await _load_user_from_db(user_id, db)
    if not user or not user.is_active:
        return None

    # Mise en cache identique à get_current_user
    try:
        await cache_set(cache_key, _user_to_cache(user), ttl=_USER_CACHE_TTL)
    except Exception:
        pass

    return user


def require_role(*roles: str):
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        role_val = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
        if role_val not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès réservé aux rôles : {', '.join(roles)}",
            )
        return current_user
    return checker


get_admin_user = require_role("admin")
get_artist_user = require_role("artist", "admin")
