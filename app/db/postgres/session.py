"""
Connexion PostgreSQL — compatible Fly Postgres / PgBouncer.

PgBouncer en mode Transaction ne supporte pas les prepared statements.
La solution : contourner le pooler (port 6543) et se connecter directement
à la base (port 5432). Le backend est un serveur long-running, il gère
son propre pool de connexions via SQLAlchemy — pas besoin du pooler.
"""
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event, text
from typing import AsyncGenerator
import asyncpg
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Supabase PgBouncer (port 6543) ne supporte pas les prepared statements.
# On bascule vers la connexion directe (port 5432) si on détecte le pooler.
_db_url = settings.DATABASE_URL
if ":6543" in _db_url:
    _db_url = _db_url.replace(":6543", ":5432")

_raw_url = _db_url.replace("postgresql+asyncpg://", "postgresql://")

# Désactiver SSL pour les connexions locales (Docker) et Fly internes
_is_local = any(h in _db_url for h in ("localhost", "127.0.0.1", "@postgres:", "@stream_postgres:", ".internal", ".flycast"))
_connect_args: dict = {
    "prepared_statement_cache_size": 0,   # requis si PgBouncer (mode transaction)
}
if _is_local:
    _connect_args["ssl"] = False

engine = create_async_engine(
    _db_url,
    # 2 instances × (3 + 5) = 16 connexions max → sous la limite Fly Postgres (25)
    pool_size=3,
    max_overflow=5,
    pool_timeout=10,
    pool_recycle=240,   # Fly coupe les idle après ~5 min, on recycle avant
    pool_pre_ping=True,
    echo=False,
    connect_args=_connect_args,
)


@event.listens_for(engine.sync_engine, "checkout")
def _invalidate_closed_connection(dbapi_conn, conn_record, conn_proxy):
    """
    asyncpg wraps the raw connection in a proxy; pool_pre_ping alone sometimes
    misses connections closed server-side.  This listener checks the raw
    asyncpg connection and invalidates it so SQLAlchemy creates a fresh one.
    """
    raw = getattr(dbapi_conn, "_connection", None)
    if raw is not None and raw.is_closed():
        conn_record.invalidate()


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables (safe to call even if tables exist)"""
    import app.db.postgres.models  # noqa: F401
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"   init_db warning: {type(e).__name__}: {e!r}")


async def check_connection() -> bool:
    """Check PostgreSQL connection via le pool (pas de connexion hors-pool)."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"   PostgreSQL check failed: {type(e).__name__}: {e!r}")
        return False


async def dispose_engine() -> None:
    """Nettoyage propre de l'engine"""
    await engine.dispose()
