"""
Routes d'upload de médias — stockage local sur le serveur.

POST /api/v1/upload/images
  → Reçoit 1 à 10 fichiers en multipart/form-data
  → Paramètre query : folder = "concerts" | "events" | "avatars"
  → Retourne la liste des URLs locales

Authentification requise (token JWT).
"""
from typing import Literal
from fastapi import APIRouter, Depends, File, UploadFile, Query, HTTPException
from pydantic import BaseModel

from app.deps import get_current_active_user
from app.db.postgres.models.user import User
from app.services.local_storage_service import upload_images, delete_file as delete_image, upload_video, upload_audio

router = APIRouter()

# Dossiers Cloudinary autorisés
FolderType = Literal["concerts", "events", "avatars", "reels", "stories", "messages", "content"]

FOLDER_MAP: dict[FolderType, str] = {
    "concerts": "concerts",
    "events":   "events",
    "avatars":  "avatars",
    "reels":    "reels",
    "stories":  "stories",
    "messages": "messages",
    "content":  "content",
}


class UploadResult(BaseModel):
    url:       str
    public_id: str
    width:     int | None = None
    height:    int | None = None
    format:    str | None = None


class UploadResponse(BaseModel):
    uploaded: list[UploadResult]
    count:    int


@router.post("/images", response_model=UploadResponse)
async def upload_images_endpoint(
    file: UploadFile = File(..., description="Image (JPEG, PNG, WebP, GIF — max 10 MB)"),
    folder: FolderType = Query("concerts"),
    _: User = Depends(get_current_active_user),
):
    cloudinary_folder = FOLDER_MAP[folder]
    results = await upload_images([file], cloudinary_folder)

    return UploadResponse(
        uploaded=[UploadResult(**r) for r in results],
        count=len(results),
    )


class DeleteRequest(BaseModel):
    public_id: str


@router.delete("/images")
async def delete_image_endpoint(
    body: DeleteRequest,
    _: User = Depends(get_current_active_user),
):
    """Supprime une image Cloudinary par son public_id."""
    ok = await delete_image(body.public_id)
    if not ok:
        raise HTTPException(status_code=502, detail="Impossible de supprimer l'image")
    return {"deleted": True, "public_id": body.public_id}


class VideoUploadResult(BaseModel):
    url:           str
    public_id:     str
    duration:      float | None = None
    thumbnail_url: str | None = None
    width:         int | None = None
    height:        int | None = None
    format:        str | None = None


VideoFolderType = Literal["reels", "stories", "messages", "events", "concerts", "content"]

VIDEO_FOLDER_MAP: dict[VideoFolderType, str] = {
    "reels":    "reels",
    "stories":  "stories",
    "messages": "messages/video",
    "events":   "events/video",
    "concerts": "concerts/video",
    "content":  "content/video",
}


@router.post("/video", response_model=VideoUploadResult)
async def upload_video_endpoint(
    file: UploadFile = File(..., description="Vidéo (MP4, MOV, M4V — max 100 MB)"),
    folder: VideoFolderType = Query("reels", description="Dossier Cloudinary cible"),
    _: User = Depends(get_current_active_user),
):
    """Upload d'une vidéo vers Cloudinary. Retourne l'URL + thumbnail + durée."""
    cloudinary_folder = VIDEO_FOLDER_MAP[folder]
    result = await upload_video(file, cloudinary_folder)
    return VideoUploadResult(**result)


# ── Audio ────────────────────────────────────────────────────────────────────

class AudioUploadResult(BaseModel):
    url:       str
    public_id: str
    duration:  float | None = None
    format:    str | None = None


AudioFolderType = Literal["messages", "stories"]

AUDIO_FOLDER_MAP: dict[AudioFolderType, str] = {
    "messages": "messages/audio",
    "stories":  "stories/audio",
}


@router.post("/audio", response_model=AudioUploadResult)
async def upload_audio_endpoint(
    file: UploadFile = File(..., description="Audio (MP3, M4A, AAC, WAV, OGG — max 25 MB)"),
    folder: AudioFolderType = Query("messages", description="Dossier Cloudinary cible"),
    _: User = Depends(get_current_active_user),
):
    """Upload d'un fichier audio (vocal) vers Cloudinary."""
    cloudinary_folder = AUDIO_FOLDER_MAP[folder]
    result = await upload_audio(file, cloudinary_folder)
    return AudioUploadResult(**result)
