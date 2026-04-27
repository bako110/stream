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
from app.db.postgres.models.reel import Reel, ReelStatus, ReelView
from app.db.postgres.models.story import Story, StoryView, StoryMediaType
from app.db.postgres.models.comment import Comment, TargetType
from app.db.postgres.models.reaction import Reaction, ReactionType
from app.db.postgres.models.share import Share, SharePlatform
from app.db.postgres.models.follow import Follow
from app.db.postgres.models.user_block import UserBlock
from app.db.postgres.models.user_interest import UserInterest
from app.db.postgres.models.community import Community, CommunityMember, CommunityRole
from app.db.postgres.models.activity import Activity, ActivityType
from app.db.postgres.models.notification import Notification, NotificationType
from app.db.postgres.models.planning_entry import PlanningEntry
from app.db.postgres.models.device_token import DeviceToken
from app.db.postgres.models.content_reminder import ContentReminder, ReminderRefType
from app.db.postgres.models.feed_hidden import FeedHidden

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
    "Reel", "ReelStatus", "ReelView",
    "Story", "StoryView", "StoryMediaType",
    "Comment", "TargetType",
    "Reaction", "ReactionType",
    "Share", "SharePlatform",
    "Follow",
    "UserBlock",
    "UserInterest",
    "Community", "CommunityMember", "CommunityRole",
    "Activity", "ActivityType",
    "Notification", "NotificationType",
    "PlanningEntry",
    "DeviceToken",
    "ContentReminder", "ReminderRefType",
    "FeedHidden",
]
