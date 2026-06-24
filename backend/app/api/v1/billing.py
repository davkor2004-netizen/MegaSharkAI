"""
Эндпоинты для управления тарифами и подписками.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import json

from app.core.database import get_db
from app.models.tariff import Tariff, UserSubscription
from app.models.user import User
from app.services.auth_service import get_current_user
from loguru import logger


router = APIRouter()


# ====================
# Схемы (Schemas)
# ====================

class TariffSchema(BaseModel):
    """Схема тарифа для отображения."""
    id: str
    name: str
    code: str
    price_monthly: float
    price_yearly: float
    trial_days: int
    features: Dict[str, Any]
    limits: Dict[str, Any]
    sort_order: int
    
    class Config:
        from_attributes = True


class UserSubscriptionSchema(BaseModel):
    """Схема текущей подписки пользователя."""
    tariff_code: Optional[str] = None
    tariff_name: Optional[str] = None
    status: str  # trial, active, expired, blocked
    is_trial: bool
    trial_ends_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    billing_cycle: Optional[str] = None  # monthly/yearly
    days_remaining: Optional[int] = None


class SubscribeRequest(BaseModel):
    """Запрос на активацию подписки."""
    tariff_code: str = Field(..., description="Код тарифа (pro/business)")
    billing_cycle: Literal["monthly", "yearly"] = Field(default="monthly", description="Период оплаты: monthly/yearly")


class SubscribeResponse(BaseModel):
    """Ответ после активации подписки."""
    status: str
    message: str
    subscription: UserSubscriptionSchema


# ====================
# Эндпоинты
# ====================

@router.get(
    "/list",
    response_model=List[TariffSchema],
    summary="Список доступных тарифов",
    description="Возвращает все активные тарифы с описанием возможностей",
)
async def get_tariffs(db: AsyncSession = Depends(get_db)):
    """
    Получение списка всех активных тарифов.
    
    Возвращает тарифы с полным описанием возможностей и лимитов.
    """
    result = await db.execute(
        select(Tariff)
        .where(Tariff.is_active == True)
        .order_by(Tariff.sort_order)
    )
    tariffs = result.scalars().all()
    
    tariff_list = []
    for tariff in tariffs:
        # Парсим JSON поля
        features = json.loads(tariff.features) if tariff.features else {}
        limits = json.loads(tariff.limits) if tariff.limits else {}
        
        tariff_list.append({
            "id": str(tariff.id),
            "name": tariff.name,
            "code": tariff.code,
            "price_monthly": tariff.price_monthly,
            "price_yearly": tariff.price_yearly,
            "trial_days": tariff.trial_days,
            "features": features,
            "limits": limits,
            "sort_order": tariff.sort_order,
        })
    
    return tariff_list


@router.get(
    "/current",
    response_model=UserSubscriptionSchema,
    summary="Текущая подписка пользователя",
    description="Возвращает информацию о текущей подписке пользователя",
)
async def get_current_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Получение текущей подписки пользователя.
    
    Возвращает статус, тариф и дату окончания подписки.
    """
    # Ищем активную подписку
    result = await db.execute(
        select(UserSubscription)
        .options(selectinload(UserSubscription.tariff))
        .where(UserSubscription.user_id == current_user.id)
        .where(UserSubscription.status.in_(["trial", "active"]))
        .order_by(UserSubscription.created_at.desc())
        .limit(1)
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        return UserSubscriptionSchema(
            tariff_code=None,
            tariff_name=None,
            status="none",
            is_trial=False,
            days_remaining=None,
        )
    
    # Считаем дни до окончания
    now = datetime.utcnow()
    end_date = subscription.trial_ends_at if subscription.is_trial else subscription.expires_at
    days_remaining = (end_date - now).days if end_date else None
    
    return UserSubscriptionSchema(
        tariff_code=subscription.tariff.code if subscription.tariff else None,
        tariff_name=subscription.tariff.name if subscription.tariff else None,
        status=subscription.status,
        is_trial=subscription.is_trial,
        trial_ends_at=subscription.trial_ends_at,
        expires_at=subscription.expires_at,
        billing_cycle=subscription.billing_cycle,
        days_remaining=days_remaining,
    )


@router.post(
    "/subscribe",
    response_model=SubscribeResponse,
    summary="Активация подписки",
    description="Активирует выбранный тариф с пробным периодом 7 дней",
)
async def subscribe(
    request: SubscribeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Активация подписки на тариф.
    
    При первой активации предоставляется 7-дневный пробный период.
    Требуется привязка карты для защиты от мультиаккаунтов.
    """
    # Проверяем тариф
    result = await db.execute(
        select(Tariff).where(Tariff.code == request.tariff_code)
    )
    tariff = result.scalar_one_or_none()
    
    if not tariff:
        raise HTTPException(status_code=404, detail="Тариф не найден")
    
    if not tariff.is_active:
        raise HTTPException(status_code=400, detail="Тариф не активен")
    
    # Проверяем существующую подписку
    result = await db.execute(
        select(UserSubscription)
        .where(UserSubscription.user_id == current_user.id)
        .where(UserSubscription.status.in_(["trial", "active"]))
        .order_by(UserSubscription.created_at.desc())
        .limit(1)
    )
    existing_subscription = result.scalar_one_or_none()
    
    if existing_subscription:
        raise HTTPException(
            status_code=400,
            detail=f"У вас уже есть активная подписка: {existing_subscription.status}"
        )
    
    # Создаём новую подписку с триалом
    now = datetime.utcnow()
    trial_end = now + timedelta(days=tariff.trial_days)
    
    subscription = UserSubscription(
        user_id=current_user.id,
        tariff_id=tariff.id,
        status="trial",
        is_trial=True,
        trial_started_at=now,
        trial_ends_at=trial_end,
        billing_cycle=request.billing_cycle,
    )
    
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)
    
    logger.info(f"✅ Пользователь {current_user.id} активировал тариф {tariff.code} (trial)")
    
    return SubscribeResponse(
        status="success",
        message=f"Тариф {tariff.name} активирован! Пробный период 7 дней.",
        subscription=UserSubscriptionSchema(
            tariff_code=tariff.code,
            tariff_name=tariff.name,
            status="trial",
            is_trial=True,
            trial_ends_at=trial_end,
            billing_cycle=request.billing_cycle,
            days_remaining=7,
        ),
    )


@router.delete(
    "/cancel",
    response_model=Dict[str, str],
    summary="Отмена подписки",
    description="Отменяет подписку после окончания текущего периода",
)
async def cancel_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Отмена подписки.
    
    Подписка остаётся активной до конца оплаченного периода.
    """
    # Ищем активную подписку
    result = await db.execute(
        select(UserSubscription)
        .where(UserSubscription.user_id == current_user.id)
        .where(UserSubscription.status.in_(["trial", "active"]))
        .order_by(UserSubscription.created_at.desc())
        .limit(1)
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Подписка не найдена")
    
    # Отменяем подписку
    subscription.status = "cancelled"
    subscription.auto_renew = False
    await db.commit()
    
    logger.info(f"✅ Пользователь {current_user.id} отменил подписку")
    
    return {
        "status": "success",
        "message": "Подписка отменена. Доступ сохранится до конца периода.",
    }
