import asyncio
from app.core.database import engine
from sqlalchemy import text

async def check():
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT email, hashed_password FROM users WHERE email = 'admin@megashark.ai'"))
        row = result.fetchone()
        if row:
            print('EMAIL:', row[0])
            print('HASH STORED:', bool(row[1]))
        else:
            print('USER NOT FOUND')

if __name__ == "__main__":
    asyncio.run(check())
