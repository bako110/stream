"""
Tâches Celery — emails et notifications push.
SMTP configuré via settings (SendGrid ou tout serveur SMTP).
"""
import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _send_smtp(to_email: str, subject: str, html: str) -> None:
    """Envoie un email via SMTP (SendGrid / tout provider)."""
    from app.config import settings
    if not settings.SMTP_PASS:
        logger.warning("[EMAIL] SMTP_PASS non configuré — email non envoyé à %s", to_email)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.EMAIL_FROM
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html", "utf-8"))

    ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.login(settings.SMTP_USER, settings.SMTP_PASS)
            server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())
        logger.info("[EMAIL] Envoyé → %s | %s", to_email, subject)
    except Exception as exc:
        logger.error("[EMAIL] Échec → %s | %s : %s", to_email, subject, exc)


# ── Templates HTML ─────────────────────────────────────────────────────────────

def _tpl_welcome(username: str) -> str:
    return f"""
    <div style="font-family:sans-serif;max-width:560px;margin:auto;background:#0D0D1A;color:#fff;border-radius:16px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#7B3FF2,#E0389A);padding:32px;text-align:center;">
        <h1 style="margin:0;font-size:28px;letter-spacing:-1px;">FoliX</h1>
        <p style="margin:4px 0 0;opacity:.8;font-size:13px;">Musique · Concerts · Événements</p>
      </div>
      <div style="padding:32px;">
        <h2 style="color:#9B65F5;margin-top:0;">Bienvenue, {username} ! 🎉</h2>
        <p style="line-height:1.7;color:#ccc;">
          Votre compte FoliX est prêt. Découvrez des concerts exclusifs, suivez vos artistes préférés
          et ne manquez aucun événement près de chez vous.
        </p>
        <a href="#" style="display:inline-block;margin-top:16px;padding:14px 28px;background:linear-gradient(135deg,#7B3FF2,#E0389A);color:#fff;border-radius:30px;text-decoration:none;font-weight:700;">
          Explorer FoliX
        </a>
      </div>
      <div style="padding:16px 32px;border-top:1px solid #1a1a2e;font-size:12px;color:#555;text-align:center;">
        Vous recevez cet email car vous venez de créer un compte FoliX.
      </div>
    </div>
    """


def _tpl_ticket(access_code: str, event_title: str, event_date: str) -> str:
    return f"""
    <div style="font-family:sans-serif;max-width:560px;margin:auto;background:#0D0D1A;color:#fff;border-radius:16px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#7B3FF2,#E0389A);padding:32px;text-align:center;">
        <h1 style="margin:0;font-size:28px;">FoliX</h1>
      </div>
      <div style="padding:32px;">
        <h2 style="color:#36D9A0;margin-top:0;">Billet confirmé ✓</h2>
        <p style="color:#ccc;line-height:1.7;">Votre place pour <strong style="color:#fff;">{event_title}</strong> est réservée.</p>
        <div style="background:#1a1a2e;border-radius:12px;padding:20px;margin:20px 0;text-align:center;">
          <p style="margin:0;color:#aaa;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Code d'accès</p>
          <p style="margin:8px 0 0;font-size:32px;font-weight:900;letter-spacing:6px;color:#9B65F5;">{access_code}</p>
          <p style="margin:8px 0 0;color:#aaa;font-size:13px;">{event_date}</p>
        </div>
        <p style="color:#888;font-size:12px;">Présentez ce code à l'entrée (QR ou saisie manuelle).</p>
      </div>
    </div>
    """


def _tpl_concert_reminder(concert_title: str, starts_at: str) -> str:
    return f"""
    <div style="font-family:sans-serif;max-width:560px;margin:auto;background:#0D0D1A;color:#fff;border-radius:16px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#7B3FF2,#E0389A);padding:32px;text-align:center;">
        <h1 style="margin:0;font-size:28px;">FoliX</h1>
      </div>
      <div style="padding:32px;">
        <h2 style="color:#FF7A2F;margin-top:0;">⏰ Concert dans 1 heure !</h2>
        <p style="color:#ccc;line-height:1.7;">
          <strong style="color:#fff;">{concert_title}</strong> commence à <strong style="color:#fff;">{starts_at}</strong>.
          Préparez-vous et profitez du show !
        </p>
      </div>
    </div>
    """


def _tpl_subscription_expiry(days_left: int, plan: str) -> str:
    return f"""
    <div style="font-family:sans-serif;max-width:560px;margin:auto;background:#0D0D1A;color:#fff;border-radius:16px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#7B3FF2,#E0389A);padding:32px;text-align:center;">
        <h1 style="margin:0;font-size:28px;">FoliX</h1>
      </div>
      <div style="padding:32px;">
        <h2 style="color:#FF7A2F;margin-top:0;">Votre abonnement expire bientôt</h2>
        <p style="color:#ccc;line-height:1.7;">
          Votre abonnement <strong style="color:#fff;">{plan}</strong> expire dans
          <strong style="color:#FF7A2F;">{days_left} jour{"s" if days_left > 1 else ""}</strong>.
          Renouvelez-le pour continuer à profiter de FoliX sans interruption.
        </p>
        <a href="#" style="display:inline-block;margin-top:16px;padding:14px 28px;background:linear-gradient(135deg,#7B3FF2,#E0389A);color:#fff;border-radius:30px;text-decoration:none;font-weight:700;">
          Renouveler maintenant
        </a>
      </div>
    </div>
    """


# ── Tâches Celery ──────────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_welcome_email(self, user_email: str, username: str):
    try:
        _send_smtp(
            to_email=user_email,
            subject=f"Bienvenue sur FoliX, {username} ! 🎉",
            html=_tpl_welcome(username),
        )
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_ticket_confirmation(self, user_email: str, access_code: str, event_title: str, event_date: str):
    try:
        _send_smtp(
            to_email=user_email,
            subject=f"Votre billet — {event_title}",
            html=_tpl_ticket(access_code, event_title, event_date),
        )
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def send_concert_reminder(self, concert_id: str):
    import asyncio

    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from sqlalchemy import select
        import uuid as _uuid
        from app.config import settings
        from app.db.postgres.models.ticket import Ticket, TicketStatus
        from app.db.postgres.models.user import User
        from app.db.postgres.models.concert import Concert

        engine = create_async_engine(settings.DATABASE_URL)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with Session() as session:
            concert_result = await session.execute(
                select(Concert).where(Concert.id == _uuid.UUID(concert_id))
            )
            concert = concert_result.scalar_one_or_none()
            if not concert:
                return

            result = await session.execute(
                select(Ticket, User)
                .join(User, User.id == Ticket.user_id)
                .where(
                    Ticket.concert_id == _uuid.UUID(concert_id),
                    Ticket.status == TicketStatus.valid,
                )
            )
            starts_at = concert.scheduled_at.strftime("%d/%m/%Y à %H:%M") if concert.scheduled_at else ""
            for ticket, user in result.all():
                _send_smtp(
                    to_email=user.email,
                    subject=f"⏰ {concert.title} commence dans 1 heure !",
                    html=_tpl_concert_reminder(concert.title, starts_at),
                )

        await engine.dispose()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def notify_concert_live(self, concert_id: str):
    """Notifier via WS tous les détenteurs de billets d'un concert qui démarre en live."""
    import asyncio

    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from sqlalchemy import select
        import uuid as _uuid
        from app.config import settings
        from app.db.postgres.models.ticket import Ticket, TicketStatus
        from app.db.postgres.models.concert import Concert
        from app.services.ws_manager import manager

        engine = create_async_engine(settings.DATABASE_URL)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with Session() as session:
            concert_result = await session.execute(
                select(Concert).where(Concert.id == _uuid.UUID(concert_id))
            )
            concert = concert_result.scalar_one_or_none()
            if not concert:
                return

            result = await session.execute(
                select(Ticket.user_id)
                .where(Ticket.concert_id == _uuid.UUID(concert_id), Ticket.status == TicketStatus.valid)
            )
            for (user_id,) in result.all():
                await manager.send_to_user(str(user_id), {
                    "type":              "notification",
                    "notification_type": "concert_live",
                    "title":             "🔴 Concert en direct !",
                    "body":              f"{concert.title} vient de démarrer en live.",
                    "ref_id":            concert_id,
                    "ref_type":          "concert",
                })

        await engine.dispose()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_subscription_expiry_warning(self, user_email: str, days_left: int, plan: str = "Premium"):
    try:
        _send_smtp(
            to_email=user_email,
            subject=f"Votre abonnement FoliX expire dans {days_left} jour{'s' if days_left > 1 else ''}",
            html=_tpl_subscription_expiry(days_left, plan),
        )
    except Exception as exc:
        raise self.retry(exc=exc)
