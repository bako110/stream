"""
Router messagerie directe — conversations & messages entre utilisateurs.
REST :
  GET  /conversations          → liste des conversations
  GET  /conversations/{uid}    → messages d'une conversation (paginé)
  POST /conversations/{uid}    → envoyer un message (HTTP + notif WS)
  PUT  /conversations/{uid}/read → marquer comme lus
  GET  /users/search           → rechercher des utilisateurs pour démarrer une conv

WebSocket :
  WS   /ws                     → connexion temps-réel par token JWT
"""
from fastapi import APIRouter, Depends, Query, HTTPException, status, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy import select, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
import json
import uuid
import logging

logger = logging.getLogger(__name__)

from app.db.mongo.session import get_mongo
from app.db.postgres.session import get_db
from app.deps import get_current_active_user
from app.db.postgres.models.user import User
from app.services.messages_service import (
    send_message,
    get_conversation,
    get_conversations,
    mark_conversation_read,
    edit_message,
    delete_message,
)
from app.services.user_service import UserService
from app.services.ws_manager import manager
from app.db.postgres.models.user_block import UserBlock
from app.db.postgres.models.device_token import DeviceToken
from app.utils.jwt import decode_access_token
from app.services.fcm_service import send_push_multicast

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class MessageCreate(BaseModel):
    content: str = Field("", max_length=2000)
    message_type: str = Field("text", pattern=r"^(text|voice|image|video|file)$")
    attachment_url: Optional[str] = None
    attachment_meta: Optional[dict] = None


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws")
async def ws_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db:    AsyncIOMotorDatabase = Depends(get_mongo),
    pg:    AsyncSession = Depends(get_db),
):
    """
    Connexion WebSocket authentifiée par token JWT passé en query param.
    Protocole JSON :
      Client → Server : { type: "ping" }  |  { type: "message", to: "<uid>", content: "<text>" }
      Server → Client : { type: "pong" }  |  { type: "message", ...msgDoc }  |  { type: "read", partner_id: "<uid>" }
    """
    # Valider le token
    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=4001)
        return

    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=4001)
        return

    await manager.connect(user_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

            elif msg_type == "subscribe_presence":
                target_id = data.get("user_id", "")
                if target_id and target_id != user_id:
                    # Ne pas exposer le statut si l'un a bloqué l'autre
                    try:
                        blk = await pg.execute(
                            select(UserBlock).where(
                                (UserBlock.blocker_id == uuid.UUID(user_id)) & (UserBlock.blocked_id == uuid.UUID(target_id)) |
                                (UserBlock.blocker_id == uuid.UUID(target_id)) & (UserBlock.blocked_id == uuid.UUID(user_id))
                            )
                        )
                        if blk.scalar_one_or_none():
                            # Répondre "hors ligne" sans s'abonner
                            await websocket.send_text(json.dumps({
                                "type": "presence",
                                "user_id": target_id,
                                "is_online": False,
                                "last_seen_at": None,
                            }))
                            continue
                    except Exception:
                        pass

                    manager.subscribe_presence(user_id, target_id)
                    is_online = manager.is_online(target_id)
                    last_seen = None
                    if not is_online:
                        try:
                            stmt = select(User.last_seen_at).where(User.id == uuid.UUID(target_id))
                            result = await pg.execute(stmt)
                            row = result.scalar_one_or_none()
                            if row:
                                last_seen = row.isoformat()
                        except Exception:
                            pass
                    await websocket.send_text(json.dumps({
                        "type": "presence",
                        "user_id": target_id,
                        "is_online": is_online,
                        "last_seen_at": last_seen,
                    }))

            elif msg_type == "unsubscribe_presence":
                target_id = data.get("user_id", "")
                if target_id:
                    manager.unsubscribe_presence(user_id, target_id)

            elif msg_type == "message":
                to      = data.get("to", "")
                content = (data.get("content") or "").strip()
                message_type = data.get("message_type", "text")
                attachment_url = data.get("attachment_url")
                attachment_meta = data.get("attachment_meta")
                if not to or to == user_id:
                    continue
                if message_type == "text" and not content:
                    continue
                # Vérifier blocage avant d'envoyer
                try:
                    blk = await pg.execute(
                        select(UserBlock).where(
                            (UserBlock.blocker_id == uuid.UUID(user_id)) & (UserBlock.blocked_id == uuid.UUID(to)) |
                            (UserBlock.blocker_id == uuid.UUID(to)) & (UserBlock.blocked_id == uuid.UUID(user_id))
                        )
                    )
                    if blk.scalar_one_or_none():
                        await websocket.send_text(json.dumps({"type": "error", "detail": "blocked"}))
                        continue
                except Exception:
                    pass
                # Persister
                msg = await send_message(
                    db,
                    sender_id=user_id,
                    receiver_id=to,
                    content=content,
                    message_type=message_type,
                    attachment_url=attachment_url,
                    attachment_meta=attachment_meta,
                )
                payload_out = {"type": "message", **msg}
                # Notifier les deux participants
                await manager.broadcast_to_pair(user_id, to, payload_out)
                # FCM — toujours envoyé (background/quit: Notifee affiche; foreground: WS toast gère)
                try:
                    sender_name = "Nouveau message"
                    try:
                        from app.db.postgres.models.user import User as UserModel
                        sender = await pg.get(UserModel, uuid.UUID(user_id))
                        if sender:
                            sender_name = sender.display_name or sender.first_name or sender.username or "Nouveau message"
                    except Exception:
                        pass
                    tokens_res = await pg.execute(select(DeviceToken.token).where(DeviceToken.user_id == uuid.UUID(to)))
                    tokens = tokens_res.scalars().all()
                    if tokens:
                        await send_push_multicast(
                            list(tokens), sender_name,
                            content[:100] if content else "Nouveau message",
                            {
                                "type":        "message",
                                "sender_id":   user_id,
                                "sender_name": sender_name,
                            },
                        )
                except Exception:
                    pass

            elif msg_type == "read":
                partner_id = data.get("partner_id", "")
                if partner_id:
                    await mark_conversation_read(db, reader_id=user_id, sender_id=partner_id)
                    # Notifier l'expéditeur que ses messages ont été lus
                    await manager.send_to_user(partner_id, {"type": "read", "partner_id": user_id})

            # ── Call signaling (WebRTC) ──────────────────────────────
            elif msg_type in ("call_offer", "call_answer", "call_ice", "call_hangup"):
                to = data.get("to", "")
                if not to or to == user_id:
                    continue
                # For call_offer, include caller's display name
                forward = {**data, "from": user_id}
                if msg_type == "call_offer":
                    try:
                        from app.db.postgres.models.user import User as UserModel
                        caller = await pg.get(UserModel, uuid.UUID(user_id))
                        if caller:
                            forward["from_name"]   = caller.display_name or caller.first_name or caller.username or "Inconnu"
                            forward["from_avatar"] = caller.avatar_url
                        else:
                            forward["from_name"]   = "Inconnu"
                            forward["from_avatar"] = None
                    except Exception:
                        forward["from_name"]   = "Inconnu"
                        forward["from_avatar"] = None
                await manager.send_to_user(to, forward)
                # FCM si destinataire hors ligne (appel entrant)
                if msg_type == "call_offer" and not manager.is_online(to):
                    try:
                        tokens_res = await pg.execute(select(DeviceToken.token).where(DeviceToken.user_id == uuid.UUID(to)))
                        tokens = tokens_res.scalars().all()
                        if tokens:
                            call_type = data.get("call_type", "voice")
                            caller_name = forward.get("from_name", "Appel entrant")
                            body_text = "Appel vidéo entrant" if call_type == "video" else "Appel vocal entrant"
                            await send_push_multicast(
                                list(tokens), caller_name, body_text,
                                {
                                    "type":         "call_offer",
                                    "call_type":    call_type,
                                    "from":         user_id,
                                    "caller_name":  caller_name,
                                    "caller_avatar": forward.get("from_avatar") or "",
                                },
                            )
                    except Exception:
                        pass

            # ── Edit message ─────────────────────────────────────────
            elif msg_type == "edit_message":
                message_id = data.get("message_id", "")
                new_content = (data.get("content") or "").strip()
                if not message_id or not new_content:
                    continue
                updated = await edit_message(db, message_id, user_id, new_content)
                if updated:
                    partner = updated.get("receiver_id") if updated.get("sender_id") == user_id else updated.get("sender_id")
                    await manager.broadcast_to_pair(user_id, partner, {
                        "type": "message_edited",
                        "message_id": updated["id"],
                        "content": updated["content"],
                        "edited_at": updated.get("edited_at").isoformat() if updated.get("edited_at") else None,
                    })

            # ── Delete message ───────────────────────────────────────
            elif msg_type == "delete_message":
                message_id = data.get("message_id", "")
                if not message_id:
                    continue
                deleted = await delete_message(db, message_id, user_id)
                if deleted:
                    partner = deleted.get("receiver_id") if deleted.get("sender_id") == user_id else deleted.get("sender_id")
                    await manager.broadcast_to_pair(user_id, partner, {
                        "type": "message_deleted",
                        "message_id": deleted["id"],
                    })

            # ── Comment via WS — handled by REST /social/comments ────
            # WS comment creation was removed: opening a new DB session inside
            # a long-lived WebSocket caused pool-connection-closed errors.
            # The frontend uses POST /api/v1/social/comments (REST) instead.
            elif msg_type == "comment":
                pass

    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(user_id, websocket)
        # Update last_seen_at if user has no more connections
        if not manager.is_online(user_id):
            try:
                stmt = (
                    update(User)
                    .where(User.id == uuid.UUID(user_id))
                    .values(last_seen_at=datetime.now(timezone.utc))
                )
                await pg.execute(stmt)
                await pg.commit()
            except Exception:
                pass


# ── Recherche d'utilisateurs (pour démarrer une conversation) ─────────────────

@router.get("/users/search")
async def search_users(
    q:            str = Query(..., min_length=1, max_length=100),
    limit:        int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_active_user),
    pg:           AsyncSession = Depends(get_db),
):
    """Recherche des utilisateurs par username ou full_name pour initier une conversation."""
    like = f"%{q.lower()}%"

    # Construire les conditions de recherche en ignorant les colonnes NULL
    from sqlalchemy import func, cast, String, text
    search_conditions = or_(
        User.username.ilike(like),
        User.email.ilike(like),
        User.display_name.ilike(like),
        User.first_name.ilike(like),
        User.last_name.ilike(like),
    )

    # Exclure les bloqués dans les deux sens
    blocked_ids_q = select(UserBlock.blocked_id).where(UserBlock.blocker_id == current_user.id)
    blocker_ids_q = select(UserBlock.blocker_id).where(UserBlock.blocked_id == current_user.id)

    stmt = (
        select(User)
        .where(
            User.id != current_user.id,
            User.id.not_in(blocked_ids_q),
            User.id.not_in(blocker_ids_q),
            search_conditions,
        )
        .limit(limit)
    )

    result = await pg.execute(stmt)
    users = result.scalars().all()

    import logging
    logging.getLogger(__name__).info(
        "search_users q=%r like=%r current_user=%s found=%d",
        q, like, current_user.id, len(users),
    )

    def build_full_name(u: User) -> str | None:
        parts = [p for p in [u.first_name, u.last_name] if p]
        return " ".join(parts) if parts else u.display_name

    def display(u: User) -> str:
        """Nom affiché : display_name > first+last > username > début email."""
        return (
            u.display_name
            or build_full_name(u)
            or u.username
            or u.email.split("@")[0]
        )

    return [
        {
            "id":         str(u.id),
            "username":   u.username or u.email.split("@")[0],
            "full_name":  build_full_name(u) or u.display_name,
            "display":    display(u),
            "avatar_url": u.avatar_url,
        }
        for u in users
    ]


# ── Routes REST ───────────────────────────────────────────────────────────────

@router.get("/conversations")
async def list_conversations(
    current_user: User = Depends(get_current_active_user),
    db:           AsyncIOMotorDatabase = Depends(get_mongo),
    pg:           AsyncSession = Depends(get_db),
):
    """Retourne toutes les conversations de l'utilisateur connecté, enrichies avec le profil du partenaire."""
    convs = await get_conversations(db, str(current_user.id))

    # Récupérer les IDs bloqués dans les deux sens
    blocked_res = await pg.execute(
        select(UserBlock.blocked_id).where(UserBlock.blocker_id == current_user.id)
    )
    blocker_res = await pg.execute(
        select(UserBlock.blocker_id).where(UserBlock.blocked_id == current_user.id)
    )
    hidden_ids = {
        str(r) for r in blocked_res.scalars().all()
    } | {
        str(r) for r in blocker_res.scalars().all()
    }

    result = []
    for c in convs:
        partner_id = c.get("partner_id")
        # Masquer les conversations avec des utilisateurs bloqués
        if partner_id in hidden_ids:
            continue
        partner_info: dict = {}
        try:
            partner = await UserService.get_by_id(uuid.UUID(partner_id), pg)
            online = manager.is_online(partner_id)
            partner_info = {
                "id":         str(partner.id),
                "username":   partner.username or str(partner.id)[:8],
                "full_name":  " ".join(p for p in [partner.first_name, partner.last_name] if p) or partner.display_name,
                "avatar_url": partner.avatar_url,
                "is_online":  online,
                "last_seen_at": partner.last_seen_at.isoformat() if partner.last_seen_at else None,
            }
        except Exception:
            partner_info = {"id": partner_id, "username": partner_id}

        result.append({**c, "partner": partner_info})

    return result


@router.get("/conversations/{partner_id}")
async def get_messages(
    partner_id: str,
    page:  int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db:           AsyncIOMotorDatabase = Depends(get_mongo),
):
    return await get_conversation(
        db,
        user_id=str(current_user.id),
        other_id=partner_id,
        page=page,
        limit=limit,
    )


@router.post("/conversations/{partner_id}", status_code=201)
async def send_msg(
    partner_id: str,
    body: MessageCreate,
    current_user: User = Depends(get_current_active_user),
    db:           AsyncIOMotorDatabase = Depends(get_mongo),
    pg:           AsyncSession = Depends(get_db),
):
    try:
        receiver = await UserService.get_by_id(uuid.UUID(partner_id), pg)
    except Exception:
        receiver = None
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")
    if str(current_user.id) == partner_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Impossible de s'envoyer un message")

    # Vérifier blocage dans les deux sens
    block_check = await pg.execute(
        select(UserBlock).where(
            (UserBlock.blocker_id == current_user.id) & (UserBlock.blocked_id == uuid.UUID(partner_id)) |
            (UserBlock.blocker_id == uuid.UUID(partner_id)) & (UserBlock.blocked_id == current_user.id)
        )
    )
    if block_check.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Impossible d'envoyer un message à cet utilisateur")

    msg = await send_message(
        db,
        sender_id=str(current_user.id),
        receiver_id=partner_id,
        content=body.content,
        message_type=body.message_type,
        attachment_url=body.attachment_url,
        attachment_meta=body.attachment_meta,
    )
    # Notifier via WebSocket si le destinataire est connecté
    await manager.send_to_user(partner_id, {"type": "message", **msg})
    # FCM — toujours envoyé
    try:
        sender_name = current_user.display_name or current_user.first_name or current_user.username or "Nouveau message"
        tokens_res = await pg.execute(select(DeviceToken.token).where(DeviceToken.user_id == uuid.UUID(partner_id)))
        tokens = tokens_res.scalars().all()
        if tokens:
            await send_push_multicast(
                list(tokens), sender_name,
                body.content[:100] if body.content else "Nouveau message",
                {
                    "type":        "message",
                    "sender_id":   str(current_user.id),
                    "sender_name": sender_name,
                },
            )
    except Exception:
        pass
    return msg


@router.put("/conversations/{partner_id}/read", status_code=204)
async def mark_read(
    partner_id: str,
    current_user: User = Depends(get_current_active_user),
    db:           AsyncIOMotorDatabase = Depends(get_mongo),
):
    await mark_conversation_read(db, reader_id=str(current_user.id), sender_id=partner_id)
    # Notifier l'expéditeur que ses messages ont été lus
    await manager.send_to_user(partner_id, {"type": "read", "partner_id": str(current_user.id)})


class MessageEdit(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


@router.patch("/messages/{message_id}")
async def patch_message(
    message_id: str,
    body: MessageEdit,
    current_user: User = Depends(get_current_active_user),
    db:           AsyncIOMotorDatabase = Depends(get_mongo),
):
    updated = await edit_message(db, message_id, str(current_user.id), body.content)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message introuvable ou non autorisé")
    partner = updated["receiver_id"] if updated["sender_id"] == str(current_user.id) else updated["sender_id"]
    await manager.broadcast_to_pair(str(current_user.id), partner, {
        "type": "message_edited",
        "message_id": updated["id"],
        "content": updated["content"],
        "edited_at": updated.get("edited_at").isoformat() if updated.get("edited_at") else None,
    })
    return updated


@router.delete("/messages/{message_id}", status_code=204)
async def remove_message(
    message_id: str,
    current_user: User = Depends(get_current_active_user),
    db:           AsyncIOMotorDatabase = Depends(get_mongo),
):
    deleted = await delete_message(db, message_id, str(current_user.id))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message introuvable ou non autorisé")
    partner = deleted["receiver_id"] if deleted["sender_id"] == str(current_user.id) else deleted["sender_id"]
    await manager.broadcast_to_pair(str(current_user.id), partner, {
        "type": "message_deleted",
        "message_id": deleted["id"],
    })

