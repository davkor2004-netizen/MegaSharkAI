# ===========================================
# Скрипт установки бэкенда MegaSharkAI
# ===========================================
# Запуск: .\install.ps1
# ===========================================

Write-Host "🦈 Установка бэкенда MegaSharkAI..." -ForegroundColor Cyan

# Проверка Python
Write-Host "`n📌 Проверка Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python не найден!" -ForegroundColor Red
    Write-Host "Установи Python 3.12 с https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Не забудь отметить 'Add Python to PATH' при установке" -ForegroundColor Yellow
    exit 1
}

# Создание виртуального окружения
Write-Host "`n📦 Создание виртуального окружения..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "⚠️  venv уже существует, пропускаем" -ForegroundColor Yellow
} else {
    python -m venv venv
    Write-Host "✅ venv создано" -ForegroundColor Green
}

# Активация venv
Write-Host "`n🔌 Активация виртуального окружения..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"
Write-Host "✅ Активировано" -ForegroundColor Green

# Установка зависимостей
Write-Host "`n📥 Установка зависимостей..." -ForegroundColor Yellow
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Ошибка установки зависимостей" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Зависимости установлены" -ForegroundColor Green

# Установка браузеров Playwright
Write-Host "`n🌐 Установка браузеров Playwright..." -ForegroundColor Yellow
playwright install chromium
Write-Host "✅ Браузеры установлены" -ForegroundColor Green

# Копирование .env
Write-Host "`n⚙️  Настройка окружения..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "⚠️  .env уже существует, пропускаем" -ForegroundColor Yellow
} else {
    Copy-Item ".env.example" ".env"
    Write-Host "✅ .env создан из .env.example" -ForegroundColor Green
    Write-Host "📝 Отредактируй .env и добавь API-ключи при необходимости" -ForegroundColor Cyan
}

# Запуск Docker
Write-Host "`n🐳 Запуск Docker (БД и Redis)..." -ForegroundColor Yellow
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Ошибка запуска Docker. Проверь, что Docker Desktop запущен" -ForegroundColor Yellow
} else {
    Write-Host "✅ Docker сервисы запущены" -ForegroundColor Green
}

Write-Host "`n===========================================" -ForegroundColor Cyan
Write-Host "🎉 Установка завершена!" -ForegroundColor Green
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "🚀 Запуск бэкенда:" -ForegroundColor Cyan
Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "   uvicorn app.main:app --reload" -ForegroundColor White
Write-Host ""
Write-Host "📚 API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "🏥 Health:   http://localhost:8000/health" -ForegroundColor Cyan
Write-Host ""
