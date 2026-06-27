"""
Модель для хранения API ключей маркетплейсов.
Каждый ключ шифруется перед сохранением.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.datetime_utils import utcnow
from app.models.base import BaseModel


class MarketplaceKey(BaseModel):
    """
    Модель API ключа маркетплейса.
    
    Атрибуты:
        id: Уникальный UUID записи
        user_id: UUID пользователя (владелец ключа)
        marketplace: Название маркетплейса (wildberries, ozon, yandex_market, avito)
        api_key: Зашифрованный API ключ
        is_active: Активен ли ключ
        last_checked: Время последней проверки ключа
        is_valid: Валиден ли ключ (результат последней проверки)
    """
    
    __tablename__ = "marketplace_keys"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="Уникальный идентификатор записи",
    )
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="UUID пользователя",
    )
    
    marketplace = Column(
        String(50),
        nullable=False,
        comment="Название маркетплейса",
    )
    
    api_key_encrypted = Column(
        Text,
        nullable=False,
        comment="Зашифрованный API ключ",
    )

    additional_credentials_encrypted = Column(
        Text,
        nullable=True,
        comment="Зашифрованные дополнительные credentials маркетплейса",
    )
    
    is_active = Column(
        Boolean,
        default=True,
        comment="Активен ли ключ",
    )
    
    last_checked = Column(
        DateTime,
        nullable=True,
        comment="Время последней проверки ключа",
    )
    
    is_valid = Column(
        Boolean,
        nullable=True,
        comment="Валиден ли ключ (результат последней проверки)",
    )
    
    created_at = Column(
        DateTime,
        default=utcnow,
        nullable=False,
        comment="Время создания записи",
    )
    
    updated_at = Column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
        comment="Время последнего обновления",
    )
    
    # Связь с пользователем
    user = relationship(
        "User",
        back_populates="marketplace_keys",
        lazy="selectin",
    )
    
    def __repr__(self) -> str:
        return f"<MarketplaceKey(id={self.id}, marketplace='{self.marketplace}', user_id={self.user_id})>"
