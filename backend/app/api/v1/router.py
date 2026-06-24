"""
Роутер API версии 1.

Объединяет все эндпоинты v1.
"""

from fastapi import APIRouter

from app.api.v1 import parsing, ai, products, auth, notifications, repricing, calendar, billing, chat, reports, analytics, widget

api_router = APIRouter()

# Включаем роутеры по модулям
api_router.include_router(auth.router, prefix="/auth", tags=["Аутентификация"])
api_router.include_router(parsing.router, prefix="/parsing", tags=["Парсинг"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI"])
api_router.include_router(products.router, prefix="/products", tags=["Товары"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Уведомления"])
api_router.include_router(repricing.router, prefix="/repricing", tags=["Репрайсинг"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["Календарь"])
api_router.include_router(billing.router, prefix="/billing", tags=["Тарифы"])
api_router.include_router(chat.router, prefix="/chat", tags=["Чат поддержки"])
api_router.include_router(reports.router, prefix="/reports", tags=["Отчёты"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Аналитика"])
api_router.include_router(widget.router, prefix="/widget", tags=["Виджет"])
