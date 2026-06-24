"""
WebSocket менеджер для чата поддержки.

Управляет подключениями пользователей и администраторов,
рассылает сообщения в реальном времени.
"""

from typing import Dict, List, Set, Optional
from uuid import UUID
import asyncio
from loguru import logger


class ConnectionManager:
    """
    Менеджер WebSocket подключений.
    
    Хранит активные подключения и предоставляет методы для рассылки.
    """
    
    def __init__(self):
        # Подключения пользователей: {user_id: websocket}
        self.user_connections: Dict[UUID, List] = {}
        
        # Подключения администраторов: {admin_id: [websocket, ...]}
        self.admin_connections: Dict[UUID, List] = {}
        
        # Подключения по конверсациям: {conversation_id: [websocket, ...]}
        # Для групповой рассылки по конкретному чату
        self.conversation_connections: Dict[int, List] = {}
        
        # Блокировка для потокобезопасности
        self._lock = asyncio.Lock()
    
    async def connect_user(
        self,
        websocket,
        user_id: UUID,
        conversation_id: Optional[int] = None,
    ):
        """Подключить пользователя."""
        async with self._lock:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(websocket)
            
            # Если подключился к конкретной конверсации
            if conversation_id:
                if conversation_id not in self.conversation_connections:
                    self.conversation_connections[conversation_id] = []
                self.conversation_connections[conversation_id].append(websocket)
            
            logger.info(f"🔌 Пользователь {user_id} подключился к WebSocket")
    
    async def connect_admin(
        self,
        websocket,
        admin_id: UUID,
        conversation_id: Optional[int] = None,
    ):
        """Подключить администратора."""
        async with self._lock:
            if admin_id not in self.admin_connections:
                self.admin_connections[admin_id] = []
            self.admin_connections[admin_id].append(websocket)
            
            # Если подключился к конкретной конверсации
            if conversation_id:
                if conversation_id not in self.conversation_connections:
                    self.conversation_connections[conversation_id] = []
                self.conversation_connections[conversation_id].append(websocket)
            
            logger.info(f"🔌 Администратор {admin_id} подключился к WebSocket")
    
    async def disconnect(
        self,
        websocket,
        user_id: Optional[UUID] = None,
        admin_id: Optional[UUID] = None,
        conversation_id: Optional[int] = None,
    ):
        """Отключить WebSocket."""
        async with self._lock:
            if user_id and user_id in self.user_connections:
                if websocket in self.user_connections[user_id]:
                    self.user_connections[user_id].remove(websocket)
                    if not self.user_connections[user_id]:
                        del self.user_connections[user_id]
            
            if admin_id and admin_id in self.admin_connections:
                if websocket in self.admin_connections[admin_id]:
                    self.admin_connections[admin_id].remove(websocket)
                    if not self.admin_connections[admin_id]:
                        del self.admin_connections[admin_id]
            
            if conversation_id and conversation_id in self.conversation_connections:
                if websocket in self.conversation_connections[conversation_id]:
                    self.conversation_connections[conversation_id].remove(websocket)
                    if not self.conversation_connections[conversation_id]:
                        del self.conversation_connections[conversation_id]
            
            logger.info(f"🔌 WebSocket отключён")
    
    async def send_personal_message(
        self,
        message: dict,
        user_id: UUID,
        exclude_sender: bool = False,
    ):
        """Отправить сообщение конкретному пользователю."""
        async with self._lock:
            if user_id in self.user_connections:
                for websocket in self.user_connections[user_id]:
                    try:
                        await websocket.send_json(message)
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось отправить сообщение пользователю {user_id}: {e}")
    
    async def send_to_admin(self, message: dict, admin_id: UUID):
        """Отправить сообщение конкретному администратору."""
        async with self._lock:
            if admin_id in self.admin_connections:
                for websocket in self.admin_connections[admin_id]:
                    try:
                        await websocket.send_json(message)
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось отправить сообщение админу {admin_id}: {e}")
    
    async def broadcast_to_conversation(
        self,
        message: dict,
        conversation_id: int,
        exclude_websocket: Optional = None,
    ):
        """Отправить сообщение всем подключенным к конверсации."""
        async with self._lock:
            if conversation_id in self.conversation_connections:
                for websocket in self.conversation_connections[conversation_id]:
                    if websocket == exclude_websocket:
                        continue
                    try:
                        await websocket.send_json(message)
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось отправить сообщение в чат {conversation_id}: {e}")
    
    async def broadcast_to_all_admins(self, message: dict):
        """Отправить сообщение всем администраторам."""
        async with self._lock:
            for admin_id, websockets in self.admin_connections.items():
                for websocket in websockets:
                    try:
                        await websocket.send_json(message)
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось отправить сообщение админу {admin_id}: {e}")
    
    async def send_typing_indicator(
        self,
        conversation_id: int,
        sender_id: UUID,
        is_admin: bool,
    ):
        """Отправить индикатор набора текста."""
        message = {
            "type": "typing",
            "conversation_id": conversation_id,
            "data": {
                "sender_id": str(sender_id),
                "is_admin": is_admin,
            },
        }
        await self.broadcast_to_conversation(message, conversation_id)
    
    def get_active_users_count(self) -> int:
        """Получить количество активных пользователей."""
        return len(self.user_connections)
    
    def get_active_admins_count(self) -> int:
        """Получить количество активных администраторов."""
        return len(self.admin_connections)
    
    async def get_stats(self) -> dict:
        """Получить статистику подключений."""
        return {
            "active_users": self.get_active_users_count(),
            "active_admins": self.get_active_admins_count(),
            "active_conversations": len(self.conversation_connections),
        }


# Глобальный менеджер подключений
ws_manager = ConnectionManager()
