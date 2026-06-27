"""
Тесты audit log и security events для Admin Control Center.

Проверяют:
- санитизацию метаданных (пароли/токены/ключи/cookie не сохраняются);
- логирование событий аутентификации (login success/failed, logout, refresh);
- доступ к /admin/audit и /admin/security/events только для superuser (403);
- что эндпоинты возвращают реальные данные и НЕ отдают секреты.
"""

from uuid import UUID

import pytest
from sqlalchemy import select

from app.models.user import User
from app.models.audit import AuditLog, SecurityEvent
from app.services.audit_service import sanitize_metadata, log_audit_event
from app.services.auth_service import create_refresh_token


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------
def register_user(client, email: str, password: str = "TestPass123!") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "QA Sec"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(client, email: str) -> tuple[dict[str, str], dict]:
    payload = register_user(client, email=email)
    return {"Authorization": f"Bearer {payload['access_token']}"}, payload


async def make_superuser(db_session, user_id: str) -> None:
    result = await db_session.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one()
    user.is_superuser = True
    await db_session.commit()


def do_login(client, email: str, password: str = "TestPass123!"):
    return client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )


# ---------------------------------------------------------------------------
# 1. Санитизация метаданных
# ---------------------------------------------------------------------------
def test_sanitize_metadata_removes_secrets():
    """Чувствительные ключи маскируются, безопасные сохраняются."""
    raw = {
        "password": "Secret123!",
        "api_key": "sk-live-xxxxxxxx",
        "access_token": "eyJhbGci...",
        "refresh_token": "rt-12345",
        "Cookie": "session=abc",
        "client_secret": "shh",
        "email": "user@example.com",
        "remember_me": True,
        "nested": {
            "marketplace_api_key": "WB-KEY-RAW",
            "note": "ok",
        },
    }
    cleaned = sanitize_metadata(raw)

    # Секреты замаскированы.
    assert cleaned["password"] == "***"
    assert cleaned["api_key"] == "***"
    assert cleaned["access_token"] == "***"
    assert cleaned["refresh_token"] == "***"
    assert cleaned["Cookie"] == "***"
    assert cleaned["client_secret"] == "***"
    assert cleaned["nested"]["marketplace_api_key"] == "***"

    # Безопасные данные на месте.
    assert cleaned["email"] == "user@example.com"
    assert cleaned["remember_me"] is True
    assert cleaned["nested"]["note"] == "ok"

    # Гарантия: ни одно сырое секретное значение не утекло в результат.
    flat = str(cleaned)
    for secret in ("Secret123!", "sk-live-xxxxxxxx", "eyJhbGci", "rt-12345", "WB-KEY-RAW"):
        assert secret not in flat


# ---------------------------------------------------------------------------
# 2. Логирование событий аутентификации
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_login_failed_creates_security_event(client, db_session):
    """Неудачный вход создаёт security event без пароля в метаданных."""
    register_user(client, "sec-failed@example.com")

    response = do_login(client, "sec-failed@example.com", password="WrongPass!")
    assert response.status_code == 401

    rows = (
        await db_session.execute(
            select(SecurityEvent).where(SecurityEvent.event_type == "login_failed")
        )
    ).scalars().all()
    assert len(rows) >= 1
    event = rows[-1]
    assert event.severity == "warning"
    # Пароль НЕ должен попасть в метаданные.
    assert "WrongPass" not in (event.metadata_json or "")


@pytest.mark.asyncio
async def test_login_success_creates_security_and_audit(client, db_session):
    """Успешный вход создаёт security event login_success и audit auth.login."""
    register_user(client, "sec-ok@example.com")

    response = do_login(client, "sec-ok@example.com")
    assert response.status_code == 200

    sec = (
        await db_session.execute(
            select(SecurityEvent).where(SecurityEvent.event_type == "login_success")
        )
    ).scalars().all()
    assert len(sec) >= 1
    assert sec[-1].severity == "info"

    audit = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "auth.login")
        )
    ).scalars().all()
    assert len(audit) >= 1


@pytest.mark.asyncio
async def test_logout_creates_events(client, db_session):
    """Выход создаёт security event logout и audit auth.logout."""
    register_user(client, "sec-logout@example.com")
    login = do_login(client, "sec-logout@example.com")
    assert login.status_code == 200

    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200

    sec = (
        await db_session.execute(
            select(SecurityEvent).where(SecurityEvent.event_type == "logout")
        )
    ).scalars().all()
    assert len(sec) >= 1

    audit = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "auth.logout")
        )
    ).scalars().all()
    assert len(audit) >= 1


@pytest.mark.asyncio
async def test_refresh_success_logged(client, db_session):
    """Успешный refresh логируется как token_refresh (info)."""
    payload = register_user(client, "sec-refresh@example.com")
    user_id = payload["user"]["id"]
    token = create_refresh_token(data={"sub": user_id, "user_id": user_id})

    response = client.post("/api/v1/auth/refresh", cookies={"refresh_token": token})
    assert response.status_code == 200

    rows = (
        await db_session.execute(
            select(SecurityEvent).where(SecurityEvent.event_type == "token_refresh")
        )
    ).scalars().all()
    assert len(rows) >= 1
    assert rows[-1].severity == "info"


@pytest.mark.asyncio
async def test_refresh_failure_logged(client, db_session):
    """Невалидный refresh-токен логируется как token_refresh_failed (warning)."""
    response = client.post(
        "/api/v1/auth/refresh", cookies={"refresh_token": "not-a-valid-jwt"}
    )
    assert response.status_code == 401

    rows = (
        await db_session.execute(
            select(SecurityEvent).where(SecurityEvent.event_type == "token_refresh_failed")
        )
    ).scalars().all()
    assert len(rows) >= 1
    assert rows[-1].severity == "warning"


# ---------------------------------------------------------------------------
# 3. Доступ к admin-эндпоинтам
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_audit_and_security_forbidden_for_regular_user(client, db_session):
    """Обычный пользователь получает 403 на audit и security endpoints."""
    user_headers, _ = auth_headers(client, "sec-regular@example.com")
    for endpoint in ("/api/v1/admin/audit", "/api/v1/admin/security/events"):
        response = client.get(endpoint, headers=user_headers)
        assert response.status_code == 403, f"{endpoint} -> {response.status_code}"


@pytest.mark.asyncio
async def test_superuser_gets_security_events(client, db_session):
    """Superuser получает события безопасности со сводкой по severity."""
    admin_headers, payload = auth_headers(client, "sec-admin@example.com")
    await make_superuser(db_session, payload["user"]["id"])

    # Сгенерируем хотя бы одно событие.
    do_login(client, "sec-admin@example.com", password="WrongPass!")

    response = client.get("/api/v1/admin/security/events", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert "summary" in data and set(data["summary"]) == {"info", "warning", "high", "critical"}
    assert isinstance(data["items"], list)
    assert "recent_failed_logins" in data


@pytest.mark.asyncio
async def test_superuser_gets_audit(client, db_session):
    """Superuser получает журнал действий."""
    admin_headers, payload = auth_headers(client, "audit-admin@example.com")
    await make_superuser(db_session, payload["user"]["id"])

    # auth.login появится в audit.
    do_login(client, "audit-admin@example.com")

    response = client.get("/api/v1/admin/audit", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert isinstance(data["items"], list)
    assert "total" in data


# ---------------------------------------------------------------------------
# 4. Эндпоинты не отдают секреты
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_audit_endpoint_does_not_leak_secrets(client, db_session):
    """Даже если в метаданные передан секрет — эндпоинт отдаёт только маску."""
    admin_headers, payload = auth_headers(client, "audit-secret@example.com")
    await make_superuser(db_session, payload["user"]["id"])

    # Пишем событие с "секретами" напрямую через сервис.
    await log_audit_event(
        db_session,
        action="test.secret",
        actor_user_id=UUID(payload["user"]["id"]),
        metadata={
            "password": "TopSecretPass1!",
            "api_key": "sk-RAW-KEY-9999",
            "token": "Bearer-RAW-TOKEN",
            "note": "safe-note",
        },
    )

    response = client.get("/api/v1/admin/audit?action=test.secret", headers=admin_headers)
    assert response.status_code == 200
    body = response.text
    assert "TopSecretPass1!" not in body
    assert "sk-RAW-KEY-9999" not in body
    assert "Bearer-RAW-TOKEN" not in body
    assert "***" in body
    assert "safe-note" in body


@pytest.mark.asyncio
async def test_security_endpoint_does_not_leak_password(client, db_session):
    """В выдаче security/events не должно быть сырых паролей."""
    admin_headers, payload = auth_headers(client, "sec-secret@example.com")
    await make_superuser(db_session, payload["user"]["id"])

    do_login(client, "sec-secret@example.com", password="LeakMePlease9!")

    response = client.get("/api/v1/admin/security/events", headers=admin_headers)
    assert response.status_code == 200
    assert "LeakMePlease9!" not in response.text
