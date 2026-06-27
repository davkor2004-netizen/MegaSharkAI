"""
Сервис контроля доступа по тарифу: feature-флаги и usage-лимиты.

Опирается на канонический каталог тарифов (app/services/plans.py). Предоставляет
единый набор функций для проверки доступа к функциям и enforcement лимитов:

- get_current_plan / get_plan_limits / get_plan_flags
- has_feature / require_feature              → 402 FEATURE_LOCKED
- check_usage_limit / increment_usage        → 402 LIMIT_EXCEEDED
- enforce_usage (monthly) / enforce_volume   → удобные обёртки
- get_usage_summary                          → данные для /billing/usage и админки

Ошибки возвращаются как HTTP 402 Payment Required с машиночитаемым detail:
{code, message, required_plan, current_plan, limit, used, reset_at, upgrade_url}.
"""

import json
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.datetime_utils import utcnow
from app.models.marketplace_key import MarketplaceKey
from app.models.product import Product
from app.models.tariff import Tariff, UserSubscription
from app.models.usage import UsageCounter
from app.services import plans

# Коды ошибок доступа.
CODE_FEATURE_LOCKED = "FEATURE_LOCKED"
CODE_LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
CODE_NO_SUBSCRIPTION = "NO_SUBSCRIPTION"

# Человекочитаемые названия фич (для сообщений).
FEATURE_LABELS: dict[str, str] = {
    "widget_access": "Виджет для сайта",
    "repricing_access": "Репрайсинг",
    "auto_repricing_access": "Авторепрайсинг",
    "telegram_notifications_access": "Telegram-уведомления",
    "advanced_reports_access": "Расширенные отчёты",
    "white_label_reports_access": "White-label отчёты",
    "team_access": "Командный доступ",
    "agency_projects_access": "Агентские проекты",
    "bulk_import_access": "Массовый импорт",
    "priority_queue_access": "Приоритетная очередь",
    "ai_audit_access": "AI-аудит карточек",
}

# usage_type → (ключ лимита в плане, метрика счётчика, тип, человекочитаемое имя)
# kind: "monthly" — учитывается через usage_counters; "volume" — по факту в БД.
USAGE_TYPES: dict[str, dict] = {
    "ai_actions": {"limit": "max_ai_actions_per_month", "metric": "ai_actions", "kind": "monthly", "label": "AI-действий в месяц"},
    "ai_audits": {"limit": "max_ai_audits_per_month", "metric": "ai_audits", "kind": "monthly", "label": "AI-аудитов в месяц"},
    "seo_generations": {"limit": "max_seo_generations_per_month", "metric": "seo_generations", "kind": "monthly", "label": "SEO-генераций в месяц"},
    "review_replies": {"limit": "max_review_replies_per_month", "metric": "review_replies", "kind": "monthly", "label": "ответов на отзывы в месяц"},
    "parsing_requests": {"limit": "max_parsing_requests_per_month", "metric": "parsing_requests", "kind": "monthly", "label": "запросов парсинга в месяц"},
    "exports": {"limit": "max_exports_per_month", "metric": "exports", "kind": "monthly", "label": "экспортов в месяц"},
    "products": {"limit": "max_products", "metric": "products", "kind": "volume", "label": "товаров"},
    "tracked_competitors": {"limit": "max_tracked_competitors", "metric": "tracked_competitors", "kind": "volume", "label": "отслеживаемых конкурентов"},
    "marketplace_keys": {"limit": "max_marketplace_keys", "metric": "marketplace_keys", "kind": "volume", "label": "ключей маркетплейсов"},
}


# ====================================================================
# Резолвинг плана
# ====================================================================
async def resolve_plan_code(db: AsyncSession, user_id) -> Optional[str]:
    """
    Код активного плана пользователя (trial/pro/business/agency/enterprise) или None.

    None означает «нет активной подписки» — применяется бесплатный fallback (Trial).
    """
    subscription = (
        await db.execute(
            select(UserSubscription)
            .where(UserSubscription.user_id == user_id)
            .where(UserSubscription.status.in_(["trial", "active"]))
            .order_by(UserSubscription.created_at.desc())
            .limit(1)
            .options(selectinload(UserSubscription.tariff))
        )
    ).scalar_one_or_none()

    if subscription is None:
        return None

    tariff = subscription.tariff
    if tariff is None:
        tariff = await db.get(Tariff, subscription.tariff_id)
    return tariff.code if tariff and tariff.code else None


async def get_current_plan(db: AsyncSession, user_id) -> str:
    """Эффективный код плана (с учётом бесплатного fallback на Trial)."""
    code = await resolve_plan_code(db, user_id)
    return code if code in plans.PLAN_CATALOG else plans.FREE_FALLBACK_PLAN


async def get_plan_limits(db: AsyncSession, user_id) -> dict:
    """
    Эффективные лимиты пользователя.

    Для ENTERPRISE индивидуальные лимиты берутся из JSON тарифа в БД (если заданы),
    иначе — из канонического каталога.
    """
    code = await resolve_plan_code(db, user_id)
    limits = plans.get_plan_limits(code)

    if code == "enterprise":
        # ENTERPRISE может иметь индивидуальные лимиты, заданные админом в тарифе.
        try:
            subscription = (
                await db.execute(
                    select(UserSubscription)
                    .where(UserSubscription.user_id == user_id)
                    .where(UserSubscription.status.in_(["trial", "active"]))
                    .order_by(UserSubscription.created_at.desc())
                    .limit(1)
                    .options(selectinload(UserSubscription.tariff))
                )
            ).scalar_one_or_none()
            if subscription and subscription.tariff and subscription.tariff.limits:
                custom = json.loads(subscription.tariff.limits)
                if isinstance(custom, dict):
                    limits.update({k: v for k, v in custom.items() if k in plans.LIMIT_KEYS})
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    return limits


async def get_plan_flags(db: AsyncSession, user_id) -> dict:
    """Эффективные feature-флаги пользователя."""
    code = await resolve_plan_code(db, user_id)
    return plans.get_plan_flags(code)


async def has_feature(db: AsyncSession, user_id, feature: str) -> bool:
    """Доступна ли фича на текущем плане."""
    flags = await get_plan_flags(db, user_id)
    return bool(flags.get(feature))


# ====================================================================
# Формирование ошибок 402
# ====================================================================
def _payment_required(
    code: str,
    message: str,
    *,
    current_plan: str,
    required_plan: Optional[str],
    limit: Optional[int] = None,
    used: Optional[int] = None,
    reset_at: Optional[str] = None,
) -> HTTPException:
    """Единообразная ошибка 402 Payment Required с машиночитаемым detail."""
    return HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "code": code,
            "message": message,
            "required_plan": required_plan,
            "current_plan": current_plan,
            "limit": limit,
            "used": used,
            "reset_at": reset_at,
            "upgrade_url": plans.UPGRADE_URL,
        },
    )


async def require_feature(db: AsyncSession, user_id, feature: str) -> None:
    """Проверить доступ к фиче. Бросает 402 FEATURE_LOCKED, если недоступна."""
    if await has_feature(db, user_id, feature):
        return
    current_plan = await get_current_plan(db, user_id)
    required = plans.feature_min_plan(feature)
    label = FEATURE_LABELS.get(feature, feature)
    required_name = plans.get_plan(required)["name"] if required else "более высоком тарифе"
    raise _payment_required(
        CODE_FEATURE_LOCKED,
        f"Функция «{label}» доступна на тарифе {required_name}. Повысьте тариф, чтобы использовать её.",
        current_plan=current_plan,
        required_plan=required,
    )


# ====================================================================
# Usage-лимиты
# ====================================================================
def _current_period() -> str:
    """Период учёта в формате YYYY-MM (календарный месяц)."""
    return utcnow().strftime("%Y-%m")


def _reset_at_iso() -> str:
    """ISO-время начала следующего календарного месяца (когда сбросятся счётчики)."""
    now = utcnow()
    if now.month == 12:
        nxt = datetime(now.year + 1, 1, 1)
    else:
        nxt = datetime(now.year, now.month + 1, 1)
    return nxt.isoformat()


async def _monthly_used(db: AsyncSession, user_id, metric: str) -> int:
    """Текущее значение месячного счётчика метрики."""
    counter = (
        await db.execute(
            select(UsageCounter).where(
                UsageCounter.user_id == user_id,
                UsageCounter.metric == metric,
                UsageCounter.period == _current_period(),
            )
        )
    ).scalar_one_or_none()
    return counter.count if counter else 0


async def _volume_used(db: AsyncSession, user_id, usage_type: str) -> int:
    """Текущее фактическое количество для volume-метрик (товары/конкуренты/ключи)."""
    if usage_type == "products":
        stmt = (
            select(func.count())
            .select_from(Product)
            .where(Product.user_id == user_id, Product.is_competitor.is_(False))
        )
    elif usage_type == "tracked_competitors":
        stmt = (
            select(func.count())
            .select_from(Product)
            .where(Product.user_id == user_id, Product.is_competitor.is_(True))
        )
    elif usage_type == "marketplace_keys":
        stmt = select(func.count()).select_from(MarketplaceKey).where(MarketplaceKey.user_id == user_id)
    else:
        return 0
    return int((await db.execute(stmt)).scalar() or 0)


def _limit_exceeded_error(
    usage_type: str, limit_value: int, used: int, current_plan: str
) -> HTTPException:
    """Сформировать 402 LIMIT_EXCEEDED для usage-типа."""
    spec = USAGE_TYPES[usage_type]
    label = spec["label"]
    required = plans.limit_min_plan(spec["limit"], used + 1)
    reset_at = _reset_at_iso() if spec["kind"] == "monthly" else None
    return _payment_required(
        CODE_LIMIT_EXCEEDED,
        f"Достигнут лимит тарифа: {label} (не более {limit_value}). Повысьте тариф, чтобы продолжить.",
        current_plan=current_plan,
        required_plan=required,
        limit=limit_value,
        used=used,
        reset_at=reset_at,
    )


async def check_usage_limit(db: AsyncSession, user_id, usage_type: str, amount: int = 1) -> None:
    """
    Проверить, не превышен ли лимит usage-типа (без инкремента).

    Бросает 402 LIMIT_EXCEEDED при превышении. ``-1`` в лимите = безлимит.
    """
    spec = USAGE_TYPES.get(usage_type)
    if spec is None:
        return
    limits = await get_plan_limits(db, user_id)
    limit_value = limits.get(spec["limit"])
    if limit_value is None or limit_value < 0:
        return

    if spec["kind"] == "monthly":
        used = await _monthly_used(db, user_id, spec["metric"])
    else:
        used = await _volume_used(db, user_id, usage_type)

    if used + amount > limit_value:
        current_plan = await get_current_plan(db, user_id)
        raise _limit_exceeded_error(usage_type, limit_value, used, current_plan)


async def increment_usage(db: AsyncSession, user_id, usage_type: str, amount: int = 1) -> None:
    """Увеличить месячный счётчик usage-типа (для kind='monthly')."""
    spec = USAGE_TYPES.get(usage_type)
    if spec is None or spec["kind"] != "monthly":
        return
    metric = spec["metric"]
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


async def enforce_usage(db: AsyncSession, user_id, usage_type: str, amount: int = 1) -> None:
    """Проверить месячный лимит и увеличить счётчик (monthly)."""
    await check_usage_limit(db, user_id, usage_type, amount)
    await increment_usage(db, user_id, usage_type, amount)


async def enforce_volume(db: AsyncSession, user_id, usage_type: str) -> None:
    """Проверить volume-лимит (товары/конкуренты/ключи) перед добавлением."""
    await check_usage_limit(db, user_id, usage_type, amount=1)


# ====================================================================
# Сводка использования (для /billing/usage и админки)
# ====================================================================
async def get_usage_summary(db: AsyncSession, user_id) -> dict:
    """
    Полная сводка: текущий план, лимиты, использование и feature-флаги.

    Используется фронтендом биллинга (прогресс-бары) и админкой (usage per user).
    Секретов не содержит.
    """
    code = await resolve_plan_code(db, user_id)
    effective_code = code if code in plans.PLAN_CATALOG else plans.FREE_FALLBACK_PLAN
    plan = plans.get_plan(effective_code)
    limits = await get_plan_limits(db, user_id)
    flags = await get_plan_flags(db, user_id)

    usage: dict[str, dict] = {}
    for usage_type, spec in USAGE_TYPES.items():
        limit_value = limits.get(spec["limit"])
        if spec["kind"] == "monthly":
            used = await _monthly_used(db, user_id, spec["metric"])
        else:
            used = await _volume_used(db, user_id, usage_type)
        usage[usage_type] = {
            "used": used,
            "limit": limit_value,
            "unlimited": limit_value is None or limit_value < 0,
            "kind": spec["kind"],
            "label": spec["label"],
        }

    return {
        "current_plan": effective_code,
        "plan_name": plan["name"],
        "is_subscribed": code is not None,
        "reset_at": _reset_at_iso(),
        "limits": limits,
        "features": flags,
        "usage": usage,
    }
