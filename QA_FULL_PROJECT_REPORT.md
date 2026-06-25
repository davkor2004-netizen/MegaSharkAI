# 🧪 Полный функциональный QA — MegaSharkAI

- **Дата проверки:** 2026-06-25
- **Commit (HEAD):** `56b4a44` — "Resolve README merge conflict" (ветка `main`, up to date с `origin/main`)
- **Окружение QA:** локальный Docker, dev-режим (`ENVIRONMENT=development`, `DEBUG=true`, `is_production=False`)
- **Хост:** Windows 10, Docker 29.2.1, Docker Compose v5.0.2
- **Стек:** FastAPI + PostgreSQL (pgvector pg16) + Redis + Alembic + SQLAlchemy async; SvelteKit + TypeScript + Tailwind

> ⚠️ QA выполнялся в **dev-режиме** (так поднят проект). Поэтому `is_production=False`, `/docs` доступен, CORS расширен на localhost — это корректное dev-поведение. Требования к production зафиксированы в `DEPLOYMENT.md` и проверены на уровне кода (см. раздел Security).

---

## 1. Сводка результатов

| Проверка | Результат |
|---|---|
| Проект запускается (Docker) | ✅ Да, все 6 контейнеров Up |
| Backend tests | ✅ **95 passed**, 292 warnings (deprecation) |
| Frontend `npm run check` | ✅ 0 errors, 0 warnings |
| Frontend `npm run build` | ✅ Успех (`built in ~17s`) |
| Миграции (`alembic upgrade head`) | ✅ current == head == `base_schema_bootstrap`, no-op |
| Backend endpoints (smoke) | ✅ Нет 500 |
| Frontend routes (smoke) | ✅ Все 20 маршрутов 200 |
| Auth-флоу | ✅ register/login/me/refresh/logout/remember_me |
| Security smoke | ✅ Без критичных проблем |

**Проблемы:** 0 critical, 0 high, 1 medium, 3 low. Блокеров для запуска не найдено.

---

## 2. Запущенные команды

```text
git status / git ls-files / git rev-parse HEAD
docker --version / docker compose version / docker compose ps
docker compose exec backend alembic current | heads | upgrade head
docker compose exec backend sh -lc "PYTHONPATH=/app python -m pytest -q"
curl http://localhost:8000/health | /health/db | /health/redis | /openapi.json
curl (auth flow: register, login, /me, /refresh, logout с cookie jar)
curl (авторизованный smoke по GET-эндпоинтам всех модулей)
curl (HTTP smoke 20 frontend-маршрутов на :3000)
cd frontend-app && npm run check && npm run build
```

---

## 3. Docker / инфраструктура

`docker compose ps` — все сервисы подняты:

| Контейнер | Статус |
|---|---|
| megashark_backend | Up, `:8000` |
| megashark_frontend | Up, `:3000` |
| megashark_db (pgvector/pgvector:pg16) | Up (healthy), `127.0.0.1:5432` |
| megashark_redis (redis:7-alpine) | Up (healthy), `127.0.0.1:6379` |
| megashark_celery_worker | Up |
| megashark_celery_beat | Up |

Health-эндпоинты: `/health=200`, `/health/db=200`, `/health/redis=200`.
Логи backend (tail 200): **нет** ERROR / Traceback / 500 / Exception.

Наличие файлов: `docker-compose.yml` ✅, `docker-compose.prod.yml` ✅, `DEPLOYMENT.md` ✅, `backend/Dockerfile` ✅, `frontend-app/Dockerfile` ✅.

---

## 4. База данных и миграции

```text
alembic current = base_schema_bootstrap (head)
alembic heads   = base_schema_bootstrap (head)
alembic upgrade head = no-op (current == head)
```

Production-условия зафиксированы в `DEPLOYMENT.md` (раздел «Обязательный чеклист перед деплоем» + «Только для чистой production-БД»):
- ✅ `ENVIRONMENT=production`
- ✅ `DEBUG=false`
- ✅ `alembic upgrade head` перед запуском backend
- ✅ pgvector (`CREATE EXTENSION IF NOT EXISTS vector;` в baseline `32bc7c876e79`)
- ✅ `alembic_version` `VARCHAR(128)` для чистой БД

`stamp head` не выполнялся.

---

## 5. Backend tests

```text
docker compose exec backend sh -lc "PYTHONPATH=/app python -m pytest -q"
=> 95 passed, 292 warnings in ~17–22s
```

- Warnings — исключительно `DeprecationWarning: datetime.datetime.utcnow()` и `StarletteDeprecationWarning` (HTTP_422). Тех-долг, не влияет на прохождение.
- Покрытие включает: auth/billing/security, widget, parser (WB), marketplace credentials, calendar/notifications, chat support, security-critical (JWT-типы).

> Примечание: дефолтный `pytest` без `PYTHONPATH=/app` падает с `ModuleNotFoundError: No module named 'app'`. Корректный вызов — через `sh -lc "PYTHONPATH=/app python -m pytest"` (как указано в задании).

---

## 6. Frontend checks

```text
npm run check  => svelte-check found 0 errors and 0 warnings
npm run build  => ✓ built in ~17s (все маршруты собраны)
```

- Скриптов `lint` / `test` в `package.json` **нет** — зафиксировано, зависимости не добавлялись.
- ⚠️ При build: `@sveltejs/adapter-auto` — "Could not detect a supported production environment". Для production нужен явный адаптер (см. находку LOW-2; уже отражено в `DEPLOYMENT.md`).

---

## 7. Auth QA

Полный флоу через cookie jar (`curl -c/-b`):

| Сценарий | Результат |
|---|---|
| register (валидный) | ✅ 201, возвращает токен + user |
| login без remember_me | ✅ 200 |
| login с remember_me=true | ✅ 200 |
| Неверный пароль | ✅ 401 (понятная ошибка, не краш) |
| `/api/v1/auth/me` с cookie | ✅ 200 |
| `/api/v1/auth/refresh` с cookie | ✅ 200 |
| logout | ✅ 200 |
| Cookie `access_token` | ✅ **HttpOnly**, path `/`, TTL ~30 мин |
| Cookie `refresh_token` | ✅ **HttpOnly**, path `/api/v1/auth`, TTL ~30 дней при remember_me |
| Раздельные TTL (access короткий, refresh длинный) | ✅ Подтверждено по `expires` в jar |
| Токены в localStorage | ✅ Отсутствуют (`auth.ts` чистит legacy JWT) |
| Email в localStorage | ✅ Только при remember_me (`REMEMBER_EMAIL_KEY`) |
| admin/superuser flow | ✅ `/me/admin`, `/chat/admin/conversations` → 403 для обычного юзера |
| `/me` не утекает пароль/хэш | ✅ Нет поля `hashed_password` |

---

## 8. Backend endpoints smoke (авторизованно)

Без авторизации: `/auth/me=401`, `/widget/config=401`, `/products/list=401` (корректно).

Авторизованным пользователем (обычный, без подписки):

| Эндпоинт | Код | Комментарий |
|---|---|---|
| `/ai/provider` | 200 | |
| `/ai/settings` | 403 | by design — superuser-only (глобальные ключи) |
| `/analytics/abc` | 200 | |
| `/billing/current`, `/billing/list` | 200 | |
| `/calendar/`, `/calendar/upcoming`, `/export/csv`, `/export/ics` | 200 | |
| `/marketplace-keys` | 200 | |
| `/notifications/`, `/settings`, `/unread-count` | 200 | |
| `/parsing/proxy-stats` | 403 | by design — superuser-only |
| `/products/stats/summary`, `/products/export`, `/products/list` | 200 | |
| `/reports/competitors` | 200 | |
| `/repricing/strategies` | 200 | |
| `/chat/conversations` | 200 | |
| `/widget/config` | 402 | by design — locked, понятный апселл тарифа (не 500) |

Тела gating-ответов корректные и человекочитаемые:
- 402 widget: «Функция «виджет…» доступна на тарифе Business…»
- 403: «Недостаточно прав для выполнения этого действия»

**Ни одного 500.**

---

## 9. Frontend routes smoke

HTTP-статусы (SSR-оболочка, `:3000`) — **все 200**, без blank/500:

`/login` `/register` `/dashboard` `/products` `/products?search=test` `/parsing` `/ai` `/ai-studio` `/analytics` `/reports` `/repricing` `/calendar` `/notifications` `/billing` `/widget` `/profile` `/settings` `/import` `/partners` `/admin/chat` — 200 (×20).

Русификация брендинга проверена: «Командный центр» вместо «Command Center / Neural Ocean» во всех видимых местах (Topbar, Sidebar, auth-layout, eyebrow страниц). Остатки `Neural Ocean Command Center` — только в комментариях кода/CSS (не видны пользователю).

`/settings` корректно гейтит AI-секцию за `isSuperuser` — обычный пользователь не инициирует 403-запрос к `/ai/settings`.

---

## 10. Security smoke

| Проверка | Результат |
|---|---|
| `.env` не в tracked files | ✅ Только `backend/.env.example` |
| Реальные секреты в репо | ✅ Не найдено |
| Токены в localStorage | ✅ Нет |
| Cookies HttpOnly | ✅ access + refresh оба HttpOnly |
| Production-валидация конфига | ✅ `validate_startup_safety()` вызывается на старте (`main.py:149`) |
| Запрет DEBUG в prod | ✅ Падает с RuntimeError при `DEBUG=true` + production |
| Запрет wildcard CORS в prod | ✅ `"*"` запрещён в production-валидации |
| Дефолтные SECRET_KEY / POSTGRES_PASSWORD / ENCRYPTION_KEY | ✅ Запрещены в production-валидации |
| Секреты в ответах API | ✅ `/me` не отдаёт хэш пароля; AI/marketplace ключи маскируются (`mask_secret`) |
| `/docs` в prod | ✅ Отключается при `is_production` (в dev доступен — корректно) |

---

## 11. Найденные проблемы

### 🟠 MEDIUM-1 — Парсер безусловно пишет debug-дампы на диск (в т.ч. в production)
- **Модуль:** Parsing (`backend/app/services/parser.py`)
- **Где:** WB — строки ~1316–1322; Ozon — ~2093–2099.
- **Шаги воспроизведения:** запустить парсинг любого товара WB/Ozon.
- **Ожидаемо:** debug-скриншот/HTML сохраняются только при включённом debug-режиме (или не сохраняются вовсе).
- **Фактически:** на **каждый** парсинг безусловно создаются `screenshot.png` + `page.content()` HTML:
  ```python
  screenshot_path = f"backend/wb_debug_{...}.png"
  await page.screenshot(path=screenshot_path, full_page=True)
  html_path = f"backend/wb_debug_{...}.html"
  ```
- **Последствия:** рост диска без ротации; запись scraped-HTML на диск в production; из-за относительного пути (`backend/...` при cwd `/app`) файлы падают в ошибочно вложенную `backend/backend/` (на хосте уже 8 артефактов).
- **Severity:** medium (не ломает функциональность, но нежелательный I/O и потенциальная утечка контента в prod).
- **Минимальный fix (НЕ применён — затрагивает parser, по правилам только через отчёт):** обернуть запись в `if settings.debug:` и/или писать в `tempfile`/выделенный том с ротацией. Пример:
  ```python
  if settings.debug:
      screenshot_path = f"/tmp/wb_debug_{...}.png"
      await page.screenshot(path=screenshot_path, full_page=True)
  ```

### 🟡 LOW-1 — `backend/celerybeat-schedule` отслеживается в git
- Рантайм-артефакт Celery beat (бинарный, меняется каждый запуск) закоммичен → постоянный «грязный» `git status`.
- **Fix (частично применён):** добавлен в `.gitignore`. Для полного устранения нужно `git rm --cached backend/celerybeat-schedule` (git-операция — оставлено на усмотрение, не выполнял без запроса).

### 🟡 LOW-2 — `adapter-auto` не определяет production-окружение
- `npm run build` выдаёт предупреждение; для prod нужен явный `@sveltejs/adapter-node` или `adapter-static`.
- Уже описано в `DEPLOYMENT.md`. Установку новых зависимостей не делал (требует разрешения).

### 🟡 LOW-3 — Тех-долг `datetime.utcnow()` (292 deprecation warnings)
- По всему backend используется устаревший `datetime.utcnow()`. Тесты проходят, но рекомендуется миграция на `datetime.now(datetime.UTC)`.

---

## 12. Что исправлено в рамках QA

- ✅ `.gitignore`: добавлены правила для рантайм-артефактов (`celerybeat-schedule`, `wb_debug_*`, `ozon_debug_*`, ошибочная `backend/backend/`). Безопасная housekeeping-правка, логику/данные не затрагивает.

Бизнес-логика, auth, billing, schema БД, parser-стратегия, AI-провайдеры — **не менялись** (согласно ограничениям задачи).

---

## 13. Что осталось / не покрыто автоматически

- **Визуальный mobile/desktop QA в браузере:** проверен на уровне сборки и наличия Tailwind-responsive паттернов; реальную проверку горизонтального скролла/адаптива на узких ширинах нужно сделать вручную в браузере.
- **WebSocket admin chat / ChatWidget:** backend-тест `test_chat_websocket_auth_and_message_ack` проходит; полный E2E подключения/реконнекта в UI требует ручной проверки.
- **Реальные внешние интеграции** (YooKassa, AI-провайдеры, прокси) намеренно **не вызывались** (safe mode) — проверены только пути ошибок/gating.
- **MEDIUM-1 (debug-дампы парсера)** — требует решения по правке parser.py.

---

## 14. Блокеры перед production

Жёстких блокеров нет. Перед prod-деплоем обязательно (из `DEPLOYMENT.md`):
1. `ENVIRONMENT=production`, `DEBUG=false`.
2. Сгенерировать и задать `SECRET_KEY`, `ENCRYPTION_KEY`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD` (иначе `validate_startup_safety()` не даст стартовать — это правильно).
3. `CORS_ORIGINS` без `*`.
4. Для чистой БД: предсоздать `alembic_version VARCHAR(128)`, убедиться в доступности pgvector, затем `alembic upgrade head`.
5. Заменить `adapter-auto` на боевой адаптер фронтенда.
6. Рекомендуется решить MEDIUM-1 (debug-дампы парсера) до prod.

---

## 15. Рекомендации следующего шага

1. **MEDIUM-1:** обернуть запись debug-дампов парсера в `if settings.debug:` и/или вынести в `/tmp` с ротацией.
2. **LOW-1:** `git rm --cached backend/celerybeat-schedule` (после этого .gitignore удержит файл вне трекинга).
3. Почистить хостовые артефакты `backend/backend/wb_debug_*` (уже под `.gitignore`).
4. **LOW-2:** добавить `@sveltejs/adapter-node`/`adapter-static` (с разрешения на установку зависимости).
5. **LOW-3:** плановая миграция `datetime.utcnow()` → timezone-aware.
6. Опционально: ручной mobile-QA ключевых страниц (products-таблица, calendar, admin chat) в браузере.

---

**Версия отчёта:** 1.0
