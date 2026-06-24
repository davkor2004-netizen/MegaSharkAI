"""
Базовые модели и миксины для всех ORM-моделей.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime
from app.core.database import Base


class TimestampMixin:
    """
    Миксин с полями created_at и updated_at.
    
    Добавляется ко всем моделям для отслеживания времени создания и обновления.
    """
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


class BaseModel(Base, TimestampMixin):
    """
    Базовая модель с первичным ключом и временными метками.
    
    Все модели наследуются от этого класса.
    """
    __abstract__ = True
    
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True,
        comment="Уникальный идентификатор",
    )
    
    def __repr__(self) -> str:
        """Строковое представление модели для отладки."""
        return f"<{self.__class__.__name__}(id={self.id})>"
