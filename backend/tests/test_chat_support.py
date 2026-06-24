"""
Тесты REST-части чата поддержки.
"""

from uuid import UUID

import pytest
from sqlalchemy import select

from app.models.chat import ChatConversation, ChatConversationStatus, ChatMessage, ChatMessageRole
from app.models.user import User


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


async def make_superuser(db_session, user_id: str) -> None:
    """Выдать пользователю права администратора в тестовой БД."""
    result = await db_session.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one()
    user.is_superuser = True
    await db_session.commit()


def test_chat_admin_list_requires_admin(client):
    """Обычный пользователь получает 403 на admin list, не 500."""
    headers, _ = register_with_headers(client, "chat-non-admin@example.com")

    response = client.get("/api/v1/chat/admin/conversations", headers=headers)

    assert response.status_code == 403


def test_chat_websocket_auth_and_message_ack(client):
    """WebSocket принимает auth первым сообщением и возвращает ack отправителю."""
    headers, payload = register_with_headers(client, "chat-ws-user@example.com")
    token = payload["access_token"]

    create_response = client.post(
        "/api/v1/chat/conversations",
        json={"topic": "WS проверка"},
        headers=headers,
    )
    assert create_response.status_code == 200, create_response.text
    conversation_id = create_response.json()["id"]

    with client.websocket_connect(f"/ws/chat?conversation_id={conversation_id}") as websocket:
        websocket.send_json({"type": "auth", "token": token})
        connected = websocket.receive_json()
        assert connected["type"] == "connected"
        assert connected["data"]["conversation_id"] == conversation_id

        websocket.send_json({
            "type": "message",
            "conversation_id": conversation_id,
            "text": "Сообщение через WebSocket",
        })
        ack = websocket.receive_json()

    assert ack["type"] == "message:ack"
    assert ack["data"]["conversation_id"] == conversation_id
    assert ack["data"]["text"] == "Сообщение через WebSocket"
    assert ack["data"]["sender_id"] == payload["user"]["id"]


@pytest.mark.asyncio
async def test_internal_admin_messages_are_hidden_from_user(client, db_session):
    """Internal notes видит админ, но не пользователь."""
    user_headers, user_payload = register_with_headers(client, "chat-user@example.com")
    admin_headers, admin_payload = register_with_headers(client, "chat-admin@example.com")
    await make_superuser(db_session, admin_payload["user"]["id"])

    conversation = ChatConversation(
        user_id=UUID(user_payload["user"]["id"]),
        admin_id=UUID(admin_payload["user"]["id"]),
        topic="Проверка internal notes",
        is_active=True,
        is_closed=False,
        status=ChatConversationStatus.IN_PROGRESS.value,
    )
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)
    conversation_id = conversation.id

    db_session.add_all([
        ChatMessage(
            conversation_id=conversation.id,
            sender_id=UUID(admin_payload["user"]["id"]),
            sender_role=ChatMessageRole.ADMIN.value,
            text="Внутренняя заметка",
            is_internal=True,
        ),
        ChatMessage(
            conversation_id=conversation.id,
            sender_id=UUID(admin_payload["user"]["id"]),
            sender_role=ChatMessageRole.ADMIN.value,
            text="Публичный ответ",
            is_internal=False,
        ),
    ])
    await db_session.commit()
    db_session.expire_all()

    admin_response = client.get(f"/api/v1/chat/conversations/{conversation_id}", headers=admin_headers)
    db_session.expire_all()
    user_response = client.get(f"/api/v1/chat/conversations/{conversation_id}", headers=user_headers)

    assert admin_response.status_code == 200
    assert user_response.status_code == 200

    admin_messages = admin_response.json()["messages"]
    user_messages = user_response.json()["messages"]

    assert {message["text"] for message in admin_messages} == {"Внутренняя заметка", "Публичный ответ"}
    assert [message["text"] for message in user_messages] == ["Публичный ответ"]
