import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import get_current_active_user, require_role
from app.db.postgres.models.user import User
from app.schemas.ticket import TicketCreate, TicketResponse
from app.services.ticket_service import TicketService

router = APIRouter()


@router.get("/me", response_model=list[TicketResponse])
async def get_my_tickets(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return await TicketService.get_user_tickets(current_user, db)


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return await TicketService.get_ticket(ticket_id, current_user, db)


@router.post("", response_model=TicketResponse, status_code=201)
async def purchase_ticket(data: TicketCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return await TicketService.purchase_ticket(data, current_user, None, db)


@router.patch("/{ticket_id}/validate", response_model=TicketResponse)
async def validate_ticket(ticket_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_role("admin", "artist"))):
    return await TicketService.validate_ticket(ticket_id, db)
