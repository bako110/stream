import asyncio
from app.db.postgres import AsyncSessionLocal
from app.utils.cache import cache_invalidate_prefix
from sqlalchemy import text

async def fix():
    async with AsyncSessionLocal() as db:
        r = await db.execute(text("SELECT status, COUNT(*) FROM reels GROUP BY status"))
        rows = r.all()
        print("Statuts actuels:", rows)

        result = await db.execute(text("UPDATE reels SET status='published' WHERE status != 'published'"))
        await db.commit()
        print(f"{result.rowcount} reel(s) mis a jour en published")

    # Invalider le cache feed
    await cache_invalidate_prefix("fil_utilisateur:")
    await cache_invalidate_prefix("fil_anonymous:")
    print("Cache feed invalide")

asyncio.run(fix())
