"""
Схемы Pydantic для пользователя.
"""

from pydantic import BaseModel, EmailStr, Field, field_serializer, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime


from app.schemas.validators import validate_password_strength


class UserBase(BaseModel):
    """Базовая схема пользователя."""
    
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """Схема для создания пользователя."""
    
    password: str = Field(..., min_length=8, description="Пароль (минимум 8 символов)")
    is_marketplace_seller: bool = Field(False, description="Является ли пользователь продавцом маркетплейса")
    marketplace_api_key: Optional[str] = Field(None, description="API ключ продавца для интеграции с маркетплейсами")

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return validate_password_strength(value)


class UserUpdate(BaseModel):
    """Схема для обновления пользователя."""
    
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6)
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    settings: Optional[dict] = None
    marketplace_tokens: Optional[dict] = None


class UserResponse(UserBase):
    """Схема ответа с данными пользователя."""
    
    id: UUID
    is_active: bool
    is_superuser: bool
    is_marketplace_seller: bool = False
    phone: Optional[str] = None
    marketplace_api_key: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("marketplace_api_key")
    @classmethod
    def mask_marketplace_api_key(cls, value: Optional[str]) -> Optional[str]:
        """Не отдаём API-ключ целиком в JSON."""
        if not value:
            return None
        if len(value) <= 8:
            return "***"
        return f"{value[:4]}...{value[-4:]}"
    
    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """Схема для входа пользователя."""
    
    email: EmailStr
    password: str


class Token(BaseModel):
    """Схема токена доступа."""
    
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None
    is_superuser: bool = False


class TokenData(BaseModel):
    """Схема данных токена."""
    
    email: Optional[str] = None
    user_id: Optional[UUID] = None
    is_superuser: Optional[bool] = None
