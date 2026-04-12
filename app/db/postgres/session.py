"""
Connexion PostgreSQL — compatible Supabase / PgBouncer Transaction pooler.

prepared_statement_cache_size=0 dans l'URL désactive le cache de prepared
statements au niveau du wrapper SQLAlchemy asyncpg — seule façon fiable
d'éviter DuplicatePreparedStatementError avec PgBouncer Transaction mode.
"""
import ssl as _ssl_module
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from typing import AsyncGenerator

from app.config import settings

_is_supabase = "supabase.co" in settings.DATABASE_URL

_ssl_ctx = None
_connect_args: dict = {}

if _is_supabase:
    _ssl_ctx = _ssl_module.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = _ssl_module.CERT_NONE
    _connect_args = {"ssl": _ssl_ctx}

engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=(settings.ENVIRONMENT == "development"),
    connect_args=_connect_args,
)

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
    import app.db.postgres.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def check_connection() -> bool:
    try:
        import asyncpg
        url = settings.DATABASE_URL.split("?")[0].replace(
            "postgresql+asyncpg://", "postgresql://"
        )
        conn = await asyncpg.connect(
            url, ssl=_ssl_ctx, statement_cache_size=0, timeout=5
        )
        await conn.execute("SELECT 1")
        await conn.close()
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("PostgreSQL check failed: %s", e)
        return False
