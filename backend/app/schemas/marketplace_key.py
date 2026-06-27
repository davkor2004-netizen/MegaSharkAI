"""
Pydantic схемы для API ключей маркетплейсов.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List, Dict
from datetime import datetime
from uuid import UUID


class MarketplaceKeyCreate(BaseModel):
    """
    Схема для создания API ключа маркетплейса.
    """
    marketplace: str = Field(..., description="Название маркетплейса")
    api_key: str = Field(..., description="API ключ (будет зашифрован)")
    client_id: Optional[str] = Field(None, description="Client-Id для Ozon Seller API")
    is_active: bool = Field(default=True, description="Активен ли ключ")

    @field_validator("marketplace")
    @classmethod
    def normalize_marketplace(cls, value: str) -> str:
        """Нормализовать marketplace."""
        return value.strip().lower()

    @field_validator("api_key", "client_id")
    @classmethod
    def strip_secret_fields(cls, value: Optional[str]) -> Optional[str]:
        """Убрать случайные пробелы вокруг credentials."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class MarketplaceKeyUpdate(BaseModel):
    """
    Схема для обновления API ключа.
    """
    api_key: Optional[str] = Field(None, description="Новый API ключ")
    client_id: Optional[str] = Field(None, description="Новый Client-Id для Ozon")
    is_active: Optional[bool] = Field(None, description="Активен ли ключ")


class MarketplaceKeyResponse(BaseModel):
    """
    Схема ответа с данными ключа.
    """
    id: UUID
    marketplace: str
    api_key_masked: str  # Замаскированный ключ (последние 4 символа)
    additional_credentials_masked: Dict[str, str] = Field(default_factory=dict)
    is_active: bool
    is_valid: Optional[bool]
    last_checked: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class MarketplaceKeyCheckResponse(BaseModel):
    """
    Схема ответа при проверке ключа.
    """
    is_valid: bool
    message: str


class MarketplaceKeysList(BaseModel):
    """
    Список ключей маркетплейсов.
    """
    keys: List[MarketplaceKeyResponse]
    total: int
