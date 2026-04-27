from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.db.postgres.session import init_db, check_connection as pg_check
from app.db.mongo.session import init_indexes, check_connection as mongo_check, close as mongo_close
from app.utils.cache import get_redis
from app.services.ws_manager import init_redis_relay, stop_redis_relay


async def _check_mongo() -> bool:
    """Init indexes + check mongo en séquentiel pour gather()"""
    try:
        await init_indexes()
        return await mongo_check()
    except Exception:
        return False


async def _pg_init_background() -> None:
    """Retry init_db + pg_check en arrière-plan (ne bloque pas le démarrage)."""
    import asyncio
    for attempt in range(1, 6):
        try:
            await init_db()
            ok = await pg_check()
            if ok:
                print(f"   PostgreSQL : OK (tentative background {attempt})")
                return
            else:
                print(f"   PostgreSQL background: tentative {attempt} — check retourné False")
        except Exception as e:
            print(f"   PostgreSQL background: tentative {attempt} — {type(e).__name__}: {e!r}")
        await asyncio.sleep(2)
    print("   PostgreSQL : toujours inaccessible après 5 tentatives background")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"\n Démarrage de {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"   Environnement : {settings.ENVIRONMENT}")

    import asyncio

    # ── Quick init — tente une fois chaque service sans bloquer longtemps ──────
    pg_ok = False
    try:
        await init_db()
        pg_ok = await pg_check()
        if pg_ok:
            from app.db.postgres.session import AsyncSessionLocal
            from app.utils.seed_admin import seed_admin
            async with AsyncSessionLocal() as db:
                await seed_admin(db)
    except Exception as e:
        print(f"   PostgreSQL init: {type(e).__name__}: {e!r}")

    mongo_result, redis_result = await asyncio.gather(
        _check_mongo(), get_redis(),
        return_exceptions=True,
    )

    print(f"   PostgreSQL : {'OK' if pg_ok else 'en attente (retry en fond)'}")
    print(f"   MongoDB    : {'OK' if isinstance(mongo_result, bool) and mongo_result else 'ERREUR'}")
    print(f"   Redis      : {'OK' if redis_result else 'indisponible (dégradé, sans cache)'}")

    # ── WS Redis relay (multi-instance support) ───────────────────────────
    if redis_result:
        await init_redis_relay(settings.REDIS_URL)

    # ── Firebase Admin (FCM push) ──────────────────────────────────────────
    from app.services.fcm_service import _get_app as _fcm_init
    _fcm_init()

    # Si PG a échoué, relancer les retries en background sans bloquer le serveur
    bg_task = None
    if not pg_ok:
        bg_task = asyncio.create_task(_pg_init_background())

    yield

    await stop_redis_relay()
    if bg_task and not bg_task.done():
        bg_task.cancel()
    await mongo_close()
    print("\n Arrêt de l'application...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── SlowAPI rate limiting ──────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Système"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health", tags=["Système"])
async def health_check():
    pg_ok = await pg_check()
    mongo_ok = await mongo_check()
    redis_ok = (await get_redis()) is not None
    return {
        "status": "healthy" if (pg_ok and mongo_ok) else "degraded",
        "postgresql": "ok" if pg_ok else "error",
        "mongodb":    "ok" if mongo_ok else "error",
        "redis":      "ok" if redis_ok else "unavailable",
        "version": settings.APP_VERSION,
    }


# ─── Routers ──────────────────────────────────────────────────────────────────
from app.routers import (
    auth, users, content, seasons, episodes, videos,
    concerts, streaming, subscriptions, payments,
    tickets, search, events, reels, social, upload, stories, messages,
    communities, activity, planning, notifications, orange_money, feed_actions,
)

API = "/api/v1"

# Auth
app.include_router(auth.router,          prefix=f"{API}/auth",          tags=["Auth"])

# Users (profil + admin users intégré)
app.include_router(users.router,         prefix=f"{API}/users",         tags=["Users"])

# Catalogue vidéo (films, séries + admin content intégré + dashboard)
app.include_router(content.router,       prefix=f"{API}/content",       tags=["Content"])
app.include_router(seasons.router,       prefix=f"{API}/content",       tags=["Seasons"])
app.include_router(episodes.router,      prefix=f"{API}",               tags=["Episodes"])
app.include_router(videos.router,        prefix=f"{API}",               tags=["Videos"])

# Concerts (gestion artiste/admin + billets intégrés)
app.include_router(concerts.router,      prefix=f"{API}/concerts",      tags=["Concerts"])
app.include_router(streaming.router,     prefix=f"{API}/stream",        tags=["Streaming"])

# Feed actions — "Pas intéressé" + "Me rappeler" (avant events/concerts pour que /events/{id}/remind soit matchée ici)
app.include_router(feed_actions.router, prefix=f"{API}",               tags=["Feed Actions"])

# Événements (anniversaire, festival… + billets intégrés)
app.include_router(events.router,        prefix=f"{API}/events",        tags=["Events"])

# Reels & Social
app.include_router(reels.router,         prefix=f"{API}/reels",         tags=["Reels"])
app.include_router(social.router,        prefix=f"{API}/social",        tags=["Social"])

# Abonnements / Paiements / Billets concerts (routes standalone)
app.include_router(subscriptions.router, prefix=f"{API}",               tags=["Subscriptions"])
app.include_router(payments.router,      prefix=f"{API}/payments",      tags=["Payments"])
app.include_router(tickets.router,       prefix=f"{API}/tickets",       tags=["Tickets"])

# Recherche
app.include_router(search.router,        prefix=f"{API}/search",        tags=["Search"])

# Upload médias (stockage local)
app.include_router(upload.router,        prefix=f"{API}/upload",        tags=["Upload"])

# Servir les fichiers uploadés localement
from pathlib import Path
from fastapi.staticfiles import StaticFiles

_upload_dir = Path(settings.UPLOAD_DIR)
_upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_upload_dir)), name="uploads")

# Stories (24h, style WhatsApp)
app.include_router(stories.router,       prefix=f"{API}/stories",       tags=["Stories"])

# Messagerie directe
app.include_router(messages.router,      prefix=f"{API}/messages",      tags=["Messages"])
app.include_router(communities.router,   prefix=f"{API}/communities",  tags=["Communities"])

# Activité sociale
app.include_router(activity.router,      prefix=f"{API}/activity",      tags=["Activity"])

# Notifications persistantes
app.include_router(notifications.router, prefix=f"{API}/notifications", tags=["Notifications"])

# Planning (agenda perso)
app.include_router(planning.router,      prefix=f"{API}/planning",      tags=["Planning"])

# Orange Money (paiement mobile)
app.include_router(orange_money.router, prefix=f"{API}/orange-money",  tags=["Orange Money"])

