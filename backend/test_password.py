from passlib.context import CryptContext
import asyncpg
import asyncio
import os

ctx = CryptContext(schemes=["bcrypt"])

async def main():
    conn = await asyncpg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        user=os.getenv("POSTGRES_USER", "megashark"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        database=os.getenv("POSTGRES_DB", "megashark_db"),
    )
    
    # Получаем хеш админа
    admin_email = os.getenv("ADMIN_EMAIL", "admin@megashark.ai")
    test_password = os.getenv("ADMIN_TEST_PASSWORD", "")

    if not test_password:
        raise RuntimeError("ADMIN_TEST_PASSWORD должен быть задан явно для проверки пароля")

    row = await conn.fetchrow("SELECT hashed_password FROM users WHERE email = $1", admin_email)
    if not row:
        raise RuntimeError("Пользователь для проверки не найден")

    hashed_password = row['hashed_password']
    
    print(f"Hash from DB: {hashed_password}")
    print(f"Hash length: {len(hashed_password)}")
    
    # Пробуем проверить пароль
    try:
        is_valid = ctx.verify(test_password, hashed_password)
        print(f"✅ Password verification: {is_valid}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
