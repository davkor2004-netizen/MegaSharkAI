# ===========================================
# Инструкция по развёртыванию MegaSharkAI
# ===========================================

## 📋 Требования

- Docker и Docker Compose
- Минимум 4GB RAM
- 2 CPU ядра
- 20GB свободного места на диске

---

## 🚀 Быстрый старт (Development)

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd MegaSharkAI
```

### 2. Настройка переменных окружения

```bash
# Бэкенд
cp backend/.env.example backend/.env
# Отредактируйте backend/.env под ваши значения
```

### 3. Запуск инфраструктуры

```bash
docker compose up -d db redis
```

### 4. Применение миграций БД

```bash
cd backend
pip install -r requirements.txt
python -m alembic upgrade head
```

### 5. Запуск бэкенда

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Запуск фронтенда

```bash
cd frontend-app
npm install
npm run dev
```

### 7. Проверка

- **Frontend:** http://localhost:3000
- **Backend:** http://localhost:8000
- **Swagger:** http://localhost:8000/docs
- **Health:** http://localhost:8000/health

---

## 🏭 Production развёртывание

### ✅ Обязательный чеклист перед деплоем

Проверить ДО запуска backend:

1. **`ENVIRONMENT=production`** — включает production-режим (отключает Swagger, включает HSTS, запрещает небезопасные defaults).
2. **`DEBUG=false`** — обязателен в production. При `DEBUG=true` приложение остаётся в dev-режиме и автоматически вызывает `create_all` в обход миграций.
3. **`alembic upgrade head` перед запуском backend** — в production схему создаёт только Alembic (`create_all` намеренно отключён при `is_production`).

> Режим определяется так: `is_production = ENVIRONMENT in {production, prod} OR DEBUG=false`. Чтобы `create_all` точно не выполнялся, выставляйте оба пункта 1 и 2.

### 🆕 Только для ЧИСТОЙ production-БД (первый деплой)

Первая (baseline) миграция содержит длинные revision ID, а Alembic по умолчанию создаёт `alembic_version.version_num` как `VARCHAR(32)`. Чтобы запись ревизии не упала с `StringDataRightTruncationError`, создайте таблицу версий заранее — ДО первого `alembic upgrade head`:

```sql
CREATE TABLE alembic_version (
  version_num VARCHAR(128) NOT NULL,
  CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
```

Также убедитесь, что в PostgreSQL доступно расширение **pgvector** — baseline-миграция (`32bc7c876e79`) выполняет:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Для этого пользователь БД должен иметь право `CREATE EXTENSION`, а пакет `pgvector` — быть установлен в инстансе (на managed-Postgres обычно включается в настройках/расширениях).

### 1. Настройка переменных окружения

```bash
# Создайте production .env
cp backend/.env.production backend/.env

# Сгенерируйте безопасные ключи:
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('REDIS_PASSWORD=' + secrets.token_urlsafe(32))"
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"

# Внесите значения в backend/.env.production
```

### 2. Настройка CORS

В `backend/.env` укажите домены вашего приложения:

```bash
CORS_ORIGINS=["https://yourdomain.com", "https://www.yourdomain.com"]
```

### 3. SSL сертификаты (рекомендуется)

```bash
# Создайте директорию для SSL
mkdir -p nginx/ssl

# Получите сертификаты (например, через Let's Encrypt)
# certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Скопируйте сертификаты
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/
```

### 4. Развёртывание через Docker Compose

```bash
# Запуск всех сервисов
docker compose -f docker-compose.prod.yml up -d

# Проверка статус
docker compose -f docker-compose.prod.yml ps

# Просмотр логов
docker compose -f docker-compose.prod.yml logs -f backend
```

PostgreSQL и Redis в production compose не публикуются на host. Доступ к ним идёт только внутри Docker network.

Frontend собирается через `@sveltejs/adapter-node` и запускается боевым Node-сервером (`npm run build && node build`), а Nginx проксирует его. Сервер слушает `HOST`/`PORT` (по умолчанию `0.0.0.0:3000`). Это полноценный production-режим с SSR (в отличие от dev `vite preview`).

### 5. Применение миграций

Миграции применяются автоматически при запуске backend. Для принудительного применения:

```bash
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

---

## 🔧 Управление сервисами

### Просмотр логов

```bash
# Все сервисы
docker compose logs -f

# Отдельный сервис
docker compose logs -f backend
docker compose logs -f db
docker compose logs -f nginx
```

### Перезапуск сервисов

```bash
# Перезапуск всех
docker compose -f docker-compose.prod.yml restart

# Перезапуск отдельного
docker compose -f docker-compose.prod.yml restart backend
```

### Остановка

```bash
docker compose -f docker-compose.prod.yml down
```

### Полная очистка (с удалением данных!)

```bash
docker compose -f docker-compose.prod.yml down -v
```

---

## 📊 Мониторинг

### Flower (Celery мониторинг)

Flower не запускается по умолчанию. Для локального мониторинга включите профиль:

```bash
FLOWER_USER=<user> FLOWER_PASSWORD=<password> \
docker compose -f docker-compose.prod.yml --profile monitoring up -d flower
```

Откройте http://localhost:5555 только с локальной машины/VPN. Не публикуйте Flower наружу.

### Health checks

```bash
# Backend
curl http://localhost:8000/health

# Database
curl http://localhost:8000/health/db

# Redis
curl http://localhost:8000/health/redis
```

---

## 🔐 Безопасность

### Рекомендации для продакшена:

1. **Измените все пароли по умолчанию**
2. **Настройте HTTPS** (обязательно!)
3. **Не публикуйте порты БД и Redis наружу**
4. **Используйте firewall** (UFW, iptables)
5. **Настройте rate limiting** (уже настроен в nginx)
6. **Включите HSTS** после настройки HTTPS
7. **Используйте стабильный ENCRYPTION_KEY и не теряйте его**
8. **Не переопределяйте CELERY_BROKER_URL без Redis-пароля**
9. **Регулярно обновляйте зависимости**

### Firewall настройки (UFW)

```bash
# Разрешить только необходимые порты
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 22/tcp    # SSH (если нужен)

# Включить firewall
ufw enable
```

---

## 📦 Резервное копирование

### База данных

```bash
# Создать дамп
docker compose exec db pg_dump -U megashark megashark_db > backup_$(date +%Y%m%d).sql

# Восстановить из дампа
docker compose exec -T db psql -U megashark megashark_db < backup_20260415.sql
```

### Redis данные

```bash
# Копировать файл данных
cp volumes/redis_data/dump.rdb backup_redis_$(date +%Y%m%d).rdb
```

---

## 🐛 Troubleshooting

### Бэкенд не запускается

```bash
# Проверить логи
docker compose logs backend

# Проверить подключение к БД
docker compose exec backend python -c "from app.config import settings; print(settings.database_url)"
```

### Ошибки миграций

```bash
# Сбросить миграции (ОСТОРОЖНО!)
docker compose exec backend alembic downgrade base
docker compose exec backend alembic upgrade head
```

### Проблемы с CORS

Проверьте `CORS_ORIGINS` в `backend/.env` и убедитесь, что домены совпадают с фронтендом.

---

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи: `docker compose logs -f`
2. Проверьте health endpoints
3. Убедитесь, что все переменные окружения настроены

---

**Версия инструкции:** 1.1  
**Дата обновления:** 2026-06-25
