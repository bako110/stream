from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.postgres.session import init_db, check_connection as pg_check
from app.db.mongo.session import init_indexes, check_connection as mongo_check, close as mongo_close


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"\n Démarrage de {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"   Environnement : {settings.ENVIRONMENT}")

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    try:
        if settings.ENVIRONMENT == "development":
            try:
                await init_db()
            except Exception as e:
                print(f"   init_db ignoré (tables déjà créées ou connexion directe indisponible) : {e.__class__.__name__}")
        pg_ok = await pg_check()
        print(f"   PostgreSQL : {'OK' if pg_ok else 'ERREUR de connexion'}")
    except Exception as e:
        print(f"   PostgreSQL : ERREUR — {e}")

    # ── MongoDB ───────────────────────────────────────────────────────────────
    try:
        await init_indexes()
        mongo_ok = await mongo_check()
        print(f"   MongoDB    : {'OK' if mongo_ok else 'ERREUR de connexion'}")
    except Exception as e:
        print(f"   MongoDB    : ERREUR — {e}")

    yield

    await mongo_close()
    print("\n Arrêt de l'application...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

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
    return {
        "status": "healthy" if (pg_ok and mongo_ok) else "degraded",
        "postgresql": "ok" if pg_ok else "error",
        "mongodb": "ok" if mongo_ok else "error",
        "version": settings.APP_VERSION,
    }


# ─── Routers ──────────────────────────────────────────────────────────────────
from app.routers import (
    auth, users, content, seasons, episodes, videos,
    concerts, streaming, subscriptions, payments,
    tickets, search, events, reels, social,
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
