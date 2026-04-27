"""
Utilitaire Redis pour le cache applicatif.

Usage :
    from app.utils.cache import cache_get, cache_set, cache_delete, cache_invalidate_prefix

    # Dans un service :
    cached = await cache_get("concerts:live")
    if cached is not None:
        return cached
    data = await db.execute(...)
    await cache_set("concerts:live", data, ttl=30)
    return data
"""
import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

# ── Singleton pool Redis ──────────────────────────────────────────────────────

_redis: Optional[aioredis.Redis] = None


async def get_redis() -> Optional[aioredis.Redis]:
    """Retourne le client Redis, ou None si Redis est indisponible."""
    global _redis
    if _redis is None:
        # Skip immédiat si Redis pointe vers localhost (inexistant sur Fly)
        if "localhost" in settings.REDIS_URL or "127.0.0.1" in settings.REDIS_URL:
            logger.info("Redis localhost ignoré (probablement indisponible)")
            return None
        try:
            _redis = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=False,
            )
            await _redis.ping()
        except Exception as e:
            logger.warning("Redis indisponible, cache désactivé : %s", e)
            _redis = None
    return _redis


async def cache_get(key: str) -> Optional[Any]:
    """Récupère une valeur depuis Redis. Retourne None si absent ou erreur."""
    r = await get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.warning("cache_get(%s) erreur : %s", key, e)
        return None


async def cache_set(key: str, value: Any, ttl: int = 60) -> None:
    """Stocke une valeur dans Redis avec un TTL en secondes."""
    r = await get_redis()
    if r is None:
        return
    try:
        await r.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception as e:
        logger.warning("cache_set(%s) erreur : %s", key, e)


async def cache_delete(*keys: str) -> None:
    """Supprime une ou plusieurs clés."""
    r = await get_redis()
    if r is None:
        return
    try:
        await r.delete(*keys)
    except Exception as e:
        logger.warning("cache_delete erreur : %s", e)


async def cache_invalidate_prefix(prefix: str) -> None:
    """Supprime toutes les clés dont le nom commence par `prefix`."""
    r = await get_redis()
    if r is None:
        return
    try:
        keys = await r.keys(f"{prefix}*")
        if keys:
            await r.delete(*keys)
    except Exception as e:
        logger.warning("cache_invalidate_prefix(%s) erreur : %s", prefix, e)
