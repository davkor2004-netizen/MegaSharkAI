"""
Задачи Celery для репрайсинга.

Ночной репрайсинг реально пересчитывает и применяет цены на маркетплейсах
для пользователей, которые включили ночной репрайсинг и автообновление.
"""

import asyncio

from loguru import logger
from sqlalchemy import select

from app.celery_app import celery_app
from app.core.database import async_session_maker
from app.models.notification import UserSettings
from app.models.product import Product
from app.models.user import User


async def _reprice_user_products(db, user: User, user_settings: UserSettings) -> int:
    """Пересчитать и применить цены для всех собственных товаров пользователя."""
    # Ленивая загрузка, чтобы не плодить циклических импортов на уровне модуля.
    from app.api.v1.repricing import (
        calculate_recommended_price,
        get_auto_competitor_prices,
        round_to_pretty_market_price,
    )
    from app.services.repricing_service import apply_price_to_marketplace

    products = (
        await db.execute(
            select(Product).where(
                Product.user_id == user.id,
                Product.is_competitor.is_(False),
                Product.price.isnot(None),
                Product.price > 0,
            )
        )
    ).scalars().all()

    strategy = user_settings.repricing_strategy or "margin_protection"
    target_margin = user_settings.target_margin or 30.0
    applied = 0

    for product in products:
        competitor_prices = await get_auto_competitor_prices(db, user, product)

        raw_price, _source, _reasoning = calculate_recommended_price(
            current_price=float(product.price or 0),
            strategy=strategy,
            target_margin=target_margin,
            competitor_prices=competitor_prices,
        )
        new_price = round_to_pretty_market_price(raw_price)

        # Пропускаем, если изменение незначительное (< 1 ₽).
        if abs(new_price - float(product.price or 0)) < 1:
            continue

        result = await apply_price_to_marketplace(
            db=db,
            user=user,
            product=product,
            new_price=new_price,
            reason="Ночной репрайсинг",
            notify=False,  # массовое уведомление отправим одно, итоговое
        )
        if result.get("status") == "applied":
            applied += 1

    return applied


async def _run_night_repricing() -> dict:
    """Асинхронная реализация ночного репрайсинга по всем подходящим пользователям."""
    from app.services.notification_service import notification_service

    async with async_session_maker() as db:
        settings_rows = (
            await db.execute(
                select(UserSettings).where(
                    UserSettings.night_repricing_enabled.is_(True),
                    UserSettings.auto_update_enabled.is_(True),
                )
            )
        ).scalars().all()

        total_applied = 0
        processed_users = 0

        for user_settings in settings_rows:
            user = await db.get(User, user_settings.user_id)
            if not user or not user.is_active:
                continue

            processed_users += 1
            applied = await _reprice_user_products(db, user, user_settings)
            total_applied += applied

            if applied > 0:
                try:
                    await notification_service.notify(
                        db=db,
                        user=user,
                        title="Ночной репрайсинг выполнен",
                        message=f"Обновлено цен: {applied}. Изменения отправлены на маркетплейс.",
                        notification_type="price_change",
                    )
                except Exception as error:
                    logger.error(f"❌ Ошибка уведомления о ночном репрайсинге: {error}")

        return {
            "status": "completed",
            "processed_users": processed_users,
            "applied_prices": total_applied,
        }


@celery_app.task(bind=True)
def night_repricing(self):
    """
    Ночной репрайсинг.

    Запускается по расписанию (3:00). Пересчитывает и применяет цены
    для пользователей с включённым ночным репрайсингом и автообновлением.
    """
    logger.info("🌙 Старт ночного репрайсинга")
    try:
        result = asyncio.run(_run_night_repricing())
        logger.info(
            f"✅ Ночной репрайсинг завершён: пользователей={result['processed_users']}, "
            f"обновлено цен={result['applied_prices']}"
        )
        return result
    except Exception as error:
        logger.error(f"❌ Ошибка ночного репрайсинга: {error}")
        return {"status": "error", "message": str(error)}


@celery_app.task(bind=True)
def reprice_single_product(self, product_id: int):
    """
    Репрайсинг одного товара по сохранённой стратегии его владельца.

    Args:
        product_id: ID собственного товара
    """
    logger.info(f"💸 Репрайсинг товара {product_id}")

    async def _run() -> dict:
        from app.api.v1.repricing import (
            calculate_recommended_price,
            get_auto_competitor_prices,
            round_to_pretty_market_price,
        )
        from app.services.repricing_service import apply_price_to_marketplace

        async with async_session_maker() as db:
            product = await db.get(Product, product_id)
            if not product or product.is_competitor or not product.user_id:
                return {"status": "skipped", "message": "Товар не найден или это конкурент"}

            user = await db.get(User, product.user_id)
            if not user:
                return {"status": "skipped", "message": "Владелец товара не найден"}

            settings_row = (
                await db.execute(
                    select(UserSettings).where(UserSettings.user_id == user.id)
                )
            ).scalar_one_or_none()

            strategy = settings_row.repricing_strategy if settings_row else "margin_protection"
            target_margin = settings_row.target_margin if settings_row else 30.0

            competitor_prices = await get_auto_competitor_prices(db, user, product)
            raw_price, _source, _reasoning = calculate_recommended_price(
                current_price=float(product.price or 0),
                strategy=strategy,
                target_margin=target_margin,
                competitor_prices=competitor_prices,
            )
            new_price = round_to_pretty_market_price(raw_price)

            return await apply_price_to_marketplace(
                db=db, user=user, product=product, new_price=new_price, reason="Репрайсинг по стратегии"
            )

    try:
        return asyncio.run(_run())
    except Exception as error:
        logger.error(f"❌ Ошибка репрайсинга товара {product_id}: {error}")
        return {"status": "error", "message": str(error)}
