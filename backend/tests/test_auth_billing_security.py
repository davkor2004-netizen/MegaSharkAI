"""
Regression-тесты для auth/security и billing-контрактов.
"""

import json
from uuid import UUID

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.tariff import Tariff
from app.models.user import User


def _set_cookie_headers(response) -> list[str]:
    """Все заголовки Set-Cookie из ответа (совместимо с httpx/requests)."""
    headers = response.headers
    if hasattr(headers, "get_list"):
        return headers.get_list("set-cookie")
    raw = headers.get("set-cookie")
    return [raw] if raw else []


def _cookie_attr(response, cookie_name: str, attr: str):
    """Достать атрибут (например, Max-Age) cookie из Set-Cookie заголовков."""
    for header in _set_cookie_headers(response):
        if header.startswith(f"{cookie_name}="):
            for part in header.split(";"):
                part = part.strip()
                if part.lower().startswith(f"{attr.lower()}="):
                    return part.split("=", 1)[1]
    return None


def _cookie_max_age(response, cookie_name: str):
    """Max-Age cookie в секундах (или None, если cookie не выставлен)."""
    value = _cookie_attr(response, cookie_name, "max-age")
    return int(value) if value is not None else None


def register_user(client, email: str, password: str = "TestPass123!") -> dict:
    """Создать пользователя через публичный API регистрации."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Тестовый Пользователь",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(client, email: str) -> tuple[dict[str, str], dict]:
    """Зарегистрировать пользователя и вернуть Authorization header."""
    payload = register_user(client, email=email)
    return {"Authorization": f"Bearer {payload['access_token']}"}, payload


async def make_superuser(db_session, user_id: str) -> None:
    """Выдать пользователю права администратора в тестовой БД."""
    result = await db_session.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one()
    user.is_superuser = True
    await db_session.commit()


async def deactivate_user(db_session, user_id: str) -> None:
    """Деактивировать пользователя в тестовой БД."""
    result = await db_session.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one()
    user.is_active = False
    await db_session.commit()


async def create_tariff(db_session, code: str = "pro", active: bool = True) -> Tariff:
    """Создать тариф для billing-тестов."""
    tariff = Tariff(
        name="Pro",
        code=code,
        price_monthly=2490.0,
        price_yearly=23900.0,
        trial_days=7,
        is_active=active,
        limits=json.dumps({"max_products": 500}),
        features=json.dumps({"monitoring": ["До 500 товаров"]}),
        sort_order=1,
    )
    db_session.add(tariff)
    await db_session.commit()
    await db_session.refresh(tariff)
    return tariff


def test_register_duplicate_email_rejected(client):
    """Повторная регистрация одного email не создаёт второй аккаунт."""
    email = "duplicate@example.com"
    register_user(client, email=email)

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "AnotherPass123!",
            "full_name": "Дубликат",
        },
    )

    assert response.status_code == 400
    assert "уже существует" in response.json()["detail"]


@pytest.mark.asyncio
async def test_inactive_user_cannot_login_or_use_token(client, db_session):
    """Деактивированный пользователь не может логиниться и использовать старый JWT."""
    payload = register_user(client, email="inactive@example.com")
    await deactivate_user(db_session, payload["user"]["id"])

    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "inactive@example.com", "password": "TestPass123!"},
    )
    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )

    assert login_response.status_code == 403
    assert me_response.status_code == 401


def test_login_without_remember_me_sets_default_session(client):
    """Логин без remember_me выставляет refresh-cookie с обычным сроком."""
    register_user(client, email="remember-default@example.com")

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "remember-default@example.com", "password": "TestPass123!"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"

    access_max_age = _cookie_max_age(response, "access_token")
    refresh_max_age = _cookie_max_age(response, "refresh_token")

    assert access_max_age == settings.access_token_expire_minutes * 60
    assert refresh_max_age == settings.refresh_token_expire_days * 24 * 60 * 60


def test_login_with_remember_me_extends_refresh_cookie(client):
    """remember_me=true продлевает refresh-cookie, не трогая access TTL."""
    register_user(client, email="remember-on@example.com")

    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "remember-on@example.com",
            "password": "TestPass123!",
            "remember_me": "true",
        },
    )

    assert response.status_code == 200

    access_max_age = _cookie_max_age(response, "access_token")
    refresh_max_age = _cookie_max_age(response, "refresh_token")

    # Access-токен остаётся короткоживущим.
    assert access_max_age == settings.access_token_expire_minutes * 60
    # Refresh-сессия дольше обычной.
    assert refresh_max_age == settings.remember_me_refresh_token_expire_days * 24 * 60 * 60
    assert refresh_max_age > settings.refresh_token_expire_days * 24 * 60 * 60


def test_login_backward_compatible_payload(client):
    """Старый payload без remember_me продолжает работать (200 + сессия)."""
    register_user(client, email="legacy-login@example.com")

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "legacy-login@example.com", "password": "TestPass123!"},
    )

    assert response.status_code == 200
    assert _cookie_max_age(response, "refresh_token") == (
        settings.refresh_token_expire_days * 24 * 60 * 60
    )


def test_refresh_issues_new_access_token(client):
    """/auth/refresh по refresh-cookie выпускает новый access и оставляет сессию рабочей."""
    register_user(client, email="refresh-flow@example.com")
    client.post(
        "/api/v1/auth/login",
        data={"username": "refresh-flow@example.com", "password": "TestPass123!"},
    )

    refresh_response = client.post("/api/v1/auth/refresh")
    me_response = client.get("/api/v1/auth/me")

    assert refresh_response.status_code == 200
    assert _cookie_max_age(refresh_response, "access_token") == (
        settings.access_token_expire_minutes * 60
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "refresh-flow@example.com"


def test_refresh_without_cookie_rejected(client):
    """Без refresh-cookie обновление сессии возвращает 401."""
    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 401


def test_logout_clears_session_cookies(client):
    """Logout удаляет и access, и refresh cookie независимо от remember_me."""
    register_user(client, email="logout-flow@example.com")
    client.post(
        "/api/v1/auth/login",
        data={
            "username": "logout-flow@example.com",
            "password": "TestPass123!",
            "remember_me": "true",
        },
    )

    logout_response = client.post("/api/v1/auth/logout")

    assert logout_response.status_code == 200
    # Cookie помечаются на удаление (Max-Age=0 в delete_cookie).
    assert _cookie_max_age(logout_response, "access_token") == 0
    assert _cookie_max_age(logout_response, "refresh_token") == 0


@pytest.mark.asyncio
async def test_ai_settings_require_superuser(client, db_session):
    """AI settings доступны только администратору."""
    user_headers, _ = auth_headers(client, "ai-regular@example.com")
    admin_headers, admin_payload = auth_headers(client, "ai-admin@example.com")
    await make_superuser(db_session, admin_payload["user"]["id"])

    regular_response = client.get("/api/v1/ai/settings", headers=user_headers)
    admin_response = client.get("/api/v1/ai/settings", headers=admin_headers)

    assert regular_response.status_code == 403
    assert admin_response.status_code == 200
    assert admin_response.json()["provider"] == "none"


def test_billing_current_requires_auth(client):
    """Текущая подписка недоступна без JWT."""
    response = client.get("/api/v1/billing/current")

    assert response.status_code == 401


def test_billing_current_without_subscription(client):
    """Пользователь без подписки получает честный status=none."""
    headers, _ = auth_headers(client, "billing-none@example.com")

    response = client.get("/api/v1/billing/current", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "none"
    assert data["tariff_code"] is None


@pytest.mark.asyncio
async def test_billing_subscribe_validates_cycle_and_prevents_duplicate(client, db_session):
    """Billing принимает только known cycle и не создаёт вторую активную подписку."""
    await create_tariff(db_session, code="pro")
    headers, _ = auth_headers(client, "billing-subscribe@example.com")

    invalid_cycle_response = client.post(
        "/api/v1/billing/subscribe",
        json={"tariff_code": "pro", "billing_cycle": "weekly"},
        headers=headers,
    )
    subscribe_response = client.post(
        "/api/v1/billing/subscribe",
        json={"tariff_code": "pro", "billing_cycle": "yearly"},
        headers=headers,
    )
    duplicate_response = client.post(
        "/api/v1/billing/subscribe",
        json={"tariff_code": "pro", "billing_cycle": "monthly"},
        headers=headers,
    )
    current_response = client.get("/api/v1/billing/current", headers=headers)

    assert invalid_cycle_response.status_code == 422
    assert subscribe_response.status_code == 200
    assert subscribe_response.json()["subscription"]["billing_cycle"] == "yearly"
    assert duplicate_response.status_code == 400

    assert current_response.status_code == 200
    current = current_response.json()
    assert current["status"] == "trial"
    assert current["tariff_code"] == "pro"
    assert current["billing_cycle"] == "yearly"
