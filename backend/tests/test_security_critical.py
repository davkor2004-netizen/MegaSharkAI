"""
Тесты критических исправлений безопасности (SSRF, JWT types).
"""

from datetime import timedelta

import pytest
from jose import jwt

from app.config import settings
from app.services.auth_service import (
    ALGORITHM,
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_PASSWORD_RESET,
    create_access_token,
    create_password_reset_token,
    is_access_token_payload,
)
from app.services.parser import MarketplaceParser, ParserError
from app.services.url_security import UrlSecurityError, validate_marketplace_product_url


class TestUrlSecurity:
    """SSRF: только whitelist hostname маркетплейсов."""

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/wildberries.ru/catalog/24319630/detail.aspx",
            "http://localhost/wildberries.ru/catalog/24319630/detail.aspx",
            "http://169.254.169.254/wildberries.ru/catalog/1/detail.aspx",
            "http://evil.com/wildberries.ru/catalog/24319630/detail.aspx",
            "https://wildberries.ru.evil.com/catalog/24319630/detail.aspx",
            "https://ozon.ru.attacker.net/product/123",
            "ftp://www.wildberries.ru/catalog/1/detail.aspx",
        ],
    )
    def test_blocks_ssrf_and_fake_hosts(self, url: str):
        with pytest.raises(UrlSecurityError):
            validate_marketplace_product_url(url)

        parser = MarketplaceParser()
        with pytest.raises(ParserError):
            parser.validate_product_url(url)

    def test_allows_real_wildberries_url(self):
        url = "https://www.wildberries.ru/catalog/24319630/detail.aspx"
        normalized, marketplace = validate_marketplace_product_url(url)
        assert marketplace == "wildberries"
        assert parser_validate(url) == normalized


def parser_validate(url: str) -> str:
    return MarketplaceParser().validate_product_url(url)


class TestJwtTokenTypes:
    """Reset-токен не должен работать как access."""

    def test_access_token_has_type_access(self):
        token = create_access_token({"sub": "00000000-0000-0000-0000-000000000001"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["type"] == TOKEN_TYPE_ACCESS
        assert is_access_token_payload(payload)

    def test_password_reset_token_rejected_as_access(self):
        token = create_password_reset_token("00000000-0000-0000-0000-000000000001")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["type"] == TOKEN_TYPE_PASSWORD_RESET
        assert not is_access_token_payload(payload)

    def test_reset_token_cannot_access_me(self, client):
        """Reset JWT не открывает /auth/me."""
        email = "jwt-reset-block@example.com"
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "TestPass123!", "full_name": "JWT Test"},
        )
        assert reg.status_code == 201
        user_id = reg.json()["user"]["id"]

        reset_token = create_password_reset_token(user_id, expires_delta=timedelta(hours=1))
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {reset_token}"},
        )
        assert response.status_code == 401

    def test_access_token_can_access_me(self, client):
        email = "jwt-access-ok@example.com"
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "TestPass123!", "full_name": "JWT OK"},
        )
        token = reg.json()["access_token"]
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["email"] == email


class TestParsingEndpointsAuth:
    """Публичные debug-эндпоинты закрыты."""

    def test_proxy_stats_requires_auth(self, client):
        assert client.get("/api/v1/parsing/proxy-stats").status_code == 401

    def test_test_parser_requires_auth(self, client):
        assert client.get("/api/v1/parsing/test-parser").status_code == 401
