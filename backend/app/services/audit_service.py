"""
Сервис журналирования: audit log и события безопасности.

Главные принципы:
- НИКОГДА не сохранять секреты (пароли, токены, API-ключи, cookie) — за это
  отвечает :func:`sanitize_metadata`.
- Логирование не должно ронять основной поток: все функции записи перехватывают
  исключения и откатывают сессию, не пробрасывая ошибку наверх.
"""

import json
from typing import Any, Optional

from fastapi import Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog, SecurityEvent

# Подстроки в ключах метаданных, значения которых считаются секретами и маскируются.
_SENSITIVE_KEY_SUBSTRINGS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "api-key",
    "authorization",
    "auth_header",
    "cookie",
    "session",
    "refresh",
    "access_token",
    "encryption",
    "private_key",
    "credential",
    "hashed_password",
    "client_secret",
)

# Допустимые уровни критичности события безопасности.
_VALID_SEVERITIES = ("info", "warning", "high", "critical")

# Маска для скрытых значений.
_MASK = "***"

# Ограничение длины строковых значений в метаданных (защита от раздувания логов).
_MAX_STR_LEN = 500


def _is_sensitive_key(key: Any) -> bool:
    """Содержит ли ключ метаданных намёк на секрет."""
    key_lower = str(key).lower()
    return any(token in key_lower for token in _SENSITIVE_KEY_SUBSTRINGS)


def _sanitize_scalar(value: Any) -> Any:
    """Привести скалярное значение к безопасному, JSON-сериализуемому виду."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    if len(text) > _MAX_STR_LEN:
        text = text[:_MAX_STR_LEN] + "…"
    return text


def sanitize_metadata(data: Any, _depth: int = 0) -> dict:
    """
    Очистить метаданные перед записью в журнал.

    - Значения "чувствительных" ключей (пароли, токены, ключи, cookie) заменяются
      на ``***``.
    - Длинные строки усекаются.
    - Гарантируется JSON-сериализуемость результата.

    Всегда возвращает словарь (для не-dict входа оборачивает значение в ``{"value": ...}``).
    """
    # Защита от слишком глубокой/циклической структуры.
    if _depth > 6:
        return {}

    if data is None:
        return {}

    if not isinstance(data, dict):
        return {"value": _sanitize_scalar(data)}

    result: dict[str, Any] = {}
    for raw_key, value in data.items():
        key = str(raw_key)
        if _is_sensitive_key(key):
            result[key] = _MASK
        elif isinstance(value, dict):
            result[key] = sanitize_metadata(value, _depth + 1)
        elif isinstance(value, (list, tuple)):
            cleaned = []
            for item in value:
                if isinstance(item, dict):
                    cleaned.append(sanitize_metadata(item, _depth + 1))
                else:
                    cleaned.append(_sanitize_scalar(item))
            result[key] = cleaned
        else:
            result[key] = _sanitize_scalar(value)
    return result


def _dump_metadata(metadata: Any) -> Optional[str]:
    """Санитизировать и сериализовать метаданные в JSON-строку (или None)."""
    sanitized = sanitize_metadata(metadata)
    if not sanitized:
        return None
    try:
        return json.dumps(sanitized, ensure_ascii=False)
    except (TypeError, ValueError):
        # На всякий случай: если что-то не сериализуется — приводим к строкам.
        return json.dumps({k: str(v) for k, v in sanitized.items()}, ensure_ascii=False)


def _client_ip(request: Optional[Request]) -> Optional[str]:
    """Получить IP-адрес клиента, учитывая X-Forwarded-For за прокси."""
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Берём первый адрес в цепочке прокси.
        return forwarded.split(",")[0].strip()[:64]
    if request.client and request.client.host:
        return request.client.host[:64]
    return None


def request_meta(request: Optional[Request]) -> dict:
    """Извлечь безопасные метаданные запроса (IP, UA, путь, метод)."""
    if request is None:
        return {"ip": None, "user_agent": None, "path": None, "method": None}
    user_agent = request.headers.get("user-agent")
    if user_agent:
        user_agent = user_agent[:512]
    return {
        "ip": _client_ip(request),
        "user_agent": user_agent,
        "path": str(request.url.path)[:512] if request.url else None,
        "method": request.method[:16] if request.method else None,
    }


async def log_audit_event(
    db: AsyncSession,
    *,
    action: str,
    actor_user_id: Optional[Any] = None,
    target_user_id: Optional[Any] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[Any] = None,
    metadata: Optional[dict] = None,
    request: Optional[Request] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Optional[AuditLog]:
    """
    Записать событие в audit log.

    Безопасно: при любой ошибке откатывает сессию и возвращает None, не ломая
    вызывающий поток. Метаданные обязательно санитизируются.
    """
    try:
        meta = request_meta(request)
        entry = AuditLog(
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            metadata_json=_dump_metadata(metadata),
            ip=ip or meta["ip"],
            user_agent=user_agent or meta["user_agent"],
        )
        db.add(entry)
        await db.commit()
        return entry
    except Exception as exc:  # noqa: BLE001 — логирование не должно ронять поток
        logger.warning(f"⚠️ Не удалось записать audit-событие '{action}': {exc}")
        try:
            await db.rollback()
        except Exception:
            pass
        return None


async def log_security_event(
    db: AsyncSession,
    *,
    event_type: str,
    severity: str = "info",
    user_id: Optional[Any] = None,
    metadata: Optional[dict] = None,
    request: Optional[Request] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    path: Optional[str] = None,
    method: Optional[str] = None,
    status_code: Optional[int] = None,
) -> Optional[SecurityEvent]:
    """
    Записать событие безопасности.

    Безопасно: при любой ошибке откатывает сессию и возвращает None. Метаданные
    санитизируются. ``severity`` нормализуется до допустимого набора.
    """
    if severity not in _VALID_SEVERITIES:
        severity = "info"
    try:
        meta = request_meta(request)
        entry = SecurityEvent(
            user_id=user_id,
            event_type=event_type,
            severity=severity,
            ip=ip or meta["ip"],
            user_agent=user_agent or meta["user_agent"],
            path=path or meta["path"],
            method=method or meta["method"],
            status_code=status_code,
            metadata_json=_dump_metadata(metadata),
        )
        db.add(entry)
        await db.commit()
        return entry
    except Exception as exc:  # noqa: BLE001 — логирование не должно ронять поток
        logger.warning(f"⚠️ Не удалось записать security-событие '{event_type}': {exc}")
        try:
            await db.rollback()
        except Exception:
            pass
        return None
