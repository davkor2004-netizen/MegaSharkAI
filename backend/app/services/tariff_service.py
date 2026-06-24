"""
Сервис для управления тарифами и подписками.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import json

from app.models.tariff import Tariff, UserSubscription
from app.models.user import User
from loguru import logger


class TariffService:
    """Сервис для работы с тарифами и подписками."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_tariff_by_code(self, code: str) -> Optional[Tariff]:
        """Получение тарифа по коду."""
        result = await self.db.execute(
            select(Tariff).where(Tariff.code == code)
        )
        return result.scalar_one_or_none()
    
    async def get_user_subscription(self, user_id: str) -> Optional[UserSubscription]:
        """Получение активной подписки пользователя."""
        result = await self.db.execute(
            select(UserSubscription)
            .options(selectinload(UserSubscription.tariff))
            .where(UserSubscription.user_id == user_id)
            .where(UserSubscription.status.in_(["trial", "active"]))
            .order_by(UserSubscription.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def check_trial_available(self, user_id: str) -> bool:
        """Проверка доступности пробного периода."""
        result = await self.db.execute(
            select(UserSubscription)
            .where(UserSubscription.user_id == user_id)
            .limit(1)
        )
        # Если подписок нет вообще — триал доступен
        return result.scalar_one_or_none() is None
    
    async def create_trial_subscription(
        self,
        user_id: str,
        tariff_id: str,
        trial_days: int = 7,
    ) -> UserSubscription:
        """Создание подписки с пробным периодом."""
        now = datetime.utcnow()
        trial_end = now + timedelta(days=trial_days)
        
        subscription = UserSubscription(
            user_id=user_id,
            tariff_id=tariff_id,
            status="trial",
            is_trial=True,
            trial_started_at=now,
            trial_ends_at=trial_end,
            billing_cycle="monthly",
        )
        
        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)
        
        logger.info(f"✅ Создан триал для пользователя {user_id} до {trial_end}")
        return subscription
    
    async def get_tariff_limits(self, tariff_code: str) -> Dict[str, Any]:
        """Получение лимитов тарифа."""
        tariff = await self.get_tariff_by_code(tariff_code)
        
        if not tariff:
            return {}
        
        return json.loads(tariff.limits) if tariff.limits else {}
    
    async def check_user_limits(
        self,
        user_id: str,
        limit_type: str,
        current_value: int,
    ) -> bool:
        """
        Проверка лимита пользователя.
        
        Args:
            user_id: ID пользователя
            limit_type: Тип лимита (max_products, ai_generations_per_month, etc.)
            current_value: Текущее значение
            
        Returns:
            bool: True если лимит не превышен
        """
        subscription = await self.get_user_subscription(user_id)
        
        if not subscription or not subscription.tariff:
            return False
        
        limits = json.loads(subscription.tariff.limits) if subscription.tariff.limits else {}
        max_value = limits.get(limit_type)
        
        if max_value is None:
            return True  # Лимит не установлен
        
        return current_value < max_value
    
    async def activate_paid_subscription(
        self,
        user_id: str,
        tariff_code: str,
        billing_cycle: Literal["monthly", "yearly"] = "monthly",
    ) -> UserSubscription:
        """Активация платной подписки после триала."""
        tariff = await self.get_tariff_by_code(tariff_code)
        
        if not tariff:
            raise ValueError(f"Тариф {tariff_code} не найден")
        
        now = datetime.utcnow()
        
        # Определяем дату окончания
        if billing_cycle == "yearly":
            expires_at = now + timedelta(days=365)
        else:
            expires_at = now + timedelta(days=30)
        
        subscription = UserSubscription(
            user_id=user_id,
            tariff_id=tariff.id,
            status="active",
            is_trial=False,
            started_at=now,
            expires_at=expires_at,
            billing_cycle=billing_cycle,
            auto_renew=True,
        )
        
        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)
        
        logger.info(f"✅ Активирована платная подписка для {user_id}")
        return subscription


# Глобальная функция для получения сервиса
_tariff_service_instance = None


def get_tariff_service(db: AsyncSession) -> TariffService:
    """Получение экземпляра TariffService."""
    return TariffService(db)
