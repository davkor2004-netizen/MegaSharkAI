"""
Миграция: Делаем поле price nullable в таблице products
"""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Правильный пароль из config.py
DATABASE_URL = "postgresql+asyncpg://megashark:megashark_secret@db:5432/megashark_db"


async def migrate():
    """Применить миграцию."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    try:
        async with engine.connect() as conn:
            await conn.execute(text("""
                ALTER TABLE products 
                ALTER COLUMN price DROP NOT NULL;
            """))
            await conn.commit()
            
            print("✅ Миграция применена: price теперь nullable")
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
