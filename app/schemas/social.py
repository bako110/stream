"""Schémas pour les interactions sociales : commentaires, réactions, partages."""
from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime

from app.db.postgres.models.reaction import ReactionType
from app.db.postgres.models.share import SharePlatform


# ─── Commentaires ─────────────────────────────────────────────────────────────

class CommentCreate(BaseModel):
    body: str
    # Une seule cible à la fois
    reel_id: Optional[UUID4] = None
    content_id: Optional[UUID4] = None
    concert_id: Optional[UUID4] = None
    event_id: Optional[UUID4] = None
    parent_id: Optional[UUID4] = None       # pour répondre à un commentaire


class CommentUpdate(BaseModel):
    body: str


class AuthorInfo(BaseModel):
    id: UUID4
    username: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

    model_config = {"from_attributes": True}


class CommentResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    body: str
    is_edited: bool
    like_count: int
    dislike_count: int = 0
    reel_id: Optional[UUID4] = None
    content_id: Optional[UUID4] = None
    concert_id: Optional[UUID4] = None
    event_id: Optional[UUID4] = None
    parent_id: Optional[UUID4] = None
    created_at: datetime
    updated_at: datetime
    author: Optional[AuthorInfo] = None

    model_config = {"from_attributes": True}


# ─── Réactions (like / dislike) ───────────────────────────────────────────────

class ReactionCreate(BaseModel):
    reaction_type: ReactionType
    # Une seule cible à la fois
    reel_id: Optional[UUID4] = None
    content_id: Optional[UUID4] = None
    concert_id: Optional[UUID4] = None
    event_id: Optional[UUID4] = None
    comment_id: Optional[UUID4] = None


class ReactionResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    reaction_type: ReactionType
    reel_id: Optional[UUID4] = None
    content_id: Optional[UUID4] = None
    concert_id: Optional[UUID4] = None
    event_id: Optional[UUID4] = None
    comment_id: Optional[UUID4] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Partages ─────────────────────────────────────────────────────────────────

class ShareCreate(BaseModel):
    platform: SharePlatform = SharePlatform.external
    reel_id: Optional[UUID4] = None
    content_id: Optional[UUID4] = None
    concert_id: Optional[UUID4] = None
    event_id: Optional[UUID4] = None


class ShareResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    platform: SharePlatform
    reel_id: Optional[UUID4] = None
    content_id: Optional[UUID4] = None
    concert_id: Optional[UUID4] = None
    event_id: Optional[UUID4] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Compteurs agrégés (réponse générique) ────────────────────────────────────

class ReactionSummary(BaseModel):
    likes: int
    dislikes: int
    user_reaction: Optional[ReactionType] = None   # réaction de l'utilisateur courant
