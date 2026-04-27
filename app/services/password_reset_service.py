"""
Service de réinitialisation de mot de passe par OTP 6 chiffres.

Flux :
1. POST /auth/forgot-password  { email | phone | username }
   → cherche l'utilisateur, génère un OTP 6 chiffres (TTL 15 min)
   → stocke le hash SHA256 de l'OTP en DB
   → envoie l'OTP par email Gmail

2. POST /auth/reset-password  { token (OTP), new_password }
   → vérifie l'OTP, met à jour le mot de passe, invalide l'OTP
"""
import re
import random
import hashlib
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.postgres.models.user import User
from app.utils.password import hash_password
from app.schemas.user import ForgotPasswordRequest

RESET_TTL_MINUTES = 15


def _normalize_phone(v: str) -> str:
    return re.sub(r"\D", "", v)


def _generate_otp() -> str:
    return f"{random.SystemRandom().randint(0, 999999):06d}"


def _hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()


def _detect_method(payload: ForgotPasswordRequest) -> str:
    if payload.email:    return "email"
    if payload.phone:    return "phone"
    if payload.username: return "username"
    return "unknown"


class PasswordResetService:

    @staticmethod
    async def request_reset(payload: ForgotPasswordRequest, db: AsyncSession) -> dict:
        user: User | None = None

        if payload.email:
            result = await db.execute(select(User).where(User.email == payload.email.strip().lower()))
            user = result.scalar_one_or_none()
        elif payload.phone:
            phone_norm = _normalize_phone(payload.phone)
            result = await db.execute(select(User).where(User.phone == phone_norm))
            user = result.scalar_one_or_none()
        elif payload.username:
            result = await db.execute(select(User).where(User.username == payload.username.strip()))
            user = result.scalar_one_or_none()

        # Réponse identique même si compte inexistant (anti-enumération)
        if not user or not user.is_active:
            return {"sent": True, "method": _detect_method(payload)}

        otp = _generate_otp()
        user.reset_token = _hash_otp(otp)
        user.reset_token_expires = datetime.utcnow() + timedelta(minutes=RESET_TTL_MINUTES)
        await db.commit()

        # Envoi email (si email réel disponible)
        if user.email and not user.email.endswith("@folix.internal"):
            display_name = user.display_name or user.username or "utilisateur"
            try:
                from app.tasks.notification_tasks import send_password_reset_email
                send_password_reset_email.delay(
                    user.email,
                    otp,
                    display_name,
                    RESET_TTL_MINUTES,
                )
            except Exception:
                # Si Celery indispo, envoyer synchrone
                try:
                    from app.tasks.notification_tasks import _send_smtp, _tpl_password_reset
                    _send_smtp(
                        to_email=user.email,
                        subject="Votre code FoliX",
                        html=_tpl_password_reset(otp, display_name, RESET_TTL_MINUTES),
                    )
                except Exception:
                    pass

        return {"sent": True, "method": _detect_method(payload)}

    @staticmethod
    async def reset_password(otp: str, new_password: str, db: AsyncSession) -> None:
        otp_hash = _hash_otp(otp.strip())

        result = await db.execute(select(User).where(User.reset_token == otp_hash))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=400, detail="Code invalide ou expiré")

        if not user.reset_token_expires or datetime.utcnow() > user.reset_token_expires:
            user.reset_token = None
            user.reset_token_expires = None
            await db.commit()
            raise HTTPException(status_code=400, detail="Code expiré — veuillez refaire la demande")

        user.password_hash = hash_password(new_password)
        user.reset_token = None
        user.reset_token_expires = None
        await db.commit()
