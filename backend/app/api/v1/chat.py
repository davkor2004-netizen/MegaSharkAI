"""
REST API эндпоинты для чата поддержки.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Literal
from loguru import logger

from app.core.database import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.crud.chat import chat_conversation_crud, chat_message_crud
from app.schemas.chat import (
    ChatConversationCreate,
    ChatConversationResponse,
    ChatConversationListResponse,
    ChatAdminConversationListResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatUserBrief,
    ChatMessageRoleEnum,
    ChatConversationStatusEnum,
)
from app.models.chat import ChatMessageRole, ChatConversationStatus

router = APIRouter()


@router.post(
    "/conversations",
    response_model=ChatConversationResponse,
    summary="Создать новый чат",
    description="Создать новую конверсацию для обращения в поддержку",
)
async def create_conversation(
    conversation_data: ChatConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Создать новый чат с поддержкой.
    
    Пользователь создаёт обращение, администраторы увидят его в списке.
    """
    logger.info(f"💬 Создание чата пользователем {current_user.email}")
    
    conversation = await chat_conversation_crud.create_conversation(
        db=db,
        user_id=current_user.id,
        topic=conversation_data.topic,
        enforce_history_limit=not current_user.is_superuser,
        history_limit=100,
    )
    
    # Получаем полную информацию с сообщениями (пустой список)
    conversation = await chat_conversation_crud.get_conversation(
        db=db,
        conversation_id=conversation.id,
        user_id=current_user.id,
        is_admin=current_user.is_superuser,
    )
    
    return conversation


@router.get(
    "/conversations",
    response_model=List[ChatConversationListResponse],
    summary="Мои чаты",
    description="Получить список всех чатов пользователя",
)
async def get_my_conversations(
    include_closed: bool = Query(False, description="Включая закрытые"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить все чаты текущего пользователя."""
    conversations = await chat_conversation_crud.get_user_conversations(
        db=db,
        user_id=current_user.id,
        include_closed=include_closed,
        limit=limit,
    )
    
    # Формируем краткий ответ
    result = []
    for conv in conversations:
        last_message = conv.messages[-1] if conv.messages else None
        unread = sum(1 for m in conv.messages if not m.is_read and m.sender_id != current_user.id)
        
        result.append(ChatConversationListResponse(
            id=conv.id,
            topic=conv.topic,
            is_active=conv.is_active,
            is_closed=conv.is_closed,
            status=conv.status,
            last_message_at=conv.last_message_at,
            last_message_preview=last_message.text[:100] if last_message else None,
            unread_count=unread,
            admin_email=conv.admin.email if conv.admin else None,
        ))
    
    return result


@router.get(
    "/conversations/{conversation_id}",
    response_model=ChatConversationResponse,
    summary="Детали чата",
    description="Получить полную информацию о чате с сообщениями",
)
async def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить детали конкретного чата."""
    conversation = await chat_conversation_crud.get_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        is_admin=current_user.is_superuser,
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Чат не найден или нет доступа",
        )
    
    return conversation


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ChatMessageResponse,
    summary="Отправить сообщение",
    description="Отправить сообщение в чат (HTTP альтернатива WebSocket)",
)
async def send_message(
    conversation_id: int,
    message_data: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Отправить сообщение в чат через HTTP.
    
    Для реального времени используйте WebSocket.
    """
    # Проверяем доступ
    conversation = await chat_conversation_crud.get_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        is_admin=current_user.is_superuser,
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Чат не найден или нет доступа",
        )
    
    if conversation.is_closed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Чат закрыт",
        )
    
    # Определяем роль
    sender_role = ChatMessageRoleEnum.ADMIN if current_user.is_superuser else ChatMessageRoleEnum.USER
    role = ChatMessageRole.ADMIN if current_user.is_superuser else ChatMessageRole.USER
    
    # Создаём сообщение
    message = await chat_message_crud.create_message(
        db=db,
        conversation_id=conversation_id,
        sender_id=current_user.id,
        sender_role=role,
        text=message_data.text,
        is_internal=message_data.is_internal if current_user.is_superuser else False,
    )
    
    logger.info(f"📩 Сообщение в чате {conversation_id} от {current_user.email}")
    
    return ChatMessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        sender_role=sender_role,
        text=message.text,
        is_read=message.is_read,
        is_internal=message.is_internal,
        created_at=message.created_at,
        edited_at=message.edited_at,
    )


# === Админские эндпоинты ===

@router.get(
    "/admin/conversations",
    response_model=List[ChatAdminConversationListResponse],
    summary="Все чаты (админ)",
    description="Получить список всех чатов для администратора",
)
async def get_all_conversations(
    conversation_status: Literal["all", "active", "closed", "unassigned", "waiting_response", "in_progress", "answered"] = Query(
        "all",
        alias="status",
        description="all, active, closed, unassigned, waiting_response, in_progress, answered",
    ),
    only_my: bool = Query(False, description="Только чаты, назначенные текущему админу"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить все чаты для администратора."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуется права администратора",
        )
    
    conversations = await chat_conversation_crud.get_admin_conversations(
        db=db,
        admin_id=current_user.id,
        status=conversation_status,
        limit=limit,
        only_my=only_my,
    )
    
    result = []
    for conv in conversations:
        last_message = conv.messages[-1] if conv.messages else None
        unread = sum(1 for m in conv.messages if not m.is_read and m.sender_role == ChatMessageRole.USER)
        
        result.append(ChatAdminConversationListResponse(
            id=conv.id,
            topic=conv.topic,
            user_email=conv.user.email,
            user_name=conv.user.full_name,
            admin_id=conv.admin_id,
            admin_email=conv.admin.email if conv.admin else None,
            is_active=conv.is_active,
            is_closed=conv.is_closed,
            status=conv.status,
            last_message_at=conv.last_message_at,
            last_message_preview=last_message.text[:100] if last_message else None,
            unread_count=unread,
        ))
    
    return result


@router.post(
    "/admin/conversations/{conversation_id}/assign",
    summary="Назначить админа на чат",
    description="Взять чат в работу",
)
async def assign_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Назначить себя администратором на чат."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуется права администратора",
        )
    
    conversation = await chat_conversation_crud.assign_admin(
        db=db,
        conversation_id=conversation_id,
        admin_id=current_user.id,
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Чат не найден",
        )
    
    logger.info(f"👨‍💼 Админ {current_user.email} взял чат {conversation_id}")
    
    return {
        "status": "success",
        "message": f"Чат {conversation_id} назначен вам",
        "conversation_id": conversation_id,
    }


@router.post(
    "/admin/conversations/{conversation_id}/status",
    summary="Обновить статус чата",
    description="Изменить статус диалога: waiting_response, in_progress, answered, closed",
)
async def update_conversation_status(
    conversation_id: int,
    status_value: ChatConversationStatusEnum,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Обновить статус чата."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуется права администратора",
        )

    conversation = await chat_conversation_crud.update_status(
        db=db,
        conversation_id=conversation_id,
        status_value=status_value.value,
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Чат не найден",
        )

    logger.info(f"✅ Админ {current_user.email} изменил статус чата {conversation_id} на {status_value.value}")

    return {
        "status": "success",
        "message": f"Статус чата {conversation_id} обновлён",
        "conversation_status": conversation.status,
    }


@router.post(
    "/admin/conversations/{conversation_id}/close",
    summary="Закрыть чат",
    description="Завершить обращение",
)
async def close_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Закрыть чат."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуется права администратора",
        )

    conversation = await chat_conversation_crud.close_conversation(
        db=db,
        conversation_id=conversation_id,
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Чат не найден",
        )

    logger.info(f"✅ Админ {current_user.email} закрыл чат {conversation_id}")

    return {
        "status": "success",
        "message": f"Чат {conversation_id} закрыт",
    }
