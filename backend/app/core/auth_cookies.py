"""
HttpOnly cookies для JWT-сессии.
"""

from fastapi import Response

from app.config import settings

ACCESS_TOKEN_COOKIE_NAME = "access_token"
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"
# Refresh-cookie нужен только auth-эндпоинтам (refresh/logout/me),
# поэтому ограничиваем path — он не уходит на остальные API-запросы.
REFRESH_TOKEN_COOKIE_PATH = "/api/v1/auth"


def set_access_token_cookie(response: Response, token: str) -> None:
    """Установить HttpOnly cookie с access JWT (короткоживущий)."""
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


def clear_access_token_cookie(response: Response) -> None:
    """Удалить cookie сессии."""
    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
    )


def set_refresh_token_cookie(response: Response, token: str, max_age_seconds: int) -> None:
    """
    Установить HttpOnly cookie с refresh JWT.

    Срок жизни (max_age) задаётся отдельно: он определяет длительность сессии
    ("Запомнить меня" продлевает именно его, а не access-токен).
    """
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=max_age_seconds,
        path=REFRESH_TOKEN_COOKIE_PATH,
    )


def clear_refresh_token_cookie(response: Response) -> None:
    """Удалить refresh cookie (logout)."""
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        path=REFRESH_TOKEN_COOKIE_PATH,
        httponly=True,
        samesite="lax",
    )
