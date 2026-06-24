# 🔐 Система ролей MegaSharkAI

## Описание

В проекте реализована система с двумя типами пользователей:

| Роль | Описание | Доступ к настройкам |
|------|----------|---------------------|
| **Администратор** (superuser) | Полный доступ ко всем функциям | ✅ Видна кнопка |
| **Пользователь** (user) | Ограниченный доступ | ❌ Не видна кнопка |

## 📋 Учётные данные

### Администратор
- **Email:** `admin@megashark.ai`
- **Пароль:** `Admin@123456`
- **Права:** Полный доступ ко всем функциям
- **Кнопка "Настройки":** ✅ Видна

### Обычный пользователь
- **Email:** `user@megashark.ai`
- **Пароль:** `User@123456`
- **Права:** Ограниченный доступ
- **Кнопка "Настройки":** ❌ Не видна

## 🚀 Как проверить

### 1. Вход как администратор

1. Откройте http://localhost:3000/login
2. Введите:
   - Email: `admin@megashark.ai`
   - Пароль: `Admin@123456`
3. Нажмите "Войти"
4. **Результат:** В боковом меню видна кнопка "⚙️ Настройки"

### 2. Вход как обычный пользователь

1. Выйдите из аккаунта (очистите localStorage или откройте инкогнито)
2. Откройте http://localhost:3000/login
3. Введите:
   - Email: `user@megashark.ai`
   - Пароль: `User@123456`
4. Нажмите "Войти"
5. **Результат:** В боковом меню **НЕТ** кнопки "Настройки"

## 🔧 Технические детали

### Бэкенд

- **Модель:** `backend/app/models/user.py`
  - Поле `is_superuser` определяет права администратора
  
- **Аутентификация:** `backend/app/api/v1/auth.py`
  - `/login` — возвращает токен + `is_superuser` флаг
  - `/me` — информация о текущем пользователе
  - `/me/admin` — только для администраторов

- **Скрипт создания:** `backend/create_users.py`
  - Создаёт начального администратора
  - Создаёт тестового пользователя

### Фронтенд

- **Layout:** `frontend-app/src/routes/+layout.svelte`
  - Проверяет `isSuperuser` из localStorage
  - Показывает/скрывает кнопку настроек

- **Логин:** `frontend-app/src/routes/(auth)/login/+page.svelte`
  - Сохраняет `isSuperuser` в localStorage после входа

## 📝 Создание нового администратора

```bash
# Подключитесь к контейнеру
docker compose exec backend bash

# Запустите Python консоль
python

# В коде:
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models.user import User
from app.api.v1.auth import get_password_hash

db = Session(bind=engine)

# Создать админа
new_admin = User(
    email="newadmin@example.com",
    hashed_password=get_password_hash("Password123!"),
    full_name="Новый админ",
    is_active=True,
    is_superuser=True  # Права администратора
)

db.add(new_admin)
db.commit()
```

## ⚠️ Безопасность

1. **Смените пароли** после первого входа в продакшене
2. **Измените SECRET_KEY** в `.env` файле
3. **Не храните** учётные данные в коде
4. **Используйте HTTPS** в продакшене

## 🔄 Миграции

Если у вас уже есть база данных, обновите схему:

```bash
# Для существующих пользователей
docker compose exec backend python -c "
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models.user import User

db = Session(bind=engine)
admin = db.query(User).filter(User.email == 'admin@megashark.ai').first()
if admin:
    admin.is_superuser = True
    db.commit()
    print('✅ Админ обновлён')
"
```

## 📊 API Endpoints

| Endpoint | Метод | Доступ | Описание |
|----------|-------|--------|----------|
| `/api/v1/auth/register` | POST | Все | Регистрация |
| `/api/v1/auth/login` | POST | Все | Вход |
| `/api/v1/auth/me` | GET | Авторизованные | Мой профиль |
| `/api/v1/auth/me/admin` | GET | Админы | Проверка прав |

## 🎯 Следующие шаги

- [ ] Добавить страницу управления пользователями (только для админов)
- [ ] Добавить ролевую модель (Admin, Manager, User)
- [ ] Добавить защиту API endpoints по ролям
- [ ] Добавить логирование действий администратора
