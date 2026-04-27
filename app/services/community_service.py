import uuid
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.models.community import Community, CommunityMember, CommunityRole, CommunityBlockedMember, CommunityMessage


class CommunityService:

    @staticmethod
    async def create(
        name: str, creator_id: uuid.UUID, db: AsyncSession,
        description: str | None = None, is_private: bool = False,
        avatar_url: str | None = None, banner_url: str | None = None,
    ) -> Community:
        community = Community(
            name=name, description=description,
            creator_id=creator_id, is_private=is_private,
            avatar_url=avatar_url, banner_url=banner_url,
            members_count=1,
        )
        db.add(community)
        await db.flush()

        member = CommunityMember(
            community_id=community.id, user_id=creator_id,
            role=CommunityRole.admin,
        )
        db.add(member)
        await db.commit()
        await db.refresh(community)
        return community

    @staticmethod
    async def list_all(db: AsyncSession, page: int = 1, limit: int = 20):
        offset = (page - 1) * limit
        result = await db.execute(
            select(Community).order_by(Community.created_at.desc()).offset(offset).limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def get_by_id(community_id: uuid.UUID, db: AsyncSession) -> Community | None:
        result = await db.execute(select(Community).where(Community.id == community_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_my_communities(user_id: uuid.UUID, db: AsyncSession):
        result = await db.execute(
            select(Community).join(CommunityMember, CommunityMember.community_id == Community.id)
            .where(CommunityMember.user_id == user_id)
            .order_by(CommunityMember.joined_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def join(community_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> bool:
        # Check if blocked
        blocked = await db.execute(
            select(CommunityBlockedMember).where(
                and_(CommunityBlockedMember.community_id == community_id, CommunityBlockedMember.user_id == user_id)
            )
        )
        if blocked.scalar_one_or_none():
            return False

        existing = await db.execute(
            select(CommunityMember).where(
                and_(CommunityMember.community_id == community_id, CommunityMember.user_id == user_id)
            )
        )
        if existing.scalar_one_or_none():
            return False

        member = CommunityMember(community_id=community_id, user_id=user_id, role=CommunityRole.member)
        db.add(member)

        await db.execute(
            Community.__table__.update()
            .where(Community.id == community_id)
            .values(members_count=Community.members_count + 1)
        )
        await db.commit()
        return True

    @staticmethod
    async def leave(community_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> bool:
        result = await db.execute(
            select(CommunityMember).where(
                and_(CommunityMember.community_id == community_id, CommunityMember.user_id == user_id)
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            return False

        await db.delete(member)
        await db.execute(
            Community.__table__.update()
            .where(Community.id == community_id)
            .values(members_count=Community.members_count - 1)
        )
        await db.commit()
        return True

    @staticmethod
    async def get_members(community_id: uuid.UUID, db: AsyncSession):
        result = await db.execute(
            select(CommunityMember).where(CommunityMember.community_id == community_id)
            .order_by(CommunityMember.joined_at.asc())
        )
        return result.scalars().all()

    @staticmethod
    async def is_member(community_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> bool:
        result = await db.execute(
            select(CommunityMember).where(
                and_(CommunityMember.community_id == community_id, CommunityMember.user_id == user_id)
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def discover(user_id: uuid.UUID, db: AsyncSession, page: int = 1, limit: int = 20):
        """Communities the user has NOT joined."""
        offset = (page - 1) * limit
        my_ids = select(CommunityMember.community_id).where(CommunityMember.user_id == user_id)
        result = await db.execute(
            select(Community)
            .where(Community.id.notin_(my_ids))
            .order_by(Community.members_count.desc(), Community.created_at.desc())
            .offset(offset).limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def block_member(
        community_id: uuid.UUID, user_id: uuid.UUID,
        blocked_by: uuid.UUID, db: AsyncSession,
        reason: str | None = None,
    ) -> bool:
        # Only admin/moderator can block
        blocker = await db.execute(
            select(CommunityMember).where(
                and_(CommunityMember.community_id == community_id, CommunityMember.user_id == blocked_by)
            )
        )
        blocker_member = blocker.scalar_one_or_none()
        if not blocker_member or blocker_member.role not in (CommunityRole.admin, CommunityRole.moderator):
            return False

        # Can't block yourself or another admin
        if user_id == blocked_by:
            return False
        target = await db.execute(
            select(CommunityMember).where(
                and_(CommunityMember.community_id == community_id, CommunityMember.user_id == user_id)
            )
        )
        target_member = target.scalar_one_or_none()
        if target_member and target_member.role == CommunityRole.admin:
            return False

        # Already blocked?
        existing = await db.execute(
            select(CommunityBlockedMember).where(
                and_(CommunityBlockedMember.community_id == community_id, CommunityBlockedMember.user_id == user_id)
            )
        )
        if existing.scalar_one_or_none():
            return False

        # Remove from members if present
        if target_member:
            await db.delete(target_member)
            await db.execute(
                Community.__table__.update()
                .where(Community.id == community_id)
                .values(members_count=Community.members_count - 1)
            )

        block = CommunityBlockedMember(
            community_id=community_id, user_id=user_id,
            blocked_by=blocked_by, reason=reason,
        )
        db.add(block)
        await db.commit()
        return True

    @staticmethod
    async def unblock_member(
        community_id: uuid.UUID, user_id: uuid.UUID,
        unblocked_by: uuid.UUID, db: AsyncSession,
    ) -> bool:
        # Only admin can unblock
        unblocker = await db.execute(
            select(CommunityMember).where(
                and_(CommunityMember.community_id == community_id, CommunityMember.user_id == unblocked_by)
            )
        )
        unblocker_member = unblocker.scalar_one_or_none()
        if not unblocker_member or unblocker_member.role != CommunityRole.admin:
            return False

        result = await db.execute(
            select(CommunityBlockedMember).where(
                and_(CommunityBlockedMember.community_id == community_id, CommunityBlockedMember.user_id == user_id)
            )
        )
        blocked = result.scalar_one_or_none()
        if not blocked:
            return False

        await db.delete(blocked)

        # Réajouter l'utilisateur comme membre
        existing = await db.execute(
            select(CommunityMember).where(
                and_(CommunityMember.community_id == community_id, CommunityMember.user_id == user_id)
            )
        )
        if not existing.scalar_one_or_none():
            db.add(CommunityMember(
                community_id=community_id,
                user_id=user_id,
                role=CommunityRole.member,
            ))

        await db.commit()
        return True

    @staticmethod
    async def get_blocked(community_id: uuid.UUID, db: AsyncSession):
        result = await db.execute(
            select(CommunityBlockedMember).where(CommunityBlockedMember.community_id == community_id)
        )
        return result.scalars().all()

    @staticmethod
    async def is_blocked(community_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> bool:
        result = await db.execute(
            select(CommunityBlockedMember).where(
                and_(CommunityBlockedMember.community_id == community_id, CommunityBlockedMember.user_id == user_id)
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def get_member_role(community_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> str | None:
        result = await db.execute(
            select(CommunityMember).where(
                and_(CommunityMember.community_id == community_id, CommunityMember.user_id == user_id)
            )
        )
        member = result.scalar_one_or_none()
        return member.role.value if member else None

    @staticmethod
    async def send_message(
        community_id: uuid.UUID, sender_id: uuid.UUID,
        content: str, db: AsyncSession,
    ) -> CommunityMessage:
        # Vérifier que l'utilisateur est membre et pas bloqué
        is_member = await db.execute(
            select(CommunityMember).where(
                and_(CommunityMember.community_id == community_id, CommunityMember.user_id == sender_id)
            )
        )
        if not is_member.scalar_one_or_none():
            raise ValueError("Not a member")

        is_blocked = await CommunityService.is_blocked(community_id, sender_id, db)
        if is_blocked:
            raise ValueError("Blocked from community")

        msg = CommunityMessage(
            community_id=community_id,
            sender_id=sender_id,
            content=content.strip(),
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return msg

    @staticmethod
    async def get_messages(
        community_id: uuid.UUID, db: AsyncSession,
        page: int = 1, limit: int = 30,
    ):
        offset = (page - 1) * limit
        result = await db.execute(
            select(CommunityMessage)
            .where(CommunityMessage.community_id == community_id)
            .order_by(CommunityMessage.created_at.desc())
            .offset(offset).limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def edit_message(
        message_id: uuid.UUID, user_id: uuid.UUID,
        new_content: str, db: AsyncSession,
    ) -> CommunityMessage | None:
        from datetime import datetime
        result = await db.execute(
            select(CommunityMessage).where(CommunityMessage.id == message_id)
        )
        msg = result.scalar_one_or_none()
        if not msg or msg.sender_id != user_id:
            return None
        msg.content = new_content.strip()
        msg.edited_at = datetime.utcnow()
        await db.commit()
        await db.refresh(msg)
        return msg

    @staticmethod
    async def delete_message(
        message_id: uuid.UUID, user_id: uuid.UUID,
        db: AsyncSession,
    ) -> str | None:
        """Returns community_id as str if deleted, None otherwise."""
        result = await db.execute(
            select(CommunityMessage).where(CommunityMessage.id == message_id)
        )
        msg = result.scalar_one_or_none()
        if not msg:
            return None
        # Le sender ou un admin/mod peut supprimer
        if msg.sender_id != user_id:
            role = await CommunityService.get_member_role(msg.community_id, user_id, db)
            if role not in ("admin", "moderator"):
                return None
        community_id = str(msg.community_id)
        await db.delete(msg)
        await db.commit()
        return community_id
