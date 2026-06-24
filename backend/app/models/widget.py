"""
Модель конфигурации встраиваемого виджета (MegaShark-ассистент на сайте продавца).

Виджет — платная фича тарифа (limits.widget_access = true). Продавец получает
публичный ключ и код вставки; на своём сайте показывает AI-ассистента.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class WidgetConfig(BaseModel):
    """
    Настройки виджета для одного аккаунта продавца.

    Поля:
        user_id: владелец виджета
        public_key: публичный ключ для кода вставки (не секрет)
        is_enabled: включён ли виджет
        title: заголовок окна виджета
        welcome_message: приветственное сообщение ассистента
        accent_color: цвет акцента (hex)
        allowed_origins: список доменов через запятую (пусто = любые)
    """

    __tablename__ = "widget_configs"

    id = Column(Integer, primary_key=True, index=True, comment="ID конфигурации")

    user_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
        comment="ID владельца виджета",
    )

    public_key = Column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="Публичный ключ виджета (для кода вставки)",
    )

    is_enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Включён ли виджет",
    )

    title = Column(
        String(120),
        default="Помощник магазина",
        nullable=False,
        comment="Заголовок окна виджета",
    )

    welcome_message = Column(
        Text,
        default="Здравствуйте! Я помогу выбрать товар и отвечу на вопросы.",
        nullable=False,
        comment="Приветственное сообщение",
    )

    accent_color = Column(
        String(9),
        default="#6d28d9",
        nullable=False,
        comment="Цвет акцента (hex)",
    )

    allowed_origins = Column(
        Text,
        nullable=True,
        comment="Разрешённые домены через запятую (пусто = любые)",
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="Время создания",
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="Время обновления",
    )

    def __repr__(self) -> str:
        return f"<WidgetConfig(user_id={self.user_id}, enabled={self.is_enabled})>"
