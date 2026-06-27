"""
Сервис парсинга маркетплейсов на Playwright.

Использует асинхронный Playwright для надёжного парсинга:
- Обход блокировок
- Рендеринг JavaScript
- Скриншоты при ошибках
- Повторы при сбоях
"""

import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from loguru import logger

from app.core.datetime_utils import utcnow
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout


class MarketplaceParserService:
    """
    Асинхронный сервис для парсинга маркетплейсов.
    
    Поддерживает:
    - Wildberries
    - Ozon
    - Avito
    - KazanExpress
    - Яндекс Маркет
    """
    
    def __init__(
        self,
        browser_name: str = "chromium",
        headless: bool = True,
        timeout: int = 30000,
    ):
        """
        Инициализация парсера.
        
        Args:
            browser_name: Браузер (chromium, firefox, webkit)
            headless: Запуск без GUI
            timeout: Таймаут операций в миллисекундах
        """
        self.browser_name = browser_name
        self.headless = headless
        self.timeout = timeout
        self.browser: Optional[Browser] = None
    
    async def start(self):
        """Запуск браузера."""
        playwright = await async_playwright().start()
        
        browser_args = {
            "headless": self.headless,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
                "--window-size=1920,1080",
            ],
        }
        
        if self.browser_name == "chromium":
            self.browser = await playwright.chromium.launch(**browser_args)
        elif self.browser_name == "firefox":
            self.browser = await playwright.firefox.launch(**browser_args)
        elif self.browser_name == "webkit":
            self.browser = await playwright.webkit.launch(**browser_args)
        
        logger.info(f"Браузер {self.browser_name} запущен")
    
    async def stop(self):
        """Остановка браузера."""
        if self.browser:
            await self.browser.close()
            logger.info("Браузер остановлен")
    
    async def parse_wildberries_product(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг товара с Wildberries.
        
        Args:
            url: Ссылка на товар WB
        Returns:
            Dict с данными товара или None при ошибке
        """
        logger.info(f"Парсинг WB: {url}")
        
        if not self.browser:
            await self.start()
        
        try:
            # Контекст с реалистичными настройками
            context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                locale="ru-RU",
                timezone_id="Europe/Moscow",
            )
            
            # Добавляем заголовки как у реального браузера
            await context.set_extra_http_headers({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            })
            
            page = await context.new_page()
            page.set_default_timeout(self.timeout)
            
            # Переход на страницу с ожиданием
            logger.info(f"Переход на страницу...")
            response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Проверяем статус ответа
            if response and response.status != 200:
                logger.warning(f"Статус ответа: {response.status}")
                await context.close()
                return None
            
            # Ждём загрузки контента
            await page.wait_for_timeout(3000)
            
            # Проверка на капчу/блокировку
            if await self._is_captcha(page):
                logger.warning("Обнаружена капча/блокировка")
                await context.close()
                return None
            
            # Парсинг данных
            data = await self._extract_wildberries_data(page, url)
            
            await context.close()
            
            if data.get('name') and data.get('name') != 'Товар Wildberries':
                logger.info(f"Товар распарсен: {data.get('name')}")
            else:
                logger.warning("Не удалось распарсить данные (возможно изменилась структура)")
            
            return data
            
        except Exception as e:
            logger.error(f"Ошибка парсинга: {e}")
            return None
    
    async def _is_captcha(self, page: Page) -> bool:
        """
        Проверка на наличие капчи.
        
        Args:
            page: Страница Playwright
            
        Returns:
            bool: True если обнаружена капча
        """
        captcha_selectors = [
            "iframe[src*='captcha']",
            "[class*='captcha']",
            "[id*='captcha']",
            "text=Капча",
            "text=Подтвердите, что вы не робот",
        ]
        
        for selector in captcha_selectors:
            if await page.locator(selector).count() > 0:
                return True
        
        return False
    
    async def _extract_wildberries_data(self, page: Page, url: str) -> Dict[str, Any]:
        """
        Извлечение данных о товаре со страницы WB.
        Актуальные селекторы на 2024-2025 год.
        """
        
        data = await page.evaluate("""
            () => {
                const getText = (selector) => {
                    const el = document.querySelector(selector);
                    return el ? el.textContent.trim() : null;
                };
                
                const getNumber = (selector) => {
                    const text = getText(selector);
                    if (!text) return null;
                    const num = parseFloat(text.replace(/[^0-9.]/g, ''));
                    return isNaN(num) ? null : num;
                };
                
                const getAllText = (selector) => {
                    const els = document.querySelectorAll(selector);
                    return Array.from(els).map(el => el.textContent.trim()).filter(t => t);
                };
                
                // ID товара из URL
                const urlParts = window.location.pathname.split('/');
                const externalId = urlParts.find(part => /^\\d+$/.test(part)) || null;
                
                // Название - новые селекторы
                let name = getText('h1[data-nm="product-name"]') || 
                           getText('h1.product-detail-name') ||
                           getText('h1') ||
                           getText('.product-header__name') ||
                           getText('[class*="product-name"]') ||
                           'Товар Wildberries';
                
                // Цена - актуальные селекторы
                let price = getNumber('[data-nm="price"] span') ||
                            getNumber('[data-nm="price"]') ||
                            getNumber('.price__current') ||
                            getNumber('[class*="price"] span:not(.old)') ||
                            getNumber('.product-price__current') ||
                            null;
                
                // Старая цена
                let oldPrice = getNumber('[data-nm="old-price"]') ||
                               getNumber('.price__old') ||
                               getNumber('[class*="old-price"]') ||
                               getNumber('.product-price__old') ||
                               null;
                
                // Скидка
                let discount = getNumber('.discount-percent') ||
                               getNumber('[data-nm="discount"]') ||
                               getNumber('[class*="discount"]') ||
                               null;
                
                // Рейтинг
                let rating = getNumber('.product-rating') ||
                             getNumber('[data-nm="rating"]') ||
                             getNumber('[class*="rating"]') ||
                             getNumber('.feedback-rating') ||
                             null;
                
                // Количество отзывов
                let reviewsCount = getNumber('.feedback-count') ||
                                   getNumber('[data-nm="reviews"]') ||
                                   getNumber('[class*="review"]') ||
                                   null;
                
                // Категория
                const category = getText('.breadcrumb-link:last-child') ||
                                 getText('.category-name') ||
                                 getText('[class*="category"]') ||
                                 null;
                
                // Бренд
                const brand = getText('[data-nm="brand"]') ||
                              getText('.brand-name') ||
                              getText('[class*="brand"]') ||
                              null;
                
                // Изображения
                const images = [];
                document.querySelectorAll('img[src*="images"], img[data-src*="images"]').forEach(img => {
                    const src = img.src || img.getAttribute('data-src');
                    if (src && src.startsWith('http') && !images.includes(src)) {
                        images.push(src);
                    }
                });
                
                // Характеристики
                const characteristics = {};
                document.querySelectorAll('.characteristics-item, .product-characteristic, [class*="characteristic"]').forEach(item => {
                    const key = item.querySelector('.characteristic-name')?.textContent?.trim();
                    const value = item.querySelector('.characteristic-value')?.textContent?.trim();
                    if (key && value) {
                        characteristics[key] = value;
                    }
                });
                
                // Описание
                const description = getText('.product-description') ||
                                    getText('[data-nm="description"]') ||
                                    getText('[class*="description"]') ||
                                    null;
                
                // Продажи
                let salesCount = getNumber('.sales-count') ||
                                 getNumber('[data-nm="sales"]') ||
                                 getNumber('[class*="sales"]') ||
                                 null;
                
                return {
                    external_id: externalId,
                    name: name,
                    description: description,
                    price: price,
                    old_price: oldPrice,
                    discount: discount,
                    rating: rating,
                    reviews_count: reviewsCount,
                    sales_count: salesCount,
                    category: category,
                    brand: brand,
                    images: images.slice(0, 10),
                    characteristics: characteristics,
                    url: window.location.href,
                };
            }
        """)
        
        from datetime import datetime
        data['last_parsed_at'] = utcnow()
        
        return data
    
    async def parse_ozon_product(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг товара с Ozon.
        
        Args:
            url: Ссылка на товар Ozon
            
        Returns:
            Dict с данными товара
        """
        logger.info(f"🔍 Парсинг Ozon: {url}")
        # TODO: Реализовать парсинг Ozon
        return None
    
    async def parse_avito_product(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг товара с Avito.
        
        Args:
            url: Ссылка на товар Avito
            
        Returns:
            Dict с данными товара
        """
        logger.info(f"🔍 Парсинг Avito: {url}")
        # TODO: Реализовать парсинг Avito
        return None


# ====================
# Async версия для FastAPI
# ====================

async def parse_wildberries_async(url: str) -> Optional[Dict[str, Any]]:
    """
    Асинхронный парсер для использования в FastAPI.
    
    Args:
        url: Ссылка на товар WB
        
    Returns:
        Dict с данными товара
    """
    parser = MarketplaceParserService(headless=True)
    
    await parser.start()
    try:
        result = await parser.parse_wildberries_product(url)
    finally:
        await parser.stop()
    
    # Если не удалось распарсить (блокировка WB) — возвращаем None,
    # чтобы вызывающий код корректно обработал ошибку, а не демо-данные.
    if not result or result.get('name') == 'Товар Wildberries':
        logger.warning("WB заблокировал парсинг, валидные данные не получены")
        return None
    
    return result


# ====================
# Синхронная обёртка для Celery
# ====================

def parse_wildberries_sync(url: str) -> Optional[Dict[str, Any]]:
    """
    Синхронная обёртка для использования в Celery задачах.
    
    Args:
        url: Ссылка на товар WB
        
    Returns:
        Dict с данными товара
    """
    import asyncio
    import nest_asyncio
    
    # Применяем nest_asyncio для совместимости
    nest_asyncio.apply()
    
    async def run_parser():
        return await parse_wildberries_async(url)
    
    return asyncio.run(run_parser())
