# MegaSharkAI: детальная сводка по проекту

Дата обзора: 16.06.2026

Документ составлен по результатам просмотра структуры репозитория, исходного кода backend, frontend, инфраструктуры и существующей документации. Секретные значения из `.env` и тестовые пароли в этот документ намеренно не перенесены.

## 1. Краткое резюме

MegaSharkAI - монорепозиторий AI-ассистента для продавцов маркетплейсов. Проект помогает анализировать товары и конкурентов, парсить карточки, хранить историю цен, рассчитывать рекомендации по репрайсингу, работать с AI-провайдерами, управлять API-ключами маркетплейсов, уведомлениями, календарём акций, тарифами и чатом поддержки.

Фактически в проекте уже есть:

- FastAPI backend с REST API, WebSocket для чата, SQLAlchemy-моделями и интеграциями с PostgreSQL/Redis.
- SvelteKit frontend с личным кабинетом, страницами авторизации, dashboard, товарами, парсингом, AI, репрайсингом, календарём, уведомлениями, импортом, биллингом, профилем и поддержкой.
- Docker Compose окружение для development, которое поднимает PostgreSQL + pgvector, Redis, backend и frontend.
- Production compose с backend, Celery worker/beat, Flower, Nginx и ограничением доступа к БД/Redis.
- Документация по запуску, деплою, парсингу, тестовым сценариям и функциональным планам.

Ключевые ограничения текущего состояния:

- `widget/` сейчас пустой, встраиваемый виджет как отдельный продукт не реализован.
- Часть Celery-задач является каркасом с `TODO`, особенно аналитика, отчёты и полноценный фоновый репрайсинг.
- Billing API частично использует первого пользователя из БД вместо текущего авторизованного пользователя.
- Production-документация упоминает Alembic-миграции и готовность к продакшену, но фактический runtime backend в dev использует `Base.metadata.create_all`, а часть миграционной структуры не была подтверждена в текущем обзоре.
- В коде есть места с хранением чувствительных данных в БД без полноценного продакшен-подхода к секретам, например AI-настройки сохраняются в таблицу открытым текстом.
- Тесты есть, но часть тестовых ожиданий выглядит устаревшей относительно текущей авторизации и response-моделей.

## 2. Технологический стек

| Зона | Технологии |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 async, Pydantic v2, Uvicorn |
| Очереди и кэш | Celery, Redis, Flower |
| База данных | PostgreSQL 16, pgvector |
| Парсинг | Playwright, httpx, ротация User-Agent и прокси |
| AI-интеграции | Yandex GPT, OpenAI, DeepSeek через HTTP API |
| Frontend | SvelteKit 2, Svelte 4, TypeScript, Vite 5 |
| UI и стили | Tailwind CSS, CSS variables, bits-ui, lucide-svelte, shadcn-подход |
| Графики | Chart.js |
| Инфраструктура | Docker, Docker Compose, Nginx |
| Тесты | pytest, pytest-asyncio, pytest-cov, FastAPI TestClient |

## 3. Структура монорепозитория

```text
MegaSharkAI/
├── backend/                 # FastAPI, Celery, модели, сервисы, тесты
├── frontend-app/            # SvelteKit личный кабинет
├── widget/                  # Сейчас пустая директория для будущего виджета
├── docs/                    # Дополнительная документация
├── nginx/                   # Конфигурация reverse proxy для production
├── docker-compose.yml       # Development compose
├── docker-compose.prod.yml  # Production compose
├── README.md                # Основное описание
├── README_RUN.md            # Документация по запуску и функциям
├── DEPLOYMENT.md            # Инструкция развёртывания
├── STATUS.md                # Исторический статус разработки
├── IMPLEMENTATION_STATUS.md # Исторический статус реализованных функций
├── FINAL_REPORT.md          # Итоговый отчёт по части работ
└── AGENTS.md                # Инструкции для AI-агентов проекта
```

Важная особенность структуры: в `backend/` присутствует локальный `venv`, а в `frontend-app/` - `node_modules` и `.svelte-kit`. При анализе и ревью их лучше исключать, чтобы не смешивать исходники проекта с установленными зависимостями и генерируемыми файлами.

## 4. Backend

### 4.1 Точка входа

Основное приложение находится в `backend/app/main.py`.

Что делает `main.py`:

- Создаёт `FastAPI` приложение с названием и версией из `settings`.
- Подключает CORS middleware.
- Добавляет middleware времени обработки запроса и служебных заголовков.
- Добавляет middleware логирования входящих запросов и ответов.
- На startup:
  - инициализирует таблицы БД через `init_db()`;
  - подключает Redis cache;
  - инициализирует пул прокси из `PROXY_LIST`;
  - инициализирует email-сервис.
- На shutdown закрывает Redis cache.
- Регистрирует health endpoints:
  - `GET /health`;
  - `GET /health/db`;
  - `GET /health/redis`.
- Подключает REST API v1 по префиксу `/api/v1`.
- Отдельно подключает `marketplace_keys_router`.
- Подключает WebSocket router по `/ws`.

Потенциальный риск: middleware логирует все headers и может писать в логи чувствительные заголовки вроде `Authorization`. Для production это стоит ограничить.

### 4.2 Конфигурация

Основные настройки находятся в `backend/app/config.py`.

Ключевые группы настроек:

- Приложение: `app_name`, `app_version`, `debug`.
- PostgreSQL: пользователь, пароль, host, port, db, computed `database_url`.
- Redis/Celery: `redis_host`, `redis_port`, `redis_db`, computed `redis_url`, `celery_broker`, `celery_backend`.
- AI: `yandex_gpt_api_key`, `yandex_cloud_folder_id`, `deepseek_api_key`, `openai_api_key`.
- Парсинг: `playwright_browser`, `parsing_timeout`, `proxy_list`.
- Безопасность: `secret_key`, `SECRET_KEY`, `access_token_expire_minutes`, `encryption_key`, `ENCRYPTION_KEY`.
- Email: SMTP host, port, user, password, from email, TLS.
- CORS: `cors_origins`.

Важный момент: значения по умолчанию подходят для разработки, но не для production. Особенно это касается `SECRET_KEY`, `POSTGRES_PASSWORD`, `ENCRYPTION_KEY`, `DEBUG` и CORS.

### 4.3 База данных

База настраивается в `backend/app/core/database.py`.

Используется:

- `create_async_engine` с `asyncpg`.
- `async_sessionmaker`.
- Dependency `get_db()` для FastAPI endpoints.
- `init_db()`, который вызывает `Base.metadata.create_all`.
- `check_db_connection()` через `SELECT 1`.

Модельная база:

- `Base` объявлена в `core/database.py`.
- `BaseModel` в `backend/app/models/base.py` добавляет integer `id`, `created_at`, `updated_at`.
- Некоторые модели, например `User`, `MarketplaceKey`, `Tariff`, переопределяют `id` на UUID.

Риск/долг:

- `create_all` удобен для MVP, но для production лучше управлять схемой через Alembic-миграции.
- В документах есть упоминания Alembic, но фактический startup использует `create_all`.
- Нужно проверить, что все модели импортируются до `Base.metadata.create_all`, иначе таблицы могут не создаться.
- По результатам дополнительного обзора Alembic выглядит фактически неиспользуемым: production command запускает `alembic upgrade head`, но миграции требуют проверки на наличие реальных операций, а не пустых `pass`.
- Есть ручные/служебные скрипты для схемы чата, поэтому нужно зафиксировать один официальный способ изменения БД.

### 4.4 API v1

Центральный роутер находится в `backend/app/api/v1/router.py`.

Подключённые модули:

- `/auth` - аутентификация, профиль, сброс пароля.
- `/parsing` - парсинг товаров и получение своих товаров через API маркетплейса.
- `/ai` - генерация SEO-названий, анализ конкурентов, настройки провайдеров.
- `/products` - список, детали, статистика, импорт/экспорт, история цен.
- `/notifications` - уведомления и настройки уведомлений.
- `/repricing` - расчёт цены и пользовательские настройки репрайсинга.
- `/calendar` - календарь распродаж и экспорт.
- `/billing` - тарифы и подписки.
- `/chat` - REST API чата поддержки.

Отдельно в `main.py` подключается:

- `/api/v1/marketplace-keys` - управление API-ключами маркетплейсов.

### 4.5 Аутентификация

Файл: `backend/app/api/v1/auth.py`.

Реализовано:

- `POST /api/v1/auth/register` - регистрация пользователя.
- `POST /api/v1/auth/login` - OAuth2 password login, выдача JWT.
- `GET /api/v1/auth/me` - текущий пользователь.
- `GET /api/v1/auth/me/admin` - проверка superuser.
- `PUT /api/v1/auth/profile` - обновление профиля.
- `POST /api/v1/auth/change-password` - смена пароля.
- `POST /api/v1/auth/reset-password-request` - запрос сброса пароля.
- `POST /api/v1/auth/reset-password-confirm` - подтверждение сброса.

Используются:

- `OAuth2PasswordBearer`.
- `python-jose` для JWT.
- `passlib/bcrypt` для хеширования.
- `get_current_user` и `get_current_superuser`.

Наблюдения:

- В `auth.py` есть локальный `get_current_user`, а в некоторых других файлах импортируется `get_current_user` из `app.services.auth_service`. Нужно держать один источник истины, иначе легко получить расхождения.
- Это не только технический долг, а потенциальная runtime-проблема: разные auth helpers могут ожидать разные JWT claims (`sub` как UUID или email). Endpoints, которые импортируют auth из разных мест, нужно проверить единым smoke-тестом после логина.
- При логине есть подробные логи, включая факт наличия пароля. Сам пароль не логируется, но production-логирование стоит сделать более аккуратным.

### 4.6 Пользователи

Файл: `backend/app/models/user.py`.

Поля:

- `id` UUID.
- `email`, `hashed_password`, `full_name`.
- `is_active`, `is_superuser`.
- `is_marketplace_seller`.
- `marketplace_api_key`.
- `marketplace_tokens` как строка JSON.
- `settings` как строка JSON.
- `created_at`, `updated_at`.

Связи:

- `subscriptions` с `UserSubscription`.
- `marketplace_keys` с `MarketplaceKey`.
- `chat_conversations`, `chat_conversations_admin`, `chat_messages`.

Риск:

- Старые поля `marketplace_api_key`, `marketplace_tokens` и новая таблица `MarketplaceKey` частично дублируют смысл. Лучше оставить один основной путь хранения ключей.

### 4.7 Товары и цены

Файл: `backend/app/models/product.py`.

Основные модели:

- `Product`.
- `PriceHistory`.
- `CompetitorAnalysis`.

`Product` хранит:

- external ID маркетплейса;
- marketplace;
- name, description;
- price, old_price, discount;
- rating, reviews_count, sales_count;
- category, brand;
- images, characteristics;
- флаг `is_competitor`;
- owner `user_id`;
- url;
- `last_parsed_at`;
- `vector_embedding` размерности 768 через pgvector.

Индексы:

- уникальный индекс `marketplace + external_id`;
- индекс `user_id + is_competitor`;
- ivfflat index по `vector_embedding`.

Важно: уникальность по `marketplace + external_id` глобальная, без `user_id`. Если два пользователя добавят один и тот же товар, возможен конфликт владения или перезапись `user_id` при UPSERT. Для многопользовательского SaaS это стоит пересмотреть.

### 4.8 Products API

Файл: `backend/app/api/v1/products.py`.

Ключевые возможности:

- `GET /api/v1/products/list` - список товаров текущего пользователя с поиском, фильтром marketplace, фильтром свои/конкуренты, сортировкой и пагинацией.
- `GET /api/v1/products/{product_id}` - детали товара текущего пользователя.
- `GET /api/v1/products/stats/summary` - статистика по товарам за период.
- `DELETE /api/v1/products/{product_id}` - удаление товара.
- `GET /api/v1/products/{product_id}/price-history` - история цены.
- `GET /api/v1/products/export` - экспорт.
- `POST /api/v1/products/import` - импорт Excel.
- `GET /api/v1/products/import/template` - шаблон импорта.

Реализованные ограничения:

- Фильтрация товаров по `current_user.id`.
- Валидация marketplace через `ALLOWED_MARKETPLACES`.
- Сортировка только по разрешённым полям.

Наблюдение:

- Excel-функции зависят от `openpyxl`.
- Массовые операции на frontend заявлены, но нужно проверить соответствующие backend endpoints для полного bulk update/delete.

### 4.9 Парсинг

Основные файлы:

- `backend/app/api/v1/parsing.py`.
- `backend/app/services/parser.py`.
- `backend/app/services/proxy_pool.py`.
- `backend/app/services/marketplace_api.py`.
- `backend/app/tasks/parsing.py`.

REST API:

- `POST /api/v1/parsing/parse-url` - парсинг товара по URL.
- `POST /api/v1/parsing/my-products` - получение своих товаров через API маркетплейса.
- `GET /api/v1/parsing/proxy-stats` - статистика прокси.
- `GET /api/v1/parsing/test-parser` - тест парсера.

Поддержка marketplace:

- Wildberries.
- Ozon.
- Яндекс Маркет.
- Avito.
- В коде парсера также упоминаются `aliexpress` и `kaspi`, но основной endpoint-документ фокусируется на четырёх площадках.

Особенности `parse-url`:

- Определяет marketplace по URL.
- Использует `MarketplaceParser`.
- Делает до 3 попыток.
- Для WB/Ozon использует прокси не во всех попытках, последняя может идти без прокси.
- Имеет внутренний timeout Playwright и внешний абсолютный timeout.
- Допускает partial-результаты без цены.
- Не затирает старую цену в БД, если новый результат без цены.
- Сохраняет товар через PostgreSQL `INSERT ... ON CONFLICT DO UPDATE`.
- Добавляет записи в `PriceHistory`.

Риски:

- URL-парсинг маркетплейсов нестабилен по природе: селекторы могут ломаться, маркетплейсы блокируют автоматизацию.
- В `services/parser.py` много логики и fallback-веток, файл большой; его стоит постепенно разделить по marketplace.
- Для Ozon Seller API в `marketplace_api.py` указан пустой `Client-Id`, без него реальная интеграция Ozon обычно не будет полноценно работать.

### 4.10 AI

Основные файлы:

- `backend/app/api/v1/ai.py`.
- `backend/app/services/ai_service.py`.
- `backend/app/models/ai_settings.py`.

REST API:

- `POST /api/v1/ai/generate-seo-title`.
- `POST /api/v1/ai/analyze-competitors`.
- `GET /api/v1/ai/provider`.
- `POST /api/v1/ai/test`.
- `POST /api/v1/ai/settings`.
- `GET /api/v1/ai/settings`.

AIService:

- Определяет доступного провайдера по ключам.
- Приоритет fallback-цепочки: Yandex GPT, OpenAI, DeepSeek.
- Возвращает fallback-текст, если провайдеров нет или все упали.
- Генерирует SEO-названия.
- Анализирует конкурентов.

Сильная сторона:

- Сервис не падает полностью без API-ключей, а возвращает fallback.

Риски:

- `AISettings` хранит API-ключи в БД как строки без шифрования.
- `POST /ai/settings` не привязан к пользователю и работает с первой записью настроек, то есть это скорее глобальные настройки.
- Для SaaS лучше делать пользовательские настройки AI с шифрованием и разграничением доступа.

### 4.11 Ключи маркетплейсов

Основные файлы:

- `backend/app/api/v1/marketplace_keys.py`.
- `backend/app/models/marketplace_key.py`.
- `backend/app/crud/marketplace_key.py`.
- `backend/app/schemas/marketplace_key.py`.
- `backend/app/services/encryption.py`.
- `backend/app/services/marketplace_api.py`.

REST API:

- `GET /api/v1/marketplace-keys`.
- `POST /api/v1/marketplace-keys`.
- `DELETE /api/v1/marketplace-keys/{key_id}`.
- `POST /api/v1/marketplace-keys/{key_id}/check`.

Поведение:

- Ключи привязаны к пользователю.
- При создании ключ проверяется через API marketplace.
- Ключ сохраняется зашифрованным.
- При выдаче наружу возвращается маскированное значение.

Риск:

- `EncryptionService` генерирует ключ, если `ENCRYPTION_KEY` не задан. После рестарта такие данные может быть невозможно расшифровать. Для production `ENCRYPTION_KEY` должен быть стабильным и защищённым.

### 4.12 Уведомления и пользовательские настройки

Файлы:

- `backend/app/api/v1/notifications.py`.
- `backend/app/models/notification.py`.

REST API:

- `GET /api/v1/notifications/`.
- `POST /api/v1/notifications/mark-read/{notification_id}`.
- `POST /api/v1/notifications/mark-all-read`.
- `GET /api/v1/notifications/unread-count`.
- `GET /api/v1/notifications/settings`.
- `POST /api/v1/notifications/settings`.

Модели:

- `Notification` - уведомления пользователя.
- `UserSettings` - настройки уведомлений, репрайсинга и автообновления.

Поддерживаемые настройки:

- email notifications;
- telegram notifications;
- telegram chat ID;
- strategy/target margin для репрайсинга;
- night repricing flags;
- auto update flags.

Риск:

- Telegram/email настройки сохраняются, но полноценная отправка уведомлений через Telegram не прослеживается как законченный поток.

### 4.13 Репрайсинг

Файл: `backend/app/api/v1/repricing.py`.

REST API:

- `POST /api/v1/repricing/calculate`.
- `POST /api/v1/repricing/strategies`.
- `GET /api/v1/repricing/strategies` или аналогичный endpoint в файле для получения настроек/стратегий.

Стратегии:

- `aggressive` - 95% от минимальной цены конкурента.
- `margin_protection` - средняя цена конкурентов + целевая маржа.
- `night` - 90% от текущей цены.
- `balanced` - среднее между минимальной и средней ценой конкурентов.

Особенности:

- Если конкурентные цены не переданы, backend пытается подобрать их автоматически из товаров-конкурентов текущего пользователя.
- Цены округляются в “маркетплейсный” вид вроде `1999`.
- Настройки пользователя сохраняются в `UserSettings`.

Долг:

- Celery-задачи реального применения репрайсинга в `backend/app/tasks/repricing.py` пока являются заглушками.
- Не видно полноценной интеграции с API маркетплейса для фактического обновления цен на площадках.

### 4.14 Календарь распродаж

Файлы:

- `backend/app/api/v1/calendar.py`.
- `backend/app/models/notification.py`, модель `SaleCalendar`.

REST API:

- `GET /api/v1/calendar/`.
- `POST /api/v1/calendar/`.
- `PUT /api/v1/calendar/{event_id}`.
- `DELETE /api/v1/calendar/{event_id}`.
- `GET /api/v1/calendar/upcoming`.
- `GET /api/v1/calendar/export/{type}`.

Возможности:

- Глобальные события и пользовательские события.
- Фильтрация по marketplace, event type, датам, status.
- Повторяющиеся события: daily, weekly, monthly.
- Экспорт календаря.
- Проверка прав: пользователь может редактировать только свои неглобальные события.

### 4.15 Billing

Файлы:

- `backend/app/api/v1/billing.py`.
- `backend/app/models/tariff.py`.
- `backend/app/services/tariff_service.py`.

REST API:

- `GET /api/v1/billing/list`.
- `GET /api/v1/billing/current`.
- `POST /api/v1/billing/subscribe`.
- `DELETE /api/v1/billing/cancel`.

Модели:

- `Tariff`.
- `UserSubscription`.

Реализовано:

- Список активных тарифов.
- Текущая подписка.
- Активация trial.
- Отмена подписки.

Критический долг:

- `current_user: User = Depends(lambda: None)` и последующий выбор первого пользователя из БД означает, что billing endpoints не используют реальную авторизацию. Это нужно исправить до production.

### 4.16 Чат поддержки

Файлы:

- `backend/app/api/v1/chat.py`.
- `backend/app/websocket/chat.py`.
- `backend/app/websocket/manager.py`.
- `backend/app/models/chat.py`.
- `backend/app/crud/chat.py`.
- `backend/app/schemas/chat.py`.

REST API:

- `POST /api/v1/chat/conversations`.
- `GET /api/v1/chat/conversations`.
- `GET /api/v1/chat/conversations/{conversation_id}`.
- `POST /api/v1/chat/conversations/{conversation_id}/messages`.
- `GET /api/v1/chat/admin/conversations`.
- `POST /api/v1/chat/admin/conversations/{conversation_id}/assign`.
- `POST /api/v1/chat/admin/conversations/{conversation_id}/close`.
- `POST /api/v1/chat/admin/conversations/{conversation_id}/status`.

WebSocket:

- `WS /ws/chat?token=...&conversation_id=...`.

Возможности:

- Пользователь создаёт обращение.
- Пользователь видит свои чаты.
- Админ видит все/назначенные чаты.
- Поддержаны статусы: waiting response, in progress, answered, closed.
- Реальное время через WebSocket.
- Fallback отправки через HTTP.
- Есть typing events.

Риски:

- WebSocket принимает JWT в query string. Это удобно, но URL может попадать в access logs. Для production лучше рассмотреть cookie/session или первый auth message без query token.

### 4.17 Celery

Файл конфигурации: `backend/app/celery_app.py`.

Настроено:

- Redis broker/backend.
- JSON serialization.
- `task_acks_late`, `task_reject_on_worker_lost`, `task_track_started`.
- soft/time limits.
- autoretry.
- Beat schedule:
  - парсинг конкурентов каждые 6 часов;
  - ночной репрайсинг в 03:00;
  - ежедневные отчёты в 08:00;
  - обновление календаря раз в неделю.

Подключённые задачи:

- `app.tasks.parsing`.
- `app.tasks.analytics`.
- `app.tasks.repricing`.
- `app.tasks.reports`.

Фактическое состояние задач:

- `tasks/parsing.py` содержит рабочие задачи для запуска Playwright-парсера, но периодический `parse_competitors` пока с TODO.
- `tasks/repricing.py` содержит стратегии как задачи, но логика применения не реализована.
- `tasks/analytics.py` содержит TODO для обновления календаря и анализа конкурентов.
- `tasks/reports.py` содержит TODO для ежедневных отчётов, PDF/HTML/XLSX генерации и Excel export.

### 4.18 Тесты backend

Файлы:

- `backend/tests/test_api.py`.
- `backend/tests/conftest.py`.
- Дополнительно в корне `backend/` есть `test_chat_api.py`, `test_token.py`.

Покрыто:

- Health endpoints.
- Root endpoint.
- Регистрация и логин с ошибочными данными.
- AI provider и генерация SEO title без auth.
- Извлечение external ID из URL для WB/Ozon/Yandex/Avito.
- Products list и stats.

Проблемы:

- Тесты Products endpoints вызывают защищённые endpoints без токена, при текущей реализации они могут получать 401 вместо 200.
- Тест регистрации ожидает `email` и `id` на верхнем уровне ответа, но текущий `register` возвращает `access_token`, `token_type`, `user`.
- Тесты выглядят как исторические и требуют актуализации.

## 5. Frontend

### 5.1 Общая архитектура

Frontend находится в `frontend-app/`.

Стек:

- SvelteKit.
- TypeScript.
- Vite dev server.
- Tailwind CSS.
- CSS variables для dark/light themes.
- `localStorage` для JWT и темы.
- Fetch API для REST.
- WebSocket для чата.

Vite proxy в `frontend-app/vite.config.ts`:

- `/api` проксируется на backend.
- `/ws` проксируется на backend с `ws: true`.
- target задаётся через `VITE_API_PROXY_TARGET`, default `http://localhost:8000`.
- dev server слушает `0.0.0.0:3000` и `strictPort: true`.

### 5.2 Маршруты frontend

Фактические страницы:

```text
src/routes/+page.svelte                         # redirect/loading на dashboard
src/routes/+layout.svelte                       # общий layout приложения
src/routes/(auth)/+layout.svelte                # auth layout
src/routes/(auth)/login/+page.svelte            # вход
src/routes/(auth)/register/+page.svelte         # регистрация
src/routes/(auth)/forgot-password/+page.svelte  # запрос сброса пароля
src/routes/(auth)/reset-password/+page.svelte   # подтверждение сброса
src/routes/(app)/dashboard/+page.svelte         # dashboard
src/routes/(app)/products/+page.svelte          # товары
src/routes/(app)/parsing/+page.svelte           # парсинг
src/routes/(app)/ai/+page.svelte                # AI-инструменты
src/routes/(app)/repricing/+page.svelte         # репрайсинг
src/routes/(app)/calendar/+page.svelte          # календарь
src/routes/(app)/notifications/+page.svelte     # уведомления
src/routes/(app)/import/+page.svelte            # импорт Excel
src/routes/(app)/billing/+page.svelte           # тарифы/подписка
src/routes/(app)/profile/+page.svelte           # профиль и marketplace keys
src/routes/(app)/settings/+page.svelte          # настройки
src/routes/(app)/partners/+page.svelte          # партнёрская страница
src/routes/(app)/admin/chat/+page.svelte        # админский чат поддержки
```

### 5.3 Layout и навигация

Файл: `frontend-app/src/routes/+layout.svelte`.

Реализовано:

- Глобальный импорт `app.css`.
- Определение темы из `localStorage`.
- Загрузка профиля по `/api/v1/auth/me`.
- Определение `isSuperuser`.
- Меню профиля.
- Logout с очисткой токенов.
- Админский polling количества непрочитанных обращений поддержки.
- Sidebar/navigation для app routes.
- Подключение `ChatWidget` для пользователей.

Риск:

- JWT хранится в `localStorage`, что повышает риск XSS-компрометации. Для production SaaS лучше рассмотреть HttpOnly cookies или усилить CSP и sanitization.

### 5.4 Авторизация

Страницы:

- `frontend-app/src/routes/(auth)/login/+page.svelte`.
- `frontend-app/src/routes/(auth)/register/+page.svelte`.
- `forgot-password`.
- `reset-password`.

Login:

- Отправляет `application/x-www-form-urlencoded` на `/api/v1/auth/login`.
- Сохраняет `access_token` и `token_type` в `localStorage`.
- После входа делает `window.location.href = '/dashboard'`.

Register:

- Многошаговая форма:
  - аккаунт;
  - выбор маркетплейсов;
  - ввод API-ключей.
- После регистрации сохраняет token.
- Затем пытается добавить ключи через `/api/v1/marketplace-keys`.
- После успешной регистрации переводит на `/login`.

Наблюдение:

- После регистрации токен сохраняется, но пользователя всё равно отправляют на login. Это можно упростить: либо сразу входить в dashboard, либо не сохранять токен до login.

### 5.5 Dashboard

Файл: `frontend-app/src/routes/(app)/dashboard/+page.svelte`.

По коду frontend dashboard обращается к:

- `/api/v1/products/stats/summary?period=...`.
- `/api/v1/products/list?limit=5`.

Назначение:

- быстрый обзор товаров;
- статистика;
- последние товары;
- динамика/визуализация.

### 5.6 Products

Файл: `frontend-app/src/routes/(app)/products/+page.svelte`.

API:

- `/api/v1/products/list`.
- `/api/v1/products/{id}`.
- `/api/v1/products/{id}/price-history`.
- `/api/v1/products/export`.

Функции:

- таблица товаров;
- поиск;
- фильтр marketplace;
- фильтр own/competitor;
- сортировка;
- просмотр деталей;
- история цены;
- экспорт;
- массовое выделение на UI.

Нужно отдельно проверить backend-поддержку всех bulk-действий, если их планируется включать в production.

### 5.7 Parsing

Файл: `frontend-app/src/routes/(app)/parsing/+page.svelte`.

API:

- `/api/v1/parsing/parse-url`.
- `/api/v1/parsing/my-products`.

Назначение:

- парсинг товара-конкурента по URL;
- загрузка своих товаров через API marketplace.

### 5.8 AI

Файл: `frontend-app/src/routes/(app)/ai/+page.svelte`.

API:

- `/api/v1/ai/provider`.
- `/api/v1/ai/generate-seo-title`.
- `/api/v1/ai/analyze-competitors`.

Дополнительно:

- frontend хранит историю AI-запросов в `localStorage` под ключом `ai-history-v1`.

### 5.9 Repricing

Файл: `frontend-app/src/routes/(app)/repricing/+page.svelte`.

API:

- `/api/v1/products/list?is_own=true&limit=500`.
- `/api/v1/repricing/strategies`.
- `/api/v1/repricing/calculate`.

Функции:

- выбор товара;
- выбор стратегии;
- целевая маржа;
- расчёт рекомендованной цены;
- сохранение настроек.

### 5.10 Calendar

Файл: `frontend-app/src/routes/(app)/calendar/+page.svelte`.

API:

- `/api/v1/calendar/`.
- `/api/v1/calendar/upcoming`.
- `/api/v1/calendar/{id}`.
- `/api/v1/calendar/export/{type}`.

Функции:

- просмотр событий;
- фильтры;
- создание;
- редактирование;
- удаление;
- экспорт;
- повторяющиеся события.

### 5.11 Notifications

Файл: `frontend-app/src/routes/(app)/notifications/+page.svelte`.

API:

- `/api/v1/notifications/`.
- `/api/v1/notifications/unread-count`.
- `/api/v1/notifications/mark-read/{id}`.
- `/api/v1/notifications/mark-all-read`.

Функции:

- список уведомлений;
- фильтр непрочитанных;
- счётчик;
- отметка одного/всех уведомлений как прочитанных.

### 5.12 Profile и Settings

Profile:

- Загружает `/api/v1/auth/me`.
- Управляет marketplace keys:
  - список;
  - добавление;
  - удаление;
  - проверка ключа.
- Обновляет профиль через `/api/v1/auth/profile`.
- Меняет пароль через `/api/v1/auth/change-password`.

Settings:

- Загружает и сохраняет notification settings.
- Показывает AI provider/settings.
- Сохраняет AI settings.
- Тестирует AI provider.

Риск:

- AI settings на backend глобальные и без user scope, а frontend выглядит как пользовательская настройка. Это архитектурное расхождение.

### 5.13 Billing

Файл: `frontend-app/src/routes/(app)/billing/+page.svelte`.

API:

- `/api/v1/billing/list`.

Вероятное назначение:

- отображение тарифов;
- выбор подписки;
- trial/paid flow.

Backend billing ещё требует доработки авторизации.

### 5.14 Chat

Файлы:

- `frontend-app/src/lib/services/chat.ts`.
- `frontend-app/src/lib/components/chat/ChatWidget.svelte`.
- `frontend-app/src/routes/(app)/admin/chat/+page.svelte`.

User widget:

- Загружает текущего пользователя.
- Загружает существующие чаты.
- Создаёт новый чат.
- Загружает сообщения.
- Подключается к WebSocket.
- Отправляет сообщения через WS или HTTP fallback.
- Показывает статус online/offline.
- Реализует reconnect.

Admin page:

- Показывает обращения поддержки.
- Подключается к WS.
- Позволяет отвечать и управлять статусами.

### 5.15 Темы и стили

Файлы:

- `frontend-app/src/app.css`.
- `frontend-app/src/stores/theme.ts`.
- `frontend-app/src/lib/stores/theme.ts`.

Реализовано:

- Dark theme по умолчанию.
- Light theme через `.light` и `data-theme`.
- CSS variables для цветов.
- Tailwind utility classes.
- Градиенты, glow shadow, анимации.
- Сохранение темы в `localStorage`.

Наблюдение:

- Есть два файла theme store в разных путях: `src/stores/theme.ts` и `src/lib/stores/theme.ts`. Нужно проверить, оба ли нужны.

## 6. Widget

Директория `widget/` существует, но файлов внутри не обнаружено.

Текущий статус:

- Отдельный встраиваемый widget не реализован.
- Внутренний чат-виджет реализован внутри `frontend-app` как `ChatWidget.svelte`, но это не то же самое, что внешний embed-widget для сторонних сайтов.

Если нужен настоящий widget, потребуется:

- отдельная сборка;
- публичный JS snippet;
- изоляция стилей;
- API авторизации/идентификации клиента;
- документация по подключению;
- CORS и rate limiting под публичный сценарий.

## 7. Инфраструктура

### 7.1 Development Docker Compose

Файл: `docker-compose.yml`.

Сервисы:

- `db`
  - image `pgvector/pgvector:pg16`;
  - container `megashark_db`;
  - port `5432:5432`;
  - healthcheck `pg_isready`.
- `redis`
  - image `redis:7-alpine`;
  - container `megashark_redis`;
  - port `6379:6379`;
  - appendonly yes;
  - healthcheck `redis-cli ping`.
- `backend`
  - build `./backend`;
  - container `megashark_backend`;
  - env file `./backend/.env`;
  - `POSTGRES_HOST=db`;
  - `REDIS_HOST=redis`;
  - volume `./backend:/app`;
  - port `8000:8000`;
  - command `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`.
- `frontend`
  - build `./frontend-app`;
  - container `megashark_frontend`;
  - volume `./frontend-app:/app`;
  - port `3000:3000`;
  - `VITE_API_PROXY_TARGET=http://backend:8000`.

Фактическая проверка запуска на 16.06.2026:

- `megashark_db` работает и healthy.
- `megashark_redis` работает и healthy.
- `megashark_backend` работает на `localhost:8000`.
- `megashark_frontend` работает на `localhost:3000`.
- Swagger доступен на `http://localhost:8000/docs`.

### 7.2 Production Docker Compose

Файл: `docker-compose.prod.yml`.

Сервисы:

- `db` с localhost-bound портом и production volume.
- `redis` с password и localhost-bound портом.
- `backend` с `./backend/.env.production`, workers=4 и командой `alembic upgrade head && uvicorn ...`.
- `celery_worker`.
- `celery_beat`.
- `nginx`.
- `flower`.

Сильные стороны:

- БД и Redis не выставляются наружу.
- Есть отдельные worker/beat.
- Есть resource limits.
- Nginx проксирует API, WebSocket и frontend service.
- Flower вынесен в optional profile `monitoring`, доступен только локально и требует basic auth.

Риски:

- Нужно убедиться, что `backend/.env.production` существует и не содержит placeholder-значений.
- Нужно подтвердить наличие Alembic конфигурации и миграций, иначе production command может упасть.
- Frontend production для MVP сейчас запускается отдельным service через `npm run build && npm run preview`; для high-load production лучше перейти на явный SvelteKit adapter (`adapter-node` или `adapter-static`).
- Prod Redis запускается с `--requirepass`; backend/cache/Celery получают `REDIS_PASSWORD`, а явные `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` в шаблоне оставлены пустыми, чтобы не потерять пароль.
- PostgreSQL и Redis больше не публикуются наружу в production compose.

### 7.3 Dockerfile backend

Файл: `backend/Dockerfile`.

Особенности:

- База `python:3.12-slim`.
- Установка `libpq5`, `curl`, `git`.
- Установка `requirements.txt`.
- Установка Playwright Chromium и deps.
- `EXPOSE 8000`.
- Default command `uvicorn app.main:app`.

### 7.4 Dockerfile frontend

Файл: `frontend-app/Dockerfile`.

Особенности:

- База `node:20-alpine`.
- `npm install`.
- Копирование исходников.
- `EXPOSE 3000`.
- Запуск `npm run dev -- --host 0.0.0.0`.

Для production это dev-server Dockerfile. Если нужен production frontend container, лучше сделать build stage и serve статики через Nginx или SvelteKit adapter под выбранный runtime.

### 7.5 Nginx

Файл: `nginx/nginx.conf`.

Реализовано:

- Gzip.
- Access/error logs.
- API rate limiting `10r/s`.
- Connection limiting.
- Upstream `backend:8000`.
- Static frontend from `/usr/share/nginx/html`.
- API proxy `/api/`.
- Health proxy `/health`.
- Swagger `/docs`.
- Блокировка dotfiles.
- Заготовка HTTPS server закомментирована.

Нужно добавить/проверить:

- WebSocket proxy для `/ws`, если чат должен работать через production Nginx.
- HTTPS block с реальными сертификатами.
- Security headers.
- Ограничение `/docs` в production.
- Корректную отдачу frontend build и fallback для SPA после выбора production adapter.

## 8. Документация

Основные документы:

- `README.md` - краткий обзор, стек, структура, быстрый старт.
- `README_RUN.md` - подробный запуск и сценарии использования.
- `DEPLOYMENT.md` - development и production deployment.
- `PRODUCTION_READY.md` - чеклист готовности.
- `STATUS.md` - исторический статус MVP.
- `IMPLEMENTATION_STATUS.md` - исторический статус реализации функций.
- `FINAL_REPORT.md` - итоговый отчёт по реализованным функциям.
- `docs/PARSING_GUIDE.md` - подробности парсинга и прокси.
- `docs/MEGASHARK_FULL_FEATURES.md` - широкий продуктовый план и описание функций.
- `docs/TEST_ACCOUNTS.md` - тестовые аккаунты и сценарии.

Расхождения:

- Некоторые документы говорят о “готовности к production” на 85-90%, но код показывает критичные TODO и места с временной логикой.
- `STATUS.md` отмечает тесты как 0%, но в `backend/tests` тесты уже есть.
- `FINAL_REPORT.md` говорит о массовых операциях как готовых, но backend поддержку bulk endpoints нужно отдельно подтвердить.
- `README.md` упоминает Flower на `localhost:5555`, но в development compose Flower не поднимается.
- Документы могут содержать тестовые учётные данные; их не стоит переносить в публичную документацию или внешние артефакты.

## 9. Безопасность

Что уже есть:

- JWT auth.
- Хеширование паролей.
- CORS config.
- `.env` подход для секретов.
- Шифрование marketplace API keys.
- Маскирование marketplace keys в API.
- Nginx rate limiting в production config.
- Ограничение БД/Redis портов в production compose на localhost.

Основные риски:

- JWT хранится во frontend `localStorage`.
- Для `(app)`-страниц нет централизованных route guards на уровне SvelteKit. Доступ в итоге ограничивает backend, но пользователь может открыть защищённый URL и получить пустые/ошибочные состояния на клиенте.
- WebSocket token передаётся в query string.
- `AISettings` хранит AI API keys без шифрования и без user scope.
- Если `ENCRYPTION_KEY` не задан, ключ шифрования генерируется при старте и может сделать старые данные нечитаемыми после рестарта.
- `SECRET_KEY` имеет небезопасное значение по умолчанию.
- В debug режиме CORS разрешает все origin.
- Логи backend включают headers запроса.
- `/health/redis` сейчас стоит воспринимать как неполную проверку: endpoint документирован, но фактическая реализация требует реального ping Redis.
- `frontend-app/static` требует проверки ассетов: в UI есть ссылки на `/logo.png` и favicon, а production build должен отдавать эти файлы без 404.
- В репозитории присутствуют `.env` файлы/упоминания; перед коммитом и деплоем нужно проверить, что секреты не попадут в VCS.

### 9.1 Карта секретов без раскрытия значений

Реальные секреты нельзя переносить в Markdown-документацию, код, README или публичные артефакты. Этот раздел фиксирует только имена переменных, назначение и место хранения. Значения должны оставаться в `.env`, secret manager или защищённых переменных окружения CI/CD.

| Переменная | Назначение | Где хранить | Примечание |
|---|---|---|---|
| `SECRET_KEY` | Подпись JWT-токенов | `backend/.env`, `backend/.env.production`, secret manager | Обязателен уникальный production-ключ |
| `ENCRYPTION_KEY` | Шифрование API-ключей маркетплейсов | Только защищённый env/secret manager | Должен быть стабильным между рестартами |
| `POSTGRES_PASSWORD` | Пароль PostgreSQL | Корневой `.env`, prod env/secret manager | В production заменить default |
| `REDIS_PASSWORD` | Пароль Redis в production | `backend/.env.production` или secret manager | Backend/Celery должны подключаться с этим паролем |
| `YANDEX_GPT_API_KEY` | API-ключ Yandex GPT | `backend/.env` или user secret storage | Не хранить в документации |
| `YANDEX_CLOUD_FOLDER_ID` | Folder ID Yandex Cloud | `backend/.env` | Не секрет уровня API-ключа, но тоже не нужен в публичных docs |
| `DEEPSEEK_API_KEY` | API-ключ DeepSeek | `backend/.env` или user secret storage | Не хранить открытым текстом в БД |
| `OPENAI_API_KEY` | API-ключ OpenAI | `backend/.env` или user secret storage | Не хранить открытым текстом в БД |
| `SMTP_USER` | SMTP-логин | `backend/.env` | Для отправки email |
| `SMTP_PASSWORD` | SMTP-пароль/app password | `backend/.env` или secret manager | Требует ротации при утечке |
| `PROXY_LIST` | Список прокси для парсинга | `backend/.env` | Может содержать логины/пароли прокси |
| Marketplace API keys | Ключи Wildberries/Ozon/Yandex/Avito | Таблица `marketplace_keys` в зашифрованном виде | Выдавать наружу только маскированными |

Рекомендуемый шаблон для документации и примеров:

```env
SECRET_KEY=<generate-secure-random-value>
ENCRYPTION_KEY=<stable-fernet-key>
POSTGRES_PASSWORD=<strong-database-password>
REDIS_PASSWORD=<strong-redis-password>
YANDEX_GPT_API_KEY=<optional-yandex-api-key>
YANDEX_CLOUD_FOLDER_ID=<optional-yandex-folder-id>
DEEPSEEK_API_KEY=<optional-deepseek-api-key>
OPENAI_API_KEY=<optional-openai-api-key>
SMTP_USER=<smtp-login>
SMTP_PASSWORD=<smtp-password-or-app-password>
PROXY_LIST=<proxy1,proxy2,proxy3>
```

Правила обращения с секретами:

- Не коммитить `.env`, рабочие credentials, тестовые пароли и прокси-доступы.
- Не вставлять реальные значения в Markdown, issue, PR, чат или логи.
- Для production хранить секреты в secret manager/переменных окружения сервера.
- При подозрении на утечку сразу ротировать `SECRET_KEY`, `ENCRYPTION_KEY`, AI-ключи, SMTP-пароль, marketplace keys и прокси.
- Перед публикацией документации проверять её поиском по паттернам `KEY`, `PASSWORD`, `TOKEN`, `SECRET`.

## 10. Готовность по модулям

| Модуль | Состояние | Комментарий |
|---|---|---|
| Docker dev | Работает | Стек успешно запускается через `docker compose up -d` |
| Backend health | Работает | `/health`, `/docs` доступны |
| Frontend dev | Работает | Vite доступен на `localhost:3000` |
| Auth | В основном готово | Нужна унификация auth helpers и audit логов |
| Products | В основном готово | Есть list/details/stats/import/export/history |
| Parsing URL | Частично готово | Реальная стабильность зависит от marketplace/proxy |
| Marketplace API | Частично готово | Ozon требует Client-Id, интеграции требуют проверки |
| AI | Частично готово | Есть провайдеры и fallback, но настройки ключей не защищены как надо |
| Repricing | Частично готово | Расчёт есть, фактическое применение цен не завершено |
| Calendar | Хорошо готово | CRUD, фильтры, повторы, экспорт |
| Notifications | Базово готово | Хранение/чтение есть, отправка внешних уведомлений не завершена |
| Billing | Нужна доработка | Нет реальной авторизации в endpoints |
| Chat support | Хорошо готово | REST + WebSocket + user/admin UI |
| Celery | Каркас + часть парсинга | Много задач с TODO |
| Reports/PDF | Не готово | Только зависимости/заготовки |
| Widget | Не готово | Директория пустая |
| Tests | Частично | Есть pytest, но требуется актуализация |
| Production | Частично | Compose/Nginx есть, но нужны проверки миграций, секретов, build flow |

## 11. Запуск проекта

### 11.1 Быстрый запуск всего стека

```powershell
docker compose up -d
```

Проверка:

```powershell
docker compose ps
```

URL:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

### 11.2 Отдельный backend без Docker

```powershell
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Перед этим нужны зависимости:

```powershell
pip install -r requirements.txt
playwright install chromium
```

### 11.3 Отдельный frontend

```powershell
cd frontend-app
npm install
npm run dev
```

### 11.4 Production compose

```powershell
docker compose -f docker-compose.prod.yml up -d
```

Перед production запуском обязательно:

- заменить `SECRET_KEY`;
- задать стабильный `ENCRYPTION_KEY`;
- заменить пароли БД/Redis;
- настроить CORS;
- подготовить SSL;
- проверить Alembic;
- собрать frontend build;
- отключить или защитить Swagger;
- проверить WebSocket через Nginx.

## 12. Тестирование

Backend:

```powershell
cd backend
pytest tests/ -v
```

Frontend:

```powershell
cd frontend-app
npm run check
```

Рекомендуемые ручные smoke-тесты:

- открыть `http://localhost:3000`;
- зарегистрировать нового пользователя;
- войти;
- открыть dashboard;
- добавить marketplace key;
- спарсить тестовый URL;
- посмотреть products list;
- открыть AI page и проверить provider;
- рассчитать repricing для товара;
- создать событие календаря;
- создать чат поддержки;
- проверить Swagger.

Важно: текущие backend tests могут требовать актуализации под текущую авторизацию.

## 13. Рекомендованный порядок дальнейшей доработки

### Приоритет 1: production safety

- Убрать небезопасные defaults для секретов.
- Сделать обязательным стабильный `ENCRYPTION_KEY`.
- Зашифровать AI API keys или хранить их только в защищённом secret storage.
- Перестать логировать headers целиком.
- Унифицировать backend-аутентификацию: один `get_current_user`, один формат JWT claims, единая матрица auth по endpoints.
- Исправить Billing endpoints на `get_current_user`.
- Проверить production Redis auth: URL для Celery/cache должны включать пароль или Redis password должен быть настроен иначе.
- Проверить WebSocket token flow.
- Настроить CORS для конкретных доменов.
- Добавить route guards/redirect для SvelteKit `(app)`-маршрутов.

### Приоритет 2: данные и миграции

- Подтвердить/восстановить Alembic setup.
- Перейти с `create_all` на миграции в production.
- Проверить фактическое содержимое Alembic versions и убрать деструктивные ручные миграционные скрипты из штатного flow.
- Пересмотреть уникальность товара: вероятно нужен индекс `user_id + marketplace + external_id`.
- Разобраться с дублирующими полями marketplace keys в `User`.
- Определить user-scope для AI settings.

### Приоритет 3: функциональная завершённость

- Доделать Celery задачи аналитики, репрайсинга и отчётов.
- Добавить фактическое обновление цен через API marketplace.
- Доделать PDF/HTML/XLSX отчёты.
- Реализовать внешний `widget/`.
- Завершить реальные marketplace API интеграции.

### Приоритет 4: качество и тесты

- Актуализировать backend tests.
- Добавить тесты auth-protected endpoints с JWT.
- Добавить тесты Products import/export.
- Добавить тесты repricing formulas.
- Добавить тесты calendar repeat logic.
- Запустить `npm run check` и исправить Svelte diagnostics.
- Добавить E2E smoke flow.

## 14. Итоговая оценка

Проект находится на стадии развитого MVP/демонстрационного продукта. Основной пользовательский кабинет, backend API, Docker dev окружение и ключевые бизнес-экраны уже есть. При этом production-готовность пока ограничена архитектурными долгами: секреты, миграции, billing auth, фоновые задачи, реальные интеграции marketplace и тестовое покрытие.

Для локальной демонстрации проект уже пригоден. Для коммерческого SaaS запуска нужно сначала закрыть security/data/auth пункты, затем стабилизировать парсинг и завершить фоновые задачи.
