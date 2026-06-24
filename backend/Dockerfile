# ===========================================
# Dockerfile для бэкенда MegaSharkAI
# ===========================================

# Базовый образ Python 3.12
FROM python:3.12-slim

# Метаданные
LABEL maintainer="MegaSharkAI Team"
LABEL description="AI-ассистент для продавцов маркетплейсов"

# Устанавливаем переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Рабочая директория в контейнере
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Копируем требования и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем браузеры для Playwright и их зависимости
RUN playwright install chromium
RUN playwright install-deps chromium

# Копируем код приложения
COPY . .

# Порт приложения
EXPOSE 8000

# Команда запуска (по умолчанию - uvicorn)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
