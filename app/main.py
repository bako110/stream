from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import settings
from app.database import init_db, check_db_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"\n🚀 Démarrage de {settings.APP_NAME} v{settings.APP_VERSION}")
    if settings.ENVIRONMENT == "development":
        await init_db()
    yield
    print("\n🛑 Arrêt de l'application...")


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
    db_ok = await check_db_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "version": settings.APP_VERSION,
    }

from app.routers import (
    auth, users, content, seasons, episodes, videos,
    concerts, streaming, subscriptions, payments,
    tickets, search, admin,
)

API_PREFIX = "/api/v1"

app.include_router(auth.router,          prefix=f"{API_PREFIX}/auth",          tags=["Auth"])
app.include_router(users.router,         prefix=f"{API_PREFIX}/users",         tags=["Users"])
app.include_router(content.router,       prefix=f"{API_PREFIX}/content",       tags=["Content"])
app.include_router(seasons.router,       prefix=f"{API_PREFIX}/content",       tags=["Seasons"])
app.include_router(episodes.router,      prefix=f"{API_PREFIX}",               tags=["Episodes"])
app.include_router(videos.router,        prefix=f"{API_PREFIX}",               tags=["Videos"])
app.include_router(concerts.router,      prefix=f"{API_PREFIX}/concerts",      tags=["Concerts"])
app.include_router(streaming.router,     prefix=f"{API_PREFIX}/stream",        tags=["Streaming"])
app.include_router(subscriptions.router, prefix=f"{API_PREFIX}",               tags=["Subscriptions"])
app.include_router(payments.router,      prefix=f"{API_PREFIX}/payments",      tags=["Payments"])
app.include_router(tickets.router,       prefix=f"{API_PREFIX}/tickets",       tags=["Tickets"])
app.include_router(search.router,        prefix=f"{API_PREFIX}/search",        tags=["Search"])
app.include_router(admin.router,         prefix=f"{API_PREFIX}/admin",         tags=["Admin"])