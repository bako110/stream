"""
Service Cloudinary — upload d'images (thumbnail, banner, galerie).

Chaque fichier est uploadé directement depuis le backend via l'API REST
Cloudinary en mode authenticated upload. Le frontend envoie les fichiers
en multipart/form-data.

Dossiers Cloudinary :
  folix/concerts/   → thumbnails + banners concerts
  folix/events/     → thumbnails + banners événements
  folix/avatars/    → avatars utilisateurs (usage futur)
"""
import hashlib
import hmac
import time
import httpx
from fastapi import HTTPException, UploadFile

from app.config import settings

CLOUDINARY_UPLOAD_URL = (
    f"https://api.cloudinary.com/v1_1/{settings.CLOUDINARY_CLOUD_NAME}/image/upload"
)
CLOUDINARY_VIDEO_UPLOAD_URL = (
    f"https://api.cloudinary.com/v1_1/{settings.CLOUDINARY_CLOUD_NAME}/video/upload"
)

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_MIME = {"video/mp4", "video/quicktime", "video/x-m4v"}
ALLOWED_AUDIO_MIME = {"audio/mpeg", "audio/mp4", "audio/aac", "audio/x-m4a", "audio/mp3", "audio/wav", "audio/ogg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_AUDIO_SIZE = 25 * 1024 * 1024  # 25 MB


def _sign_params(params: dict) -> str:
    """Génère la signature HMAC-SHA1 pour l'upload authentifié."""
    sorted_params = "&".join(
        f"{k}={v}" for k, v in sorted(params.items()) if k not in ("file", "api_key")
    )
    to_sign = sorted_params + settings.CLOUDINARY_API_SECRET
    return hashlib.sha1(to_sign.encode()).hexdigest()


async def upload_image(file: UploadFile, folder: str) -> dict:
    """
    Upload un fichier image vers Cloudinary.

    Retourne :
        {
            "url":        "https://res.cloudinary.com/...",
            "public_id":  "folix/concerts/abc123",
            "width":      1200,
            "height":     675,
            "format":     "jpg",
        }
    """
    if not settings.CLOUDINARY_CLOUD_NAME:
        raise HTTPException(status_code=503, detail="Cloudinary non configuré")

    # Validation type MIME
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail=f"Type de fichier non supporté : {file.content_type}. "
                   f"Formats acceptés : JPEG, PNG, WebP, GIF",
        )

    # Lecture + validation taille
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Fichier trop volumineux ({len(content) // 1024} KB). Maximum : 10 MB",
        )

    timestamp = int(time.time())
    params = {
        "folder":    folder,
        "timestamp": timestamp,
    }
    signature = _sign_params(params)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            CLOUDINARY_UPLOAD_URL,
            data={
                "api_key":   settings.CLOUDINARY_API_KEY,
                "timestamp": timestamp,
                "signature": signature,
                "folder":    folder,
            },
            files={"file": (file.filename, content, file.content_type)},
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Cloudinary erreur {resp.status_code}: {resp.text[:200]}",
        )

    data = resp.json()
    return {
        "url":       data["secure_url"],
        "public_id": data["public_id"],
        "width":     data.get("width"),
        "height":    data.get("height"),
        "format":    data.get("format"),
    }


async def upload_images(files: list[UploadFile], folder: str) -> list[dict]:
    """Upload plusieurs images en parallèle. Retourne la liste des résultats."""
    import asyncio
    tasks = [upload_image(f, folder) for f in files]
    return await asyncio.gather(*tasks)


async def upload_video(file: UploadFile, folder: str) -> dict:
    """
    Upload un fichier vidéo vers Cloudinary.

    Retourne :
        {
            "url":          "https://res.cloudinary.com/...",
            "public_id":    "folix/reels/abc123",
            "duration":     15.2,
            "thumbnail_url":"https://res.cloudinary.com/...jpg",
            "width":        1080,
            "height":       1920,
            "format":       "mp4",
        }
    """
    if not settings.CLOUDINARY_CLOUD_NAME:
        raise HTTPException(status_code=503, detail="Cloudinary non configuré")

    if file.content_type not in ALLOWED_VIDEO_MIME:
        raise HTTPException(
            status_code=400,
            detail=f"Type de fichier non supporté : {file.content_type}. "
                   f"Formats acceptés : MP4, MOV, M4V",
        )

    content = await file.read()
    if len(content) > MAX_VIDEO_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Fichier trop volumineux ({len(content) // (1024*1024)} MB). Maximum : 100 MB",
        )

    timestamp = int(time.time())
    params = {
        "folder":    folder,
        "timestamp": timestamp,
    }
    signature = _sign_params(params)

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            CLOUDINARY_VIDEO_UPLOAD_URL,
            data={
                "api_key":       settings.CLOUDINARY_API_KEY,
                "timestamp":     timestamp,
                "signature":     signature,
                "folder":        folder,
                "resource_type": "video",
            },
            files={"file": (file.filename, content, file.content_type)},
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Cloudinary erreur {resp.status_code}: {resp.text[:200]}",
        )

    data = resp.json()
    video_url = data["secure_url"]

    # Cloudinary génère automatiquement une thumbnail pour les vidéos
    thumbnail_url = data["secure_url"].rsplit(".", 1)[0] + ".jpg"
    return {
        "url":           video_url,
        "public_id":     data["public_id"],
        "duration":      data.get("duration"),
        "thumbnail_url": thumbnail_url,
        "width":         data.get("width"),
        "height":        data.get("height"),
        "format":        data.get("format"),
    }


async def upload_audio(file: UploadFile, folder: str) -> dict:
    """Upload un fichier audio vers Cloudinary (vocal, mp3, etc.)."""
    if not settings.CLOUDINARY_CLOUD_NAME:
        raise HTTPException(status_code=503, detail="Cloudinary non configuré")

    if file.content_type not in ALLOWED_AUDIO_MIME:
        raise HTTPException(
            status_code=400,
            detail=f"Type audio non supporté : {file.content_type}. "
                   f"Formats acceptés : MP3, M4A, AAC, WAV, OGG",
        )

    content = await file.read()
    if len(content) > MAX_AUDIO_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Fichier trop volumineux ({len(content) // (1024*1024)} MB). Maximum : 25 MB",
        )

    timestamp = int(time.time())
    params = {"folder": folder, "timestamp": timestamp}
    signature = _sign_params(params)

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            CLOUDINARY_VIDEO_UPLOAD_URL,  # Cloudinary uses video endpoint for audio too
            data={
                "api_key":       settings.CLOUDINARY_API_KEY,
                "timestamp":     timestamp,
                "signature":     signature,
                "folder":        folder,
                "resource_type": "video",
            },
            files={"file": (file.filename, content, file.content_type)},
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Cloudinary erreur {resp.status_code}: {resp.text[:200]}",
        )

    data = resp.json()
    return {
        "url":       data["secure_url"],
        "public_id": data["public_id"],
        "duration":  data.get("duration"),
        "format":    data.get("format"),
    }


def get_h264_url(video_url: str) -> str:
    """
    Transforme une URL Cloudinary vidéo pour forcer H.264/AAC à la volée.
    Fonctionne pour les vidéos déjà uploadées (transformation on-the-fly).

    Avant : https://res.cloudinary.com/xxx/video/upload/v123/folix/reels/abc.mp4
    Après :  https://res.cloudinary.com/xxx/video/upload/vc_h264:main:3.1,ac_aac/v123/folix/reels/abc.mp4
    """
    if not video_url or "/video/upload/" not in video_url:
        return video_url
    # Insérer la transformation après "/video/upload/"
    return video_url.replace(
        "/video/upload/",
        "/video/upload/vc_h264:main:3.1,ac_aac/",
    )


async def delete_image(public_id: str) -> bool:
    """Supprime une image Cloudinary par son public_id."""
    if not settings.CLOUDINARY_CLOUD_NAME:
        return False
    timestamp = int(time.time())
    params = {"public_id": public_id, "timestamp": timestamp}
    signature = _sign_params(params)

    delete_url = (
        f"https://api.cloudinary.com/v1_1/{settings.CLOUDINARY_CLOUD_NAME}/image/destroy"
    )
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            delete_url,
            data={
                "api_key":   settings.CLOUDINARY_API_KEY,
                "timestamp": timestamp,
                "signature": signature,
                "public_id": public_id,
            },
        )
    return resp.status_code == 200 and resp.json().get("result") == "ok"
