"""
Rate limiting для защиты auth-эндпоинтов от brute-force.

Использует Redis (INCR + EXPIRE), при недоступности Redis — in-memory fallback.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import DefaultDict, List

from fastapi import HTTPException, Request, status
from loguru import logger

from app.config import settings
from app.services.cache_service import cache_service


class RateLimiter:
    """Ограничитель частоты запросов по ключу (IP + scope)."""

    def __init__(self) -> None:
        # Fallback для dev/тестов без Redis: key -> timestamps
        self._memory_hits: DefaultDict[str, List[float]] = defaultdict(list)

    @staticmethod
    def resolve_client_ip(request: Request) -> str:
        """IP клиента с учётом reverse proxy."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    async def check(self, key: str, limit: int, window_seconds: int) -> None:
        """
        Проверить лимит. При превышении — HTTP 429.

        Args:
            key: Уникальный ключ (например auth:127.0.0.1)
            limit: Максимум запросов в окне
            window_seconds: Размер окна в секундах
        """
        if limit <= 0:
            return

        if cache_service.redis:
            allowed = await self._check_redis(key, limit, window_seconds)
        else:
            allowed = self._check_memory(key, limit, window_seconds)

        if not allowed:
            logger.warning(f"🚫 Rate limit: {key} ({limit}/{window_seconds}s)")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много запросов. Попробуйте позже.",
                headers={"Retry-After": str(window_seconds)},
            )

    async def _check_redis(self, key: str, limit: int, window_seconds: int) -> bool:
        redis_key = f"rate_limit:{key}"
        try:
            count = await cache_service.redis.incr(redis_key)
            if count == 1:
                await cache_service.redis.expire(redis_key, window_seconds)
            return count <= limit
        except Exception as exc:
            logger.warning(f"⚠️ Rate limit Redis недоступен, fallback in-memory: {exc}")
            return self._check_memory(key, limit, window_seconds)

    def _check_memory(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        window_start = now - window_seconds
        hits = [ts for ts in self._memory_hits[key] if ts > window_start]
        if len(hits) >= limit:
            self._memory_hits[key] = hits
            return False
        hits.append(now)
        self._memory_hits[key] = hits
        return True

    def reset_memory(self) -> None:
        """Сброс in-memory счётчиков (для тестов)."""
        self._memory_hits.clear()


rate_limiter = RateLimiter()


async def enforce_auth_rate_limit(request: Request) -> None:
    """Лимит на login/register/reset-password по IP."""
    client_ip = RateLimiter.resolve_client_ip(request)
    await rate_limiter.check(
        key=f"auth:{client_ip}",
        limit=settings.auth_rate_limit_per_minute,
        window_seconds=60,
    )
