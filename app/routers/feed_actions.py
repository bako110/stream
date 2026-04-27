"""
Feed actions — "Pas intéressé" et "Me rappeler" pour events et concerts.
"""
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import get_current_user
from app.db.postgres.models.user import User
from app.db.postgres.models.feed_hidden import FeedHidden
from app.db.postgres.models.content_reminder import ContentReminder, ReminderRefType
from app.db.postgres.models.event import Event
from app.db.postgres.models.concert import Concert
from app.services.notification_service import NotificationService
from app.db.postgres.models.notification import NotificationType

router = APIRouter(tags=["feed-actions"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class HideResponse(BaseModel):
    hidden: bool
    ref_id: str
    ref_type: str

class ReminderResponse(BaseModel):
    active: bool
    ref_id: str
    ref_type: str
    event_date: datetime | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_event_info(ref_id: str, db: AsyncSession) -> tuple[str, datetime]:
    row = await db.execute(select(Event).where(Event.id == uuid.UUID(ref_id)))
    ev = row.scalar_one_or_none()
    if not ev:
        raise HTTPException(404, "Événement introuvable")
    return ev.title, ev.starts_at


async def _get_concert_info(ref_id: str, db: AsyncSession) -> tuple[str, datetime]:
    row = await db.execute(select(Concert).where(Concert.id == uuid.UUID(ref_id)))
    c = row.scalar_one_or_none()
    if not c:
        raise HTTPException(404, "Concert introuvable")
    return c.title, c.scheduled_at


# ── "Pas intéressé" ───────────────────────────────────────────────────────────

@router.post("/events/{event_id}/hide", response_model=HideResponse)
async def hide_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ref_id = str(event_id)
    existing = await db.execute(
        select(FeedHidden).where(
            FeedHidden.user_id == current_user.id,
            FeedHidden.ref_id  == ref_id,
            FeedHidden.ref_type == "event",
        )
    )
    row = existing.scalar_one_or_none()
    if row:
        await db.execute(
            delete(FeedHidden).where(FeedHidden.id == row.id)
        )
        await db.commit()
        return HideResponse(hidden=False, ref_id=ref_id, ref_type="event")

    db.add(FeedHidden(user_id=current_user.id, ref_id=ref_id, ref_type="event"))
    await db.commit()
    return HideResponse(hidden=True, ref_id=ref_id, ref_type="event")


@router.post("/concerts/{concert_id}/hide", response_model=HideResponse)
async def hide_concert(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ref_id = str(concert_id)
    existing = await db.execute(
        select(FeedHidden).where(
            FeedHidden.user_id == current_user.id,
            FeedHidden.ref_id  == ref_id,
            FeedHidden.ref_type == "concert",
        )
    )
    row = existing.scalar_one_or_none()
    if row:
        await db.execute(
            delete(FeedHidden).where(FeedHidden.id == row.id)
        )
        await db.commit()
        return HideResponse(hidden=False, ref_id=ref_id, ref_type="concert")

    db.add(FeedHidden(user_id=current_user.id, ref_id=ref_id, ref_type="concert"))
    await db.commit()
    return HideResponse(hidden=True, ref_id=ref_id, ref_type="concert")


# ── "Me rappeler" ─────────────────────────────────────────────────────────────

@router.post("/events/{event_id}/remind", response_model=ReminderResponse)
async def toggle_remind_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ref_id = str(event_id)
    existing = await db.execute(
        select(ContentReminder).where(
            ContentReminder.user_id  == current_user.id,
            ContentReminder.ref_id   == ref_id,
            ContentReminder.ref_type == ReminderRefType.event,
        )
    )
    row = existing.scalar_one_or_none()
    if row:
        await db.execute(delete(ContentReminder).where(ContentReminder.id == row.id))
        await db.commit()
        return ReminderResponse(active=False, ref_id=ref_id, ref_type="event")

    title, event_date = await _get_event_info(ref_id, db)
    db.add(ContentReminder(
        user_id    = current_user.id,
        ref_id     = ref_id,
        ref_type   = ReminderRefType.event,
        event_date = event_date,
        title      = title,
    ))
    await db.commit()
    return ReminderResponse(active=True, ref_id=ref_id, ref_type="event", event_date=event_date)


@router.post("/concerts/{concert_id}/remind", response_model=ReminderResponse)
async def toggle_remind_concert(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ref_id = str(concert_id)
    existing = await db.execute(
        select(ContentReminder).where(
            ContentReminder.user_id  == current_user.id,
            ContentReminder.ref_id   == ref_id,
            ContentReminder.ref_type == ReminderRefType.concert,
        )
    )
    row = existing.scalar_one_or_none()
    if row:
        await db.execute(delete(ContentReminder).where(ContentReminder.id == row.id))
        await db.commit()
        return ReminderResponse(active=False, ref_id=ref_id, ref_type="concert")

    title, event_date = await _get_concert_info(ref_id, db)
    db.add(ContentReminder(
        user_id    = current_user.id,
        ref_id     = ref_id,
        ref_type   = ReminderRefType.concert,
        event_date = event_date,
        title      = title,
    ))
    await db.commit()
    return ReminderResponse(active=True, ref_id=ref_id, ref_type="concert", event_date=event_date)


# ── GET état (rappel actif?) ──────────────────────────────────────────────────

@router.get("/events/{event_id}/remind", response_model=ReminderResponse)
async def get_remind_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ref_id = str(event_id)
    row = (await db.execute(
        select(ContentReminder).where(
            ContentReminder.user_id  == current_user.id,
            ContentReminder.ref_id   == ref_id,
            ContentReminder.ref_type == ReminderRefType.event,
        )
    )).scalar_one_or_none()
    return ReminderResponse(
        active=row is not None, ref_id=ref_id, ref_type="event",
        event_date=row.event_date if row else None,
    )


@router.get("/concerts/{concert_id}/remind", response_model=ReminderResponse)
async def get_remind_concert(
    concert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ref_id = str(concert_id)
    row = (await db.execute(
        select(ContentReminder).where(
            ContentReminder.user_id  == current_user.id,
            ContentReminder.ref_id   == ref_id,
            ContentReminder.ref_type == ReminderRefType.concert,
        )
    )).scalar_one_or_none()
    return ReminderResponse(
        active=row is not None, ref_id=ref_id, ref_type="concert",
        event_date=row.event_date if row else None,
    )
