"""
Тесты эндпоинтов виджета (/api/v1/widget/config, rotate-key).

Регрессия: GET /config падал с 500 для пользователей с подпиской из-за
ленивой загрузки subscription.tariff в async-контексте (MissingGreenlet).
Теперь:
- нет доступа по тарифу → 402 (locked), а не 500;
- доступный тариф → 200 с автосозданием default-конфига (public_key + embed_code).
"""

import json
from uuid import UUID

import pytest

from app.models.tariff import Tariff, UserSubscription


def register_user(client, email: str, password: str = "TestPass123!") -> dict:
    """Создать пользователя через публичный API регистрации."""
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Виджет Тест"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(client, email: str) -> tuple[dict[str, str], dict]:
    """Зарегистрировать пользователя и вернуть Authorization header."""
    payload = register_user(client, email=email)
    return {"Authorization": f"Bearer {payload['access_token']}"}, payload


async def give_subscription(db_session, user_id: str, widget_access: bool) -> None:
    """Создать активную подписку на тариф с заданным widget_access."""
    tariff = Tariff(
        name="Business" if widget_access else "Start",
        code="business" if widget_access else "start",
        price_monthly=4990.0,
        price_yearly=49900.0,
        trial_days=7,
        is_active=True,
        limits=json.dumps({"widget_access": widget_access, "max_products": 500}),
        features=json.dumps({}),
        sort_order=1,
    )
    db_session.add(tariff)
    await db_session.commit()
    await db_session.refresh(tariff)

    subscription = UserSubscription(
        user_id=UUID(user_id),
        tariff_id=tariff.id,
        status="active",
        is_trial=False,
        billing_cycle="monthly",
    )
    db_session.add(subscription)
    await db_session.commit()


@pytest.mark.asyncio
async def test_widget_config_locked_without_subscription(client, db_session):
    """Без подписки виджет недоступен → 402 (locked), не 500."""
    headers, _ = auth_headers(client, "widget-nosub@example.com")

    response = client.get("/api/v1/widget/config", headers=headers)

    assert response.status_code == 402


@pytest.mark.asyncio
async def test_widget_config_locked_for_tariff_without_widget_access(client, db_session):
    """Подписка на тариф без widget_access → 402, а не 500 (регрессия lazy-load)."""
    headers, payload = auth_headers(client, "widget-basic@example.com")
    await give_subscription(db_session, payload["user"]["id"], widget_access=False)

    response = client.get("/api/v1/widget/config", headers=headers)

    assert response.status_code == 402


@pytest.mark.asyncio
async def test_widget_config_created_for_allowed_tariff(client, db_session):
    """Доступный тариф → 200 и автосоздание default-конфига с ключом и кодом вставки."""
    headers, payload = auth_headers(client, "widget-ok@example.com")
    await give_subscription(db_session, payload["user"]["id"], widget_access=True)

    response = client.get("/api/v1/widget/config", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["public_key"]
    assert "widget.js" in data["embed_code"]
    assert data["public_key"] in data["embed_code"]
    assert data["title"]
    assert data["is_enabled"] is True


@pytest.mark.asyncio
async def test_widget_config_get_is_idempotent(client, db_session):
    """Повторный GET не создаёт новый конфиг — ключ стабилен."""
    headers, payload = auth_headers(client, "widget-idem@example.com")
    await give_subscription(db_session, payload["user"]["id"], widget_access=True)

    first = client.get("/api/v1/widget/config", headers=headers).json()
    second = client.get("/api/v1/widget/config", headers=headers).json()

    assert first["public_key"] == second["public_key"]


@pytest.mark.asyncio
async def test_widget_config_update_persists(client, db_session):
    """PUT /config сохраняет настройки и возвращает success."""
    headers, payload = auth_headers(client, "widget-put@example.com")
    await give_subscription(db_session, payload["user"]["id"], widget_access=True)

    update_response = client.put(
        "/api/v1/widget/config",
        headers=headers,
        json={
            "is_enabled": False,
            "title": "Мой магазин",
            "welcome_message": "Привет!",
            "accent_color": "#123abc",
            "allowed_origins": "example.com",
        },
    )
    persisted = client.get("/api/v1/widget/config", headers=headers).json()

    assert update_response.status_code == 200
    assert update_response.json()["status"] == "success"
    assert persisted["title"] == "Мой магазин"
    assert persisted["is_enabled"] is False
    assert persisted["allowed_origins"] == "example.com"


@pytest.mark.asyncio
async def test_widget_rotate_key_changes_public_key(client, db_session):
    """rotate-key выдаёт новый публичный ключ (старый код вставки инвалидируется)."""
    headers, payload = auth_headers(client, "widget-rotate@example.com")
    await give_subscription(db_session, payload["user"]["id"], widget_access=True)

    before = client.get("/api/v1/widget/config", headers=headers).json()["public_key"]
    rotate_response = client.post("/api/v1/widget/rotate-key", headers=headers)

    assert rotate_response.status_code == 200
    after = rotate_response.json()["public_key"]
    assert after
    assert after != before


@pytest.mark.asyncio
async def test_widget_config_update_locked_without_access(client, db_session):
    """PUT тоже защищён тарифом: без widget_access → 402."""
    headers, payload = auth_headers(client, "widget-put-locked@example.com")
    await give_subscription(db_session, payload["user"]["id"], widget_access=False)

    response = client.put(
        "/api/v1/widget/config",
        headers=headers,
        json={
            "is_enabled": True,
            "title": "X",
            "welcome_message": "Y",
            "accent_color": "#000000",
            "allowed_origins": None,
        },
    )

    assert response.status_code == 402
