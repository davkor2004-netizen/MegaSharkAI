"""
Тесты тарифной модели, feature-флагов и usage-лимитов.

Покрывают:
- канонический каталог тарифов (plans.py) и его лимиты/флаги;
- enforcement feature-флагов (widget, repricing, auto-repricing) на эндпоинтах;
- usage-счётчики (инкремент, блокировка при достижении лимита);
- volume-лимиты (товары, ключи маркетплейсов);
- совпадение /admin/tariffs с каноническим источником;
- usage summary в админке;
- отсутствие секретов в выдаче.
"""

import json
from uuid import UUID

import pytest

from app.models.tariff import Tariff, UserSubscription
from app.services import feature_access, plans


# ====================================================================
# Хелперы
# ====================================================================
def register_user(client, email: str, password: str = "TestPass123!") -> dict:
    """Создать пользователя через публичный API регистрации."""
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Тариф Тест"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(client, email: str) -> tuple[dict[str, str], dict]:
    """Зарегистрировать пользователя и вернуть Authorization header + payload."""
    payload = register_user(client, email=email)
    return {"Authorization": f"Bearer {payload['access_token']}"}, payload


async def make_superuser(db_session, user_id: str) -> None:
    """Сделать пользователя суперпользователем."""
    from app.models.user import User

    user = await db_session.get(User, UUID(user_id))
    user.is_superuser = True
    await db_session.commit()


async def give_plan(db_session, user_id: str, code: str) -> None:
    """Создать активную подписку на тариф с заданным кодом (trial/pro/business/...)."""
    tariff = Tariff(
        name=code.upper(),
        code=code,
        price_monthly=1000.0,
        price_yearly=10000.0,
        trial_days=7,
        is_active=True,
        limits=json.dumps({}),
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


# ====================================================================
# 1. Канонический каталог
# ====================================================================
def test_trial_has_small_limits():
    """Trial — маленькие лимиты согласно тарифной модели."""
    limits = plans.get_plan_limits("trial")
    assert limits["max_products"] == 10
    assert limits["max_ai_actions_per_month"] == 25
    assert limits["max_exports_per_month"] == 1
    assert limits["max_marketplace_keys"] == 1


def test_pro_has_no_widget_access():
    """PRO не имеет доступа к виджету."""
    flags = plans.get_plan_flags("pro")
    assert flags["widget_access"] is False
    assert flags["bulk_import_access"] is True
    assert flags["auto_repricing_access"] is False


def test_business_has_widget_access():
    """BUSINESS имеет widget_access и repricing."""
    flags = plans.get_plan_flags("business")
    assert flags["widget_access"] is True
    assert flags["repricing_access"] is True
    assert flags["auto_repricing_access"] is True
    assert flags["white_label_reports_access"] is False


def test_agency_has_white_label():
    """AGENCY имеет white_label_reports_access и agency_projects_access."""
    flags = plans.get_plan_flags("agency")
    assert flags["white_label_reports_access"] is True
    assert flags["agency_projects_access"] is True


def test_enterprise_all_features_and_unlimited():
    """ENTERPRISE — все флаги true, лимиты безлимитны."""
    flags = plans.get_plan_flags("enterprise")
    assert all(flags.values())
    limits = plans.get_plan_limits("enterprise")
    assert limits["max_products"] == -1
    assert limits["max_ai_actions_per_month"] == -1


def test_feature_min_plan():
    """Минимальный план для фич определяется корректно (для upgrade-подсказок)."""
    assert plans.feature_min_plan("widget_access") == "business"
    assert plans.feature_min_plan("white_label_reports_access") == "agency"
    assert plans.feature_min_plan("bulk_import_access") == "pro"


# ====================================================================
# 2. Feature-флаги на эндпоинтах
# ====================================================================
@pytest.mark.asyncio
async def test_no_subscription_blocks_paid_feature(client, db_session):
    """Без подписки платная фича (repricing/apply) → 402 FEATURE_LOCKED."""
    headers, _ = auth_headers(client, "tf-nosub@example.com")

    response = client.post(
        "/api/v1/repricing/apply",
        headers=headers,
        json={"product_id": 1, "strategy": "balanced", "target_margin": 30},
    )

    assert response.status_code == 402
    detail = response.json()["detail"]
    assert detail["code"] == "FEATURE_LOCKED"
    assert detail["required_plan"] == "business"
    assert detail["upgrade_url"] == "/billing"


@pytest.mark.asyncio
async def test_pro_blocked_on_widget(client, db_session):
    """PRO не имеет widget_access → 402 на конфиге виджета."""
    headers, payload = auth_headers(client, "tf-pro-widget@example.com")
    await give_plan(db_session, payload["user"]["id"], "pro")

    response = client.get("/api/v1/widget/config", headers=headers)
    assert response.status_code == 402


@pytest.mark.asyncio
async def test_business_allowed_on_widget(client, db_session):
    """BUSINESS имеет widget_access → 200 на конфиге виджета."""
    headers, payload = auth_headers(client, "tf-biz-widget@example.com")
    await give_plan(db_session, payload["user"]["id"], "business")

    response = client.get("/api/v1/widget/config", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_pro_blocked_on_repricing_apply(client, db_session):
    """PRO заблокирован на репрайсинге (apply) → 402."""
    headers, payload = auth_headers(client, "tf-pro-rep@example.com")
    await give_plan(db_session, payload["user"]["id"], "pro")

    response = client.post(
        "/api/v1/repricing/apply",
        headers=headers,
        json={"product_id": 1, "strategy": "balanced", "target_margin": 30},
    )
    assert response.status_code == 402
    assert response.json()["detail"]["code"] == "FEATURE_LOCKED"


@pytest.mark.asyncio
async def test_business_passes_repricing_feature_gate(client, db_session):
    """BUSINESS проходит feature-гейт репрайсинга (нет 402; товар не найден → 404)."""
    headers, payload = auth_headers(client, "tf-biz-rep@example.com")
    await give_plan(db_session, payload["user"]["id"], "business")

    response = client.post(
        "/api/v1/repricing/apply",
        headers=headers,
        json={"product_id": 999999, "strategy": "balanced", "target_margin": 30},
    )
    # Доступ к фиче есть → не 402. Далее товар не найден → 404.
    assert response.status_code != 402
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_pro_blocked_on_auto_repricing(client, db_session):
    """PRO заблокирован на сохранении авто-стратегии репрайсинга → 402."""
    headers, payload = auth_headers(client, "tf-pro-auto@example.com")
    await give_plan(db_session, payload["user"]["id"], "pro")

    response = client.post(
        "/api/v1/repricing/strategies",
        headers=headers,
        json={
            "strategy": "balanced",
            "target_margin": 30,
            "night_repricing_enabled": False,
            "auto_update_enabled": True,
        },
    )
    assert response.status_code == 402


@pytest.mark.asyncio
async def test_business_allowed_auto_repricing(client, db_session):
    """BUSINESS может сохранить авто-стратегию репрайсинга → 200."""
    headers, payload = auth_headers(client, "tf-biz-auto@example.com")
    await give_plan(db_session, payload["user"]["id"], "business")

    response = client.post(
        "/api/v1/repricing/strategies",
        headers=headers,
        json={
            "strategy": "balanced",
            "target_margin": 30,
            "night_repricing_enabled": False,
            "auto_update_enabled": True,
        },
    )
    assert response.status_code == 200


# ====================================================================
# 3. Usage-лимиты (service-level)
# ====================================================================
@pytest.mark.asyncio
async def test_increment_usage_increments_counter(client, db_session):
    """increment_usage увеличивает месячный счётчик метрики."""
    _, payload = auth_headers(client, "tf-inc@example.com")
    uid = UUID(payload["user"]["id"])

    summary_before = await feature_access.get_usage_summary(db_session, uid)
    assert summary_before["usage"]["ai_actions"]["used"] == 0

    await feature_access.increment_usage(db_session, uid, "ai_actions", 3)

    summary_after = await feature_access.get_usage_summary(db_session, uid)
    assert summary_after["usage"]["ai_actions"]["used"] == 3


@pytest.mark.asyncio
async def test_ai_limit_blocks_when_reached(client, db_session):
    """При достижении месячного лимита AI следующий запрос блокируется (402)."""
    _, payload = auth_headers(client, "tf-ai-limit@example.com")
    uid = UUID(payload["user"]["id"])
    await give_plan(db_session, payload["user"]["id"], "trial")

    # Trial: 25 AI-действий. Доводим счётчик до лимита.
    await feature_access.increment_usage(db_session, uid, "ai_actions", 25)

    with pytest.raises(Exception) as exc_info:
        await feature_access.check_usage_limit(db_session, uid, "ai_actions")

    err = exc_info.value
    assert getattr(err, "status_code", None) == 402
    assert err.detail["code"] == "LIMIT_EXCEEDED"
    assert err.detail["limit"] == 25
    assert err.detail["used"] == 25
    assert err.detail["reset_at"] is not None


@pytest.mark.asyncio
async def test_unlimited_plan_never_blocks(client, db_session):
    """Безлимитный план (enterprise) не блокирует даже при больших счётчиках."""
    _, payload = auth_headers(client, "tf-ent@example.com")
    uid = UUID(payload["user"]["id"])
    await give_plan(db_session, payload["user"]["id"], "enterprise")

    await feature_access.increment_usage(db_session, uid, "ai_actions", 100000)
    # Не должно бросить исключение.
    await feature_access.check_usage_limit(db_session, uid, "ai_actions")


# ====================================================================
# 4. Volume-лимиты на эндпоинтах
# ====================================================================
@pytest.mark.asyncio
async def test_marketplace_keys_limit_enforced(client, db_session):
    """Trial → 1 ключ маркетплейса; второй ключ блокируется 402."""
    headers, payload = auth_headers(client, "tf-keys@example.com")
    await give_plan(db_session, payload["user"]["id"], "trial")

    first = client.post(
        "/api/v1/marketplace-keys",
        headers=headers,
        json={"marketplace": "wildberries", "api_key": "key-1234567890", "is_active": True},
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/v1/marketplace-keys",
        headers=headers,
        json={"marketplace": "ozon", "api_key": "key-0987654321", "client_id": "123", "is_active": True},
    )
    assert second.status_code == 402
    assert second.json()["detail"]["code"] == "LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_export_increments_usage(client, db_session):
    """Экспорт товаров расходует месячный лимит exports."""
    headers, payload = auth_headers(client, "tf-export@example.com")
    uid = UUID(payload["user"]["id"])
    await give_plan(db_session, payload["user"]["id"], "trial")

    response = client.get("/api/v1/products/export", headers=headers)
    assert response.status_code == 200

    summary = await feature_access.get_usage_summary(db_session, uid)
    assert summary["usage"]["exports"]["used"] == 1


# ====================================================================
# 5. Admin: каталог и usage summary
# ====================================================================
@pytest.mark.asyncio
async def test_admin_tariffs_matches_canonical(client, db_session):
    """/admin/tariffs совпадает с каноническим источником plans.py."""
    headers, payload = auth_headers(client, "tf-admin@example.com")
    await make_superuser(db_session, payload["user"]["id"])

    response = client.get("/api/v1/admin/tariffs", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]

    by_code = {item["code"]: item for item in items}
    for code in plans.PLAN_ORDER:
        assert code in by_code
        assert by_code[code]["limits"] == plans.get_plan_limits(code)
        assert by_code[code]["feature_flags"] == plans.get_plan_flags(code)


@pytest.mark.asyncio
async def test_admin_user_detail_has_usage_summary(client, db_session):
    """Детальная карточка пользователя в админке содержит usage_summary."""
    admin_headers, admin_payload = auth_headers(client, "tf-admin2@example.com")
    await make_superuser(db_session, admin_payload["user"]["id"])

    _, target_payload = auth_headers(client, "tf-target@example.com")
    target_id = target_payload["user"]["id"]
    await give_plan(db_session, target_id, "pro")

    response = client.get(f"/api/v1/admin/users/{target_id}", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()

    summary = data["usage_summary"]
    assert summary["current_plan"] == "pro"
    assert "ai_actions" in summary["usage"]
    assert summary["features"]["widget_access"] is False
    # Секретов в сводке нет.
    raw = json.dumps(data)
    assert "password" not in raw.lower()
    assert "api_key_encrypted" not in raw
