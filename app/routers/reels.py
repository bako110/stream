import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import get_current_active_user
from app.db.postgres.models.user import User
from app.schemas.reel import ReelCreate, ReelUpdate, ReelResponse
from app.services.reel_service import ReelService

router = APIRouter()


@router.get("", response_model=list[ReelResponse])
async def list_reels(page: int = 1, limit: int = 20, db: AsyncSession = Depends(get_db)):
    return (await ReelService.list_reels(page, limit, db))["items"]


@router.get("/{reel_id}", response_model=ReelResponse)
async def get_reel(reel_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await ReelService.get_reel(reel_id, db)


@router.post("/{reel_id}/view", status_code=204)
async def view_reel(reel_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await ReelService.increment_view(reel_id, db)


@router.post("", response_model=ReelResponse, status_code=201)
async def create_reel(
    data: ReelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await ReelService.create_reel(data, current_user, db)


@router.put("/{reel_id}", response_model=ReelResponse)
async def update_reel(
    reel_id: uuid.UUID,
    data: ReelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await ReelService.update_reel(reel_id, data, current_user, db)


@router.delete("/{reel_id}", status_code=204)
async def delete_reel(
    reel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await ReelService.delete_reel(reel_id, current_user, db)


@router.get("/user/{user_id}", response_model=list[ReelResponse])
async def get_user_reels(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await ReelService.get_user_reels(user_id, db)
