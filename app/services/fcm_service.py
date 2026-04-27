"""
Firebase Cloud Messaging — push notifications for offline users.
Initialises firebase-admin once using the service account key file.
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_app = None


def _get_app():
    global _app
    if _app is not None:
        return _app
    try:
        import firebase_admin
        from firebase_admin import credentials

        base = Path(__file__).parent.parent.parent
        # Chercher la clé Firebase — plusieurs noms possibles pour éviter les problèmes d'encodage
        candidates = [
            base / "firebase-service-account.json",
            base / "clé_prive.json",
            base / "cle_prive.json",
            base / "service-account.json",
            Path(__file__).parent.parent / "firebase-service-account.json",
            Path(__file__).parent.parent / "clé_prive.json",
            Path(__file__).parent.parent / "cle_prive.json",
        ]
        # Aussi chercher via variable d'environnement
        env_path = os.environ.get("FIREBASE_KEY_PATH")
        if env_path:
            candidates.insert(0, Path(env_path))

        key_path = next((p for p in candidates if p.exists()), None)
        if key_path is None:
            logger.warning("FCM: service account key not found, push disabled")
            return None

        cred = credentials.Certificate(str(key_path))
        _app = firebase_admin.initialize_app(cred)
        logger.info("FCM: firebase-admin initialised")
    except Exception as e:
        logger.error("FCM init error: %s", e)
        _app = None
    return _app


def _build_android(channel_id: str = "messages") -> "messaging.AndroidConfig":
    """
    Data-only message with high priority — passes through setBackgroundMessageHandler
    so Notifee can display it with the correct channel (sound + vibration).
    No notification block = Android does NOT intercept it.
    """
    from firebase_admin import messaging
    return messaging.AndroidConfig(
        priority="high",
        # No AndroidNotification here — Notifee handles display
    )


def _build_apns(title: str = "", body: str = "") -> "messaging.APNSConfig":
    from firebase_admin import messaging
    return messaging.APNSConfig(
        headers={
            "apns-priority":   "10",
            "apns-push-type":  "alert",
        },
        payload=messaging.APNSPayload(
            aps=messaging.Aps(
                alert=messaging.ApsAlert(title=title, body=body) if title else None,
                sound="default",
                content_available=True,
                badge=1,
            )
        ),
    )


def _send_sync(tokens: list[str], title: str, body: str, data: dict) -> int:
    """Blocking FCM send — data-only (Android) + alert (iOS) so Notifee handles display with sound."""
    app = _get_app()
    if app is None:
        return 0
    try:
        from firebase_admin import messaging
        # Pass title/body inside data — Notifee reads them in the background handler (Android)
        payload_data = {
            "title": title,
            "body":  body,
            **{k: str(v) for k, v in data.items()},
        }
        if len(tokens) == 1:
            msg = messaging.Message(
                data=payload_data,
                token=tokens[0],
                android=_build_android(),
                apns=_build_apns(title, body),
            )
            messaging.send(msg, app=app)
            return 1
        else:
            msg = messaging.MulticastMessage(
                data=payload_data,
                tokens=tokens,
                android=_build_android(),
                apns=_build_apns(title, body),
            )
            resp = messaging.send_each_for_multicast(msg, app=app)
            return resp.success_count
    except Exception as e:
        logger.warning("FCM send error: %s", e)
        return 0


async def send_push(
    token: str,
    title: str,
    body: str,
    data: dict | None = None,
) -> bool:
    import asyncio
    count = await asyncio.get_event_loop().run_in_executor(
        None, _send_sync, [token], title, body, data or {}
    )
    return count > 0


async def send_push_multicast(
    tokens: list[str],
    title: str,
    body: str,
    data: dict | None = None,
) -> int:
    if not tokens:
        return 0
    import asyncio
    return await asyncio.get_event_loop().run_in_executor(
        None, _send_sync, tokens, title, body, data or {}
    )
