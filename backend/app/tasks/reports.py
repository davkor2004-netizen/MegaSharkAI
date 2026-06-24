"""
Задачи Celery для генерации отчётов.
"""

import asyncio

from loguru import logger
from sqlalchemy import select

from app.celery_app import celery_app
from app.core.database import async_session_maker
from app.models.product import Product
from app.models.user import User


async def _send_daily_reports() -> dict:
    """Сформировать сводку дня и уведомить активных пользователей с товарами."""
    from app.services.notification_service import notification_service
    from app.services.report_service import build_report_data

    sent = 0
    async with async_session_maker() as db:
        # Пользователи, у которых есть хотя бы один товар.
        user_ids = (
            await db.execute(
                select(Product.user_id).where(Product.user_id.isnot(None)).distinct()
            )
        ).scalars().all()

        for user_id in user_ids:
            user = await db.get(User, user_id)
            if not user or not user.is_active:
                continue

            report = await build_report_data(db, user_id)
            message = (
                f"Своих товаров: {report['own_count']}, конкурентов: {report['competitor_count']}. "
                f"Средняя своя цена: {int(report['own_avg_price'])} ₽, "
                f"у конкурентов: {int(report['competitor_avg_price'])} ₽. "
                f"Полный отчёт доступен в разделе «Отчёты» (xlsx/pdf)."
            )
            try:
                await notification_service.notify(
                    db=db,
                    user=user,
                    title="Ежедневный отчёт MegaSharkAI",
                    message=message,
                    notification_type="report_ready",
                )
                sent += 1
            except Exception as error:
                logger.error(f"❌ Ошибка отправки ежедневного отчёта: {error}")

    return {"status": "completed", "reports_sent": sent}


@celery_app.task(bind=True)
def daily_reports(self):
    """
    Генерация и рассылка ежедневных отчётов (8:00).
    """
    logger.info("📊 Старт ежедневных отчётов")
    try:
        result = asyncio.run(_send_daily_reports())
        logger.info(f"✅ Ежедневные отчёты отправлены: {result['reports_sent']}")
        return result
    except Exception as error:
        logger.error(f"❌ Ошибка ежедневных отчётов: {error}")
        return {"status": "error", "message": str(error)}


@celery_app.task(bind=True)
def generate_competitor_report(self, user_id: str, format: str = "xlsx"):
    """
    Сгенерировать отчёт по конкурентам для пользователя (фоновая генерация).

    Файл формируется и проверяется; скачивание доступно через
    GET /api/v1/reports/competitors.

    Args:
        user_id: ID пользователя
        format: Формат отчёта (xlsx, pdf)
    """
    logger.info(f"📋 Фоновая генерация отчёта ({format}) для пользователя {user_id}")

    async def _run() -> dict:
        from app.services.report_service import generate_competitor_report as build_report

        async with async_session_maker() as db:
            content, filename, _media = await build_report(db, user_id, format)
            return {"status": "completed", "filename": filename, "size_bytes": len(content)}

    try:
        return asyncio.run(_run())
    except Exception as error:
        logger.error(f"❌ Ошибка фоновой генерации отчёта: {error}")
        return {"status": "error", "message": str(error)}
