import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import get_current_active_user, require_role
from app.db.postgres.models.user import User
from app.db.postgres.models.activity import ActivityType
from app.schemas.event import EventCreate, EventUpdate, EventResponse, EventListItem, EventTicketResponse
from app.services.event_service import EventService
from app.services.activity_service import ActivityService
from app.utils.cache import cache_get, cache_set, cache_invalidate_prefix

router = APIRouter()


@router.get("", response_model=list[EventListItem])
async def list_events(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    event_type: Optional[str] = None,
    city: Optional[str] = None,
    status: Optional[str] = None,
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    contact_ids: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Pas de cache si géoloc ou contacts fournis (résultats personnalisés)
    no_cache = request.headers.get("Cache-Control") == "no-cache" or lat is not None or contact_ids is not None

    if not no_cache:
        ck = f"events:list:p{page}:l{limit}:t{event_type or 'all'}:c{city or 'all'}:s{status or 'all'}"
        if (cached := await cache_get(ck)) is not None:
            return cached

    # Récupérer les IDs des gens suivis pour le boost
    from sqlalchemy import select as _select
    from app.db.postgres.models.follow import Follow
    following_result = await db.execute(
        _select(Follow.following_id).where(Follow.follower_id == current_user.id)
    )
    following_ids = [row[0] for row in following_result.fetchall()]

    # Filtre contacts — liste d'UUIDs séparés par virgule
    parsed_contact_ids = None
    if contact_ids:
        try:
            import uuid as _uuid
            parsed_contact_ids = [_uuid.UUID(i.strip()) for i in contact_ids.split(",") if i.strip()]
        except Exception:
            parsed_contact_ids = None

    result = (await EventService.list_events(
        page, limit, event_type, city, status, db,
        user_lat=lat, user_lon=lon, following_ids=following_ids,
        organizer_ids=parsed_contact_ids,
    ))["items"]
    serialized = [EventListItem.model_validate(e).model_dump(mode="json") for e in result]

    if not no_cache:
        await cache_set(ck, serialized, ttl=60)
    return serialized


@router.get("/me", response_model=list[EventResponse])
async def my_events(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from sqlalchemy import select as _select
    from app.db.postgres.models.event import Event as EventModel
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        _select(EventModel)
        .options(selectinload(EventModel.organizer))
        .where(EventModel.organizer_id == current_user.id)
        .order_by(EventModel.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(event_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await EventService.get_event(event_id, db)


@router.post("", response_model=EventResponse, status_code=201)
async def create_event(
    data: EventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await EventService.create_event(data, current_user, db)
    await cache_invalidate_prefix("events:")
    await cache_invalidate_prefix("fil_utilisateur:")
    await cache_invalidate_prefix("fil_anonymous:")
    try:
        await ActivityService.log(
            actor_id=current_user.id,
            activity_type=ActivityType.event_created,
            db=db,
            ref_id=str(result.id),
            summary=f"{current_user.display_name or current_user.username} a créé l'événement « {result.title} »",
        )
    except Exception:
        pass
    return result


@router.put("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: uuid.UUID,
    data: EventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await EventService.update_event(event_id, data, current_user, db)
    await cache_invalidate_prefix("events:")
    await cache_invalidate_prefix("fil_utilisateur:")
    await cache_invalidate_prefix("fil_anonymous:")
    return result


@router.patch("/{event_id}/publish", response_model=EventResponse)
async def publish_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await EventService.publish_event(event_id, current_user, db)
    await cache_invalidate_prefix("events:")
    await cache_invalidate_prefix("fil_utilisateur:")
    await cache_invalidate_prefix("fil_anonymous:")
    return result


@router.delete("/{event_id}", status_code=200)
async def delete_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await EventService.delete_event(event_id, current_user, db)
    await cache_invalidate_prefix("events:")
    await cache_invalidate_prefix("fil_utilisateur:")
    await cache_invalidate_prefix("fil_anonymous:")


# ── Billets ────────────────────────────────────────────────────────────────

@router.post("/{event_id}/tickets", response_model=EventTicketResponse, status_code=201)
async def purchase_event_ticket(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    ticket = await EventService.purchase_ticket(event_id, current_user, None, db)
    try:
        event = await EventService.get_event(event_id, db)
        await ActivityService.log(
            actor_id=current_user.id,
            activity_type=ActivityType.event_going,
            db=db,
            ref_id=str(event_id),
            summary=f"{current_user.display_name or current_user.username} va à « {event.title} »",
        )
    except Exception:
        pass
    return ticket


@router.get("/tickets/me", response_model=list[EventTicketResponse])
async def my_event_tickets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await EventService.get_my_tickets(current_user, db)


@router.patch("/tickets/{ticket_id}/validate", response_model=EventTicketResponse)
async def validate_event_ticket(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin", "artist")),
):
    return await EventService.validate_ticket(ticket_id, db)
