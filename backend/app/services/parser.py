"""
Сервис парсинга товаров с маркетплейсов через Playwright.
Поддерживает: Wildberries, Ozon, Яндекс Маркет, Avito

ВАЖНО: Wildberries активно блокирует парсинг. Используются:
- Ротация User-Agent
- Реалистичные заголовки
- Случайные задержки
- Обход детекции ботов

Альтернатива: Использовать официальное API WB для продавцов
"""

import asyncio
import os
import random
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from typing import Optional, Dict, Any, List
from datetime import datetime
import httpx
from loguru import logger
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout, BrowserContext
from app.config import settings
from app.services.url_security import marketplace_from_hostname, validate_marketplace_product_url, UrlSecurityError


class ParserError(Exception):
    """Ошибка парсинга."""
    pass


def _parser_debug_dumps_enabled() -> bool:
    """
    Разрешено ли сохранять debug-дампы парсера (screenshot/HTML).

    Двойной guard для безопасности production:
    1. Только в dev-режиме (``settings.debug=True``).
    2. Только при явном opt-in через env ``PARSER_DEBUG_DUMPS`` (по умолчанию выключено).

    В production (``DEBUG=false``) файлы не создаются никогда.
    """
    if not settings.debug:
        return False
    flag = os.getenv("PARSER_DEBUG_DUMPS", "false").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def _parser_debug_dir() -> Path:
    """
    Безопасная директория для debug-дампов.

    Берётся из env ``PARSER_DEBUG_DIR`` либо системный temp
    (``<tmp>/megashark_parser_debug``). Никаких относительных путей вида
    ``backend/...``, чтобы не создавалась вложенная ``backend/backend/``.
    """
    configured = os.getenv("PARSER_DEBUG_DIR", "").strip()
    base = Path(configured) if configured else Path(tempfile.gettempdir()) / "megashark_parser_debug"
    return base


async def _save_parser_debug_dump(page: "Page", prefix: str) -> None:
    """
    Сохранить screenshot + усечённый HTML для отладки антибота.

    No-op, если debug-дампы не разрешены (см. ``_parser_debug_dumps_enabled``).
    Никогда не пишет secrets/cookies/tokens — только публичный HTML страницы,
    усечённый до 50KB. Исключения подавляются, чтобы отладка не ломала парсинг.
    """
    if not _parser_debug_dumps_enabled():
        return

    try:
        debug_dir = _parser_debug_dir()
        debug_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        screenshot_path = debug_dir / f"{prefix}_debug_{stamp}.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)

        html_path = debug_dir / f"{prefix}_debug_{stamp}.html"
        html_content = await page.content()
        html_path.write_text(html_content[:50000], encoding="utf-8")

        logger.debug(f"🐞 Debug-дамп парсера сохранён: {debug_dir} (prefix={prefix})")
    except Exception as exc:  # отладка не должна влиять на основной парсинг
        logger.debug(f"Не удалось сохранить debug-дамп парсера: {exc}")


class MarketplaceParser:
    """Парсер для различных маркетплейсов."""
    
    # Реалистичные User-Agent (2024-2025)
    USER_AGENTS = [
        # Chrome Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        # Firefox Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        # Safari Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        # Edge Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    ]
    
    # Реалистичные заголовки
    HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    # Заголовки для публичных JSON-источников WB (card.wb.ru / basket CDN).
    # Без них WB-WAF чаще отвечает 403. Браузерный UA + Referer на сайт WB.
    WB_PUBLIC_JSON_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": "https://www.wildberries.ru",
        "Referer": "https://www.wildberries.ru/",
    }

    # Селекторы для Wildberries (ОБНОВЛЕНО 2026)
    WB_SELECTORS = {
        "name": "h1[data-nm='product-name'], .product-header__title, h1",
        "price": "[data-nm='price-current'] .sum-price, .price-block__sum-price, span[data-nm='price'], .price__current, .price span:first-child",
        "old_price": "[data-nm='price-old'] .sum-price, .price-block__old-sum-price, span[data-nm='old-price'], .price__old, .price del",
        "discount": "[data-nm='discount'] .discount, .price-block__discount, span[data-nm='discount'], .price__discount, .badge_discount",
        "rating": ".product-review__link span, .rating-sum, [data-nm='rating'], .stars-rating__count",
        "reviews": ".product-review__link, .reviews-count, [data-nm='reviews'], .feedback-link",
        "stock": ".stock-status, .availability, .product-availability",
        "brand": ".product-header__brand, [data-nm='brand'], .brand a",
        "category": ".breadcrumbs__link:last-child, [data-nm='category'], .breadcrumb a:last-child",
        "images": ".product-gallery__image img, .photo-gallery__image img, [data-nm='image']",
        "description": ".product-description, .description, [data-nm='description'], .description__text",
        "seller": ".seller-info__name, .seller__name, [data-nm='seller']",
        "article": ".product-articles__article, .article, [data-nm='article']",
    }
    
    # Селекторы для Ozon
    OZON_SELECTORS = {
        "name": "h1.r0655, h1[data-test='product-title'], h1",
        "price": "span.r1060, span[data-test='price-value'], .price .current-price, span:contains('₽'):first",
        "old_price": "span[data-test='price-old-value'], .price .old-price, del",
        "discount": "span[data-test='price-discount'], .discount-badge, .badge_discount",
        "rating": "span[data-test='reviews-count'], .rating-sum, .stars-rating__count",
        "reviews": "a[data-test='reviews-link'], .reviews-count",
        "stock": "span[data-test='stock-status'], .availability-text",
        "brand": "a[data-test='brand-link'], .brand a",
        "category": "a[data-test='breadcrumb-link']:last-child, .breadcrumbs a:last-child",
        "images": "img[data-test='product-image'], .product-gallery img",
        "seller": "a[data-test='seller-link'], .seller-info a",
    }
    
    # Селекторы для Яндекс Маркет
    YANDEX_SELECTORS = {
        "name": "h1[data-zone-name='title'], h1",
        "price": "span[data-zone-name='price'], .price-current, .price",
        "old_price": "span[data-zone-name='old-price'], .price-old, del",
        "discount": "span[data-zone-name='discount'], .discount-badge",
        "rating": "span[data-zone-name='rating'], .rating-sum",
        "reviews": "a[data-zone-name='reviews'], .reviews-count",
        "stock": "span[data-zone-name='stock'], .availability",
        "brand": "a[data-zone-name='brand'], .brand a",
        "category": "a[data-zone-name='category']:last-child, .breadcrumbs a:last-child",
        "images": "img[data-zone-name='image'], .product-gallery img",
        "seller": "a[data-zone-name='seller'], .seller-info a",
    }
    
    # Селекторы для Avito
    AVITO_SELECTORS = {
        "name": "h1[data-name='ItemTitle'], h1",
        "price": "span[data-name='ItemPrice'], .price",
        "old_price": None,  # Нет на Avito
        "discount": None,
        "rating": None,
        "reviews": None,
        "stock": "span[data-name='StockStatus'], .availability",
        "brand": None,
        "category": "a[data-name='Breadcrumb'], .breadcrumbs a",
        "images": "img[data-name='ItemImage'], .gallery img",
        "seller": "a[data-name='SellerProfile'], .seller-info a",
    }
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
    
    def _determine_marketplace(self, url: str) -> str:
        """Определить маркетплейс по hostname URL (не по path/query)."""
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            if not hostname:
                return "unknown"
            marketplace = marketplace_from_hostname(hostname)
            return marketplace or "unknown"
        except UrlSecurityError:
            return "unknown"

    def detect_marketplace(self, url: str) -> str:
        """Публично определить поддерживаемый маркетплейс по URL."""
        marketplace = self._determine_marketplace(url)
        if marketplace == "unknown":
            raise ParserError("Неподдерживаемый маркетплейс")
        return marketplace

    def validate_product_url(self, url: str) -> str:
        """Проверить URL товара до запуска браузерного парсинга."""
        try:
            normalized_url, marketplace = validate_marketplace_product_url(url)
        except UrlSecurityError as exc:
            raise ParserError(str(exc)) from exc

        external_id = self.extract_external_id(normalized_url, marketplace)
        if not external_id:
            raise ParserError("Не удалось определить ID товара из URL")

        return normalized_url
    
    async def _get_selector(self, marketplace: str, field: str) -> Optional[str]:
        """Получить селектор для поля."""
        selectors = {
            "wildberries": self.WB_SELECTORS,
            "ozon": self.OZON_SELECTORS,
            "yandex_market": self.YANDEX_SELECTORS,
            "avito": self.AVITO_SELECTORS,
        }
        
        mp_selectors = selectors.get(marketplace.lower())
        if not mp_selectors:
            logger.warning(f"⚠️ Неизвестный маркетплейс: {marketplace}")
            return None
        
        return mp_selectors.get(field)
    
    async def _detect_marketplace(self, url: str) -> str:
        """Определить маркетплейс по URL."""
        url_lower = url.lower()
        
        if "wildberries.ru" in url_lower or "wb.ru" in url_lower:
            return "wildberries"
        elif "ozon.ru" in url_lower:
            return "ozon"
        elif "market.yandex.ru" in url_lower or "yandex.ru/market" in url_lower:
            return "yandex_market"
        elif "avito.ru" in url_lower:
            return "avito"
        else:
            raise ParserError(f"Неподдерживаемый маркетплейс: {url}")
    
    def _normalize_marketplace_url(self, url: str, marketplace: str) -> str:
        """
        Нормализовать URL маркетплейса перед парсингом.

        Для WB удаляем служебные query-параметры, которые могут вести
        на промежуточные страницы/редиректы и ухудшать стабильность goto.
        """
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return url

            marketplace_normalized = (marketplace or "").lower()
            if marketplace_normalized == "wildberries":
                allowed_query_keys = {"nm", "nm_id", "imt_id"}
                normalized_query_pairs = [
                    (key, value)
                    for key, value in parse_qsl(parsed.query, keep_blank_values=False)
                    if key in allowed_query_keys
                ]

                normalized_query = urlencode(normalized_query_pairs, doseq=True)
                normalized_url = urlunparse(
                    (
                        parsed.scheme,
                        parsed.netloc,
                        parsed.path,
                        parsed.params,
                        normalized_query,
                        "",  # удаляем fragment
                    )
                )
                return normalized_url
                
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ""))
        except Exception:
            return url

    async def _extract_text(self, page: Page, selector: Optional[str], fallback_selectors: Optional[List[str]] = None) -> Optional[str]:
        """Извлечь текст по селектору с поддержкой fallback."""
        if not selector:
            return None
        
        selectors_to_try = [selector]
        if fallback_selectors:
            selectors_to_try.extend(fallback_selectors)
        
        for sel in selectors_to_try:
            try:
                element = await page.query_selector(sel)
                if element:
                    text = await element.inner_text()
                    if text and text.strip():
                        return text.strip()
            except Exception:
                continue
        
        return None
    
    async def _extract_all_texts(self, page: Page, selector: str) -> List[str]:
        """Извлечь все тексты по селектору."""
        try:
            elements = await page.query_selector_all(selector)
            texts = []
            for el in elements:
                text = await el.inner_text()
                if text and text.strip():
                    texts.append(text.strip())
            return texts
        except Exception:
            return []
    
    async def _extract_price(self, page: Page, marketplace: str) -> Optional[int]:
        """Извлечь цену (в рублях) с улучшенной обработкой."""
        selector = await self._get_selector(marketplace, "price")
        
        # Пробуем основной селектор
        price_text = await self._extract_text(page, selector)
        
        # Если не получилось, пробуем альтернативные варианты
        if not price_text:
            # Ищем любой элемент с ценой
            price_selectors = [
                ".price", ".price-current", "[data-nm='price-current']",
                "span:contains('₽'):first", "span[class*='price']:first"
            ]
            for sel in price_selectors:
                price_text = await self._extract_text(page, sel)
                if price_text:
                    break
        
        if not price_text:
            return None
        
        # Очистка от символов валюты и пробелов
        price_text = re.sub(r'[^\d,.\s]', '', price_text)
        price_text = price_text.replace(',', '.').replace(' ', '')
        
        try:
            price = float(price_text)
            return int(price) if price > 0 else None
        except (ValueError, TypeError):
            return None
    
    async def _extract_old_price(self, page: Page, marketplace: str) -> Optional[int]:
        """Извлечь старую цену."""
        selector = await self._get_selector(marketplace, "old_price")
        old_price_text = await self._extract_text(page, selector)
        
        if not old_price_text:
            # Пробуем найти цену в del или .old
            del_elements = await page.query_selector_all("del, .old-price, .price-old")
            for el in del_elements:
                text = await el.inner_text()
                if text:
                    old_price_text = text
                    break
        
        if not old_price_text:
            return None
        
        old_price_text = re.sub(r'[^\d,.\s]', '', old_price_text)
        old_price_text = old_price_text.replace(',', '.').replace(' ', '')
        
        try:
            price = float(old_price_text)
            return int(price) if price > 0 else None
        except (ValueError, TypeError):
            return None
    
    async def _extract_rating(self, page: Page, marketplace: str) -> Optional[float]:
        """Извлечь рейтинг с улучшенной обработкой."""
        selector = await self._get_selector(marketplace, "rating")
        rating_text = await self._extract_text(page, selector)
        
        # Если не нашли по селектору, ищем паттерн рейтинга
        if not rating_text:
            # Ищем элементы со звёздами или рейтингом
            rating_elements = await page.query_selector_all("[class*='rating'], [class*='star']")
            for el in rating_elements:
                text = await el.inner_text()
                if text:
                    rating_text = text
                    break
        
        if not rating_text:
            return None
        
        # Очистка от текста (например "4.8 (123 отзыва)")
        match = re.search(r'(\d+[.,]?\d*)', rating_text)
        if match:
            try:
                rating = float(match.group(1).replace(',', '.'))
                return min(rating, 5.0)  # Рейтинг не больше 5
            except ValueError:
                pass
        
        return None
    
    async def _extract_reviews_count(self, page: Page, marketplace: str) -> Optional[int]:
        """Извлечь количество отзывов."""
        selector = await self._get_selector(marketplace, "reviews")
        reviews_text = await self._extract_text(page, selector)
        
        if not reviews_text:
            return None
        
        # Очистка от текста (например "123 отзыва")
        match = re.search(r'(\d+)', reviews_text)
        if match:
            return int(match.group(1))
        
        return None
    
    def _contains_demo_markers(self, data: Dict[str, Any]) -> bool:
        """
        Проверить, что в распарсенных данных нет признаков демо/заглушки.
        """
        # Используем regex с границами слов, чтобы не ловить ложные срабатывания
        # на нормальные слова вроде "latest" (содержит "test").
        marker_patterns = [
            r"\bдемо\b",
            r"\bdemo\b",
            r"\bsample\b",
            r"\bmock\b",
            r"\bplaceholder\b",
            r"товар\s*wildberries",
        ]
        
        fields_to_check = [
            str(data.get("name") or "").lower(),
            str(data.get("description") or "").lower(),
            str(data.get("brand") or "").lower(),
            str(data.get("category") or "").lower(),
            str(data.get("warning") or "").lower(),
        ]
        
        for value in fields_to_check:
            for pattern in marker_patterns:
                if re.search(pattern, value):
                    return True

        return False
    
    def _is_generic_marketplace_title(self, value: Optional[str]) -> bool:
        """
        Проверка, что название похоже на общий заголовок витрины,
        а не на реальное название карточки товара.
        """
        if not value:
            return False

        normalized = str(value).strip().lower()
        if len(normalized) < 6:
            return True

        generic_patterns = [
            r"^интернет[\s\-]?магазин\s+wildberries",
            r"широкий\s+ассортимент\s+товаров",
            r"скидки\s+каждый\s+день",
            r"^wildberries\b",
            r"^ozon\b",
        ]
        
        return any(re.search(pattern, normalized) for pattern in generic_patterns)
    
    def _extract_wb_nm_id_from_url(self, url: str) -> Optional[str]:
        """
        Извлечь nm_id товара Wildberries из разных форматов URL.
        """
        patterns = [
            r"/catalog/(\d+)",
            r"/product/(\d+)",
            r"/detail\.aspx/(\d+)",
            r"[?&]nm=(\d+)",
            r"[?&]nm_id=(\d+)",
            r"[?&]imt_id=(\d+)",
            r"/detail\.aspx\?[^#]*?(?:^|&)nm=(\d+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def _extract_ozon_product_id_from_url(self, url: str) -> Optional[str]:
        """
        Извлечь product_id товара Ozon из URL.

        Поддерживает форматы вида:
        - /product/<slug>-123456789/
        - /product/123456789/
        - ?product_id=123456789
        """
        patterns = [
            r"/product/(?:[\w\-]+-)?(\d+)(?:[/?#]|$)",
            r"[?&]product_id=(\d+)",
            r"[?&]sku=(\d+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def _extract_yandex_market_id_from_url(self, url: str) -> Optional[str]:
        """
        Извлечь product/offer id из URL Яндекс Маркета.
        """
        patterns = [
            r"/product--[^/]+/(\d+)(?:[/?#]|$)",
            r"/product/(\d+)(?:[/?#]|$)",
            r"[?&]sku=(\d+)",
            r"[?&]offerid=([\w\-]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def _extract_avito_id_from_url(self, url: str) -> Optional[str]:
        """
        Извлечь id объявления Avito.
        """
        patterns = [
            r"_(\d+)(?:[/?#]|$)",
            r"[?&]itemId=(\d+)",
            r"[?&]id=(\d+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def _extract_external_id_from_url(self, marketplace: str, url: str) -> Optional[str]:
        """
        Универсально извлечь external_id товара по маркетплейсу.

        Возвращает None, если надёжно извлечь идентификатор не удалось.
        """
        marketplace_normalized = (marketplace or "").lower()

        if marketplace_normalized == "wildberries":
            return self._extract_wb_nm_id_from_url(url)
        if marketplace_normalized == "ozon":
            return self._extract_ozon_product_id_from_url(url)
        if marketplace_normalized == "yandex_market":
            return self._extract_yandex_market_id_from_url(url)
        if marketplace_normalized == "avito":
            return self._extract_avito_id_from_url(url)

        # Общий fallback для прочих маркетплейсов: последний числовой сегмент URL.
        generic_match = re.search(r"/(\d+)(?:[/?#]|$)", url)
        if generic_match:
            return generic_match.group(1)

        return None

    def extract_external_id(self, url: str, marketplace: Optional[str] = None) -> Optional[str]:
        """
        Публичный метод для получения external_id.

        Нужен для повторного использования в API/Celery и исключения
        дублирования регулярных выражений в разных слоях.
        """
        detected_marketplace = marketplace or self._determine_marketplace(url)
        return self._extract_external_id_from_url(detected_marketplace, url)

    def _to_int_safe(self, value: Any) -> Optional[int]:
        """
        Безопасно привести значение к int.

        Поддерживает числа и строки вида "1 234", "1,234", "1234".
        Возвращает None, если значение не удалось корректно преобразовать.
        """
        if value is None:
            return None

        if isinstance(value, bool):
            return None

        if isinstance(value, (int, float)):
            return int(value)

        text = str(value).strip()
        if not text:
            return None

        cleaned = re.sub(r"[^\d]", "", text)
        if not cleaned:
            return None

        try:
            return int(cleaned)
        except (TypeError, ValueError):
            return None

    def _extract_sales_per_day(self, payload: Dict[str, Any]) -> Optional[int]:
        """
        Попробовать извлечь «продажи в день» из различных полей payload.

        В публичных WB-источниках это поле часто отсутствует,
        поэтому метод возвращает None, если надёжного значения нет.
        """
        keys = [
            "salesPerDay",
            "sales_per_day",
            "ordersPerDay",
            "orders_per_day",
            "avgOrdersPerDay",
            "avg_orders_per_day",
            "avgSalesPerDay",
            "avg_sales_per_day",
        ]
        
        for key in keys:
            value = self._to_int_safe(payload.get(key))
            if value is not None and value >= 0:
                return value

        return None

    def _normalize_wb_price_value(self, value: Any) -> Optional[int]:
        """
        Нормализовать цену WB к рублям.

        В некоторых источниках WB цена приходит в копейках (priceU/salePriceU),
        в других — сразу в рублях.
        """
        price_raw = self._to_int_safe(value)
        if price_raw is None or price_raw <= 0:
            return None

        # Для WB значения в копейках обычно значительно больше 100000.
        # Например 149990 => 1499 руб.
        if price_raw >= 100000:
            return int(price_raw / 100)

        return price_raw

    def _extract_wb_prices_from_product(self, product: Dict[str, Any]) -> Dict[str, Optional[int]]:
        """
        Извлечь price/old_price из WB payload с учётом разных структур.

        WB может отдавать цены:
        - на верхнем уровне карточки (salePriceU/priceU и т.д.),
        - внутри массива размеров sizes[*].price.{total,product,basic}.
        """
        price: Optional[int] = None
        old_price: Optional[int] = None

        direct_price_candidates = [
            product.get("salePriceU"),
            product.get("priceU"),
            product.get("salePrice"),
            product.get("finalPrice"),
            product.get("final_price"),
            product.get("price"),
        ]
        direct_old_price_candidates = [
            product.get("priceU"),
            product.get("oldPriceU"),
            product.get("oldPrice"),
            product.get("old_price"),
            product.get("price"),
        ]
        
        size_price_candidates: List[Any] = []
        size_old_price_candidates: List[Any] = []

        sizes = product.get("sizes")
        if isinstance(sizes, list):
            for size in sizes:
                if not isinstance(size, dict):
                    continue

                price_obj = size.get("price")
                if isinstance(price_obj, dict):
                    size_price_candidates.extend([
                        price_obj.get("total"),
                        price_obj.get("product"),
                        price_obj.get("walletPrice"),
                        price_obj.get("price"),
                    ])
                    size_old_price_candidates.extend([
                        price_obj.get("basic"),
                        price_obj.get("oldPrice"),
                        price_obj.get("old_price"),
                        price_obj.get("product"),
                    ])

                size_price_candidates.extend([
                    size.get("salePriceU"),
                    size.get("priceU"),
                    size.get("salePrice"),
                    size.get("price"),
                ])
                size_old_price_candidates.extend([
                    size.get("priceU"),
                    size.get("oldPriceU"),
                    size.get("oldPrice"),
                    size.get("old_price"),
                    size.get("price"),
                ])

        for candidate in [*direct_price_candidates, *size_price_candidates]:
            parsed = self._normalize_wb_price_value(candidate)
            if parsed is not None and parsed > 0:
                price = parsed
                break

        for candidate in [*direct_old_price_candidates, *size_old_price_candidates]:
            parsed = self._normalize_wb_price_value(candidate)
            if parsed is None or parsed <= 0:
                continue
        
            # old_price должен быть не меньше текущей цены.
            if price is None or parsed >= price:
                old_price = parsed
                break

        return {
            "price": price,
            "old_price": old_price,
        }

    async def _extract_wb_embedded_metrics(self, page: Page) -> Dict[str, Any]:
        """
        Извлечь price/rating/reviews/sales из встроенных JSON-данных страницы WB.

        Это fallback на случай, когда селекторы недоступны из-за антибота,
        но данные уже присутствуют внутри HTML/скриптов.
        """
        try:
            html = await page.content()
            if not html:
                return {}

            result: Dict[str, Any] = {}

            # Цена (возможны копейки в полях *PriceU).
            # Ищем в числовых ключах и в size.price.{total,product,basic}.
            price_patterns = [
                r'"salePriceU"\s*:\s*"?(\d+)"?',
                r'"priceU"\s*:\s*"?(\d+)"?',
                r'"salePrice"\s*:\s*"?(\d+)"?',
                r'"finalPrice"\s*:\s*"?(\d+)"?',
                r'"final_price"\s*:\s*"?(\d+)"?',
                r'"price"\s*:\s*"?(\d+)"?',
                r'"total"\s*:\s*"?(\d+)"?',
                r'"product"\s*:\s*"?(\d+)"?',
            ]
            for pattern in price_patterns:
                matches = re.findall(pattern, html)
                for raw_value in matches:
                    parsed_price = self._normalize_wb_price_value(raw_value)
                    if parsed_price is not None and parsed_price > 0:
                        result["price"] = parsed_price
                        break
                if result.get("price"):
                    break

            # Старая цена — преимущественно priceU/oldPrice/basic.
            old_price_patterns = [
                r'"priceU"\s*:\s*"?(\d+)"?',
                r'"oldPriceU"\s*:\s*"?(\d+)"?',
                r'"oldPrice"\s*:\s*"?(\d+)"?',
                r'"basic"\s*:\s*"?(\d+)"?',
            ]
            for pattern in old_price_patterns:
                matches = re.findall(pattern, html)
                for raw_value in matches:
                    parsed_old_price = self._normalize_wb_price_value(raw_value)
                    if parsed_old_price is not None and parsed_old_price > 0:
                        if result.get("price") is None or parsed_old_price >= result.get("price"):
                            result["old_price"] = parsed_old_price
                            break
                if result.get("old_price"):
                    break

            # Рейтинг.
            rating_patterns = [
                r'"reviewRating"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
                r'"rating"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
                r'"imt_rating"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
            ]
            for pattern in rating_patterns:
                rating_match = re.search(pattern, html)
                if not rating_match:
                    continue
                try:
                    rating_value = float(rating_match.group(1))
                    if rating_value >= 0:
                        result["rating"] = rating_value
                        break
                except (TypeError, ValueError):
                    continue

            # Количество отзывов.
            reviews_patterns = [
                r'"feedbacks"\s*:\s*"?(\d+)"?',
                r'"feedbackCount"\s*:\s*"?(\d+)"?',
                r'"imt_feedbacks"\s*:\s*"?(\d+)"?',
                r'"reviewCount"\s*:\s*"?(\d+)"?',
            ]
            for pattern in reviews_patterns:
                reviews_match = re.search(pattern, html)
                if not reviews_match:
                    continue
                parsed_reviews = self._to_int_safe(reviews_match.group(1))
                if parsed_reviews is not None and parsed_reviews >= 0:
                    result["reviews_count"] = parsed_reviews
                    break

            # Продажи в день (если присутствуют в embedded-данных).
            sales_patterns = [
                r'"salesPerDay"\s*:\s*"?(\d+)"?',
                r'"ordersPerDay"\s*:\s*"?(\d+)"?',
                r'"avgOrdersPerDay"\s*:\s*"?(\d+)"?',
                r'"avgSalesPerDay"\s*:\s*"?(\d+)"?',
                r'"ordersCount"\s*:\s*"?(\d+)"?',
            ]
            for pattern in sales_patterns:
                sales_match = re.search(pattern, html)
                if sales_match:
                    parsed_sales = self._to_int_safe(sales_match.group(1))
                    if parsed_sales is not None and parsed_sales >= 0:
                        result["sales_per_day"] = parsed_sales
                        break

            return result
        except Exception:
            return {}


    
    async def parse_url(
        self,
        url: str,
        proxy_url: Optional[str] = None,
        timeout: int = 180000  # 3 минуты
    ) -> Dict[str, Any]:
        """
        Распарсить URL товара.
        
        Args:
            url: URL страницы товара
            proxy_url: URL прокси
            timeout: Таймаут в миллисекундах (по умолчанию 180000 = 3 мин)
        
        Returns:
            Данные товара
        """
        validated_url = self.validate_product_url(url)
        marketplace = self.detect_marketplace(validated_url)
        normalized_url = self._normalize_marketplace_url(validated_url, marketplace)

        logger.info(
            f"🕷️ Парсинг {marketplace}: {normalized_url} (proxy={proxy_url is not None}, original_url={url})"
        )
        
        use_proxy = proxy_url is not None
        data: Dict[str, Any]
        
        # Для Wildberries используем продвинутый метод
        if marketplace == "wildberries":
            logger.info("🔴 WB обнаружен - используем продвинутый метод парсинга")
            browser_error: Optional[Exception] = None
            try:
                data = await self._parse_wildberries_advanced(normalized_url, proxy_url if use_proxy else None, timeout)
            except ParserError as wb_error:
                # Браузерный путь упал (таймаут/антибот) — продолжаем с пустым
                # каркасом, ниже обогатим его публичными JSON-источниками WB.
                browser_error = wb_error
                logger.warning(f"⚠️ WB browser-парсинг не удался, переходим к публичным JSON-источникам: {wb_error}")
                data = {
                    "url": normalized_url,
                    "marketplace": "wildberries",
                    "name": None,
                    "price": None,
                    "old_price": None,
                    "discount": 0,
                    "rating": None,
                    "reviews_count": None,
                    "sales_per_day": None,
                    "sales_count": None,
                    "brand": None,
                    "category": None,
                    "seller": None,
                    "parsed_at": datetime.utcnow().isoformat(),
                }

            # ВАЖНО: публичные JSON-источники WB (card.wb.ru / basket CDN) подключаем
            # ВСЕГДА, когда чего-то не хватает, а не только при ParserError.
            # Браузерный путь часто отдаёт частичный результат БЕЗ исключения
            # (например, name по fallback и price=None), и тогда раньше данные
            # из надёжного basket-CDN не подтягивались вовсе.
            needs_enrichment = (
                not isinstance(data, dict)
                or not data.get("name")
                or self._is_generic_marketplace_title(data.get("name"))
                or data.get("price") is None
                or not data.get("category")
                or data.get("rating") is None
                or data.get("reviews_count") is None
            )

            if needs_enrichment:
                logger.info("🔎 WB: дополняем данные из публичных JSON-источников (card.wb.ru/basket)")
                wb_api_data = await self._extract_wb_card_api_data(
                    normalized_url, proxy_url=proxy_url if use_proxy else None
                )

                if not isinstance(data, dict):
                    data = {"url": normalized_url, "marketplace": "wildberries"}

                if wb_api_data:
                    # Дополняем только недостающие поля, не затирая то, что уже извлёк браузер.
                    for key in ("name", "price", "old_price", "rating", "reviews_count", "brand", "category", "seller", "sales_per_day"):
                        api_value = wb_api_data.get(key)
                        current = data.get(key)
                        if api_value not in (None, "") and current in (None, ""):
                            data[key] = api_value

                    # sales_count держим синхронным с sales_per_day для модели Product.
                    if data.get("sales_count") in (None, 0) and data.get("sales_per_day") is not None:
                        data["sales_count"] = data.get("sales_per_day")

                    # Пересчитываем скидку, если есть обе цены.
                    price = data.get("price")
                    old_price = data.get("old_price")
                    if price and old_price and old_price > price:
                        data["discount"] = int((1 - price / old_price) * 100)

                    source_note = "API fallback" if browser_error else "публичные JSON-источники WB"
                    if data.get("price") is not None:
                        data["warning"] = f"Часть данных WB получена через {source_note}."
                    else:
                        data["warning"] = f"WB отдал карточку без цены ({source_note}); цена временно недоступна."
                else:
                    if browser_error:
                        data["warning"] = f"WB недоступен для браузерного и API парсинга: {browser_error}"
                    else:
                        data["warning"] = "Карточка WB распарсена частично: публичные источники не вернули недостающие поля."
        # Для Ozon используем продвинутый метод
        elif marketplace == "ozon":
            logger.info("🔴 Ozon обнаружен - используем продвинутый метод парсинга")
            data = await self._parse_ozon_advanced(normalized_url, proxy_url if use_proxy else None, timeout)
        # Для остальных маркетплейсов - стандартный метод
        else:
            # Для прочих маркетплейсов используем единый стабильный путь
            # через локальный контекст Playwright, чтобы не зависеть от self.browser.
            async with async_playwright() as p:
                data = await self._parse_with_browser(
                    p, normalized_url, marketplace, proxy_url if use_proxy else None, timeout
                )
                
        # Финальная валидация, чтобы не пропускать демо/заглушки как успешный парсинг
        if self._contains_demo_markers(data):
            raise ParserError("Обнаружены демо/заглушечные данные в результате парсинга")

        # Нормализация «пустой» цены: 0 и отрицательные значения считаем отсутствием цены.
        if data.get("price") is not None:
            try:
                if int(data.get("price")) <= 0:
                    data["price"] = None
            except (TypeError, ValueError):
                data["price"] = None

        # Нормализация рейтинга.
        if data.get("rating") is not None:
            try:
                rating_value = float(str(data.get("rating")).replace(",", "."))
                data["rating"] = max(0.0, min(rating_value, 5.0))
            except (TypeError, ValueError):
                data["rating"] = None

        # Нормализация числа отзывов.
        if data.get("reviews_count") is not None:
            reviews_value = self._to_int_safe(data.get("reviews_count"))
            data["reviews_count"] = reviews_value if reviews_value is not None and reviews_value >= 0 else None

        # Нормализация продаж в день.
        if data.get("sales_per_day") is not None:
            sales_value = self._to_int_safe(data.get("sales_per_day"))
            data["sales_per_day"] = sales_value if sales_value is not None and sales_value >= 0 else None

        # Для совместимости с существующей моделью Product сохраняем также в sales_count.
        if data.get("sales_count") is None and data.get("sales_per_day") is not None:
            data["sales_count"] = data.get("sales_per_day")

        # Отбрасываем общий заголовок маркетплейса вместо названия карточки товара.
        if self._is_generic_marketplace_title(data.get("name")):
            data["name"] = None

        # Вычисляем единый внешний идентификатор товара для БД/API.
        external_id = self._extract_external_id_from_url(marketplace, normalized_url)
        data["external_id"] = external_id

        # Если название отсутствует, подставляем нейтральный fallback из URL,
        # чтобы результат можно было сохранить и отобразить пользователю.
        if not data.get("name"):
            product_id = external_id or "unknown"
            data["name"] = f"Товар {marketplace} #{product_id}"
            data["warning"] = "Название не извлечено из страницы, использован fallback по URL."

        # Важно: не требуем одновременно и name, и price.
        # На некоторых страницах одно из полей может временно отсутствовать
        # из-за антибот-защиты или задержки рендера, но это всё равно реальные данные.
        # После fallback названия проверка остаётся только на случай полностью пустого результата.
        if not data.get("name") and not data.get("price"):
            raise ParserError("Не удалось извлечь ключевые поля товара (name/price)")

        # Валидируем цену только если она действительно извлечена.
        if data.get("price") is not None and data.get("price", 0) > 1_000_000:
            raise ParserError("Извлечена некорректная цена товара")

        # Признак частичного результата + перечень незаполненных ключевых полей.
        # Backward-compatible: добавляем доп. ключи внутрь data, response shape не меняется,
        # фронтенд (alias-normalizer) уже корректно показывает partial.
        used_fallback_name = bool(data.get("name")) and str(data.get("name", "")).startswith(f"Товар {marketplace} #")
        missing_fields = [
            field for field in ("name", "price", "rating", "reviews_count", "brand", "category")
            if data.get(field) in (None, "") or (field == "name" and used_fallback_name)
        ]
        data["partial"] = len(missing_fields) > 0
        data["missing_fields"] = missing_fields

        # Безопасное диагностическое логирование (без cookies/токенов/ключей).
        logger.info(
            "🧾 Parse summary: marketplace=%s external_id=%s http_source=%s "
            "name=%s price=%s old_price=%s rating=%s reviews=%s brand=%s category=%s partial=%s missing=%s"
            % (
                marketplace,
                data.get("external_id"),
                "browser+public_json" if marketplace == "wildberries" else "browser",
                "yes" if data.get("name") and not used_fallback_name else ("fallback" if used_fallback_name else "no"),
                data.get("price"),
                data.get("old_price"),
                data.get("rating"),
                data.get("reviews_count"),
                "yes" if data.get("brand") else "no",
                "yes" if data.get("category") else "no",
                data.get("partial"),
                ",".join(missing_fields) or "-",
            )
        )

        return data
            
    async def _parse_with_browser(
        self,
        p,
        url: str,
        marketplace: str,
        proxy_url: Optional[str],
        timeout: int = 60000
    ) -> Dict[str, Any]:
        """Стандартный метод парсинга для Ozon, Yandex, Avito."""
        browser = None
        context = None

        try:
            browser_args = {
                "headless": True,
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--window-size=1920,1080",
                ]
            }
            
            if proxy_url:
                browser_args["proxy"] = {"server": proxy_url}
            
            if p:
                browser = await p.chromium.launch(**browser_args)
            else:
                browser = await self.browser.chromium.launch(**browser_args) if self.browser else None
            
            if not browser:
                raise ParserError("Браузер не инициализирован")
            
            context = await browser.new_context(
                user_agent=random.choice(self.USER_AGENTS),
                viewport={"width": 1920, "height": 1080},
                locale="ru-RU",
                timezone_id="Europe/Moscow",
            )
            
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)

            page = await context.new_page()
            
            logger.info(f"🌐 Переход на страницу: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            
            await asyncio.sleep(3)
            
            try:
                await page.wait_for_selector("h1", timeout=10000)
            except PlaywrightTimeout:
                logger.warning("⚠️ Таймаут ожидания контента")
            
            await asyncio.sleep(2)
            
            data = {
                "url": url,
                "marketplace": marketplace,
                "name": await self._extract_text(page, await self._get_selector(marketplace, "name")),
                "price": await self._extract_price(page, marketplace),
                "old_price": await self._extract_old_price(page, marketplace),
                "rating": await self._extract_rating(page, marketplace),
                "reviews_count": await self._extract_reviews_count(page, marketplace),
                "brand": await self._extract_text(page, await self._get_selector(marketplace, "brand")),
                "category": await self._extract_text(page, await self._get_selector(marketplace, "category")),
                "seller": await self._extract_text(page, await self._get_selector(marketplace, "seller")),
                "parsed_at": datetime.utcnow().isoformat(),
            }
            
            if data["price"] and data["old_price"] and data["old_price"] > data["price"]:
                data["discount"] = int((1 - data["price"] / data["old_price"]) * 100)
            else:
                data["discount"] = 0
            
            logger.info(f"📦 Результаты: {data['name'][:50] if data['name'] else '❌'}...")
            
            if not data["name"]:
                h1 = await page.query_selector("h1")
                if h1:
                    data["name"] = await h1.inner_text()
            
            # Дополнительный fallback на структурированные данные страницы
            # для маркетплейсов, где селекторы могли измениться.
            if not data.get("name") or data.get("price") is None:
                structured = await self._extract_structured_product_data(page)
                if not data.get("name") and structured.get("name"):
                    data["name"] = structured.get("name")
                if data.get("price") is None and structured.get("price") is not None:
                    data["price"] = int(structured.get("price"))
                if data.get("old_price") is None and structured.get("old_price") is not None:
                    data["old_price"] = int(structured.get("old_price"))
                if data.get("rating") is None and structured.get("rating") is not None:
                    data["rating"] = structured.get("rating")
                if data.get("reviews_count") is None and structured.get("reviews_count") is not None:
                    data["reviews_count"] = structured.get("reviews_count")

            # Не прерываем парсинг при частично извлечённых данных.
            # Критической ошибкой считаем только полностью пустой результат.
            if not data.get("name") and data.get("price") is None:
                raise ParserError("Не удалось извлечь ключевые поля товара (name/price)")
            
            await page.close()
            await context.close()
            await browser.close()
            return data
        
        except PlaywrightTimeout:
            logger.error(f"⏰ Таймаут при парсинге {url}")
            if context:
                await context.close()
            if browser:
                await browser.close()
            raise ParserError("Таймаут при загрузке страницы")
        
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга {url}: {type(e).__name__}: {e}")
            if context:
                await context.close()
            if browser:
                await browser.close()
            raise ParserError(f"Ошибка парсинга: {str(e)}")

    async def _parse_wildberries_advanced(
        self,
        url: str,
        proxy_url: Optional[str],
        timeout: int
    ) -> Dict[str, Any]:
        """
        Продвинутый парсинг Wildberries с МАКСИМАЛЬНЫМ обходом защиты.
        Использует Chromium с улучшенными настройками + JS evaluation.
        """
        browser = None
        context = None
        page = None

        try:
            async with async_playwright() as p:
                # Запускаем Chromium с максимальным скрытием.
                # Важно: если передан proxy_url, обязательно пробрасываем его
                # в browser.launch, иначе WB-парсинг фактически идёт без прокси.
                launch_args = {
                    "headless": True,
                    "args": [
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-accelerated-2d-canvas",
                        "--disable-gpu",
                        "--window-size=1920,1080",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--disable-site-isolation-trials",
                        "--disable-features=ImprovedCookieControls",
                        "--no-first-run",
                        "--no-default-browser-check",
                    ],
                }
                if proxy_url:
                    launch_args["proxy"] = {"server": proxy_url}

                browser = await p.chromium.launch(**launch_args)
                
                # Desktop User-Agent (стабильнее работает)
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                
                # Создаём контекст с реалистичными параметрами
                context = await browser.new_context(
                    user_agent=user_agent,
                    viewport={"width": 1920, "height": 1080},
                    locale="ru-RU",
                    timezone_id="Europe/Moscow",
                    extra_http_headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Sec-Fetch-User": "?1",
                        "Cache-Control": "max-age=0",
                    },
                )
                
                # Скрипт для скрытия автоматизации (МАКСИМАЛЬНЫЙ)
                await context.add_init_script("""
                    // Скрываем webdriver
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });
                    
                    // Подделываем плагины
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5],
                    });
                    
                    // Подделываем языки
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['ru-RU', 'ru', 'en-US', 'en'],
                    });
                    
                    // Подделываем аппаратную информацию
                    Object.defineProperty(navigator, 'hardwareConcurrency', {
                        get: () => 8,
                    });
                    Object.defineProperty(navigator, 'deviceMemory', {
                        get: () => 8,
                    });
                    
                    // Подделываем userAgent
                    Object.defineProperty(navigator, 'userAgent', {
                        get: () => 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
                    });
                    
                    // Подделываем vendor
                    Object.defineProperty(navigator, 'vendor', {
                        get: () => 'Apple Computer, Inc.',
                    });
                    
                    // Подделываем platform
                    Object.defineProperty(navigator, 'platform', {
                        get: () => 'iPhone',
                    });
                    
                    // Удаляем permision
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                """)
                
                page = await context.new_page()
                
                # Реалистичная задержка перед запросом
                await asyncio.sleep(random.uniform(3, 5))
                
                logger.info(f"🌐 Переход на WB (Mobile): {url}")
                logger.info(f"📋 User-Agent: {user_agent[:50]}...")
                if proxy_url:
                    logger.info(f"🔹 WB используем прокси: {proxy_url}")
                else:
                    logger.warning("⚠️ WB парсинг БЕЗ прокси")
                
                # Переход на страницу
                response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                
                # Проверяем ответ
                if response:
                    status = response.status
                    logger.info(f"📊 Статус ответа: {status}")
                    
                    if status == 403:
                        raise ParserError("WB вернул 403 - доступ запрещён (блокировка)")
                    elif status == 404:
                        raise ParserError("Страница товара не найдена (404)")
                    elif status == 503:
                        raise ParserError("WB недоступен (503)")
                
                # Ждём загрузки основного контента
                try:
                    await page.wait_for_selector("h1, .product-header, [data-nm]", timeout=15000)
                    logger.info("✅ Основной контент загрузился")
                except PlaywrightTimeout:
                    logger.warning("⚠️ Таймаут ожидания контента")
                
                # Дополнительная задержка для JS
                await asyncio.sleep(random.uniform(5, 7))
                
                # Проверяем, не заблокировали ли нас
                page_title = await page.title()
                logger.info(f"📄 Заголовок страницы: {page_title[:80] if page_title else '❌ None'}")
                
                # Если заголовок содержит "блокировка" или "captcha" - нас заблокировали
                if page_title and any(word in page_title.lower() for word in ['блокировка', 'captcha', 'robot', 'проверка']):
                    logger.error(f"🚫 WB обнаружил бота: {page_title}")
                    raise ParserError(f"WB обнаружил автоматизацию: {page_title}")
                
                # Debug-дамп (screenshot + HTML) только в dev при явном opt-in.
                await _save_parser_debug_dump(page, "wb")
                
                # Извлекаем данные через JavaScript (более надёжно)
                data = await self._extract_wildberries_data_js(page, url)
                
                # Fallback-1: если name/price не извлеклись селекторами, пробуем JSON-LD/meta
                if not data.get("name") or not data.get("price"):
                    structured = await self._extract_structured_product_data(page)
                    if not data.get("name") and structured.get("name"):
                        data["name"] = structured.get("name")
                    if not data.get("price") and structured.get("price"):
                        data["price"] = int(structured.get("price"))
                    if not data.get("old_price") and structured.get("old_price"):
                        data["old_price"] = int(structured.get("old_price"))
                    if data.get("rating") is None and structured.get("rating") is not None:
                        data["rating"] = structured.get("rating")
                    if data.get("reviews_count") is None and structured.get("reviews_count") is not None:
                        data["reviews_count"] = structured.get("reviews_count")
                
                # Fallback-2: встроенные JSON-данные страницы WB (часто есть даже при антиботе)
                if (
                    not data.get("price")
                    or data.get("rating") is None
                    or data.get("reviews_count") is None
                    or data.get("sales_per_day") is None
                ):
                    embedded_data = await self._extract_wb_embedded_metrics(page)
                    for field in ["price", "old_price", "rating", "reviews_count", "sales_per_day"]:
                        if data.get(field) is None and embedded_data.get(field) is not None:
                            data[field] = embedded_data.get(field)

                # Fallback-3: WB API/JSON источники по nm_id
                if (
                    not data.get("name")
                    or not data.get("price")
                    or data.get("rating") is None
                    or data.get("reviews_count") is None
                    or data.get("sales_per_day") is None
                ):
                    wb_api_data = await self._extract_wb_card_api_data(url, proxy_url=proxy_url)
                    for field in ["name", "price", "old_price", "brand", "rating", "reviews_count", "sales_per_day", "seller"]:
                        if data.get(field) is None and wb_api_data.get(field) is not None:
                            data[field] = wb_api_data.get(field)

                logger.info(
                    f"✅ WB данные: name={data.get('name', '❌')[:50] if data.get('name') else '❌'}, "
                    f"price={data.get('price')}, rating={data.get('rating')}, "
                    f"reviews={data.get('reviews_count')}, sales/day={data.get('sales_per_day')}"
                )
                
                await page.close()
                await context.close()
                await browser.close()
                
                return data
        
        except PlaywrightTimeout:
            logger.error("⏰ Таймаут при парсинге WB")
            raise ParserError("Таймаут при загрузке страницы WB")
        
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга WB: {type(e).__name__}: {e}")
            raise ParserError(f"Ошибка парсинга WB: {str(e)}")
    
        finally:
            # Закрываем ресурсы корректно
            try:
                if page:
                    await page.close()
            except Exception:
                pass
            try:
                if context:
                    await context.close()
            except Exception:
                pass
            try:
                if browser:
                    await browser.close()
            except Exception:
                pass
    
    async def _extract_structured_product_data(self, page: Page) -> Dict[str, Any]:
        """
        Универсальный fallback: извлечь ключевые данные из JSON-LD и meta-тегов.
        """
        try:
            extracted = await page.evaluate("""
                () => {
                    const result = {
                        name: null,
                        price: null,
                        old_price: null,
                        rating: null,
                        reviews_count: null,
                    };

                    const toNumber = (value) => {
                        if (value === null || value === undefined) return null;
                        const text = String(value).replace(/[^\\d.,]/g, '').replace(',', '.');
                        const num = parseFloat(text);
                        return Number.isFinite(num) && num > 0 ? num : null;
                    };

                    const toInt = (value) => {
                        if (value === null || value === undefined) return null;
                        const text = String(value).replace(/[^\\d]/g, '');
                        if (!text) return null;
                        const num = parseInt(text, 10);
                        return Number.isFinite(num) && num >= 0 ? num : null;
                    };

                    const isGenericTitle = (value) => {
                        if (!value) return false;
                        const normalized = String(value).trim().toLowerCase();
                        return (
                            normalized.startsWith('интернет-магазин wildberries') ||
                            normalized.includes('широкий ассортимент товаров') ||
                            normalized.includes('скидки каждый день') ||
                            normalized === 'wildberries' ||
                            normalized === 'ozon'
                        );
                    };

                    const trySet = (nameValue, priceValue, oldPriceValue = null, ratingValue = null, reviewsValue = null) => {
                        if (!result.name && nameValue && String(nameValue).trim().length > 2 && !isGenericTitle(nameValue)) {
                            result.name = String(nameValue).trim();
                        }
                        if (!result.price) {
                            result.price = toNumber(priceValue);
                        }
                        if (!result.old_price) {
                            result.old_price = toNumber(oldPriceValue);
                        }
                        if (!result.rating) {
                            result.rating = toNumber(ratingValue);
                        }
                        if (result.reviews_count === null) {
                            result.reviews_count = toInt(reviewsValue);
                        }
                    };

                    // 1) JSON-LD
                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    for (const script of scripts) {
                        const raw = script.textContent?.trim();
                        if (!raw) continue;
                        try {
                            const parsed = JSON.parse(raw);
                            const nodes = Array.isArray(parsed)
                                ? parsed
                                : (parsed['@graph'] && Array.isArray(parsed['@graph']) ? parsed['@graph'] : [parsed]);

                            for (const node of nodes) {
                                if (!node || typeof node !== 'object') continue;
                                const nodeType = String(node['@type'] || '').toLowerCase();

                                if (nodeType.includes('product')) {
                                    const offers = node.offers || {};
                                    const offerPrice = Array.isArray(offers)
                                        ? offers[0]?.price
                                        : (offers.price || offers.lowPrice || offers.highPrice);

                                    const aggregate = node.aggregateRating || {};
                                    const ratingValue = aggregate.ratingValue || node.ratingValue || null;
                                    const reviewsValue = aggregate.reviewCount || aggregate.ratingCount || node.reviewCount || node.ratingCount || null;

                                    trySet(node.name, offerPrice, offers?.highPrice || null, ratingValue, reviewsValue);
                                }
                            }
                        } catch (_) {
                            // игнорируем невалидный JSON-LD
                        }
                    }

                    // 2) Meta fallback
                    const metaName =
                        document.querySelector('meta[property="og:title"]')?.content ||
                        document.querySelector('meta[name="twitter:title"]')?.content ||
                        null;

                    const metaPrice =
                        document.querySelector('meta[property="product:price:amount"]')?.content ||
                        document.querySelector('meta[itemprop="price"]')?.content ||
                        null;

                    const metaRating =
                        document.querySelector('meta[itemprop="ratingValue"]')?.content ||
                        null;

                    const metaReviews =
                        document.querySelector('meta[itemprop="reviewCount"]')?.content ||
                        document.querySelector('meta[itemprop="ratingCount"]')?.content ||
                        null;

                    trySet(metaName, metaPrice, null, metaRating, metaReviews);

                    return result;
                }
            """)

            return extracted or {"name": None, "price": None, "old_price": None, "rating": None, "reviews_count": None}
        except Exception:
            return {"name": None, "price": None, "old_price": None, "rating": None, "reviews_count": None}

    def _wb_basket_hosts(self) -> List[str]:
        """
        Список basket-хостов WB CDN в порядке перебора.

        WB шардит карточки по vol-диапазонам на хостах basket-01..basket-NN,
        и сопоставление vol->host нестабильно и периодически расширяется
        (новые товары уезжают на более высокие хосты, напр. basket-41).
        Поэтому вместо хрупкой таблицы перебираем широкий диапазон, а сам
        перебор выполняется конкурентно (см. _wb_fetch_first_json), чтобы это
        было быстро и не зависело от точной формулы.
        """
        return [f"basket-{i:02d}.wbbasket.ru" for i in range(1, 51)]

    async def _wb_fetch_first_json(
        self,
        client: httpx.AsyncClient,
        urls: List[str],
        chunk_size: int = 25,
    ) -> Optional[Dict[str, Any]]:
        """
        Конкурентно опросить список URL и вернуть JSON первого ответа 200.

        Запросы выполняются пачками (chunk_size), чтобы не открывать сразу
        полсотни соединений. Ошибки/таймауты отдельных хостов игнорируются —
        это нормально для перебора basket-CDN.
        """
        for start in range(0, len(urls), chunk_size):
            chunk = urls[start:start + chunk_size]

            async def _try(u: str):
                try:
                    resp = await client.get(u)
                    if resp.status_code == 200:
                        return u, resp
                except Exception:
                    return None
                return None

            results = await asyncio.gather(*[_try(u) for u in chunk], return_exceptions=True)
            for res in results:
                if not res or isinstance(res, Exception):
                    continue
                found_url, response = res
                try:
                    payload = response.json()
                except Exception:
                    continue
                if isinstance(payload, (dict, list)):
                    logger.info(f"🟢 WB basket источник найден: {found_url}")
                    return {"_source_url": found_url, "_payload": payload}
        return None

    async def _extract_wb_card_api_data(self, url: str, proxy_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Fallback для Wildberries: получить данные по nm_id из доступных публичных источников.

        Последовательность:
        1) card.wb.ru/cards/v4/detail (может отдавать 403)
        2) card.wb.ru/cards/detail (legacy-эндпоинт, иногда работает, когда v4 заблокирован)
        3) basket-XX.wbbasket.ru/.../card.json (обычно стабильно для name/brand)

        Важно: basket card.json не всегда содержит цену, поэтому цена может остаться None.

        Args:
            url: URL карточки товара WB
            proxy_url: URL прокси в формате http://user:pass@host:port (опционально)
        """
        nm_id = self._extract_wb_nm_id_from_url(url)
        if not nm_id:
            return {}

        async def _from_card_v4(client: httpx.AsyncClient) -> Dict[str, Any]:
            # Пробуем несколько регионов (dest), так как WB может отдавать разные данные.
            destinations = ["-1257786", "-1029256", "-123", "-1"]

            for dest in destinations:
                api_url = f"https://card.wb.ru/cards/v4/detail?appType=1&curr=rub&dest={dest}&spp=0&nm={nm_id}"
                try:
                    response = await client.get(api_url)
                    if response.status_code == 404:
                        continue
                    response.raise_for_status()
                    payload = response.json()

                    products = payload.get("data", {}).get("products", [])
                    if not products:
                        continue

                    product = None
                    for candidate in products:
                        if str(candidate.get("id")) == str(nm_id) or str(candidate.get("nmId")) == str(nm_id):
                            product = candidate
                            break

                    # Критично: не берём products[0], если nm_id не совпал.
                    # Иначе можно подтянуть чужую карточку и неверные данные.
                    if product is None:
                        continue

                    # Извлекаем цену с учётом разных форматов WB payload.
                    prices = self._extract_wb_prices_from_product(product)
                    price_rub = prices.get("price")
                    old_price_rub = prices.get("old_price")

                    # Нормализуем рейтинг и отзывы.
                    rating_raw = product.get("reviewRating")
                    try:
                        rating = float(str(rating_raw).replace(",", ".")) if rating_raw is not None else None
                    except (TypeError, ValueError):
                        rating = None

                    reviews_count = self._to_int_safe(product.get("feedbacks"))
                    sales_per_day = self._extract_sales_per_day(product)

                    return {
                        "name": product.get("name"),
                        "price": price_rub,
                        "old_price": old_price_rub,
                        "brand": product.get("brand"),
                        "rating": rating,
                        "reviews_count": reviews_count,
                        "sales_per_day": sales_per_day,
                        "seller": product.get("supplier"),
                    }
                except Exception:
                    continue

            return {}

        async def _from_card_legacy_detail(client: httpx.AsyncClient) -> Dict[str, Any]:
            # Legacy-эндпоинт WB: иногда остаётся доступным при проблемах с v4.
            destinations = ["-1257786", "-1029256", "-123", "-1"]

            for dest in destinations:
                api_url = f"https://card.wb.ru/cards/detail?appType=1&curr=rub&dest={dest}&spp=0&nm={nm_id}"
                try:
                    response = await client.get(api_url)
                    if response.status_code == 404:
                        continue
                    response.raise_for_status()
                    payload = response.json()

                    products = payload.get("data", {}).get("products", [])
                    if not products:
                        continue

                    product = None
                    for candidate in products:
                        if str(candidate.get("id")) == str(nm_id) or str(candidate.get("nmId")) == str(nm_id):
                            product = candidate
                            break
                    if product is None:
                        product = products[0]

                    # Извлекаем цену с учётом разных форматов WB payload.
                    prices = self._extract_wb_prices_from_product(product)
                    price_rub = prices.get("price")
                    old_price_rub = prices.get("old_price")

                    rating_raw = product.get("reviewRating")
                    try:
                        rating = float(str(rating_raw).replace(",", ".")) if rating_raw is not None else None
                    except (TypeError, ValueError):
                        rating = None

                    reviews_count = self._to_int_safe(product.get("feedbacks"))
                    sales_per_day = self._extract_sales_per_day(product)

                    return {
                        "name": product.get("name"),
                        "price": price_rub,
                        "old_price": old_price_rub,
                        "brand": product.get("brand"),
                        "rating": rating,
                        "reviews_count": reviews_count,
                        "sales_per_day": sales_per_day,
                        "seller": product.get("supplier"),
                    }
                except Exception:
                    continue

            return {}

        async def _from_basket_card_json(client: httpx.AsyncClient) -> Dict[str, Any]:
            nm_id_int = int(nm_id)
            vol = nm_id_int // 100000
            part = nm_id_int // 1000

            # Конкурентно перебираем basket-хосты: карточка лежит ровно на одном
            # из них, и его номер может быть большим (наблюдалось basket-41).
            card_urls = [
                f"https://{host}/vol{vol}/part{part}/{nm_id}/info/ru/card.json"
                for host in self._wb_basket_hosts()
            ]
            found = await self._wb_fetch_first_json(client, card_urls)
            if not found:
                return {}

            payload = found["_payload"]
            if not isinstance(payload, dict):
                return {}

            # Название карточки.
            name = payload.get("imt_name") or payload.get("subj_name")

            # Бренд может лежать в нескольких местах.
            selling = payload.get("selling") or {}
            brand = (
                selling.get("brand_name")
                or payload.get("brand")
                or payload.get("brand_name")
            )

            # Категория: предметная категория WB (subj_name) + корневой раздел.
            category = payload.get("subj_name") or payload.get("subj_root_name")

            # card.json обычно НЕ содержит цену (она динамическая, через card.wb.ru),
            # но на всякий случай пробуем извлечь, если поле присутствует.
            prices = self._extract_wb_prices_from_product(payload)
            price = prices.get("price")
            old_price = prices.get("old_price")

            # Рейтинг и число отзывов иногда доступны в базовой карточке.
            rating = None
            reviews_count = None

            rating_candidates = [
                payload.get("reviewRating"),
                payload.get("rating"),
                payload.get("imt_rating"),
                (payload.get("nm_review_rating") if isinstance(payload, dict) else None),
            ]
            for candidate in rating_candidates:
                try:
                    if candidate is not None:
                        rating = float(str(candidate).replace(",", "."))
                        break
                except (TypeError, ValueError):
                    continue

            reviews_candidates = [
                payload.get("feedbacks"),
                payload.get("feedbackCount"),
                payload.get("imt_feedbacks"),
                payload.get("nm_feedbacks"),
            ]
            for candidate in reviews_candidates:
                parsed_reviews = self._to_int_safe(candidate)
                if parsed_reviews is not None:
                    reviews_count = parsed_reviews
                    break

            sales_per_day = self._extract_sales_per_day(payload)

            return {
                "name": name,
                "price": price,
                "old_price": old_price,
                "brand": brand,
                "category": category,
                "rating": rating,
                "reviews_count": reviews_count,
                "sales_per_day": sales_per_day,
                "seller": None,
            }

        async def _from_basket_price_history(client: httpx.AsyncClient) -> Dict[str, Any]:
            """
            Дополнительный fallback WB: prices-history.json на basket-хостах.

            Файл часто доступен даже когда card/detail недоступен.
            Из него берём текущую и предыдущую цену, а name/brand подтянем из card.json,
            если получится.
            """
            nm_id_int = int(nm_id)
            vol = nm_id_int // 100000
            part = nm_id_int // 1000

            def _entry_price_rub(entry: Any) -> Optional[int]:
                """Извлечь цену в рублях из записи истории цен WB."""
                if not isinstance(entry, dict):
                    return None
                # Актуальный формат: {"dt": ..., "price": {"RUB": <копейки>}}.
                price_field = entry.get("price")
                if isinstance(price_field, dict):
                    for cur_key in ("RUB", "rub", "value"):
                        kopecks = self._to_int_safe(price_field.get(cur_key))
                        if kopecks and kopecks > 0:
                            # Значение в истории цен WB приходит в копейках.
                            return int(kopecks / 100)
                # Старые/альтернативные форматы: скалярные поля.
                for key in ("price", "salePrice", "salePriceU", "priceU", "value"):
                    normalized = self._normalize_wb_price_value(entry.get(key))
                    if normalized:
                        return normalized
                return None

            price_urls = [
                f"https://{host}/vol{vol}/part{part}/{nm_id}/info/price-history.json"
                for host in self._wb_basket_hosts()
            ]
            found = await self._wb_fetch_first_json(client, price_urls)
            if not found:
                return {}

            payload = found["_payload"]

            # price-history бывает как top-level список, так и dict с вложенным history.
            if isinstance(payload, list):
                entries = payload
            elif isinstance(payload, dict):
                entries = payload.get("priceHistory") or payload.get("history") or payload.get("prices") or []
            else:
                entries = []

            if not isinstance(entries, list) or not entries:
                return {}

            latest_price = _entry_price_rub(entries[-1])
            prev_price = _entry_price_rub(entries[-2]) if len(entries) > 1 else None

            if latest_price is None:
                return {}

            # Возвращаем только цену: name/brand/category уже подтягиваются
            # отдельно из card.json в оркестраторе (без повторного сканирования basket).
            return {
                "price": latest_price,
                "old_price": prev_price if prev_price and prev_price >= latest_price else None,
            }

        client_kwargs: Dict[str, Any] = {
            # Короткий таймаут: basket-CDN отвечает быстро или не отвечает вовсе,
            # а перебор хостов идёт конкурентно пачками. Это держит общую
            # длительность enrichment в пределах ~10-15с даже при мёртвых хостах.
            "timeout": httpx.Timeout(5.0, connect=4.0),
            "follow_redirects": True,
            # Браузерные заголовки снижают долю 403 от WB-WAF.
            "headers": self.WB_PUBLIC_JSON_HEADERS,
        }
        if proxy_url:
            client_kwargs["proxy"] = proxy_url

        def _merge(primary: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
            """Дополнить primary недостающими (None/пустыми) полями из extra."""
            merged = dict(primary)
            for key, value in (extra or {}).items():
                if value in (None, "", 0) and key in ("price", "old_price"):
                    # Для цен 0 трактуем как отсутствие, но не затираем уже найденное.
                    continue
                if merged.get(key) in (None, "") and value not in (None, ""):
                    merged[key] = value
            return merged

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                result: Dict[str, Any] = {}

                # 1) card.wb.ru v4 — самый полный источник (цена/рейтинг/отзывы),
                # но часто отдаёт 403 с датацентровых IP без прокси.
                try:
                    v4 = await _from_card_v4(client)
                    if v4:
                        result = _merge(result, v4)
                except Exception as e:
                    logger.warning(f"⚠️ WB card.v4 недоступен: {type(e).__name__}: {e}")

                # 2) legacy card/detail — если v4 не дал цену.
                if result.get("price") is None:
                    try:
                        legacy = await _from_card_legacy_detail(client)
                        if legacy:
                            result = _merge(result, legacy)
                    except Exception as e:
                        logger.warning(f"⚠️ WB card/detail недоступен: {type(e).__name__}: {e}")

                # 3) basket card.json — стабильный источник name/brand/category.
                if not result.get("name") or not result.get("category"):
                    try:
                        basket = await _from_basket_card_json(client)
                        if basket:
                            result = _merge(result, basket)
                    except Exception as e:
                        logger.warning(f"⚠️ WB basket card.json недоступен: {type(e).__name__}: {e}")

                # 4) price-history.json — отдельный надёжный источник цены,
                # доступен даже когда card.wb.ru заблокирован (как сейчас).
                if result.get("price") is None:
                    try:
                        history = await _from_basket_price_history(client)
                        if history:
                            result = _merge(result, history)
                    except Exception as e:
                        logger.warning(f"⚠️ WB price-history недоступен: {type(e).__name__}: {e}")

                return result
        except Exception as e:
            logger.warning(f"⚠️ WB API fallback не сработал: {type(e).__name__}: {e}")
            return {}

    async def _parse_ozon_advanced(
        self,
        url: str,
        proxy_url: Optional[str],
        timeout: int = 120000  # 2 минуты
    ) -> Dict[str, Any]:
        """
        Продвинутый парсинг Ozon с обходом капчи.
        Использует Chromium с улучшенными настройками + JS evaluation.
        """
        browser = None
        context = None
        page = None

        try:
            async with async_playwright() as p:
                # Запускаем Chromium с максимальным скрытием
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-accelerated-2d-canvas",
                        "--disable-gpu",
                        "--window-size=1920,1080",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--disable-site-isolation-trials",
                        "--disable-features=ImprovedCookieControls",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-features=UserAgentClientHint",
                        "--disable-features=UseChromeOSInfoBar",
                    ]
                )
                
                # Mobile User-Agent (меньше блокируют)
                user_agent = "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.64 Mobile Safari/537.36"
                
                # Настройки контекста
                context_args = {
                    "user_agent": user_agent,
                    "viewport": {"width": 412, "height": 915},  # Mobile размеры
                    "locale": "ru-RU",
                    "timezone_id": "Europe/Moscow",
                    "device_scale_factor": 2.625,
                    "is_mobile": True,
                    "has_touch": True,
                    "extra_http_headers": {
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Cache-Control": "max-age=0",
                    },
                }
                
                # Добавляем прокси если есть
                if proxy_url:
                    logger.info(f"🔹 Ozon используем прокси: {proxy_url}")
                    context_args["proxy"] = {"server": proxy_url}
                else:
                    logger.warning("⚠️ Ozon парсинг БЕЗ прокси")
                
                # Создаём контекст
                context = await browser.new_context(**context_args)
                
                # Скрипт для скрытия автоматизации (МАКСИМАЛЬНЫЙ)
                await context.add_init_script("""
                    // Скрываем webdriver
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });
                    
                    // Подделываем плагины
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5],
                    });
                    
                    // Подделываем языки
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['ru-RU', 'ru', 'en-US', 'en'],
                    });
                    
                    // Подделываем аппаратную информацию
                    Object.defineProperty(navigator, 'hardwareConcurrency', {
                        get: () => 8,
                    });
                    Object.defineProperty(navigator, 'deviceMemory', {
                        get: () => 8,
                    });
                    
                    // Подделываем vendor
                    Object.defineProperty(navigator, 'vendor', {
                        get: () => 'Google Inc.',
                    });
                    
                    // Подделываем platform
                    Object.defineProperty(navigator, 'platform', {
                        get: () => 'Linux aarch64',
                    });
                    
                    // Удаляем permision
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                """)
                
                page = await context.new_page()
                
                # Реалистичная задержка перед запросом
                await asyncio.sleep(random.uniform(2, 4))
                
                logger.info(f"🌐 Переход на Ozon (Mobile): {url}")
                logger.info(f"📋 User-Agent: {user_agent[:50]}...")
                
                # Переход на страницу с увеличенным таймаутом
                response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                
                # Проверяем ответ
                if response:
                    status = response.status
                    logger.info(f"📊 Статус ответа: {status}")
                    
                    if status == 403:
                        raise ParserError("Ozon вернул 403 - доступ запрещён")
                    elif status == 404:
                        raise ParserError("Страница товара не найдена (404)")
                
                # Ждём загрузки основного контента
                try:
                    await page.wait_for_selector("h1, .ProductHeader, .product-page, [data-product]", timeout=20000)
                    logger.info("✅ Основной контент загрузился")
                except PlaywrightTimeout:
                    logger.warning("⚠️ Таймаут ожидания контента")
                
                # Дополнительная задержка для JS
                await asyncio.sleep(random.uniform(3, 5))
                
                # Проверяем на капчу
                page_title = await page.title()
                logger.info(f"📄 Заголовок страницы: {page_title[:80] if page_title else '❌ None'}")
                
                # Если есть капча - пробуем подождать
                if page_title and any(word in page_title.lower() for word in ['captcha', 'robot', 'проверка', 'пазл']):
                    logger.warning("🧩 Обнаружена капча, ждём...")
                    await asyncio.sleep(10)
                    
                    # Проверяем снова
                    page_title = await page.title()
                    if any(word in page_title.lower() for word in ['captcha', 'robot', 'проверка', 'пазл']):
                        logger.error("🚫 Ozon не пропустил (капча)")
                        raise ParserError(f"Ozon требует капчу: {page_title}")
                
                # Debug-дамп (screenshot + HTML) только в dev при явном opt-in.
                await _save_parser_debug_dump(page, "ozon")
                
                # Извлекаем данные через JavaScript
                data = await self._extract_ozon_data_js(page, url)
                
                # Fallback-1: если name/price не извлеклись селекторами, пробуем JSON-LD/meta
                if not data.get("name") or not data.get("price"):
                    structured = await self._extract_structured_product_data(page)
                    if not data.get("name") and structured.get("name"):
                        data["name"] = structured.get("name")
                    if not data.get("price") and structured.get("price"):
                        data["price"] = int(structured.get("price"))
                    if not data.get("old_price") and structured.get("old_price"):
                        data["old_price"] = int(structured.get("old_price"))
                    if data.get("rating") is None and structured.get("rating") is not None:
                        data["rating"] = structured.get("rating")
                    if data.get("reviews_count") is None and structured.get("reviews_count") is not None:
                        data["reviews_count"] = structured.get("reviews_count")
                
                # Fallback-2 для Ozon намеренно не используем WB-источники,
                # чтобы исключить загрязнение чужими данными.

                # Проверяем что данные извлечены
                if not data.get('price') or data.get('price', 0) > 1000000:
                    logger.error(f"❌ Не удалось извлечь цену: {data.get('price')}")
                    raise ParserError("Не удалось извлечь корректную цену")
                
                logger.info(f"✅ Ozon данные: name={data.get('name', '❌')[:50]}, price={data.get('price')}")
                
                await page.close()
                await context.close()
                await browser.close()
                
                return data
        
        except PlaywrightTimeout:
            logger.error("⏰ Таймаут при парсинге Ozon")
            raise ParserError("Таймаут при загрузке страницы Ozon (прокси может быть медленным)")
        
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга Ozon: {type(e).__name__}: {e}")
            raise ParserError(f"Ошибка парсинга Ozon: {str(e)}")
        
        finally:
            try:
                if page: await page.close()
            except Exception:
                pass
            try:
                if context: await context.close()
            except Exception:
                pass
            try:
                if browser: await browser.close()
            except Exception:
                pass
    
    async def _extract_wildberries_data_js(self, page: Page, url: str) -> Dict[str, Any]:
        """Извлечь данные со страницы Wildberries через JavaScript evaluation."""
        
        logger.info("🔍 Извлечение данных через JavaScript...")
        
        # Ждём пока JS загрузит данные
        await asyncio.sleep(3)
        
        # Извлекаем все данные через один JS скрипт
        extracted = await page.evaluate("""
            () => {
                const data = {
                    name: null,
                    price: null,
                    old_price: null,
                    rating: null,
                    reviews_count: null,
                    sales_per_day: null,
                    brand: null,
                    category: null,
                    seller: null
                };
                
                // Название - ВАЖНО: не брать из meta og:title (это заголовок сайта!)
                const nameSelectors = [
                    'h1[data-nm="product-name"]',
                    '.product-header__title',
                    'h1.product-name',
                    '[data-nm="product-name"]',
                    '.product-title h1',
                    'header h1'
                ];
                for (const sel of nameSelectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        const text = el.textContent.trim();
                        // Проверка: это не заголовок сайта?
                        if (text && text.length > 5 && text.length < 200 && !text.includes('Интернет-магазин')) {
                            data.name = text;
                            console.log('✅ Name found via:', sel, '->', data.name.substring(0, 50));
                            break;
                        }
                    }
                }
                
                // Если не нашли, пробуем взять первый заголовок
                if (!data.name) {
                    const h1 = document.querySelector('h1');
                    if (h1) {
                        const text = h1.textContent.trim();
                        if (text && text.length > 5 && text.length < 200 && !text.includes('Интернет-магазин')) {
                            data.name = text;
                            console.log('✅ Name from h1:', data.name.substring(0, 50));
                        }
                    }
                }
                
                // Цена - ищем активную цену (ОЧЕНЬ ВАЖНО: не старую цену!)
                const priceSelectors = [
                    '[data-nm="price-current"] .sum-price',
                    '.price-block__sum-price',
                    'span[data-nm="price-current"]',
                    '.price__current',
                    '[class*="price-current"]',
                    '.price-item_current .sum-price',
                    'span[class*="current-price"]'
                ];
                for (const sel of priceSelectors) {
                    const elements = document.querySelectorAll(sel);
                    for (const el of elements) {
                        const text = el.textContent.trim();
                        if (text && text.length > 0) {
                            // Очищаем: "1 999 ₽" -> "1999"
                            const priceText = text.replace(/[^\\d,]/g, '').replace(',', '.');
                            const price = parseFloat(priceText);
                            if (price > 0 && price < 10000000) {
                                data.price = price;
                                console.log('✅ Price found via:', sel, '->', data.price, 'from:', text);
                                break;
                            }
                        }
                    }
                    if (data.price) break;
                }
                
                // Старая цена (в зачеркнутом элементе)
                const oldPriceSelectors = [
                    '[data-nm="price-old"] .sum-price',
                    '.price-block__old-sum-price',
                    'span[data-nm="old-price"]',
                    '.price__old',
                    'del .sum-price',
                    '[class*="old-price"]',
                    '.price-item_old .sum-price'
                ];
                for (const sel of oldPriceSelectors) {
                    const elements = document.querySelectorAll(sel);
                    for (const el of elements) {
                        const text = el.textContent.trim();
                        if (text && text.length > 0) {
                            const priceText = text.replace(/[^\\d,]/g, '').replace(',', '.');
                            const price = parseFloat(priceText);
                            if (price > 0 && price < 10000000) {
                                data.old_price = price;
                                console.log('✅ Old price found via:', sel, '->', data.old_price, 'from:', text);
                                break;
                            }
                        }
                    }
                    if (data.old_price) break;
                }
                
                // Рейтинг
                const ratingSelectors = [
                    '.stars-rating__count',
                    '.rating-sum',
                    '[data-nm="rating"]',
                    '.product-rating__count',
                    '.feedback-rating'
                ];
                for (const sel of ratingSelectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        const text = el.textContent.trim();
                        const match = text.match(/(\\d+[.,]?\\d*)/);
                        if (match) {
                            data.rating = parseFloat(match[1].replace(',', '.'));
                            if (data.rating > 0 && data.rating <= 5) {
                                console.log('✅ Rating found:', data.rating);
                                break;
                            }
                        }
                    }
                }
                
                // Отзывы
                const reviewsSelectors = [
                    '.product-review__link',
                    '.reviews-count',
                    '[data-nm="reviews"]',
                    '.feedback-count'
                ];
                for (const sel of reviewsSelectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        const text = el.textContent.trim();
                        const match = text.match(/(\\d+)/);
                        if (match) {
                            data.reviews_count = parseInt(match[1]);
                            console.log('✅ Reviews found:', data.reviews_count);
                            break;
                        }
                    }
                }
                
                // Продажи в день (если блок видим на карточке)
                const salesSelectors = [
                    '[data-nm="sales"]',
                    '.sales-count',
                    '.product-sales',
                    '[class*="sales"]',
                    '[class*="orders"]'
                ];
                for (const sel of salesSelectors) {
                    const el = document.querySelector(sel);
                    if (!el) continue;

                    const text = el.textContent.trim().toLowerCase();
                    if (!text || (!text.includes('день') && !text.includes('/day') && !text.includes('в день'))) {
                        continue;
                    }

                    const match = text.match(/(\\d[\\d\\s]*)/);
                    if (match) {
                        const parsed = parseInt(match[1].replace(/\\s+/g, ''), 10);
                        if (Number.isFinite(parsed) && parsed >= 0) {
                            data.sales_per_day = parsed;
                            console.log('✅ Sales/day found:', data.sales_per_day);
                            break;
                        }
                    }
                }
                
                // Бренд
                const brandEl = document.querySelector('.product-header__brand, [data-nm="brand"], .brand a');
                if (brandEl) {
                    data.brand = brandEl.textContent.trim();
                }
                
                // Категория (последний хлебный крошка)
                const breadcrumbs = document.querySelectorAll('.breadcrumbs__link');
                if (breadcrumbs.length > 0) {
                    data.category = breadcrumbs[breadcrumbs.length - 1].textContent.trim();
                }
                
                // Продавец
                const sellerEl = document.querySelector('.seller-info__name, .seller__name, [data-nm="seller"]');
                if (sellerEl) {
                    data.seller = sellerEl.textContent.trim();
                }
                
                console.log('📦 Final extracted data:', JSON.stringify(data, null, 2));
                return data;
            }
        """)
        
        logger.info(f"📦 JS extraction result: name={extracted['name'][:50] if extracted['name'] else '❌'}, price={extracted['price']}")
        
        # Расчет скидки
        discount = 0
        if extracted.get('price') and extracted.get('old_price') and extracted['old_price'] > extracted['price']:
            discount = int((1 - extracted['price'] / extracted['old_price']) * 100)
        
        return {
            "url": url,
            "marketplace": "wildberries",
            "name": extracted.get('name'),
            "price": int(extracted['price']) if extracted.get('price') else None,
            "old_price": int(extracted['old_price']) if extracted.get('old_price') else None,
            "rating": extracted.get('rating'),
            "reviews_count": extracted.get('reviews_count'),
            "sales_per_day": extracted.get('sales_per_day'),
            "sales_count": extracted.get('sales_per_day'),
            "brand": extracted.get('brand'),
            "category": extracted.get('category'),
            "seller": extracted.get('seller'),
            "discount": discount,
            "parsed_at": datetime.utcnow().isoformat(),
        }
            
    async def _extract_ozon_data_js(self, page: Page, url: str) -> Dict[str, Any]:
        """Извлечь данные со страницы Ozon через JavaScript evaluation."""

        logger.info("🔍 Извлечение данных Ozon через JavaScript...")
        
        # Извлекаем все данные через один JS скрипт
        extracted = await page.evaluate("""
            () => {
                const data = {
                    name: null,
                    price: null,
                    old_price: null,
                    rating: null,
                    reviews_count: null,
                    brand: null,
                    category: null,
                    seller: null
                };
                
                // Название - пробуем разные селекторы
                const nameSelectors = [
                    'h1.ProductHeader-title',
                    '.ProductHeader-title',
                    'h1',
                    '.product-page-title'
                ];
                for (const sel of nameSelectors) {
                    const el = document.querySelector(sel);
                    if (el && el.textContent.trim()) {
                        data.name = el.textContent.trim();
                        break;
                    }
                }
                
                // Цена - ищем активную цену
                const priceSelectors = [
                    '[data-price]',
                    '.Price-value',
                    '.price-value',
                    'span[data-price]',
                    '.product-price'
                ];
                for (const sel of priceSelectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        const priceText = el.getAttribute('data-price') || el.textContent.trim();
                        const price = parseFloat(priceText.replace(/[^\\d.]/g, ''));
                        if (price > 0) {
                            data.price = price;
                            break;
                        }
                    }
                }
                
                // Старая цена
                const oldPriceSelectors = [
                    '.Price-oldValue',
                    '.price-old',
                    'del',
                    '.product-old-price'
                ];
                for (const sel of oldPriceSelectors) {
                    const el = document.querySelector(sel);
                    if (el && el.textContent.trim()) {
                        const priceText = el.textContent.trim().replace(/[^\\d.]/g, '');
                        const price = parseFloat(priceText);
                        if (price > 0) {
                            data.old_price = price;
                            break;
                        }
                    }
                }
                
                // Рейтинг
                const ratingEl = document.querySelector('.ProductRating-rating, .rating-value');
                if (ratingEl) {
                    const match = ratingEl.textContent.match(/(\\d+[.,]?\\d*)/);
                    if (match) {
                        data.rating = parseFloat(match[1].replace(',', '.'));
                        if (data.rating > 5) data.rating = 5.0;
                    }
                }
                
                // Отзывы
                const reviewsEl = document.querySelector('.ProductReviews-count, .reviews-count');
                if (reviewsEl) {
                    const match = reviewsEl.textContent.match(/(\\d+)/);
                    if (match) {
                        data.reviews_count = parseInt(match[1]);
                    }
                }
                
                // Бренд
                const brandEl = document.querySelector('.ProductHeader-brand, .brand-name');
                if (brandEl) {
                    data.brand = brandEl.textContent.trim();
                }
                
                // Категория
                const categoryEl = document.querySelector('.Breadcrumb:last-child');
                if (categoryEl) {
                    data.category = categoryEl.textContent.trim();
                }
                
                // Продавец
                const sellerEl = document.querySelector('.SellerInfo-name, .seller-name');
                if (sellerEl) {
                    data.seller = sellerEl.textContent.trim();
                }
                
                return data;
            }
        """)
        
        logger.info(f"📦 Ozon JS extraction: name={extracted['name'][:50] if extracted['name'] else '❌'}, price={extracted['price']}")
        
        # Расчет скидки
        discount = 0
        if extracted.get('price') and extracted.get('old_price') and extracted['old_price'] > extracted['price']:
            discount = int((1 - extracted['price'] / extracted['old_price']) * 100)
        
        return {
            "url": url,
            "marketplace": "ozon",
            "name": extracted.get('name'),
            "price": int(extracted['price']) if extracted.get('price') else None,
            "old_price": int(extracted['old_price']) if extracted.get('old_price') else None,
            "rating": extracted.get('rating'),
            "reviews_count": extracted.get('reviews_count'),
            "brand": extracted.get('brand'),
            "category": extracted.get('category'),
            "seller": extracted.get('seller'),
            "discount": discount,
            "parsed_at": datetime.utcnow().isoformat(),
        }
            
    async def _extract_wildberries_data(self, page: Page, url: str) -> Dict[str, Any]:
        """Извлечь данные со страницы Wildberries."""

        # Пробуем разные методы извлечения названия
        name = None
        name_selectors = [
            "h1[data-nm='product-name']",
            ".product-header__title",
            "h1",
            "[data-nm='product-name']",
        ]
        
        for selector in name_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text and text.strip():
                        name = text.strip()
                        logger.info(f"✅ Название найдено через '{selector}': {name[:50]}...")
                        break
            except Exception:
                continue
        
        # Если не нашли, пробуем через textContent
        if not name:
            try:
                # Ищем любой h1
                h1 = await page.query_selector("h1")
                if h1:
                    name = await h1.text_content()
                    if name:
                        name = name.strip()
                        logger.info(f"✅ Название найдено через h1 textContent: {name[:50]}...")
            except Exception:
                pass
        
        # Извлекаем цену
        price = None
        price_selectors = [
            "[data-nm='price-current'] .sum-price",
            ".price-block__sum-price",
            "span[data-nm='price']",
            ".price__current",
            ".price span:first-child",
        ]
        
        for selector in price_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text:
                        # Очищаем цену
                        price_text = re.sub(r'[^\d,.\s]', '', text)
                        price_text = price_text.replace(',', '.').replace(' ', '')
                        try:
                            price = int(float(price_text))
                            if price > 0:
                                logger.info(f"✅ Цена найдена через '{selector}': {price} ₽")
                                break
                        except (ValueError, TypeError):
                            continue
            except Exception:
                continue
        
        # Старая цена
        old_price = None
        old_price_selectors = [
            "[data-nm='price-old'] .sum-price",
            ".price-block__old-sum-price",
            "span[data-nm='old-price']",
            ".price__old",
            "del",
        ]
        
        for selector in old_price_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text:
                        price_text = re.sub(r'[^\d,.\s]', '', text)
                        price_text = price_text.replace(',', '.').replace(' ', '')
                        try:
                            old_price = int(float(price_text))
                            if old_price > 0:
                                logger.info(f"✅ Старая цена найдена: {old_price} ₽")
                                break
                        except (ValueError, TypeError):
                            continue
            except Exception:
                continue
        
        # Рейтинг
        rating = None
        try:
            rating_element = await page.query_selector(".stars-rating__count, .rating-sum, [data-nm='rating']")
            if rating_element:
                text = await rating_element.inner_text()
                match = re.search(r'(\d+[.,]?\d*)', text)
                if match:
                    rating = float(match.group(1).replace(',', '.'))
                    rating = min(rating, 5.0)
                    logger.info(f"✅ Рейтинг: {rating}")
        except Exception:
            pass
        
        # Количество отзывов
        reviews_count = None
        try:
            reviews_element = await page.query_selector(".product-review__link, .reviews-count")
            if reviews_element:
                text = await reviews_element.inner_text()
                match = re.search(r'(\d+)', text)
                if match:
                    reviews_count = int(match.group(1))
                    logger.info(f"✅ Отзывы: {reviews_count}")
        except Exception:
            pass
        
        # Бренд
        brand = None
        try:
            brand_element = await page.query_selector(".product-header__brand, [data-nm='brand']")
            if brand_element:
                brand = await brand_element.inner_text()
                brand = brand.strip() if brand else None
        except Exception:
            pass
        
        # Категория
        category = None
        try:
            category_element = await page.query_selector(".breadcrumbs__link:last-child")
            if category_element:
                category = await category_element.inner_text()
                category = category.strip() if category else None
        except Exception:
            pass
        
        # Продавец
        seller = None
        try:
            seller_element = await page.query_selector(".seller-info__name, .seller__name")
            if seller_element:
                seller = await seller_element.inner_text()
                seller = seller.strip() if seller else None
        except Exception:
            pass
        
        # Расчет скидки
        discount = 0
        if price and old_price and old_price > price:
            discount = int((1 - price / old_price) * 100)
        
        return {
            "url": url,
            "marketplace": "wildberries",
            "name": name,
            "price": price,
            "old_price": old_price,
            "rating": rating,
            "reviews_count": reviews_count,
            "brand": brand,
            "category": category,
            "seller": seller,
            "discount": discount,
            "parsed_at": datetime.utcnow().isoformat(),
        }
            

# Глобальный экземпляр парсера
parser = MarketplaceParser()


async def parse_product_url(
    url: str,
    proxy_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Распарсить URL товара.
    
    Args:
        url: URL страницы товара
        proxy_url: URL прокси
    
    Returns:
        Данные товара
    """
    return await parser.parse_url(url, proxy_url)

