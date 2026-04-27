"""
LiveKit service — gestion des rooms + tokens pour les concerts live.
SDK : livekit-api 0.7.x — LiveKitAPI sans context manager, appel direct + aclose().
"""
import time
from datetime import timedelta
from livekit import api
from app.config import settings


def _make_client() -> api.LiveKitAPI:
    return api.LiveKitAPI(
        settings.LIVEKIT_URL,
        settings.LIVEKIT_API_KEY,
        settings.LIVEKIT_API_SECRET,
    )


class LiveKitService:

    @staticmethod
    async def create_room(concert_id: str, *, max_participants: int = 0) -> dict:
        lk = _make_client()
        try:
            room = await lk.room.create_room(
                api.CreateRoomRequest(
                    name=f"concert-{concert_id}",
                    empty_timeout=300,
                    max_participants=max_participants or 0,
                )
            )
            return {"room_name": room.name, "sid": room.sid}
        finally:
            await lk.aclose()

    @staticmethod
    async def delete_room(concert_id: str) -> None:
        lk = _make_client()
        try:
            await lk.room.delete_room(
                api.DeleteRoomRequest(room=f"concert-{concert_id}")
            )
        finally:
            await lk.aclose()

    @staticmethod
    async def list_participants(concert_id: str) -> int:
        lk = _make_client()
        try:
            resp = await lk.room.list_participants(
                api.ListParticipantsRequest(room=f"concert-{concert_id}")
            )
            return len(resp.participants)
        finally:
            await lk.aclose()

    @staticmethod
    def generate_token(
        concert_id: str,
        user_id: str,
        username: str,
        *,
        is_publisher: bool = False,
        ttl: int = 6 * 3600,
    ) -> str:
        room_name = f"concert-{concert_id}"

        grant = api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=is_publisher,
            can_subscribe=True,
            can_publish_data=is_publisher,
        )

        token = (
            api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
            .with_identity(user_id)
            .with_name(username)
            .with_ttl(timedelta(seconds=ttl))
            .with_grants(grant)
        )

        return token.to_jwt()
