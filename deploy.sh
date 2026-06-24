#!/usr/bin/env bash
# ===========================================
# Скрипт автоматического развёртывания MegaSharkAI
# ===========================================
# Использование: ./deploy.sh
# ===========================================

set -e

echo "🦈 MegaSharkAI - Развёртывание"
echo "================================"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker не установлен!${NC}"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose не установлен!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker и Docker Compose найдены${NC}"

# Проверка .env файла
if [ ! -f "backend/.env" ]; then
    echo -e "${YELLOW}⚠️  Файл backend/.env не найден. Копируем из .env.example...${NC}"
    cp backend/.env.example backend/.env
    echo -e "${YELLOW}⚠️  Отредактируйте backend/.env перед продолжением!${NC}"
    exit 1
fi

# Генерация SECRET_KEY если не задан
if grep -q "your-secret-key-change-in-production" backend/.env; then
    echo -e "${YELLOW}⚠️  Генерация SECRET_KEY...${NC}"
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    sed -i "s/your-secret-key-change-in-production/$SECRET_KEY/" backend/.env
    echo -e "${GREEN}✅ SECRET_KEY сгенерирован${NC}"
fi

# Остановка старых контейнеров
echo -e "${YELLOW}🔄 Остановка старых контейнеров...${NC}"
docker compose down || true

# Запуск инфраструктуры
echo -e "${YELLOW}🚀 Запуск PostgreSQL и Redis...${NC}"
docker compose up -d db redis

# Ожидание готовности БД
echo -e "${YELLOW}⏳ Ожидание готовности БД...${NC}"
sleep 5

# Применение миграций
echo -e "${YELLOW}📦 Применение миграций БД...${NC}"
cd backend
python -m alembic upgrade head
cd ..

# Запуск бэкенда (для development)
echo -e "${YELLOW}🚀 Запуск бэкенда...${NC}"
# uvicorn app.main:app --host 0.0.0.0 --port 8000 &

echo -e "${GREEN}✅ Развёртывание завершено!${NC}"
echo ""
echo "📊 Сервисы доступны по адресам:"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   Swagger:  http://localhost:8000/docs"
echo "   Health:   http://localhost:8000/health"
echo ""
echo -e "${YELLOW}⚠️  Не забудьте настроить CORS и SECRET_KEY для продакшена!${NC}"
