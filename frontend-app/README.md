# 🦈 MegaSharkAI Frontend

Фронтенд личного кабинета на **SvelteKit + shadcn-svelte**.

## 🚀 Быстрый старт

### 1. Установка зависимостей

```powershell
cd frontend-app
npm install
```

### 2. Запуск dev-сервера

```powershell
npm run dev
```

### 3. Открыть в браузере

http://localhost:3000

---

## 📁 Структура

```
frontend-app/
├── src/
│   ├── lib/
│   │   └── components/
│   │       └── ui/          # shadcn-svelte компоненты
│   └── routes/
│       ├── (auth)/          # Страницы авторизации
│       │   └── login/
│       ├── (app)/           # Основное приложение
│       │   ├── dashboard/   # Дашборд
│       │   ├── parsing/     # Парсинг
│       │   └── ai/          # AI Генератор
│       ├── +layout.svelte   # Основной layout
│       └── +page.svelte     # Главная
├── static/                  # Статические файлы
├── package.json
├── svelte.config.js
├── tailwind.config.js
└── vite.config.ts
```

---

## 🎨 Компоненты

### shadcn-svelte

UI библиотека на основе Tailwind CSS.

**Установка компонентов:**

```bash
npx shadcn-svelte@latest add button
npx shadcn-svelte@latest add input
npx shadcn-svelte@latest add card
```

---

## 🔌 API Integration

Все API запросы идут через proxy на бэкенд (порт 8000):

- `/api/v1/health` → `http://localhost:8000/api/v1/health`
- `/api/v1/products` → `http://localhost:8000/api/v1/products`
- `/api/v1/parsing/*` → `http://localhost:8000/api/v1/parsing/*`
- `/api/v1/ai/*` → `http://localhost:8000/api/v1/ai/*`

Настроено в `vite.config.ts`.

---

## 📝 Страницы

### 1. Логин (`/login`)
- Форма входа
- Email + пароль
- Валидация

### 2. Дашборд (`/dashboard`)
- Статистика товаров
- Быстрые действия
- Графики (TODO)

### 3. Парсинг (`/parsing`)
- Выбор маркетплейса
- Ввод URL
- Результаты парсинга

### 4. AI Генератор (`/ai`)
- Генерация SEO-названий
- Настройки (категория, бренд, характеристики)
- Копирование результата

---

## 🛠 Разработка

### Проверка типов

```bash
npm run check
```

### Сборка

```bash
npm run build
```

### Preview

```bash
npm run preview
```

---

## 🎯 TODO

- [ ] Регистрация
- [ ] Восстановление пароля
- [ ] Таблица товаров
- [ ] Фильтры и сортировка
- [ ] Экспорт в Excel
- [ ] Графики и диаграммы
- [ ] Настройки профиля
- [ ] История парсинга
- [ ] Уведомления
