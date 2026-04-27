from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Streaming Platform API"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # ─── PostgreSQL ───────────────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/streaming?prepared_statement_cache_size=0"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_pg_url(cls, v: str) -> str:
        # Fly.io sets postgres:// but asyncpg needs postgresql+asyncpg://
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        # asyncpg ne comprend pas sslmode (param libpq), on le retire
        import re
        v = re.sub(r"[?&]sslmode=[^&]*", "", v)
        return v

    # ─── MongoDB (données lourdes : vidéos, watch history, catalogue enrichi) ─────────
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "streaming_media"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Stockage local des médias
    UPLOAD_DIR: str = "/var/www/uploads"
    MEDIA_BASE_URL: str = "http://178.104.248.78"

    # Cloudinary (désactivé — conservé pour compatibilité)
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # JWT
    JWT_SECRET_KEY: str = "change-this-secret-key"
    JWT_REFRESH_SECRET_KEY: str = "change-this-refresh-secret-key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # S3 / MinIO
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_RAW: str = "videos-raw"
    S3_BUCKET_HLS: str = "videos-hls"
    S3_BUCKET_THUMBS: str = "thumbnails"
    CDN_BASE_URL: str = "http://localhost:9000"
    CDN_SIGNED_URL_EXPIRE_SECONDS: int = 7200

    # Stripe
    STRIPE_SECRET_KEY: str = "sk_test_..."
    STRIPE_WEBHOOK_SECRET: str = "whsec_..."

    # Email
    SMTP_HOST: str = "smtp.sendgrid.net"
    SMTP_PORT: int = 587
    SMTP_USER: str = "apikey"
    SMTP_PASS: str = ""
    EMAIL_FROM: str = "noreply@yourplatform.com"

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    # LiveKit
    LIVEKIT_URL: str = ""
    LIVEKIT_API_KEY: str = ""
    LIVEKIT_API_SECRET: str = ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


settings = Settings()
