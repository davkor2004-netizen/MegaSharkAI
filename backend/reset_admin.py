import asyncio
import os
from app.core.database import engine
from sqlalchemy import text
from app.services.auth_service import get_password_hash

async def reset():
    new_password = os.getenv("ADMIN_NEW_PASSWORD")
    if not new_password:
        raise RuntimeError("ADMIN_NEW_PASSWORD должен быть задан явно")

    async with engine.begin() as conn:
        new_hash = get_password_hash(new_password)
        await conn.execute(
            text("UPDATE users SET hashed_password = :hash WHERE email = 'admin@megashark.ai'"),
            {"hash": new_hash}
        )
        print('Admin password reset successfully')

if __name__ == "__main__":
    asyncio.run(reset())
