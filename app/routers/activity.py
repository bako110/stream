from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import get_current_user
from app.services.activity_service import ActivityService

router = APIRouter(tags=["Activity"])


def _serialize(a):
    return {
        "id": str(a.id),
        "actor_id": str(a.actor_id),
        "actor": {
            "id": str(a.actor.id),
            "username": a.actor.username,
            "display_name": a.actor.display_name,
            "avatar_url": a.actor.avatar_url,
        } if a.actor else None,
        "target_user_id": str(a.target_user_id) if a.target_user_id else None,
        "activity_type": a.activity_type.value if hasattr(a.activity_type, "value") else a.activity_type,
        "ref_id": a.ref_id,
        "summary": a.summary,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/feed")
async def get_activity_feed(
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    activities = await ActivityService.get_feed(user.id, db, page=page, limit=limit)
    return [_serialize(a) for a in activities]
