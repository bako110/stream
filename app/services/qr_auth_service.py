"""
Service d'authentification par QR code.

Flux :
1. L'utilisateur connecté appelle POST /auth/qr/generate
   → reçoit un token UUID + expiry (120s)
   → affiche ce token encodé en QR sur son écran

2. Un autre appareil scanne le QR et appelle POST /auth/qr/verify
   → si le token est valide et non utilisé, reçoit access + refresh tokens
   → le token Redis est supprimé immédiatement (usage unique)

3. L'appareil générateur peut poller GET /auth/qr/status/{token}
   → retourne "pending" | "scanned" | "expired"
   → "scanned" signifie que le scan a eu lieu
"""
import uuid
import json
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.postgres.models.user import User
from app.utils.jwt import create_access_token, create_refresh_token
from app.utils.cache import get_redis

QR_TTL = 120  # secondes
_PREFIX_PENDING = "qr:pending:"
_PREFIX_SCANNED = "qr:scanned:"


def _pending_key(token: str) -> str:
    return f"{_PREFIX_PENDING}{token}"


def _scanned_key(token: str) -> str:
    return f"{_PREFIX_SCANNED}{token}"


class QRAuthService:

    @staticmethod
    async def generate(user: User) -> dict:
        """Génère un token QR lié à l'utilisateur connecté."""
        r = await get_redis()
        if r is None:
            raise HTTPException(
                status_code=503,
                detail="Service QR indisponible (Redis requis)",
            )

        token = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(seconds=QR_TTL)

        payload = json.dumps({
            "user_id": str(user.id),
            "role": user.role.value if hasattr(user.role, "value") else user.role,
        })
        await r.set(_pending_key(token), payload, ex=QR_TTL)

        return {
            "token": token,
            "expires_at": expires_at.isoformat() + "Z",
            "ttl_seconds": QR_TTL,
        }

    @staticmethod
    async def verify(token: str, db: AsyncSession) -> dict:
        """Échange un token QR valide contre des JWT. Usage unique."""
        r = await get_redis()
        if r is None:
            raise HTTPException(status_code=503, detail="Service QR indisponible")

        key = _pending_key(token)
        raw = await r.get(key)
        if raw is None:
            raise HTTPException(
                status_code=404,
                detail="QR code invalide ou expiré",
            )

        data = json.loads(raw)
        user_id = data["user_id"]
        role = data["role"]

        # Invalider immédiatement (usage unique)
        await r.delete(key)
        # Marquer comme scanné pour le polling (TTL court, juste pour notification)
        await r.set(_scanned_key(token), "1", ex=30)

        # Vérifier que l'utilisateur est toujours actif
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=403, detail="Compte introuvable ou désactivé")

        token_data = {"sub": str(user.id), "role": role}
        from app.schemas.user import UserResponse
        return {
            "access_token": create_access_token(token_data),
            "refresh_token": create_refresh_token(token_data),
            "token_type": "bearer",
            "user": UserResponse.model_validate(user),
        }

    @staticmethod
    async def status(token: str) -> dict:
        """
        Retourne l'état du token QR pour le polling côté mobile.
        - pending  : en attente de scan
        - scanned  : scanné avec succès (tokens émis)
        - expired  : expiré ou inexistant
        """
        r = await get_redis()
        if r is None:
            return {"status": "expired"}

        if await r.exists(_scanned_key(token)):
            return {"status": "scanned"}
        if await r.exists(_pending_key(token)):
            ttl = await r.ttl(_pending_key(token))
            return {"status": "pending", "ttl_seconds": ttl}
        return {"status": "expired"}
