"""
WebSocket connection manager for real-time messaging.
Each connected user is stored by user_id.
When a message is sent, the receiver is notified if connected.

Multi-instance support via Redis Pub/Sub:
  send_to_user() publishes to Redis channel "ws:user:{user_id}"
  Each instance subscribes and delivers to local sockets.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

import redis.asyncio as aioredis
from fastapi import WebSocket

logger = logging.getLogger(__name__)

# ── Redis relay channel prefix ────────────────────────────────────────────────
_CHANNEL_USER = "ws:user:"
_CHANNEL_COMMUNITY = "ws:community:"
_CHANNEL_BROADCAST = "ws:broadcast"

_redis_pub: Optional[aioredis.Redis] = None
_relay_task: Optional[asyncio.Task] = None


async def init_redis_relay(redis_url: str) -> None:
    """Start the Redis Pub/Sub relay — call once at app startup."""
    global _redis_pub, _relay_task
    if _redis_pub is not None:
        return
    try:
        _redis_pub = aioredis.from_url(
            redis_url, encoding="utf-8", decode_responses=True,
            socket_connect_timeout=3, socket_timeout=3,
        )
        await _redis_pub.ping()
        _relay_task = asyncio.create_task(_subscribe_loop(redis_url))
        print("   WS Redis relay : OK")
    except Exception as e:
        print(f"   WS Redis relay : indisponible ({e}), mode local uniquement")
        _redis_pub = None


async def stop_redis_relay() -> None:
    global _relay_task, _redis_pub
    if _relay_task:
        _relay_task.cancel()
        _relay_task = None
    if _redis_pub:
        await _redis_pub.aclose()
        _redis_pub = None


async def _subscribe_loop(redis_url: str) -> None:
    """Background task: subscribe to Redis channels and deliver to local sockets."""
    sub_redis = aioredis.from_url(
        redis_url, encoding="utf-8", decode_responses=True,
        socket_connect_timeout=3,
    )
    pubsub = sub_redis.pubsub()
    await pubsub.psubscribe(f"{_CHANNEL_USER}*", f"{_CHANNEL_COMMUNITY}*", _CHANNEL_BROADCAST)
    try:
        async for msg in pubsub.listen():
            if msg["type"] != "pmessage":
                continue
            channel: str = msg["channel"]
            data = json.loads(msg["data"])
            origin = data.pop("_origin", None)
            # Skip messages we published ourselves
            if origin == id(manager):
                continue
            if channel.startswith(_CHANNEL_USER):
                user_id = channel[len(_CHANNEL_USER):]
                await manager._local_send(user_id, data)
            elif channel.startswith(_CHANNEL_COMMUNITY):
                community_id = channel[len(_CHANNEL_COMMUNITY):]
                exclude = data.pop("_exclude_user", None)
                await community_manager._local_broadcast(community_id, data, exclude)
            elif channel == _CHANNEL_BROADCAST:
                await manager._local_broadcast_all(data)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.punsubscribe()
        await sub_redis.aclose()


async def _redis_publish(channel: str, payload: dict) -> None:
    """Publish payload to Redis if available."""
    if _redis_pub is None:
        return
    try:
        text = ConnectionManager._serialize({**payload, "_origin": id(manager)})
        await _redis_pub.publish(channel, text)
    except Exception:
        pass


class ConnectionManager:
    def __init__(self):
        self._connections: Dict[str, list[WebSocket]] = {}
        self._presence_subscribers: Dict[str, set[str]] = {}

    @staticmethod
    def _serialize(payload: dict) -> str:
        """JSON-serialize with automatic datetime → ISO string conversion."""
        def _default(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
        return json.dumps(payload, default=_default)

    async def connect(self, user_id: str, ws: WebSocket) -> None:
        was_offline = not self._connections.get(user_id)
        await ws.accept()
        self._connections.setdefault(user_id, []).append(ws)
        logger.debug("WS connected: user=%s total_sockets=%d", user_id, len(self._connections[user_id]))
        if was_offline:
            await self._broadcast_presence(user_id, online=True)

    async def disconnect(self, user_id: str, ws: WebSocket) -> None:
        bucket = self._connections.get(user_id, [])
        if ws in bucket:
            bucket.remove(ws)
        if not bucket:
            self._connections.pop(user_id, None)
            await self._broadcast_presence(user_id, online=False)
        logger.debug("WS disconnected: user=%s", user_id)

    def is_online(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))

    async def _local_send(self, user_id: str, payload: dict) -> None:
        """Send to local sockets only (no Redis publish)."""
        sockets = list(self._connections.get(user_id, []))
        if not sockets:
            return
        text = self._serialize(payload)
        dead: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(user_id, ws)

    async def send_to_user(self, user_id: str, payload: dict) -> None:
        """Send a JSON payload to all sockets of a given user (local + other instances via Redis)."""
        await self._local_send(user_id, payload)
        await _redis_publish(f"{_CHANNEL_USER}{user_id}", payload)

    async def broadcast_to_pair(self, user_a: str, user_b: str, payload: dict) -> None:
        """Notify both participants of a conversation."""
        await self.send_to_user(user_a, payload)
        await self.send_to_user(user_b, payload)

    async def _local_broadcast_all(self, payload: dict) -> None:
        """Broadcast to all local sockets."""
        text = self._serialize(payload)
        dead: list[tuple[str, WebSocket]] = []
        for uid, sockets in list(self._connections.items()):
            for ws in list(sockets):
                try:
                    await ws.send_text(text)
                except Exception:
                    dead.append((uid, ws))
        for uid, ws in dead:
            await self.disconnect(uid, ws)

    async def broadcast_all(self, payload: dict) -> None:
        """Broadcast a payload to ALL connected users (local + other instances)."""
        await self._local_broadcast_all(payload)
        await _redis_publish(_CHANNEL_BROADCAST, payload)

    def subscribe_presence(self, subscriber_id: str, target_id: str) -> None:
        self._presence_subscribers.setdefault(target_id, set()).add(subscriber_id)

    def unsubscribe_presence(self, subscriber_id: str, target_id: str) -> None:
        subs = self._presence_subscribers.get(target_id)
        if subs:
            subs.discard(subscriber_id)

    async def _broadcast_presence(self, user_id: str, online: bool) -> None:
        subs = self._presence_subscribers.get(user_id, set())
        payload = {
            "type": "presence",
            "user_id": user_id,
            "is_online": online,
            "last_seen_at": datetime.now(timezone.utc).isoformat() if not online else None,
        }
        for sub_id in list(subs):
            if self.is_online(sub_id):
                await self.send_to_user(sub_id, payload)


class CommunityConnectionManager:
    """
    Gère les connexions WebSocket groupées par community_id.
    """

    def __init__(self):
        self._rooms: Dict[str, Dict[str, list[WebSocket]]] = {}

    async def connect(self, community_id: str, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        room = self._rooms.setdefault(community_id, {})
        room.setdefault(user_id, []).append(ws)
        logger.debug("Community WS connected: community=%s user=%s", community_id, user_id)

    def disconnect(self, community_id: str, user_id: str, ws: WebSocket) -> None:
        room = self._rooms.get(community_id, {})
        bucket = room.get(user_id, [])
        if ws in bucket:
            bucket.remove(ws)
        if not bucket:
            room.pop(user_id, None)
        if not room:
            self._rooms.pop(community_id, None)
        logger.debug("Community WS disconnected: community=%s user=%s", community_id, user_id)

    def get_online_count(self, community_id: str) -> int:
        return len(self._rooms.get(community_id, {}))

    async def _local_broadcast(self, community_id: str, payload: dict, exclude_user: str | None = None) -> None:
        """Broadcast to local sockets in a community room."""
        room = self._rooms.get(community_id, {})
        def _default(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
        text = json.dumps(payload, default=_default)
        dead: list[tuple[str, WebSocket]] = []
        for uid, sockets in room.items():
            if uid == exclude_user:
                continue
            for ws in list(sockets):
                try:
                    await ws.send_text(text)
                except Exception:
                    dead.append((uid, ws))
        for uid, ws in dead:
            self.disconnect(community_id, uid, ws)

    async def broadcast(self, community_id: str, payload: dict, exclude_user: str | None = None) -> None:
        """Broadcast to all connected users in a community (local + other instances)."""
        await self._local_broadcast(community_id, payload, exclude_user)
        await _redis_publish(
            f"{_CHANNEL_COMMUNITY}{community_id}",
            {**payload, "_exclude_user": exclude_user},
        )


# Singletons — shared across the entire app process
manager = ConnectionManager()
community_manager = CommunityConnectionManager()
