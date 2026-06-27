"""
Основной модуль приложения MegaSharkAI.

FastAPI приложение с базовыми эндпоинтами и настройками.
"""

import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, status, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from app.config import settings
from app.core.database import init_db, check_db_connection
from app.api.v1.router import api_router
from app.services.cache_service import init_cache, close_cache, cache_service

# ====================
# Инициализация приложения
# ====================

# В production Swagger/OpenAPI отключены (разведка API)
_api_docs_enabled = not settings.is_production


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Жизненный цикл приложения (современная замена on_event startup/shutdown).

    Код до ``yield`` выполняется при запуске, после ``yield`` — при остановке.
    """
    # --- Startup ---
    logger.info(f"🦈 {settings.app_name} запускается...")
    logger.info(f"Версия: {settings.app_version}")
    logger.info(f"Debug режим: {settings.debug}")
    settings.validate_startup_safety()

    # В production схему меняет Alembic перед стартом контейнера.
    # create_all оставляем только для локальной разработки, чтобы не обходить миграции.
    if settings.is_production:
        logger.info("Production режим: создание таблиц через create_all пропущено")
    else:
        logger.info("Инициализация базы данных...")
        await init_db()
        logger.info("База данных инициализирована ✓")

    # Инициализация Redis кэша
    logger.info("Инициализация Redis кэша...")
    try:
        await init_cache(
            host=settings.redis_host,
            port=int(settings.redis_port),
            db=settings.redis_db,
            password=settings.redis_password,
        )
        logger.info("Redis кэш инициализирован ✓")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось подключиться к Redis: {e}")

    # Инициализация пула прокси
    logger.info("Инициализация пула прокси...")
    try:
        from app.services.proxy_pool import init_proxy_pool
        proxies = settings.proxies
        if proxies:
            init_proxy_pool(proxies)
            logger.info(f"✅ Пул прокси инициализирован: {len(proxies)} шт")
        else:
            logger.warning("⚠️ Прокси не настроены")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации прокси: {e}")

    # Инициализация Email сервиса
    logger.info("Инициализация Email сервиса...")
    try:
        from app.services.email import EmailService

        # Глобальная инициализация
        import app.services.email as email_module
        email_module.email_service = EmailService(
            smtp_host=getattr(settings, 'smtp_host', 'smtp.gmail.com'),
            smtp_port=getattr(settings, 'smtp_port', 587),
            smtp_user=getattr(settings, 'smtp_user', None),
            smtp_password=getattr(settings, 'smtp_password', None),
            from_email=getattr(settings, 'from_email', None),
            use_tls=getattr(settings, 'use_tls', True),
        )
        logger.info("Email сервис инициализирован ✓")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось инициализировать Email сервис: {e}")

    yield

    # --- Shutdown ---
    logger.info("🦈 Приложение останавливается...")
    await close_cache()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-ассистент для продавцов маркетплейсов",
    docs_url="/docs" if _api_docs_enabled else None,
    redoc_url="/redoc" if _api_docs_enabled else None,
    openapi_url="/openapi.json" if _api_docs_enabled else None,
    lifespan=lifespan,
)

# ====================
# Middleware
# ====================

# CORS настройки
cors_origins = settings.cors_origins if hasattr(settings, 'cors_origins') and settings.cors_origins else ["*"]

if settings.debug and "*" in cors_origins:
    # В dev разрешаем локальный frontend, но не используем wildcard с credentials.
    cors_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

logger.info(f"CORS origins: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
    "proxy-authorization",
}


def sanitize_headers(headers) -> dict:
    """Маскирует чувствительные заголовки перед записью в логи."""
    sanitized = {}
    for key, value in dict(headers).items():
        if key.lower() in SENSITIVE_HEADERS:
            sanitized[key] = "***"
        else:
            sanitized[key] = value
    return sanitized


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Базовые security-заголовки для всех ответов."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Публичный фрейм виджета должен встраиваться на сторонних сайтах,
    # поэтому для него не запрещаем фрейминг (CSP frame-ancestors задаётся в роуте).
    is_widget_frame = (
        request.url.path.startswith("/api/v1/widget/public/")
        and request.url.path.endswith("/frame")
    )
    if not is_widget_frame:
        response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Добавляет заголовок со временем выполнения запроса."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time, 3))
    response.headers["X-Service-Name"] = settings.app_name
    # Запрещаем кэширование ошибок
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Логирование запросов."""
    logger.info(f"📥 {request.method} {request.url.path} - Client: {request.client}")
    logger.debug(f"📨 Headers: {sanitize_headers(request.headers)}")
    try:
        response = await call_next(request)
        logger.info(f"📤 Response: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"❌ Ошибка в запросе {request.method} {request.url.path}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"detail": "Внутренняя ошибка сервера"},
        )


# ====================
# Health Check эндпоинты
# ====================

@app.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Проверка здоровья сервиса",
    description="Возвращает статус работы приложения",
    tags=["Health"],
)
async def health_check():
    """
    Базовая проверка работоспособности сервиса.
    
    Returns:
        dict: Статус приложения
    """
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@app.get(
    "/health/db",
    status_code=status.HTTP_200_OK,
    summary="Проверка подключения к базе данных",
    description="Проверяет подключение к PostgreSQL",
    tags=["Health"],
)
async def health_check_db():
    """
    Проверка подключения к базе данных.
    
    Returns:
        dict: Статус подключения к БД
    """
    is_connected = await check_db_connection()
    
    if is_connected:
        payload = {
            "status": "ok",
            "database": "postgresql",
        }
        if not settings.is_production:
            payload.update({
                "host": settings.postgres_host,
                "port": settings.postgres_port,
                "db_name": settings.postgres_db,
            })
        return payload
    else:
        return {
            "status": "error",
            "database": "postgresql",
            "message": "Не удалось подключиться к базе данных",
        }


@app.get(
    "/health/redis",
    status_code=status.HTTP_200_OK,
    summary="Проверка подключения к Redis",
    description="Проверяет подключение к Redis (Celery broker)",
    tags=["Health"],
)
async def health_check_redis():
    """
    Проверка подключения к Redis.
    
    Returns:
        dict: Статус подключения к Redis
    """
    is_connected = await cache_service.ping()
    if not is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Не удалось подключиться к Redis",
        )

    return {
        "status": "ok",
        "redis": "connected" if settings.is_production else settings.redis_host,
    }


# ====================
# Корневой эндпоинт
# ====================

@app.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Информация о сервисе",
    tags=["Root"],
)
async def root():
    """
    Корневой эндпоинт с информацией о сервисе.
    """
    return {
        "message": "Добро пожаловать в MegaSharkAI API 🦈",
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
        "api_v1": "/api/v1",
    }


# ====================
# API v1 Роуты
# ====================

# ====================
# Статика (сгенерированные изображения и пр.)
# ====================
# Папка для медиа (AI-изображения и т.п.). Создаём при старте, чтобы mount не упал.
MEDIA_ROOT = Path(__file__).resolve().parent.parent / "media"
(MEDIA_ROOT / "ai_images").mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(MEDIA_ROOT)), name="media")


app.include_router(api_router, prefix="/api/v1")

from app.api.v1.marketplace_keys import router as marketplace_keys_router
app.include_router(marketplace_keys_router, prefix="/api/v1", tags=["Маркетплейсы"])

# WebSocket роутеры
from app.websocket.chat import router as ws_chat_router
app.include_router(ws_chat_router, prefix="/ws", tags=["WebSocket"])
