# 📧 Настройка отправки Email (SMTP)

## Для чего это нужно?

Email уведомления используются для:
- 🔑 Сброса пароля пользователями
- 📬 Уведомлений о событиях (в будущем)

---

## Настройка SMTP для Gmail

### Шаг 1: Создайте App Password

1. Откройте [Google Account](https://myaccount.google.com/)
2. Перейдите в **Безопасность** → **Двухэтапная аутентификация**
3. Включите 2FA (если ещё не включена)
4. Вернитесь в **Безопасность** → **Пароли приложений**
5. Создайте новый пароль:
   - Приложение: `Mail`
   - Устройство: `Other`
   - Название: `MegaSharkAI`
6. Скопируйте полученный 16-значный пароль

### Шаг 2: Настройте .env

Откройте `backend/.env` и заполните:

```env
# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx  # 16-значный App Password
FROM_EMAIL=your-email@gmail.com
USE_TLS=true

# URL приложения
APP_URL=http://localhost:3000  # Для разработки
# APP_URL=https://megashark.ai  # Для продакшена
```

### Шаг 3: Перезапустите бэкенд

```bash
docker compose restart backend
```

---

## Настройка для других провайдеров

### Яндекс.Почта

```env
SMTP_HOST=smtp.yandex.ru
SMTP_PORT=587
SMTP_USER=your-email@yandex.ru
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx  # Пароль приложения
FROM_EMAIL=your-email@yandex.ru
USE_TLS=true
```

### Mail.ru

```env
SMTP_HOST=smtp.mail.ru
SMTP_PORT=587
SMTP_USER=your-email@mail.ru
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx
FROM_EMAIL=your-email@mail.ru
USE_TLS=true
```

### Корпоративная почта

Уточните SMTP настройки у вашего почтового провайдера. Обычно:
- SMTP_HOST: `smtp.yourcompany.com`
- SMTP_PORT: `587` (TLS) или `465` (SSL)
- SMTP_USER: ваш email
- SMTP_PASSWORD: ваш пароль

---

## Проверка работы

### Тест в режиме разработки

1. Откройте http://localhost:3000/forgot-password
2. Введите email существующего пользователя
3. Нажмите "Отправить ссылку"
4. Проверьте:
   - Если SMTP настроен: письмо придёт на email
   - Если SMTP не настроен: токен отобразится на странице (для тестирования)

### Проверка логов

```bash
docker compose logs backend | grep -i email
```

Пример успешной отправки:
```
✅ Email отправлен: user@example.com
✅ Email со ссылкой для сброса отправлен на user@example.com
```

---

## Безопасность

### ⚠️ Важно для продакшена

1. **Не используйте личный Gmail** для продакшена
   - Создайте отдельный сервисный аккаунт
   - Или используйте SendGrid, Mailgun, Amazon SES

2. **Добавьте переменные в .env.production**:
   ```bash
   # Скопируйте настройки в production env
   cp backend/.env backend/.env.production
   # Отредактируйте с production значениями
   ```

3. **Используйте секреты Docker**:
   ```yaml
   # docker-compose.yml
   secrets:
     - smtp_password
   
   services:
     backend:
       secrets:
         - smtp_password
   ```

---

## Альтернативные сервисы

### SendGrid (бесплатно до 100 писем/день)

1. Зарегистрируйтесь на https://sendgrid.com
2. Создайте API ключ в настройках
3. Настройте:
   ```env
   SMTP_HOST=smtp.sendgrid.net
   SMTP_PORT=587
   SMTP_USER=apikey
   SMTP_PASSWORD=SG.xxxxxxxxxxxxx
   FROM_EMAIL=noreply@megashark.ai
   ```

### Mailgun (бесплатно до 5000 писем/месяц)

1. Зарегистрируйтесь на https://mailgun.com
2. Создайте домен и получите SMTP credentials
3. Настройте:
   ```env
   SMTP_HOST=smtp.mailgun.org
   SMTP_PORT=587
   SMTP_USER=postmaster@your-domain.mailgun.org
   SMTP_PASSWORD=xxxxxxxxxxxxxx
   ```

---

## Troubleshooting

### Ошибка: "Authentication failed"

- Проверьте, что используете **App Password**, а не обычный пароль
- Убедитесь, что включена двухфакторная аутентификация
- Проверьте правильность SMTP_HOST и SMTP_PORT

### Ошибка: "Connection timeout"

- Проверьте, что порт 587 не заблокирован фаерволом
- Попробуйте порт 465 с `USE_TLS=false` (SSL)

### Письма не приходят

1. Проверьте спам
2. Проверьте логи бэкенда: `docker compose logs backend`
3. Убедитесь, что `FROM_EMAIL` совпадает с `SMTP_USER`

---

## Пример письма

Пользователь получает красивое HTML-письмо с:
- 🦈 Логотипом MegaSharkAI
- 🔘 Кнопкой "Сбросить пароль"
- ⏱ Информацией о сроке действия (1 час)
- 📱 Адаптивным дизайном для мобильных

---

**Готово!** Теперь пользователи могут восстанавливать пароль через email 🎉
