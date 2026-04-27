from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.postgres.models.user import User, UserRole
from app.utils.password import hash_password

ADMIN_EMAIL      = "admin@folyx.com"
ADMIN_PASSWORD   = "admin123"
ADMIN_FIRST_NAME = "Admin"
ADMIN_LAST_NAME  = "FoliX"
ADMIN_USERNAME   = "folyx_admin"


async def seed_admin(db: AsyncSession) -> None:
    result = await db.execute(select(User).where(User.email == ADMIN_EMAIL))
    existing = result.scalar_one_or_none()
    if existing:
        print(f"   Seed admin : compte déjà présent ({ADMIN_EMAIL})")
        return

    admin = User(
        email=ADMIN_EMAIL,
        password_hash=hash_password(ADMIN_PASSWORD),
        first_name=ADMIN_FIRST_NAME,
        last_name=ADMIN_LAST_NAME,
        username=ADMIN_USERNAME,
        role=UserRole.admin,
        is_verified=True,
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    print(f"   Seed admin : compte créé — {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
