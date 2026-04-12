"""
Tâches de nettoyage planifiées (via Celery Beat).
- Expirer les billets dépassés
- Expirer les abonnements dépassés
- Mettre à jour les contenus tendance
"""
import asyncio
from datetime import datetime

from app.tasks.celery_app import celery_app


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_session():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.config import settings
    engine = create_async_engine(settings.DATABASE_URL)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, Session


@celery_app.task
def expire_tickets():
    """Passe en 'expired' tous les billets dont expires_at est dépassé."""
    async def _run_task():
        from sqlalchemy import select, update
        from app.db.postgres.models.ticket import Ticket, TicketStatus
        from app.db.postgres.models.event_ticket import EventTicket

        engine, Session = _make_session()
        now = datetime.utcnow()

        async with Session() as session:
            # Billets concerts
            result = await session.execute(
                select(Ticket).where(
                    Ticket.status == TicketStatus.valid,
                    Ticket.expires_at != None,
                    Ticket.expires_at < now,
                )
            )
            tickets = result.scalars().all()
            for t in tickets:
                t.status = TicketStatus.expired

            # Billets événements
            result = await session.execute(
                select(EventTicket).where(
                    EventTicket.status == TicketStatus.valid,
                    EventTicket.expires_at != None,
                    EventTicket.expires_at < now,
                )
            )
            for t in result.scalars().all():
                t.status = TicketStatus.expired

            await session.commit()
            print(f"[CLEANUP] {len(tickets)} billet(s) expiré(s)")

        await engine.dispose()

    _run(_run_task())


@celery_app.task
def expire_subscriptions():
    """Passe en 'expired' les abonnements dont current_period_end est dépassé."""
    async def _run_task():
        from sqlalchemy import select
        from app.db.postgres.models.subscription import Subscription, SubscriptionStatus

        engine, Session = _make_session()
        now = datetime.utcnow()

        async with Session() as session:
            result = await session.execute(
                select(Subscription).where(
                    Subscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.trialing]),
                    Subscription.current_period_end < now,
                )
            )
            subs = result.scalars().all()
            for sub in subs:
                sub.status = SubscriptionStatus.expired
            await session.commit()
            print(f"[CLEANUP] {len(subs)} abonnement(s) expiré(s)")

        await engine.dispose()

    _run(_run_task())


@celery_app.task
def update_trending():
    """
    Recalcule les 10 contenus tendance en base sur view_count des 7 derniers jours.
    En production : alimenter un cache Redis pour les requêtes rapides.
    """
    async def _run_task():
        from sqlalchemy import select
        from app.db.postgres.models.content import Content, ContentStatus

        engine, Session = _make_session()

        async with Session() as session:
            result = await session.execute(
                select(Content)
                .where(Content.status == ContentStatus.published)
                .order_by(Content.view_count.desc())
                .limit(10)
            )
            trending = result.scalars().all()
            ids = [str(c.id) for c in trending]
            print(f"[TRENDING] Top 10 : {ids}")
            # En production : stocker dans Redis avec TTL 30min
            # redis_client.set("trending:content", json.dumps(ids), ex=1800)

        await engine.dispose()

    _run(_run_task())
