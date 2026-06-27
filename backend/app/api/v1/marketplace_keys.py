"""
API для управления ключами маркетплейсов.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from loguru import logger
from datetime import datetime

from app.core.database import get_db
from app.core.datetime_utils import utcnow
from app.services.auth_service import get_current_user
from app.models.user import User
from app.schemas.marketplace_key import (
    MarketplaceKeyCreate,
    MarketplaceKeyResponse,
    MarketplaceKeyCheckResponse,
    MarketplaceKeysList,
)
from app.crud.marketplace_key import marketplace_key_crud
from app.services.marketplace_api import marketplace_api_service
from app.services import feature_access


router = APIRouter(prefix="/marketplace-keys", tags=["Маркетплейсы"])


def build_additional_credentials(key_data: MarketplaceKeyCreate) -> dict:
    """Собрать marketplace-specific credentials из запроса."""
    credentials = {}
    if key_data.marketplace == "ozon" and key_data.client_id:
        credentials["client_id"] = key_data.client_id
    return credentials


def to_key_response(key) -> MarketplaceKeyResponse:
    """Преобразовать ORM-запись в безопасный response без раскрытия секретов."""
    decrypted_key = marketplace_key_crud.decrypt_key(key.api_key_encrypted)
    additional_credentials = marketplace_key_crud.decrypt_additional_credentials(
        key.additional_credentials_encrypted
    )

    return MarketplaceKeyResponse(
        id=key.id,
        marketplace=key.marketplace,
        api_key_masked=marketplace_key_crud.mask_key(decrypted_key),
        additional_credentials_masked=marketplace_key_crud.mask_additional_credentials(additional_credentials),
        is_active=key.is_active,
        is_valid=key.is_valid,
        last_checked=key.last_checked,
        created_at=key.created_at,
        updated_at=key.updated_at,
    )


@router.get("", response_model=MarketplaceKeysList)
async def get_marketplace_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить все ключи маркетплейсов текущего пользователя.
    
    Returns:
        Список ключей с замаскированными значениями
    """
    keys = await marketplace_key_crud.get_keys_by_user(db, current_user.id)
    
    response_keys = [to_key_response(key) for key in keys]
    
    return {"keys": response_keys, "total": len(response_keys)}


@router.post("", response_model=MarketplaceKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_marketplace_key(
    key_data: MarketplaceKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Добавить новый ключ маркетплейса.
    
    - **marketplace**: Название маркетплейса (wildberries, ozon, yandex_market, avito)
    - **api_key**: API ключ (будет зашифрован)
    """
    if key_data.marketplace == "ozon" and not key_data.client_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Для Ozon Seller API требуется Client-Id",
        )

    additional_credentials = build_additional_credentials(key_data)

    # Проверяем, есть ли уже ключ для этого маркетплейса
    existing_key = await marketplace_key_crud.get_key_by_marketplace(
        db, current_user.id, key_data.marketplace
    )
    
    if existing_key:
        # Обновляем существующий ключ
        logger.info(f"Обновление ключа для {key_data.marketplace}")
        
        # Проверяем валидность ключа
        is_valid = await marketplace_api_service.check_api_key(
            key_data.marketplace,
            key_data.api_key,
            additional_credentials=additional_credentials,
        )
        
        updated_key = await marketplace_key_crud.update_key(
            db,
            existing_key.id,
            api_key=key_data.api_key,
            additional_credentials=additional_credentials,
            is_active=key_data.is_active,
            is_valid=is_valid,
            last_checked=utcnow()
        )

        return to_key_response(updated_key)
    else:
        # Создаём новый ключ
        logger.info(f"Создание ключа для {key_data.marketplace}")

        # Лимит тарифа на количество ключей маркетплейсов.
        await feature_access.enforce_volume(db, current_user.id, "marketplace_keys")

        # Проверяем валидность ключа
        is_valid = await marketplace_api_service.check_api_key(
            key_data.marketplace,
            key_data.api_key,
            additional_credentials=additional_credentials,
        )
        
        new_key = await marketplace_key_crud.create_key(
            db,
            current_user.id,
            key_data.marketplace,
            key_data.api_key,
            key_data.is_active,
            additional_credentials=additional_credentials,
        )
        
        # Обновляем статус валидности
        checked_key = await marketplace_key_crud.update_key(
            db,
            new_key.id,
            is_valid=is_valid,
            last_checked=utcnow()
        )
        
        return to_key_response(checked_key)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_marketplace_key(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Удалить ключ маркетплейса.
    """
    key = await marketplace_key_crud.get_key_by_id(db, key_id)
    
    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ключ не найден"
        )
    
    # Проверяем, что ключ принадлежит пользователю
    if key.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет прав на удаление этого ключа"
        )
    
    await marketplace_key_crud.delete_key(db, key_id)
    
    return None


@router.post("/{key_id}/check", response_model=MarketplaceKeyCheckResponse)
async def check_marketplace_key(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Проверить валидность ключа маркетплейса.
    """
    key = await marketplace_key_crud.get_key_by_id(db, key_id)
    
    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ключ не найден"
        )
    
    # Проверяем, что ключ принадлежит пользователю
    if key.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет прав на проверку этого ключа"
        )
    
    # Дешифруем ключ
    api_key = marketplace_key_crud.decrypt_key(key.api_key_encrypted)
    additional_credentials = marketplace_key_crud.decrypt_additional_credentials(
        key.additional_credentials_encrypted
    )
    
    # Проверяем через API
    is_valid = await marketplace_api_service.check_api_key(
        key.marketplace,
        api_key,
        additional_credentials=additional_credentials,
    )
    
    # Обновляем статус
    await marketplace_key_crud.update_key(
        db,
        key_id,
        is_valid=is_valid,
        last_checked=utcnow()
    )
    
    return {
        "is_valid": is_valid,
        "message": "Ключ валиден" if is_valid else "Ключ недействителен"
    }
