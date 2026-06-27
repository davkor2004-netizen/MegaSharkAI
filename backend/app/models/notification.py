"""
Модели для уведомлений и настроек.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.datetime_utils import utcnow

from app.models.base import BaseModel


class Notification(BaseModel):
    """
    Уведомление для пользователя.
    
    Типы уведомлений:
    - price_change: Изменение цены конкурента
    - low_stock: Заканчиваются остатки
    - report_ready: Отчёт готов
    - competitor_analysis: AI-анализ конкурентов
    - system: Системные уведомления
    """
    
    __tablename__ = "notifications"
    
    id = Column(
        Integer,
        primary_key=True,
        index=True,
        comment="ID уведомления",
    )
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID пользователя",
    )
    
    title = Column(
        String(255),
        nullable=False,
        comment="Заголовок уведомления",
    )
    
    message = Column(
        Text,
        nullable=False,
        comment="Текст уведомления",
    )
    
    type = Column(
        String(50),
        nullable=False,
        default="system",
        comment="Тип уведомления",
    )
    
    is_read = Column(
        Boolean,
        default=False,
        index=True,
        comment="Прочитано ли уведомление",
    )
    
    created_at = Column(
        DateTime,
        default=utcnow,
        nullable=False,
        index=True,
        comment="Время создания",
    )
    
    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, title='{self.title}', type='{self.type}')>"


class UserSettings(BaseModel):
    """
    Настройки пользователя.
    
    Хранит:
    - Стратегия репрайсинга
    - Целевая маржа
    - Уведомления (email, telegram)
    - Рабочее время для ночного репрайсинга
    """
    
    __tablename__ = "user_settings"
    
    id = Column(
        Integer,
        primary_key=True,
        index=True,
        comment="ID настроек",
    )
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="ID пользователя",
    )
    
    # Репрайсинг
    repricing_strategy = Column(
        String(50),
        default="margin_protection",  # aggressive, margin, night
        comment="Стратегия репрайсинга",
    )
    
    target_margin = Column(
        Float,
        default=30.0,
        comment="Целевая маржа в процентах",
    )
    
    min_price = Column(
        Float,
        nullable=True,
        comment="Минимальная цена товара",
    )
    
    max_price = Column(
        Float,
        nullable=True,
        comment="Максимальная цена товара",
    )
    
    # Уведомления
    email_notifications = Column(
        Boolean,
        default=True,
        comment="Email уведомления",
    )
    
    telegram_notifications = Column(
        Boolean,
        default=False,
        comment="Telegram уведомления",
    )
    
    telegram_chat_id = Column(
        String(100),
        nullable=True,
        comment="Telegram chat ID",
    )
    
    # Ночной репрайсинг
    night_repricing_enabled = Column(
        Boolean,
        default=False,
        comment="Включить ночной репрайсинг",
    )
    
    night_repricing_start = Column(
        String(5),
        default="23:00",
        comment="Время начала (HH:MM)",
    )
    
    night_repricing_end = Column(
        String(5),
        default="06:00",
        comment="Время окончания (HH:MM)",
    )
    
    # Автоматическое обновление
    auto_update_enabled = Column(
        Boolean,
        default=True,
        comment="Автообновление цен",
    )
    
    auto_update_interval = Column(
        Integer,
        default=3600,  # 1 час
        comment="Интервал в секундах",
    )
    
    updated_at = Column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
        comment="Время обновления",
    )
    
    def __repr__(self) -> str:
        return f"<UserSettings(user_id={self.user_id}, strategy='{self.repricing_strategy}')>"


class SaleCalendar(BaseModel):
    """
    Календарь распродаж и акций.
    
    Хранит даты распродаж на маркетплейсах.
    """
    
    __tablename__ = "sale_calendar"
    
    id = Column(
        Integer,
        primary_key=True,
        index=True,
        comment="ID события",
    )
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="ID пользователя (None для общих событий)",
    )
    
    title = Column(
        String(255),
        nullable=False,
        comment="Название события",
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Описание события",
    )
    
    marketplace = Column(
        String(50),
        nullable=True,
        comment="Маркетплейс (WB, Ozon и т.д.)",
    )
    
    event_type = Column(
        String(50),
        default="sale",  # sale, promotion, holiday
        comment="Тип события",
    )
    
    start_date = Column(
        DateTime,
        nullable=False,
        comment="Дата начала",
    )
    
    end_date = Column(
        DateTime,
        nullable=False,
        comment="Дата окончания",
    )
    
    is_global = Column(
        Boolean,
        default=False,
        comment="Глобальное событие (для всех)",
    )
    
    discount_percent = Column(
        Float,
        nullable=True,
        comment="Ожидаемый процент скидки",
    )
    
    notes = Column(
        Text,
        nullable=True,
        comment="Заметки пользователя",
    )
    
    created_at = Column(
        DateTime,
        default=utcnow,
        nullable=False,
        comment="Время создания",
    )
    
    def __repr__(self) -> str:
        return f"<SaleCalendar(id={self.id}, title='{self.title}')>"