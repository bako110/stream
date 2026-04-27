import uuid
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import get_current_active_user
from app.db.postgres.models.user import User
from app.db.postgres.models.notification import Notification
from app.db.postgres.models.device_token import DeviceToken
from app.services.notification_service import NotificationService

router = APIRouter()


def _serialize(n: Notification) -> dict:
    return {
        "id":                str(n.id),
        "notification_type": n.notification_type.value if hasattr(n.notification_type, "value") else n.notification_type,
        "title":             n.title,
        "body":              n.body,
        "ref_id":            n.ref_id,
        "ref_type":          n.ref_type,
        "is_read":           n.is_read,
        "created_at":        n.created_at.isoformat() if n.created_at else None,
        "actor": {
            "id":           str(n.actor.id),
            "username":     n.actor.username,
            "display_name": n.actor.display_name,
            "avatar_url":   n.actor.avatar_url,
        } if n.actor else None,
    }


@router.get("")
async def list_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    notifs = await NotificationService.get_for_user(
        current_user.id, db, page=page, limit=limit, unread_only=unread_only,
    )
    return [_serialize(n) for n in notifs]


@router.get("/unread-count")
async def unread_count(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    count = await NotificationService.unread_count(current_user.id, db)
    return {"unread_count": count}


@router.patch("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    updated = await NotificationService.mark_all_read(current_user.id, db)
    return {"marked_read": updated}


@router.patch("/{notif_id}/read")
async def mark_read(
    notif_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await NotificationService.mark_read(notif_id, current_user.id, db)
    return {"ok": True}


@router.delete("/{notif_id}")
async def delete_notification(
    notif_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await NotificationService.delete(notif_id, current_user.id, db)
    return {"ok": True}


@router.delete("")
async def delete_all_notifications(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await NotificationService.delete_all(current_user.id, db)
    return {"ok": True}


# ── FCM Device Token ──────────────────────────────────────────────────────────

class DeviceTokenBody(BaseModel):
    token: str
    platform: str = "android"


@router.post("/device-token", status_code=204)
async def register_device_token(
    body: DeviceTokenBody,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Register or refresh a FCM device token for push notifications."""
    existing = await db.execute(
        select(DeviceToken).where(
            DeviceToken.user_id == current_user.id,
            DeviceToken.token == body.token,
        )
    )
    row = existing.scalar_one_or_none()
    if row:
        row.platform = body.platform
    else:
        db.add(DeviceToken(user_id=current_user.id, token=body.token, platform=body.platform))
    await db.commit()


@router.delete("/device-token", status_code=204)
async def unregister_device_token(
    body: DeviceTokenBody,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a FCM device token (on logout)."""
    await db.execute(
        delete(DeviceToken).where(
            DeviceToken.user_id == current_user.id,
            DeviceToken.token == body.token,
        )
    )
    await db.commit()


@router.post("/device-token/remove", status_code=204)
async def unregister_device_token_post(
    body: DeviceTokenBody,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a FCM device token — POST variant for clients that can't send body with DELETE."""
    await db.execute(
        delete(DeviceToken).where(
            DeviceToken.user_id == current_user.id,
            DeviceToken.token == body.token,
        )
    )
    await db.commit()
