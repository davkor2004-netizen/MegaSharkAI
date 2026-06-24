"""
Эндпоинты для репрайсинга (автоматического расчёта цен).
"""

from typing import Literal

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.core.database import get_db
from app.models.product import Product
from app.models.user import User
from app.models.notification import UserSettings
from app.api.v1.auth import get_current_user
from app.services.repricing_service import apply_price_to_marketplace

router = APIRouter()

# Разрешённые стратегии репрайсинга.
RepricingStrategy = Literal["aggressive", "margin_protection", "night", "balanced"]

# Человекочитаемые названия стратегий для ответа API.
STRATEGY_LABELS: dict[RepricingStrategy, str] = {
    "aggressive": "Агрессивный рост",
    "margin_protection": "Защита маржи",
    "night": "Ночной",
    "balanced": "Сбалансированная",
}


class RepricingCalculateRequest(BaseModel):
    """Тело запроса для расчёта цены."""

    product_id: int = Field(..., gt=0, description="ID товара")
    strategy: RepricingStrategy = Field(
        default="margin_protection",
        description="Стратегия расчёта",
    )
    target_margin: float = Field(
        default=30.0,
        ge=0,
        le=100,
        description="Целевая маржа в процентах",
    )
    competitor_prices: list[float] | None = Field(
        default=None,
        max_length=100,
        description="Необязательный список цен конкурентов",
    )

    @field_validator("competitor_prices")
    @classmethod
    def validate_competitor_prices(cls, value: list[float] | None):
        """Проверяем, что цены конкурентов корректные и положительные."""
        if value is None:
            return value

        if len(value) == 0:
            return None

        for price in value:
            if price <= 0:
                raise ValueError("Все цены конкурентов должны быть больше 0")

        return value


class RepricingSettingsRequest(BaseModel):
    """Тело запроса для сохранения пользовательских настроек репрайсинга."""

    strategy: RepricingStrategy = Field(
        ...,
        description="Стратегия репрайсинга по умолчанию",
    )
    target_margin: float = Field(
        default=30.0,
        ge=0,
        le=100,
        description="Целевая маржа в процентах",
    )
    night_repricing_enabled: bool = Field(
        default=False,
        description="Включён ли ночной репрайсинг",
    )
    auto_update_enabled: bool = Field(
        default=True,
        description="Включено ли автообновление цен",
    )


def round_to_pretty_market_price(raw_price: float) -> float:
    """
    Округлить цену к удобному «маркетплейсному» виду.

    Правило:
    - округляем к десяткам;
    - вычитаем 1, чтобы получить вид вроде 1999.
    """
    rounded = round(raw_price / 10) * 10 - 1
    return float(max(rounded, 100))


def calculate_recommended_price(
    *,
    current_price: float,
    strategy: RepricingStrategy,
    target_margin: float,
    competitor_prices: list[float] | None,
) -> tuple[float, str, str]:
    """
    Рассчитать рекомендованную цену и пояснение по формуле.

    Возвращает кортеж:
    - рекомендованная цена до финального округления;
    - источник данных (competitors / fallback_current_price);
    - человекочитаемое объяснение.
    """
    # Если есть валидные данные конкурентов — считаем от них.
    if competitor_prices:
        min_competitor = min(competitor_prices)
        avg_competitor = sum(competitor_prices) / len(competitor_prices)

        if strategy == "aggressive":
            calculated = min_competitor * 0.95
            return (
                calculated,
                "competitors",
                "Агрессивная стратегия: 95% от минимальной цены конкурента",
            )

        if strategy == "margin_protection":
            calculated = avg_competitor * (1 + target_margin / 100)
            return (
                calculated,
                "competitors",
                "Защита маржи: средняя цена конкурентов + целевая маржа",
            )

        if strategy == "night":
            calculated = current_price * 0.90
            return (
                calculated,
                "mixed",
                "Ночная стратегия: 90% от текущей цены",
            )

        # balanced
        calculated = (avg_competitor + min_competitor) / 2
        return (
            calculated,
            "competitors",
            "Сбалансированная стратегия: среднее между min и avg ценой конкурентов",
        )

    # Fallback без конкурентных данных.
    if current_price <= 0:
        raise HTTPException(
            status_code=400,
            detail="Невозможно рассчитать цену: у товара отсутствует текущая цена и нет данных конкурентов",
        )

    if strategy == "night":
        return (
            current_price * 0.90,
            "fallback_current_price",
            "Ночная стратегия без конкурентов: 90% от текущей цены",
        )

    # Для остальных стратегий без конкурентов не меняем цену, чтобы не вносить шум.
    return (
        current_price,
        "fallback_current_price",
        "Нет данных конкурентов: оставляем текущую цену без изменений",
    )


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


async def get_auto_competitor_prices(
    db: AsyncSession,
    current_user: User,
    product: Product,
) -> list[float]:
    """
    Автоматически подобрать цены конкурентов из БД.

    Логика подбора идёт от более точного совпадения к более общему:
    1) same marketplace + same category + same brand;
    2) same marketplace + same category;
    3) same marketplace.

    Берём только товары-конкуренты текущего пользователя с валидной ценой.
    """
    # Общая база фильтров для всех шагов.
    base_filters = [
        Product.user_id == current_user.id,
        Product.is_competitor == True,
        Product.price.isnot(None),
        Product.price > 0,
        Product.marketplace == product.marketplace,
    ]

    # Сценарии уточнения, расположены по приоритету.
    filter_scenarios: list[list] = []

    if product.category and product.brand:
        filter_scenarios.append([
            Product.category == product.category,
            Product.brand == product.brand,
        ])

    if product.category:
        filter_scenarios.append([
            Product.category == product.category,
        ])

    # Самый общий fallback: только по маркетплейсу.
    filter_scenarios.append([])

    for scenario_filters in filter_scenarios:
        query = (
            select(Product.price)
            .where(*base_filters, *scenario_filters)
            .limit(100)
        )
        result = await db.execute(query)
        prices = [float(price) for price in result.scalars().all() if price is not None and price > 0]

        if prices:
            return prices

    return []


@router.post(
    "/calculate",
    summary="Расчёт оптимальной цены",
    description="Расчёт рекомендованной цены на основе стратегии",
)
async def calculate_optimal_price(
    payload: RepricingCalculateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Расчёт оптимальной цены для товара текущего пользователя.

    Важно:
    - доступен только владельцу товара;
    - учитывает выбранную стратегию и ограничения.
    """
    logger.info(
        f"💰 Расчёт цены: user_id={current_user.id}, product_id={payload.product_id}, strategy={payload.strategy}"
    )

    # Получаем товар ТОЛЬКО текущего пользователя.
    result = await db.execute(
        select(Product).where(
            Product.id == payload.product_id,
            Product.user_id == current_user.id,
        )
    )
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    if product.is_competitor:
        raise HTTPException(
            status_code=400,
            detail="Репрайсинг доступен только для собственных товаров, а не для карточек конкурентов",
        )

    current_price = float(product.price or 0)

    # Если цены конкурентов не переданы вручную, пытаемся подобрать их автоматически.
    competitor_prices = payload.competitor_prices
    auto_loaded_competitor_prices = False
    if not competitor_prices:
        competitor_prices = await get_auto_competitor_prices(db, current_user, product)
        auto_loaded_competitor_prices = len(competitor_prices) > 0

    raw_recommended_price, data_source, reasoning = calculate_recommended_price(
        current_price=current_price,
        strategy=payload.strategy,
        target_margin=payload.target_margin,
        competitor_prices=competitor_prices,
    )

    # Дополнительное ограничение: если есть старая цена, не выходим выше 95% от неё.
    if product.old_price and product.old_price > 0:
        raw_recommended_price = min(raw_recommended_price, float(product.old_price) * 0.95)

    # Финальное округление к виду X...9.
    recommended_price = round_to_pretty_market_price(raw_recommended_price)

    competitor_count = len(competitor_prices) if competitor_prices else 0
    min_competitor_price = min(competitor_prices) if competitor_prices else None
    avg_competitor_price = (
        sum(competitor_prices) / len(competitor_prices)
        if competitor_prices
        else None
    )

    change_percent = 0.0
    if current_price > 0:
        change_percent = round(((recommended_price - current_price) / current_price) * 100, 2)

    return {
        "product_id": payload.product_id,
        "product_name": product.name,
        "current_price": current_price,
        "recommended_price": recommended_price,
        "strategy": STRATEGY_LABELS[payload.strategy],
        "strategy_code": payload.strategy,
        "target_margin": payload.target_margin,
        "competitor_count": competitor_count,
        "min_competitor_price": min_competitor_price,
        "avg_competitor_price": avg_competitor_price,
        "change_percent": change_percent,
        "data_source": data_source,
        "reasoning": reasoning,
        "competitor_prices_source": "manual" if payload.competitor_prices else ("auto" if auto_loaded_competitor_prices else "none"),
    }


class RepricingApplyRequest(BaseModel):
    """Тело запроса для применения цены на маркетплейсе."""

    product_id: int = Field(..., gt=0, description="ID товара")
    # Если задана manual_price — применяем её напрямую (с проверкой границ).
    manual_price: float | None = Field(
        default=None,
        gt=0,
        le=10_000_000,
        description="Явная цена. Если не задана — рассчитываем по стратегии",
    )
    strategy: RepricingStrategy = Field(default="margin_protection")
    target_margin: float = Field(default=30.0, ge=0, le=100)
    competitor_prices: list[float] | None = Field(default=None, max_length=100)


@router.post(
    "/apply",
    summary="Применить цену на маркетплейсе",
    description="Рассчитывает (или принимает) цену и отправляет её на маркетплейс через API",
)
async def apply_optimal_price(
    payload: RepricingApplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Применить новую цену товара на маркетплейсе.

    В отличие от `/calculate`, этот эндпоинт реально отправляет цену на площадку
    через её API (нужен сохранённый и активный ключ маркетплейса).
    """
    logger.info(
        f"💸 Применение цены: user_id={current_user.id}, product_id={payload.product_id}, strategy={payload.strategy}"
    )

    result = await db.execute(
        select(Product).where(
            Product.id == payload.product_id,
            Product.user_id == current_user.id,
        )
    )
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    if product.is_competitor:
        raise HTTPException(
            status_code=400,
            detail="Репрайсинг доступен только для собственных товаров",
        )

    # 1. Определяем целевую цену: либо ручная, либо расчёт по стратегии.
    if payload.manual_price is not None:
        target_price = round_to_pretty_market_price(payload.manual_price)
        reasoning = "Ручная цена"
    else:
        current_price = float(product.price or 0)
        competitor_prices = payload.competitor_prices
        if not competitor_prices:
            competitor_prices = await get_auto_competitor_prices(db, current_user, product)

        raw_price, _data_source, reasoning = calculate_recommended_price(
            current_price=current_price,
            strategy=payload.strategy,
            target_margin=payload.target_margin,
            competitor_prices=competitor_prices,
        )
        target_price = round_to_pretty_market_price(raw_price)

    # 2. Отправляем цену на маркетплейс через сервис.
    apply_result = await apply_price_to_marketplace(
        db=db,
        user=current_user,
        product=product,
        new_price=target_price,
        reason=STRATEGY_LABELS.get(payload.strategy, reasoning),
    )

    status_to_http = {
        "no_key": 400,
        "not_supported": 400,
        "disabled": 409,
        "error": 502,
    }
    if apply_result.get("status") != "applied":
        raise HTTPException(
            status_code=status_to_http.get(apply_result.get("status"), 400),
            detail=apply_result.get("message", "Не удалось применить цену"),
        )

    return {
        "status": "applied",
        "product_id": product.id,
        "product_name": product.name,
        "applied_price": target_price,
        "reasoning": reasoning,
        **apply_result,
    }


@router.post(
    "/strategies",
    summary="Сохранить стратегию репрайсинга",
    description="Настройка стратегии для текущего пользователя",
)
async def save_repricing_strategy(
    payload: RepricingSettingsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Сохранение настроек репрайсинга для текущего пользователя.
    """
    logger.info(
        f"⚙️ Сохранение стратегии: user_id={current_user.id}, strategy={payload.strategy}, margin={payload.target_margin}%"
    )

    settings = await get_or_create_user_settings(db, current_user.id)
    settings.repricing_strategy = payload.strategy
    settings.target_margin = payload.target_margin
    settings.night_repricing_enabled = payload.night_repricing_enabled
    settings.auto_update_enabled = payload.auto_update_enabled

    await db.commit()
    await db.refresh(settings)

    return {
        "status": "success",
        "strategy": settings.repricing_strategy,
        "target_margin": settings.target_margin,
        "night_repricing_enabled": settings.night_repricing_enabled,
        "auto_update_enabled": settings.auto_update_enabled,
        "message": "Стратегия сохранена",
    }


@router.get(
    "/strategies",
    summary="Получить стратегию репрайсинга",
    description="Получение текущей стратегии пользователя",
)
async def get_repricing_strategy(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Получение текущих настроек репрайсинга.
    """
    settings = await get_or_create_user_settings(db, current_user.id)

    return {
        "strategy": settings.repricing_strategy,
        "target_margin": settings.target_margin,
        "night_repricing_enabled": settings.night_repricing_enabled,
        "auto_update_enabled": settings.auto_update_enabled,
    }