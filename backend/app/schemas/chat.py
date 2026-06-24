"""
Схемы Pydantic для чата поддержки.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum


class ChatMessageRoleEnum(str, Enum):
    """Роль отправителя сообщения."""
    USER = "user"
    ADMIN = "admin"


class ChatMessageBase(BaseModel):
    """Базовая схема сообщения."""
    text: str = Field(..., min_length=1, max_length=5000, description="Текст сообщения")
    is_internal: Optional[bool] = Field(False, description="Внутренняя заметка (только для админов)")


class ChatMessageCreate(ChatMessageBase):
    """Создание сообщения."""
    pass


class ChatMessageResponse(BaseModel):
    """Ответ с сообщением."""
    id: int
    conversation_id: int
    sender_id: UUID
    sender_role: ChatMessageRoleEnum
    text: str
    is_read: bool
    is_internal: Optional[bool] = False
    created_at: datetime
    edited_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ChatUserBrief(BaseModel):
    """Краткая информация о пользователе."""
    id: UUID
    email: str
    full_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class ChatConversationStatusEnum(str, Enum):
    """Статусы диалога поддержки."""
    WAITING_RESPONSE = "waiting_response"
    IN_PROGRESS = "in_progress"
    ANSWERED = "answered"
    CLOSED = "closed"


class ChatConversationBase(BaseModel):
    """Базовая схема конверсации."""
    topic: Optional[str] = Field(None, max_length=255, description="Тема обращения")


class ChatConversationCreate(ChatConversationBase):
    """Создание конверсации."""
    pass


class ChatConversationResponse(ChatConversationBase):
    """Ответ с конверсацией."""
    id: int
    user_id: UUID
    user: Optional[ChatUserBrief] = None
    admin_id: Optional[UUID] = None
    admin: Optional[ChatUserBrief] = None
    is_active: bool
    is_closed: bool
    status: ChatConversationStatusEnum
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    messages: List[ChatMessageResponse] = []
    
    class Config:
        from_attributes = True


class ChatConversationListResponse(BaseModel):
    """Список конверсаций (кратко)."""
    id: int
    topic: Optional[str]
    is_active: bool
    is_closed: bool
    status: ChatConversationStatusEnum
    last_message_at: Optional[datetime]
    last_message_preview: Optional[str] = None  # Краткий текст последнего сообщения
    unread_count: int = 0
    admin_email: Optional[str] = None  # Email админа, если назначен
    
    class Config:
        from_attributes = True


class ChatAdminConversationListResponse(BaseModel):
    """Список конверсаций для админа."""
    id: int
    topic: Optional[str]
    user_email: str
    user_name: Optional[str]
    admin_id: Optional[UUID] = None
    admin_email: Optional[str] = None
    is_active: bool
    is_closed: bool
    status: ChatConversationStatusEnum
    last_message_at: Optional[datetime]
    last_message_preview: Optional[str]
    unread_count: int = 0
    
    class Config:
        from_attributes = True


class WebSocketMessage(BaseModel):
    """Сообщение WebSocket."""
    type: str  # "message", "typing", "read", "status"
    conversation_id: Optional[int] = None
    data: Optional[dict] = None


# WebSocket типы событий
class WSEventType(str, Enum):
    """Типы WebSocket событий."""
    MESSAGE_NEW = "message:new"
    MESSAGE_READ = "message:read"
    CONVERSATION_ASSIGNED = "conversation:assigned"
    CONVERSATION_CLOSED = "conversation:closed"
    TYPING = "typing"
    ERROR = "error"
