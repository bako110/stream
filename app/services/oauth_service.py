"""
Service OAuth — Google et Facebook.
Valide le token côté serveur, récupère le profil, crée ou retrouve l'utilisateur.
"""
import re
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.db.postgres.models.user import User, UserRole
from app.utils.jwt import create_access_token, create_refresh_token

GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
FACEBOOK_USERINFO_URL = "https://graph.facebook.com/me?fields=id,name,email,picture"


def _make_username(base: str) -> str:
    """Transforme un nom en username valide."""
    slug = re.sub(r"[^a-zA-Z0-9_\-]", "", base.replace(" ", "_")).lower()
    return slug[:30] or "user"


async def _get_or_create_oauth_user(
    provider: str,
    oauth_id: str,
    email: str,
    display_name: str,
    avatar_url: str | None,
    db: AsyncSession,
) -> User:
    # 1. Chercher par provider + oauth_id (compte déjà lié)
    result = await db.execute(
        select(User).where(User.oauth_provider == provider, User.oauth_id == oauth_id)
    )
    user = result.scalar_one_or_none()
    if user:
        return user

    # 2. Chercher par email (compte classique existant → lier)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        user.oauth_provider = provider
        user.oauth_id = oauth_id
        if not user.avatar_url and avatar_url:
            user.avatar_url = avatar_url
        await db.commit()
        await db.refresh(user)
        return user

    # 3. Créer un nouveau compte
    base = _make_username(display_name)
    username = base
    suffix = 1
    while (await db.execute(select(User).where(User.username == username))).scalar_one_or_none():
        username = f"{base}{suffix}"
        suffix += 1

    user = User(
        email=email,
        username=username,
        display_name=display_name,
        avatar_url=avatar_url,
        oauth_provider=provider,
        oauth_id=oauth_id,
        is_verified=True,  # email déjà vérifié par le provider
        role=UserRole.user,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


class OAuthService:

    @staticmethod
    async def google_login(access_token: str, db: AsyncSession) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Token Google invalide")

        data = resp.json()
        email = data.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email non disponible depuis Google")

        user = await _get_or_create_oauth_user(
            provider="google",
            oauth_id=data["sub"],
            email=email,
            display_name=data.get("name", email.split("@")[0]),
            avatar_url=data.get("picture"),
            db=db,
        )
        return _build_tokens(user)

    @staticmethod
    async def facebook_login(access_token: str, db: AsyncSession) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                FACEBOOK_USERINFO_URL,
                params={"access_token": access_token},
                timeout=10,
            )
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Token Facebook invalide")

        data = resp.json()
        email = data.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email non disponible depuis Facebook (permissions manquantes)")

        avatar = None
        if "picture" in data and isinstance(data["picture"], dict):
            avatar = data["picture"].get("data", {}).get("url")

        user = await _get_or_create_oauth_user(
            provider="facebook",
            oauth_id=data["id"],
            email=email,
            display_name=data.get("name", email.split("@")[0]),
            avatar_url=avatar,
            db=db,
        )
        return _build_tokens(user)


def _build_tokens(user: User) -> dict:
    _role = user.role.value if hasattr(user.role, 'value') else user.role
    payload = {"sub": str(user.id), "role": _role}
    return {
        "access_token": create_access_token(payload),
        "refresh_token": create_refresh_token(payload),
        "token_type": "bearer",
    }
