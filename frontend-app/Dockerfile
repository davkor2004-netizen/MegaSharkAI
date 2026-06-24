# ===========================================
# Dockerfile для фронтенда MegaSharkAI
# ===========================================

FROM node:20-alpine

WORKDIR /app

# Копируем package files
COPY package*.json ./

# Установка зависимостей по lock-файлу для воспроизводимой сборки
RUN npm ci

# Копируем исходный код
COPY . .

# Открываем порт Vite
EXPOSE 3000

# Запуск dev-сервера
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
