"""
Тестовый скрипт для проверки API чата.
"""
import asyncio
from uuid import uuid4

from app.core.database import get_db
from app.models.user import User
from app.models.chat import ChatMessageRole
from app.crud.chat import chat_conversation_crud, chat_message_crud


async def test_chat_api():
    """Протестировать API чата."""
    async for db in get_db():
        # Создаём тестового пользователя если нет
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.email == "test_chat@example.com"))
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                id=uuid4(),
                email="test_chat@example.com",
                full_name="Test Chat User",
                hashed_password="fake_hash",
                is_active=True,
                is_superuser=False,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            print(f"Создан пользователь: {user.id}")
        else:
            print(f"Найден пользователь: {user.id}")
        
        # Создаём конверсацию
        conv = await chat_conversation_crud.create_conversation(
            db=db,
            user_id=user.id,
            topic="Тестовое обращение",
        )
        print(f"Создана конверсация: {conv.id}")
        
        # Создаём сообщение
        msg = await chat_message_crud.create_message(
            db=db,
            conversation_id=conv.id,
            sender_id=user.id,
            sender_role=ChatMessageRole.USER,
            text="Привет, это тестовое сообщение!",
        )
        print(f"Создано сообщение: {msg.id}")
        
        # Получаем конверсации пользователя
        convs = await chat_conversation_crud.get_user_conversations(
            db=db,
            user_id=user.id,
        )
        print(f"Конверсаций пользователя: {len(convs)}")
        
        # Получаем сообщения
        msgs = await chat_message_crud.get_messages(
            db=db,
            conversation_id=conv.id,
        )
        print(f"Сообщений в конверсации: {len(msgs)}")
        
        print("\n✅ Все тесты пройдены!")


if __name__ == "__main__":
    asyncio.run(test_chat_api())
