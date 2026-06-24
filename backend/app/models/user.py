"""
Модель пользователя системы MegaSharkAI.
"""

from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.models.base import BaseModel


class User(BaseModel):
    """
    Модель пользователя (продавца на маркетплейсе).
    
    Атрибуты:
        id: Уникальный UUID пользователя
        email: Email для входа
        hashed_password: Хеш пароля
        full_name: Полное имя
        is_active: Активен ли аккаунт
        is_superuser: Права администратора
        marketplace_tokens: JSON с API-токенами для маркетплейсов
        settings: JSON с настройками пользователя
    """
    
    __tablename__ = "users"
    
    # Переопределяем id как UUID
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="Уникальный идентификатор (UUID)",
    )
    
    email = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Email пользователя",
    )
    
    hashed_password = Column(
        String(255),
        nullable=False,
        comment="Хеш пароля",
    )
    
    full_name = Column(
        String(255),
        nullable=True,
        comment="Полное имя",
    )

    phone = Column(
        String(32),
        nullable=True,
        comment="Телефон пользователя",
    )
    
    is_active = Column(
        Boolean,
        default=True,
        comment="Активен ли аккаунт",
    )
    
    is_superuser = Column(
        Boolean,
        default=False,
        comment="Права администратора",
    )
    
    is_marketplace_seller = Column(
        Boolean,
        default=False,
        comment="Является ли пользователь продавцом маркетплейса",
    )

    two_factor_enabled = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Включена ли двухфакторная аутентификация",
    )
    
    marketplace_api_key = Column(
        String(500),
        nullable=True,
        comment="API ключ продавца для интеграции с маркетплейсами",
    )
    
    marketplace_tokens = Column(
        String(1000),  # JSON как строка
        nullable=True,
        comment="API-токены для маркетплейсов (WB, Ozon и т.д.)",
    )
    
    settings = Column(
        String(2000),  # JSON как строка
        nullable=True,
        comment="Настройки пользователя",
    )
    
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="Время создания аккаунта",
    )
    
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="Время последнего обновления",
    )
    
    # Связь с подписками
    subscriptions = relationship(
        "UserSubscription",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="UserSubscription.user_id",
    )
    
    # Связь с API ключами маркетплейсов
    marketplace_keys = relationship(
        "MarketplaceKey",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    # Связь с чатами (как пользователь)
    chat_conversations = relationship(
        "ChatConversation",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="ChatConversation.user_id",
    )
    
    # Связь с чатами (как администратор, который отвечает)
    chat_conversations_admin = relationship(
        "ChatConversation",
        back_populates="admin",
        foreign_keys="ChatConversation.admin_id",
        lazy="selectin",
    )
    
    # Связь с сообщениями
    chat_messages = relationship(
        "ChatMessage",
        back_populates="sender",
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="ChatMessage.sender_id",
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"
