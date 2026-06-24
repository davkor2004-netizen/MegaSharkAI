"""
WebSocket эндпоинты для чата поддержки.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import asyncio
import json
from loguru import logger

from app.core.database import get_db
from app.core.auth_cookies import ACCESS_TOKEN_COOKIE_NAME
from app.services.auth_service import get_current_user_from_ws
from app.models.user import User
from app.models.chat import ChatMessageRole, ChatConversation
from app.crud.chat import chat_message_crud, chat_conversation_crud
from app.websocket.manager import ws_manager
from app.schemas.chat import WSEventType

router = APIRouter()


async def validate_conversation_access(
    db: AsyncSession,
    conversation_id: int,
    user: User,
) -> bool:
    """Проверить доступ к конверсации."""
    conversation = await db.get(ChatConversation, conversation_id)
    if not conversation:
        return False
    
    # Админ имеет доступ ко всем
    if user.is_superuser:
        return True
    
    # Пользователь имеет доступ только к своим
    if conversation.user_id == user.id:
        return True
    
    # Админ, назначенный на чат
    if conversation.admin_id == user.id:
        return True
    
    return False


@router.websocket("/chat")
async def chat_websocket_endpoint(
    websocket: WebSocket,
    conversation_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket подключение для чата поддержки.
    
    Параметры:
        conversation_id: ID конверсации (опционально, можно подключиться ко всем)
    
    Клиент авторизуется через HttpOnly cookie или первым сообщением:
    {"type": "auth", "token": "<JWT>"}  (token опционален при cookie)
    """
    await websocket.accept()
    
    user: Optional[User] = None
    token: Optional[str] = websocket.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    
    try:
        if not token:
            # Fallback: Bearer в первом auth-сообщении (API-клиенты, тесты)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=10)
                auth_data = json.loads(data)
            except asyncio.TimeoutError:
                await websocket.send_json({
                    "type": WSEventType.ERROR.value,
                    "data": {"message": "Таймаут авторизации WebSocket"},
                })
                await websocket.close(code=1008)
                return
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": WSEventType.ERROR.value,
                    "data": {"message": "Первое WebSocket сообщение должно быть JSON auth-сообщением"},
                })
                await websocket.close(code=1008)
                return

            if auth_data.get("type") != "auth":
                await websocket.send_json({
                    "type": WSEventType.ERROR.value,
                    "data": {"message": "Первое WebSocket сообщение должно иметь type=auth"},
                })
                await websocket.close(code=1008)
                return

            token = auth_data.get("token")

        if not token:
            await websocket.send_json({
                "type": WSEventType.ERROR.value,
                "data": {"message": "Требуется авторизация"},
            })
            await websocket.close(code=1008)
            return
        
        async def handle_authenticated_connection() -> None:
            nonlocal user
            user = await get_current_user_from_ws(token, db)
            
            if not user:
                await websocket.send_json({
                    "type": WSEventType.ERROR.value,
                    "data": {"message": "Неверный токен"},
                })
                await websocket.close(code=1008)
                return
            
            is_admin = user.is_superuser
            
            # Подключаем к менеджеру
            if conversation_id:
                # Проверяем доступ к конкретной конверсации
                has_access = await validate_conversation_access(db, conversation_id, user)
                if not has_access:
                    await websocket.send_json({
                        "type": WSEventType.ERROR.value,
                        "data": {"message": "Нет доступа к этому чату"},
                    })
                    await websocket.close(code=1008)
                    return
                
                if is_admin:
                    await ws_manager.connect_admin(websocket, user.id, conversation_id)
                else:
                    await ws_manager.connect_user(websocket, user.id, conversation_id)
                
                logger.info(f"💬 {user.email} подключился к чату {conversation_id}")
            else:
                # Подключение ко всем чатам (для админа)
                if is_admin:
                    await ws_manager.connect_admin(websocket, user.id)
                    logger.info(f"👨‍💼 Админ {user.email} подключился ко всем чатам")
                else:
                    # Обычный пользователь должен указать conversation_id
                    await websocket.send_json({
                        "type": WSEventType.ERROR.value,
                        "data": {"message": "Пользователь должен указать conversation_id"},
                    })
                    await websocket.close(code=1008)
                    return
            
            # Отправляем подтверждение подключения
            await websocket.send_json({
                "type": "connected",
                "data": {
                    "user_id": str(user.id),
                    "is_admin": is_admin,
                    "conversation_id": conversation_id,
                },
            })
            
            # Цикл получения сообщений
            while True:
                try:
                    data = await websocket.receive_text()
                    message_data = json.loads(data)
                    
                    msg_type = message_data.get("type", "message")
                    
                    if msg_type == "message":
                        # Новое сообщение
                        text = message_data.get("text", "").strip()
                        if not text:
                            continue
                        
                        conv_id = message_data.get("conversation_id") or conversation_id
                        if not conv_id:
                            await websocket.send_json({
                                "type": WSEventType.ERROR.value,
                                "data": {"message": "Требуется conversation_id"},
                            })
                            continue
                        
                        # Проверяем доступ
                        has_access = await validate_conversation_access(db, conv_id, user)
                        if not has_access:
                            continue
                        
                        # Создаём сообщение в БД
                        sender_role = ChatMessageRole.ADMIN if is_admin else ChatMessageRole.USER
                        is_internal = message_data.get("is_internal", False) and is_admin
                        
                        message = await chat_message_crud.create_message(
                            db=db,
                            conversation_id=conv_id,
                            sender_id=user.id,
                            sender_role=sender_role,
                            text=text,
                            is_internal=is_internal,
                        )
                        
                        # Формируем ответ для рассылки
                        message_payload = {
                            "id": message.id,
                            "conversation_id": message.conversation_id,
                            "sender_id": str(message.sender_id),
                            "sender_role": message.sender_role if isinstance(message.sender_role, str) else message.sender_role.value,
                            "text": message.text,
                            "is_read": message.is_read,
                            "is_internal": message.is_internal,
                            "created_at": message.created_at.isoformat(),
                        }
                        
                        # Рассылаем всем подключенным к конверсации
                        broadcast_data = {
                            "type": WSEventType.MESSAGE_NEW.value,
                            "conversation_id": conv_id,
                            "data": message_payload,
                        }
                        
                        await ws_manager.broadcast_to_conversation(
                            broadcast_data,
                            conv_id,
                            exclude_websocket=websocket,
                        )
                        
                        # Отправляем подтверждение отправителю
                        await websocket.send_json({
                            "type": "message:ack",
                            "data": message_payload,
                        })
                        
                        logger.info(f"📩 Сообщение в чате {conv_id} от {user.email}")
                    
                    elif msg_type == "typing":
                        # Индикатор набора текста
                        conv_id = message_data.get("conversation_id") or conversation_id
                        if conv_id:
                            has_access = await validate_conversation_access(db, conv_id, user)
                            if not has_access:
                                continue
                            await ws_manager.send_typing_indicator(
                                conv_id,
                                user.id,
                                is_admin,
                            )
                    
                    elif msg_type == "read":
                        # Прочитано
                        conv_id = message_data.get("conversation_id") or conversation_id
                        if conv_id:
                            has_access = await validate_conversation_access(db, conv_id, user)
                            if not has_access:
                                continue
                            reader_role = ChatMessageRole.ADMIN if is_admin else ChatMessageRole.USER
                            await chat_message_crud.mark_as_read(db, conv_id, reader_role)
                            
                            # Уведомляем другую сторону
                            await ws_manager.broadcast_to_conversation(
                                {
                                    "type": WSEventType.MESSAGE_READ.value,
                                    "conversation_id": conv_id,
                                    "data": {
                                        "reader_id": str(user.id),
                                        "is_admin": is_admin,
                                    },
                                },
                                conv_id,
                            )
                    
                    elif msg_type == "close":
                        # Закрыть чат (только админ)
                        if is_admin:
                            conv_id = message_data.get("conversation_id") or conversation_id
                            if conv_id:
                                has_access = await validate_conversation_access(db, conv_id, user)
                                if not has_access:
                                    continue
                                await chat_conversation_crud.close_conversation(db, conv_id)
                                await ws_manager.broadcast_to_conversation(
                                    {
                                        "type": WSEventType.CONVERSATION_CLOSED.value,
                                        "conversation_id": conv_id,
                                    },
                                    conv_id,
                                )
                    
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": WSEventType.ERROR.value,
                        "data": {"message": "Неверный формат JSON"},
                    })

        await handle_authenticated_connection()
    
    except WebSocketDisconnect:
        logger.info(f"🔌 {user.email if user else 'Unknown'} отключился от WebSocket")
    except Exception as e:
        logger.error(f"❌ Ошибка WebSocket: {e}")
    finally:
        # Отключаем от менеджера
        if user:
            await ws_manager.disconnect(
                websocket,
                user_id=user.id if not user.is_superuser else None,
                admin_id=user.id if user.is_superuser else None,
                conversation_id=conversation_id,
            )
