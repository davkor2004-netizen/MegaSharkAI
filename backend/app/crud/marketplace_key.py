"""
CRUD операции для API ключей маркетплейсов.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import json

from app.models.marketplace_key import MarketplaceKey
from app.services.encryption import encryption_service


class MarketplaceKeyCRUD:
    """
    CRUD операции для MarketplaceKey.
    """
    
    async def get_keys_by_user(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> List[MarketplaceKey]:
        """
        Получить все ключи пользователя.
        
        Args:
            db: Сессия БД
            user_id: UUID пользователя
            
        Returns:
            Список ключей
        """
        result = await db.execute(
            select(MarketplaceKey)
            .where(MarketplaceKey.user_id == user_id)
            .order_by(MarketplaceKey.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_key_by_id(
        self,
        db: AsyncSession,
        key_id: UUID
    ) -> Optional[MarketplaceKey]:
        """
        Получить ключ по ID.
        
        Args:
            db: Сессия БД
            key_id: UUID ключа
            
        Returns:
            Ключ или None
        """
        result = await db.execute(
            select(MarketplaceKey)
            .where(MarketplaceKey.id == key_id)
        )
        return result.scalar_one_or_none()
    
    async def get_key_by_marketplace(
        self,
        db: AsyncSession,
        user_id: UUID,
        marketplace: str
    ) -> Optional[MarketplaceKey]:
        """
        Получить ключ для конкретного маркетплейса.
        
        Args:
            db: Сессия БД
            user_id: UUID пользователя
            marketplace: Название маркетплейса
            
        Returns:
            Ключ или None
        """
        result = await db.execute(
            select(MarketplaceKey)
            .where(
                MarketplaceKey.user_id == user_id,
                MarketplaceKey.marketplace == marketplace
            )
        )
        return result.scalar_one_or_none()
    
    async def create_key(
        self,
        db: AsyncSession,
        user_id: UUID,
        marketplace: str,
        api_key: str,
        is_active: bool = True,
        additional_credentials: Optional[dict] = None,
    ) -> MarketplaceKey:
        """
        Создать новый ключ.
        
        Args:
            db: Сессия БД
            user_id: UUID пользователя
            marketplace: Название маркетплейса
            api_key: API ключ (будет зашифрован)
            is_active: Активен ли ключ
            
        Returns:
            Созданный ключ
        """
        # Шифруем ключ
        encrypted_key = encryption_service.encrypt(api_key)
        encrypted_additional_credentials = self.encrypt_additional_credentials(additional_credentials)
        
        db_key = MarketplaceKey(
            user_id=user_id,
            marketplace=marketplace,
            api_key_encrypted=encrypted_key,
            additional_credentials_encrypted=encrypted_additional_credentials,
            is_active=is_active,
        )
        
        db.add(db_key)
        await db.commit()
        await db.refresh(db_key)
        
        return db_key
    
    async def update_key(
        self,
        db: AsyncSession,
        key_id: UUID,
        api_key: Optional[str] = None,
        additional_credentials: Optional[dict] = None,
        is_active: Optional[bool] = None,
        is_valid: Optional[bool] = None,
        last_checked: Optional[datetime] = None
    ) -> Optional[MarketplaceKey]:
        """
        Обновить ключ.
        
        Args:
            db: Сессия БД
            key_id: UUID ключа
            api_key: Новый API ключ (опционально)
            is_active: Активен ли ключ
            is_valid: Валиден ли ключ
            last_checked: Время последней проверки
            
        Returns:
            Обновлённый ключ или None
        """
        db_key = await self.get_key_by_id(db, key_id)
        if not db_key:
            return None
        
        if api_key is not None:
            db_key.api_key_encrypted = encryption_service.encrypt(api_key)

        if additional_credentials is not None:
            db_key.additional_credentials_encrypted = self.encrypt_additional_credentials(additional_credentials)
        
        if is_active is not None:
            db_key.is_active = is_active
        
        if is_valid is not None:
            db_key.is_valid = is_valid
        
        if last_checked is not None:
            db_key.last_checked = last_checked
        
        await db.commit()
        await db.refresh(db_key)
        
        return db_key
    
    async def delete_key(
        self,
        db: AsyncSession,
        key_id: UUID
    ) -> bool:
        """
        Удалить ключ.
        
        Args:
            db: Сессия БД
            key_id: UUID ключа
            
        Returns:
            True если удалён
        """
        db_key = await self.get_key_by_id(db, key_id)
        if not db_key:
            return False
        
        await db.delete(db_key)
        await db.commit()
        
        return True
    
    def mask_key(self, key: str) -> str:
        """
        Замаскировать ключ для отображения.
        
        Args:
            key: API ключ
            
        Returns:
            Замаскированный ключ
        """
        if not key:
            return ""
        
        if len(key) <= 8:
            return "*" * len(key)
        
        # Показываем первые 2 и последние 4 символа
        return f"{key[:2]}{'*' * (len(key) - 6)}{key[-4:]}"
    
    def decrypt_key(self, encrypted_key: str) -> str:
        """
        Расшифровать ключ.
        
        Args:
            encrypted_key: Зашифрованный ключ
            
        Returns:
            Расшифрованный ключ
        """
        return encryption_service.decrypt(encrypted_key)

    def encrypt_additional_credentials(self, credentials: Optional[dict]) -> Optional[str]:
        """Зашифровать дополнительные credentials маркетплейса."""
        if not credentials:
            return None

        sanitized = {
            key: str(value).strip()
            for key, value in credentials.items()
            if value is not None and str(value).strip()
        }
        if not sanitized:
            return None

        return encryption_service.encrypt(json.dumps(sanitized, ensure_ascii=False))

    def decrypt_additional_credentials(self, encrypted_credentials: Optional[str]) -> dict:
        """Расшифровать дополнительные credentials маркетплейса."""
        if not encrypted_credentials:
            return {}

        decrypted = encryption_service.decrypt(encrypted_credentials)
        if not decrypted:
            return {}

        try:
            parsed = json.loads(decrypted)
        except json.JSONDecodeError:
            return {}

        return parsed if isinstance(parsed, dict) else {}

    def mask_additional_credentials(self, credentials: dict) -> dict:
        """Замаскировать дополнительные credentials для ответа API."""
        return {
            key: self.mask_key(str(value))
            for key, value in credentials.items()
            if value
        }


# Глобальный экземпляр
marketplace_key_crud = MarketplaceKeyCRUD()
