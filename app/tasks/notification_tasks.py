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
    """Envoie un email via SMTP — compatible Gmail (port 587 STARTTLS)."""
    from app.config import settings
    if not settings.SMTP_PASS:
        logger.warning("[EMAIL] SMTP_PASS non configuré — email non envoyé à %s", to_email)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"FoliX <{settings.EMAIL_FROM}>"
    msg["To"]      = to_email
    msg["X-Mailer"] = "FoliX Platform"
    msg.attach(MIMEText(html, "html", "utf-8"))

    ctx = ssl.create_default_context()
    try:
        if settings.SMTP_PORT == 465:
            # SSL direct (port 465)
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=ctx) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASS)
                server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())
        else:
            # STARTTLS (port 587 — Gmail, etc.)
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.ehlo()
                server.login(settings.SMTP_USER, settings.SMTP_PASS)
                server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())
        logger.info("[EMAIL] Envoyé → %s | %s", to_email, subject)
    except Exception as exc:
        logger.error("[EMAIL] Échec → %s | %s : %s", to_email, subject, exc)
        raise


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


def _tpl_password_reset(otp: str, display_name: str, ttl_minutes: int) -> str:
    # Formater l'OTP en "123 456" pour meilleure lisibilité
    otp_display = f"{otp[:3]} {otp[3:]}"
    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f4f8;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f8;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

        <!-- Header gradient -->
        <tr>
          <td style="background:linear-gradient(135deg,#7B3FF2 0%,#E0389A 100%);padding:36px 40px;text-align:center;">
            <h1 style="margin:0;color:#ffffff;font-size:32px;font-weight:900;letter-spacing:-1px;">FoliX</h1>
            <p style="margin:6px 0 0;color:rgba(255,255,255,0.75);font-size:13px;letter-spacing:1px;">MUSIQUE · CONCERTS · ÉVÉNEMENTS</p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:40px 40px 32px;">

            <p style="margin:0 0 8px;font-size:13px;color:#9B65F5;font-weight:700;text-transform:uppercase;letter-spacing:1px;">Sécurité du compte</p>
            <h2 style="margin:0 0 16px;font-size:24px;font-weight:800;color:#1a1a2e;">Bonjour {display_name},</h2>
            <p style="margin:0 0 28px;font-size:15px;color:#555;line-height:1.7;">
              Nous avons reçu une demande de réinitialisation de mot de passe pour votre compte FoliX.
              Voici votre code de vérification à usage unique :
            </p>

            <!-- OTP Block -->
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td align="center" style="background:linear-gradient(135deg,#f0e8ff,#fde8f3);border-radius:16px;padding:32px 20px;">
                  <p style="margin:0 0 8px;font-size:12px;color:#9B65F5;font-weight:700;text-transform:uppercase;letter-spacing:2px;">Code de vérification</p>
                  <p style="margin:0;font-size:48px;font-weight:900;letter-spacing:12px;color:#7B3FF2;font-family:'Courier New',monospace;">{otp_display}</p>
                  <p style="margin:12px 0 0;font-size:13px;color:#888;">
                    Valide pendant <strong style="color:#E0389A;">{ttl_minutes} minutes</strong> &nbsp;·&nbsp; Usage unique
                  </p>
                </td>
              </tr>
            </table>

            <p style="margin:28px 0 0;font-size:14px;color:#555;line-height:1.7;">
              Entrez ce code dans l'application FoliX pour réinitialiser votre mot de passe.
            </p>

            <!-- Avertissement -->
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:24px;">
              <tr>
                <td style="background:#fff8f0;border-left:4px solid #F5A623;border-radius:0 8px 8px 0;padding:14px 16px;">
                  <p style="margin:0;font-size:13px;color:#8a6000;line-height:1.6;">
                    <strong>Vous n'avez pas fait cette demande ?</strong><br>
                    Ignorez simplement cet email. Votre mot de passe restera inchangé.
                    Si vous pensez que votre compte est compromis, contactez notre support.
                  </p>
                </td>
              </tr>
            </table>

          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#fafafa;border-top:1px solid #f0f0f0;padding:24px 40px;text-align:center;">
            <p style="margin:0 0 4px;font-size:12px;color:#aaa;">
              Cet email a été envoyé automatiquement — merci de ne pas y répondre.
            </p>
            <p style="margin:0;font-size:12px;color:#ccc;">
              © 2026 FoliX · Tous droits réservés
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


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


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def send_password_reset_email(self, user_email: str, otp: str, display_name: str, ttl_minutes: int = 15):
    try:
        _send_smtp(
            to_email=user_email,
            subject=f"[FoliX] Votre code de vérification : {otp[:3]} {otp[3:]}",
            html=_tpl_password_reset(otp, display_name, ttl_minutes),
        )
    except Exception as exc:
        raise self.retry(exc=exc)


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
