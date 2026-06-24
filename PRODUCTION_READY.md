# 🦈 MegaSharkAI — Production Hardening Status

> Текущий статус: **MVP demo-ready после локальной проверки, но не production-ready**.
> Документ фиксирует, что уже подготовлено, и что обязательно нужно закрыть перед публичным production-запуском.

## Чеклист готовности

### Инфраструктура
- [x] Docker Compose для development
- [x] Docker Compose для production с обязательными secret env
- [x] PostgreSQL + pgvector
- [x] Redis (кэш + Celery broker)
- [x] Nginx (reverse proxy + rate limiting)
- [x] Celery worker + beat
- [x] Frontend production build запускается отдельным service за Nginx для MVP demo
- [ ] Перейти на явный SvelteKit production adapter для high-load production

### База данных
- [x] Alembic конфигурация восстановлена и импортирует все ORM-модели
- [x] Добавлена миграция для user-scoped product uniqueness
- [ ] Проверить и очистить старые пустые/merge migrations перед production
- [ ] Прогнать `alembic upgrade head` на чистой staging БД

### Безопасность
- [x] Startup validation запрещает небезопасный production config
- [x] CORS wildcard запрещён при production-настройках
- [x] Rate limiting (nginx)
- [x] Переменные окружения
- [x] `SECRET_KEY` и `ENCRYPTION_KEY` валидируются для production
- [x] Health check endpoints
- [ ] Перейти с localStorage token storage на HttpOnly cookie или добавить строгий CSP
- [ ] Провести отдельный security review перед публичным запуском

### Мониторинг
- [x] Health check (/health, /health/db, /health/redis)
- [x] Flower вынесен в optional profile `monitoring` и требует basic auth
- [x] Логирование через loguru
- [ ] Централизовать redaction логов во всех интеграциях

### Документация
- [x] DEPLOYMENT.md
- [x] .env.example
- [x] Docker Compose инструкции
- [ ] Синхронизировать все исторические отчёты со статусом MVP

---

## 🚀 Быстрый старт

### Development

```bash
# 1. Запуск инфраструктуры
docker compose up -d db redis

# 2. Применение миграций
cd backend
python -m alembic upgrade head

# 3. Запуск бэкенда
uvicorn app.main:app --reload

# 4. Запуск фронтенда (в другом терминале)
cd frontend-app
npm run dev
```

### Production

```bash
# 1. Настройка .env
cp backend/.env.production backend/.env
# Отредактируйте значения!

# 2. Генерация ключей
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"

# 3. Запуск
docker compose -f docker-compose.prod.yml up -d

# Flower при необходимости
FLOWER_USER=<user> FLOWER_PASSWORD=<password> \
docker compose -f docker-compose.prod.yml --profile monitoring up -d flower

# 4. Проверка
docker compose -f docker-compose.prod.yml logs -f
```

Перед этим обязательно проверьте:

- `DEBUG=false`
- `ENVIRONMENT=production`
- `SECRET_KEY` не равен placeholder/default
- `ENCRYPTION_KEY` задан и стабилен
- `CORS_ORIGINS` содержит только реальные домены
- PostgreSQL/Redis не опубликованы наружу
- Flower не доступен публично
- `/ws` проксируется через Nginx

---

## 📁 Структура файлов

```
MegaSharkAI/
├── docker-compose.yml          # Development
├── docker-compose.prod.yml     # Production
├── DEPLOYMENT.md               # Инструкция по развёртыванию
├── deploy.sh                   # Скрипт автоматического развёртывания
├── nginx/
│   └── nginx.conf              # Конфигурация nginx
├── backend/
│   ├── .env.example            # Шаблон переменных окружения
│   ├── .env.production         # Production переменные
│   ├── alembic/                # Миграции БД
│   ├── app/
│   │   ├── main.py             # FastAPI приложение
│   │   ├── config.py           # Настройки
│   │   └── ...
│   └── Dockerfile
└── frontend-app/
    └── ...
```

---

## 🔐 Checklist перед запуском

### Обязательные действия

- [ ] Изменить `SECRET_KEY` в `.env`
- [ ] Изменить пароли БД и Redis
- [ ] Настроить `CORS_ORIGINS` для вашего домена
- [ ] Получить SSL сертификаты (Let's Encrypt)
- [ ] Настроить firewall (открыть только 80/443)
- [ ] Протестировать health endpoints
- [ ] Настроить резервное копирование БД

### Рекомендуемые действия

- [ ] Настроить мониторинг (Prometheus + Grafana)
- [ ] Настроить логирование (ELK stack)
- [ ] Настроить CI/CD (GitHub Actions, GitLab CI)
- [ ] Настроить уведомления об ошибках (Sentry)

---

## 📊 URLs для проверки

| Сервис | URL | Примечание |
|--------|-----|------------|
| Frontend | http://localhost:3000 | SvelteKit приложение |
| Backend API | http://localhost:8000/api/v1 | REST API |
| Swagger Docs | http://localhost:8000/docs | API документация |
| Health | http://localhost:8000/health | Проверка сервиса |
| Health DB | http://localhost:8000/health/db | Проверка БД |
| Health Redis | http://localhost:8000/health/redis | Проверка Redis |
| Flower | http://localhost:5555 | Только локально/VPN/basic auth |

---

## 🐛 Troubleshooting

### Бэкенд не запускается

```bash
# Проверить логи
docker compose logs backend

# Проверить подключение к БД
curl http://localhost:8000/health/db
```

### Ошибки миграций

```bash
# Откатить последнюю миграцию
cd backend
python -m alembic downgrade -1

# Применить заново
python -m alembic upgrade head
```

### CORS ошибки

Проверьте `CORS_ORIGINS` в `backend/.env`:
```bash
CORS_ORIGINS=["https://yourdomain.com"]
```

---

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи: `docker compose logs -f`
2. Проверьте health endpoints
3. Убедитесь, что все переменные окружения настроены

---

**Итог:** проект можно использовать для контролируемой MVP-демонстрации после smoke-проверок. Для production нужны закрытие оставшихся пунктов hardening, staging-прогон миграций и ручной security review.
