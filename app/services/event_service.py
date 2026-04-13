import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException

from app.db.postgres.models.event import Event, EventStatus, EventAccessType
from app.db.postgres.models.event_ticket import EventTicket
from app.db.postgres.models.ticket import TicketStatus
from app.db.postgres.models.user import User
from app.schemas.event import EventCreate, EventUpdate
from app.utils.cache import cache_invalidate_prefix


class EventService:

    @staticmethod
    async def list_events(page: int, limit: int, event_type: str | None, city: str | None, db: AsyncSession) -> dict:
        query = select(Event)
        if event_type:
            query = query.where(Event.event_type == event_type)
        if city:
            query = query.where(Event.venue_city.ilike(f"%{city}%"))
        query = query.order_by(Event.starts_at)
        total = await db.scalar(select(func.count()).select_from(query.subquery()))
        result = await db.execute(query.offset((page - 1) * limit).limit(limit))
        items = result.scalars().all()
        return {"items": items, "total": total, "page": page, "limit": limit}

    @staticmethod
    async def get_event(event_id: uuid.UUID, db: AsyncSession) -> Event:
        result = await db.execute(select(Event).where(Event.id == event_id))
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        return event

    @staticmethod
    async def create_event(data: EventCreate, organizer: User, db: AsyncSession) -> Event:
        event = Event(**data.model_dump(exclude_none=True), organizer_id=organizer.id)
        db.add(event)
        await db.commit()
        await db.refresh(event)
        await cache_invalidate_prefix("events:")
        return event

    @staticmethod
    def _check_owner(event: Event, user: User) -> None:
        if event.organizer_id != user.id and user.role.value != "admin":
            raise HTTPException(status_code=403, detail="Accès réservé à l'organisateur")

    @staticmethod
    async def update_event(event_id: uuid.UUID, data: EventUpdate, user: User, db: AsyncSession) -> Event:
        result = await db.execute(select(Event).where(Event.id == event_id))
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        EventService._check_owner(event, user)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(event, key, value)
        await db.commit()
        await db.refresh(event)
        await cache_invalidate_prefix("events:")
        return event

    @staticmethod
    async def publish_event(event_id: uuid.UUID, user: User, db: AsyncSession) -> Event:
        result = await db.execute(select(Event).where(Event.id == event_id))
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        EventService._check_owner(event, user)
        event.status = EventStatus.published
        event.published_at = datetime.utcnow()
        await db.commit()
        await db.refresh(event)
        await cache_invalidate_prefix("events:")
        return event

    @staticmethod
    async def delete_event(event_id: uuid.UUID, user: User, db: AsyncSession) -> None:
        result = await db.execute(select(Event).where(Event.id == event_id))
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        EventService._check_owner(event, user)
        await db.delete(event)
        await db.commit()
        await cache_invalidate_prefix("events:")

    # ── Billets événement ────────────────────────────────────────────────────

    @staticmethod
    async def purchase_ticket(event_id: uuid.UUID, user: User, payment_id: uuid.UUID | None, db: AsyncSession) -> EventTicket:
        result = await db.execute(select(Event).where(Event.id == event_id))
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        if event.status != EventStatus.published:
            raise HTTPException(status_code=400, detail="Cet événement n'accepte plus de billets")
        if event.access_type == EventAccessType.free:
            raise HTTPException(status_code=400, detail="Cet événement est gratuit, aucun billet requis")
        if event.max_attendees and event.current_attendees >= event.max_attendees:
            raise HTTPException(status_code=409, detail="Plus de places disponibles")

        ticket = EventTicket(
            user_id=user.id,
            event_id=event_id,
            payment_id=payment_id,
            price_paid=event.ticket_price or 0,
        )
        event.current_attendees += 1
        db.add(ticket)
        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def get_my_tickets(user: User, db: AsyncSession) -> list:
        result = await db.execute(
            select(EventTicket).where(EventTicket.user_id == user.id).order_by(EventTicket.created_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def validate_ticket(ticket_id: uuid.UUID, db: AsyncSession) -> EventTicket:
        result = await db.execute(select(EventTicket).where(EventTicket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="Billet non trouvé")
        if ticket.status != TicketStatus.valid:
            raise HTTPException(status_code=400, detail=f"Billet non valide : statut = {ticket.status}")
        ticket.status = TicketStatus.used
        ticket.used_at = datetime.utcnow()
        await db.commit()
        await db.refresh(ticket)
        return ticket
