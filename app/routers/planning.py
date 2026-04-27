"""
Planning — vue agenda : billets concerts + billets événements + mes propres events/concerts + entrées perso.
"""
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.postgres.session import get_db
from app.deps import get_current_user
from app.db.postgres.models.ticket import Ticket, TicketStatus
from app.db.postgres.models.event_ticket import EventTicket
from app.db.postgres.models.concert import Concert
from app.db.postgres.models.event import Event
from app.db.postgres.models.planning_entry import PlanningEntry

router = APIRouter(tags=["Planning"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class PlanningEntryCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    date: datetime
    end_date: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=255)
    color: Optional[str] = Field("#3B82F6", max_length=7)

class PlanningEntryUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=255)
    color: Optional[str] = Field(None, max_length=7)


def _serialize_concert_item(ticket: Ticket) -> dict:
    c = ticket.concert
    return {
        "type": "concert",
        "id": str(ticket.id),
        "ref_id": str(c.id),
        "title": c.title,
        "date": c.scheduled_at.isoformat() if c.scheduled_at else None,
        "venue": ", ".join(filter(None, [c.venue_name, c.venue_city])),
        "thumbnail_url": c.thumbnail_url,
        "genre": c.genre,
        "status": c.status.value if hasattr(c.status, "value") else c.status,
        "ticket_status": ticket.status.value if hasattr(ticket.status, "value") else ticket.status,
        "access_code": ticket.access_code,
        "artist": {
            "id": str(c.artist.id),
            "username": c.artist.username,
            "display_name": c.artist.display_name,
            "avatar_url": c.artist.avatar_url,
        } if c.artist else None,
    }


def _serialize_event_item(ticket: EventTicket) -> dict:
    e = ticket.event
    return {
        "type": "event",
        "id": str(ticket.id),
        "ref_id": str(e.id),
        "title": e.title,
        "date": e.starts_at.isoformat() if e.starts_at else None,
        "end_date": e.ends_at.isoformat() if e.ends_at else None,
        "venue": ", ".join(filter(None, [e.venue_name, e.venue_city])),
        "thumbnail_url": e.thumbnail_url,
        "event_type": e.event_type.value if hasattr(e.event_type, "value") else e.event_type,
        "status": e.status.value if hasattr(e.status, "value") else e.status,
        "ticket_status": ticket.status.value if hasattr(ticket.status, "value") else ticket.status,
        "access_code": ticket.access_code,
        "organizer": {
            "id": str(e.organizer.id),
            "username": e.organizer.username,
            "display_name": e.organizer.display_name,
            "avatar_url": e.organizer.avatar_url,
        } if e.organizer else None,
    }


def _serialize_my_concert(c: Concert) -> dict:
    return {
        "type": "my_concert",
        "id": str(c.id),
        "ref_id": str(c.id),
        "title": c.title,
        "date": c.scheduled_at.isoformat() if c.scheduled_at else None,
        "venue": ", ".join(filter(None, [c.venue_name, c.venue_city])),
        "thumbnail_url": c.thumbnail_url,
        "genre": c.genre,
        "status": c.status.value if hasattr(c.status, "value") else c.status,
        "ticket_status": None,
        "access_code": None,
        "artist": None,
    }


def _serialize_my_event(e: Event) -> dict:
    return {
        "type": "my_event",
        "id": str(e.id),
        "ref_id": str(e.id),
        "title": e.title,
        "date": e.starts_at.isoformat() if e.starts_at else None,
        "end_date": e.ends_at.isoformat() if e.ends_at else None,
        "venue": ", ".join(filter(None, [e.venue_name, e.venue_city])),
        "thumbnail_url": e.thumbnail_url,
        "event_type": e.event_type.value if hasattr(e.event_type, "value") else e.event_type,
        "status": e.status.value if hasattr(e.status, "value") else e.status,
        "ticket_status": None,
        "access_code": None,
        "organizer": None,
    }


def _serialize_personal_entry(entry: PlanningEntry) -> dict:
    return {
        "type": "personal",
        "id": str(entry.id),
        "ref_id": str(entry.id),
        "title": entry.title,
        "description": entry.description,
        "date": entry.date.isoformat() if entry.date else None,
        "end_date": entry.end_date.isoformat() if entry.end_date else None,
        "venue": entry.location or "",
        "thumbnail_url": None,
        "color": entry.color,
        "status": "personal",
        "ticket_status": None,
        "access_code": None,
        "artist": None,
        "organizer": None,
    }


@router.get("")
async def get_planning(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retourne l'agenda de l'utilisateur :
    - Concerts pour lesquels il a un billet (valid)
    - Événements pour lesquels il a un billet (valid)
    - Concerts qu'il a créés
    - Événements qu'il a créés
    Trié par date croissante.
    """
    uid = user.id
    now = datetime.utcnow()

    # 1) Billets concerts (valid, concert pas terminé/archivé)
    concert_tickets_q = await db.execute(
        select(Ticket)
        .options(
            selectinload(Ticket.concert).selectinload(Concert.artist),
        )
        .where(
            Ticket.user_id == uid,
            Ticket.status == TicketStatus.valid,
        )
    )
    concert_tickets = concert_tickets_q.scalars().all()

    # 2) Billets événements (valid)
    event_tickets_q = await db.execute(
        select(EventTicket)
        .options(
            selectinload(EventTicket.event).selectinload(Event.organizer),
        )
        .where(
            EventTicket.user_id == uid,
            EventTicket.status == TicketStatus.valid,
        )
    )
    event_tickets = event_tickets_q.scalars().all()

    # 3) Mes concerts (que j'ai créés)
    my_concerts_q = await db.execute(
        select(Concert)
        .where(Concert.artist_id == uid)
    )
    my_concerts = my_concerts_q.scalars().all()

    # 4) Mes événements (que j'ai créés)
    my_events_q = await db.execute(
        select(Event)
        .where(Event.organizer_id == uid)
    )
    my_events = my_events_q.scalars().all()

    # 5) Entrées personnelles
    personal_q = await db.execute(
        select(PlanningEntry)
        .where(PlanningEntry.user_id == uid)
    )
    personal_entries = personal_q.scalars().all()

    # Agréger et sérialiser
    items = []
    seen_refs = set()

    for t in concert_tickets:
        ref = str(t.concert_id)
        if ref not in seen_refs:
            seen_refs.add(ref)
            items.append(_serialize_concert_item(t))

    for t in event_tickets:
        ref = str(t.event_id)
        if ref not in seen_refs:
            seen_refs.add(ref)
            items.append(_serialize_event_item(t))

    for c in my_concerts:
        ref = str(c.id)
        if ref not in seen_refs:
            seen_refs.add(ref)
            items.append(_serialize_my_concert(c))

    for e in my_events:
        ref = str(e.id)
        if ref not in seen_refs:
            seen_refs.add(ref)
            items.append(_serialize_my_event(e))

    for entry in personal_entries:
        items.append(_serialize_personal_entry(entry))

    # Tri par date
    items.sort(key=lambda x: x.get("date") or "9999")

    # Pagination simple
    offset = (page - 1) * limit
    return items[offset:offset + limit]


# ── CRUD entrées personnelles ─────────────────────────────────────────────────

@router.post("/entries", status_code=201)
async def create_entry(
    data: PlanningEntryCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = PlanningEntry(
        user_id=user.id,
        title=data.title,
        description=data.description,
        date=data.date.replace(tzinfo=None) if data.date else data.date,
        end_date=data.end_date.replace(tzinfo=None) if data.end_date else data.end_date,
        location=data.location,
        color=data.color or "#3B82F6",
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return _serialize_personal_entry(entry)


@router.put("/entries/{entry_id}")
async def update_entry(
    entry_id: uuid.UUID,
    data: PlanningEntryUpdate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlanningEntry).where(
            PlanningEntry.id == entry_id,
            PlanningEntry.user_id == user.id,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(404, "Entrée introuvable")

    for field, val in data.model_dump(exclude_unset=True).items():
        if field in ("date", "end_date") and val is not None and hasattr(val, 'replace'):
            val = val.replace(tzinfo=None)
        setattr(entry, field, val)

    await db.commit()
    await db.refresh(entry)
    return _serialize_personal_entry(entry)


@router.delete("/entries/{entry_id}", status_code=204)
async def delete_entry(
    entry_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlanningEntry).where(
            PlanningEntry.id == entry_id,
            PlanningEntry.user_id == user.id,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(404, "Entrée introuvable")

    await db.delete(entry)
    await db.commit()
