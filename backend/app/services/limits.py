"""
Сервис enforcement тарифных лимитов.

Проверяет лимиты активной подписки пользователя и не даёт превысить их.
- Месячные лимиты (AI-генерации, отчёты) учитываются через таблицу usage_counters.
- Лимиты-«объёмы» (макс. товаров) проверяются по фактическому количеству.

Если у пользователя нет активной подписки, применяются дефолтные лимиты
бесплатного режима (DEFAULT_LIMITS), чтобы продукт оставался ограниченно
доступным, но не бесплатным безлимитом.
"""

import json
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tariff import UserSubscription
from app.models.usage import UsageCounter

# Лимиты по умолчанию (нет активной подписки).
DEFAULT_LIMITS: dict[str, int] = {
    "max_products": 30,
    "max_repricing_products": 10,
    "ai_generations_per_month": 20,
    "competitor_reports": 5,
    "ai_images_per_month": 10,
}

# Человекочитаемые названия метрик для сообщений об ошибке.
METRIC_LABELS: dict[str, str] = {
    "max_products": "товаров в мониторинге",
    "max_repricing_products": "товаров на репрайсинге",
    "ai_generations_per_month": "AI-генераций в месяц",
    "competitor_reports": "отчётов по конкурентам в месяц",
    "ai_images_per_month": "AI-генераций изображений в месяц",
}


def _current_period() -> str:
    """Текущий период учёта в формате YYYY-MM."""
    return datetime.utcnow().strftime("%Y-%m")


async def get_active_limits(db: AsyncSession, user_id) -> dict:
    """
    Получить лимиты активной подписки пользователя.

    Возвращает лимиты тарифа, либо DEFAULT_LIMITS, если активной подписки нет.
    """
    subscription = (
        await db.execute(
            select(UserSubscription)
            .where(UserSubscription.user_id == user_id)
            .where(UserSubscription.status.in_(["trial", "active"]))
            .order_by(UserSubscription.created_at.desc())
            .limit(1)
            # Eager-load тарифа: в async ленивый доступ к relationship вне greenlet
            # бросает MissingGreenlet (→ 500). Грузим тариф сразу запросом.
            .options(selectinload(UserSubscription.tariff))
        )
    ).scalar_one_or_none()

    if not subscription:
        return dict(DEFAULT_LIMITS)

    # tariff уже загружен через selectinload; fallback через db.get на всякий случай.
    tariff = subscription.tariff
    if tariff is None:
        from app.models.tariff import Tariff

        tariff = await db.get(Tariff, subscription.tariff_id)

    if not tariff or not tariff.limits:
        return dict(DEFAULT_LIMITS)

    try:
        limits = json.loads(tariff.limits)
    except (json.JSONDecodeError, TypeError):
        return dict(DEFAULT_LIMITS)

    return limits if isinstance(limits, dict) else dict(DEFAULT_LIMITS)


def _limit_exceeded_error(metric: str, limit_value: int) -> HTTPException:
    """Сформировать единообразную ошибку превышения лимита (402 Payment Required)."""
    label = METRIC_LABELS.get(metric, metric)
    return HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail=(
            f"Достигнут лимит тарифа: {label} (не более {limit_value}). "
            f"Повысьте тариф, чтобы продолжить."
        ),
    )


async def require_feature(db: AsyncSession, user_id, feature: str) -> None:
    """
    Проверить, что фича доступна на тарифе пользователя.

    Используется для булевых возможностей тарифа (widget_access, api_access,
    photo_analysis и т.д.). Бросает 402, если фича не входит в активный тариф.
    """
    limits = await get_active_limits(db, user_id)
    if not limits.get(feature):
        feature_labels = {
            "widget_access": "виджет для встраивания на сайт",
            "api_access": "API-доступ",
            "photo_analysis": "анализ качества фото",
            "custom_repricing": "кастомные правила репрайсинга",
        }
        label = feature_labels.get(feature, feature)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Функция «{label}» доступна на тарифе Business. Повысьте тариф, чтобы использовать её.",
        )


async def enforce_volume_limit(
    db: AsyncSession,
    user_id,
    metric: str,
    current_count: int,
) -> None:
    """
    Проверить лимит-объём (например, max_products) перед добавлением новой сущности.

    Бросает 402, если добавление превысит лимит.
    """
    limits = await get_active_limits(db, user_id)
    limit_value = limits.get(metric)

    # Лимит не задан или -1 => безлимит.
    if limit_value is None or limit_value < 0:
        return

    if current_count >= limit_value:
        raise _limit_exceeded_error(metric, limit_value)


async def check_monthly_limit(
    db: AsyncSession,
    user_id,
    metric: str,
    amount: int = 1,
) -> None:
    """
    Проверить месячный лимит БЕЗ инкремента счётчика.

    Полезно для «дорогих» действий (генерация изображений), где счётчик нужно
    увеличивать только после успешного выполнения.

    Бросает 402, если действие превысит месячный лимит.
    """
    limits = await get_active_limits(db, user_id)
    limit_value = limits.get(metric)

    if limit_value is None or limit_value < 0:
        return

    period = _current_period()
    counter = (
        await db.execute(
            select(UsageCounter).where(
                UsageCounter.user_id == user_id,
                UsageCounter.metric == metric,
                UsageCounter.period == period,
            )
        )
    ).scalar_one_or_none()

    used = counter.count if counter else 0
    if used + amount > limit_value:
        raise _limit_exceeded_error(metric, limit_value)


async def increment_monthly_usage(
    db: AsyncSession,
    user_id,
    metric: str,
    amount: int = 1,
) -> None:
    """Увеличить месячный счётчик использования метрики."""
    period = _current_period()
    counter = (
        await db.execute(
            select(UsageCounter).where(
                UsageCounter.user_id == user_id,
                UsageCounter.metric == metric,
                UsageCounter.period == period,
            )
        )
    ).scalar_one_or_none()

    if counter:
        counter.count = (counter.count or 0) + amount
    else:
        counter = UsageCounter(user_id=user_id, metric=metric, period=period, count=amount)
        db.add(counter)

    await db.commit()


async def enforce_monthly_limit(
    db: AsyncSession,
    user_id,
    metric: str,
    amount: int = 1,
) -> None:
    """
    Проверить и увеличить месячный счётчик (например, ai_generations_per_month).

    Бросает 402, если действие превысит месячный лимит. Иначе инкрементирует счётчик.
    """
    await check_monthly_limit(db, user_id, metric, amount)
    await increment_monthly_usage(db, user_id, metric, amount)
