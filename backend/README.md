# 🦈 Бэкенд MegaSharkAI

FastAPI приложение для AI-ассистента продавцов маркетплейсов.

## 🚀 Быстрый старт

### 1. Установка Python

Убедись, что установлен **Python 3.12**:
- Скачай с https://www.python.org/downloads/
- ⚠️ **Отметь галочку** "Add Python to PATH" при установке

### 2. Создание виртуального окружения

```powershell
cd backend

# Создание venv
python -m venv venv

# Активация (PowerShell)
.\venv\Scripts\Activate.ps1

# Активация (cmd)
venv\Scripts\activate
```

### 3. Установка зависимостей

```powershell
pip install -r requirements.txt

# Установка браузеров Playwright
playwright install chromium
```

### 4. Настройка окружения

```powershell
# Скопировать шаблон
copy .env.example .env

# Отредактировать .env и добавить API-ключи (если нужны)
```

### 5. Запуск Docker (БД и Redis)

```powershell
# Из корня проекта
docker compose up -d
```

### 6. Запуск бэкенда

```powershell
# Режим разработки (с автоперезагрузкой)
uvicorn app.main:app --reload

# Или через Python
python -m uvicorn app.main:app --reload
```

### 7. Проверка

- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

---

## 📁 Структура

```
backend/
├── app/
│   ├── api/v1/          # API эндпоинты
│   │   ├── parsing.py   # Парсинг маркетплейсов
│   │   ├── ai.py        # AI-функционал
│   │   └── products.py  # Товары
│   ├── core/            # Ядро
│   │   └── database.py  # Подключение к БД
│   ├── models/          # SQLAlchemy модели
│   │   ├── user.py
│   │   └── product.py
│   ├── services/        # Бизнес-логика
│   │   ├── parser.py          # Основной Playwright-парсер маркетплейсов
│   │   ├── parser_service.py  # Legacy-обёртки парсинга (совместимость)
│   │   └── ai_service.py      # AI
│   ├── tasks/           # Celery задачи
│   │   ├── parsing.py
│   │   ├── analytics.py
│   │   ├── repricing.py
│   │   └── reports.py
│   ├── config.py        # Настройки
│   ├── celery_app.py    # Celery конфигурация
│   └── main.py          # Точка входа
├── tests/               # Тесты
├── requirements.txt     # Зависимости
├── Dockerfile
└── .env                 # Переменные окружения
```

---

## 🔑 API Endpoints

### Health

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| GET | `/health` | Проверка сервиса |
| GET | `/health/db` | Проверка БД |
| GET | `/health/redis` | Проверка Redis |

### Парсинг

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| POST | `/api/v1/parsing/wildberries` | Парсинг WB (асинхронно) |
| POST | `/api/v1/parsing/parse-sync` | Парсинг (синхронно) |
| GET | `/api/v1/parsing/status/{id}` | Статус задачи |

### AI

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| POST | `/api/v1/ai/generate-seo-title` | Генерация SEO-названия |
| POST | `/api/v1/ai/analyze-competitors` | Анализ конкурентов |
| GET | `/api/v1/ai/provider` | Текущий AI-провайдер |

### Товары

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| GET | `/api/v1/products` | Список товаров |
| GET | `/api/v1/products/{id}` | Товар по ID |
| GET | `/api/v1/products/stats/summary?period=30d` | Статистика за период (`today`, `7d`, `30d`) |

---

## 🤖 AI Провайдеры

Поддерживаются:

1. **Яндекс GPT**
   - `YANDEX_GPT_API_KEY`
   - `YANDEX_CLOUD_FOLDER_ID`

2. **OpenAI**
   - `OPENAI_API_KEY`

3. **DeepSeek**
   - `DEEPSEEK_API_KEY`

Логика вызова: сервис сначала пытается обратиться к **Яндекс GPT**, при ошибке автоматически переключается на **OpenAI**, затем на **DeepSeek**.

---

## 🧪 Тестирование

```powershell
# Запуск тестов
pytest

# С покрытием
pytest --cov=app

# Линтинг
ruff check app
mypy app
```

---

## 📦 Celery (фоновые задачи)

```powershell
# Worker
celery -A app.celery_app worker --loglevel=info

# Beat (периодические задачи)
celery -A app.celery_app beat --loglevel=info

# Flower (мониторинг)
celery -A app.celery_app flower
```
