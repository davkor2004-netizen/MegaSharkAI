"""
Модели тарифов и подписок MegaSharkAI.
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.models.base import BaseModel


class Tariff(BaseModel):
    """
    Модель тарифного плана.
    
    Атрибуты:
        id: Уникальный идентификатор
        name: Название тарифа (Pro, Business)
        code: Код тарифа (pro, business)
        price_monthly: Цена в рублях в месяц
        price_yearly: Цена в рублях в год (со скидкой 20%)
        trial_days: Длительность пробного периода (7 дней)
        is_active: Активен ли тариф для продажи
        
        Лимиты (JSON):
        - max_products: макс. товаров в мониторинге
        - max_repricing_products: макс. товаров на репрайсинге
        - ai_generations_per_month: лимит AI-генераций
        - ai_analyst_questions: лимит вопросов AI-аналитику
        - competitor_reports: лимит отчётов по конкурентам
        - price_update_frequency: частота обновления (4/сутки или 24/сутки)
        - excel_import: импорт через Excel (true/false)
        - excel_mass_update: массовое обновление (true/false)
        - api_access: доступ к API
        - widget_access: доступ к виджету
        - photo_analysis: анализ качества фото
        - forecast_months: прогноз распродаж (мес)
        - custom_repricing: кастомные правила репрайсинга
        - max_users: макс. пользователей в аккаунте
        - support_priority: приоритет поддержки (standard/priority)
        
        features: JSON со списком возможностей для отображения
        sort_order: Порядок отображения
    """
    
    __tablename__ = "tariffs"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="Уникальный идентификатор тарифа",
    )
    
    name = Column(
        String(100),
        nullable=False,
        comment="Название тарифа (Pro, Business)",
    )
    
    code = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Код тарифа (pro, business)",
    )
    
    price_monthly = Column(
        Float,
        default=0.0,
        nullable=False,
        comment="Цена в рублях в месяц",
    )
    
    price_yearly = Column(
        Float,
        default=0.0,
        nullable=False,
        comment="Цена в рублях в год (со скидкой)",
    )
    
    trial_days = Column(
        Integer,
        default=7,
        nullable=False,
        comment="Длительность пробного периода в днях",
    )
    
    is_active = Column(
        Boolean,
        default=True,
        comment="Активен ли тариф для продажи",
    )
    
    # Лимиты тарифа (JSON строка)
    limits = Column(
        Text,
        nullable=True,
        comment="JSON с лимитами тарифа",
    )
    
    # Список возможностей для отображения (JSON строка)
    features = Column(
        Text,
        nullable=True,
        comment="JSON со списком возможностей",
    )
    
    sort_order = Column(
        Integer,
        default=0,
        comment="Порядок отображения (меньше = выше)",
    )
    
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="Время создания тарифа",
    )
    
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="Время последнего обновления",
    )
    
    def __repr__(self) -> str:
        return f"<Tariff(code='{self.code}', price={self.price_monthly})>"


class UserSubscription(BaseModel):
    """
    Модель подписки пользователя на тариф.
    
    Атрибуты:
        id: Уникальный идентификатор подписки
        user_id: ID пользователя
        tariff_id: ID тарифа
        status: Статус подписки
        is_trial: Активен ли пробный период
        trial_started_at: Дата начала триала
        trial_ends_at: Дата окончания триала
        started_at: Дата начала платной подписки
        expires_at: Дата окончания подписки
        auto_renew: Автопродление
        payment_method: Способ оплаты
        billing_cycle: Период оплаты (monthly/yearly)
    """
    
    __tablename__ = "user_subscriptions"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="Уникальный идентификатор подписки",
    )
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID пользователя",
    )
    
    tariff_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tariffs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="ID тарифа",
    )
    
    status = Column(
        String(50),
        default="trial",  # trial, active, cancelled, expired, blocked
        nullable=False,
        index=True,
        comment="Статус: trial, active, cancelled, expired, blocked",
    )
    
    # Trial
    is_trial = Column(
        Boolean,
        default=True,
        comment="Активен ли пробный период",
    )
    
    trial_started_at = Column(
        DateTime,
        nullable=True,
        comment="Дата начала триала",
    )
    
    trial_ends_at = Column(
        DateTime,
        nullable=True,
        comment="Дата окончания триала (через 7 дней)",
    )
    
    # Платная подписка
    started_at = Column(
        DateTime,
        nullable=True,
        comment="Дата начала платной подписки",
    )
    
    expires_at = Column(
        DateTime,
        nullable=True,
        comment="Дата окончания подписки",
    )
    
    auto_renew = Column(
        Boolean,
        default=False,
        comment="Автопродление подписки",
    )
    
    billing_cycle = Column(
        String(20),
        default="monthly",  # monthly или yearly
        nullable=False,
        comment="Период оплаты: monthly/yearly",
    )
    
    payment_method = Column(
        String(50),
        nullable=True,
        comment="Способ оплаты (card, sbp, invoice)",
    )
    
    # Для истории
    previous_tariff_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tariffs.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID предыдущего тарифа (для истории)",
    )
    
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="Время создания записи",
    )
    
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="Время последнего обновления",
    )
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")
    tariff = relationship("Tariff", foreign_keys=[tariff_id])
    previous_tariff = relationship("Tariff", foreign_keys=[previous_tariff_id])
    
    def __repr__(self) -> str:
        return f"<UserSubscription(user_id={self.user_id}, status='{self.status}')>"


# Добавим relationship в модель User
# Это нужно сделать в app/models/user.py
# from sqlalchemy.orm import relationship
# subscriptions = relationship(
#     "UserSubscription",
#     back_populates="user",
#     cascade="all, delete-orphan",
#     lazy="selectin"
# )
