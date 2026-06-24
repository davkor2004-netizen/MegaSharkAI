# 🦈 MegaSharkAI — Документация по запуску

## ✅ Выполненные задачи

| № | Задача | Статус | Файлы |
|---|--------|--------|-------|
| 1 | **AI-ключи** | ✅ Готово | `settings/+page.svelte`, `api/v1/ai.py` |
| 2 | **Регистрация/Вход** | ✅ Готово | `auth.py`, `login/+page.svelte`, `register/+page.svelte` |
| 3 | **Таблица товаров** | ✅ Готово | `products/+page.svelte`, `api/v1/products.py` |
| 4 | **Тесты (pytest)** | ✅ Готово | `tests/test_api.py`, `tests/conftest.py` |
| 6 | **Дашборд с графиками** | ✅ Готово | `dashboard/+page.svelte` |
| 7 | **B2B партнёрство** | ✅ Готово | `partners/+page.svelte` |
| 8 | **Экспорт в Excel** | ✅ Готово | `api/v1/products.py` (export) |
| 9 | **История цен** | ✅ Готово | `PriceHistory`, `price-history API` |
| 10 | **Кэширование** | ✅ Готово | `cache_service.py`, Redis |

---

## 🚀 Быстрый старт

### 1. Запуск инфраструктуры

```powershell
docker compose up -d
```

**Проверка:**
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

---

### 2. Запуск бэкенда

```powershell
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**URL:**
- API: http://localhost:8000
- Swagger: http://localhost:8000/docs

---

### 3. Запуск фронтенда

```powershell
cd frontend-app
npm run dev
```

**URL:** http://localhost:3000

---

## 🔑 Настройка AI-ключей

### 1. Откройте настройки

Перейдите на **http://localhost:3000/settings**

### 2. Получите ключи

#### Яндекс GPT (рекомендуется):
1. https://console.cloud.yandex.ru
2. Создайте платежный аккаунт
3. Создайте API-ключ
4. Скопируйте Folder ID

#### DeepSeek (дешевле):
1. https://platform.deepseek.com
2. Зарегистрируйтесь
3. Создайте API-ключ

#### OpenAI (опционально):
1. https://platform.openai.com
2. API Keys → Create new key

### 3. Сохраните и протестируйте

Введите ключи → нажмите **"Сохранить"** → нажмите **"Тест"**

---

## 📋 Регистрация и вход

### Регистрация нового пользователя:

1. Перейдите на **http://localhost:3000/register**
2. Введите:
   - Email (например: `seller@example.com`)
   - Пароль (минимум 6 символов)
   - Полное имя (опционально)
3. Нажмите **"Создать аккаунт"**

### Вход:

1. Перейдите на **http://localhost:3000/login**
2. Введите email и пароль
3. Нажмите **"Войти"**

---

## 📦 Управление товарами

### Страница товаров:

**http://localhost:3000/products**

**Возможности:**
- 🔍 Поиск по названию
- 🏪 Фильтр по маркетплейсу (WB, Ozon, Avito)
- 📋 Фильтр: свои / конкуренты
- 📊 Сортировка по дате, названию, цене
- 🗑️ Удаление товаров

---

## 🤖 AI Генератор названий

**http://localhost:3000/ai**

**Пример использования:**

1. **Название товара:** `Футболка мужская`
2. **Категория:** `Одежда`
3. **Бренд:** `Nike`
4. **Характеристики (JSON):**
   ```json
   {"Материал": "Хлопок", "Цвет": "Белый", "Размер": "L"}
   ```
5. Нажмите **"Сгенерировать название"**

**Результат:**
```
Футболка мужская Nike хлопковая базовая белая размер L
```

---

## 🔍 Парсинг товаров

**http://localhost:3000/parsing**

**Пример URL для теста:**
```
https://www.wildberries.ru/catalog/24319630/detail.aspx
```

**Что парсит:**
- Название товара
- Цена и старая цена
- Скидка (%)
- Рейтинг
- Количество отзывов
- Категория
- Бренд

---

## 🧪 Запуск тестов

```powershell
cd backend

# Установка зависимостей для тестов
pip install pytest pytest-asyncio pytest-cov

# Запуск всех тестов
pytest tests/ -v

# Запуск с покрытием
pytest tests/ -v --cov=app --cov-report=html
```

**Просмотр отчёта:**
```powershell
start htmlcov/index.html
```

---

## 📊 Дашборд

**http://localhost:3000/dashboard**

**Что показывает:**
- 📈 Всего товаров
- 📦 Свои товары (с прогресс-баром)
- 👥 Конкуренты (с прогресс-баром)
- 💰 Средняя цена
- 📊 Распределение по типам
- 📦 Последние 5 товаров

---

## 🛠 Структура проекта

```
MegaSharkAI/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── auth.py       # Аутентификация
│   │   │   ├── ai.py         # AI генерация
│   │   │   ├── parsing.py    # Парсинг
│   │   │   └── products.py   # Товары
│   │   ├── services/
│   │   │   ├── ai_service.py      # AI сервис
│   │   │   └── parser_service.py  # Парсинг
│   │   ├── models/
│   │   │   ├── user.py       # Пользователи
│   │   │   └── product.py    # Товары
│   │   └── main.py           # FastAPI приложение
│   ├── tests/
│   │   ├── test_api.py       # Тесты API
│   │   └── conftest.py       # Конфигурация тестов
│   └── requirements.txt
│
├── frontend-app/
│   └── src/routes/
│       ├── (auth)/
│       │   ├── login/+page.svelte
│       │   └── register/+page.svelte
│       ├── (app)/
│       │   ├── dashboard/+page.svelte
│       │   ├── parsing/+page.svelte
│       │   ├── ai/+page.svelte
│       │   ├── products/+page.svelte
│       │   └── settings/+page.svelte
│       └── +layout.svelte
│
└── docker-compose.yml
```

---

## 🔧 Переменные окружения

### backend/.env:

```env
# Приложение
APP_NAME=MegaSharkAI
DEBUG=true

# База данных
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=megashark_db
POSTGRES_USER=megashark
POSTGRES_PASSWORD=your_password_here

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# AI ключи (можно задать через настройки)
YANDEX_GPT_API_KEY=your_yandex_key
YANDEX_CLOUD_FOLDER_ID=your_folder_id
DEEPSEEK_API_KEY=your_deepseek_key
OPENAI_API_KEY=your_openai_key

# JWT для авторизации
SECRET_KEY=your-secret-key-change-in-production
```

---

## 📝 API Endpoints

### Аутентификация
| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| POST | `/api/v1/auth/register` | Регистрация |
| POST | `/api/v1/auth/login` | Вход (form-data) |
| GET | `/api/v1/auth/me` | Текущий пользователь |

### AI
| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| POST | `/api/v1/ai/generate-seo-title` | Генерация названия |
| POST | `/api/v1/ai/test` | Тест AI |
| POST | `/api/v1/ai/settings` | Сохранение ключей |
| GET | `/api/v1/ai/provider` | Текущий провайдер |

### Парсинг
| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| POST | `/api/v1/parsing/parse-sync` | Синхронный парсинг |

### Товары
| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| GET | `/api/v1/products/list` | Список с фильтрами |
| GET | `/api/v1/products/export` | **Экспорт в Excel** |
| GET | `/api/v1/products/import/template` | **Скачать шаблон импорта Excel** |
| GET | `/api/v1/products/{id}/price-history` | **История цен** |
| GET | `/api/v1/products/stats/summary` | Статистика |
| DELETE | `/api/v1/products/{id}` | Удаление |

### Кэширование
| Эндпоинт | Описание |
|----------|----------|
| Redis | Автоматическое кэширование парсинга (24 часа) |

---

## ❓ Частые проблемы

### 1. Ошибка подключения к БД
```
Solution: Убедитесь, что Docker запущен
docker compose up -d
```

### 2. AI не работает
```
Solution: Настройте ключи в /settings
Или добавьте в backend/.env
```

### 3. Фронтенд не видит бэкенд
```
Solution: Проверьте vite.config.ts
proxy должен указывать на http://localhost:8000
```

### 4. Парсинг не работает
```
Solution: Установите Playwright
cd backend
playwright install
```

---

## 📞 Поддержка

- **Документация API:** http://localhost:8000/docs
- **Email:** support@megasharkai.online
- **Сайт:** https://megasharkai.online

---

## 🎯 Следующие улучшения

- [ ] Интеграция с MPStats API
- [ ] Графики Chart.js на дашборде
- [ ] Экспорт товаров в Excel
- [ ] Уведомления об изменении цен
- [ ] Мобильная версия

---

**MegaSharkAI v0.2.0** 🦈
*AI-ассистент для продавцов маркетплейсов*
