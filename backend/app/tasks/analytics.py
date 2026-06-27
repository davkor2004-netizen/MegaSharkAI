"""
Задачи Celery для AI-аналитики и календаря распродаж.
"""

import asyncio
from datetime import datetime

from loguru import logger
from sqlalchemy import select

from app.celery_app import celery_app
from app.core.database import async_session_maker
from app.core.datetime_utils import utcnow
from app.models.notification import SaleCalendar
from app.models.product import CompetitorAnalysis, Product


# Известные регулярные распродажи маркетплейсов (день/месяц).
# Это глобальные события-ориентиры; точные даты акций площадки публикуют отдельно,
# но эти «якорные» даты стабильны из года в год и полезны для планирования.
KNOWN_SALES = [
    {"title": "Новогодняя распродажа", "month": 12, "day": 20, "duration_days": 20, "marketplace": None},
    {"title": "Гендерные праздники (23 февраля)", "month": 2, "day": 14, "duration_days": 10, "marketplace": None},
    {"title": "8 марта", "month": 3, "day": 1, "duration_days": 8, "marketplace": None},
    {"title": "Весенняя распродажа", "month": 4, "day": 1, "duration_days": 10, "marketplace": None},
    {"title": "Летняя распродажа", "month": 6, "day": 1, "duration_days": 14, "marketplace": None},
    {"title": "Распродажа к 1 сентября", "month": 8, "day": 20, "duration_days": 12, "marketplace": None},
    {"title": "11.11 Всемирный день шопинга", "month": 11, "day": 11, "duration_days": 3, "marketplace": None},
    {"title": "Чёрная пятница", "month": 11, "day": 24, "duration_days": 5, "marketplace": None},
    {"title": "Киберпонедельник", "month": 12, "day": 1, "duration_days": 2, "marketplace": None},
]


async def _sync_sales_calendar() -> dict:
    """Добавить недостающие глобальные события распродаж на текущий и следующий год."""
    from datetime import timedelta

    now = utcnow()
    years = [now.year, now.year + 1]
    created = 0

    async with async_session_maker() as db:
        for year in years:
            for sale in KNOWN_SALES:
                try:
                    start_date = datetime(year, sale["month"], sale["day"])
                except ValueError:
                    continue
                end_date = start_date + timedelta(days=sale["duration_days"])

                # Идемпотентность: не дублируем событие с тем же названием и датой начала.
                exists = (
                    await db.execute(
                        select(SaleCalendar).where(
                            SaleCalendar.title == sale["title"],
                            SaleCalendar.start_date == start_date,
                            SaleCalendar.is_global.is_(True),
                        )
                    )
                ).scalar_one_or_none()

                if exists:
                    continue

                db.add(
                    SaleCalendar(
                        user_id=None,
                        title=sale["title"],
                        description="Регулярная распродажа маркетплейсов. Планируйте остатки и цены заранее.",
                        marketplace=sale["marketplace"],
                        event_type="sale",
                        start_date=start_date,
                        end_date=end_date,
                        is_global=True,
                    )
                )
                created += 1

        await db.commit()

    return {"status": "completed", "created_events": created}


@celery_app.task(bind=True)
def update_sales_calendar(self):
    """
    Обновление календаря распродаж.

    Поддерживает актуальный набор глобальных событий-распродаж на текущий и следующий год.
    """
    logger.info("📅 Обновление календаря распродаж")
    try:
        result = asyncio.run(_sync_sales_calendar())
        logger.info(f"✅ Календарь обновлён: добавлено событий {result['created_events']}")
        return result
    except Exception as error:
        logger.error(f"❌ Ошибка обновления календаря: {error}")
        return {"status": "error", "message": str(error)}


async def _analyze_competitors_for_product(product_id: int) -> dict:
    """AI-анализ конкурентов для конкретного товара с сохранением результата."""
    from app.services.ai_service import get_ai_service

    async with async_session_maker() as db:
        product = await db.get(Product, product_id)
        if not product:
            return {"status": "skipped", "message": "Товар не найден"}

        # Подбираем конкурентов того же владельца, маркетплейса и (по возможности) категории.
        filters = [
            Product.is_competitor.is_(True),
            Product.marketplace == product.marketplace,
            Product.price.isnot(None),
            Product.price > 0,
        ]
        if product.user_id:
            filters.append(Product.user_id == product.user_id)
        if product.category:
            filters.append(Product.category == product.category)

        competitors = (
            await db.execute(select(Product).where(*filters).limit(50))
        ).scalars().all()

        competitor_data = [
            {"name": c.name, "price": float(c.price or 0), "rating": float(c.rating or 0)}
            for c in competitors
        ]

        ai_service = get_ai_service()
        analysis = await ai_service.analyze_competitors(
            product_name=product.name,
            competitor_data=competitor_data,
        )

        db.add(
            CompetitorAnalysis(
                product_id=product.id,
                price_position=str(analysis.get("price_position") or "")[:20] or None,
                min_competitor_price=analysis.get("min_price"),
                avg_competitor_price=analysis.get("avg_price"),
                max_competitor_price=analysis.get("max_price"),
                recommended_price=analysis.get("recommended_price"),
                analysis_data=analysis,
            )
        )
        await db.commit()

        return {"status": "completed", "competitors": len(competitor_data), "analysis": analysis}


@celery_app.task(bind=True)
def analyze_competitors(self, product_id: int):
    """
    AI-анализ конкурентов для товара (фоновый).

    Args:
        product_id: ID товара
    """
    logger.info(f"🤖 Фоновый AI-анализ конкурентов для товара {product_id}")
    try:
        return asyncio.run(_analyze_competitors_for_product(product_id))
    except Exception as error:
        logger.error(f"❌ Ошибка фонового AI-анализа: {error}")
        return {"status": "error", "message": str(error)}
