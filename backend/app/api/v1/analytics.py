"""
Эндпоинты внутренней аналитики кабинета.

Включает:
- калькулятор юнит-экономики (P&L на единицу товара);
- ABC-анализ ассортимента по выручке;
- оценку продаж конкурента (эвристика по отзывам и истории цен).
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.product import PriceHistory, Product
from app.models.user import User
from app.api.v1.auth import get_current_user

router = APIRouter()


class UnitEconomicsRequest(BaseModel):
    """Входные данные для расчёта юнит-экономики."""
    price: float = Field(..., gt=0, description="Цена продажи, ₽")
    cost_price: float = Field(..., ge=0, description="Себестоимость закупки, ₽")
    commission_percent: float = Field(default=15.0, ge=0, le=100, description="Комиссия маркетплейса, %")
    logistics: float = Field(default=0.0, ge=0, description="Логистика на единицу, ₽")
    storage: float = Field(default=0.0, ge=0, description="Хранение на единицу, ₽")
    other_costs: float = Field(default=0.0, ge=0, description="Прочие расходы на единицу, ₽")
    tax_percent: float = Field(default=6.0, ge=0, le=100, description="Налог, % от цены")
    buyout_percent: float = Field(default=100.0, gt=0, le=100, description="Процент выкупа, %")


@router.post(
    "/unit-economics",
    summary="Калькулятор юнит-экономики",
    description="Считает прибыль и маржу на единицу товара с учётом комиссий, логистики и выкупа",
)
async def calculate_unit_economics(
    payload: UnitEconomicsRequest,
    current_user: User = Depends(get_current_user),
):
    """Рассчитать P&L на единицу товара."""
    commission = payload.price * payload.commission_percent / 100
    tax = payload.price * payload.tax_percent / 100

    # Учитываем невыкуп: логистика обычно платится и за возвраты.
    buyout_ratio = payload.buyout_percent / 100
    logistics_effective = payload.logistics / buyout_ratio if buyout_ratio > 0 else payload.logistics

    total_costs = (
        payload.cost_price
        + commission
        + logistics_effective
        + payload.storage
        + payload.other_costs
        + tax
    )
    profit = payload.price - total_costs
    margin_percent = round(profit / payload.price * 100, 2) if payload.price > 0 else 0.0
    markup_percent = round(profit / payload.cost_price * 100, 2) if payload.cost_price > 0 else None

    return {
        "price": round(payload.price, 2),
        "total_costs": round(total_costs, 2),
        "breakdown": {
            "cost_price": round(payload.cost_price, 2),
            "commission": round(commission, 2),
            "logistics_effective": round(logistics_effective, 2),
            "storage": round(payload.storage, 2),
            "tax": round(tax, 2),
            "other_costs": round(payload.other_costs, 2),
        },
        "profit_per_unit": round(profit, 2),
        "margin_percent": margin_percent,
        "markup_percent": markup_percent,
        "is_profitable": profit > 0,
    }


@router.get(
    "/abc",
    summary="ABC-анализ ассортимента",
    description="Разбивает собственные товары на группы A/B/C по доле в выручке",
)
async def abc_analysis(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ABC-анализ по выручке-прокси (цена × количество продаж).

    Группы: A — до 80% выручки, B — до 95%, C — остальные.
    """
    products = (
        await db.execute(
            select(Product).where(
                Product.user_id == current_user.id,
                Product.is_competitor.is_(False),
            )
        )
    ).scalars().all()

    items = []
    for product in products:
        revenue = float(product.price or 0) * int(product.sales_count or 0)
        items.append({"id": product.id, "name": product.name, "revenue": round(revenue, 2)})

    items.sort(key=lambda x: x["revenue"], reverse=True)
    total_revenue = sum(i["revenue"] for i in items)

    if total_revenue <= 0:
        return {
            "total_products": len(items),
            "total_revenue": 0.0,
            "note": "Недостаточно данных о продажах (sales_count) для ABC-анализа",
            "groups": {"A": [], "B": [], "C": [i["name"] for i in items]},
        }

    cumulative = 0.0
    groups = {"A": [], "B": [], "C": []}
    for item in items:
        cumulative += item["revenue"]
        share = cumulative / total_revenue * 100
        if share <= 80:
            groups["A"].append(item)
        elif share <= 95:
            groups["B"].append(item)
        else:
            groups["C"].append(item)

    return {
        "total_products": len(items),
        "total_revenue": round(total_revenue, 2),
        "groups": groups,
    }


@router.get(
    "/competitor-sales/{product_id}",
    summary="Оценка продаж конкурента",
    description="Эвристическая оценка продаж конкурента по отзывам и истории цен",
)
async def estimate_competitor_sales(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Оценить продажи товара-конкурента.

    Метод эвристический: число отзывов отражает примерно 3–7% покупателей,
    динамика истории цен помогает оценить активность карточки.
    Точные продажи закрыты площадками — это ориентир, а не факт.
    """
    product = (
        await db.execute(
            select(Product).where(
                Product.id == product_id,
                Product.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    reviews = int(product.reviews_count or 0)

    # Доля покупателей, оставляющих отзыв, обычно ~5%. Берём диапазон 3–7%.
    estimated_total_sales_min = int(reviews / 0.07) if reviews else 0
    estimated_total_sales_max = int(reviews / 0.03) if reviews else 0

    # История цен — индикатор «живости» карточки за период наблюдения.
    history = (
        await db.execute(
            select(PriceHistory)
            .where(PriceHistory.product_id == product.id)
            .order_by(PriceHistory.created_at.asc())
        )
    ).scalars().all()

    period_days = None
    if len(history) >= 2 and history[0].created_at and history[-1].created_at:
        period_days = max((history[-1].created_at - history[0].created_at).days, 1)

    estimated_monthly_min = None
    estimated_monthly_max = None
    if period_days:
        estimated_monthly_min = int(estimated_total_sales_min / period_days * 30)
        estimated_monthly_max = int(estimated_total_sales_max / period_days * 30)

    return {
        "product_id": product.id,
        "product_name": product.name,
        "reviews_count": reviews,
        "estimated_total_sales": {
            "min": estimated_total_sales_min,
            "max": estimated_total_sales_max,
        },
        "estimated_monthly_sales": {
            "min": estimated_monthly_min,
            "max": estimated_monthly_max,
        },
        "price_history_points": len(history),
        "method": "Эвристика по отзывам (3–7% покупателей оставляют отзыв) и истории цен",
        "disclaimer": "Оценка приблизительная: точные продажи маркетплейсы не раскрывают.",
    }
