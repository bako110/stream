"""
Utilitaire Redis pour le cache applicatif.

Utilise un ConnectionPool partagé par worker :
- Reconnexion automatique si Redis redémarre (health_check_interval)
- Pool de 10 connexions max par worker (--workers 2 = 20 connexions total)
- Graceful degradation : si Redis tombe, le cache est désactivé sans crash
- reset_on_error : invalide les connexions mortes au lieu de les recycler

Usage :
    from app.utils.cache import cache_get, cache_set, cache_delete, cache_invalidate_prefix
"""
import json
import logging
import time
from typing import Any, Optional

import redis.asyncio as aioredis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import BusyLoadingError, ConnectionError, TimeoutError

from app.config import settings

logger = logging.getLogger(__name__)

# ── Pool de connexions Redis par worker ───────────────────────────────────────

_pool: Optional[aioredis.ConnectionPool] = None
_pool_failed_at: float = 0.0
_RETRY_COOLDOWN = 30.0  # secondes avant de retenter si le pool a échoué


def _is_localhost() -> bool:
    url = settings.REDIS_URL or ""
    return "localhost" in url or "127.0.0.1" in url


def _build_pool() -> Optional[aioredis.ConnectionPool]:
    if _is_localhost():
        logger.info("Redis localhost ignoré (non disponible en prod)")
        return None
    try:
        retry = Retry(ExponentialBackoff(cap=2, base=0.1), retries=3)
        pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=10,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry=retry,
            retry_on_error=[BusyLoadingError, ConnectionError, TimeoutError],
            health_check_interval=30,  # ping toutes les 30s — détecte Redis mort/revenu
        )
        return pool
    except Exception as e:
        logger.warning("Redis pool init échoué : %s", e)
        return None


async def get_redis() -> Optional[aioredis.Redis]:
    """
    Retourne un client Redis depuis le pool partagé.
    - Si le pool n'existe pas, tente de le créer (avec cooldown 30s si échec).
    - Si Redis est mort puis revient, health_check_interval détecte la reconnexion.
    - Retourne None si Redis est indisponible (mode dégradé sans cache).
    """
    global _pool, _pool_failed_at

    if _is_localhost():
        return None

    # Recrée le pool si absent et cooldown écoulé
    if _pool is None:
        now = time.monotonic()
        if now - _pool_failed_at < _RETRY_COOLDOWN:
            return None  # Encore en cooldown, on ne spamme pas Redis
        _pool = _build_pool()
        if _pool is None:
            _pool_failed_at = now
            return None

    try:
        client = aioredis.Redis(connection_pool=_pool)
        await client.ping()
        return client
    except Exception as e:
        logger.warning("Redis indisponible : %s", e)
        # Invalide le pool — sera recréé au prochain appel après cooldown
        try:
            await _pool.disconnect(inuse_connections=True)
        except Exception:
            pass
        _pool = None
        _pool_failed_at = time.monotonic()
        return None


async def close_redis() -> None:
    """Ferme proprement le pool au shutdown de l'app."""
    global _pool
    if _pool is not None:
        try:
            await _pool.disconnect()
        except Exception:
            pass
        _pool = None


# ── API publique ──────────────────────────────────────────────────────────────

async def cache_get(key: str) -> Optional[Any]:
    """Récupère une valeur depuis Redis. Retourne None si absent ou erreur."""
    r = await get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        return json.loads(raw) if raw is not None else None
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
        # SCAN itératif plutôt que KEYS — non-bloquant sur gros datasets
        cursor = 0
        to_delete: list[str] = []
        while True:
            cursor, keys = await r.scan(cursor, match=f"{prefix}*", count=100)
            to_delete.extend(keys)
            if cursor == 0:
                break
        if to_delete:
            await r.delete(*to_delete)
    except Exception as e:
        logger.warning("cache_invalidate_prefix(%s) erreur : %s", prefix, e)
