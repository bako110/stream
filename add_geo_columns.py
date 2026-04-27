"""Migration : ajoute latitude/longitude sur events et concerts."""
import asyncio, os, sys
os.chdir('/app')
sys.path.insert(0, '.')

async def main():
    from app.db.postgres.session import AsyncSessionLocal
    from sqlalchemy import text
    async with AsyncSessionLocal() as db:
        await db.execute(text("""
            ALTER TABLE events
              ADD COLUMN IF NOT EXISTS latitude  FLOAT,
              ADD COLUMN IF NOT EXISTS longitude FLOAT;
        """))
        await db.execute(text("""
            ALTER TABLE concerts
              ADD COLUMN IF NOT EXISTS latitude  FLOAT,
              ADD COLUMN IF NOT EXISTS longitude FLOAT;
        """))
        await db.commit()
        print("OK — colonnes latitude/longitude ajoutées sur events et concerts.")

asyncio.run(main())
