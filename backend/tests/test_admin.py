"""
Тесты Admin Control Center (read-only эндпоинты).

Проверяют:
- доступ только для superuser (обычный пользователь → 403);
- overview доступен админу;
- отсутствие утечек секретов (хэш пароля, сырые ключи маркетплейсов);
- финальную тарифную сетку и feature-флаги;
- system/security/audit/parser/ai не падают.
"""

from uuid import UUID

import pytest
from sqlalchemy import select

from app.models.user import User


def register_user(client, email: str, password: str = "TestPass123!") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "QA Admin"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(client, email: str) -> tuple[dict[str, str], dict]:
    payload = register_user(client, email=email)
    return {"Authorization": f"Bearer {payload['access_token']}"}, payload


async def make_superuser(db_session, user_id: str) -> None:
    result = await db_session.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one()
    user.is_superuser = True
    await db_session.commit()


ADMIN_ENDPOINTS = [
    "/api/v1/admin/overview",
    "/api/v1/admin/users",
    "/api/v1/admin/billing/subscriptions",
    "/api/v1/admin/tariffs",
    "/api/v1/admin/system/status",
    "/api/v1/admin/security/events",
    "/api/v1/admin/audit",
    "/api/v1/admin/parser/status",
    "/api/v1/admin/ai/status",
]


@pytest.mark.asyncio
async def test_regular_user_forbidden_on_all_admin_endpoints(client, db_session):
    """Обычный пользователь получает 403 на любом /api/v1/admin/*."""
    user_headers, _ = auth_headers(client, "admin-regular@example.com")
    for endpoint in ADMIN_ENDPOINTS:
        response = client.get(endpoint, headers=user_headers)
        assert response.status_code == 403, f"{endpoint} -> {response.status_code}"


@pytest.mark.asyncio
async def test_anonymous_forbidden(client):
    """Без авторизации /api/v1/admin/* недоступны (401)."""
    response = client.get("/api/v1/admin/overview")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_superuser_gets_overview(client, db_session):
    """Superuser получает overview со сводными метриками."""
    admin_headers, payload = auth_headers(client, "admin-overview@example.com")
    await make_superuser(db_session, payload["user"]["id"])

    response = client.get("/api/v1/admin/overview", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    for key in (
        "users_total",
        "new_users_24h",
        "new_users_7d",
        "new_users_30d",
        "active_trials",
        "paid_users",
        "active_subscriptions",
        "approximate_mrr",
        "backend_status",
        "db_status",
        "redis_status",
        "celery_status",
    ):
        assert key in data
    assert data["users_total"] >= 1
    assert data["backend_status"] == "ok"


@pytest.mark.asyncio
async def test_admin_users_never_leaks_password_hash(client, db_session):
    """Список пользователей не содержит хэш пароля."""
    admin_headers, payload = auth_headers(client, "admin-users@example.com")
    await make_superuser(db_session, payload["user"]["id"])

    response = client.get("/api/v1/admin/users", headers=admin_headers)
    assert response.status_code == 200
    body = response.text
    assert "hashed_password" not in body
    assert "TestPass123!" not in body

    data = response.json()
    assert data["total"] >= 1
    assert isinstance(data["items"], list)
    # У элемента нет полей с секретами
    sample = data["items"][0]
    assert "hashed_password" not in sample
    assert "password" not in sample


@pytest.mark.asyncio
async def test_admin_user_detail_masks_marketplace_keys(client, db_session):
    """Детали пользователя отдают только маскированный ключ, не сырой."""
    from app.crud.marketplace_key import marketplace_key_crud

    admin_headers, payload = auth_headers(client, "admin-detail@example.com")
    user_id = payload["user"]["id"]
    await make_superuser(db_session, user_id)

    raw_key = "SUPERSECRETKEY1234567890"
    await marketplace_key_crud.create_key(
        db=db_session,
        user_id=UUID(user_id),
        marketplace="wildberries",
        api_key=raw_key,
    )

    response = client.get(f"/api/v1/admin/users/{user_id}", headers=admin_headers)
    assert response.status_code == 200
    body = response.text
    # Сырой ключ и зашифрованное поле не должны утекать
    assert raw_key not in body
    assert "api_key_encrypted" not in body

    data = response.json()
    keys = data["marketplace_keys"]
    assert len(keys) == 1
    masked = keys[0]["api_key_masked"]
    assert masked and raw_key != masked
    assert "*" in masked


@pytest.mark.asyncio
async def test_admin_tariffs_returns_final_grid(client, db_session):
    """Тарифы возвращают финальную сетку с корректными ценами."""
    admin_headers, payload = auth_headers(client, "admin-tariffs@example.com")
    await make_superuser(db_session, payload["user"]["id"])

    response = client.get("/api/v1/admin/tariffs", headers=admin_headers)
    assert response.status_code == 200
    items = response.json()["items"]
    by_code = {t["code"]: t for t in items}

    assert set(by_code) == {"trial", "pro", "business", "agency", "enterprise"}
    assert by_code["trial"]["price"] == 0
    assert by_code["pro"]["price"] == 2990
    assert by_code["business"]["price"] == 7990
    assert by_code["agency"]["price"] == 14990
    assert by_code["enterprise"]["price"] is None
    assert by_code["enterprise"]["is_manual_only"] is True


@pytest.mark.asyncio
async def test_widget_access_is_business_plus(client, db_session):
    """widget_access доступен с BUSINESS и выше, у PRO — нет."""
    admin_headers, payload = auth_headers(client, "admin-flags@example.com")
    await make_superuser(db_session, payload["user"]["id"])

    response = client.get("/api/v1/admin/tariffs", headers=admin_headers)
    assert response.status_code == 200
    by_code = {t["code"]: t for t in response.json()["items"]}

    assert by_code["pro"]["feature_flags"]["widget_access"] is False
    assert by_code["trial"]["feature_flags"]["widget_access"] is False
    assert by_code["business"]["feature_flags"]["widget_access"] is True
    assert by_code["agency"]["feature_flags"]["widget_access"] is True
    assert by_code["enterprise"]["feature_flags"]["widget_access"] is True

    # white_label_reports_access — только AGENCY+
    assert by_code["business"]["feature_flags"]["white_label_reports_access"] is False
    assert by_code["agency"]["feature_flags"]["white_label_reports_access"] is True


@pytest.mark.asyncio
async def test_admin_system_status_reports_health(client, db_session):
    """system/status отдаёт health и предупреждения."""
    admin_headers, payload = auth_headers(client, "admin-system@example.com")
    await make_superuser(db_session, payload["user"]["id"])

    response = client.get("/api/v1/admin/system/status", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    for key in ("environment", "debug", "is_production", "db_status", "redis_status", "warnings"):
        assert key in data
    assert isinstance(data["warnings"], list)


@pytest.mark.asyncio
async def test_admin_security_and_audit_do_not_crash(client, db_session):
    """security/audit/parser/ai эндпоинты не падают и отдают корректную структуру."""
    admin_headers, payload = auth_headers(client, "admin-misc@example.com")
    await make_superuser(db_session, payload["user"]["id"])

    security = client.get("/api/v1/admin/security/events", headers=admin_headers)
    assert security.status_code == 200
    assert security.json()["available"] is False

    audit = client.get("/api/v1/admin/audit", headers=admin_headers)
    assert audit.status_code == 200
    assert audit.json()["available"] is False
    assert audit.json()["items"] == []

    parser = client.get("/api/v1/admin/parser/status", headers=admin_headers)
    assert parser.status_code == 200
    assert "supported_marketplaces" in parser.json()

    ai = client.get("/api/v1/admin/ai/status", headers=admin_headers)
    assert ai.status_code == 200
    ai_body = ai.json()
    assert "active_provider" in ai_body
    assert "providers" in ai_body
