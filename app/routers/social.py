"""
Router social — commentaires, réactions (like/dislike), partages.
Toutes les interactions utilisateur sur reels, contenus, concerts, événements.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import get_current_active_user
from app.db.postgres.models.user import User
from app.schemas.social import (
    CommentCreate, CommentUpdate, CommentResponse,
    ReactionCreate, ReactionResponse,
    ShareCreate, ShareResponse,
)
from app.services.social_service import CommentService, ReactionService, ShareService

router = APIRouter()


# ── Commentaires ─────────────────────────────────────────────────────────────

@router.get("/comments", response_model=list[CommentResponse])
async def list_comments(
    reel_id: Optional[uuid.UUID] = Query(None),
    content_id: Optional[uuid.UUID] = Query(None),
    concert_id: Optional[uuid.UUID] = Query(None),
    event_id: Optional[uuid.UUID] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await CommentService.list_comments(reel_id, content_id, concert_id, event_id, page, limit, db)


@router.get("/comments/{comment_id}/replies", response_model=list[CommentResponse])
async def get_replies(comment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await CommentService.get_replies(comment_id, db)


@router.post("/comments", response_model=CommentResponse, status_code=201)
async def create_comment(
    data: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await CommentService.create_comment(data, current_user, db)


@router.put("/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: uuid.UUID,
    data: CommentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await CommentService.update_comment(comment_id, data, current_user, db)


@router.delete("/comments/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await CommentService.delete_comment(comment_id, current_user, db)


# ── Réactions ─────────────────────────────────────────────────────────────────

@router.post("/reactions", response_model=dict)
async def toggle_reaction(
    data: ReactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Like ou dislike — si la même réaction existe elle est supprimée (toggle)."""
    return await ReactionService.toggle_reaction(data, current_user, db)


@router.get("/reactions/me")
async def my_reaction(
    reel_id: Optional[uuid.UUID] = Query(None),
    content_id: Optional[uuid.UUID] = Query(None),
    concert_id: Optional[uuid.UUID] = Query(None),
    event_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    reaction = await ReactionService.get_my_reaction(
        current_user, reel_id, content_id, concert_id, event_id, db
    )
    return {"reaction_type": reaction}


@router.get("/reactions/counts")
async def reaction_counts(
    reel_id: Optional[uuid.UUID] = Query(None),
    content_id: Optional[uuid.UUID] = Query(None),
    concert_id: Optional[uuid.UUID] = Query(None),
    event_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Compteurs likes/dislikes pour une cible."""
    return await ReactionService.get_counts(reel_id, content_id, concert_id, event_id, db)


# ── Partages ──────────────────────────────────────────────────────────────────

@router.post("/shares", response_model=ShareResponse, status_code=201)
async def share_content(
    data: ShareCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await ShareService.share(data, current_user, db)


@router.get("/shares/counts")
async def share_counts(
    reel_id: Optional[uuid.UUID] = Query(None),
    content_id: Optional[uuid.UUID] = Query(None),
    concert_id: Optional[uuid.UUID] = Query(None),
    event_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Compteur de partages par plateforme pour une cible."""
    return await ShareService.get_share_counts(reel_id, content_id, concert_id, event_id, db)
