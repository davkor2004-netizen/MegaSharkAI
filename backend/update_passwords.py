from passlib.context import CryptContext
import asyncpg
import asyncio

ctx = CryptContext(schemes=["bcrypt"])

# Пароли
passwords = {
    "admin@megashark.ai": "AdminPass123!",
    "test.seller@megashark.ai": "TestSeller123!",
}

async def main():
    conn = await asyncpg.connect(
        host="db",
        user="megashark",
        password="megashark_secret",
        database="megashark_db"
    )
    
    for email, password in passwords.items():
        hashed = ctx.hash(password)
        await conn.execute(
            "UPDATE users SET hashed_password = $1 WHERE email = $2",
            hashed, email
        )
        print(f"✅ Updated {email}")
    
    await conn.close()

asyncio.run(main())
