"""
Конфигурация приложения MegaSharkAI.

Этот модуль загружает все настройки из переменных окружения
и предоставляет единый интерфейс для доступа к ним.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from urllib.parse import quote


class Settings(BaseSettings):
    """
    Основные настройки приложения.
    
    Все значения загружаются из переменных окружения.
    Если переменная не задана, используются значения по умолчанию.
    """
    
    # ====================
    # Приложение
    # ====================
    app_name: str = "MegaSharkAI"
    app_version: str = "0.1.0"
    debug: bool = True
    environment: str = "development"
    
    # ====================
    # База данных PostgreSQL
    # ====================
    postgres_user: str = "megashark"
    postgres_password: str = "megashark_secret"
    postgres_host: str = "db"
    postgres_port: str = "5432"
    postgres_db: str = "megashark_db"
    
    @property
    def database_url(self) -> str:
        """
        Формирует URL подключения к базе данных.
        
        Returns:
            str: PostgreSQL URL в формате postgresql+asyncpg://user:pass@host:port/db
        """
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    # ====================
    # Redis (для Celery)
    # ====================
    redis_host: str = "redis"
    redis_port: str = "6379"
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    @property
    def redis_url(self) -> str:
        """
        Формирует URL подключения к Redis.
        
        Returns:
            str: Redis URL в формате redis://host:port/db
        """
        if self.redis_password:
            password = quote(self.redis_password, safe="")
            return f"redis://:{password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"

        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    # ====================
    # Celery
    # ====================
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None
    
    @property
    def celery_broker(self) -> str:
        """URL брокера для Celery (Redis)."""
        return self.celery_broker_url or self.redis_url
    
    @property
    def celery_backend(self) -> str:
        """URL бэкенда для результатов Celery (Redis)."""
        return self.celery_result_backend or self.redis_url
    
    # ====================
    # AI сервисы
    # ====================
    # Яндекс GPT
    yandex_gpt_api_key: Optional[str] = None
    yandex_cloud_folder_id: Optional[str] = None
    
    # DeepSeek (опционально)
    deepseek_api_key: Optional[str] = None
    
    # OpenAI (опционально)
    openai_api_key: Optional[str] = None
    
    # ====================
    # Парсинг
    # ====================
    playwright_browser: str = "chromium"  # chromium, firefox, webkit
    parsing_timeout: int = 30000  # таймаут в миллисекундах
    
    # Прокси для парсинга (список через запятую)
    proxy_list: Optional[str] = None
    
    @property
    def proxies(self) -> list:
        """
        Получить список прокси из переменных окружения.
        
        Returns:
            list: Список строк формата "ip:port:login:password"
        """
        if self.proxy_list:
            return [p.strip() for p in self.proxy_list.split(',') if p.strip()]
        
        return []
    
    # ====================
    # Безопасность
    # ====================
    secret_key: str = "your-secret-key-change-in-production"
    SECRET_KEY: str = "your-secret-key-change-in-production"  # Алиас для совместимости
    access_token_expire_minutes: int = 30
    # Срок жизни refresh-сессии без "Запомнить меня" (обычная сессия).
    refresh_token_expire_days: int = 7
    # Срок жизни refresh-сессии при включённом "Запомнить меня".
    remember_me_refresh_token_expire_days: int = 30
    # Лимит запросов на auth-эндпоинты с одного IP в минуту
    auth_rate_limit_per_minute: int = 10
    # Максимальный размер XLSX импорта (байты)
    max_import_file_bytes: int = 5 * 1024 * 1024
    
    # Ключ шифрования для API ключей маркетплейсов
    encryption_key: Optional[str] = None
    ENCRYPTION_KEY: Optional[str] = None  # Алиас для совместимости
    
    # ====================
    # Email (SMTP)
    # ====================
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    from_email: Optional[str] = None
    use_tls: bool = True
    
    # URL приложения (для писем)
    app_url: str = "http://localhost:3000"

    # ====================
    # Telegram (для уведомлений)
    # ====================
    # Токен бота для отправки уведомлений (получается у @BotFather).
    telegram_bot_token: Optional[str] = None

    # ====================
    # Репрайсинг
    # ====================
    # Глобальный «рубильник» применения цен на маркетплейсах.
    # Если False — расчёт работает, но реальная отправка цены блокируется.
    repricing_apply_enabled: bool = True
    
    # ====================
    # CORS
    # ====================
    cors_origins: list = ["*"]  # В продакшене: ["https://yourdomain.com"]

    @property
    def is_production(self) -> bool:
        """Определяет production-режим по ENVIRONMENT или DEBUG."""
        return self.environment.lower() in {"production", "prod"} or not self.debug

    def validate_startup_safety(self) -> None:
        """
        Проверяет критические настройки перед запуском production.

        В dev-режиме не блокируем запуск, чтобы не ломать локальную демонстрацию.
        В production запрещаем небезопасные defaults и wildcard CORS.
        """
        if not self.is_production:
            return

        errors: list[str] = []

        if self.debug:
            errors.append("DEBUG должен быть false в production")

        if self.SECRET_KEY == "your-secret-key-change-in-production":
            errors.append("SECRET_KEY должен быть заменён на безопасное значение")

        if not (self.ENCRYPTION_KEY or self.encryption_key):
            errors.append("ENCRYPTION_KEY обязателен в production")

        if "*" in (self.cors_origins or []):
            errors.append("Wildcard CORS запрещён в production")

        if self.postgres_password == "megashark_secret":
            errors.append("POSTGRES_PASSWORD должен быть заменён в production")

        if errors:
            raise RuntimeError("Небезопасная production-конфигурация: " + "; ".join(errors))
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Глобальный экземпляр настроек
settings = Settings()
