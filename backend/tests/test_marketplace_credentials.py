"""
Тесты безопасного хранения credentials маркетплейсов.
"""

from app.services.marketplace_api import MarketplaceAPIService


def auth_headers(client, email: str) -> dict[str, str]:
    """Создать пользователя и вернуть JWT header."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "TestPass123!",
            "full_name": "Тестовый Пользователь",
        },
    )

    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_ozon_headers_require_client_id():
    """Ozon Seller API нельзя вызывать без Client-Id."""
    service = MarketplaceAPIService()

    headers = service.build_headers("ozon", "api-secret")

    assert headers is None


def test_ozon_headers_include_client_id_without_mutating_key():
    """Для Ozon headers содержат и Api-Key, и Client-Id."""
    service = MarketplaceAPIService()

    headers = service.build_headers(
        "ozon",
        "api-secret",
        additional_credentials={"client_id": "client-123"},
    )

    assert headers == {
        "Api-Key": "api-secret",
        "Client-Id": "client-123",
        "Content-Type": "application/json",
    }


def test_create_ozon_key_requires_client_id(client):
    """Backend явно просит Client-Id при подключении Ozon."""
    response = client.post(
        "/api/v1/marketplace-keys",
        headers=auth_headers(client, email="ozon-missing-client@example.com"),
        json={
            "marketplace": "ozon",
            "api_key": "ozon-api-secret",
            "is_active": True,
        },
    )

    assert response.status_code == 422
    assert "Client-Id" in response.json()["detail"]


def test_create_ozon_key_masks_credentials(client, monkeypatch):
    """API сохраняет Ozon credentials и возвращает только маски."""
    from app.api.v1.marketplace_keys import marketplace_api_service

    async def fake_check_api_key(*args, **kwargs):
        return True

    monkeypatch.setattr(marketplace_api_service, "check_api_key", fake_check_api_key)

    response = client.post(
        "/api/v1/marketplace-keys",
        headers=auth_headers(client, email="ozon-client@example.com"),
        json={
            "marketplace": "ozon",
            "api_key": "ozon-api-secret",
            "client_id": "client-123456",
            "is_active": True,
        },
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["marketplace"] == "ozon"
    assert data["is_valid"] is True
    assert data["api_key_masked"] != "ozon-api-secret"
    assert data["additional_credentials_masked"]["client_id"] != "client-123456"
    assert "secret" not in str(data)
    assert "client-123456" not in str(data)
