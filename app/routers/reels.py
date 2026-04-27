import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from app.db.postgres.session import get_db
from app.deps import get_current_active_user, get_optional_user
from app.db.postgres.models.user import User
from app.db.postgres.models.reel import Reel  # FIX: import manquant
from app.schemas.reel import ReelCreate, ReelUpdate, ReelResponse, ReelViewInput
from app.services.reel_service import ReelService
from app.services.activity_service import ActivityService
from app.db.postgres.models.activity import ActivityType
from app.utils.cache import cache_get, cache_set, cache_invalidate_prefix

router = APIRouter()


@router.get("", response_model=list[ReelResponse])
async def list_reels(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    # Recherche textuelle — priorité sur le feed normal
    if search and search.strip():
        from sqlalchemy import select as sa_select, or_
        from sqlalchemy.orm import selectinload as sio
        from app.db.postgres.models.reel import ReelStatus as RS
        q = search.strip()
        stmt = (
            sa_select(Reel)
            .options(sio(Reel.author))
            .join(Reel.author)
            .where(
                Reel.status == RS.published,
                or_(
                    Reel.caption.ilike(f"%{q}%"),
                    User.username.ilike(f"%{q}%"),
                    User.display_name.ilike(f"%{q}%"),
                ),
            )
            .order_by(Reel.view_count.desc(), Reel.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        res = await db.execute(stmt)
        reels = ReelService._transform_reel_urls(list(res.scalars().all()))
        return [ReelResponse.model_validate(r) for r in reels]

    if current_user:
        from app.db.postgres.models.user_block import UserBlock
        from sqlalchemy import select as sa_select
        blocked_res = await db.execute(
            sa_select(UserBlock.blocked_id).where(UserBlock.blocker_id == current_user.id)
        )
        blocked_ids = {r[0] for r in blocked_res.all()}
        blockers_res = await db.execute(
            sa_select(UserBlock.blocker_id).where(UserBlock.blocked_id == current_user.id)
        )
        blocked_ids |= {r[0] for r in blockers_res.all()}
        result = (await ReelService.get_feed(current_user.id, page, limit, db))["items"]
        if blocked_ids:
            result = [r for r in result if str(r.get("user_id") or (r.get("author") or {}).get("id", "")) not in [str(b) for b in blocked_ids]]
    else:
        ck = f"reels:list:p{page}:l{limit}"
        if (cached := await cache_get(ck)) is not None:
            return cached
        result = (await ReelService.list_reels(page, limit, db))["items"]
        serialized = [ReelResponse.model_validate(r).model_dump(mode="json") for r in result]
        await cache_set(ck, serialized, ttl=60)
    return result


# FIX: /user/{user_id} AVANT /{reel_id} sinon FastAPI intercepte "user" comme UUID
@router.get("/user/{user_id}", response_model=list[ReelResponse])
async def get_user_reels(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    ck = f"reels:user:{user_id}"
    if (cached := await cache_get(ck)) is not None:
        return cached
    result = await ReelService.get_user_reels(user_id, db)
    serialized = [ReelResponse.model_validate(r).model_dump(mode="json") for r in result]
    await cache_set(ck, serialized, ttl=60)
    return result


@router.get("/{reel_id}", response_model=ReelResponse)
async def get_reel(reel_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await ReelService.get_reel(reel_id, db)


@router.post("/{reel_id}/view", status_code=204)
async def view_reel(
    reel_id: uuid.UUID,
    data: ReelViewInput = ReelViewInput(),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    if current_user:
        await ReelService.record_view(reel_id, current_user.id, data.watch_ratio, db)
    else:
        await db.execute(
            update(Reel).where(Reel.id == reel_id).values(view_count=Reel.view_count + 1)
        )
        await db.commit()


@router.post("", response_model=ReelResponse, status_code=201)
async def create_reel(
    data: ReelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await ReelService.create_reel(data, current_user, db)
    await cache_invalidate_prefix("reels:")
    try:
        await ActivityService.log(
            actor_id=current_user.id,
            activity_type=ActivityType.reel_posted,
            db=db,
            ref_id=str(result.id),
            summary=f"{current_user.display_name or current_user.username} a posté un reel",
        )
    except Exception:
        pass
    return result


@router.put("/{reel_id}", response_model=ReelResponse)
async def update_reel(
    reel_id: uuid.UUID,
    data: ReelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await ReelService.update_reel(reel_id, data, current_user, db)
    await cache_invalidate_prefix("reels:")
    return result


@router.delete("/{reel_id}", status_code=204)
async def delete_reel(
    reel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await ReelService.delete_reel(reel_id, current_user, db)
    await cache_invalidate_prefix("reels:")
