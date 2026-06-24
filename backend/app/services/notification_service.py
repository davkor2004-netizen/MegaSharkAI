"""
Сервис доставки уведомлений.

Единая точка отправки уведомлений пользователю по всем каналам:
1. Запись в БД (таблица notifications) — всегда.
2. Email — если у пользователя включены email-уведомления и настроен SMTP.
3. Telegram — если включены telegram-уведомления, указан chat_id и настроен бот.

Сервис не бросает исключения наружу: ошибка одного канала не должна
ломать бизнес-логику (репрайсинг, отчёты, парсинг и т.д.).
"""

import asyncio
from typing import Optional

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.notification import Notification, UserSettings
from app.models.user import User
from app.services.email import EmailService


async def send_telegram_message(chat_id: str, text: str) -> bool:
    """
    Отправить сообщение в Telegram через Bot API.

    Args:
        chat_id: ID чата получателя (пользователь берёт его у @userinfobot)
        text: Текст сообщения

    Returns:
        bool: True если сообщение принято Telegram
    """
    token = settings.telegram_bot_token
    if not token:
        logger.warning("⚠️ Telegram-бот не настроен (TELEGRAM_BOT_TOKEN пуст)")
        return False

    if not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)

        if response.status_code == 200:
            logger.info(f"✅ Telegram-уведомление отправлено: chat_id={chat_id}")
            return True

        logger.error(
            f"❌ Telegram API вернул статус {response.status_code} для chat_id={chat_id}"
        )
        return False
    except Exception as error:
        logger.error(f"❌ Ошибка отправки Telegram-уведомления: {error}")
        return False


class NotificationService:
    """Сервис создания и доставки уведомлений."""

    def __init__(self):
        # Используем те же SMTP-настройки, что и остальное приложение.
        self.email_service = EmailService(
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_user=settings.smtp_user,
            smtp_password=settings.smtp_password,
            from_email=settings.from_email,
            use_tls=settings.use_tls,
        )

    async def _get_settings(self, db: AsyncSession, user_id) -> Optional[UserSettings]:
        """Получить настройки уведомлений пользователя (или None)."""
        result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        return result.scalar_one_or_none()

    def _build_email_html(self, title: str, message: str) -> str:
        """Простой адаптивный HTML-шаблон письма-уведомления."""
        return f"""
        <!DOCTYPE html>
        <html lang="ru">
        <head><meta charset="UTF-8"></head>
        <body style="font-family: Arial, sans-serif; color: #1e293b; padding: 16px;">
            <h2 style="margin: 0 0 12px;">{title}</h2>
            <p style="font-size: 15px; line-height: 1.5;">{message}</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">
            <p style="font-size: 12px; color: #64748b;">
                MegaSharkAI — AI-ассистент для продавцов маркетплейсов.<br>
                Управлять уведомлениями можно в настройках личного кабинета.
            </p>
        </body>
        </html>
        """

    async def notify(
        self,
        db: AsyncSession,
        user: User,
        title: str,
        message: str,
        notification_type: str = "system",
        send_email: bool = True,
        send_telegram: bool = True,
    ) -> Notification:
        """
        Создать уведомление и доставить его по доступным каналам.

        Args:
            db: Сессия БД
            user: Пользователь-получатель
            title: Заголовок
            message: Текст
            notification_type: Тип (price_change/report_ready/system и т.д.)
            send_email: Разрешить email-канал (если включён у пользователя)
            send_telegram: Разрешить telegram-канал (если включён у пользователя)

        Returns:
            Notification: созданная запись уведомления
        """
        # 1. Всегда сохраняем уведомление в БД — это «колокольчик» в кабинете.
        notification = Notification(
            user_id=user.id,
            title=title,
            message=message,
            type=notification_type,
            is_read=False,
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)

        # 2. Подтягиваем настройки каналов пользователя.
        user_settings = await self._get_settings(db, user.id)

        # 3. Email-канал (блокирующий smtplib выносим в отдельный поток).
        if (
            send_email
            and user_settings is not None
            and user_settings.email_notifications
            and getattr(user, "email", None)
        ):
            try:
                await asyncio.to_thread(
                    self.email_service.send_email,
                    user.email,
                    f"MegaSharkAI: {title}",
                    self._build_email_html(title, message),
                    message,
                )
            except Exception as error:
                logger.error(f"❌ Не удалось отправить email-уведомление: {error}")

        # 4. Telegram-канал.
        if (
            send_telegram
            and user_settings is not None
            and user_settings.telegram_notifications
            and user_settings.telegram_chat_id
        ):
            telegram_text = f"<b>{title}</b>\n\n{message}"
            await send_telegram_message(user_settings.telegram_chat_id, telegram_text)

        return notification


# Глобальный экземпляр сервиса.
notification_service = NotificationService()
