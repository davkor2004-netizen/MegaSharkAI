"""
Тесты API MegaSharkAI.

Использует pytest и httpx для тестирования FastAPI эндпоинтов.
"""

import pytest
from uuid import UUID

from app.models.product import Product
from app.services.parser import MarketplaceParser, ParserError


def register_user(client, email: str = "test@example.com", password: str = "TestPass123!") -> dict:
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


def auth_headers(client, email: str = "test@example.com", password: str = "TestPass123!") -> dict[str, str]:
    """Зарегистрировать пользователя и вернуть Authorization header."""
    register_data = register_user(client, email=email, password=password)
    token = register_data["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestHealthEndpoints:
    """Тесты health check эндпоинтов."""
    
    def test_health_check(self, client):
        """Тест базовой проверки здоровья."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "MegaSharkAI" in data["service"]
    
    def test_root_endpoint(self, client):
        """Тест корневого эндпоинта."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "MegaSharkAI" in data["message"]
        assert data["docs"] == "/docs"


class TestAuthEndpoints:
    """Тесты аутентификации."""
    
    def test_register_user(self, client):
        """Тест регистрации нового пользователя."""
        user_data = {
            "email": "test@example.com",
            "password": "TestPass123!",
            "full_name": "Тестовый Пользователь"
        }
        
        response = client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["access_token"]
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == user_data["email"]
        assert "id" in data["user"]

    def test_register_login_me_smoke(self, client):
        """Smoke-сценарий: register -> login -> /auth/me."""
        email = "login-smoke@example.com"
        password = "TestPass123!"
        register_user(client, email=email, password=password)

        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )

        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        me_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert me_response.status_code == 200
        assert me_response.json()["email"] == email
    
    def test_login_invalid_credentials(self, client):
        """Тест входа с неверными данными."""
        login_data = {
            "username": "nonexistent@example.com",
            "password": "WrongPassword"
        }
        
        response = client.post("/api/v1/auth/login", data=login_data)
        
        assert response.status_code == 401


class TestAIEndpoints:
    """Тесты AI функционала."""
    
    def test_get_ai_provider_requires_auth(self, client):
        """AI provider должен быть доступен только авторизованному пользователю."""
        response = client.get("/api/v1/ai/provider")
        
        assert response.status_code == 401

    def test_get_ai_provider_with_auth(self, client):
        """Авторизованный пользователь может получить статус AI-провайдера."""
        response = client.get("/api/v1/ai/provider", headers=auth_headers(client, email="ai@example.com"))

        assert response.status_code == 200
        data = response.json()
        assert "provider" in data
        assert data["provider"] in ["yandex", "deepseek", "openai", "none"]
    
    def test_generate_seo_title_requires_auth(self, client):
        """Генерация SEO-названия без авторизации запрещена."""
        seo_data = {
            "product_name": "Футболка мужская",
            "category": "Одежда"
        }
        
        response = client.post("/api/v1/ai/generate-seo-title", json=seo_data)
        
        assert response.status_code == 401


class TestParsingEndpoints:
    """Тесты парсинга."""

    def test_detect_marketplace_rejects_unknown_domain(self):
        """Parser быстро отклоняет неподдерживаемый маркетплейс."""
        parser = MarketplaceParser()

        with pytest.raises(ParserError):
            parser.detect_marketplace("https://example.com/product/123")

    def test_validate_product_url_rejects_missing_external_id(self):
        """URL без ID товара не запускает Playwright."""
        parser = MarketplaceParser()

        with pytest.raises(ParserError):
            parser.validate_product_url("https://www.ozon.ru/category/smartfony-15502/")

    def test_validate_product_url_accepts_supported_product_url(self):
        """Поддерживаемый URL товара проходит валидацию."""
        parser = MarketplaceParser()

        url = "https://www.wildberries.ru/catalog/24319630/detail.aspx?utm_source=test"
        assert parser.validate_product_url(url) == url
    
    def test_extract_external_id_wildberries(self):
        """Проверка извлечения external_id для Wildberries."""
        parser = MarketplaceParser()
        url = "https://www.wildberries.ru/catalog/24319630/detail.aspx"

        external_id = parser.extract_external_id(url, "wildberries")
        assert external_id == "24319630"

    def test_extract_external_id_ozon(self):
        """Проверка извлечения external_id для Ozon."""
        parser = MarketplaceParser()
        url = "https://www.ozon.ru/product/smartfon-apple-iphone-15-pro-256gb-123456789/"

        external_id = parser.extract_external_id(url, "ozon")
        assert external_id == "123456789"

    def test_extract_external_id_yandex_market(self):
        """Проверка извлечения external_id для Яндекс Маркета."""
        parser = MarketplaceParser()
        url = "https://market.yandex.ru/product--iphone-15-pro/123456789"

        external_id = parser.extract_external_id(url, "yandex_market")
        assert external_id == "123456789"

    def test_extract_external_id_avito(self):
        """Проверка извлечения external_id для Avito."""
        parser = MarketplaceParser()
        url = "https://www.avito.ru/moskva/telefony/iphone_15_pro_1234567890"

        external_id = parser.extract_external_id(url, "avito")
        assert external_id == "1234567890"


class TestProductsEndpoints:
    """Тесты товаров."""
    
    def test_get_products_list_requires_auth(self, client):
        """Список товаров без JWT запрещён."""
        response = client.get("/api/v1/products/list")
        
        assert response.status_code == 401

    def test_get_products_list_with_auth(self, client):
        """Авторизованный пользователь получает свой список товаров."""
        response = client.get(
            "/api/v1/products/list",
            headers=auth_headers(client, email="products@example.com"),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
    
    def test_get_product_stats_requires_auth(self, client):
        """Статистика товаров без JWT запрещена."""
        response = client.get("/api/v1/products/stats/summary")
        
        assert response.status_code == 401

    def test_get_product_stats_with_auth(self, client):
        """Статистика пользователя без товаров возвращает нулевые значения."""
        response = client.get(
            "/api/v1/products/stats/summary",
            headers=auth_headers(client, email="stats@example.com"),
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_products" in data
        assert "average_price" in data

    def test_export_products_route_is_not_captured_by_product_id(self, client):
        """Статический /export не должен попадать в динамический /{product_id:int}."""
        response = client.get(
            "/api/v1/products/export",
            headers=auth_headers(client, email="export@example.com"),
        )

        assert response.status_code == 200
        assert "spreadsheetml.sheet" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_products_list_is_scoped_to_current_user(self, client, db_session):
        """Пользователь видит только свои товары."""
        first_user = register_user(client, email="owner-a@example.com")
        second_user = register_user(client, email="owner-b@example.com")

        db_session.add_all([
            Product(
                user_id=UUID(first_user["user"]["id"]),
                name="Товар первого пользователя",
                marketplace="wildberries",
                external_id="own-1",
                price=1000,
                is_competitor=False,
            ),
            Product(
                user_id=UUID(second_user["user"]["id"]),
                name="Товар второго пользователя",
                marketplace="ozon",
                external_id="own-2",
                price=2000,
                is_competitor=False,
            ),
        ])
        await db_session.commit()

        response = client.get(
            "/api/v1/products/list",
            headers={"Authorization": f"Bearer {first_user['access_token']}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Товар первого пользователя"

    @pytest.mark.asyncio
    async def test_delete_foreign_product_returns_not_found(self, client, db_session):
        """Удаление чужого товара не раскрывает его наличие."""
        first_user = register_user(client, email="delete-a@example.com")
        second_user = register_user(client, email="delete-b@example.com")

        foreign_product = Product(
            user_id=UUID(second_user["user"]["id"]),
            name="Чужой товар",
            marketplace="wildberries",
            external_id="foreign-1",
            price=1000,
            is_competitor=False,
        )
        db_session.add(foreign_product)
        await db_session.commit()
        await db_session.refresh(foreign_product)

        response = client.delete(
            f"/api/v1/products/{foreign_product.id}",
            headers={"Authorization": f"Bearer {first_user['access_token']}"},
        )

        assert response.status_code == 404


# Запуск тестов
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
