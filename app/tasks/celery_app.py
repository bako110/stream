"""
Configuration Celery — broker Redis, backend Redis.
Worker : celery -A app.tasks.celery_app worker --loglevel=info
Beat   : celery -A app.tasks.celery_app beat   --loglevel=info
"""
from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "streaming",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.video_tasks",
        "app.tasks.notification_tasks",
        "app.tasks.cleanup_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# ── Tâches planifiées (Beat) ──────────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    # Expirer les billets toutes les heures
    "expire-tickets-hourly": {
        "task": "app.tasks.cleanup_tasks.expire_tickets",
        "schedule": crontab(minute=0),
    },
    # Expirer les abonnements toutes les heures
    "expire-subscriptions-hourly": {
        "task": "app.tasks.cleanup_tasks.expire_subscriptions",
        "schedule": crontab(minute=15),
    },
    # Mettre à jour les contenus tendance toutes les 30 min
    "update-trending-30min": {
        "task": "app.tasks.cleanup_tasks.update_trending",
        "schedule": crontab(minute="*/30"),
    },
}
