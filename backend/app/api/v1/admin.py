"""
Admin Control Center — read-only эндпоинты для суперпользователя.

Все маршруты защищены зависимостью ``get_current_superuser`` (обычный пользователь
получает 403). Эндпоинты только читают данные и НИКОГДА не отдают секреты:
пароли-хэши, сырые API-ключи маркетплейсов и AI-провайдеров не возвращаются —
только маскированные значения.
"""

import asyncio
import time
from datetime import timedelta
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.core.datetime_utils import utcnow
from app.crud.marketplace_key import marketplace_key_crud
from app.models.ai_settings import AISettings
from app.models.marketplace_key import MarketplaceKey
from app.models.product import Product
from app.models.tariff import Tariff, UserSubscription
from app.models.usage import UsageCounter
from app.models.user import User
from app.services.auth_service import get_current_superuser
from app.services.cache_service import cache_service

router = APIRouter()

# Момент загрузки модуля — приблизительный старт процесса (для uptime в /system/status).
_PROCESS_START_MONOTONIC = time.monotonic()

# Поддерживаемые маркетплейсы (для /parser/status). Совпадает с ALLOWED_MARKETPLACES.
SUPPORTED_MARKETPLACES = [
    "wildberries",
    "ozon",
    "avito",
    "yandex_market",
    "kazanexpress",
]

# ====================================================================
# Финальная тарифная сетка (справочная витрина для админки).
# Это канонический «прайс», независимый от сидов БД. Read-only.
# Feature-флаги: BUSINESS+ означает BUSINESS и выше, AGENCY+ — AGENCY и выше.
# ====================================================================
ADMIN_TARIFF_CATALOG = [
    {
        "code": "trial",
        "name": "Trial",
        "price": 0,
        "currency": "RUB",
        "billing_period": "3 дня",
        "is_public": True,
        "is_manual_only": False,
        "limits": {
            "max_products": 100,
            "max_repricing_products": 20,
            "ai_generations_per_month": 10,
            "competitor_reports": 3,
            "max_users": 1,
            "price_update_frequency": 1,
        },
        "feature_flags": {
            "widget_access": False,
            "auto_repricing_access": False,
            "white_label_reports_access": False,
            "team_access": False,
            "agency_projects_access": False,
            "priority_queue_access": False,
        },
    },
    {
        "code": "pro",
        "name": "PRO",
        "price": 2990,
        "currency": "RUB",
        "billing_period": "месяц",
        "is_public": True,
        "is_manual_only": False,
        "limits": {
            "max_products": 500,
            "max_repricing_products": 100,
            "ai_generations_per_month": 50,
            "competitor_reports": 10,
            "max_users": 1,
            "price_update_frequency": 4,
        },
        "feature_flags": {
            "widget_access": False,
            "auto_repricing_access": False,
            "white_label_reports_access": False,
            "team_access": False,
            "agency_projects_access": False,
            "priority_queue_access": False,
        },
    },
    {
        "code": "business",
        "name": "BUSINESS",
        "price": 7990,
        "currency": "RUB",
        "billing_period": "месяц",
        "is_public": True,
        "is_manual_only": False,
        "limits": {
            "max_products": -1,
            "max_repricing_products": -1,
            "ai_generations_per_month": -1,
            "competitor_reports": -1,
            "max_users": 5,
            "price_update_frequency": 24,
        },
        "feature_flags": {
            "widget_access": True,
            "auto_repricing_access": True,
            "white_label_reports_access": False,
            "team_access": True,
            "agency_projects_access": False,
            "priority_queue_access": True,
        },
    },
    {
        "code": "agency",
        "name": "AGENCY",
        "price": 14990,
        "currency": "RUB",
        "billing_period": "месяц",
        "is_public": True,
        "is_manual_only": False,
        "limits": {
            "max_products": -1,
            "max_repricing_products": -1,
            "ai_generations_per_month": -1,
            "competitor_reports": -1,
            "max_users": 15,
            "price_update_frequency": 24,
        },
        "feature_flags": {
            "widget_access": True,
            "auto_repricing_access": True,
            "white_label_reports_access": True,
            "team_access": True,
            "agency_projects_access": True,
            "priority_queue_access": True,
        },
    },
    {
        "code": "enterprise",
        "name": "ENTERPRISE",
        "price": None,
        "currency": "RUB",
        "billing_period": "индивидуально",
        "is_public": False,
        "is_manual_only": True,
        "limits": {
            "max_products": -1,
            "max_repricing_products": -1,
            "ai_generations_per_month": -1,
            "competitor_reports": -1,
            "max_users": -1,
            "price_update_frequency": 24,
        },
        "feature_flags": {
            "widget_access": True,
            "auto_repricing_access": True,
            "white_label_reports_access": True,
            "team_access": True,
            "agency_projects_access": True,
            "priority_queue_access": True,
        },
    },
]


# ====================================================================
# Безопасные служебные проверки (никогда не бросают исключений наружу)
# ====================================================================
async def _scalar(db: AsyncSession, stmt) -> int:
    """Выполнить count/scalar-запрос и вернуть число (0 при None)."""
    result = await db.execute(stmt)
    return int(result.scalar() or 0)


async def _check_db(db: AsyncSession) -> str:
    """Проверка доступности БД через SELECT 1."""
    try:
        await db.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "unavailable"


async def _check_redis() -> str:
    """Проверка Redis через ping (не бросает исключений)."""
    try:
        ok = await cache_service.ping()
        return "ok" if ok else "unavailable"
    except Exception:
        return "unavailable"


async def _check_celery() -> dict:
    """
    Best-effort проверка живости Celery worker через control.inspect().ping().

    Выполняется в отдельном потоке с таймаутом, чтобы не блокировать event loop
    и не зависать, если брокер/воркер недоступны.
    """
    def _ping() -> dict:
        from app.celery_app import celery_app

        inspector = celery_app.control.inspect(timeout=0.5)
        return inspector.ping() or {}

    try:
        replies = await asyncio.wait_for(asyncio.to_thread(_ping), timeout=2.0)
        if replies:
            return {"status": "ok", "workers": list(replies.keys())}
        return {"status": "unknown", "workers": []}
    except Exception:
        return {"status": "unknown", "workers": []}


def _alembic_head() -> Optional[str]:
    """Текущий head миграций по скриптам (best-effort)."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        ini_path = Path(__file__).resolve().parents[3] / "alembic.ini"
        cfg = Config(str(ini_path))
        script = ScriptDirectory.from_config(cfg)
        return script.get_current_head()
    except Exception:
        return None


async def _alembic_current(db: AsyncSession) -> Optional[str]:
    """Текущая версия из таблицы alembic_version (best-effort)."""
    try:
        result = await db.execute(text("SELECT version_num FROM alembic_version"))
        row = result.first()
        return row[0] if row else None
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass
        return None


def _parser_debug_enabled() -> bool:
    """Включены ли debug-дампы парсера (без падения, если parser не импортируется)."""
    try:
        from app.services.parser import _parser_debug_dumps_enabled

        return bool(_parser_debug_dumps_enabled())
    except Exception:
        return False


def _parser_debug_dir() -> Optional[str]:
    try:
        from app.services.parser import _parser_debug_dir as _dir

        return str(_dir())
    except Exception:
        return None


def _proxy_pool_stats() -> dict:
    """Сводка по пулу прокси без раскрытия адресов."""
    try:
        from app.services.proxy_pool import get_proxy_stats

        stats = get_proxy_stats() or {}
        total = int(stats.get("total", 0) or 0)
        return {
            "enabled": total > 0,
            "total": total,
            "available": int(stats.get("available", 0) or 0),
            "blocked": int(stats.get("blocked", 0) or 0),
        }
    except Exception:
        return {"enabled": False, "total": 0, "available": 0, "blocked": 0}


def _provider_info(env_value: Optional[str], db_value: Optional[str]) -> dict:
    """Сводка по AI-провайдеру: настроен ли и маскированный ключ (без раскрытия)."""
    configured = bool(env_value) or bool(db_value)
    key_masked: Optional[str] = None
    if env_value:
        key_masked = marketplace_key_crud.mask_key(str(env_value))
    elif db_value:
        # Ключ в БД хранится зашифрованным — не расшифровываем, отдаём заглушку.
        key_masked = "***"
    return {"configured": configured, "key_masked": key_masked}


# ====================================================================
# 1. Обзор
# ====================================================================
@router.get("/overview")
async def admin_overview(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    """Сводные метрики платформы для дашборда админки."""
    now = utcnow()

    users_total = await _scalar(db, select(func.count()).select_from(User))
    new_24h = await _scalar(
        db,
        select(func.count()).select_from(User).where(User.created_at >= now - timedelta(days=1)),
    )
    new_7d = await _scalar(
        db,
        select(func.count()).select_from(User).where(User.created_at >= now - timedelta(days=7)),
    )
    new_30d = await _scalar(
        db,
        select(func.count()).select_from(User).where(User.created_at >= now - timedelta(days=30)),
    )

    active_trials = await _scalar(
        db,
        select(func.count()).select_from(UserSubscription).where(UserSubscription.status == "trial"),
    )
    active_subscriptions = await _scalar(
        db,
        select(func.count())
        .select_from(UserSubscription)
        .where(UserSubscription.status.in_(["active", "trial"])),
    )
    paid_users = await _scalar(
        db,
        select(func.count(func.distinct(UserSubscription.user_id))).where(
            UserSubscription.status == "active"
        ),
    )

    # Приблизительный MRR: сумма помесячной стоимости активных платных подписок.
    mrr = 0.0
    mrr_rows = await db.execute(
        select(UserSubscription.billing_cycle, Tariff.price_monthly, Tariff.price_yearly)
        .join(Tariff, UserSubscription.tariff_id == Tariff.id)
        .where(UserSubscription.status == "active")
    )
    for billing_cycle, price_monthly, price_yearly in mrr_rows.all():
        if billing_cycle == "yearly" and price_yearly:
            mrr += float(price_yearly) / 12.0
        elif price_monthly:
            mrr += float(price_monthly)

    celery = await _check_celery()

    return {
        "users_total": users_total,
        "new_users_24h": new_24h,
        "new_users_7d": new_7d,
        "new_users_30d": new_30d,
        "active_trials": active_trials,
        "paid_users": paid_users,
        "active_subscriptions": active_subscriptions,
        "approximate_mrr": round(mrr, 2),
        "currency": "RUB",
        "backend_status": "ok",
        "db_status": await _check_db(db),
        "redis_status": await _check_redis(),
        "celery_status": celery["status"],
        # Статистики ещё не собираются — честный null вместо выдуманных данных.
        "parser_summary": None,
        "ai_summary": None,
    }


# ====================================================================
# 2. Пользователи
# ====================================================================
@router.get("/users")
async def admin_users(
    search: str = Query("", description="Поиск по email, имени или ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    """Список пользователей с базовыми метриками. Хэш пароля не возвращается."""
    base = select(User)
    count_base = select(func.count()).select_from(User)

    search = (search or "").strip()
    if search:
        pattern = f"%{search.lower()}%"
        condition = func.lower(User.email).like(pattern)
        name_condition = func.lower(func.coalesce(User.full_name, "")).like(pattern)
        filter_clause = condition | name_condition
        # Точное совпадение по UUID, если строка похожа на id.
        try:
            filter_clause = filter_clause | (User.id == UUID(search))
        except (ValueError, AttributeError):
            pass
        base = base.where(filter_clause)
        count_base = count_base.where(filter_clause)

    total = await _scalar(db, count_base)

    rows = await db.execute(
        base.order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    users = list(rows.scalars().all())
    user_ids = [u.id for u in users]

    # Карты счётчиков и подписок одним запросом на страницу (без N+1).
    products_map: dict = {}
    keys_map: dict = {}
    subs_map: dict = {}

    if user_ids:
        prod_rows = await db.execute(
            select(Product.user_id, func.count())
            .where(Product.user_id.in_(user_ids))
            .group_by(Product.user_id)
        )
        products_map = {uid: int(cnt) for uid, cnt in prod_rows.all()}

        key_rows = await db.execute(
            select(MarketplaceKey.user_id, func.count())
            .where(MarketplaceKey.user_id.in_(user_ids))
            .group_by(MarketplaceKey.user_id)
        )
        keys_map = {uid: int(cnt) for uid, cnt in key_rows.all()}

        sub_rows = await db.execute(
            select(
                UserSubscription.user_id,
                UserSubscription.status,
                UserSubscription.is_trial,
                UserSubscription.trial_ends_at,
                Tariff.code,
            )
            .join(Tariff, UserSubscription.tariff_id == Tariff.id)
            .where(
                UserSubscription.user_id.in_(user_ids),
                UserSubscription.status.in_(["active", "trial"]),
            )
        )
        for uid, st, is_trial, trial_ends_at, code in sub_rows.all():
            # Берём первую active/trial подписку как текущую.
            subs_map.setdefault(
                uid,
                {
                    "subscription_status": st,
                    "current_tariff": code,
                    "is_trial": bool(is_trial),
                    "trial_until": trial_ends_at,
                },
            )

    items = []
    for user in users:
        sub = subs_map.get(user.id, {})
        items.append(
            {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
                "is_marketplace_seller": user.is_marketplace_seller,
                "created_at": user.created_at,
                "current_tariff": sub.get("current_tariff"),
                "subscription_status": sub.get("subscription_status", "none"),
                "trial_until": sub.get("trial_until"),
                "products_count": products_map.get(user.id, 0),
                "marketplace_keys_count": keys_map.get(user.id, 0),
                "last_activity": None,  # отдельного поля активности пока нет
            }
        )

    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/users/{user_id}")
async def admin_user_detail(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    """Детали пользователя. Ключи маркетплейсов — только маскированные."""
    try:
        uid = UUID(user_id)
    except (ValueError, AttributeError):
        return {"detail": "Пользователь не найден"}

    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if user is None:
        return {"detail": "Пользователь не найден"}

    # Подписка (текущая)
    sub_row = (
        await db.execute(
            select(UserSubscription, Tariff)
            .join(Tariff, UserSubscription.tariff_id == Tariff.id)
            .where(UserSubscription.user_id == uid)
            .order_by(UserSubscription.created_at.desc())
            .limit(1)
        )
    ).first()

    subscription = None
    if sub_row is not None:
        sub, tariff = sub_row
        subscription = {
            "tariff_code": tariff.code,
            "tariff_name": tariff.name,
            "status": sub.status,
            "is_trial": sub.is_trial,
            "trial_ends_at": sub.trial_ends_at,
            "expires_at": sub.expires_at,
            "billing_cycle": sub.billing_cycle,
        }

    # Usage за текущий период
    period = utcnow().strftime("%Y-%m")
    usage_rows = await db.execute(
        select(UsageCounter.metric, UsageCounter.count).where(
            UsageCounter.user_id == uid, UsageCounter.period == period
        )
    )
    usage = {metric: int(count) for metric, count in usage_rows.all()}

    # Ключи маркетплейсов — только маскированные
    key_rows = await db.execute(
        select(MarketplaceKey).where(MarketplaceKey.user_id == uid)
    )
    keys = []
    for key in key_rows.scalars().all():
        masked = "***"
        try:
            decrypted = marketplace_key_crud.decrypt_key(key.api_key_encrypted)
            masked = marketplace_key_crud.mask_key(decrypted)
        except Exception:
            masked = "***"
        keys.append(
            {
                "marketplace": key.marketplace,
                "api_key_masked": masked,
                "is_active": key.is_active,
                "is_valid": key.is_valid,
                "last_checked": key.last_checked,
                "created_at": key.created_at,
            }
        )

    products_count = await _scalar(
        db, select(func.count()).select_from(Product).where(Product.user_id == uid)
    )

    return {
        "profile": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "is_marketplace_seller": user.is_marketplace_seller,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        },
        "subscription": subscription,
        "usage": usage,
        "products_count": products_count,
        "marketplace_keys": keys,
        # Журнал действий/безопасности ещё не подключён (см. /admin/audit).
        "recent_events": [],
    }


# ====================================================================
# 3. Биллинг — подписки
# ====================================================================
@router.get("/billing/subscriptions")
async def admin_billing_subscriptions(
    status: str = Query("", description="Фильтр по статусу подписки"),
    plan: str = Query("", description="Фильтр по коду тарифа"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    """Список подписок пользователей. Только чтение, без управляющих действий."""
    base = (
        select(UserSubscription, User.email, Tariff)
        .join(User, UserSubscription.user_id == User.id)
        .join(Tariff, UserSubscription.tariff_id == Tariff.id)
    )
    count_base = select(func.count()).select_from(UserSubscription).join(
        Tariff, UserSubscription.tariff_id == Tariff.id
    )

    status = (status or "").strip()
    plan = (plan or "").strip()
    if status:
        base = base.where(UserSubscription.status == status)
        count_base = count_base.where(UserSubscription.status == status)
    if plan:
        base = base.where(Tariff.code == plan)
        count_base = count_base.where(Tariff.code == plan)

    total = await _scalar(db, count_base)

    rows = await db.execute(
        base.order_by(UserSubscription.created_at.desc()).limit(limit).offset(offset)
    )

    items = []
    for sub, email, tariff in rows.all():
        if sub.billing_cycle == "yearly":
            price = tariff.price_yearly
        else:
            price = tariff.price_monthly
        items.append(
            {
                "user_email": email,
                "plan": tariff.code,
                "plan_name": tariff.name,
                "status": sub.status,
                "started_at": sub.started_at,
                "current_period_end": sub.expires_at,
                "trial_ends_at": sub.trial_ends_at,
                "is_trial": sub.is_trial,
                "is_active": sub.status == "active",
                "price": price,
                "billing_cycle": sub.billing_cycle,
                "source": sub.payment_method or "manual",
            }
        )

    return {"items": items, "total": total, "limit": limit, "offset": offset}


# ====================================================================
# 4. Тарифы (финальная сетка)
# ====================================================================
@router.get("/tariffs")
async def admin_tariffs(_: User = Depends(get_current_superuser)) -> dict:
    """Канонический прайс с лимитами и feature-флагами. Read-only."""
    return {"items": ADMIN_TARIFF_CATALOG}


# ====================================================================
# 5. Система
# ====================================================================
@router.get("/system/status")
async def admin_system_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    """Состояние инфраструктуры и предупреждения по опасным конфигурациям."""
    db_status = await _check_db(db)
    redis_status = await _check_redis()
    celery = await _check_celery()
    alembic_current = await _alembic_current(db)
    alembic_head = _alembic_head()
    parser_debug = _parser_debug_enabled()

    warnings = []
    if settings.debug:
        warnings.append("DEBUG=true — отключите отладку в production")
    if not settings.is_production:
        warnings.append("ENVIRONMENT не production")
    if db_status != "ok":
        warnings.append("База данных недоступна")
    if redis_status != "ok":
        warnings.append("Redis недоступен")
    if celery["status"] != "ok":
        warnings.append("Celery worker не отвечает")
    if alembic_current and alembic_head and alembic_current != alembic_head:
        warnings.append("Версия миграций (current) не совпадает с head")
    if parser_debug:
        warnings.append("Debug-дампы парсера включены (PARSER_DEBUG_DUMPS)")

    return {
        "environment": settings.environment,
        "debug": settings.debug,
        "is_production": settings.is_production,
        "version": settings.app_version,
        "commit": None,
        "uptime_seconds": round(time.monotonic() - _PROCESS_START_MONOTONIC, 1),
        "db_status": db_status,
        "redis_status": redis_status,
        "celery_status": celery["status"],
        "celery_workers": celery["workers"],
        "alembic_current": alembic_current,
        "alembic_head": alembic_head,
        "parser_debug_dumps_enabled": parser_debug,
        "warnings": warnings,
    }


# ====================================================================
# 6. Безопасность (read-only, честные заглушки пока нет сбора событий)
# ====================================================================
@router.get("/security/events")
async def admin_security_events(_: User = Depends(get_current_superuser)) -> dict:
    """
    Сводка событий безопасности.

    Централизованного сбора событий пока нет, поэтому возвращаем честные пустые
    структуры с пометкой ``available: false`` — без выдуманных данных.
    """
    return {
        "available": False,
        "note": "Сбор событий безопасности ещё не подключён. Появится в следующем спринте.",
        "failed_logins": [],
        "suspicious_events": [],
        "recent_401_403_summary": {"window": "24h", "count_401": None, "count_403": None},
        "admin_actions_summary": {"available": False, "count": 0},
    }


# ====================================================================
# 7. Журнал действий (audit log ещё не создан — read-only заглушка)
# ====================================================================
@router.get("/audit")
async def admin_audit(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    action: str = Query(""),
    actor: str = Query(""),
    target: str = Query(""),
    _: User = Depends(get_current_superuser),
) -> dict:
    """
    Лента административных действий.

    Модель audit_log пока не реализована (см. отчёт). Эндпоинт возвращает пустую
    ленту с ``available: false``, не падает и поддерживает параметры фильтрации.
    """
    return {
        "available": False,
        "note": "Журнал действий (audit_log) ещё не создан. Предложена минимальная модель в отчёте.",
        "items": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
        "filters": {"action": action or None, "actor": actor or None, "target": target or None},
    }


# ====================================================================
# 8. Парсер
# ====================================================================
@router.get("/parser/status")
async def admin_parser_status(_: User = Depends(get_current_superuser)) -> dict:
    """Конфигурация парсера и пула прокси. Логику парсера не затрагивает."""
    return {
        "parser_debug_dumps_enabled": _parser_debug_enabled(),
        "parser_debug_dir": _parser_debug_dir(),
        "supported_marketplaces": SUPPORTED_MARKETPLACES,
        "proxy_pool": _proxy_pool_stats(),
        # Статистика парсинга ещё не собирается централизованно.
        "recent_stats": None,
    }


# ====================================================================
# 9. AI-провайдеры
# ====================================================================
@router.get("/ai/status")
async def admin_ai_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    """Статус AI-провайдеров. Ключи только маскированные, сырые не возвращаются."""
    ai_row = None
    try:
        ai_row = (
            await db.execute(select(AISettings).order_by(AISettings.id.desc()).limit(1))
        ).scalar_one_or_none()
    except Exception:
        ai_row = None

    active_provider = ai_row.current_provider if ai_row else "none"

    providers = {
        "yandex": _provider_info(
            settings.yandex_gpt_api_key, getattr(ai_row, "yandex_api_key", None)
        ),
        "openai": _provider_info(
            settings.openai_api_key, getattr(ai_row, "openai_api_key", None)
        ),
        "deepseek": _provider_info(
            settings.deepseek_api_key, getattr(ai_row, "deepseek_api_key", None)
        ),
    }

    return {
        "active_provider": active_provider,
        "providers": providers,
        # Безопасная проверка соединения и счётчики использования — следующий спринт.
        "test_connection_status": None,
        "usage_counters": None,
        "last_errors": None,
    }
