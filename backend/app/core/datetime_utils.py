"""
Утилиты для работы с датой/временем.

`datetime.utcnow()` объявлен устаревшим (DeprecationWarning) и будет удалён в
будущих версиях Python. При этом весь проект исторически работает с НАИВНЫМИ
UTC-датами (колонки БД — ``DateTime`` без ``timezone=True``, сравнения дат в
коде рассчитаны на naive-значения).

Поэтому здесь предоставляется единая замена ``utcnow()``, которая использует
актуальный API (``datetime.now(timezone.utc)``), но возвращает НАИВНОЕ значение
UTC — полностью совместимое с текущим поведением. Это убирает deprecation без
риска ошибок "can't compare offset-naive and offset-aware datetimes".
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Вернуть текущее время UTC как наивный datetime (без tzinfo).

    Прямая замена устаревшего ``datetime.utcnow()`` с идентичным результатом.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
