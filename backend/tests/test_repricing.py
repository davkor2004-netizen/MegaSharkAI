"""
Unit-тесты формул репрайсинга.
"""

import pytest
from fastapi import HTTPException
from uuid import UUID

from app.api.v1.repricing import calculate_recommended_price, round_to_pretty_market_price
from app.models.product import Product


def auth_headers(client, email: str) -> tuple[dict[str, str], dict]:
    """Создать пользователя и вернуть JWT header вместе с payload регистрации."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "TestPass123!",
            "full_name": "Тестовый Пользователь",
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    return {"Authorization": f"Bearer {payload['access_token']}"}, payload


def test_round_to_pretty_market_price():
    """Цена округляется к маркетплейсному виду и не падает ниже 100."""
    assert round_to_pretty_market_price(1234) == 1229.0
    assert round_to_pretty_market_price(51) == 100.0


def test_aggressive_strategy_uses_min_competitor_price():
    """Aggressive стратегия ставит цену ниже минимальной цены конкурента."""
    price, source, reason = calculate_recommended_price(
        current_price=2000,
        strategy="aggressive",
        target_margin=30,
        competitor_prices=[1900, 2100, 2200],
    )

    assert price == 1805.0
    assert source == "competitors"
    assert "Агрессивная" in reason


def test_margin_protection_strategy_uses_average_plus_margin():
    """Margin protection считает от средней цены конкурентов + целевая маржа."""
    price, source, reason = calculate_recommended_price(
        current_price=2000,
        strategy="margin_protection",
        target_margin=20,
        competitor_prices=[1000, 2000],
    )

    assert price == 1800.0
    assert source == "competitors"
    assert "маржи" in reason


def test_night_strategy_uses_current_price():
    """Night стратегия снижает текущую цену на 10%."""
    price, source, reason = calculate_recommended_price(
        current_price=2000,
        strategy="night",
        target_margin=30,
        competitor_prices=[1000, 2000],
    )

    assert price == 1800.0
    assert source == "mixed"
    assert "Ночная" in reason


def test_balanced_strategy_between_min_and_average():
    """Balanced стратегия берёт среднее между min и avg ценой конкурентов."""
    price, source, reason = calculate_recommended_price(
        current_price=2000,
        strategy="balanced",
        target_margin=30,
        competitor_prices=[1000, 2000, 3000],
    )

    assert price == 1500.0
    assert source == "competitors"
    assert "Сбалансированная" in reason


def test_fallback_without_competitors_keeps_current_price():
    """Без конкурентов обычные стратегии не меняют цену."""
    price, source, reason = calculate_recommended_price(
        current_price=2000,
        strategy="balanced",
        target_margin=30,
        competitor_prices=None,
    )

    assert price == 2000
    assert source == "fallback_current_price"
    assert "оставляем текущую цену" in reason


def test_fallback_without_any_price_raises_error():
    """Без текущей цены и конкурентов расчёт невозможен."""
    with pytest.raises(HTTPException) as exc_info:
        calculate_recommended_price(
            current_price=0,
            strategy="balanced",
            target_margin=30,
            competitor_prices=None,
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_repricing_rejects_competitor_product(client, db_session):
    """API не считает репрайсинг для карточек конкурентов."""
    headers, user_payload = auth_headers(client, "repricing-competitor@example.com")

    product = Product(
        user_id=UUID(user_payload["user"]["id"]),
        name="Конкурент",
        marketplace="wildberries",
        external_id="competitor-repricing",
        price=1000,
        is_competitor=True,
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)

    response = client.post(
        "/api/v1/repricing/calculate",
        headers=headers,
        json={
            "product_id": product.id,
            "strategy": "balanced",
            "target_margin": 30,
        },
    )

    assert response.status_code == 400
    assert "собственных товаров" in response.json()["detail"]


def test_repricing_rejects_too_many_manual_competitor_prices(client):
    """Ручной список цен конкурентов ограничен по размеру."""
    headers, _ = auth_headers(client, "repricing-too-many@example.com")

    response = client.post(
        "/api/v1/repricing/calculate",
        headers=headers,
        json={
            "product_id": 1,
            "strategy": "balanced",
            "target_margin": 30,
            "competitor_prices": [1000] * 101,
        },
    )

    assert response.status_code == 422
