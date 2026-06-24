"""Скрипт для анализа структуры Wildberries."""
import asyncio
from playwright.async_api import async_playwright


async def analyze_wb():
    """Анализ страницы WB."""
    print("[INFO] Запускаем браузер...")
    
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    page = await context.new_page()
    
    url = "https://www.wildberries.ru/catalog/24319630/detail.aspx"
    print(f"[INFO] Переходим на {url}...")
    
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        print("[OK] Страница загружена")
        
        # Ищем цену
        print("\n[PRICE] Поиск цены...")
        price_selectors = [
            "[data-nm='price']",
            ".price",
            "[class*='price']",
            "span[data-nm]",
        ]
        for selector in price_selectors:
            elements = await page.query_selector_all(selector)
            if elements:
                print(f"  {selector}: {len(elements)} элементов")
                for el in elements[:2]:
                    text = await el.inner_text()
                    print(f"    → {text[:100]}")
        
        # Ищем название
        print("\n[NAME] Поиск названия...")
        
        # Ищем рейтинг
        print("\n[RATING] Поиск рейтинга...")
        
        # Ищем бренд
        print("\n[BRAND] Поиск бренда...")
        
        # Ищем изображения
        print("\n[IMAGES] Поиск изображений...")
        
        # Сохраним HTML для анализа
        html = await page.content()
        with open("wb_page_sample.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n[SAVE] HTML сохранён в wb_page_sample.html ({len(html)} байт)")
        
    except Exception as e:
        print(f"[ERROR] Ошибка: {e}")
    finally:
        await browser.close()
        print("\n[DONE] Браузер закрыт")


if __name__ == "__main__":
    asyncio.run(analyze_wb())
