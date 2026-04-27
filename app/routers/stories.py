import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.session import get_db
from app.deps import get_current_active_user
from app.db.postgres.models.user import User
from app.schemas.story import StoryCreate, StoryUpdate, StoryResponse, StoryGroupResponse, StoryViewerResponse
from app.services.story_service import StoryService

router = APIRouter()


# ── Feed groupé (style WhatsApp) ──────────────────────────────────────────────

@router.get("/feed", response_model=list[StoryGroupResponse])
async def get_stories_feed(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retourne les stories actives groupées par utilisateur, non-vues en premier."""
    return await StoryService.get_feed(current_user.id, db)


# ── Mes stories ───────────────────────────────────────────────────────────────

@router.get("/me", response_model=list[StoryResponse])
async def get_my_stories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    stories = await StoryService.get_my_stories(current_user.id, db)
    return [StoryResponse.model_validate(s) for s in stories]


# ── Créer une story ───────────────────────────────────────────────────────────

@router.post("", response_model=StoryResponse, status_code=status.HTTP_201_CREATED)
async def create_story(
    data: StoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    story = await StoryService.create(current_user.id, data, db)
    return StoryResponse.model_validate(story)


# ── Viewers d'une story (propriétaire uniquement) ────────────────────────────

@router.get("/{story_id}/viewers", response_model=list[StoryViewerResponse])
async def get_story_viewers(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retourne la liste des utilisateurs qui ont vu cette story (propriétaire uniquement)."""
    return await StoryService.get_viewers(story_id, current_user.id, db)


# ── Marquer une story comme vue ───────────────────────────────────────────────

@router.post("/{story_id}/view", status_code=status.HTTP_204_NO_CONTENT)
async def view_story(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await StoryService.mark_viewed(story_id, current_user.id, db)

# ── Modifier une story ─────────────────────────────────────────────────────

@router.patch("/{story_id}", response_model=StoryResponse)
async def update_story(
    story_id: uuid.UUID,
    data: StoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    story = await StoryService.update(story_id, current_user.id, data, db)
    return StoryResponse.model_validate(story)

# ── Supprimer une story ───────────────────────────────────────────────────────

@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_story(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await StoryService.delete(story_id, current_user.id, db)
