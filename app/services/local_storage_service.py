"""
Service de stockage local — remplace Cloudinary.

Les fichiers sont sauvegardés dans UPLOAD_DIR/{folder}/ sur le serveur
et servis via /uploads/ (monté comme StaticFiles dans main.py).

Structure des dossiers :
  uploads/concerts/     → thumbnails + banners concerts
  uploads/events/       → thumbnails + banners événements
  uploads/avatars/      → avatars utilisateurs
  uploads/reels/        → vidéos reels
  uploads/stories/      → médias stories (images/vidéos)
  uploads/stories/audio/→ audios stories
  uploads/messages/     → images messages
  uploads/messages/video/ → vidéos messages
"""
import asyncio
import subprocess
import uuid
from pathlib import Path
from fastapi import HTTPException, UploadFile

from app.config import settings

UPLOAD_DIR = Path(settings.UPLOAD_DIR)
BASE_URL = settings.MEDIA_BASE_URL.rstrip("/")

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_MIME = {"video/mp4", "video/quicktime", "video/x-m4v"}
ALLOWED_AUDIO_MIME = {"audio/mpeg", "audio/mp4", "audio/aac", "audio/x-m4a", "audio/mp3", "audio/wav", "audio/ogg"}
MAX_FILE_SIZE  =    10 * 1024 * 1024   #   10 MB  images
MAX_VIDEO_SIZE = 8 * 1024 * 1024 * 1024  #    8 GB  vidéos/films/séries
MAX_AUDIO_SIZE =    25 * 1024 * 1024   #   25 MB  audio
CHUNK_SIZE     = 8 * 1024 * 1024       #    8 MB  chunk streaming

MIME_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/x-m4v": ".m4v",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/aac": ".aac",
    "audio/x-m4a": ".m4a",
    "audio/wav": ".wav",
    "audio/ogg": ".ogg",
}


def _save_file(content: bytes, folder: str, mime: str) -> tuple[str, str]:
    """
    Sauvegarde le contenu dans UPLOAD_DIR/folder/ avec un nom unique.
    Retourne (url_publique, public_id).
    """
    ext = MIME_EXT.get(mime, "")
    filename = f"{uuid.uuid4().hex}{ext}"
    dest_dir = UPLOAD_DIR / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename
    dest_path.write_bytes(content)

    public_id = f"{folder}/{filename}"
    url = f"{BASE_URL}/uploads/{public_id}"
    return url, public_id


async def upload_image(file: UploadFile, folder: str) -> dict:
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail=f"Type de fichier non supporté : {file.content_type}. "
                   f"Formats acceptés : JPEG, PNG, WebP, GIF",
        )
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Fichier trop volumineux ({len(content) // 1024} KB). Maximum : 10 MB",
        )
    url, public_id = _save_file(content, folder, file.content_type)
    return {
        "url": url,
        "public_id": public_id,
        "width": None,
        "height": None,
        "format": file.content_type.split("/")[-1],
    }


async def upload_images(files: list[UploadFile], folder: str) -> list[dict]:
    import asyncio
    tasks = [upload_image(f, folder) for f in files]
    return await asyncio.gather(*tasks)


def _ffprobe_duration(video_path: Path) -> float | None:
    """Retourne la durée en secondes via ffprobe, ou None si ffprobe absent."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
            capture_output=True, text=True, timeout=15,
        )
        return float(result.stdout.strip()) if result.returncode == 0 else None
    except Exception:
        return None


def _ffmpeg_thumbnail(video_path: Path, thumb_path: Path) -> bool:
    """Extrait une frame à 10% de la durée en JPEG qualité maximale."""
    try:
        # Récupère la durée d'abord pour prendre une frame à 10%
        dur = _ffprobe_duration(video_path)
        seek = max(1.0, (dur or 10.0) * 0.1)
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(seek),
                "-i", str(video_path),
                "-frames:v", "1",
                "-q:v", "1",          # qualité JPEG maximale (1=max, 31=min)
                "-vf", "scale=iw:ih", # garde la résolution native
                str(thumb_path),
            ],
            capture_output=True, timeout=60,
        )
        return result.returncode == 0 and thumb_path.exists()
    except Exception:
        return False


async def upload_video(file: UploadFile, folder: str) -> dict:
    if file.content_type not in ALLOWED_VIDEO_MIME:
        raise HTTPException(
            status_code=400,
            detail=f"Type de fichier non supporté : {file.content_type}. "
                   f"Formats acceptés : MP4, MOV, M4V",
        )

    # Écriture en streaming par chunks — ne charge pas tout en RAM
    ext = MIME_EXT.get(file.content_type, ".mp4")
    filename = f"{uuid.uuid4().hex}{ext}"
    dest_dir = UPLOAD_DIR / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename

    total_size = 0
    try:
        with dest_path.open("wb") as f:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_VIDEO_SIZE:
                    f.close()
                    dest_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Fichier trop volumineux. Maximum : 8 GB",
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'upload : {e}")

    public_id = f"{folder}/{filename}"
    url = f"{BASE_URL}/uploads/{public_id}"
    video_path = dest_path

    # Génération thumbnail + durée via ffmpeg (dans un thread pour ne pas bloquer)
    thumb_name = video_path.stem + "_thumb.jpg"
    thumb_path = video_path.parent / thumb_name

    duration, thumbnail_url = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: (
            _ffprobe_duration(video_path),
            f"{BASE_URL}/uploads/{folder}/{thumb_name}"
            if _ffmpeg_thumbnail(video_path, thumb_path) else None,
        ),
    )

    return {
        "url": url,
        "public_id": public_id,
        "duration": duration,
        "thumbnail_url": thumbnail_url,
        "width": None,
        "height": None,
        "format": file.content_type.split("/")[-1],
    }


async def upload_audio(file: UploadFile, folder: str) -> dict:
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
    url, public_id = _save_file(content, folder, file.content_type)
    return {
        "url": url,
        "public_id": public_id,
        "duration": None,
        "format": file.content_type.split("/")[-1],
    }


async def delete_file(public_id: str) -> bool:
    """Supprime un fichier local par son public_id (ex: 'concerts/abc123.jpg')."""
    file_path = UPLOAD_DIR / public_id
    try:
        file_path.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def get_h264_url(video_url: str) -> str:
    """Pas de transformation nécessaire en local — retourne l'URL telle quelle."""
    return video_url


def public_id_from_url(url: str | None) -> str | None:
    """Extrait le public_id depuis une URL locale (ex: http://host/uploads/reels/abc.mp4 → reels/abc.mp4)."""
    if not url:
        return None
    marker = "/uploads/"
    idx = url.find(marker)
    if idx == -1:
        return None
    return url[idx + len(marker):]


async def delete_media(url: str | None) -> None:
    """Supprime un fichier local à partir de son URL publique. Silencieux si absent."""
    pid = public_id_from_url(url)
    if pid:
        await delete_file(pid)
