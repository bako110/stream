"""
Users — profil, historique, reels, gestion admin des comptes.
Les actions admin (changer rôle, désactiver, lister) sont ici, pas dans un router séparé.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.postgres.session import get_db
from app.db.mongo.session import get_mongo
from app.deps import get_current_active_user, get_optional_user, require_role
from app.db.postgres.models.user import User, UserRole, VerificationStatus
from app.db.postgres.models.follow import Follow
from app.db.postgres.models.user_block import UserBlock
from app.schemas.user import (
    UserResponse, UserPublic, UserPublicProfile, UserUpdate, PrivacySettings,
    VerificationRequest, VerificationReview, VerificationStatusResponse,
)
from app.services.user_service import UserService
from app.services.activity_service import ActivityService
from app.db.postgres.models.activity import ActivityType
from app.utils.cache import cache_get, cache_set, cache_delete, cache_invalidate_prefix

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


@router.delete("/me", status_code=204)
async def delete_my_account(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Suppression de compte initiée par l'utilisateur (soft-delete : désactivation + marquage)."""
    await UserService.soft_delete(current_user.id, db)


@router.get("/me/privacy", response_model=PrivacySettings)
async def get_privacy(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retourne les paramètres de confidentialité — toujours depuis la DB."""
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()
    return PrivacySettings.model_validate(user)


@router.put("/me/privacy", response_model=PrivacySettings)
async def update_privacy(
    data: PrivacySettings,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Met à jour les paramètres de confidentialité via UPDATE direct (évite le problème cache ORM)."""
    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(**data.model_dump())
    )
    await db.commit()
    # Invalider le cache user ET tous les caches profil (tous les viewers)
    await cache_delete(f"user:{current_user.id}")
    await cache_invalidate_prefix(f"profile:{current_user.id}:")
    return data


@router.get("/suggestions", response_model=list[UserPublic])
async def get_user_suggestions(
    limit: int = Query(10, ge=1, le=30),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Suggestions d'utilisateurs à suivre — amis de mes amis, puis aléatoires. Paginé via offset."""
    return await UserService.suggest_users(current_user.id, db, limit=limit, offset=offset)


@router.get("/me/history")
async def get_watch_history(
    current_user: User = Depends(get_current_active_user),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo),
):
    """Historique de visionnage de l'utilisateur connecté."""
    return await UserService.get_watch_history(current_user, mongo)


# ── Profils publics ───────────────────────────────────────────────────────────

@router.get("/{user_id}/profile", response_model=UserPublicProfile)
async def get_public_profile(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    """Profil public enrichi avec compteurs follow — mis en cache 10 min."""
    from fastapi import HTTPException
    # Bloquer l'accès si l'un a bloqué l'autre
    if current_user:
        block = await db.execute(
            select(UserBlock).where(
                (UserBlock.blocker_id == current_user.id) & (UserBlock.blocked_id == user_id) |
                (UserBlock.blocker_id == user_id) & (UserBlock.blocked_id == current_user.id)
            )
        )
        if block.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    viewer_id = str(current_user.id) if current_user else "anon"
    cache_key = f"profile:{user_id}:viewer:{viewer_id}"

    cached = await cache_get(cache_key)
    if cached is not None:
        return UserPublicProfile(**cached)

    user = await UserService.get_by_id(user_id, db)

    # Une seule requête pour les deux compteurs follow
    counts_result = await db.execute(
        select(
            func.count(Follow.id).filter(Follow.following_id == user_id).label("followers"),
            func.count(Follow.id).filter(Follow.follower_id == user_id).label("following"),
        )
    )
    row = counts_result.one()
    followers_count = row.followers or 0
    following_count = row.following or 0

    # Vérification is_followed si connecté
    is_followed = False
    if current_user:
        check = await db.execute(
            select(Follow.id).where(
                Follow.follower_id == current_user.id,
                Follow.following_id == user_id,
            )
        )
        is_followed = check.scalar_one_or_none() is not None

    # Appliquer les règles de confidentialité
    # Un utilisateur voit toujours son propre profil complet
    is_owner = current_user is not None and current_user.id == user_id
    # Un follower mutuel (ami) voit plus d'infos qu'un inconnu
    is_follower = is_followed  # le viewer suit cet utilisateur

    profile = UserPublicProfile(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        bio=user.bio,
        avatar_url=user.avatar_url,
        banner_url=user.banner_url,
        followers_count=followers_count,
        following_count=following_count,
        is_followed=is_followed,
        is_verified=user.is_verified,
        # Champs conditionnels selon privacy
        first_name=user.first_name if (is_owner or user.privacy_profile_public or is_follower) else None,
        last_name=user.last_name if (is_owner or user.privacy_profile_public or is_follower) else None,
        location=user.location if (is_owner or user.privacy_show_location) else None,
        website=user.website if (is_owner or user.privacy_profile_public) else None,
        phone=user.phone if (is_owner or user.privacy_show_phone) else None,
        date_of_birth=user.date_of_birth if (is_owner or user.privacy_show_birthday) else None,
        gender=user.gender if (is_owner or user.privacy_profile_public) else None,
        created_at=user.created_at if (is_owner or user.privacy_profile_public) else None,
    )

    await cache_set(cache_key, profile.model_dump(mode="json"), ttl=600)

    # Notifier le propriétaire du profil (hors soi-même, throttlé par le cache 10min)
    if current_user and current_user.id != user_id and cached is None:
        try:
            await ActivityService.log(
                actor_id=current_user.id,
                activity_type=ActivityType.profile_view,
                db=db,
                target_user_id=user_id,
            )
        except Exception:
            pass

    return profile


@router.get("/{user_id}/reels")
async def get_user_reels(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from app.services.reel_service import ReelService
    return await ReelService.get_user_reels(user_id, db)


@router.get("/{user_id}/events")
async def get_user_events(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Événements publiés d'un utilisateur."""
    from app.db.postgres.models.event import Event, EventStatus
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Event)
        .options(selectinload(Event.organizer))
        .where(Event.organizer_id == user_id, Event.status == EventStatus.published)
        .order_by(Event.starts_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.get("/{user_id}/concerts")
async def get_user_concerts(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Concerts publiés d'un utilisateur."""
    from app.db.postgres.models.concert import Concert, ConcertStatus
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Concert)
        .options(selectinload(Concert.artist))
        .where(Concert.artist_id == user_id, Concert.status == ConcertStatus.published)
        .order_by(Concert.scheduled_at.desc())
        .limit(50)
    )
    return result.scalars().all()


# ── Follow / Unfollow ─────────────────────────────────────────────────────────

@router.post("/{user_id}/follow")
async def follow_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Suivre un utilisateur."""
    from fastapi import HTTPException
    if user_id == current_user.id:
        raise HTTPException(400, "Vous ne pouvez pas vous suivre vous-même")

    # Impossible de suivre quelqu'un qui vous a bloqué ou que vous avez bloqué
    block = await db.execute(
        select(UserBlock).where(
            (UserBlock.blocker_id == current_user.id) & (UserBlock.blocked_id == user_id) |
            (UserBlock.blocker_id == user_id) & (UserBlock.blocked_id == current_user.id)
        )
    )
    if block.scalar_one_or_none():
        raise HTTPException(403, "Action impossible")

    exists = await db.execute(
        select(Follow).where(
            Follow.follower_id == current_user.id,
            Follow.following_id == user_id,
        )
    )
    if exists.scalar_one_or_none():
        return {"message": "Déjà suivi", "is_following": True}

    db.add(Follow(follower_id=current_user.id, following_id=user_id))
    await db.commit()
    try:
        await ActivityService.log(
            actor_id=current_user.id,
            activity_type=ActivityType.follow,
            db=db,
            target_user_id=user_id,
            summary=None,
        )
    except Exception:
        pass
    return {"message": "Suivi", "is_following": True}


@router.delete("/{user_id}/follow")
async def unfollow_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Ne plus suivre un utilisateur."""
    result = await db.execute(
        select(Follow).where(
            Follow.follower_id == current_user.id,
            Follow.following_id == user_id,
        )
    )
    follow = result.scalar_one_or_none()
    if follow:
        await db.delete(follow)
        await db.commit()
    return {"message": "Ne plus suivi", "is_following": False}


@router.get("/{user_id}/followers", response_model=list[UserPublic])
async def get_followers(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Liste des abonnés d'un utilisateur."""
    result = await db.execute(
        select(User)
        .join(Follow, Follow.follower_id == User.id)
        .where(Follow.following_id == user_id)
        .order_by(Follow.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.get("/{user_id}/following", response_model=list[UserPublic])
async def get_following(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Liste des abonnements d'un utilisateur."""
    result = await db.execute(
        select(User)
        .join(Follow, Follow.following_id == User.id)
        .where(Follow.follower_id == user_id)
        .order_by(Follow.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


# ── Block / Unblock ──────────────────────────────────────────────────────────

@router.post("/{user_id}/block")
async def block_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Bloquer un utilisateur — il ne peut plus voir ton profil, contenu, ni t'écrire."""
    from fastapi import HTTPException
    if user_id == current_user.id:
        raise HTTPException(400, "Vous ne pouvez pas vous bloquer vous-même")

    exists = await db.execute(
        select(UserBlock).where(
            UserBlock.blocker_id == current_user.id,
            UserBlock.blocked_id == user_id,
        )
    )
    if exists.scalar_one_or_none():
        return {"blocked": True, "message": "Déjà bloqué"}

    # Supprimer le follow dans les deux sens si existant
    for fid, tid in [(current_user.id, user_id), (user_id, current_user.id)]:
        follow = await db.execute(
            select(Follow).where(Follow.follower_id == fid, Follow.following_id == tid)
        )
        f = follow.scalar_one_or_none()
        if f:
            await db.delete(f)

    db.add(UserBlock(blocker_id=current_user.id, blocked_id=user_id))
    await db.commit()
    # Invalider le cache profil
    await cache_delete(f"profile:{user_id}:viewer:{current_user.id}")
    return {"blocked": True, "message": "Utilisateur bloqué"}


@router.delete("/{user_id}/block")
async def unblock_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Débloquer un utilisateur."""
    result = await db.execute(
        select(UserBlock).where(
            UserBlock.blocker_id == current_user.id,
            UserBlock.blocked_id == user_id,
        )
    )
    block = result.scalar_one_or_none()
    if block:
        await db.delete(block)
        await db.commit()
    return {"blocked": False, "message": "Utilisateur débloqué"}


@router.get("/me/blocked", response_model=list[UserPublic])
async def get_blocked_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Liste des utilisateurs que j'ai bloqués."""
    result = await db.execute(
        select(User)
        .join(UserBlock, UserBlock.blocked_id == User.id)
        .where(UserBlock.blocker_id == current_user.id)
        .order_by(UserBlock.created_at.desc())
    )
    return result.scalars().all()


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


# ── Vérification FoliX ────────────────────────────────────────────────────────

@router.get("/me/verification", response_model=VerificationStatusResponse)
async def get_verification_status(
    current_user: User = Depends(get_current_active_user),
):
    """Statut de vérification de l'utilisateur connecté."""
    return VerificationStatusResponse(
        status=current_user.verification_status,
        is_verified=current_user.is_verified,
        note=current_user.verification_note,
        requested_at=current_user.verification_requested_at,
        reviewed_at=current_user.verification_reviewed_at,
    )


@router.post("/me/verify-request", response_model=VerificationStatusResponse)
async def request_verification(
    payload: VerificationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Soumettre une demande de vérification FoliX."""
    from fastapi import HTTPException
    from datetime import datetime

    if current_user.is_verified:
        raise HTTPException(400, "Votre compte est déjà vérifié")
    if current_user.verification_status == VerificationStatus.pending:
        raise HTTPException(400, "Une demande est déjà en cours d'examen")

    current_user.verification_status = VerificationStatus.pending
    current_user.verification_note = payload.note
    current_user.verification_requested_at = datetime.utcnow()
    current_user.verification_reviewed_at = None
    await db.commit()
    await db.refresh(current_user)

    return VerificationStatusResponse(
        status=current_user.verification_status,
        is_verified=current_user.is_verified,
        note=current_user.verification_note,
        requested_at=current_user.verification_requested_at,
        reviewed_at=current_user.verification_reviewed_at,
    )


@router.patch("/{user_id}/verify", response_model=UserResponse)
async def review_verification(
    user_id: uuid.UUID,
    payload: VerificationReview,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """[Admin] Approuver ou rejeter une demande de vérification."""
    from fastapi import HTTPException
    from datetime import datetime

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")

    if payload.approved:
        user.is_verified = True
        user.verification_status = VerificationStatus.approved
    else:
        user.is_verified = False
        user.verification_status = VerificationStatus.rejected

    user.verification_note = payload.note
    user.verification_reviewed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(user)
    return user
