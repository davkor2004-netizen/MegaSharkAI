"""
Миграция для создания таблиц чата поддержки.

Запуск: python migrate_chat.py
"""

import asyncio
import os
from sqlalchemy import text
from app.core.database import engine


async def migrate():
    """Создание таблиц чата."""
    
    async with engine.begin() as conn:
        if os.getenv("CONFIRM_DROP_CHAT_TABLES") == "yes":
            await conn.execute(text("DROP TABLE IF EXISTS chat_messages CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS chat_conversations CASCADE"))
        
        # Таблица конверсаций
        await conn.execute(text("""
            CREATE TABLE chat_conversations (
                id SERIAL PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                admin_id UUID REFERENCES users(id) ON DELETE SET NULL,
                topic VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE NOT NULL,
                is_closed BOOLEAN DEFAULT FALSE NOT NULL,
                closed_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMPTZ,
                last_message_at TIMESTAMPTZ
            )
        """))
        
        # Индексы для конверсаций
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_chat_conv_user_active 
            ON chat_conversations(user_id, is_active)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_chat_conv_admin_active 
            ON chat_conversations(admin_id, is_active)
        """))
        
        # Таблица сообщений
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id SERIAL PRIMARY KEY,
                conversation_id INTEGER NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
                sender_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                sender_role VARCHAR(20) NOT NULL,
                text TEXT NOT NULL,
                is_read BOOLEAN DEFAULT FALSE NOT NULL,
                read_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
                edited_at TIMESTAMPTZ,
                is_internal BOOLEAN DEFAULT FALSE
            )
        """))
        
        # Индексы для сообщений
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_chat_msg_conv_created 
            ON chat_messages(conversation_id, created_at)
        """))
        
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_chat_messages_sender_id 
            ON chat_messages(sender_id)
        """))
        
        print("SUCCESS: Chat tables ensured!")


if __name__ == "__main__":
    asyncio.run(migrate())
