# Import dans l'ordre des dépendances FK pour que Base.metadata.create_all() fonctionne
from app.db.postgres.models.user import User, UserRole, OAuthProvider
from app.db.postgres.models.content import Content, ContentType, ContentStatus
from app.db.postgres.models.season import Season
from app.db.postgres.models.episode import Episode
from app.db.postgres.models.concert import Concert, ConcertType, AccessType, ConcertStatus
from app.db.postgres.models.event import Event, EventType, EventStatus, EventAccessType
from app.db.postgres.models.subscription import Subscription, PlanType, SubscriptionStatus, PLAN_CONFIG
from app.db.postgres.models.payment import Payment, PaymentType, PaymentStatus
from app.db.postgres.models.ticket import Ticket, TicketStatus
from app.db.postgres.models.event_ticket import EventTicket
from app.db.postgres.models.reel import Reel, ReelStatus
from app.db.postgres.models.comment import Comment, TargetType
from app.db.postgres.models.reaction import Reaction, ReactionType
from app.db.postgres.models.share import Share, SharePlatform

__all__ = [
    "User", "UserRole", "OAuthProvider",
    "Content", "ContentType", "ContentStatus",
    "Season",
    "Episode",
    "Concert", "ConcertType", "AccessType", "ConcertStatus",
    "Event", "EventType", "EventStatus", "EventAccessType",
    "Subscription", "PlanType", "SubscriptionStatus", "PLAN_CONFIG",
    "Payment", "PaymentType", "PaymentStatus",
    "Ticket", "TicketStatus",
    "EventTicket",
    "Reel", "ReelStatus",
    "Comment", "TargetType",
    "Reaction", "ReactionType",
    "Share", "SharePlatform",
]
