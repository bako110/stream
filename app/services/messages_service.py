"""
Service de messagerie directe (DM) — stockage MongoDB.
Collections :
  • messages  : { _id, sender_id, receiver_id, content, created_at, read }
"""
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


# ─── helpers ──────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fmt(doc: dict) -> dict:
    """Convertit ObjectId → str pour la sérialisation JSON."""
    if doc is None:
        return doc
    doc["id"] = str(doc.pop("_id"))
    return doc


# ─── service ─────────────────────────────────────────────────────────────────

async def send_message(
    db: AsyncIOMotorDatabase,
    sender_id: str,
    receiver_id: str,
    content: str,
    message_type: str = "text",
    attachment_url: str | None = None,
    attachment_meta: dict | None = None,
) -> dict:
    """Insère un message et retourne le document créé."""
    doc = {
        "sender_id":    sender_id,
        "receiver_id":  receiver_id,
        "content":      content.strip() if content else "",
        "message_type": message_type,
        "created_at":   _now(),
        "read":         False,
    }
    if attachment_url:
        doc["attachment_url"] = attachment_url
    if attachment_meta:
        doc["attachment_meta"] = attachment_meta
    result = await db["messages"].insert_one(doc)
    doc["_id"] = result.inserted_id
    return _fmt(doc)


async def get_conversation(
    db: AsyncIOMotorDatabase,
    user_id: str,
    other_id: str,
    page: int = 1,
    limit: int = 30,
) -> list[dict]:
    """Messages échangés entre deux utilisateurs, du plus récent au plus ancien."""
    skip = (page - 1) * limit
    cursor = db["messages"].find(
        {
            "$or": [
                {"sender_id": user_id,  "receiver_id": other_id},
                {"sender_id": other_id, "receiver_id": user_id},
            ]
        },
        sort=[("created_at", -1)],
        skip=skip,
        limit=limit,
    )
    docs = await cursor.to_list(length=limit)
    return [_fmt(d) for d in docs]


async def mark_conversation_read(
    db: AsyncIOMotorDatabase,
    reader_id: str,
    sender_id: str,
) -> None:
    """Marque comme lus tous les messages reçus d'un expéditeur donné."""
    await db["messages"].update_many(
        {"sender_id": sender_id, "receiver_id": reader_id, "read": False},
        {"$set": {"read": True}},
    )


async def edit_message(
    db: AsyncIOMotorDatabase,
    message_id: str,
    sender_id: str,
    new_content: str,
) -> dict | None:
    """Modifie le contenu d'un message (auteur uniquement)."""
    result = await db["messages"].find_one_and_update(
        {"_id": ObjectId(message_id), "sender_id": sender_id, "deleted": {"$ne": True}},
        {"$set": {"content": new_content.strip(), "edited_at": _now()}},
        return_document=True,
    )
    return _fmt(result) if result else None


async def delete_message(
    db: AsyncIOMotorDatabase,
    message_id: str,
    sender_id: str,
) -> dict | None:
    """Supprime un message pour tous (auteur uniquement) — suppression douce."""
    result = await db["messages"].find_one_and_update(
        {"_id": ObjectId(message_id), "sender_id": sender_id},
        {"$set": {"deleted": True, "deleted_at": _now(), "content": "", "attachment_url": None, "attachment_meta": None}},
        return_document=True,
    )
    return _fmt(result) if result else None


async def get_conversations(
    db: AsyncIOMotorDatabase,
    user_id: str,
) -> list[dict]:
    """
    Retourne la liste des conversations (un doc par interlocuteur unique)
    avec : partner_id, last_message, last_time, unread_count.
    Utilise une pipeline d'agrégation MongoDB.
    """
    pipeline = [
        # 1. Filtrer les messages où l'utilisateur est impliqué
        {
            "$match": {
                "$or": [
                    {"sender_id": user_id},
                    {"receiver_id": user_id},
                ]
            }
        },
        # 2. Calculer le partenaire (l'autre côté)
        {
            "$addFields": {
                "partner_id": {
                    "$cond": {
                        "if":   {"$eq": ["$sender_id", user_id]},
                        "then": "$receiver_id",
                        "else": "$sender_id",
                    }
                }
            }
        },
        # 3. Grouper par partenaire → dernier message + nb non-lus
        {
            "$sort": {"created_at": -1}
        },
        {
            "$group": {
                "_id":          "$partner_id",
                "last_message": {"$first": "$content"},
                "last_time":    {"$first": "$created_at"},
                "unread_count": {
                    "$sum": {
                        "$cond": [
                            {"$and": [
                                {"$eq": ["$receiver_id", user_id]},
                                {"$eq": ["$read", False]},
                            ]},
                            1,
                            0,
                        ]
                    }
                },
            }
        },
        # 4. Trier par dernier message le plus récent
        {"$sort": {"last_time": -1}},
        {"$limit": 100},
        # 5. Renommer _id → partner_id
        {
            "$project": {
                "_id":          0,
                "partner_id":   "$_id",
                "last_message": 1,
                "last_time":    1,
                "unread_count": 1,
            }
        },
    ]

    cursor = db["messages"].aggregate(pipeline)
    return await cursor.to_list(length=100)
