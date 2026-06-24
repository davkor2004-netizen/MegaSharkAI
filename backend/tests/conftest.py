"""
Конфигурация тестов.

Настройки pytest для тестирования FastAPI приложения.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
import app.models  # noqa: F401 - регистрирует все ORM-модели перед create_all


# Тестовая БД в памяти (SQLite для скорости)
# В реальном проекте лучше использовать test PostgreSQL
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Создаём тестовый движок
test_engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Сессия для тестов
test_session_maker = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(autouse=True)
def isolate_rate_limits(monkeypatch):
    """Сбрасываем rate limit между тестами, чтобы suite не блокировал register."""
    from app.services.rate_limit import rate_limiter

    rate_limiter.reset_memory()
    monkeypatch.setattr("app.config.settings.auth_rate_limit_per_minute", 1000)
    yield
    rate_limiter.reset_memory()


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """
    Фикстура для сессии базы данных.
    
    Создаёт таблицы перед каждым тестом и удаляет после.
    """
    # Создаём таблицы
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Создаём сессию
    async with test_session_maker() as session:
        yield session
    
    # Удаляем таблицы
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """
    Фикстура для тестового клиента FastAPI.
    
    Переопределяет зависимость get_db для использования тестовой БД.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    
    # Переопределяем зависимость
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db

    # Не используем контекстный менеджер TestClient, чтобы не запускать startup
    # с реальными PostgreSQL/Redis в unit-тестах.
    test_client = TestClient(app)

    try:
        yield test_client
    finally:
        # Очищаем overrides
        app.dependency_overrides.clear()
