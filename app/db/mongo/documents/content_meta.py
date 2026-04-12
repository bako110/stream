"""
Document MongoDB — collection 'content_meta'

Métadonnées enrichies du catalogue (films / séries) non stockées dans PostgreSQL :
  - Cast complet avec photos
  - Tags et genres détaillés
  - Données TMDB / IMDb
  - Agrégats de reviews

Index texte sur (title, synopsis) pour la recherche full-text MongoDB.

Référence vers PostgreSQL :
  - content_id → contents.id  (index unique)
"""
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


class CastMember(BaseModel):
    name: str
    role: Optional[str] = None          # "Acteur", "Réalisateur"...
    character: Optional[str] = None     # Nom du personnage
    photo_url: Optional[str] = None


class ContentMetaDocument(BaseModel):
    """Schéma d'un document de la collection 'content_meta'."""

    content_id: str                     # UUID string → contents.id (PostgreSQL), index unique

    # Champs dupliqués depuis PostgreSQL pour la recherche full-text
    title: str
    synopsis: Optional[str] = None

    # Enrichissement
    tags: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    cast_detailed: list[CastMember] = Field(default_factory=list)

    # Sources externes
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
    external_ratings: dict[str, Any] = Field(default_factory=dict)
    # ex : {"imdb": 7.4, "tmdb": 8.1, "rotten_tomatoes": 92}

    # Agrégats de reviews utilisateurs
    total_reviews: int = 0
    average_rating: Optional[float] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
