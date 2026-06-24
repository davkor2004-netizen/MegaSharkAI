"""
Сервис кэширования на Redis.

Используется для:
- Кэширования результатов парсинга
- Временного хранения данных
- Уменьшения нагрузки на маркетплейсы
"""

import json
from typing import Optional, Any, Dict
from datetime import timedelta
from loguru import logger
import redis.asyncio as redis


class CacheService:
    """
    Сервис для работы с Redis кэшем.
    """
    
    def __init__(self):
        """Инициализация Redis подключения."""
        self.redis: Optional[redis.Redis] = None
        self.default_ttl = timedelta(hours=24)  # Кэш на 24 часа
    
    async def connect(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
    ):
        """
        Подключение к Redis.
        
        Args:
            host: Хост Redis
            port: Порт Redis
            db: Номер базы данных
            password: Пароль Redis, если включён requirepass
        """
        self.redis = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True
        )
        await self.redis.ping()
        logger.info(f"💾 Подключено к Redis: {host}:{port}/{db}")
    
    async def disconnect(self):
        """Отключение от Redis."""
        if self.redis:
            await self.redis.close()
            logger.info("💾 Отключено от Redis")

    async def ping(self) -> bool:
        """Проверка доступности Redis."""
        if not self.redis:
            return False

        try:
            return bool(await self.redis.ping())
        except Exception as e:
            logger.error(f"❌ Redis ping failed: {e}")
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Получение данных из кэша.
        
        Args:
            key: Ключ кэша
            
        Returns:
            Данные или None если не найдено
        """
        if not self.redis:
            return None
        
        try:
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения из кэша: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[timedelta] = None
    ) -> bool:
        """
        Сохранение данных в кэш.
        
        Args:
            key: Ключ кэша
            value: Данные для сохранения
            ttl: Время жизни (по умолчанию 24 часа)
            
        Returns:
            bool: True если успешно
        """
        if not self.redis:
            return False
        
        try:
            expire_seconds = int((ttl or self.default_ttl).total_seconds())
            await self.redis.setex(
                key,
                expire_seconds,
                json.dumps(value, ensure_ascii=False)
            )
            logger.debug(f"✅ Сохранено в кэш: {key} (TTL: {expire_seconds}s)")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в кэш: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Удаление данных из кэша.
        
        Args:
            key: Ключ кэша
            
        Returns:
            bool: True если удалено
        """
        if not self.redis:
            return False
        
        try:
            await self.redis.delete(key)
            logger.debug(f"🗑️ Удалено из кэша: {key}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления из кэша: {e}")
            return False
    
    def _parse_url_key(self, url: str) -> str:
        """
        Создание ключа кэша из URL.
        
        Args:
            url: URL товара
            
        Returns:
            str: Ключ кэша
        """
        # Хэшируем URL для создания короткого ключа
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        return f"parse:wb:{url_hash}"
    
    async def get_parsed_product(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Получение распарсенного товара из кэша.
        
        Args:
            url: URL товара
            
        Returns:
            Dict с данными товара или None
        """
        key = self._parse_url_key(url)
        return await self.get(key)
    
    async def cache_parsed_product(
        self,
        url: str,
        data: Dict[str, Any],
        ttl: Optional[timedelta] = None
    ) -> bool:
        """
        Кэширование результатов парсинга.
        
        Args:
            url: URL товара
            data: Данные товара
            ttl: Время жизни кэша
            
        Returns:
            bool: True если успешно
        """
        key = self._parse_url_key(url)
        return await self.set(key, data, ttl)
    
    async def clear_parse_cache(self):
        """Очистка всего кэша парсинга."""
        if not self.redis:
            return
        
        try:
            keys = await self.redis.keys("parse:*")
            if keys:
                await self.redis.delete(*keys)
                logger.info(f"🗑️ Очищен кэш парсинга: {len(keys)} записей")
        except Exception as e:
            logger.error(f"❌ Ошибка очистки кэша: {e}")


# Глобальный экземпляр сервиса
cache_service = CacheService()


async def init_cache(
    host: str = "localhost",
    port: int = 6379,
    db: int = 0,
    password: Optional[str] = None,
):
    """Инициализация кэш сервиса."""
    await cache_service.connect(host, port, db, password)


async def close_cache():
    """Закрытие подключения к кэшу."""
    await cache_service.disconnect()
