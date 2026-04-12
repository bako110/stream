"""
Concerts — liste publique, détail, gestion artiste/admin, billets.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.postgres.session import get_db
from app.db.mongo.session import get_mongo
from app.deps import get_current_active_user, require_role
from app.db.postgres.models.user import User
from app.db.postgres.models.concert import ConcertStatus, Concert
from app.schemas.concert import ConcertCreate, ConcertUpdate, ConcertResponse, ConcertListItem
from app.schemas.ticket import TicketCreate, TicketResponse
from app.services.concert_service import ConcertService
from app.services.ticket_service import TicketService

router = APIRouter()


# ── Public ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ConcertListItem])
async def list_concerts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    genre: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    return (await ConcertService.list_concerts(page, limit, genre, db))["items"]


@router.get("/live", response_model=list[ConcertResponse])
async def get_live_concerts(db: AsyncSession = Depends(get_db)):
    return await ConcertService.get_live_concerts(db)


@router.get("/upcoming", response_model=list[ConcertResponse])
async def get_upcoming_concerts(db: AsyncSession = Depends(get_db)):
    return await ConcertService.get_upcoming_concerts(db)


@router.get("/{concert_id}", response_model=ConcertResponse)
async def get_concert(concert_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await ConcertService.get_concert(concert_id, db)


# ── Artiste / Admin — gestion ─────────────────────────────────────────────────

@router.post("", response_model=ConcertResponse, status_code=201)
async def create_concert(
    data: ConcertCreate,
    db: AsyncSession = Depends(get_db),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo),
    current_user: User = Depends(require_role("artist", "admin")),
):
    return await ConcertService.create_concert(data, current_user, db, mongo)


@router.put("/{concert_id}", response_model=ConcertResponse)
async def update_concert(
    concert_id: uuid.UUID,
    data: ConcertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await ConcertService.update_concert(concert_id, data, current_user, db)


@router.patch("/{concert_id}/publish", response_model=ConcertResponse)
async def publish_concert(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await ConcertService.publish_concert(concert_id, current_user, db)


@router.patch("/{concert_id}/start-live", response_model=ConcertResponse)
async def start_live(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await ConcertService.set_live_status(concert_id, ConcertStatus.live, current_user, db)


@router.patch("/{concert_id}/end-live", response_model=ConcertResponse)
async def end_live(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await ConcertService.set_live_status(concert_id, ConcertStatus.ended, current_user, db)


@router.delete("/{concert_id}", status_code=204)
async def delete_concert(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo),
    current_user: User = Depends(get_current_active_user),
):
    await ConcertService.delete_concert(concert_id, current_user, db, mongo)


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
    """Acheter un billet pour ce concert."""
    data = TicketCreate(concert_id=concert_id)
    return await TicketService.purchase_ticket(data, current_user, None, db)


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
