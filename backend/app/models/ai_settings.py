"""
Модель настроек AI.
"""

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from app.models.base import Base


class AISettings(Base):
    """Настройки AI-провайдеров."""
    
    __tablename__ = "ai_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Yandex GPT
    yandex_api_key = Column(String, nullable=True)
    yandex_folder_id = Column(String, nullable=True)
    
    # DeepSeek
    deepseek_api_key = Column(String, nullable=True)
    
    # OpenAI
    openai_api_key = Column(String, nullable=True)
    
    # Текущий провайдер
    current_provider = Column(String, default="none")
    
    # Дата обновления
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
