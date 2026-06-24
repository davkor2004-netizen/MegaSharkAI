"""
Эндпоинты для уведомлений и пользовательских настроек уведомлений.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from loguru import logger

from app.core.database import get_db
from app.models.user import User
from app.models.notification import Notification, UserSettings
from app.api.v1.auth import get_current_user
from app.services.notification_service import notification_service

router = APIRouter()


class NotificationSettingsRequest(BaseModel):
    """Тело запроса для сохранения настроек уведомлений."""

    email_notifications: bool = Field(default=True, description="Включены ли email-уведомления")
    telegram_notifications: bool = Field(default=False, description="Включены ли telegram-уведомления")
    telegram_chat_id: str | None = Field(default=None, description="Telegram Chat ID")

    @field_validator("telegram_chat_id")
    @classmethod
    def validate_telegram_chat_id(cls, value: str | None) -> str | None:
        """Нормализуем telegram_chat_id и убираем пустые значения."""
        if value is None:
            return None

        normalized_value = value.strip()
        if normalized_value == "":
            return None

        if len(normalized_value) > 100:
            raise ValueError("Telegram Chat ID слишком длинный")

        return normalized_value

    @model_validator(mode="after")
    def validate_telegram_settings(self):
        """Telegram-уведомления нельзя включить без chat_id."""
        if self.telegram_notifications and not self.telegram_chat_id:
            raise ValueError("Для Telegram-уведомлений укажите Telegram Chat ID")
        return self


async def get_or_create_user_settings(db: AsyncSession, user_id) -> UserSettings:
    """Получить настройки пользователя или создать запись с дефолтными значениями."""
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings = result.scalar_one_or_none()

    if settings:
        return settings

    settings = UserSettings(user_id=user_id)
    db.add(settings)
    await db.commit()
    await db.refresh(settings)
    return settings
    

@router.get(
    "/",
    summary="Список уведомлений",
    description="Получение списка уведомлений для текущего пользователя",
)
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    unread_only: bool = False,
):
    """
    Получение списка уведомлений.
    """
    logger.info(f"🔔 Запрос уведомлений: user_id={current_user.id}, limit={limit}, unread_only={unread_only}")

    query = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )

    if unread_only:
        query = query.where(Notification.is_read.is_(False))

    result = await db.execute(query)
    notifications = result.scalars().all()

    return [
        {
            "id": notification.id,
            "title": notification.title,
            "message": notification.message,
            "type": notification.type,
            "is_read": notification.is_read,
            "created_at": notification.created_at.isoformat() if notification.created_at else None,
        }
        for notification in notifications
    ]


@router.post(
    "/mark-read/{notification_id}",
    summary="Пометить уведомление прочитанным",
    description="Отметить конкретное уведомление как прочитанное",
)
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Пометить уведомление как прочитанное.
    """
    logger.info(f"✅ Пометить уведомление {notification_id} как прочитанное: user_id={current_user.id}")

    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")

    notification.is_read = True
    await db.commit()

    return {"status": "success"}


@router.post(
    "/mark-all-read",
    summary="Пометить все уведомления прочитанными",
    description="Отметить все уведомления текущего пользователя как прочитанные",
)
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Пометить все уведомления как прочитанные.
    """
    logger.info(f"✅ Пометить все уведомления как прочитанные: user_id={current_user.id}")

    await db.execute(
        update(Notification)
        .values(is_read=True)
        .where(Notification.user_id == current_user.id)
    )
    await db.commit()

    return {"status": "success"}


@router.get(
    "/unread-count",
    summary="Количество непрочитанных уведомлений",
    description="Получение количества непрочитанных уведомлений текущего пользователя",
)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Получение количества непрочитанных уведомлений.
    """
    logger.info(f"📊 Запрос количества непрочитанных: user_id={current_user.id}")

    query = (
        select(func.count(Notification.id))
        .where(Notification.is_read.is_(False))
        .where(Notification.user_id == current_user.id)
    )
    result = await db.execute(query)
    count = result.scalar() or 0
    
    return {"unread_count": count}


@router.post(
    "/test",
    summary="Тестовое уведомление",
    description="Отправляет тестовое уведомление по всем включённым каналам (in-app, email, Telegram)",
)
async def send_test_notification(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Отправить тестовое уведомление текущему пользователю.

    Помогает продавцу проверить, что email/Telegram действительно настроены
    и сообщения доходят.
    """
    settings_row = await get_or_create_user_settings(db, current_user.id)

    await notification_service.notify(
        db=db,
        user=current_user,
        title="Проверка уведомлений",
        message=(
            "Это тестовое уведомление MegaSharkAI. "
            "Если вы видите его в нужных каналах — доставка настроена корректно."
        ),
        notification_type="system",
    )

    return {
        "status": "success",
        "channels": {
            "in_app": True,
            "email": bool(settings_row.email_notifications and current_user.email),
            "telegram": bool(
                settings_row.telegram_notifications and settings_row.telegram_chat_id
            ),
        },
    }


@router.get(
    "/settings",
    summary="Получение настроек уведомлений",
    description="Возвращает настройки email/telegram уведомлений текущего пользователя",
)
async def get_notification_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получение настроек уведомлений текущего пользователя."""
    settings = await get_or_create_user_settings(db, current_user.id)

    return {
        "email_notifications": settings.email_notifications,
        "telegram_notifications": settings.telegram_notifications,
        "telegram_chat_id": settings.telegram_chat_id,
    }


@router.post(
    "/settings",
    summary="Сохранение настроек уведомлений",
    description="Сохраняет настройки email/telegram уведомлений текущего пользователя",
)
async def save_notification_settings(
    payload: NotificationSettingsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Сохранение настроек уведомлений текущего пользователя."""
    settings = await get_or_create_user_settings(db, current_user.id)

    settings.email_notifications = payload.email_notifications
    settings.telegram_notifications = payload.telegram_notifications
    settings.telegram_chat_id = payload.telegram_chat_id if payload.telegram_notifications else None

    await db.commit()
    await db.refresh(settings)

    return {
        "status": "success",
        "email_notifications": settings.email_notifications,
        "telegram_notifications": settings.telegram_notifications,
        "telegram_chat_id": settings.telegram_chat_id,
    }
