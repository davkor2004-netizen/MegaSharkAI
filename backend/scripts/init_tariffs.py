"""
Скрипт для инициализации тарифов в базе данных.

Запуск:
    python scripts/init_tariffs.py
"""

import asyncio
import sys
import json
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.models.tariff import Tariff
from app.config import settings


# Данные тарифов согласно ТЗ
TARIFFS_DATA = [
    {
        "name": "Pro",
        "code": "pro",
        "price_monthly": 2490.0,
        "price_yearly": 23900.0,  # ~20% скидка
        "trial_days": 7,
        "sort_order": 1,
        "limits": {
            "max_products": 500,
            "max_repricing_products": 100,
            "ai_generations_per_month": 50,
            "ai_analyst_questions": 20,
            "competitor_reports": 10,
            "price_update_frequency": 4,  # раза в сутки
            "excel_import": True,
            "excel_mass_update": True,  # до 200 товаров
            "api_access": False,
            "widget_access": False,
            "photo_analysis": False,
            "forecast_months": 3,
            "custom_repricing": False,
            "max_users": 1,
            "support_priority": "standard",
        },
        "features": {
            "monitoring": [
                "До 500 товаров в мониторинге",
                "Парсинг цен: Ozon, WB, Авито, KazanExpress, Яндекс.Маркет",
                "Обновление данных 4 раза в сутки (каждые 6 часов)",
            ],
            "repricing": [
                "3 стратегии репрайсинга",
                "«Агрессивный рост доли» (всегда на 5 ₽ дешевле)",
                "«Защита маржи» (не ниже себестоимости)",
                "«Ночной репрайсинг» (поднимать цену ночью)",
                "До 100 товаров на активном репрайсинге",
            ],
            "ai_generation": [
                "50 генераций SEO-названий в месяц",
                "50 генераций описаний товаров в месяц",
                "Модели: DeepSeek-V3 + YandexGPT Pro",
            ],
            "analytics": [
                "10 отчётов по карточке конкурента в месяц",
                "Прогноз изменения спроса (для 50 товаров)",
                "ИИ-календарь распродаж (базовый, 3 месяца)",
            ],
            "ai_analyst": [
                "20 вопросов к AI-аналитику в месяц",
                "Анализ динамики цен и остатков",
            ],
            "mass_management": [
                "Импорт товаров через Excel (до 500 товаров)",
                "Обновление цен и характеристик (до 200 товаров)",
            ],
            "integrations": [
                "Без API-доступа",
                "Без виджета",
            ],
            "support": [
                "Стандартная поддержка в чате",
                "Время ответа до 24 часов",
            ],
        },
    },
    {
        "name": "Business",
        "code": "business",
        "price_monthly": 7990.0,
        "price_yearly": 76700.0,  # ~20% скидка
        "trial_days": 7,
        "sort_order": 2,
        "limits": {
            "max_products": -1,  # безлимит
            "max_repricing_products": -1,  # безлимит
            "ai_generations_per_month": -1,  # безлимит
            "ai_analyst_questions": -1,  # безлимит
            "competitor_reports": -1,  # безлимит
            "price_update_frequency": 24,  # раз в сутки (каждый час)
            "excel_import": True,
            "excel_mass_update": True,  # полный массовый
            "api_access": True,
            "widget_access": True,
            "photo_analysis": True,
            "forecast_months": 12,
            "custom_repricing": True,
            "max_users": 5,
            "support_priority": "priority_247",
        },
        "features": {
            "monitoring": [
                "Безлимитное количество товаров",
                "Парсинг цен: Ozon, WB, Авито, KazanExpress, Яндекс.Маркет",
                "Обновление данных каждый час (24 раза в сутки)",
            ],
            "repricing": [
                "Все 3 стратегии + кастомные правила",
                "Безлимитное количество товаров на репрайсинге",
                "Агрессивный рост доли",
                "Защита маржи",
                "Ночной репрайсинг",
            ],
            "ai_generation": [
                "Безлимитные генерации SEO-названий",
                "Безлимитные генерации описаний",
                "Анализ качества фото (CLIP + YOLO)",
                "Модели: DeepSeek-V3 + YandexGPT Pro + Claude Opus",
            ],
            "analytics": [
                "Безлимитные отчёты по конкурентам",
                "Прогноз спроса для всех товаров",
                "ИИ-календарь распродаж (расширенный, 12 месяцев)",
            ],
            "ai_analyst": [
                "Безлимитные вопросы к AI-аналитику",
                "Глубокий анализ с историей товара",
                "Анализ отзывов и действий конкурентов",
            ],
            "mass_management": [
                "Полный массовый импорт/экспорт Excel",
                "Массовое обновление фото и названий",
                "Сотни товаров одной операцией",
            ],
            "integrations": [
                "API-доступ для интеграции",
                "Виджет для встраивания на сайты",
                "Персональный код вставки",
            ],
            "multiuser": [
                "До 5 пользователей в аккаунте",
                "Разграничение прав (админ, аналитик, менеджер)",
            ],
            "support": [
                "Приоритетная поддержка 24/7",
                "Время ответа до 2 часов",
                "Выделенный менеджер (от 500к ₽/мес)",
            ],
        },
    },
]


async def init_tariffs():
    """Инициализация тарифов в БД."""
    
    # Создаём движок
    engine = create_async_engine(
        settings.database_url,
        echo=False,
    )
    
    async with engine.begin() as conn:
        # Создаём сессию
        async_session = sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        async with async_session() as db:
            # Проверяем существующие тарифы
            result = await db.execute(select(Tariff))
            existing_tariffs = result.scalars().all()
            
            if existing_tariffs:
                print(f"Warning: {len(existing_tariffs)} tariffs already exist")
                response = input("Delete and recreate? (y/n): ")
                if response.lower() == 'y':
                    for tariff in existing_tariffs:
                        await db.delete(tariff)
                    await db.commit()
                    print("Old tariffs deleted")
                else:
                    print("Cancelled")
                    return
            
            # Create tariffs
            for tariff_data in TARIFFS_DATA:
                tariff = Tariff(
                    name=tariff_data["name"],
                    code=tariff_data["code"],
                    price_monthly=tariff_data["price_monthly"],
                    price_yearly=tariff_data["price_yearly"],
                    trial_days=tariff_data["trial_days"],
                    sort_order=tariff_data["sort_order"],
                    is_active=True,
                    limits=json.dumps(tariff_data["limits"]),
                    features=json.dumps(tariff_data["features"]),
                )
                db.add(tariff)
                print(f"Added tariff: {tariff.name} ({tariff.code})")
            
            await db.commit()
            print(f"\nSuccess: created {len(TARIFFS_DATA)} tariffs!")
            
            # Print info
            print("\nTariffs:")
            for tariff_data in TARIFFS_DATA:
                print(f"  - {tariff_data['name']}: {tariff_data['price_monthly']} RUB/month or {tariff_data['price_yearly']} RUB/year")
                print(f"    Trial: {tariff_data['trial_days']} days")


if __name__ == "__main__":
    print("Init tariffs MegaSharkAI...")
    asyncio.run(init_tariffs())
