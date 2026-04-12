"""
Users — profil, historique, reels, gestion admin des comptes.
Les actions admin (changer rôle, désactiver, lister) sont ici, pas dans un router séparé.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.postgres.session import get_db
from app.db.mongo.session import get_mongo
from app.deps import get_current_active_user, require_role
from app.db.postgres.models.user import User, UserRole
from app.schemas.user import UserResponse, UserPublic, UserUpdate
from app.services.user_service import UserService

router = APIRouter()


# ── Profil personnel ─────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await UserService.update_me(data, current_user, db)


@router.get("/me/history")
async def get_watch_history(
    current_user: User = Depends(get_current_active_user),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo),
):
    """Historique de visionnage de l'utilisateur connecté."""
    return await UserService.get_watch_history(current_user, mongo)


# ── Profils publics ───────────────────────────────────────────────────────────

@router.get("/{user_id}/profile", response_model=UserPublic)
async def get_public_profile(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await UserService.get_by_id(user_id, db)


@router.get("/{user_id}/reels")
async def get_user_reels(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from app.services.reel_service import ReelService
    return await ReelService.get_user_reels(user_id, db)


# ── Admin — gestion des comptes ───────────────────────────────────────────────

@router.get("", response_model=list[UserResponse])
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    role: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """[Admin] Liste tous les utilisateurs avec filtre optionnel par rôle."""
    return await UserService.list_users(page, limit, role, db)


@router.put("/{user_id}/role")
async def change_user_role(
    user_id: uuid.UUID,
    role: UserRole,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """[Admin] Changer le rôle d'un utilisateur."""
    user = await UserService.change_role(user_id, role, db)
    return {"message": f"Rôle mis à jour : {role}", "user_id": str(user.id)}


@router.patch("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """[Admin] Désactiver un compte."""
    return await UserService.set_active(user_id, False, db)


@router.patch("/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """[Admin] Réactiver un compte."""
    return await UserService.set_active(user_id, True, db)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """[Admin] Supprimer définitivement un compte."""
    await UserService.delete(user_id, db)
