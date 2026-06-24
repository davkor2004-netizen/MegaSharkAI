"""
Эндпоинты для парсинга маркетплейсов.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
import asyncio

from app.core.database import get_db
from app.models.product import Product, PriceHistory
from app.models.user import User
from app.services.auth_service import get_current_user, get_current_superuser
from app.services.limits import enforce_volume_limit
from app.services.marketplace_api import marketplace_api_service
from app.crud.marketplace_key import marketplace_key_crud
from app.services.parser import ParserError
from app.services.proxy_pool import get_proxy, get_proxy_stats
from app.services.parser import MarketplaceParser

router = APIRouter()


class ParseRequest(BaseModel):
    """Запрос на парсинг товара."""
    url: str
    is_competitor: bool = True


class ParseResponse(BaseModel):
    """Ответ после парсинга."""
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None


class MyProductsRequest(BaseModel):
    """Запрос на получение своих товаров через API."""
    marketplace: str = "wildberries"
    product_id: Optional[str] = None


class MyProductsResponse(BaseModel):
    """Ответ со списком товаров."""
    status: str
    message: str
    data: Optional[List[Dict[str, Any]]] = None
    total: int = 0


@router.post(
    "/parse-url",
    response_model=ParseResponse,
    summary="Парсинг товара по URL",
    description="Парсит данные о товаре с любого поддерживаемого маркетплейса",
)
async def parse_url(
    request: ParseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Парсинг товара по URL.
    
    Автоматически определяет маркетплейс по URL.
    Использует ротацию прокси для обхода блокировок.
    
    **Поддерживаемые маркетплейсы:**
    - Wildberries (wildberries.ru, wb.ru)
    - Ozon (ozon.ru)
    - Яндекс Маркет (market.yandex.ru)
    - Avito (avito.ru)
    """
    logger.info(f"🕷️ Парсинг URL: {request.url}, user_id={current_user.id}")
    
    try:
        # Инициализируем единый экземпляр парсера для всех попыток.
        parser = MarketplaceParser()
        validated_url = parser.validate_product_url(request.url)

        # Для WB и Ozon пробуем с ротацией прокси (до 3 попыток)
        max_attempts = 3

        # Жёсткие лимиты времени:
        # 1) timeout для браузерного page.goto внутри парсера (мс)
        # 2) абсолютный лимит на всю попытку (сек), включая fallback-источники
        parser_timeout_ms = 90_000
        attempt_deadline_seconds = 95

        last_error = None
        proxy = None
        data: Optional[Dict[str, Any]] = None
        
        for attempt in range(max_attempts):
            try:
                # Получаем прокси из пула (с ротацией)
                proxy = get_proxy(strategy="random" if attempt > 0 else "least_used")
                proxy_url = proxy.proxy_url if proxy else None
                
                # Для WB и Ozon пробуем БЕЗ прокси в последней попытке
                if 'wildberries' in validated_url.lower() or 'wb.ru' in validated_url.lower():
                    if attempt == max_attempts - 1:
                        logger.warning(f"⚠️ WB попытка {attempt + 1}/{max_attempts} БЕЗ прокси")
                        proxy_url = None
                    else:
                        logger.info(f"🔹 WB попытка {attempt + 1}/{max_attempts} с прокси: {proxy.ip if proxy else 'None'}")
                elif 'ozon.ru' in validated_url.lower():
                    if attempt == max_attempts - 1:
                        logger.warning(f"⚠️ Ozon попытка {attempt + 1}/{max_attempts} БЕЗ прокси")
                        proxy_url = None
                    else:
                        logger.info(f"🔹 Ozon попытка {attempt + 1}/{max_attempts} с прокси: {proxy.ip if proxy else 'None'}")
                else:
                    logger.info(f"🔹 Используем прокси: {proxy.ip if proxy else 'None'}")
                
                # Парсим URL с двумя ограничителями времени:
                # - внутренний timeout Playwright/page.goto
                # - внешний абсолютный timeout на всю попытку
                data = await asyncio.wait_for(
                    parser.parse_url(validated_url, proxy_url, timeout=parser_timeout_ms),
                    timeout=attempt_deadline_seconds,
                )
                
                # Если получили валидный результат (полный или частичный) — выходим из цикла.
                # Для WB price может временно отсутствовать из-за антибота/таймаутов,
                # но при этом name/external_id уже пригодны для сохранения и отображения.
                if data and isinstance(data, dict):
                    # Для partial-результата без цены продолжаем ротацию прокси,
                    # чтобы повысить шанс получить полноценные данные на следующих попытках.
                    if data.get('price') is None and attempt < max_attempts - 1:
                        logger.warning(
                            f"⚠️ Попытка {attempt + 1}: partial WB/Ozon результат без цены, пробуем следующую прокси"
                        )
                        if proxy:
                            proxy.mark_error()
                        await asyncio.sleep(1)
                        continue

                    if proxy:
                        proxy.mark_success()
                    break
                    
            except asyncio.TimeoutError:
                last_error = ParserError(
                    f"Превышено время попытки парсинга ({attempt_deadline_seconds} сек)"
                )
                logger.warning(
                    f"⚠️ Попытка {attempt + 1} прервана по общему таймауту {attempt_deadline_seconds} сек"
                )
                if proxy:
                    proxy.mark_error()
                if attempt < max_attempts - 1:
                    await asyncio.sleep(1)
                continue

            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ Попытка {attempt + 1} не удалась: {e}")
                if proxy:
                    proxy.mark_error()
                if attempt < max_attempts - 1:
                    await asyncio.sleep(1)  # Пауза перед следующей попыткой
                continue
        else:
            # Все попытки не удались
            if last_error:
                raise last_error
        
        # Проверка валидности результата:
        # допускаем частичный парсинг (например, есть name, но нет price),
        # чтобы не отдавать 400 при реальных данных под антибот-защитой.
        # Важный момент: parse_url уже выставляет fallback name, поэтому здесь
        # проверяем только полную пустоту данных как защиту от некорректного ответа.
        if not data or not isinstance(data, dict):
            logger.warning("⚠️ Парсер вернул пустой/невалидный ответ")
            raise ParserError("Маркетплейс не вернул данные товара")

        if data.get('price') is not None and data.get('price', 0) > 1000000:
            logger.warning(f"⚠️ Неадекватная цена: {data.get('price')}")
            raise ParserError("Маркетплейс вернул некорректную цену")
        
        # Защитная нормализация: 0 и отрицательные значения цены считаем
        # отсутствующей ценой, чтобы UI не показывал вводящий в заблуждение "0 ₽".
        if data.get('price') is not None:
            try:
                if int(data.get('price')) <= 0:
                    data['price'] = None
            except (TypeError, ValueError):
                data['price'] = None
        
        # Если прокси сработал хорошо - помечаем как успех
        if proxy and proxy_url:
            proxy.mark_success()
        
        # ВАЖНО: если текущий парсинг вернул частичный результат без цены,
        # не затираем существующую цену в БД (если она уже была получена ранее).
        existing_product = None
        marketplace = data.get('marketplace', 'unknown')
        external_id = data.get('external_id') or parser.extract_external_id(validated_url, marketplace)
        if external_id:
            existing_stmt = select(Product).where(
                Product.user_id == current_user.id,
                Product.marketplace == marketplace,
                Product.external_id == str(external_id),
            )
            existing_result = await db.execute(existing_stmt)
            existing_product = existing_result.scalar_one_or_none()
        
            if data.get('price') is None and existing_product and existing_product.price is not None:
                data['price'] = existing_product.price
                if data.get('old_price') is None:
                    data['old_price'] = existing_product.old_price
                if data.get('discount') in (None, 0) and existing_product.discount is not None:
                    data['discount'] = existing_product.discount
                if not data.get('warning'):
                    data['warning'] = 'Актуальные данные WB частично недоступны, использована последняя сохранённая цена.'
        
        now = datetime.utcnow()
        
        # Определяем marketplace/external_id для UPSERT.
        # Если выше уже вычислили external_id, используем его.
        marketplace = data.get('marketplace', 'unknown')
        external_id = external_id or data.get('external_id') or parser.extract_external_id(validated_url, marketplace)
        if not external_id:
            external_id = data.get('name', 'unknown')[:50]
        
        product_values = {
            "name": data.get('name', 'Unknown'),
            "price": data.get('price'),
            "old_price": data.get('old_price'),
            "discount": data.get('discount', 0),
            "rating": data.get('rating'),
            "reviews_count": data.get('reviews_count'),
            "sales_count": data.get('sales_count') if data.get('sales_count') is not None else data.get('sales_per_day'),
            "brand": data.get('brand'),
            "category": data.get('category'),
            "is_competitor": request.is_competitor,
            "url": validated_url,
            "last_parsed_at": now,
        }

        if existing_product:
            for field, value in product_values.items():
                setattr(existing_product, field, value)
            product = existing_product
        else:
            # Enforcement лимита тарифа на количество товаров в мониторинге.
            current_products_count = await db.scalar(
                select(func.count(Product.id)).where(Product.user_id == current_user.id)
            )
            await enforce_volume_limit(
                db, current_user.id, "max_products", current_products_count or 0
            )

            product = Product(
                user_id=current_user.id,
                external_id=str(external_id),
                marketplace=marketplace,
                **product_values,
            )
            db.add(product)
            await db.flush()

        if product.price is not None and product.price > 0:
            latest_history_result = await db.execute(
                select(PriceHistory)
                .where(PriceHistory.product_id == product.id)
                .order_by(PriceHistory.created_at.desc())
                .limit(1)
            )
            latest_history = latest_history_result.scalar_one_or_none()

            price_changed = (
                latest_history is None
                or latest_history.price != product.price
                or latest_history.old_price != product.old_price
                or latest_history.discount != product.discount
            )

            if price_changed:
                db.add(PriceHistory(
                    product_id=product.id,
                    price=product.price,
                    old_price=product.old_price,
                    discount=product.discount,
                ))

        await db.commit()

        logger.info(f"✅ Товар распарсен и сохранён: {data.get('name', 'Unknown')[:50]}...")
        
        return ParseResponse(
            status="success",
            message=f"Товар успешно распарсен",
            data=data,
        )
    
    except ParserError as e:
        logger.error(f"❌ Ошибка парсинга: {e}")
        
        # Помечаем прокси как проблемный
        proxy = get_proxy(strategy="least_used")
        if proxy:
            proxy.mark_error()
        
        # Возвращаем явную ошибку вместо демо-данных,
        # чтобы в систему не попадали подменённые результаты.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка парсинга: {str(e)}"
        )

    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка парсинга: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка: {str(e)}"
        )


@router.post(
    "/my-products",
    response_model=MyProductsResponse,
    summary="Получение своих товаров через API",
    description="Получает данные о товарах продавца через API маркетплейса",
)
async def get_my_products(
    request: MyProductsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получение своих товаров через API маркетплейса.
    
    Для администраторов: работает в демо-режиме без API ключа.
    """
    logger.info(f"📦 Запрос товаров через API: marketplace={request.marketplace}, user_id={current_user.id}, is_superuser={current_user.is_superuser}")
    
    # Для администраторов - демо режим
    if current_user.is_superuser:
        logger.info("🔑 Администратор - использую демо-данные")
        
        # Демо-данные для теста
        demo_products = [
            {
                "product_id": "12345678",
                "name": f"Демо товар {request.marketplace}",
                "price": 1999,
                "old_price": 2999,
                "discount": 33,
                "stock": 100,
                "category": "Тестовая категория",
                "brand": "Демо бренд",
                "rating": 4.5,
                "reviews_count": 150,
                "url": f"https://{request.marketplace}.ru/product/12345678",
            },
            {
                "product_id": "87654321",
                "name": f"Товар 2 {request.marketplace}",
                "price": 3499,
                "old_price": 4999,
                "discount": 30,
                "stock": 50,
                "category": "Тестовая категория 2",
                "brand": "Демо бренд 2",
                "rating": 4.8,
                "reviews_count": 320,
                "url": f"https://{request.marketplace}.ru/product/87654321",
            },
        ]
        
        return MyProductsResponse(
            status="success",
            message=f"Демо режим для администратора: {len(demo_products)} товаров",
            data=demo_products,
            total=len(demo_products)
        )
        
    # Для обычных пользователей - проверка API ключа
    api_key_record = await marketplace_key_crud.get_key_by_marketplace(
        db, current_user.id, request.marketplace
    )
    
    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API ключ для {request.marketplace} не подключён. Добавьте его в профиле."
        )

    if not api_key_record.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API ключ для {request.marketplace} не активен"
        )

    # Дешифруем ключ
    api_key = marketplace_key_crud.decrypt_key(api_key_record.api_key_encrypted)
    additional_credentials = marketplace_key_crud.decrypt_additional_credentials(
        api_key_record.additional_credentials_encrypted
    )
    
    try:
        # Получаем товары через API
        if request.marketplace == "wildberries":
            products = await marketplace_api_service.get_wildberries_products(api_key, request.product_id)
        elif request.marketplace == "ozon":
            products = await marketplace_api_service.get_ozon_products(
                api_key,
                request.product_id,
                additional_credentials=additional_credentials,
            )
        elif request.marketplace == "yandex_market":
            products = await marketplace_api_service.get_yandex_products(api_key, request.product_id)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Маркетплейс {request.marketplace} не поддерживается"
            )
        
        return MyProductsResponse(
            status="success",
            message=f"Получено {len(products)} товаров",
            data=products,
            total=len(products)
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения товаров: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении товаров: {str(e)}"
        )


@router.get(
    "/proxy-stats",
    summary="Статистика прокси",
    description="Показывает статус и использование пула прокси (только админ)",
)
async def get_proxy_statistics(
    current_user: User = Depends(get_current_superuser),
):
    """
    Получить статистику использования прокси.
    """
    _ = current_user
    stats = get_proxy_stats()
    return {
        "status": "success",
        "data": stats
    }


@router.get(
    "/test-parser",
    summary="Тест парсера",
    description="Проверяет работу парсера на тестовом URL (только админ)",
)
async def test_parser(
    current_user: User = Depends(get_current_superuser),
):
    """
    Тест парсера.
    """
    _ = current_user
    # Тестовый URL WB
    test_url = "https://www.wildberries.ru/catalog/24319630/detail.aspx"
    
    try:
        proxy = get_proxy(strategy="random")
        proxy_url = proxy.proxy_url if proxy else None
        
        parser = MarketplaceParser()
        data = await parser.parse_url(test_url, proxy_url)
        
        return {
            "status": "success",
            "message": "Парсер работает",
            "data": data,
            "proxy_used": proxy.ip if proxy else None,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }
