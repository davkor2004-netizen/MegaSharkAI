"""
Безопасные административные действия над пользователями и подписками.

Принципы:
- Только для superuser (проверка прав — на уровне роутера через get_current_superuser).
- Никаких реальных платёжных операций (YooKassa НЕ вызывается): изменения подписок
  выполняются вручную и помечаются как ``manual_admin`` override.
- Каждое действие пишет запись в AuditLog с санитизированными метаданными.
- Нельзя удалить пользователя на этом этапе; блокировка = ``is_active = False``.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utcnow
from app.models.tariff import Tariff, UserSubscription
from app.models.user import User
from app.services.audit_service import log_audit_event

# Пометка ручного (админского) изменения подписки в существующем поле payment_method.
# Отдельного поля source в модели нет, поэтому используем безопасную метку здесь
# и дублируем флаг manual=true в audit-метаданные.
MANUAL_OVERRIDE_MARKER = "manual_admin"

# Разрешённые коды тарифов для ручной смены плана.
ALLOWED_PLAN_CODES = {"trial", "pro", "business", "agency", "enterprise", "manual"}

# Максимальный срок единичного продления (защита от случайного "вечного" продления).
MAX_EXTEND_DAYS = 365


class AdminActionError(Exception):
    """Бизнес-ошибка админского действия с HTTP-кодом и сообщением."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def _get_user_or_404(db: AsyncSession, user_id: str) -> User:
    """Получить пользователя по id или бросить 404."""
    try:
        uid = UUID(str(user_id))
    except (ValueError, AttributeError):
        raise AdminActionError(404, "Пользователь не найден")
    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if user is None:
        raise AdminActionError(404, "Пользователь не найден")
    return user


async def _latest_subscription(
    db: AsyncSession, user_id: UUID, only_active: bool = False
) -> Optional[UserSubscription]:
    """Последняя подписка пользователя (опционально — только active/trial)."""
    stmt = select(UserSubscription).where(UserSubscription.user_id == user_id)
    if only_active:
        stmt = stmt.where(UserSubscription.status.in_(["active", "trial"]))
    stmt = stmt.order_by(UserSubscription.created_at.desc()).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none()


async def _tariff_code(db: AsyncSession, tariff_id: Optional[UUID]) -> Optional[str]:
    """Код тарифа по id (для записи в audit)."""
    if tariff_id is None:
        return None
    tariff = (await db.execute(select(Tariff).where(Tariff.id == tariff_id))).scalar_one_or_none()
    return tariff.code if tariff else None


# ---------------------------------------------------------------------------
# 1. Блокировка / разблокировка
# ---------------------------------------------------------------------------
async def block_user(
    db: AsyncSession,
    *,
    actor: User,
    target_user_id: str,
    reason: str = "",
    request: Optional[Request] = None,
) -> dict:
    """Заблокировать пользователя (is_active=False) с защитами и audit."""
    target = await _get_user_or_404(db, target_user_id)

    if target.id == actor.id:
        raise AdminActionError(400, "Нельзя заблокировать самого себя")

    # Нельзя заблокировать последнего активного суперпользователя.
    if target.is_superuser and target.is_active:
        active_superusers = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(User)
                    .where(User.is_superuser.is_(True), User.is_active.is_(True))
                )
            ).scalar()
            or 0
        )
        if active_superusers <= 1:
            raise AdminActionError(400, "Нельзя заблокировать последнего администратора")

    old_status = "active" if target.is_active else "blocked"
    if not target.is_active:
        # Уже заблокирован — не считаем ошибкой, но и не пишем лишний audit.
        return {"user_id": str(target.id), "is_active": False, "changed": False}

    target.is_active = False
    await db.commit()

    await log_audit_event(
        db,
        action="admin.user.block",
        actor_user_id=actor.id,
        target_user_id=target.id,
        entity_type="user",
        entity_id=target.id,
        metadata={"reason": reason, "old_status": old_status, "new_status": "blocked"},
        request=request,
    )
    return {"user_id": str(target.id), "is_active": False, "changed": True}


async def unblock_user(
    db: AsyncSession,
    *,
    actor: User,
    target_user_id: str,
    reason: str = "",
    request: Optional[Request] = None,
) -> dict:
    """Разблокировать пользователя (is_active=True) с audit."""
    target = await _get_user_or_404(db, target_user_id)

    old_status = "active" if target.is_active else "blocked"
    if target.is_active:
        return {"user_id": str(target.id), "is_active": True, "changed": False}

    target.is_active = True
    await db.commit()

    await log_audit_event(
        db,
        action="admin.user.unblock",
        actor_user_id=actor.id,
        target_user_id=target.id,
        entity_type="user",
        entity_id=target.id,
        metadata={"reason": reason, "old_status": old_status, "new_status": "active"},
        request=request,
    )
    return {"user_id": str(target.id), "is_active": True, "changed": True}


# ---------------------------------------------------------------------------
# 2. Ручная смена тарифа
# ---------------------------------------------------------------------------
async def change_plan(
    db: AsyncSession,
    *,
    actor: User,
    target_user_id: str,
    tariff_code: str,
    reason: str = "",
    period_end: Optional[datetime] = None,
    trial_end: Optional[datetime] = None,
    request: Optional[Request] = None,
) -> dict:
    """
    Ручная смена тарифа/подписки (admin override, без YooKassa).

    Обновляет последнюю подписку пользователя или создаёт новую. Помечает
    payment_method=manual_admin. Реальные платежи не выполняются.
    """
    code = (tariff_code or "").strip().lower()
    if code not in ALLOWED_PLAN_CODES:
        raise AdminActionError(400, f"Недопустимый тариф: {tariff_code}")

    target = await _get_user_or_404(db, target_user_id)

    tariff = (
        await db.execute(select(Tariff).where(Tariff.code == code))
    ).scalar_one_or_none()
    if tariff is None:
        raise AdminActionError(404, f"Тариф '{code}' не найден в системе")

    now = utcnow()
    sub = await _latest_subscription(db, target.id)
    old_plan = await _tariff_code(db, sub.tariff_id) if sub else None
    old_status = sub.status if sub else "none"

    # Определяем целевое состояние подписки.
    if trial_end is not None:
        new_status = "trial"
        is_trial = True
    else:
        new_status = "active"
        is_trial = False

    if sub is None:
        sub = UserSubscription(user_id=target.id, tariff_id=tariff.id)
        db.add(sub)
    else:
        # Сохраняем предыдущий тариф для истории.
        sub.previous_tariff_id = sub.tariff_id
        sub.tariff_id = tariff.id

    sub.status = new_status
    sub.is_trial = is_trial
    sub.payment_method = MANUAL_OVERRIDE_MARKER
    sub.auto_renew = False  # ручное изменение не включает автосписание

    if is_trial:
        sub.trial_started_at = sub.trial_started_at or now
        sub.trial_ends_at = trial_end
        sub.expires_at = period_end
    else:
        sub.started_at = now
        sub.expires_at = period_end or (now + timedelta(days=30))
        sub.trial_ends_at = trial_end  # обычно None

    await db.commit()

    await log_audit_event(
        db,
        action="admin.subscription.change_plan",
        actor_user_id=actor.id,
        target_user_id=target.id,
        entity_type="subscription",
        entity_id=sub.id,
        metadata={
            "old_plan": old_plan,
            "new_plan": code,
            "old_status": old_status,
            "new_status": new_status,
            "reason": reason,
            "manual": True,
            "period_end": period_end,
            "trial_end": trial_end,
        },
        request=request,
    )
    return {
        "user_id": str(target.id),
        "plan": code,
        "status": new_status,
        "manual": True,
    }


# ---------------------------------------------------------------------------
# 3. Продление подписки / триала
# ---------------------------------------------------------------------------
async def extend_subscription(
    db: AsyncSession,
    *,
    actor: User,
    target_user_id: str,
    days: int,
    reason: str = "",
    request: Optional[Request] = None,
) -> dict:
    """Продлить подписку или триал на N дней (1..365) с audit."""
    if days is None or days <= 0:
        raise AdminActionError(400, "Количество дней должно быть положительным")
    if days > MAX_EXTEND_DAYS:
        raise AdminActionError(400, f"Максимальное продление — {MAX_EXTEND_DAYS} дней")

    target = await _get_user_or_404(db, target_user_id)
    sub = await _latest_subscription(db, target.id)
    if sub is None:
        raise AdminActionError(404, "У пользователя нет подписки для продления")

    now = utcnow()
    # Триал продлеваем по trial_ends_at, платную — по expires_at.
    use_trial = bool(sub.is_trial or sub.status == "trial")
    field = "trial_ends_at" if use_trial else "expires_at"
    current_end = getattr(sub, field)

    # Продлеваем от текущего конца, если он в будущем, иначе от "сейчас".
    base = current_end if (current_end and current_end > now) else now
    new_end = base + timedelta(days=days)
    setattr(sub, field, new_end)
    await db.commit()

    await log_audit_event(
        db,
        action="admin.subscription.extend",
        actor_user_id=actor.id,
        target_user_id=target.id,
        entity_type="subscription",
        entity_id=sub.id,
        metadata={
            "days": days,
            "field": field,
            "old_end": current_end,
            "new_end": new_end,
            "reason": reason,
        },
        request=request,
    )
    return {
        "user_id": str(target.id),
        "field": field,
        "new_end": new_end.isoformat(),
        "days": days,
    }


# ---------------------------------------------------------------------------
# 4. Ручная отмена подписки
# ---------------------------------------------------------------------------
async def cancel_subscription(
    db: AsyncSession,
    *,
    actor: User,
    target_user_id: str,
    reason: str = "",
    request: Optional[Request] = None,
) -> dict:
    """Отменить активную/триальную подписку вручную (без YooKassa) с audit."""
    target = await _get_user_or_404(db, target_user_id)
    sub = await _latest_subscription(db, target.id, only_active=True)
    if sub is None:
        raise AdminActionError(404, "У пользователя нет активной подписки")

    old_status = sub.status
    sub.status = "cancelled"
    sub.auto_renew = False
    await db.commit()

    await log_audit_event(
        db,
        action="admin.subscription.cancel",
        actor_user_id=actor.id,
        target_user_id=target.id,
        entity_type="subscription",
        entity_id=sub.id,
        metadata={"old_status": old_status, "new_status": "cancelled", "reason": reason},
        request=request,
    )
    return {"user_id": str(target.id), "status": "cancelled"}
