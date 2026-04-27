from fastapi import APIRouter, Depends, Query, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import json
import uuid as _uuid

from app.db.postgres.session import get_db
from app.deps import get_current_user
from app.services.community_service import CommunityService
from app.services.ws_manager import community_manager
from app.utils.jwt import decode_access_token
from app.utils.cache import cache_get, cache_set, cache_invalidate_prefix

router = APIRouter(tags=["Communities"])


class CommunityCreate(BaseModel):
    name: str
    description: str | None = None
    is_private: bool = False
    avatar_url: str | None = None
    banner_url: str | None = None


def _serialize(c):
    return {
        "id": str(c.id),
        "name": c.name,
        "description": c.description,
        "avatar_url": c.avatar_url,
        "banner_url": c.banner_url,
        "is_private": c.is_private,
        "members_count": c.members_count,
        "creator_id": str(c.creator_id),
        "creator": {
            "id": str(c.creator.id),
            "username": c.creator.username,
            "display_name": c.creator.display_name,
            "avatar_url": c.creator.avatar_url,
        } if c.creator else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.post("")
async def create_community(body: CommunityCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    community = await CommunityService.create(
        name=body.name, creator_id=user.id, db=db,
        description=body.description, is_private=body.is_private,
        avatar_url=body.avatar_url, banner_url=body.banner_url,
    )
    await cache_invalidate_prefix("communities:list:")
    return _serialize(community)


@router.get("")
async def list_communities(
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    ck = f"communities:list:p{page}:l{limit}"
    if (cached := await cache_get(ck)) is not None:
        return cached
    communities = await CommunityService.list_all(db, page=page, limit=limit)
    serialized = [_serialize(c) for c in communities]
    await cache_set(ck, serialized, ttl=120)
    return serialized


@router.get("/me")
async def my_communities(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    communities = await CommunityService.get_my_communities(user.id, db)
    return [_serialize(c) for c in communities]


@router.get("/{community_id}")
async def get_community(community_id: str, db: AsyncSession = Depends(get_db)):
    ck = f"community:{community_id}"
    if (cached := await cache_get(ck)) is not None:
        return cached
    c = await CommunityService.get_by_id(_uuid.UUID(community_id), db)
    if not c:
        raise HTTPException(status_code=404, detail="Community not found")
    serialized = _serialize(c)
    await cache_set(ck, serialized, ttl=120)
    return serialized


@router.post("/{community_id}/join")
async def join_community(community_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    joined = await CommunityService.join(_uuid.UUID(community_id), user.id, db)
    await cache_invalidate_prefix(f"community:{community_id}")
    await cache_invalidate_prefix("communities:list:")
    return {"joined": joined}


@router.post("/{community_id}/leave")
async def leave_community(community_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    left = await CommunityService.leave(_uuid.UUID(community_id), user.id, db)
    await cache_invalidate_prefix(f"community:{community_id}")
    await cache_invalidate_prefix("communities:list:")
    return {"left": left}


@router.get("/{community_id}/members")
async def get_members(community_id: str, db: AsyncSession = Depends(get_db)):
    members = await CommunityService.get_members(_uuid.UUID(community_id), db)
    return [
        {
            "id": str(m.id),
            "user_id": str(m.user_id),
            "username": m.user.username if m.user else None,
            "display_name": m.user.display_name if m.user else None,
            "avatar_url": m.user.avatar_url if m.user else None,
            "role": m.role,
            "joined_at": m.joined_at.isoformat() if m.joined_at else None,
        }
        for m in members
    ]


@router.get("/discover/list")
async def discover_communities(
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    communities = await CommunityService.discover(user.id, db, page=page, limit=limit)
    return [_serialize(c) for c in communities]


@router.post("/{community_id}/block/{user_id}")
async def block_member(community_id: str, user_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    blocked = await CommunityService.block_member(
        _uuid.UUID(community_id), _uuid.UUID(user_id), user.id, db,
    )
    if not blocked:
        raise HTTPException(status_code=403, detail="Cannot block this member")
    return {"blocked": True}


@router.delete("/{community_id}/block/{user_id}")
async def unblock_member(community_id: str, user_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    unblocked = await CommunityService.unblock_member(
        _uuid.UUID(community_id), _uuid.UUID(user_id), user.id, db,
    )
    if not unblocked:
        raise HTTPException(status_code=403, detail="Cannot unblock this member")
    return {"unblocked": True}


@router.get("/{community_id}/blocked")
async def get_blocked_members(community_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Only admin/mod can see blocked list
    role = await CommunityService.get_member_role(_uuid.UUID(community_id), user.id, db)
    if role not in ("admin", "moderator"):
        raise HTTPException(status_code=403, detail="Not authorized")
    blocked = await CommunityService.get_blocked(_uuid.UUID(community_id), db)
    return [
        {
            "id": str(b.id),
            "user_id": str(b.user_id),
            "username": b.user.username if b.user else None,
            "display_name": b.user.display_name if b.user else None,
            "avatar_url": b.user.avatar_url if b.user else None,
            "blocked_at": b.blocked_at.isoformat() if b.blocked_at else None,
            "reason": b.reason,
        }
        for b in blocked
    ]


@router.get("/{community_id}/role")
async def get_my_role(community_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    role = await CommunityService.get_member_role(_uuid.UUID(community_id), user.id, db)
    return {"role": role}


class MessageCreate(BaseModel):
    content: str


class MessageEdit(BaseModel):
    content: str


def _serialize_msg(m):
    return {
        "id": str(m.id),
        "community_id": str(m.community_id),
        "sender_id": str(m.sender_id),
        "sender_username": m.sender.username if m.sender else None,
        "sender_display_name": m.sender.display_name if m.sender else None,
        "sender_avatar_url": m.sender.avatar_url if m.sender else None,
        "content": m.content,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "edited_at": m.edited_at.isoformat() if m.edited_at else None,
    }


@router.get("/{community_id}/messages")
async def get_community_messages(
    community_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    messages = await CommunityService.get_messages(_uuid.UUID(community_id), db, page=page, limit=limit)
    return [_serialize_msg(m) for m in messages]


@router.post("/{community_id}/messages")
async def send_community_message(
    community_id: str,
    body: MessageCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        msg = await CommunityService.send_message(
            _uuid.UUID(community_id), user.id, body.content, db,
        )
        payload = {"type": "community_message", **_serialize_msg(msg)}
        await community_manager.broadcast(community_id, payload)
        return _serialize_msg(msg)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.put("/{community_id}/messages/{message_id}")
async def edit_community_message(
    community_id: str,
    message_id: str,
    body: MessageEdit,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await CommunityService.edit_message(
        _uuid.UUID(message_id), user.id, body.content, db,
    )
    if not msg:
        raise HTTPException(status_code=403, detail="Cannot edit this message")
    payload = {"type": "community_message_edited", **_serialize_msg(msg)}
    await community_manager.broadcast(community_id, payload)
    return _serialize_msg(msg)


@router.delete("/{community_id}/messages/{message_id}", status_code=204)
async def delete_community_message(
    community_id: str,
    message_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted_cid = await CommunityService.delete_message(
        _uuid.UUID(message_id), user.id, db,
    )
    if not deleted_cid:
        raise HTTPException(status_code=403, detail="Cannot delete this message")
    payload = {"type": "community_message_deleted", "id": message_id, "community_id": community_id}
    await community_manager.broadcast(community_id, payload)


# ── WebSocket communautaire ──────────────────────────────────────────────────

@router.websocket("/{community_id}/ws")
async def community_ws_endpoint(
    websocket: WebSocket,
    community_id: str,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Connexion WebSocket pour le chat communautaire.
    Protocole JSON :
      Client → Server : { type: "ping" } | { type: "message", content: "<text>" }
      Server → Client : { type: "pong" } | { type: "community_message", ...msg }
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

    # Vérifier que l'utilisateur est membre
    cid = _uuid.UUID(community_id)
    is_member = await CommunityService.is_member(cid, _uuid.UUID(user_id), db)
    if not is_member:
        await websocket.close(code=4003)
        return

    await community_manager.connect(community_id, user_id, websocket)
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

            elif msg_type == "message":
                content = (data.get("content") or "").strip()
                if not content:
                    continue
                try:
                    msg = await CommunityService.send_message(cid, _uuid.UUID(user_id), content, db)
                    out = {"type": "community_message", **_serialize_msg(msg)}
                    await community_manager.broadcast(community_id, out)
                except ValueError:
                    await websocket.send_text(json.dumps({"type": "error", "detail": "Cannot send message"}))

            elif msg_type == "edit":
                msg_id = data.get("message_id", "")
                content = (data.get("content") or "").strip()
                if not msg_id or not content:
                    continue
                edited = await CommunityService.edit_message(_uuid.UUID(msg_id), _uuid.UUID(user_id), content, db)
                if edited:
                    out = {"type": "community_message_edited", **_serialize_msg(edited)}
                    await community_manager.broadcast(community_id, out)
                else:
                    await websocket.send_text(json.dumps({"type": "error", "detail": "Cannot edit"}))

            elif msg_type == "delete":
                msg_id = data.get("message_id", "")
                if not msg_id:
                    continue
                deleted_cid = await CommunityService.delete_message(_uuid.UUID(msg_id), _uuid.UUID(user_id), db)
                if deleted_cid:
                    out = {"type": "community_message_deleted", "id": msg_id, "community_id": community_id}
                    await community_manager.broadcast(community_id, out)
                else:
                    await websocket.send_text(json.dumps({"type": "error", "detail": "Cannot delete"}))

    except WebSocketDisconnect:
        pass
    finally:
        community_manager.disconnect(community_id, user_id, websocket)
