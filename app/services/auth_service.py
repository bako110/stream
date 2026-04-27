from datetime import datetime
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from fastapi import HTTPException

from app.db.postgres.models.user import User
from app.schemas.user import UserRegister, LoginRequest, UserResponse
from app.utils.password import hash_password, verify_password
from app.utils.jwt import create_access_token, create_refresh_token, decode_refresh_token


def _is_email(value: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value))


def _is_phone(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    return len(digits) >= 8


def _normalize_phone(value: str) -> str:
    return re.sub(r"\D", "", value)


def _generate_username(base_hint: str, first_name: str, last_name: str) -> str:
    """Génère un username depuis prénom+nom."""
    base = f"{first_name.lower()}{last_name.lower()}"
    base = re.sub(r"[^a-z0-9]", "", base)
    if not base:
        base = re.sub(r"[^a-z0-9]", "", base_hint.lower())[:15]
    return base[:30] if base else "user"


class AuthService:

    @staticmethod
    async def register(payload: UserRegister, db: AsyncSession) -> User:
        # ── Vérif unicité email / phone ────────────────────────────────────────
        if payload.email:
            if (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Email déjà utilisé")

        phone_normalized: str | None = None
        if payload.phone:
            phone_normalized = _normalize_phone(payload.phone)
            if (await db.execute(select(User).where(User.phone == phone_normalized))).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Numéro de téléphone déjà utilisé")

        # ── Email interne si inscription par phone uniquement ──────────────────
        email = payload.email
        if not email:
            email = f"phone_{phone_normalized}@folix.internal"

        # ── Résolution username ────────────────────────────────────────────────
        username = payload.username
        if username:
            if (await db.execute(select(User).where(User.username == username))).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Username déjà utilisé")
        else:
            hint = payload.email or phone_normalized or "user"
            base = _generate_username(hint, payload.first_name, payload.last_name)
            username = base
            counter = 1
            while (await db.execute(select(User).where(User.username == username))).scalar_one_or_none():
                username = f"{base}{counter}"
                counter += 1

        display_name = f"{payload.first_name.strip()} {payload.last_name.strip()}"

        user = User(
            email=email,
            phone=phone_normalized,
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

        # Chercher par email, username ou téléphone
        if _is_email(identifier):
            result = await db.execute(select(User).where(User.email == identifier))
        elif _is_phone(identifier):
            phone_normalized = _normalize_phone(identifier)
            result = await db.execute(select(User).where(User.phone == phone_normalized))
        else:
            result = await db.execute(select(User).where(User.username == identifier))

        user = result.scalar_one_or_none()

        if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Identifiant ou mot de passe incorrect")
        if not user.is_active:
            detail = "Ce compte a été supprimé" if getattr(user, 'is_deleted', False) else "Compte désactivé"
            raise HTTPException(status_code=403, detail=detail)

        user.last_login_at = datetime.utcnow()
        await db.commit()

        _role = user.role.value if hasattr(user.role, 'value') else user.role
        token_data = {"sub": str(user.id), "role": _role}
        return {
            "access_token": create_access_token(token_data),
            "refresh_token": create_refresh_token(token_data),
            "user": UserResponse.model_validate(user),
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

        _role = user.role.value if hasattr(user.role, 'value') else user.role
        token_data = {"sub": str(user.id), "role": _role}
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
