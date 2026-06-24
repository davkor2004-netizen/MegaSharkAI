# 🕷️ ПАРСИНГ MEGASHARK AI - ИНСТРУКЦИЯ

## ✅ Что реализовано

### Бэкенд:
1. **Сервис прокси (`proxy_pool.py`)**:
   - 20 прокси из Proxy6
   - Автоматическая ротация (least_used, random, next)
   - Отслеживание ошибок и блокировок
   - Статистика использования

2. **Сервис парсинга (`parser.py`)**:
   - Playwright (Chromium)
   - Поддержка 4 маркетплейсов: WB, Ozon, Яндекс Маркет, Avito
   - Извлечение: название, цена, рейтинг, отзывы, бренд, категория, продавец
   - Автоматическое определение маркетплейса по URL

3. **API endpoints (`/api/v1/parsing/`)**:
   - `POST /parse-url` - Парсинг по URL
   - `POST /my-products` - Получение своих товаров через API
   - `GET /proxy-stats` - Статистика прокси
   - `GET /test-parser` - Тест парсера

### Фронтенд:
- Страница `/parsing` (требует обновления UI)

---

## 🧪 ТЕСТИРОВАНИЕ

### 1. Проверка прокси:
```bash
GET http://localhost:8000/api/v1/parsing/proxy-stats
```

**Ожидаемый ответ:**
```json
{
  "status": "success",
  "data": {
    "total": 20,
    "available": 20,
    "blocked": 0
  }
}
```

---

### 2. Тест парсера:
```bash
GET http://localhost:8000/api/v1/parsing/test-parser
```

**Ожидаемый ответ:**
```json
{
  "status": "success",
  "message": "Парсер работает",
  "data": {...},
  "proxy_used": "185.126.84.182"
}
```

---

### 3. Парсинг URL (через UI или API):

**API:**
```bash
POST http://localhost:8000/api/v1/parsing/parse-url
Authorization: Bearer <token>
Content-Type: application/json

{
  "url": "https://www.wildberries.ru/catalog/24319630/detail.aspx",
  "is_competitor": true
}
```

**Примеры URL для теста:**
- Wildberries: `https://www.wildberries.ru/catalog/24319630/detail.aspx`
- Ozon: `https://www.ozon.ru/product/...`
- Яндекс Маркет: `https://market.yandex.ru/product/...`
- Avito: `https://www.avito.ru/...`

---

## 📊 КАК ЭТО РАБОТАЕТ

### Схема работы:

```
Пользователь → Фронтенд → Бэкенд → Proxy Pool → Playwright → Маркетплейс
                                              ↓
                                         Прокси 1-20
                                              ↓
                                         Результат → БД
```

### Ротация прокси:

1. **Стратегия "least_used"** (по умолчанию):
   - Берётся прокси с наименьшим количеством запросов
   - Равномерное распределение нагрузки

2. **Автоматическая блокировка**:
   - 5 ошибок → блокировка на 30 минут
   - Прокси пропускается в ротации

3. **Статистика**:
   - `usage_count` - сколько раз использован
   - `error_count` - количество ошибок
   - `is_blocked` - заблокирован ли сейчас

---

## 🔧 НАСТРОЙКИ

### Переменные окружения (`.env`):

```bash
# Прокси (список через запятую)
PROXY_LIST=ip1:port:login:pass,ip2:port:login:pass,...

# Таймаут парсинга (мс)
PARSING_TIMEOUT=30000

# Браузер
PLAYWRIGHT_BROWSER=chromium
```

---

## 🚀 ИСПОЛЬЗОВАНИЕ НА ФРОНТЕНДЕ

### Пример запроса:

```typescript
async function parseProduct(url: string) {
  const token = localStorage.getItem('access_token');
  
  const response = await fetch('/api/v1/parsing/parse-url', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      url: url,
      is_competitor: true
    })
  });
  
  const data = await response.json();
  
  if (response.ok) {
    console.log('Распарсено:', data.data);
    // data.data = {
    //   name: "...",
    //   price: 1999,
    //   rating: 4.5,
    //   reviews_count: 150,
    //   sales_per_day: 12, // если удалось извлечь
    //   ...
    // }
  } else {
    console.error('Ошибка:', data.detail);
  }
}
```

---

## ⚠️ ВОЗМОЖНЫЕ ПРОБЛЕМЫ

### 1. Таймаут при парсинге:
**Причина:** Сайт долго загружается или прокси медленный

**Решение:**
- Увеличить `PARSING_TIMEOUT` в `.env`
- Проверить скорость прокси
- Попробовать другой прокси

---

### 2. Ошибка "Не удалось извлечь название или цену":
**Причина:** Изменилась структура сайта (селекторы)

**Решение:**
- Обновить селекторы в `parser.py`
- Проверить вручную через браузер

---

### 3. Все прокси заблокированы:
**Причина:** Слишком много запросов, маркетплейс банит IP

**Решение:**
- Подождать 30 минут (авторазблокировка)
- Увеличить задержки между запросами
- Добавить больше прокси

---

### 4. Playwright не устанавливается:
**Решение:**
```bash
cd backend
playwright install chromium
```

---

## 📈 СЛЕДУЮЩИЕ ШАГИ

1. **Обновить фронтенд** (`/parsing`):
   - Форма для вставки URL
   - Выбор режима (конкуренты / мои товары)
   - Таблица результатов
   - История парсинга

2. **Добавить Celery задачи**:
   - Фоновый парсинг
   - Расписание обновлений
   - Очереди на парсинг

3. **Интеграция с API маркетплейсов**:
   - Wildberries API (реальный)
   - Ozon API (реальный)
   - Автоматическое обновление цен

4. **Аналитика**:
   - История изменений цен
   - Графики динамики
   - Сравнение с конкурентами

---

## 💡 СОВЕТЫ

1. **Не парсить слишком часто** - маркетплейсы могут забанить
2. **Использовать режим "мои товары" через API** - это легально и стабильно
3. **Мониторить статистику прокси** - вовремя добавлять новые
4. **Кэшировать результаты** - не парсить одно и то же дважды

---

**Готово к использованию! 🦈**
