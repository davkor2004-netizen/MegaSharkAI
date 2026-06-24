"""
Модели чата поддержки.

Поддержка живого общения между пользователями и администраторами.
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.models.base import Base


class ChatMessageRole(str, enum.Enum):
    """Роль отправителя сообщения."""
    USER = "user"
    ADMIN = "admin"


class ChatConversationStatus(str, enum.Enum):
    """Статусы диалога поддержки."""
    WAITING_RESPONSE = "waiting_response"   # Ждёт ответа администратора
    IN_PROGRESS = "in_progress"             # В процессе
    ANSWERED = "answered"                   # Админ ответил
    CLOSED = "closed"                       # Закрыто


class ChatConversation(Base):
    """
    Чат-конверсация между пользователем и поддержкой.
    """
    __tablename__ = "chat_conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Пользователь, который начал чат (UUID как в users)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user = relationship("User", foreign_keys=[user_id], back_populates="chat_conversations")
    
    # Статус конверсации
    is_active = Column(Boolean, default=True, nullable=False)
    is_closed = Column(Boolean, default=False, nullable=False)
    status = Column(String(32), default=ChatConversationStatus.WAITING_RESPONSE.value, nullable=False, index=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Кто из админов отвечает
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    admin = relationship("User", foreign_keys=[admin_id], back_populates="chat_conversations_admin")
    
    # Тема/заголовок
    topic = Column(String(255), nullable=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    
    # Сообщения в конверсации
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ChatMessage.created_at")
    
    def __repr__(self):
        return f"<ChatConversation id={self.id} user_id={self.user_id} active={self.is_active}>"


class ChatMessage(Base):
    """
    Сообщение в чате поддержки.
    """
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Ссылка на конверсацию
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation = relationship("ChatConversation", back_populates="messages")
    
    # Кто отправил (UUID как в users)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sender = relationship("User", foreign_keys=[sender_id], back_populates="chat_messages")
    
    # Роль отправителя
    sender_role = Column(String(20), nullable=False)
    
    # Текст сообщения
    text = Column(Text, nullable=False)
    
    # Статусы прочтения
    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    edited_at = Column(DateTime(timezone=True), nullable=True)
    
    # Внутренняя заметка (только для админов)
    is_internal = Column(Boolean, default=False, nullable=True)
    
    def __repr__(self):
        return f"<ChatMessage id={self.id} conv={self.conversation_id} role={self.sender_role}>"
