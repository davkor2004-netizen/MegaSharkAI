"""
Конфигурация Celery для фоновых задач.

Celery используется для:
- Парсинга товаров с маркетплейсов
- Генерации отчётов
- AI-анализа данных
- Периодического репрайсинга
"""

from celery import Celery
from celery.schedules import crontab
from app.config import settings

# ====================
# Инициализация Celery
# ====================

celery_app = Celery(
    "megashark",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=[
        "app.tasks.parsing",
        "app.tasks.analytics",
        "app.tasks.repricing",
        "app.tasks.reports",
    ],
)

# ====================
# Конфигурация Celery
# ====================

celery_app.conf.update(
    # Сериализация задач и результатов
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    
    # Надёжность
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    
    # Таймауты
    task_soft_time_limit=300,  # 5 минут
    task_time_limit=600,  # 10 минут
    
    # Повторы при ошибках
    task_autoretry_for=(Exception,),
    task_max_retries=3,
    task_default_retry_delay=60,
    
    # Периодические задачи (будут переопределены в celery_beat_config)
    beat_schedule={},
)

# ====================
# Расписание периодических задач
# ====================

celery_app.conf.beat_schedule = {
    # Парсинг конкурентов каждые 6 часов
    "parse-competitors-every-6h": {
        "task": "app.tasks.parsing.parse_competitors",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    
    # Ночной репрайсинг в 3:00
    "night-repricing-every-day": {
        "task": "app.tasks.repricing.night_repricing",
        "schedule": crontab(minute=0, hour=3),
    },
    
    # Генерация ежедневных отчётов в 8:00
    "daily-reports-every-day": {
        "task": "app.tasks.reports.daily_reports",
        "schedule": crontab(minute=0, hour=8),
    },
    
    # Обновление календаря распродаж раз в неделю (понедельник 9:00)
    "update-sales-calendar-every-week": {
        "task": "app.tasks.analytics.update_sales_calendar",
        "schedule": crontab(minute=0, hour=9, day_of_week=1),
    },
}

# ====================
# Автообнаружение задач
# ====================

celery_app.autodiscover_tasks(["app"])


@celery_app.task(bind=True)
def debug_task(self):
    """
    Тестовая задача для проверки работы Celery.
    """
    print(f"Request: {self.request!r}")
    return "Celery работает! 🦈"
