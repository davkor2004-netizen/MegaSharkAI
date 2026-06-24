"""
Тесты исправлений среднего/высокого приоритета.
"""


class TestRateLimit:
    """Brute-force защита auth-эндпоинтов."""

    def test_register_rate_limited_by_ip(self, client, monkeypatch):
        """После N регистраций с одного IP — 429."""
        monkeypatch.setattr("app.config.settings.auth_rate_limit_per_minute", 3)

        for index in range(3):
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"ratelimit{index}@example.com",
                    "password": "TestPass123!",
                    "full_name": "Rate Limit",
                },
            )
            assert response.status_code == 201, response.text

        blocked = client.post(
            "/api/v1/auth/register",
            json={
                "email": "ratelimit-blocked@example.com",
                "password": "TestPass123!",
                "full_name": "Blocked",
            },
        )
        assert blocked.status_code == 429
        assert "Слишком много запросов" in blocked.json()["detail"]


class TestUserResponseMasking:
    """API-ключ пользователя маскируется в /auth/me."""

    def test_marketplace_api_key_masked_in_me(self, client):
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": "mask-key@example.com",
                "password": "TestPass123!",
                "full_name": "Mask Test",
                "marketplace_api_key": "SECRETKEY12345678",
            },
        )
        assert reg.status_code == 201
        token = reg.json()["access_token"]

        me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me.status_code == 200
        masked = me.json()["marketplace_api_key"]
        assert masked is not None
        assert "SECRETKEY12345678" not in masked
        assert "..." in masked


class TestSecurityHeaders:
    """Базовые security-заголовки на ответах."""

    def test_health_has_security_headers(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
