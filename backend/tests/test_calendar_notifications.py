"""
Тесты календаря и уведомлений.
"""

from datetime import datetime, timedelta
from uuid import UUID

import pytest

from app.models.notification import Notification, SaleCalendar


def register_with_headers(client, email: str) -> tuple[dict[str, str], dict]:
    """Создать пользователя и вернуть Authorization header."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "TestPass123!",
            "full_name": "Тестовый Пользователь",
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    return {"Authorization": f"Bearer {payload['access_token']}"}, payload


def test_calendar_static_routes_are_not_captured_by_event_id(client):
    """Статические маршруты calendar/upcoming и export не должны падать в /{event_id:int}."""
    headers, _ = register_with_headers(client, "calendar-routes@example.com")

    upcoming_response = client.get("/api/v1/calendar/upcoming", headers=headers)
    csv_response = client.get("/api/v1/calendar/export/csv", headers=headers)
    ics_response = client.get("/api/v1/calendar/export/ics", headers=headers)

    assert upcoming_response.status_code == 200
    assert isinstance(upcoming_response.json(), list)
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    assert ics_response.status_code == 200
    assert "text/calendar" in ics_response.headers["content-type"]


@pytest.mark.asyncio
async def test_calendar_delete_foreign_event_returns_not_found(client, db_session):
    """Удаление чужого события не раскрывает его наличие."""
    first_headers, _ = register_with_headers(client, "calendar-owner-a@example.com")
    _, second_user = register_with_headers(client, "calendar-owner-b@example.com")

    event = SaleCalendar(
        user_id=UUID(second_user["user"]["id"]),
        title="Чужая акция",
        marketplace="wildberries",
        event_type="sale",
        start_date=datetime.utcnow() + timedelta(days=1),
        end_date=datetime.utcnow() + timedelta(days=2),
        is_global=False,
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)

    response = client.delete(f"/api/v1/calendar/{event.id}", headers=first_headers)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_notifications_are_user_scoped_and_mark_read(client, db_session):
    """Пользователь видит и помечает прочитанными только свои уведомления."""
    first_headers, first_user = register_with_headers(client, "notifications-a@example.com")
    _, second_user = register_with_headers(client, "notifications-b@example.com")

    own_notification = Notification(
        user_id=UUID(first_user["user"]["id"]),
        title="Своё уведомление",
        message="Только для первого пользователя",
        type="system",
        is_read=False,
    )
    foreign_notification = Notification(
        user_id=UUID(second_user["user"]["id"]),
        title="Чужое уведомление",
        message="Не должно быть видно",
        type="system",
        is_read=False,
    )
    db_session.add_all([own_notification, foreign_notification])
    await db_session.commit()
    await db_session.refresh(own_notification)
    await db_session.refresh(foreign_notification)

    list_response = client.get("/api/v1/notifications/", headers=first_headers)
    assert list_response.status_code == 200
    notifications = list_response.json()
    assert len(notifications) == 1
    assert notifications[0]["title"] == "Своё уведомление"

    foreign_mark_response = client.post(
        f"/api/v1/notifications/mark-read/{foreign_notification.id}",
        headers=first_headers,
    )
    assert foreign_mark_response.status_code == 404

    own_mark_response = client.post(
        f"/api/v1/notifications/mark-read/{own_notification.id}",
        headers=first_headers,
    )
    assert own_mark_response.status_code == 200

    unread_response = client.get("/api/v1/notifications/unread-count", headers=first_headers)
    assert unread_response.status_code == 200
    assert unread_response.json()["unread_count"] == 0


def test_telegram_notifications_require_chat_id(client):
    """Telegram-уведомления нельзя включить без chat_id."""
    headers, _ = register_with_headers(client, "notifications-settings@example.com")

    response = client.post(
        "/api/v1/notifications/settings",
        headers=headers,
        json={
            "email_notifications": True,
            "telegram_notifications": True,
            "telegram_chat_id": "",
        },
    )

    assert response.status_code == 422
