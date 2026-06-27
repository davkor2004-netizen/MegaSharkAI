"""
Задачи Celery для парсинга маркетплейсов.

Модуль содержит задачи для:
- Парсинга товаров с Wildberries, Ozon, Avito, KazanExpress, Яндекс Маркет
- Периодического обновления данных о конкурентах
- Сохранения результатов парсинга в базу данных
"""

import asyncio

from celery import Task
from loguru import logger
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import select

from app.celery_app import celery_app
from app.core.database import async_session_maker
from app.core.datetime_utils import utcnow
from app.models.product import Product, PriceHistory
from app.services.parser import MarketplaceParser as PlaywrightMarketplaceParser, ParserError


# ====================
# Базовый класс для парсеров
# ====================

class MarketplaceParser:
    """
    Базовый класс для парсеров маркетплейсов.
    
    Все парсеры наследуются от этого класса и реализуют метод parse().
    """
    
    marketplace_name: str = "base"
    
    async def parse_product(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг данных о товаре.
        
        Args:
            url: Ссылка на товар
            
        Returns:
            Dict с данными товара или None при ошибке
        """
        raise NotImplementedError("Метод parse_product должен быть реализован")
    
    async def save_product(self, data: Dict[str, Any], is_competitor: bool = True) -> Optional[Product]:
        """
        Сохранение товара в базу данных.
        
        Args:
            data: Данные товара
            is_competitor: Флаг конкурента
            
        Returns:
            Сохранённый объект Product или None
        """
        async with async_session_maker() as session:
            # Проверяем существование товара
            existing = await session.execute(
                select(Product).where(
                    Product.marketplace == self.marketplace_name,
                    Product.external_id == data.get("external_id"),
                )
            )
            product = existing.scalar_one_or_none()
            
            if product:
                # Обновляем существующий товар
                for key, value in data.items():
                    if hasattr(product, key):
                        setattr(product, key, value)
                product.last_parsed_at = utcnow()
            else:
                # Создаём новый товар
                product = Product(
                    **data,
                    marketplace=self.marketplace_name,
                    is_competitor=is_competitor,
                    last_parsed_at=utcnow(),
                )
                session.add(product)
            
            await session.commit()
            await session.refresh(product)
            
            # Добавляем запись в историю цен
            await self._save_price_history(session, product)
            
            return product
    
    async def _save_price_history(self, session, product: Product):
        """Сохранение истории изменения цены."""
        price_history = PriceHistory(
            product_id=product.id,
            price=product.price,
            old_price=product.old_price,
            discount=product.discount,
        )
        session.add(price_history)


# ====================
# Парсер Wildberries
# ====================

class WildberriesParser(MarketplaceParser):
    """Парсер товаров с Wildberries."""
    
    marketplace_name = "wildberries"
    
    async def parse_product(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг товара с Wildberries.
        
        Args:
            url: Ссылка на товар WB
            
        Returns:
            Dict с данными товара
        """
        logger.info(f"🔍 Парсинг Wildberries: {url}")
        
        parser = PlaywrightMarketplaceParser()
        return await parser.parse_url(url)


# ====================
# Celery задачи
# ====================

@celery_app.task(bind=True, max_retries=3)
def parse_wildberries_product(self, url: str, is_competitor: bool = True):
    """
    Задача для парсинга одного товара с Wildberries.
    
    Args:
        url: Ссылка на товар
        is_competitor: Флаг конкурента
    """
    logger.info(f"🦈 Задача парсинга WB: {url}")
    
    async def run_parser() -> Dict[str, Any]:
        """Асинхронный запуск реального Playwright-парсера."""
        parser = PlaywrightMarketplaceParser()
        parsed_data = await parser.parse_url(url)
        return parsed_data

    try:
        result = asyncio.run(run_parser())
        logger.info(f"✅ Парсинг завершён: {str(result.get('name') or 'Unknown')[:80]}")
        return {"status": "success", "data": result}
        
    except ParserError as e:
        logger.error(f"❌ Ошибка парсинга WB: {e}")
        raise self.retry(exc=e, countdown=60)
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка парсинга WB: {e}")
        raise self.retry(exc=e, countdown=60)


async def _refresh_competitors() -> dict:
    """
    Перепарсить все отслеживаемые товары-конкуренты, у которых есть URL.

    Логика:
    - берём конкурентов с непустым URL и владельцем;
    - парсим актуальные данные;
    - обновляем цену/скидку, пишем историю цен;
    - при изменении цены уведомляем владельца.
    """
    from app.models.notification import UserSettings  # локальный импорт во избежание циклов
    from app.models.user import User
    from app.services.notification_service import notification_service

    parser = PlaywrightMarketplaceParser()
    checked = 0
    updated = 0
    notified = 0

    async with async_session_maker() as session:
        competitors = (
            await session.execute(
                select(Product).where(
                    Product.is_competitor.is_(True),
                    Product.url.isnot(None),
                    Product.user_id.isnot(None),
                )
            )
        ).scalars().all()

        for product in competitors:
            checked += 1
            try:
                data = await parser.parse_url(product.url)
            except Exception as error:
                logger.warning(f"⚠️ Не удалось перепарсить конкурента {product.id}: {error}")
                continue

            if not data:
                continue

            new_price = data.get("price")
            old_recorded_price = float(product.price or 0)

            # Не затираем валидную цену пустым результатом.
            if new_price is None or float(new_price) <= 0:
                continue

            new_price = float(new_price)
            price_changed = abs(new_price - old_recorded_price) >= 1

            product.price = new_price
            if data.get("old_price"):
                product.old_price = float(data["old_price"])
            if data.get("discount") is not None:
                product.discount = data.get("discount")
            if data.get("rating") is not None:
                product.rating = data.get("rating")
            if data.get("reviews_count") is not None:
                product.reviews_count = data.get("reviews_count")
            product.last_parsed_at = utcnow()

            session.add(product)
            session.add(
                PriceHistory(
                    product_id=product.id,
                    price=new_price,
                    old_price=product.old_price,
                    discount=product.discount,
                )
            )
            await session.commit()
            updated += 1

            if price_changed and old_recorded_price > 0:
                owner = await session.get(User, product.user_id)
                if owner:
                    direction = "снизил" if new_price < old_recorded_price else "поднял"
                    try:
                        await notification_service.notify(
                            db=session,
                            user=owner,
                            title="Конкурент изменил цену",
                            message=(
                                f"Конкурент «{product.name[:80]}» {direction} цену: "
                                f"{int(old_recorded_price)} ₽ → {int(new_price)} ₽."
                            ),
                            notification_type="price_change",
                        )
                        notified += 1
                    except Exception as error:
                        logger.error(f"❌ Ошибка уведомления об изменении цены конкурента: {error}")

    return {"status": "completed", "checked": checked, "updated": updated, "notified": notified}


@celery_app.task(bind=True)
def parse_competitors(self):
    """
    Периодическая задача для парсинга всех конкурентов.
    
    Запускается по расписанию (каждые 6 часов).
    """
    logger.info("🔄 Запуск парсинга конкурентов...")

    try:
        result = asyncio.run(_refresh_competitors())
        logger.info(
            f"✅ Парсинг конкурентов завершён: проверено={result['checked']}, "
            f"обновлено={result['updated']}, уведомлений={result['notified']}"
        )
        return result
    except Exception as error:
        logger.error(f"❌ Ошибка периодического парсинга конкурентов: {error}")
        return {"status": "error", "message": str(error)}


@celery_app.task(bind=True, max_retries=3)
def parse_product_task(self, marketplace: str, url: str):
    """
    Универсальная задача для парсинга товара с любого маркетплейса.
    
    Args:
        marketplace: Название маркетплейса (wildberries, ozon, avito, etc.)
        url: Ссылка на товар
    """
    logger.info(f"🔍 Парсинг {marketplace}: {url}")
    
    async def run_parser() -> Dict[str, Any]:
        """Асинхронный запуск единого Playwright-парсера."""
        parser = PlaywrightMarketplaceParser()
        parsed_data = await parser.parse_url(url)
        return parsed_data

    try:
        result = asyncio.run(run_parser())

        parsed_marketplace = (result.get("marketplace") or "").lower()
        if marketplace and parsed_marketplace and marketplace.lower() != parsed_marketplace:
            logger.warning(
                f"⚠️ Несовпадение marketplace: requested={marketplace}, parsed={parsed_marketplace}"
            )

        return {"status": "success", "data": result}
    except ParserError as e:
        logger.error(f"❌ Ошибка парсинга: {e}")
        raise self.retry(exc=e, countdown=60)
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка парсинга: {e}")
        raise self.retry(exc=e, countdown=60)
