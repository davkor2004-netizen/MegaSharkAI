"""
Admin Control Center — read-only эндпоинты для суперпользователя.

Все маршруты защищены зависимостью ``get_current_superuser`` (обычный пользователь
получает 403). Эндпоинты только читают данные и НИКОГДА не отдают секреты:
пароли-хэши, сырые API-ключи маркетплейсов и AI-провайдеров не возвращаются —
только маскированные значения.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import admin_actions_service
from app.services.admin_actions_service import AdminActionError

from app.config import settings
from app.core.database import get_db
from app.core.datetime_utils import utcnow
from app.crud.marketplace_key import marketplace_key_crud
from app.models.ai_settings import AISettings
from app.models.audit import AuditLog, SecurityEvent
from app.models.marketplace_key import MarketplaceKey
from app.models.product import Product
from app.models.tariff import Tariff, UserSubscription
from app.models.usage import UsageCounter
from app.models.user import User
from app.services.auth_service import get_current_superuser
from app.services.cache_service import cache_service
from app.services import feature_access, plans

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
# Тарифная сетка для админки строится ИЗ КАНОНИЧЕСКОГО источника
# (app/services/plans.py), чтобы /admin/tariffs, /billing и enforcement
# никогда не расходились.
# ====================================================================
def _build_admin_tariff_catalog() -> list[dict]:
    """Сформировать read-only витрину тарифов из канонического каталога."""
    catalog: list[dict] = []
    for code in plans.PLAN_ORDER:
        plan = plans.PLAN_CATALOG[code]
        catalog.append(
            {
                "code": plan["code"],
                "name": plan["name"],
                "price": plan["price"],
                "currency": plan["currency"],
                "billing_period": plan["billing_period"],
                "is_public": plan["is_public"],
                "is_manual_only": plan["is_manual_only"],
                "limits": dict(plan["limits"]),
                "feature_flags": dict(plan["feature_flags"]),
            }
        )
    return catalog


ADMIN_TARIFF_CATALOG = _build_admin_tariff_catalog()


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

    # Сводка использования по тарифу (current_plan, лимиты, used/limit, feature-флаги).
    # Использует канонический источник тарифов — без раскрытия секретов.
    usage_summary = await feature_access.get_usage_summary(db, uid)

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
        "usage_summary": usage_summary,
        "products_count": products_count,
        "marketplace_keys": keys,
        # Журнал действий/безопасности ещё не подключён (см. /admin/audit).
        "recent_events": [],
    }


# ====================================================================
# 2b. Безопасные админские действия (write). Только superuser.
# Все действия пишут AuditLog. Платежи YooKassa НЕ затрагиваются.
# ====================================================================
class AdminReasonRequest(BaseModel):
    """Базовый запрос с причиной действия (для audit)."""

    reason: str = Field("", max_length=500, description="Причина действия (пишется в audit)")


class AdminChangePlanRequest(BaseModel):
    """Запрос ручной смены тарифа (admin override, без оплаты)."""

    tariff_code: str = Field(..., max_length=50, description="Код тарифа: trial/pro/business/agency/enterprise/manual")
    reason: str = Field("", max_length=500)
    period_end: Optional[datetime] = Field(None, description="Окончание платного периода (опционально)")
    trial_end: Optional[datetime] = Field(None, description="Окончание триала — переводит в статус trial (опционально)")


class AdminExtendRequest(BaseModel):
    """Запрос продления подписки/триала."""

    days: int = Field(..., ge=1, le=365, description="На сколько дней продлить (1..365)")
    reason: str = Field("", max_length=500)


def _handle_action_error(exc: AdminActionError) -> None:
    """Преобразовать бизнес-ошибку в HTTP-ответ."""
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/users/{user_id}/block")
async def admin_block_user(
    user_id: str,
    body: AdminReasonRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_superuser),
) -> dict:
    """Заблокировать пользователя (is_active=False). Пишет audit admin.user.block."""
    try:
        return await admin_actions_service.block_user(
            db, actor=admin, target_user_id=user_id, reason=body.reason, request=request
        )
    except AdminActionError as exc:
        _handle_action_error(exc)


@router.post("/users/{user_id}/unblock")
async def admin_unblock_user(
    user_id: str,
    body: AdminReasonRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_superuser),
) -> dict:
    """Разблокировать пользователя (is_active=True). Пишет audit admin.user.unblock."""
    try:
        return await admin_actions_service.unblock_user(
            db, actor=admin, target_user_id=user_id, reason=body.reason, request=request
        )
    except AdminActionError as exc:
        _handle_action_error(exc)


@router.post("/users/{user_id}/subscription/change-plan")
async def admin_change_plan(
    user_id: str,
    body: AdminChangePlanRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_superuser),
) -> dict:
    """Ручная смена тарифа (manual override, без YooKassa). Пишет audit."""
    try:
        return await admin_actions_service.change_plan(
            db,
            actor=admin,
            target_user_id=user_id,
            tariff_code=body.tariff_code,
            reason=body.reason,
            period_end=body.period_end,
            trial_end=body.trial_end,
            request=request,
        )
    except AdminActionError as exc:
        _handle_action_error(exc)


@router.post("/users/{user_id}/subscription/extend")
async def admin_extend_subscription(
    user_id: str,
    body: AdminExtendRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_superuser),
) -> dict:
    """Продлить подписку/триал на N дней. Пишет audit admin.subscription.extend."""
    try:
        return await admin_actions_service.extend_subscription(
            db, actor=admin, target_user_id=user_id, days=body.days, reason=body.reason, request=request
        )
    except AdminActionError as exc:
        _handle_action_error(exc)


@router.post("/users/{user_id}/subscription/cancel")
async def admin_cancel_subscription(
    user_id: str,
    body: AdminReasonRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_superuser),
) -> dict:
    """Отменить подписку вручную (без YooKassa). Пишет audit admin.subscription.cancel."""
    try:
        return await admin_actions_service.cancel_subscription(
            db, actor=admin, target_user_id=user_id, reason=body.reason, request=request
        )
    except AdminActionError as exc:
        _handle_action_error(exc)


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
        select(UserSubscription, User.email, User.id, Tariff)
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
    for sub, email, uid, tariff in rows.all():
        if sub.billing_cycle == "yearly":
            price = tariff.price_yearly
        else:
            price = tariff.price_monthly
        items.append(
            {
                "user_id": str(uid),
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


def _parse_metadata(raw: Optional[str]) -> Optional[dict]:
    """Безопасно разобрать JSON-метаданные из БД (уже санитизированные при записи)."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _short_user(user: Optional[User]) -> Optional[dict]:
    """Минимальное безопасное представление пользователя (без секретов)."""
    if user is None:
        return None
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
    }


# ====================================================================
# 6. Безопасность (real-time события из security_events)
# ====================================================================
@router.get("/security/events")
async def admin_security_events(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    severity: str = Query(""),
    event_type: str = Query(""),
    user_id: str = Query(""),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    """
    Лента и сводка событий безопасности.

    Возвращает события из таблицы ``security_events`` с фильтрами по severity,
    типу события и пользователю, а также агрегаты по уровням критичности.
    Секреты не хранятся и не отдаются (метаданные санитизируются при записи).
    """
    # --- Сводка по уровням критичности (по всей таблице) ---
    summary = {"info": 0, "warning": 0, "high": 0, "critical": 0}
    try:
        sev_rows = await db.execute(
            select(SecurityEvent.severity, func.count())
            .group_by(SecurityEvent.severity)
        )
        for sev, count in sev_rows.all():
            if sev in summary:
                summary[sev] = int(count or 0)
    except Exception:
        # Таблицы может не быть на очень старой БД — отдаём пустую сводку.
        return {
            "available": False,
            "note": "Хранилище событий безопасности недоступно.",
            "items": [],
            "total": 0,
            "summary": summary,
            "recent_failed_logins": [],
            "limit": limit,
            "offset": offset,
        }

    # --- Базовый запрос с фильтрами ---
    query = (
        select(SecurityEvent, User)
        .outerjoin(User, SecurityEvent.user_id == User.id)
    )
    count_query = select(func.count()).select_from(SecurityEvent)

    if severity:
        query = query.where(SecurityEvent.severity == severity)
        count_query = count_query.where(SecurityEvent.severity == severity)
    if event_type:
        query = query.where(SecurityEvent.event_type == event_type)
        count_query = count_query.where(SecurityEvent.event_type == event_type)
    if user_id:
        try:
            uid = UUID(user_id)
            query = query.where(SecurityEvent.user_id == uid)
            count_query = count_query.where(SecurityEvent.user_id == uid)
        except ValueError:
            pass

    total = int((await db.execute(count_query)).scalar() or 0)

    rows = (
        await db.execute(
            query.order_by(SecurityEvent.created_at.desc(), SecurityEvent.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    items = []
    for event, user in rows:
        items.append({
            "id": event.id,
            "event_type": event.event_type,
            "severity": event.severity,
            "user": _short_user(user),
            "ip": event.ip,
            "user_agent": event.user_agent,
            "path": event.path,
            "method": event.method,
            "status_code": event.status_code,
            "metadata": _parse_metadata(event.metadata_json),
            "created_at": event.created_at.isoformat() if event.created_at else None,
        })

    # --- Недавние неудачные входы (для быстрого триажа) ---
    failed_rows = (
        await db.execute(
            select(SecurityEvent)
            .where(SecurityEvent.event_type == "login_failed")
            .order_by(SecurityEvent.created_at.desc(), SecurityEvent.id.desc())
            .limit(10)
        )
    ).scalars().all()
    recent_failed_logins = [
        {
            "id": e.id,
            "ip": e.ip,
            "metadata": _parse_metadata(e.metadata_json),
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in failed_rows
    ]

    return {
        "available": True,
        "items": items,
        "total": total,
        "summary": summary,
        "recent_failed_logins": recent_failed_logins,
        "limit": limit,
        "offset": offset,
        "filters": {
            "severity": severity or None,
            "event_type": event_type or None,
            "user_id": user_id or None,
        },
    }


# ====================================================================
# 7. Журнал действий (audit log из таблицы audit_logs)
# ====================================================================
@router.get("/audit")
async def admin_audit(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    action: str = Query(""),
    actor: str = Query(""),
    target: str = Query(""),
    entity_type: str = Query(""),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    """
    Лента административных и значимых действий из таблицы ``audit_logs``.

    Поддерживает фильтры по действию, инициатору (actor), цели (target) и типу
    сущности. Метаданные уже санитизированы при записи — секретов не содержат.
    """
    Actor = aliased(User)
    Target = aliased(User)

    query = (
        select(AuditLog, Actor, Target)
        .outerjoin(Actor, AuditLog.actor_user_id == Actor.id)
        .outerjoin(Target, AuditLog.target_user_id == Target.id)
    )
    count_query = select(func.count()).select_from(AuditLog)

    try:
        if action:
            query = query.where(AuditLog.action == action)
            count_query = count_query.where(AuditLog.action == action)
        if entity_type:
            query = query.where(AuditLog.entity_type == entity_type)
            count_query = count_query.where(AuditLog.entity_type == entity_type)
        if actor:
            try:
                actor_uuid = UUID(actor)
                query = query.where(AuditLog.actor_user_id == actor_uuid)
                count_query = count_query.where(AuditLog.actor_user_id == actor_uuid)
            except ValueError:
                query = query.where(Actor.email.ilike(f"%{actor}%"))
                count_query = count_query.where(
                    AuditLog.actor_user_id.in_(
                        select(User.id).where(User.email.ilike(f"%{actor}%"))
                    )
                )
        if target:
            try:
                target_uuid = UUID(target)
                query = query.where(AuditLog.target_user_id == target_uuid)
                count_query = count_query.where(AuditLog.target_user_id == target_uuid)
            except ValueError:
                query = query.where(Target.email.ilike(f"%{target}%"))
                count_query = count_query.where(
                    AuditLog.target_user_id.in_(
                        select(User.id).where(User.email.ilike(f"%{target}%"))
                    )
                )

        total = int((await db.execute(count_query)).scalar() or 0)

        rows = (
            await db.execute(
                query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
    except Exception:
        return {
            "available": False,
            "note": "Хранилище журнала действий недоступно.",
            "items": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
        }

    items = []
    for entry, actor_user, target_user in rows:
        items.append({
            "id": entry.id,
            "action": entry.action,
            "actor": _short_user(actor_user),
            "target": _short_user(target_user),
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "metadata": _parse_metadata(entry.metadata_json),
            "ip": entry.ip,
            "user_agent": entry.user_agent,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        })

    return {
        "available": True,
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {
            "action": action or None,
            "actor": actor or None,
            "target": target or None,
            "entity_type": entity_type or None,
        },
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
