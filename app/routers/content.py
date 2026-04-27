"""
Content — films, séries, dashboard stats admin.
Les routes admin (créer, publier, supprimer) sont ici dans la section dédiée.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.postgres.session import get_db
from app.deps import get_current_active_user, require_role
from app.db.postgres.models.user import User
from app.db.postgres.models.content import Content, ContentStatus, ContentType
from app.db.postgres.models.concert import Concert
from app.db.postgres.models.payment import Payment
from app.db.postgres.models.reel import Reel
from app.schemas.content import ContentCreate, ContentUpdate, ContentResponse, ContentListResponse
from app.services.content_service import ContentService
from app.utils.cache import cache_get, cache_set, cache_invalidate_prefix

router = APIRouter()


# ── Dashboard admin ───────────────────────────────────────────────────────────

@router.get("/dashboard")
async def dashboard(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """[Admin] Statistiques globales de la plateforme."""
    from app.db.postgres.models.event import Event
    from app.db.postgres.models.subscription import Subscription, SubscriptionStatus
    return {
        "users":         await db.scalar(select(func.count()).select_from(
                             select(User).subquery())),
        "contents":      await db.scalar(select(func.count()).select_from(
                             select(Content).subquery())),
        "films":         await db.scalar(select(func.count()).select_from(
                             select(Content).where(Content.type == ContentType.film).subquery())),
        "series":        await db.scalar(select(func.count()).select_from(
                             select(Content).where(Content.type == ContentType.serie).subquery())),
        "concerts":      await db.scalar(select(func.count()).select_from(
                             select(Concert).subquery())),
        "events":        await db.scalar(select(func.count()).select_from(
                             select(Event).subquery())),
        "reels":         await db.scalar(select(func.count()).select_from(
                             select(Reel).subquery())),
        "payments":      await db.scalar(select(func.count()).select_from(
                             select(Payment).subquery())),
        "subscriptions": await db.scalar(select(func.count()).select_from(
                             select(Subscription).where(
                                 Subscription.status == SubscriptionStatus.active).subquery())),
    }


# ── Films — public ────────────────────────────────────────────────────────────

@router.get("/films", response_model=ContentListResponse)
async def list_films(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    year: Optional[int] = None,
    language: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    ck = f"films:list:p{page}:l{limit}:y{year or 'all'}:l{language or 'all'}"
    if (cached := await cache_get(ck)) is not None:
        return cached
    result = await ContentService.list_films(page, limit, year, language, db)
    serialized = {
        "items": [ContentResponse.model_validate(i).model_dump(mode="json") for i in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "limit": result["limit"],
    }
    await cache_set(ck, serialized, ttl=120)
    return result


# ── Films — admin list (draft + published) ────────────────────────────────────

@router.get("/films/admin", response_model=ContentListResponse)
async def list_films_admin(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await ContentService.list_films(page, limit, None, None, db, admin=True)
    return result


@router.get("/films/{content_id}", response_model=ContentResponse)
async def get_film(content_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    ck = f"film:{content_id}"
    if (cached := await cache_get(ck)) is not None:
        return cached
    result = await ContentService.get_film(content_id, db)
    await cache_set(ck, ContentResponse.model_validate(result).model_dump(mode="json"), ttl=300)
    return result


# ── Films — admin ─────────────────────────────────────────────────────────────

@router.post("/films", response_model=ContentResponse, status_code=201)
async def create_film(
    data: ContentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = await ContentService.create_film(data, current_user.id, db)
    await cache_invalidate_prefix("films:")
    await cache_invalidate_prefix("series:")
    return result


@router.put("/films/{content_id}", response_model=ContentResponse)
async def update_film(
    content_id: uuid.UUID,
    data: ContentUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await ContentService.update_content(content_id, data, db)
    await cache_invalidate_prefix("films:")
    await cache_invalidate_prefix("series:")
    await cache_invalidate_prefix(f"film:{content_id}")
    await cache_invalidate_prefix(f"serie:{content_id}")
    return result


@router.patch("/films/{content_id}/publish", response_model=ContentResponse)
async def publish_film(
    content_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await ContentService.toggle_publish(content_id, db)
    await cache_invalidate_prefix("films:")
    await cache_invalidate_prefix("series:")
    await cache_invalidate_prefix(f"film:{content_id}")
    await cache_invalidate_prefix(f"serie:{content_id}")
    return result


@router.delete("/films/{content_id}", status_code=204)
async def delete_film(
    content_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    await ContentService.delete_content(content_id, db)
    await cache_invalidate_prefix("films:")
    await cache_invalidate_prefix("series:")
    await cache_invalidate_prefix(f"film:{content_id}")
    await cache_invalidate_prefix(f"serie:{content_id}")


# ── Séries — public ───────────────────────────────────────────────────────────

@router.get("/series", response_model=ContentListResponse)
async def list_series(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    ck = f"series:list:p{page}:l{limit}"
    if (cached := await cache_get(ck)) is not None:
        return cached
    result = await ContentService.list_series(page, limit, db)
    serialized = {
        "items": [ContentResponse.model_validate(i).model_dump(mode="json") for i in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "limit": result["limit"],
    }
    await cache_set(ck, serialized, ttl=120)
    return result


# ── Séries — admin list (draft + published) ───────────────────────────────────

@router.get("/series/admin", response_model=ContentListResponse)
async def list_series_admin(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await ContentService.list_series(page, limit, db, admin=True)
    return result


@router.get("/series/{content_id}", response_model=ContentResponse)
async def get_serie(content_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    ck = f"serie:{content_id}"
    if (cached := await cache_get(ck)) is not None:
        return cached
    result = await ContentService.get_serie(content_id, db)
    await cache_set(ck, ContentResponse.model_validate(result).model_dump(mode="json"), ttl=300)
    return result


# ── Séries — admin ────────────────────────────────────────────────────────────

@router.post("/series", response_model=ContentResponse, status_code=201)
async def create_serie(
    data: ContentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = await ContentService.create_serie(data, current_user.id, db)
    await cache_invalidate_prefix("series:")
    await cache_invalidate_prefix("films:")
    return result


@router.put("/series/{content_id}", response_model=ContentResponse)
async def update_serie(
    content_id: uuid.UUID,
    data: ContentUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await ContentService.update_content(content_id, data, db)
    await cache_invalidate_prefix("series:")
    await cache_invalidate_prefix("films:")
    return result


@router.patch("/series/{content_id}/publish", response_model=ContentResponse)
async def publish_serie(
    content_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    result = await ContentService.toggle_publish(content_id, db)
    await cache_invalidate_prefix("series:")
    await cache_invalidate_prefix("films:")
    return result


@router.delete("/series/{content_id}", status_code=204)
async def delete_serie(
    content_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    await ContentService.delete_content(content_id, db)
    await cache_invalidate_prefix("series:")
    await cache_invalidate_prefix("films:")


# ── Admin — liste complète tous contenus ──────────────────────────────────────

@router.get("/all", response_model=list[ContentResponse])
async def list_all_content(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """[Admin] Tous les contenus (draft inclus), triés par date de création."""
    result = await db.execute(
        select(Content).order_by(Content.created_at.desc()).limit(100)
    )
    return result.scalars().all()
