"""
Unit-тесты AI-сервиса без реальных внешних API.
"""

import pytest

from app.services.ai_service import AIService


@pytest.mark.asyncio
async def test_competitor_analysis_uses_rule_based_fallback_without_provider():
    """Без AI-провайдера анализ конкурентов остаётся структурированным."""
    service = AIService()
    service.yandex_api_key = None
    service.yandex_folder_id = None
    service.openai_api_key = None
    service.deepseek_api_key = None

    result = await service.analyze_competitors(
        product_name="Футболка",
        competitor_data=[
            {"name": "Конкурент 1", "price": 1000, "rating": 4.2},
            {"name": "Конкурент 2", "price": 1500, "rating": 4.5},
        ],
    )

    assert result["min_price"] == 1000
    assert result["max_price"] == 1500
    assert result["avg_price"] == 1250
    assert result["recommended_price"] == 1125
    assert result["ai_status"] == "not_configured"
    assert result["provider_used"] == "none"


def test_parse_competitor_ai_response_sanitizes_expected_fields():
    """AI JSON приводится к ожидаемой безопасной структуре."""
    service = AIService()

    parsed = service._parse_competitor_ai_response(
        """
        Ответ:
        {
            "min_price": 900,
            "max_price": 1400,
            "avg_price": 1150,
            "recommended_price": 1090,
            "price_position": "средняя",
            "recommendations": ["Снизить цену", "Усилить карточку"]
        }
        """
    )

    assert parsed == {
        "min_price": 900.0,
        "max_price": 1400.0,
        "avg_price": 1150.0,
        "recommended_price": 1090.0,
        "price_position": "средняя",
        "recommendations": ["Снизить цену", "Усилить карточку"],
    }


@pytest.mark.asyncio
async def test_competitor_analysis_falls_back_on_invalid_ai_response(monkeypatch):
    """Невалидный ответ AI не ломает анализ конкурентов."""
    service = AIService()
    service.deepseek_api_key = "configured"
    service.yandex_api_key = None
    service.yandex_folder_id = None
    service.openai_api_key = None

    async def fake_generate_text(*args, **kwargs):
        service.last_used_provider = "deepseek"
        return "not json"

    monkeypatch.setattr(service, "_generate_text_with_fallback", fake_generate_text)

    result = await service.analyze_competitors(
        product_name="Футболка",
        competitor_data=[
            {"name": "Конкурент 1", "price": 1000},
            {"name": "Конкурент 2", "price": 1500},
        ],
    )

    assert result["recommended_price"] == 1125
    assert result["ai_status"] == "fallback_invalid_ai_response"
    assert result["provider_used"] == "deepseek"
