# Ce fichier est INDISPENSABLE pour que init_db() dans database.py
# découvre tous les modèles via Base.metadata.create_all

from app.models.user import User, UserRole
from app.models.content import Content, ContentType, ContentStatus
from app.models.season import Season
from app.models.episode import Episode        # ← doit être AVANT video
from app.models.video import Video, VideoVersion, TranscodeStatus
from app.models.concert import Concert, ConcertType, AccessType, ConcertStatus
from app.models.subscription import Subscription, PlanType, SubscriptionStatus
from app.models.payment import Payment, PaymentType, PaymentStatus
from app.models.ticket import Ticket, TicketStatus
from app.models.watch_history import WatchHistory

__all__ = [
    "User", "UserRole",
    "Content", "ContentType", "ContentStatus",
    "Season",
    "Episode",
    "Video", "VideoVersion", "TranscodeStatus",
    "Concert", "ConcertType", "AccessType", "ConcertStatus",
    "Subscription", "PlanType", "SubscriptionStatus",
    "Payment", "PaymentType", "PaymentStatus",
    "Ticket", "TicketStatus",
    "WatchHistory",
]