"""
Concerts — liste publique, détail, gestion artiste/admin, billets.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.postgres.session import get_db
from app.db.mongo.session import get_mongo
from app.deps import get_current_active_user, require_role
from app.db.postgres.models.user import User
from app.db.postgres.models.concert import ConcertStatus, Concert
from app.db.postgres.models.follow import Follow
from app.schemas.concert import ConcertCreate, ConcertUpdate, ConcertResponse, ConcertListItem
from app.schemas.ticket import TicketCreate, TicketResponse
from app.services.concert_service import ConcertService
from app.services.ticket_service import TicketService
from app.services.activity_service import ActivityService
from app.db.postgres.models.activity import ActivityType
from app.utils.cache import cache_get, cache_set, cache_invalidate_prefix

router = APIRouter()


# ── Public ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ConcertListItem])
async def list_concerts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    genre: Optional[str] = None,
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    no_cache = lat is not None
    if not no_cache:
        ck = f"concerts:list:p{page}:l{limit}:g{genre or 'all'}"
        if (cached := await cache_get(ck)) is not None:
            return cached

    following_result = await db.execute(
        select(Follow.following_id).where(Follow.follower_id == current_user.id)
    )
    following_ids = [row[0] for row in following_result.fetchall()]

    result = (await ConcertService.list_concerts(
        page, limit, genre, db,
        user_lat=lat, user_lon=lon, following_ids=following_ids,
    ))["items"]
    serialized = [ConcertListItem.model_validate(c).model_dump(mode="json") for c in result]

    if not no_cache:
        await cache_set(ck, serialized, ttl=60)
    return serialized


@router.get("/live", response_model=list[ConcertResponse])
async def get_live_concerts(db: AsyncSession = Depends(get_db)):
    if (cached := await cache_get("concerts:live")) is not None:
        return cached
    result = await ConcertService.get_live_concerts(db)
    serialized = [ConcertResponse.model_validate(c).model_dump(mode="json") for c in result]
    await cache_set("concerts:live", serialized, ttl=15)
    return serialized


@router.get("/upcoming", response_model=list[ConcertResponse])
async def get_upcoming_concerts(db: AsyncSession = Depends(get_db)):
    if (cached := await cache_get("concerts:upcoming")) is not None:
        return cached
    result = await ConcertService.get_upcoming_concerts(db)
    serialized = [ConcertResponse.model_validate(c).model_dump(mode="json") for c in result]
    await cache_set("concerts:upcoming", serialized, ttl=120)
    return serialized


@router.get("/me", response_model=list[ConcertResponse])
async def my_concerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Concert)
        .options(selectinload(Concert.artist))
        .where(Concert.artist_id == current_user.id)
        .order_by(Concert.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{concert_id}", response_model=ConcertResponse)
async def get_concert(concert_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    ck = f"concerts:{concert_id}"
    if (cached := await cache_get(ck)) is not None:
        return cached
    result = await ConcertService.get_concert(concert_id, db)
    serialized = ConcertResponse.model_validate(result).model_dump(mode="json")
    await cache_set(ck, serialized, ttl=60)
    return serialized


# ── Artiste / Admin — gestion ─────────────────────────────────────────────────

@router.post("", response_model=ConcertResponse, status_code=201)
async def create_concert(
    data: ConcertCreate,
    db: AsyncSession = Depends(get_db),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo),
    current_user: User = Depends(get_current_active_user),
):
    result = await ConcertService.create_concert(data, current_user, db, mongo)
    await cache_invalidate_prefix("concerts:")
    await cache_invalidate_prefix("fil_utilisateur:")
    await cache_invalidate_prefix("fil_anonymous:")
    try:
        await ActivityService.log(
            actor_id=current_user.id,
            activity_type=ActivityType.concert_created,
            db=db,
            ref_id=str(result.id),
            summary=f"{current_user.display_name or current_user.username} a créé le concert « {result.title} »",
        )
    except Exception:
        pass
    return result


@router.put("/{concert_id}", response_model=ConcertResponse)
async def update_concert(
    concert_id: uuid.UUID,
    data: ConcertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await ConcertService.update_concert(concert_id, data, current_user, db)
    await cache_invalidate_prefix("concerts:")
    await cache_invalidate_prefix("fil_utilisateur:")
    await cache_invalidate_prefix("fil_anonymous:")
    return result


@router.patch("/{concert_id}/publish", response_model=ConcertResponse)
async def publish_concert(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await ConcertService.publish_concert(concert_id, current_user, db)
    await cache_invalidate_prefix("concerts:")
    await cache_invalidate_prefix("fil_utilisateur:")
    await cache_invalidate_prefix("fil_anonymous:")
    return result


@router.patch("/{concert_id}/start-live", response_model=ConcertResponse)
async def start_live(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await ConcertService.set_live_status(concert_id, ConcertStatus.live, current_user, db)
    await cache_invalidate_prefix("concerts:")
    return result


@router.patch("/{concert_id}/end-live", response_model=ConcertResponse)
async def end_live(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await ConcertService.set_live_status(concert_id, ConcertStatus.ended, current_user, db)
    await cache_invalidate_prefix("concerts:")
    return result


@router.delete("/{concert_id}", status_code=204)
async def delete_concert(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo),
    current_user: User = Depends(get_current_active_user),
):
    await ConcertService.delete_concert(concert_id, current_user, db, mongo)
    await cache_invalidate_prefix("concerts:")


# ── Admin — liste complète ────────────────────────────────────────────────────

@router.get("/admin/all", response_model=list[ConcertResponse])
async def list_all_concerts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """[Admin] Tous les concerts (draft inclus)."""
    result = await db.execute(select(Concert).order_by(Concert.created_at.desc()).limit(100))
    return result.scalars().all()


# ── Billets concert ───────────────────────────────────────────────────────────

@router.post("/{concert_id}/tickets", response_model=TicketResponse, status_code=201)
async def purchase_ticket(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Acheter / s'inscrire à ce concert."""
    data = TicketCreate(concert_id=concert_id)
    ticket = await TicketService.purchase_ticket(data, current_user, None, db)
    try:
        concert = await ConcertService.get_concert(concert_id, db)
        await ActivityService.log(
            actor_id=current_user.id,
            activity_type=ActivityType.concert_going,
            db=db,
            ref_id=str(concert_id),
            summary=f"{current_user.display_name or current_user.username} va au concert « {concert.title} »",
        )
    except Exception:
        pass
    return ticket


@router.get("/tickets/me", response_model=list[TicketResponse])
async def my_concert_tickets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await TicketService.get_user_tickets(current_user, db)


@router.patch("/tickets/{ticket_id}/validate", response_model=TicketResponse)
async def validate_concert_ticket(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin", "artist")),
):
    return await TicketService.validate_ticket(ticket_id, db)
