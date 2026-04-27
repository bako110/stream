import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.db.postgres.models.ticket import Ticket, TicketStatus
from app.db.postgres.models.concert import Concert
from app.db.postgres.models.user import User
from app.schemas.ticket import TicketCreate


class TicketService:

    @staticmethod
    async def get_user_tickets(user: User, db: AsyncSession) -> list:
        result = await db.execute(
            select(Ticket)
            .options(selectinload(Ticket.concert))
            .where(Ticket.user_id == user.id)
            .order_by(Ticket.created_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def get_ticket(ticket_id: uuid.UUID, user: User, db: AsyncSession) -> Ticket:
        result = await db.execute(
            select(Ticket)
            .options(selectinload(Ticket.concert))
            .where(Ticket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="Billet non trouvé")
        role = user.role.value if hasattr(user.role, 'value') else user.role
        if ticket.user_id != user.id and role != "admin":
            raise HTTPException(status_code=403, detail="Accès refusé")
        return ticket

    @staticmethod
    async def purchase_ticket(data: TicketCreate, user: User, payment_id: uuid.UUID | None, db: AsyncSession) -> Ticket:
        result = await db.execute(select(Concert).where(Concert.id == data.concert_id))
        concert = result.scalar_one_or_none()
        if not concert:
            raise HTTPException(status_code=404, detail="Concert non trouvé")

        existing = await db.scalar(
            select(Ticket).where(Ticket.user_id == user.id, Ticket.concert_id == data.concert_id)
        )
        if existing:
            raise HTTPException(status_code=409, detail="Vous êtes déjà inscrit à ce concert")

        ticket = Ticket(
            user_id=user.id, concert_id=data.concert_id, payment_id=payment_id,
            price_paid=concert.ticket_price or 0, includes_replay=data.includes_replay,
        )
        db.add(ticket)
        await db.commit()
        await db.refresh(ticket)
        return ticket

    @staticmethod
    async def validate_ticket(ticket_id: uuid.UUID, db: AsyncSession) -> Ticket:
        result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
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
