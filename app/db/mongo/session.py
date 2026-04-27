"""
Connexion MongoDB via Motor async.
Expose : get_mongo(), init_indexes(), check_connection(), close()
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import AsyncGenerator

from app.config import settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            maxPoolSize=50,
            minPoolSize=10,
            maxIdleTimeMS=30000,
            connectTimeoutMS=10000,
            socketTimeoutMS=30000,
            serverSelectionTimeoutMS=10000,
            retryWrites=True,
            w="majority",
        )
    return _client


def get_db() -> AsyncIOMotorDatabase:
    global _db
    if _db is None:
        _db = get_client()[settings.MONGODB_DB_NAME]
    return _db


async def get_mongo() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """Dependency FastAPI — injecte la db Mongo dans les routes/services."""
    yield get_db()


async def init_indexes() -> None:
    """Crée tous les index MongoDB au démarrage de l'application."""
    db = get_db()

    # ── videos ──────────────────────────────────────────────────────────────
    # Recherche par contenu parent (film/série) ou épisode
    await db["videos"].create_index("content_id")
    await db["videos"].create_index("episode_id")
    await db["videos"].create_index("transcode_status")
    # Index pour récupérer la vidéo par défaut d'un contenu rapidement
    await db["videos"].create_index([("content_id", 1), ("is_default", 1)])
    await db["videos"].create_index([("episode_id", 1), ("sort_order", 1)])

    # ── watch_history ────────────────────────────────────────────────────────
    # Index unique : un seul document de progression par (user, video)
    await db["watch_history"].create_index(
        [("user_id", 1), ("video_id", 1)], unique=True
    )
    # Historique récent d'un utilisateur (page "continuer à regarder")
    await db["watch_history"].create_index(
        [("user_id", 1), ("last_watched_at", -1)]
    )
    # TTL : suppression automatique des entrées après 90 jours d'inactivité
    await db["watch_history"].create_index(
        "last_watched_at",
        expireAfterSeconds=7_776_000,  # 90 jours
        name="ttl_watch_history_90d",
    )

    # ── content_meta ─────────────────────────────────────────────────────────
    # Un seul document de métadonnées enrichies par contenu PostgreSQL
    await db["content_meta"].create_index("content_id", unique=True)
    # Recherche full-text sur titre + synopsis
    await db["content_meta"].create_index(
        [("title", "text"), ("synopsis", "text")]
    )

    # ── concert_streams ───────────────────────────────────────────────────────
    # Un seul document de stream par concert PostgreSQL
    await db["concert_streams"].create_index("concert_id", unique=True)

    # ── messages (DM) ─────────────────────────────────────────────────────────
    # Recherche d'une conversation entre deux utilisateurs
    await db["messages"].create_index([("sender_id", 1),   ("receiver_id", 1), ("created_at", -1)])
    await db["messages"].create_index([("receiver_id", 1), ("sender_id", 1),   ("created_at", -1)])
    # Messages non lus reçus par un utilisateur
    await db["messages"].create_index([("receiver_id", 1), ("read", 1)])


async def check_connection() -> bool:
    try:
        await get_client().admin.command("ping")
        return True
    except Exception:
        return False


async def close() -> None:
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
