import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import get_current_active_user, require_role
from app.db.postgres.models.user import User
from app.schemas.event import EventCreate, EventUpdate, EventResponse, EventListItem, EventTicketResponse
from app.services.event_service import EventService

router = APIRouter()


@router.get("", response_model=list[EventListItem])
async def list_events(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    event_type: Optional[str] = None,
    city: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    return (await EventService.list_events(page, limit, event_type, city, db))["items"]


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(event_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await EventService.get_event(event_id, db)


@router.post("", response_model=EventResponse, status_code=201)
async def create_event(
    data: EventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await EventService.create_event(data, current_user, db)


@router.put("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: uuid.UUID,
    data: EventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await EventService.update_event(event_id, data, current_user, db)


@router.patch("/{event_id}/publish", response_model=EventResponse)
async def publish_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await EventService.publish_event(event_id, current_user, db)


@router.delete("/{event_id}", status_code=204)
async def delete_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await EventService.delete_event(event_id, current_user, db)


# ── Billets ────────────────────────────────────────────────────────────────

@router.post("/{event_id}/tickets", response_model=EventTicketResponse, status_code=201)
async def purchase_event_ticket(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await EventService.purchase_ticket(event_id, current_user, None, db)


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
