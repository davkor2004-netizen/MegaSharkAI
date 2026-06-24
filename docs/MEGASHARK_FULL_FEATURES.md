# 🚀 MEGASHARK AI - МОЩНЫЙ ФУНКЦИОНАЛ

Полное руководство по всем инструментам личного кабинета с технической реализацией.

---

## 📋 СОДЕРЖАНИЕ

1. [Dashboard (Главная панель)](#1-dashboard-главная-панель)
2. [Parsing (Парсинг)](#2-parsing-парсинг-товаров)
3. [Products (Товары)](#3-products-управление-товарами)
4. [Analytics (Аналитика)](#4-analytics-аналитика)
5. [AI Assistant (AI Помощник)](#5-ai-assistant-ai-помощник)
6. [Repricing (Автоценообразование)](#6-repricing-автоценообразование)
7. [Calendar (Календарь)](#7-calendar-календарь-событий)
8. [Notifications (Уведомления)](#8-notifications-уведомления)
9. [Billing (Подписка)](#9-billing-подписка-и-оплата)
10. [Import/Export (Импорт/Экспорт)](#10-importexport-импортэкспорт)
11. [Partners (Партнёрка)](#11-partners-партнёрская-программа)
12. [Settings (Настройки)](#12-settings-настройки)
13. [Marketplace Keys (API ключи)](#13-marketplace-keys-ключи-маркетплейсов)

---

## 1. DASHBOARD (Главная панель)

### 📊 Назначение
Центральный хаб для быстрого обзора состояния бизнеса.

### 🔧 Функционал

| Виджет | Описание | API Endpoint |
|--------|----------|--------------|
| **Общая статистика** | Кол-во товаров, средняя цена, изменения за 24ч | `GET /api/v1/products/stats/summary` |
| **График цен** | Динамика цен (ваши vs конкуренты) за 7/30 дней | `GET /api/v1/analytics/price-chart` |
| **Топ товаров** | 5 товаров с наибольшими изменениями цен | `GET /api/v1/products/list?limit=5` |
| **Уведомления** | Последние 5 уведомлений | `GET /api/v1/notifications/?limit=5` |
| **Календарь** | Ближайшие события (акции, дедлайны) | `GET /api/v1/calendar/upcoming` |
| **Статус подписки** | Текущий тариф, дни до конца | `GET /api/v1/billing/current` |

### 💾 Источники данных
- PostgreSQL (товары, цены)
- Redis (кэш статистики)
- Celery (фоновые задачи парсинга)

### 🛠️ Что нужно доделать
- [ ] Эндпоинт `/api/v1/analytics/price-chart`
- [ ] Эндпоинт `/api/v1/calendar/upcoming`
- [ ] WebSocket для real-time обновлений

### 💰 Затраты
- **0 ₽** — базовый функционал

---

## 2. PARSING (Парсинг товаров)

### 🕷️ Назначение
Сбор данных о товарах с маркетплейсов.

### 🔧 Два режима работы

#### Режим 1: Парсинг по URL (Конкуренты)
```
Вводишь URL товара конкурента → Playwright извлекает:
- Название
- Цену
- Остатки
- Рейтинг
- Отзывы
```

**Техническая реализация:**
```python
# backend/app/services/parser.py
from playwright.async_api import async_playwright

async def parse_wildberries_product(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)
        
        # Извлечение данных
        price = await page.query_selector('.price-block__sum-price')
        name = await page.query_selector('.product-header__title')
        
        return {
            'name': await name.inner_text(),
            'price': int(await price.inner_text().replace('₽', '')),
        }
```

**Что нужно:**
- ✅ Playwright (установлен)
- 🔶 **Прокси-серверы** (500-2000 ₽/мес)
- 🔶 Rotating User-Agents

#### Режим 2: API (Мои товары)
```
Подключаешь API ключ → Автоматическая загрузка всех твоих товаров
```

**Поддерживаемые API:**

| Маркетплейс | API Documentation | Стоимость |
|-------------|-------------------|-----------|
| **Wildberries** | https://openapi.wildberries.ru | Бесплатно |
| **Ozon** | https://docs.ozon.ru/api/seller | Бесплатно |
| **Яндекс Маркет** | https://yandex.ru/dev/marketplace | Бесплатно |
| **Avito** | https://developers.avito.ru/api | Бесплатно |

**Техническая реализация:**
```python
# backend/app/services/marketplace_api.py
import httpx

async def get_wildberries_products(api_key: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://supplier-backoffice-api.wildberries.ru/api/v1/products",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        return response.json()
```

### 🛠️ Что нужно доделать
- [ ] Реальная интеграция с API Wildberries
- [ ] Реальная интеграция с API Ozon
- [ ] Реальная интеграция с API Яндекс Маркет
- [ ] Celery задачи для фонового парсинга
- [ ] Очереди на парсинг (Redis Queue)

### 💰 Затраты
- **Прокси**: 500-2000 ₽/мес (для URL парсинга)
- **API ключи**: Бесплатно

---

## 3. PRODUCTS (Управление товарами)

### 📦 Назначение
Просмотр, редактирование, управление товарами.

### 🔧 Функционал

| Функция | Описание | API |
|---------|----------|-----|
| **Список товаров** | Таблица с фильтрами (поиск, категория, маркетплейс) | `GET /api/v1/products/list` |
| **Редактирование** | Изменение цены, описания, остатков | `PUT /api/v1/products/{id}` |
| **Добавление** | Ручное добавление товара | `POST /api/v1/products` |
| **Удаление** | Удаление товара из базы | `DELETE /api/v1/products/{id}` |
| **Массовые операции** | Изменение цен нескольких товаров сразу | `POST /api/v1/products/bulk-update` |

### 💾 Модель данных
```python
# backend/app/models/product.py
class Product(Base):
    id = Column(Integer, primary_key=True)
    user_id = Column(UUID, ForeignKey('users.id'))
    marketplace = Column(String)  # wildberries, ozon, etc.
    product_id = Column(String)  # ID на маркетплейсе
    name = Column(String)
    price = Column(Integer)
    old_price = Column(Integer)
    discount = Column(Integer)
    rating = Column(Float)
    reviews_count = Column(Integer)
    stock = Column(Integer)
    is_competitor = Column(Boolean)  # True = конкурент, False = мой
    url = Column(String)
    image_url = Column(String)
```

### 🛠️ Что нужно доделать
- [ ] Массовое редактирование (bulk update)
- [ ] Фильтрация по категориям
- [ ] Экспорт в CSV/XLSX
- [ ] История изменений цен

### 💰 Затраты
- **0 ₽** — базовый функционал

---

## 4. ANALYTICS (Аналитика)

### 📈 Назначение
Глубокий анализ продаж, цен, позиций.

### 🔧 Функционал

| График | Описание | API |
|--------|----------|-----|
| **Динамика цен** | График изменения цен (ваши vs конкуренты) | `GET /api/v1/analytics/price-history` |
| **Продажи по периодам** | Столбчатая диаграмма продаж по дням/неделям | `GET /api/v1/analytics/sales-chart` |
| **Позиции в поиске** | Изменение позиций товаров в выдаче | `GET /api/v1/analytics/ranking-history` |
| **ABC-анализ** | Классификация товаров по важности | `GET /api/v1/analytics/abc-analysis` |
| **Сравнение с конкурентами** | Radar chart: ваши преимущества/недостатки | `GET /api/v1/analytics/competitor-comparison` |

### 🛠️ Что нужно доделать
- [ ] Все эндпоинты аналитики
- [ ] Агрегация исторических данных ( hourly/daily snapshots)
- [ ] Библиотека для графиков на фронтенде (Chart.js / Recharts)

### 💾 Хранение истории
```python
# backend/app/models/price_history.py
class PriceHistory(Base):
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'))
    price = Column(Integer)
    competitor_price = Column(Integer)
    position = Column(Integer)  # Позиция в поиске
    timestamp = Column(DateTime, default=datetime.utcnow)
```

### 💰 Затраты
- **0 ₽** — работает на основе собранных данных

---

## 5. AI ASSISTANT (AI Помощник)

### 🤖 Назначение
AI-рекомендации по ценам, описаниям, стратегиям.

### 🔧 Функционал

| Функция | Описание | Модель |
|---------|----------|--------|
| **Генерация описаний** | Создание SEO-оптимизированных описаний товаров | GPT-4 / Claude |
| **Рекомендации по ценам** | Анализ рынка → совет по цене | GPT-4 + данные парсинга |
| **Анализ отзывов** | Sentiment analysis отзывов конкурентов | GPT-4 |
| **Прогноз спроса** | Предсказание спроса на основе сезона/трендов | GPT-4 + исторические данные |
| **Оптимизация карточки** | Советы по улучшению карточки товара | GPT-4 Vision |

### 🔌 Интеграция с OpenAI

```python
# backend/app/services/ai_service.py
from openai import AsyncOpenAI

class AIService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    async def generate_product_description(self, product_data: dict) -> str:
        prompt = f"""
        Создай SEO-оптимизированное описание товара:
        Название: {product_data['name']}
        Категория: {product_data['category']}
        Цена: {product_data['price']} ₽
        Особенности: {product_data['features']}
        
        Требования:
        - До 1000 символов
        - Ключевые слова для поиска
        - Преимущества для покупателя
        """
        
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        
        return response.choices[0].message.content
    
    async def analyze_competitors(self, your_price: float, competitor_prices: list) -> dict:
        prompt = f"""
        Ваша цена: {your_price} ₽
        Цены конкурентов: {competitor_prices}
        
        Дай рекомендацию:
        1. Стоит ли менять цену?
        2. Какую цену установить?
        3. Какие преимущества подчеркнуть?
        """
        
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        
        return {
            "recommendation": response.choices[0].message.content,
            "optimal_price": self._calculate_optimal_price(...)
        }
```

### 🛠️ Что нужно доделать
- [ ] Сервис `ai_service.py`
- [ ] Эндпоинты `/api/v1/ai/generate-description`
- [ ] Эндпоинты `/api/v1/ai/analyze-competitors`
- [ ] Эндпоинты `/api/v1/ai/review-analysis`
- [ ] Интеграция с фронтендом (чат-интерфейс)

### 💰 Затраты
| Провайдер | Модель | Стоимость | Рекомендация |
|-----------|--------|-----------|--------------|
| **OpenAI** | GPT-4o-mini | ~$0.15 / 1M токенов | ⭐ Лучшее соотношение |
| **OpenAI** | GPT-4 Turbo | ~$10 / 1M токенов | Для сложных задач |
| **Anthropic** | Claude 3.5 Sonnet | ~$3 / 1M токенов | Альтернатива |
| **Local** | Llama 3.1 70B | $0 (нужен GPU сервер) | Для экономии |

**Примерный расход:** $10-50/мес при активном использовании

---

## 6. REPRICING (Автоценообразование)

### 💰 Назначение
Автоматическая корректировка цен для победы в Buy Box.

### 🔧 Стратегии

| Стратегия | Описание | Когда использовать |
|-----------|----------|-------------------|
| **Aggressive** | Цена на 1-5% ниже минимума конкурентов | Для захвата рынка |
| **Margin Protection** | Средняя цена конкурентов + целевая маржа | Для сохранения прибыли |
| **Night** | Снижение на 5-10% ночью | Для ночных продаж |
| **Balanced** | Между средним и минимальным | Сбалансированный подход |
| **Follow Leader** |跟随 цену лидера рынка | Если есть явный лидер |

### 🔌 Техническая реализация

```python
# backend/app/services/repricing_service.py
class RepricingService:
    async def calculate_optimal_price(
        self,
        product: Product,
        competitor_prices: List[float],
        strategy: str,
        target_margin: float = 30.0
    ) -> float:
        if not competitor_prices:
            return product.price
        
        min_price = min(competitor_prices)
        avg_price = sum(competitor_prices) / len(competitor_prices)
        
        if strategy == "aggressive":
            recommended = min_price * 0.95
        elif strategy == "margin_protection":
            recommended = avg_price * (1 + target_margin / 100)
        elif strategy == "night":
            recommended = product.price * 0.90
        elif strategy == "balanced":
            recommended = (avg_price + min_price) / 2
        
        # Округление до 99
        recommended = round(recommended / 10) * 10 - 1
        
        # Ограничения
        recommended = max(recommended, product.min_price or 100)
        recommended = min(recommended, product.max_price or 999999)
        
        return recommended
    
    async def apply_repricing(self, user_id: UUID):
        # Celery задача для фонового применения
        products = await self.get_user_products(user_id)
        for product in products:
            competitors = await self.get_competitors(product)
            new_price = await self.calculate_optimal_price(...)
            await self.update_marketplace_price(product, new_price)
```

### 🛠️ Celery задача для авто-репрайсинга

```python
# backend/app/celery_tasks.py
@app.task(bind=True, max_retries=3)
def run_repricing_task(self, user_id: str):
    try:
        repricing_service = RepricingService()
        asyncio.run(repricing_service.apply_repricing(UUID(user_id)))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=300)
```

### 🛠️ Что нужно доделать
- [ ] Сервис `repricing_service.py`
- [ ] Celery задачи для фонового применения
- [ ] Интеграция с API маркетплейсов (для обновления цен)
- [ ] Настройка расписания (Celery Beat)
- [ ] Логирование изменений цен

### 💰 Затраты
- **0 ₽** — базовый функционал
- **API ключи маркетплейсов** — бесплатно

---

## 7. CALENDAR (Календарь событий)

### 📅 Назначение
Планирование акций, отслеживание событий маркетплейсов.

### 🔧 Функционал

| Тип события | Источник | Пример |
|-------------|----------|--------|
| **Акции маркетплейсов** | Парсинг / API | "Чёрная пятница WB: 25-27 ноября" |
| **Дедлайны поставок** | Ввод пользователя | "Поставка на склад до 15 декабря" |
| **Изменения правил** | RSS / Парсинг | "WB меняет комиссию с 1 января" |
| **Планы по ценам** | Ввод пользователя | "Поднять цены на 10% после НГ" |

### 🔌 Интеграция с календарями

```python
# backend/app/services/calendar_service.py
from icalendar import Calendar, Event
from datetime import datetime, timedelta

class CalendarService:
    async def get_marketplace_events(self) -> List[dict]:
        # Парсинг событий с сайтов маркетплейсов
        return [
            {
                "title": "Чёрная пятница",
                "start": "2025-11-25",
                "end": "2025-11-27",
                "marketplace": "wildberries",
                "type": "sale"
            }
        ]
    
    async def export_to_ics(self, user_id: UUID) -> bytes:
        cal = Calendar()
        events = await self.get_user_events(user_id)
        
        for event in events:
            e = Event()
            e.add('summary', event['title'])
            e.add('dtstart', datetime.fromisoformat(event['start']))
            e.add('dtend', datetime.fromisoformat(event['end']))
            cal.add_component(e)
        
        return cal.to_ical()
```

### 🛠️ Что нужно доделать
- [ ] Модель `CalendarEvent` в БД
- [ ] Эндпоинты `/api/v1/calendar/events`
- [ ] Эндпоинты `/api/v1/calendar/export-ics`
- [ ] Интеграция с Google Calendar API (опционально)
- [ ] Фронтенд: календарь (FullCalendar.js)

### 💰 Затраты
- **0 ₽** — базовый функционал
- **Google Calendar API** — бесплатно (до 1M запросов/день)

---

## 8. NOTIFICATIONS (Уведомления)

### 🔔 Назначение
Оповещения об изменениях, новых событиях.

### 🔧 Каналы уведомлений

| Канал | Описание | Стоимость |
|-------|----------|-----------|
| **Email** | Письма на почту | SMTP: $0-15/мес |
| **Telegram** | Бот в Telegram | Бесплатно |
| **Push (Web)** | Browser Push | Бесплатно |
| **In-App** | Уведомления в ЛК | Бесплатно |

### 🔌 Реализация

#### Email (SendGrid / Gmail)
```python
# backend/app/services/email.py
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

class EmailService:
    def send_price_alert(self, to_email: str, product_name: str, old_price: float, new_price: float):
        message = Mail(
            from_email='alerts@megashark.ai',
            to_emails=to_email,
            subject=f'🔔 Изменение цены: {product_name}',
            html_content=f'''
            <h2>Цена изменилась!</h2>
            <p>Товар: {product_name}</p>
            <p>Старая цена: {old_price} ₽</p>
            <p>Новая цена: {new_price} ₽</p>
            '''
        )
        
        sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        sg.send(message)
```

#### Telegram Bot
```python
# backend/app/services/telegram_bot.py
from telegram import Bot
import asyncio

class TelegramBotService:
    def __init__(self):
        self.bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
    
    async def send_notification(self, user_chat_id: str, message: str):
        await self.bot.send_message(
            chat_id=user_chat_id,
            text=message,
            parse_mode='HTML'
        )
```

#### Web Push
```python
# backend/app/services/push_service.py
from pywebpush import webpush
import json

class PushService:
    def send_push(self, subscription_info: dict, title: str, message: str):
        webpush(
            subscription_info,
            json.dumps({
                "title": title,
                "body": message,
                "icon": "/logo.png"
            }),
            os.getenv("VAPID_PUBLIC_KEY"),
            os.getenv("VAPID_PRIVATE_KEY"),
            ttl=86400
        )
```

### 🛠️ Что нужно доделать
- [ ] Email сервис (SendGrid интеграция)
- [ ] Telegram бот (создать через @BotFather)
- [ ] Web Push (VAPID ключи)
- [ ] Триггеры для уведомлений (Celery Beat)
- [ ] Настройки уведомлений для пользователя

### 💰 Затраты
| Сервис | Бесплатный лимит | Платный тариф |
|--------|------------------|---------------|
| **SendGrid** | 100 писем/день | $15/мес (40K писем) |
| **Gmail SMTP** | 500 писем/день | Бесплатно |
| **Telegram Bot** | Безлимитно | Бесплатно |
| **Web Push** | Безлимитно | Бесплатно |

---

## 9. BILLING (Подписка и оплата)

### 💳 Назначение
Управление тарифами, приём оплаты.

### 🔧 Тарифы

| Тариф | Цена/мес | Возможности |
|-------|----------|-------------|
| **Free** | 0 ₽ | • До 10 товаров<br>• Базовый парсинг<br>• 1 маркетплейс |
| **Pro** | 990 ₽ | • До 100 товаров<br>• AI помощник<br>• Автоценообразование<br>• Все маркетплейсы |
| **Business** | 2990 ₽ | • Безлимит товаров<br>• Приоритетная поддержка<br>• API доступ<br>• White label |

### 🔌 Интеграция с ЮKassa

```python
# backend/app/services/payment_service.py
from yookassa import Configuration, Payment
import uuid

class PaymentService:
    def __init__(self):
        Configuration.account_id = os.getenv('YOOKASSA_SHOP_ID')
        Configuration.secret_key = os.getenv('YOOKASSA_API_KEY')
    
    async def create_payment(self, user_id: UUID, amount: float, tariff_code: str) -> dict:
        payment = Payment.create({
            "amount": {
                "value": str(amount),
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": f"https://megashark.ai/billing/success?session_id={uuid.uuid4()}"
            },
            "capture": True,
            "description": f"Оплата тарифа {tariff_code}",
            "metadata": {
                "user_id": str(user_id),
                "tariff_code": tariff_code
            }
        })
        
        return {
            "payment_id": payment.id,
            "confirmation_url": payment.confirmation.confirmation_url
        }
```

### 🛠️ Что нужно доделать
- [ ] Модель `Tariff` и `UserSubscription` (есть)
- [ ] Интеграция с ЮKassa / CloudPayments
- [ ] Webhook для обработки оплат
- [ ] Пробный период (7 дней)
- [ ] Автопродление подписки
- [ ] Фронтенд: страница тарифов

### 💰 Затраты
| Платёжная система | Комиссия | Выплаты |
|-------------------|----------|---------|
| **ЮKassa** | 2.8% + 30₽ | Ежедневно |
| **CloudPayments** | 2.8% | Ежедневно |
| **Robokassa** | 2.5-3.5% | По запросу |
| **Stripe** | 2.9% + $0.30 | 2-7 дней |

---

## 10. IMPORT/EXPORT (Импорт/Экспорт)

### 📥 Назначение
Массовая загрузка/выгрузка товаров.

### 🔧 Форматы

| Формат | Описание | Пример |
|--------|----------|--------|
| **CSV** | Текст, разделённый запятыми | `id,name,price,stock` |
| **XLSX** | Excel файл | Таблица с форматированием |
| **XML** | Для некоторых маркетплейсов | YML для Яндекс Маркет |
| **JSON** | Универсальный формат | Структурированные данные |

### 🔌 Реализация импорта CSV

```python
# backend/app/services/import_service.py
import pandas as pd
from io import BytesIO

class ImportService:
    async def import_csv(self, file: UploadFile, user_id: UUID) -> dict:
        # Чтение файла
        contents = await file.read()
        df = pd.read_csv(BytesIO(contents))
        
        # Валидация
        required_columns = ['name', 'price']
        if not all(col in df.columns for col in required_columns):
            raise ValueError("Отсутствуют обязательные колонки")
        
        # Импорт в БД
        imported_count = 0
        for _, row in df.iterrows():
            product = Product(
                user_id=user_id,
                name=row['name'],
                price=float(row['price']),
                marketplace=row.get('marketplace', 'manual'),
                is_competitor=False
            )
            # db.add(product)
            imported_count += 1
        
        return {
            "status": "success",
            "imported_count": imported_count
        }
```

### 🛠️ Что нужно доделать
- [ ] Сервис `import_service.py`
- [ ] Эндпоинты `/api/v1/import/csv`
- [ ] Эндпоинты `/api/v1/export/csv`
- [ ] Фронтенд: загрузка файлов
- [ ] Валидация данных
- [ ] Прогресс-бар для больших файлов

### 💰 Затраты
- **0 ₽** — базовый функционал

---

## 11. PARTNERS (Партнёрская программа)

### 🤝 Назначение
Привлечение пользователей через рефералов.

### 🔧 Механика

```
Пользователь А получает ссылку: https://megashark.ai/register?ref=user_a
Пользователь Б регистрируется по ссылке
Пользователь Б оплачивает подписку 990₽
Пользователь А получает 20% = 198₽ на баланс
```

### 🔌 Реализация

```python
# backend/app/models/referral.py
class Referral(Base):
    id = Column(Integer, primary_key=True)
    referrer_id = Column(UUID, ForeignKey('users.id'))  # Кто пригласил
    referred_id = Column(UUID, ForeignKey('users.id'))  # Кого пригласили
    created_at = Column(DateTime, default=datetime.utcnow)
    commission_paid = Column(Boolean, default=False)

# backend/app/services/referral_service.py
class ReferralService:
    async def on_user_register(self, referred_user: User, referrer_code: str):
        # Находим пригласившего
        referrer = await self.get_user_by_referral_code(referrer_code)
        if referrer:
            referral = Referral(
                referrer_id=referrer.id,
                referred_id=referred_user.id
            )
            # db.add(referral)
    
    async def on_payment(self, user: User, amount: float):
        # Находим реферала
        referral = await self.get_referral_by_referred(user.id)
        if referral and not referral.commission_paid:
            commission = amount * 0.20  # 20%
            await self.add_to_balance(referral.referrer_id, commission)
            referral.commission_paid = True
```

### 🛠️ Что нужно доделать
- [ ] Модель `Referral`
- [ ] Генерация реферальных ссылок
- [ ] Начисление комиссий
- [ ] Вывод средств (на карту/кошелёк)
- [ ] Фронтенд: страница партнёрки
- [ ] Статистика рефералов

### 💰 Затраты
- **0 ₽** — внутренняя система
- **20% от подписок** — выплаты партнёрам

---

## 12. SETTINGS (Настройки)

### ⚙️ Назначение
Глобальные настройки аккаунта.

### 🔧 Разделы настроек

| Раздел | Опции |
|--------|-------|
| **Профиль** | Email, имя, телефон, пароль |
| **Тема** | Светлая / Тёмная / Авто |
| **Язык** | Русский / English |
| **Часовой пояс** | UTC, MSK, и т.д. |
| **Уведомления** | Включить/выключить каналы |
| **API ключи** | Управление ключами маркетплейсов |
| **Правила репрайсинга** | Стратегия, мин/макс цены |
| **Шаблоны** | Шаблоны описаний, ответов на отзывы |

### 🛠️ Что нужно доделать
- [ ] Модель `UserSettings` (есть частично)
- [ ] Эндпоинты `/api/v1/settings`
- [ ] Фронтенд: страница настроек
- [ ] Сохранение предпочтений

### 💰 Затраты
- **0 ₽**

---

## 13. MARKETPLACE KEYS (Ключи маркетплейсов)

### 🔑 Назначение
Подключение API маркетплейсов.

### 🔧 Поддерживаемые площадки

| Маркетплейс | Получение ключа | Документация |
|-------------|-----------------|--------------|
| **Wildberries** | ЛК продавца → Профиль → API | https://openapi.wildberries.ru |
| **Ozon** | ЛК продавца → Настройки → API | https://docs.ozon.ru/api/seller |
| **Яндекс Маркет** | ЛК продавца → Настройки | https://yandex.ru/dev/marketplace |
| **Avito** | ЛК продавца → Настройки → API | https://developers.avito.ru |

### 🔐 Безопасность

```python
# backend/app/services/encryption.py
from cryptography.fernet import Fernet

class EncryptionService:
    def __init__(self):
        self.key = os.getenv('ENCRYPTION_KEY').encode()
        self.fernet = Fernet(self.key)
    
    def encrypt(self, api_key: str) -> str:
        return self.fernet.encrypt(api_key.encode()).decode()
    
    def decrypt(self, encrypted_key: str) -> str:
        return self.fernet.decrypt(encrypted_key.encode()).decode()
```

### ✅ Уже реализовано
- [x] Модель `MarketplaceKey`
- [x] Шифрование AES-256
- [x] CRUD эндпоинты
- [x] Валидация ключей
- [x] Фронтенд: профиль (частично)

### 🛠️ Что нужно доделать
- [ ] Реальная валидация ключей (интеграция с API)
- [ ] Автообновление токенов (если требуется)
- [ ] Уведомления об истечении ключей

### 💰 Затраты
- **0 ₽** — API ключи бесплатные

---

# 💰 СВОДНАЯ ТАБЛИЦА ЗАТРАТ

## Минимальный набор (Старт)

| Компонент | Стоимость | Обязательность |
|-----------|-----------|----------------|
| **VPS сервер** | 1000-2000 ₽/мес | ⭐ Обязательно |
| **Домен** | 500 ₽/год | ⭐ Обязательно |
| **PostgreSQL** | 0 ₽ (на VPS) | ⭐ Обязательно |
| **Redis** | 0 ₽ (на VPS) | ⭐ Обязательно |
| **Платёжный шлюз** | 2.8% комиссия | ⭐ Для приёма оплаты |
| **Gmail SMTP** | 0 ₽ | 🔶 Для email |
| **Telegram Bot** | 0 ₽ | 🔶 Для уведомлений |

**Итого:** ~2000 ₽/мес + 2.8% комиссия

---

## Рекомендуемый набор (Pro)

| Компонент | Стоимость | Обязательность |
|-----------|-----------|----------------|
| **VPS сервер (4GB RAM)** | 3000-5000 ₽/мес | ⭐ |
| **Прокси-серверы** | 1000-2000 ₽/мес | 🔶 Для парсинга |
| **OpenAI API** | $20-50/мес (~2000-5000 ₽) | 🔶 Для AI |
| **SendGrid** | $15/мес (~1500 ₽) | 🔶 Для email |
| **ЮKassa** | 2.8% + 30₽ | ⭐ Для оплаты |
| **Резервное хранилище** | 500 ₽/мес | 🔶 Для бэкапов |

**Итого:** ~8000-14000 ₽/мес + 2.8% комиссия

---

## Максимальный набор (Enterprise)

| Компонент | Стоимость | Обязательность |
|-----------|-----------|----------------|
| **Выделенный сервер** | 15000-30000 ₽/мес | ⭐ |
| **Прокси (rotating)** | 5000-10000 ₽/мес | 🔶 |
| **OpenAI Enterprise** | $500-1000/мес | 🔶 |
| **SendGrid Pro** | $90/мес (~9000 ₽) | 🔶 |
| **Cloudflare Enterprise** | $200/мес (~20000 ₽) | 🔶 Для защиты |
| **MongoDB Atlas** | $100/мес (~10000 ₽) | 🔶 Для аналитики |

**Итого:** ~60000-100000 ₽/мес + комиссии

---

# 📋 ПЛАН РАЗРАБОТКИ

## Этап 1: MVP (2-4 недели)
- [x] Авторизация / Регистрация
- [x] Профиль пользователя
- [x] Marketplace Keys (базовый)
- [ ] Парсинг URL (Playwright)
- [ ] Products (CRUD)
- [ ] Dashboard (статистика)

## Этап 2: Автоматизация (4-6 недель)
- [ ] API интеграция (WB, Ozon)
- [ ] Repricing (автоценообразование)
- [ ] Celery задачи (фон)
- [ ] Notifications (Email, Telegram)
- [ ] Billing (ЮKassa)

## Этап 3: AI и Аналитика (6-8 недель)
- [ ] AI Assistant (OpenAI)
- [ ] Analytics (графики)
- [ ] Price History
- [ ] Import/Export

## Этап 4: Масштабирование (8-12 недель)
- [ ] Partners (рефералка)
- [ ] Calendar (события)
- [ ] Advanced Analytics
- [ ] Mobile App (опционально)

---

# 🎯 СЛЕДУЮЩИЕ ШАГИ

1. **Выбрать приоритетные инструменты** для реализации
2. **Настроить инфраструктуру** (VPS, домен, SSL)
3. **Подключить платежную систему** (ЮKassa)
4. **Реализовать парсинг** (Playwright + прокси)
5. **Интегрировать AI** (OpenAI API)
6. **Запустить бета-тест** с реальными пользователями

---

**Готов приступить к реализации любого инструмента! Какой начинаем? 🦈**
