from datetime import datetime
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from fastapi import HTTPException

from app.db.postgres.models.user import User
from app.schemas.user import UserRegister, LoginRequest
from app.utils.password import hash_password, verify_password
from app.utils.jwt import create_access_token, create_refresh_token, decode_refresh_token


def _is_email(value: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value))


def _generate_username(email: str, first_name: str, last_name: str) -> str:
    """Génère un username depuis prénom+nom en snake_case."""
    base = f"{first_name.lower()}{last_name.lower()}"
    # garder uniquement alphanum + underscore
    base = re.sub(r"[^a-z0-9]", "", base)
    if not base:
        base = email.split("@")[0]
    return base[:30]


class AuthService:

    @staticmethod
    async def register(payload: UserRegister, db: AsyncSession) -> User:
        # Vérif email unique
        if (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email déjà utilisé")

        # Résolution du username
        username = payload.username
        if username:
            # Vérif unicité si fourni
            if (await db.execute(select(User).where(User.username == username))).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Username déjà utilisé")
        else:
            # Auto-génération depuis prénom+nom
            base = _generate_username(payload.email, payload.first_name, payload.last_name)
            username = base
            # Rendre unique si collision
            counter = 1
            while (await db.execute(select(User).where(User.username == username))).scalar_one_or_none():
                username = f"{base}{counter}"
                counter += 1

        # display_name = "Prénom Nom"
        display_name = f"{payload.first_name.strip()} {payload.last_name.strip()}"

        user = User(
            email=payload.email,
            username=username,
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            display_name=display_name,
            password_hash=hash_password(payload.password),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def login(payload: LoginRequest, db: AsyncSession) -> dict:
        identifier = payload.identifier.strip()

        # Chercher par email OU par username
        if _is_email(identifier):
            result = await db.execute(select(User).where(User.email == identifier))
        else:
            result = await db.execute(select(User).where(User.username == identifier))

        user = result.scalar_one_or_none()

        if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Identifiant ou mot de passe incorrect")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Compte désactivé")

        user.last_login_at = datetime.utcnow()
        await db.commit()

        token_data = {"sub": str(user.id), "role": user.role.value}
        return {
            "access_token": create_access_token(token_data),
            "refresh_token": create_refresh_token(token_data),
        }

    @staticmethod
    async def refresh(refresh_token: str, db: AsyncSession) -> dict:
        decoded = decode_refresh_token(refresh_token)
        if not decoded:
            raise HTTPException(status_code=401, detail="Refresh token invalide ou expiré")
        result = await db.execute(select(User).where(User.id == decoded.get("sub")))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Utilisateur introuvable ou inactif")

        token_data = {"sub": str(user.id), "role": user.role.value}
        return {
            "access_token": create_access_token(token_data),
            "refresh_token": create_refresh_token(token_data),
        }

    @staticmethod
    async def change_password(current_password: str, new_password: str, user: User, db: AsyncSession) -> None:
        if not user.password_hash:
            raise HTTPException(status_code=400, detail="Compte OAuth — pas de mot de passe à changer")
        if not verify_password(current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
        user.password_hash = hash_password(new_password)
        await db.commit()
