"""
Tâches de notification — emails, alertes concerts live.
"""
from app.tasks.celery_app import celery_app


@celery_app.task
def send_welcome_email(user_email: str, username: str):
    """Email de bienvenue après inscription."""
    from app.config import settings
    # En production : intégrer SendGrid / SMTP via fastapi-mail
    print(f"[EMAIL] Bienvenue {username} ({user_email}) sur {settings.APP_NAME}")


@celery_app.task
def send_ticket_confirmation(user_email: str, access_code: str, event_title: str, event_date: str):
    """Email de confirmation de billet (concert ou événement)."""
    print(f"[EMAIL] Billet confirmé pour {event_title} le {event_date} — code : {access_code} → {user_email}")


@celery_app.task
def send_concert_reminder(concert_id: str):
    """
    Rappel 1h avant le début d'un concert.
    Envoie une notification push / email à tous les détenteurs de billets.
    """
    import asyncio

    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from sqlalchemy import select
        import uuid
        from app.config import settings
        from app.db.postgres.models.ticket import Ticket, TicketStatus
        from app.db.postgres.models.user import User

        engine = create_async_engine(settings.DATABASE_URL)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with Session() as session:
            result = await session.execute(
                select(Ticket, User)
                .join(User, User.id == Ticket.user_id)
                .where(
                    Ticket.concert_id == uuid.UUID(concert_id),
                    Ticket.status == TicketStatus.valid,
                )
            )
            for ticket, user in result.all():
                print(f"[NOTIF] Rappel concert → {user.email} (billet {ticket.access_code})")

        await engine.dispose()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task
def notify_concert_live(concert_id: str):
    """Notifier les abonnés qu'un concert vient de démarrer en live."""
    print(f"[NOTIF] Concert {concert_id} est maintenant en LIVE")


@celery_app.task
def send_subscription_expiry_warning(user_email: str, days_left: int):
    """Avertir l'utilisateur que son abonnement expire bientôt."""
    print(f"[EMAIL] Abonnement expire dans {days_left} jours → {user_email}")
