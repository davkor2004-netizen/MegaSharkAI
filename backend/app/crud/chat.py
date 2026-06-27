"""
CRUD операции для чата поддержки.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, update
from sqlalchemy.orm import joinedload, with_loader_criteria
from typing import List, Optional
from datetime import datetime
from uuid import UUID

from app.core.datetime_utils import utcnow
from app.models.chat import ChatConversation, ChatMessage, ChatMessageRole, ChatConversationStatus
from app.models.user import User


class ChatConversationCRUD:
    """Операции для конверсаций чата."""
    
    async def create_conversation(
        self,
        db: AsyncSession,
        user_id: UUID,
        topic: Optional[str] = None,
        enforce_history_limit: bool = True,
        history_limit: int = 100,
    ) -> ChatConversation:
        """Создать новую конверсацию."""
        # Ограничиваем историю обращений пользователя.
        # Если лимит достигнут, удаляем самые старые диалоги,
        # чтобы после создания нового осталось не более history_limit.
        if enforce_history_limit:
            total_conversations_query = select(func.count(ChatConversation.id)).where(
                ChatConversation.user_id == user_id
            )
            total_conversations = (await db.execute(total_conversations_query)).scalar() or 0

            overflow_count = total_conversations - history_limit + 1
            if overflow_count > 0:
                oldest_conversations_query = (
                    select(ChatConversation)
                    .where(ChatConversation.user_id == user_id)
                    .order_by(
                        ChatConversation.last_message_at.asc().nullsfirst(),
                        ChatConversation.created_at.asc(),
                    )
                    .limit(overflow_count)
                )
                oldest_conversations = (await db.execute(oldest_conversations_query)).scalars().all()

                for old_conversation in oldest_conversations:
                    await db.delete(old_conversation)

        conversation = ChatConversation(
            user_id=user_id,
            topic=topic,
            is_active=True,
            is_closed=False,
            status=ChatConversationStatus.WAITING_RESPONSE.value,
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        return conversation
    
    async def get_conversation(
        self,
        db: AsyncSession,
        conversation_id: int,
        user_id: Optional[UUID] = None,
        is_admin: bool = False,
    ) -> Optional[ChatConversation]:
        """Получить конверсацию по ID."""
        query = select(ChatConversation).options(
            joinedload(ChatConversation.messages),
            joinedload(ChatConversation.user),
            joinedload(ChatConversation.admin),
        )
        if not is_admin:
            query = query.options(
                with_loader_criteria(ChatMessage, ChatMessage.is_internal == False)
            )
        query = query.where(ChatConversation.id == conversation_id)
        
        # Если не админ, проверяем принадлежность
        if not is_admin and user_id:
            query = query.where(ChatConversation.user_id == user_id)
        
        result = await db.execute(query)
        return result.unique().scalar_one_or_none()
    
    async def get_user_conversations(
        self,
        db: AsyncSession,
        user_id: UUID,
        include_closed: bool = False,
        limit: int = 20,
    ) -> List[ChatConversation]:
        """Получить все конверсации пользователя."""
        query = select(ChatConversation).options(
            joinedload(ChatConversation.messages),
            with_loader_criteria(ChatMessage, ChatMessage.is_internal == False),
            joinedload(ChatConversation.admin),
        )
        query = query.where(ChatConversation.user_id == user_id)
        
        if not include_closed:
            query = query.where(ChatConversation.is_closed == False)
        
        query = query.order_by(ChatConversation.last_message_at.desc())
        query = query.limit(limit)
        
        result = await db.execute(query)
        return list(result.unique().scalars().all())
    
    async def get_admin_conversations(
        self,
        db: AsyncSession,
        admin_id: Optional[UUID] = None,
        status: str = "all",  # all, active, closed, unassigned, waiting_response, in_progress, answered
        limit: int = 50,
        only_my: bool = False,
    ) -> List[ChatConversation]:
        """Получить конверсации для администратора."""
        query = select(ChatConversation).options(
            joinedload(ChatConversation.user),
            joinedload(ChatConversation.admin),
            joinedload(ChatConversation.messages),
        )
        
        if status == "active":
            query = query.where(ChatConversation.is_active == True)
            query = query.where(ChatConversation.is_closed == False)
            if admin_id:
                query = query.where(ChatConversation.admin_id == admin_id)
        elif status == "closed":
            query = query.where(ChatConversation.is_closed == True)
        elif status == "unassigned":
            query = query.where(ChatConversation.admin_id.is_(None))
            query = query.where(ChatConversation.is_active == True)
            query = query.where(ChatConversation.is_closed == False)
        elif status == "waiting_response":
            query = query.where(ChatConversation.status == ChatConversationStatus.WAITING_RESPONSE.value)
            query = query.where(ChatConversation.is_closed == False)
        elif status == "in_progress":
            query = query.where(ChatConversation.status == ChatConversationStatus.IN_PROGRESS.value)
            query = query.where(ChatConversation.is_closed == False)
        elif status == "answered":
            query = query.where(ChatConversation.status == ChatConversationStatus.ANSWERED.value)
            query = query.where(ChatConversation.is_closed == False)
        
        if only_my and admin_id:
            query = query.where(ChatConversation.admin_id == admin_id)

        query = query.order_by(ChatConversation.last_message_at.desc())
        query = query.limit(limit)
        
        result = await db.execute(query)
        return list(result.unique().scalars().all())

    async def assign_admin(
        self,
        db: AsyncSession,
        conversation_id: int,
        admin_id: UUID,
    ) -> Optional[ChatConversation]:
        """Назначить администратора на конверсацию."""
        conversation = await self.get_conversation(db, conversation_id, is_admin=True)
        if conversation:
            conversation.admin_id = admin_id
            conversation.is_active = True
            if conversation.status == ChatConversationStatus.WAITING_RESPONSE.value:
                conversation.status = ChatConversationStatus.IN_PROGRESS.value
            await db.commit()
            await db.refresh(conversation)
        return conversation
    
    async def update_status(
        self,
        db: AsyncSession,
        conversation_id: int,
        status_value: str,
    ) -> Optional[ChatConversation]:
        """Обновить статус конверсации."""
        conversation = await self.get_conversation(db, conversation_id, is_admin=True)
        if conversation:
            conversation.status = status_value
            if status_value == ChatConversationStatus.CLOSED.value:
                conversation.is_closed = True
                conversation.is_active = False
                conversation.closed_at = utcnow()
            else:
                conversation.is_closed = False
                conversation.is_active = True
                conversation.closed_at = None
            await db.commit()
            await db.refresh(conversation)
        return conversation

    async def close_conversation(
        self,
        db: AsyncSession,
        conversation_id: int,
    ) -> Optional[ChatConversation]:
        """Закрыть конверсацию."""
        return await self.update_status(db, conversation_id, ChatConversationStatus.CLOSED.value)
    
    async def update_last_message_time(
        self,
        db: AsyncSession,
        conversation_id: int,
    ) -> None:
        """Обновить время последнего сообщения."""
        await db.execute(
            update(ChatConversation)
            .where(ChatConversation.id == conversation_id)
            .values(last_message_at=utcnow())
        )
        

class ChatMessageCRUD:
    """Операции для сообщений чата."""
    
    async def create_message(
        self,
        db: AsyncSession,
        conversation_id: int,
        sender_id: UUID,
        sender_role: ChatMessageRole,
        text: str,
        is_internal: bool = False,
    ) -> ChatMessage:
        """Создать сообщение."""
        sender_role_str = sender_role.value if hasattr(sender_role, 'value') else str(sender_role)
        message = ChatMessage(
            conversation_id=conversation_id,
            sender_id=sender_id,
            sender_role=sender_role_str,
            text=text,
            is_internal=is_internal if sender_role_str == ChatMessageRole.ADMIN.value else False,
        )
        db.add(message)
        
        # Обновим время последнего сообщения в конверсации
        conversation = await db.get(ChatConversation, conversation_id)
        if conversation:
            conversation.last_message_at = utcnow()
            sender_role_str = sender_role.value if hasattr(sender_role, 'value') else str(sender_role)
            if sender_role_str == ChatMessageRole.USER.value:
                # Пользователь написал — ждёт ответа поддержки
                conversation.status = ChatConversationStatus.WAITING_RESPONSE.value
            else:
                # Админ ответил
                conversation.status = ChatConversationStatus.ANSWERED.value
        
        await db.commit()
        await db.refresh(message)
        return message
    
    async def get_messages(
        self,
        db: AsyncSession,
        conversation_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ChatMessage]:
        """Получить сообщения конверсации."""
        query = select(ChatMessage).options(
            joinedload(ChatMessage.sender),
        )
        query = query.where(ChatMessage.conversation_id == conversation_id)
        query = query.order_by(ChatMessage.created_at.asc())
        query = query.offset(offset).limit(limit)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    async def mark_as_read(
        self,
        db: AsyncSession,
        conversation_id: int,
        reader_role: ChatMessageRole,
    ) -> int:
        """Отметить сообщения как прочитанные."""
        from sqlalchemy import update
        
        reader_role_str = reader_role.value if hasattr(reader_role, 'value') else str(reader_role)
        opposite_role = "admin" if reader_role_str == "user" else "user"
        
        stmt = (
            update(ChatMessage)
            .where(
                and_(
                    ChatMessage.conversation_id == conversation_id,
                    ChatMessage.sender_role == opposite_role,
                    ChatMessage.is_read == False,
                )
            )
            .values(is_read=True, read_at=utcnow())
        )
        
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount


# Глобальные экземпляры
chat_conversation_crud = ChatConversationCRUD()
chat_message_crud = ChatMessageCRUD()
