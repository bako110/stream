"""
Service de réinitialisation de mot de passe.

Flux :
1. POST /auth/forgot-password  { email | phone | username }
   → cherche l'utilisateur, génère un token sécurisé (TTL 15 min)
   → stocke le hash du token en DB (reset_token, reset_token_expires)
   → envoie le token par email si email connu, sinon retourne le token
     dans la réponse (pour SMS ou username — à brancher sur un vrai
     provider SMS en production)

2. POST /auth/reset-password  { token, new_password }
   → vérifie le token, met à jour le mot de passe, invalide le token
"""
import re
import secrets
import hashlib
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.db.postgres.models.user import User
from app.utils.password import hash_password
from app.schemas.user import ForgotPasswordRequest

RESET_TTL_MINUTES = 15


def _normalize_phone(v: str) -> str:
    return re.sub(r"\D", "", v)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class PasswordResetService:

    @staticmethod
    async def request_reset(payload: ForgotPasswordRequest, db: AsyncSession) -> dict:
        """
        Cherche l'utilisateur et génère un token de reset.
        Retourne toujours la même réponse pour ne pas révéler si le compte existe.
        """
        user: User | None = None

        if payload.email:
            result = await db.execute(
                select(User).where(User.email == payload.email.strip().lower())
            )
            user = result.scalar_one_or_none()

        elif payload.phone:
            phone_norm = _normalize_phone(payload.phone)
            result = await db.execute(
                select(User).where(User.phone == phone_norm)
            )
            user = result.scalar_one_or_none()

        elif payload.username:
            result = await db.execute(
                select(User).where(User.username == payload.username.strip())
            )
            user = result.scalar_one_or_none()

        # Réponse identique qu'on trouve l'utilisateur ou non (sécurité)
        if not user or not user.is_active:
            return {"sent": True, "method": _detect_method(payload)}

        raw_token = secrets.token_urlsafe(48)
        token_hash = _hash_token(raw_token)
        expires = datetime.utcnow() + timedelta(minutes=RESET_TTL_MINUTES)

        user.reset_token = token_hash
        user.reset_token_expires = expires
        await db.commit()

        method = _detect_method(payload)

        # Envoi email si méthode email ou si l'email est disponible
        if method == "email" or (user.email and not user.email.endswith("@folix.internal")):
            try:
                from app.tasks.notification_tasks import send_password_reset_email
                send_password_reset_email.delay(user.email, raw_token, RESET_TTL_MINUTES)
            except Exception:
                pass

        # En production : pour phone → envoyer via SMS provider (Twilio, etc.)
        # Pour username → envoyer à l'email associé (déjà couvert ci-dessus)

        return {"sent": True, "method": method}

    @staticmethod
    async def reset_password(token: str, new_password: str, db: AsyncSession) -> None:
        """Vérifie le token et met à jour le mot de passe."""
        token_hash = _hash_token(token)

        result = await db.execute(
            select(User).where(User.reset_token == token_hash)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=400, detail="Token invalide ou expiré")

        if not user.reset_token_expires or datetime.utcnow() > user.reset_token_expires:
            # Invalider le token expiré
            user.reset_token = None
            user.reset_token_expires = None
            await db.commit()
            raise HTTPException(status_code=400, detail="Token expiré — veuillez refaire la demande")

        user.password_hash = hash_password(new_password)
        user.reset_token = None
        user.reset_token_expires = None
        await db.commit()


def _detect_method(payload: ForgotPasswordRequest) -> str:
    if payload.email:    return "email"
    if payload.phone:    return "phone"
    if payload.username: return "username"
    return "unknown"
