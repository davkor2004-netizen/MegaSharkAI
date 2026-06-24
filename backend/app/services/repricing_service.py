"""
Сервис применения цен репрайсинга на маркетплейсах.

Здесь сосредоточена «опасная» часть репрайсинга — фактическая отправка цены
на площадку через её API. Используется и REST-эндпоинтом `/repricing/apply`,
и фоновой задачей ночного репрайсинга.
"""

from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.marketplace_key import marketplace_key_crud
from app.models.product import PriceHistory, Product
from app.models.user import User
from app.services.marketplace_api import marketplace_api_service
from app.services.notification_service import notification_service


async def apply_price_to_marketplace(
    db: AsyncSession,
    user: User,
    product: Product,
    new_price: float,
    reason: str = "",
    notify: bool = True,
) -> dict:
    """
    Отправить новую цену товара на маркетплейс и сохранить изменение в БД.

    Шаги:
    1. Проверяем глобальный «рубильник» применения цен.
    2. Находим активный API-ключ пользователя для маркетплейса товара.
    3. Расшифровываем ключ и дополнительные credentials.
    4. Вызываем API маркетплейса для обновления цены.
    5. При успехе обновляем цену в БД, пишем историю цен и уведомляем продавца.

    Returns:
        dict: {"status": "applied"|"error"|"disabled"|"no_key"|"not_supported", "message": str, ...}
    """
    if not settings.repricing_apply_enabled:
        return {
            "status": "disabled",
            "message": "Применение цен временно отключено администратором (REPRICING_APPLY_ENABLED=false)",
        }

    if new_price <= 0:
        return {"status": "error", "message": "Цена должна быть больше 0"}

    # Ищем ключ пользователя именно для маркетплейса этого товара.
    key = await marketplace_key_crud.get_key_by_marketplace(db, user.id, product.marketplace)
    if not key or not key.is_active:
        return {
            "status": "no_key",
            "message": f"Не найден активный API-ключ для маркетплейса {product.marketplace}",
        }

    if not product.external_id:
        return {
            "status": "error",
            "message": "У товара нет external_id (артикула на маркетплейсе)",
        }

    try:
        api_key = marketplace_key_crud.decrypt_key(key.api_key_encrypted)
        additional_credentials = marketplace_key_crud.decrypt_additional_credentials(
            key.additional_credentials_encrypted
        )
    except Exception as error:
        logger.error(f"❌ Не удалось расшифровать ключ маркетплейса: {error}")
        return {"status": "error", "message": "Не удалось расшифровать API-ключ маркетплейса"}

    old_price = float(product.price or 0)

    result = await marketplace_api_service.update_price(
        marketplace=product.marketplace,
        api_key=api_key,
        external_id=str(product.external_id),
        price=new_price,
        old_price=old_price or None,
        additional_credentials=additional_credentials,
    )

    if result.get("status") != "applied":
        return result

    # Фиксируем новую цену в БД и сохраняем историю.
    product.price = new_price
    product.last_parsed_at = datetime.utcnow()
    db.add(product)
    db.add(
        PriceHistory(
            product_id=product.id,
            price=new_price,
            old_price=old_price or None,
            discount=product.discount,
        )
    )
    await db.commit()
    await db.refresh(product)

    if notify:
        change_note = f" ({reason})" if reason else ""
        try:
            await notification_service.notify(
                db=db,
                user=user,
                title="Цена обновлена на маркетплейсе",
                message=(
                    f"Товар «{product.name[:80]}»: цена изменена "
                    f"с {int(old_price)} ₽ на {int(new_price)} ₽{change_note}."
                ),
                notification_type="price_change",
            )
        except Exception as error:
            logger.error(f"❌ Не удалось отправить уведомление о смене цены: {error}")

    return {
        "status": "applied",
        "message": result.get("message", "Цена применена"),
        "old_price": old_price,
        "new_price": new_price,
        "marketplace": product.marketplace,
    }
