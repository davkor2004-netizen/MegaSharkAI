# 🦈 MegaSharkAI

AI-ассистент для продавцов маркетплейсов: анализирует товары, конкурентов и помогает с ценообразованием.

## 📋 Оглавление

- [Возможности](#-возможности)
- [Технологический стек](#-технологический-стек)
- [Структура проекта](#-структура-проекта)
- [Быстрый старт](#-быстрый-старт)
- [Разработка](#-разработка)
- [API Документация](#-api-документация)

## ✨ Возможности

- 🔍 **AI-аналитика** — Глубокий анализ товаров и конкурентов
- 📊 **Парсинг маркетплейсов** — Wildberries, Ozon, Avito, KazanExpress, Яндекс Маркет
- 💰 **Репрайсинг** — 3 стратегии: агрессивный рост, защита маржи, ночной репрайсинг
- 📈 **Отчёты** — PDF/HTML отчёты по конкурентам, Excel импорт/экспорт
- 📅 **Календарь распродаж** — Планирование акций
- 🤖 **Автоматизация** — Автообновление цен и остатков

## 🛠 Технологический стек

| Компонент | Технология |
|-----------|------------|
| **Бэкенд** | Python 3.12 + FastAPI + Celery |
| **Фронтенд** | SvelteKit + shadcn-svelte |
| **База данных** | PostgreSQL 16 + pgvector |
| **Кэш/Брокер** | Redis 7 |
| **Парсинг** | Playwright |
| **Инфраструктура** | Docker + Docker Compose |

## 📁 Структура проекта

```
MegaSharkAI/
├── backend/           # FastAPI приложение
│   ├── app/
│   │   ├── api/       # API эндпоинты
│   │   ├── core/      # Ядро (БД, конфиг)
│   │   ├── models/    # SQLAlchemy модели
│   │   ├── schemas/   # Pydantic схемы
│   │   ├── services/  # Бизнес-логика
│   │   ├── tasks/     # Celery задачи
│   │   ├── config.py  # Настройки
│   │   └── main.py    # Точка входа
│   ├── tests/         # Тесты
│   ├── Dockerfile
│   └── requirements.txt
├── frontend-app/      # Личный кабинет (SvelteKit)
├── widget/            # Заготовка внешнего embed-widget, сейчас не реализован
├── docker-compose.yml
├── .gitignore
└── README.md
```

## 🚀 Быстрый старт

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd MegaSharkAI
```

### 2. Настройка переменных окружения

```bash
# Скопировать шаблон
cp backend/.env.example backend/.env

# Отредактировать backend/.env и добавить API-ключи
```

### 3. Запуск инфраструктуры

```bash
# Запуск всех сервисов
docker compose up -d

# Просмотр логов
docker compose logs -f backend
```

### 4. Проверка работы

- **API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **Frontend**: http://localhost:3000
- **Flower (Celery мониторинг)**: только если запущен prod/отдельный Flower service

### 5. Health Check

```bash
curl http://localhost:8000/health
# Ответ: {"status": "ok", "service": "MegaSharkAI", "version": "0.1.0"}
```

## 👨‍💻 Разработка

### Запуск бэкенда (без Docker)

```bash
cd backend

# Установка зависимостей
pip install -r requirements.txt

# Установка браузеров Playwright
playwright install

# Запуск сервера
uvicorn app.main:app --reload
```

### Запуск фронтенда

```bash
cd frontend-app

# Установка зависимостей
npm install

# Запуск dev-сервера
npm run dev
```

### Тестирование

```bash
cd backend

# Запуск тестов
pytest

# Запуск с покрытием
pytest --cov=app
```

### Линтинг

```bash
cd backend

# Ruff (быстрый линтер)
ruff check app

# Mypy (проверка типов)
mypy app
```

## 📖 API Документация

После запуска приложения доступна интерактивная документация:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Основные эндпоинты

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| GET | `/health` | Проверка здоровья сервиса |
| GET | `/health/db` | Проверка подключения к БД |
| GET | `/health/redis` | Проверка подключения к Redis |
| GET | `/` | Информация о сервисе |

## 🔐 Безопасность

- Все секретные ключи хранятся в `.env` файле
- `.env` добавлен в `.gitignore`
- В продакшене используйте сложные `SECRET_KEY`
- Не коммитьте `.env` в репозиторий!

## 📝 Лицензия

© 2024 MegaSharkAI Team. Все права защищены.
