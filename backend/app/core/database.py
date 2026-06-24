"""
Конфигурация подключения к базе данных PostgreSQL.

Используется SQLAlchemy 2.0 с асинхронным драйвером asyncpg.
pgvector добавляется для векторного поиска (AI-аналитика).
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# ====================
# Движок базы данных
# ====================

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # Логирование SQL-запросов в debug режиме
    pool_pre_ping=True,  # Проверка подключения перед использованием
    pool_size=10,  # Размер пула подключений
    max_overflow=20,  # Максимум дополнительных подключений
    pool_recycle=3600,  # Переподключение через 1 час
)

# ====================
# Сессия базы данных
# ====================

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """
    Зависимость FastAPI для получения сессии БД.
    
    Использование в эндпоинтах:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    
    Yields:
        AsyncSession: Асинхронная сессия базы данных
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    Инициализация базы данных.
    
    Создаёт все таблицы, если они не существуют.
    Вызывается при запуске приложения.
    """
    import app.models  # noqa: F401 - регистрирует все ORM-модели в metadata
    from app.models.base import Base
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def check_db_connection() -> bool:
    """
    Проверка подключения к базе данных.
    
    Returns:
        bool: True если подключение успешно, иначе False
    """
    try:
        async with async_session_maker() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# ====================
# Базовый класс для моделей
# ====================

class Base(DeclarativeBase):
    """
    Базовый класс для всех ORM-моделей.
    
    Все модели должны наследоваться от этого класса.
    """
    pass
