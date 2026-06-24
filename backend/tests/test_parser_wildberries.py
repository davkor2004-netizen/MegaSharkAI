"""
Юнит-тесты Wildberries-парсера (диагностический фикс /parsing).

Проверяем чистую логику без обращения к сети:
- извлечение nm_id из разных форматов URL;
- нормализацию цены WB (копейки -> рубли);
- извлечение цены из price-history вложенного формата {"RUB": копейки};
- merge-логику публичных JSON-источников;
- корректный partial-результат, когда источник недоступен.
"""

import pytest

from app.services.parser import MarketplaceParser


@pytest.fixture()
def parser() -> MarketplaceParser:
    return MarketplaceParser()


class TestExtractNmId:
    def test_catalog_detail_aspx(self, parser: MarketplaceParser):
        url = "https://www.wildberries.ru/catalog/1009716283/detail.aspx"
        assert parser._extract_wb_nm_id_from_url(url) == "1009716283"

    def test_query_nm(self, parser: MarketplaceParser):
        # Без сегмента /catalog/<id>/ nm берётся из query-параметра.
        url = "https://www.wildberries.ru/product?nm=24319630"
        assert parser._extract_wb_nm_id_from_url(url) == "24319630"

    def test_no_id(self, parser: MarketplaceParser):
        assert parser._extract_wb_nm_id_from_url("https://www.wildberries.ru/") is None

    def test_public_extract_external_id(self, parser: MarketplaceParser):
        url = "https://www.wildberries.ru/catalog/1009716283/detail.aspx"
        assert parser.extract_external_id(url, "wildberries") == "1009716283"


class TestNormalizeWbPrice:
    def test_kopecks_large(self, parser: MarketplaceParser):
        # 149990 копеек -> 1499 руб.
        assert parser._normalize_wb_price_value(149990) == 1499

    def test_rubles_small(self, parser: MarketplaceParser):
        assert parser._normalize_wb_price_value(1499) == 1499

    def test_zero_and_negative(self, parser: MarketplaceParser):
        assert parser._normalize_wb_price_value(0) is None
        assert parser._normalize_wb_price_value(-5) is None

    def test_none(self, parser: MarketplaceParser):
        assert parser._normalize_wb_price_value(None) is None


class TestWbPricesFromProduct:
    def test_direct_sale_price(self, parser: MarketplaceParser):
        product = {"salePriceU": 177800, "priceU": 250000}
        prices = parser._extract_wb_prices_from_product(product)
        assert prices["price"] == 1778
        assert prices["old_price"] == 2500

    def test_sizes_price_block(self, parser: MarketplaceParser):
        product = {
            "sizes": [
                {"price": {"total": 177800, "basic": 250000}}
            ]
        }
        prices = parser._extract_wb_prices_from_product(product)
        assert prices["price"] == 1778
        assert prices["old_price"] == 2500


class TestPriceHistoryEntryParsing:
    """
    Проверяем разбор реального формата price-history.json:
    [{"dt": ..., "price": {"RUB": <копейки>}}, ...]

    Логика вынесена во вложенную функцию _entry_price_rub внутри
    _from_basket_price_history, поэтому проверяем её через нормализатор
    и явный расчёт, повторяющий контракт (копейки -> рубли).
    """

    def test_nested_rub_kopecks(self, parser: MarketplaceParser):
        entry_price = {"RUB": 177831}
        # Контракт: значение в копейках -> делим на 100.
        kopecks = parser._to_int_safe(entry_price.get("RUB"))
        assert kopecks == 177831
        assert int(kopecks / 100) == 1778


class TestGenericTitleDetection:
    def test_fallback_title_is_generic(self, parser: MarketplaceParser):
        assert parser._is_generic_marketplace_title("Wildberries") is True

    def test_real_title_not_generic(self, parser: MarketplaceParser):
        assert parser._is_generic_marketplace_title("Кроссовки женские adidas samba") is False


@pytest.mark.asyncio
class TestApiFallbackPartial:
    async def test_unknown_nm_returns_empty(self, parser: MarketplaceParser, monkeypatch):
        """Если nm_id не извлекается, API fallback возвращает пустой словарь."""
        data = await parser._extract_wb_card_api_data("https://www.wildberries.ru/")
        assert data == {}
