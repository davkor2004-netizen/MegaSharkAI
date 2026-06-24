import asyncio
import os
from app.core.database import engine
from sqlalchemy import text
from app.services.auth_service import verify_password

async def check():
    password_to_check = os.getenv("USER_PASSWORD_TO_CHECK")
    if not password_to_check:
        raise RuntimeError("USER_PASSWORD_TO_CHECK должен быть задан явно")

    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT email, hashed_password FROM users WHERE email = 'user@megashark.ai'"))
        row = result.fetchone()
        if row:
            _, hashed_password = row
            is_valid = verify_password(password_to_check, hashed_password)
            print(f'USER PASSWORD MATCH: {is_valid}')
        else:
            print('USER NOT FOUND')

if __name__ == "__main__":
    asyncio.run(check())
