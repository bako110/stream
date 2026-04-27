import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, cast, Float, literal, String
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.db.postgres.models.event import Event, EventStatus
from app.db.postgres.models.event_ticket import EventTicket
from app.db.postgres.models.ticket import TicketStatus
from app.db.postgres.models.user import User
from app.schemas.event import EventCreate, EventUpdate
from app.utils.cache import cache_invalidate_prefix
from app.services.local_storage_service import delete_media


class EventService:

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Distance en km entre deux coordonnées GPS."""
        from math import radians, sin, cos, sqrt, atan2
        R = 6371.0
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        return R * 2 * atan2(sqrt(a), sqrt(1 - a))

    @staticmethod
    async def list_events(
        page: int, limit: int,
        event_type: str | None, city: str | None, status: str | None,
        db: AsyncSession,
        user_lat: float | None = None, user_lon: float | None = None,
        following_ids: list | None = None,
        organizer_ids: list | None = None,
    ) -> dict:
        now = datetime.utcnow()
        follow_ids_str = [str(fid) for fid in (following_ids or [])]

        # Filtres WHERE
        filters = [Event.status == (status if status else EventStatus.published)]
        if event_type:
            filters.append(Event.event_type == event_type)
        if city:
            filters.append(Event.venue_city.ilike(f"%{city}%"))
        if organizer_ids:
            filters.append(Event.organizer_id.in_(organizer_ids))

        total = await db.scalar(
            select(func.count()).select_from(select(Event).where(*filters).subquery())
        )

        # Score SQL : follow boost + featured + fraîcheur date
        follow_boost = (
            case((Event.organizer_id.cast(String).in_(follow_ids_str), cast(1000.0, Float)), else_=cast(0.0, Float))
            if follow_ids_str else cast(0.0, Float)
        )
        featured_boost = case((Event.is_featured == True, cast(200.0, Float)), else_=cast(0.0, Float))
        time_penalty = func.abs(
            func.extract("epoch", Event.starts_at) - func.extract("epoch", literal(now))
        ) / 86400.0
        score_col = (follow_boost + featured_boost - time_penalty).label("score")

        result = await db.execute(
            select(Event)
            .options(selectinload(Event.organizer))
            .where(*filters)
            .order_by(score_col.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        items = result.scalars().all()

        return {"items": items, "total": total, "page": page, "limit": limit}

    @staticmethod
    async def get_event(event_id: uuid.UUID, db: AsyncSession) -> Event:
        result = await db.execute(
            select(Event)
            .options(selectinload(Event.organizer))
            .where(Event.id == event_id)
        )
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        return event

    @staticmethod
    async def create_event(data: EventCreate, organizer: User, db: AsyncSession) -> Event:
        dump = data.model_dump(exclude_none=True)
        for key in ("starts_at", "ends_at"):
            if key in dump and dump[key] is not None and dump[key].tzinfo is not None:
                dump[key] = dump[key].replace(tzinfo=None)
        event = Event(**dump, organizer_id=organizer.id)
        db.add(event)
        await db.commit()
        result = await db.execute(
            select(Event)
            .options(selectinload(Event.organizer))
            .where(Event.id == event.id)
        )
        event = result.scalar_one()
        await cache_invalidate_prefix("events:")
        return event

    @staticmethod
    def _check_owner(event: Event, user: User) -> None:
        role = user.role.value if hasattr(user.role, "value") else user.role
        event_org_id = uuid.UUID(str(event.organizer_id))
        user_id = uuid.UUID(str(user.id))
        if event_org_id != user_id and role != "admin":
            raise HTTPException(status_code=403, detail="Accès réservé à l'organisateur")

    @staticmethod
    async def update_event(event_id: uuid.UUID, data: EventUpdate, user: User, db: AsyncSession) -> Event:
        result = await db.execute(select(Event).where(Event.id == event_id))
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        EventService._check_owner(event, user)
        for key, value in data.model_dump(exclude_unset=True).items():
            if key in ("starts_at", "ends_at") and value is not None and value.tzinfo is not None:
                value = value.replace(tzinfo=None)
            setattr(event, key, value)
        await db.commit()
        result = await db.execute(
            select(Event)
            .options(selectinload(Event.organizer))
            .where(Event.id == event.id)
        )
        event = result.scalar_one()
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
        result = await db.execute(
            select(Event)
            .options(selectinload(Event.organizer))
            .where(Event.id == event_id)
        )
        event = result.scalar_one()
        await cache_invalidate_prefix("events:")
        return event

    @staticmethod
    async def delete_event(event_id: uuid.UUID, user: User, db: AsyncSession) -> None:
        result = await db.execute(select(Event).where(Event.id == event_id))
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        EventService._check_owner(event, user)
        video_url = event.video_url
        thumbnail_url = event.thumbnail_url
        banner_url = event.banner_url
        await db.delete(event)
        await db.commit()
        await delete_media(video_url)
        await delete_media(thumbnail_url)
        await delete_media(banner_url)
        await cache_invalidate_prefix("events:")

    # ── Billets événement ────────────────────────────────────────────────────

    @staticmethod
    async def purchase_ticket(event_id: uuid.UUID, user: User, payment_id: uuid.UUID | None, db: AsyncSession) -> EventTicket:
        result = await db.execute(select(Event).where(Event.id == event_id))
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=404, detail="Événement non trouvé")
        if event.status != EventStatus.published:
            raise HTTPException(status_code=400, detail="Cet événement n'accepte plus d'inscriptions")
        if event.max_attendees and event.current_attendees >= event.max_attendees:
            raise HTTPException(status_code=409, detail="Plus de places disponibles")

        # Vérifier si l'utilisateur est déjà inscrit
        existing = await db.scalar(
            select(EventTicket).where(
                EventTicket.user_id == user.id,
                EventTicket.event_id == event_id,
            )
        )
        if existing:
            raise HTTPException(status_code=409, detail="Vous êtes déjà inscrit à cet événement")

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
            select(EventTicket)
            .options(selectinload(EventTicket.event))
            .where(EventTicket.user_id == user.id)
            .order_by(EventTicket.created_at.desc())
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
