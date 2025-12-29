# app/websocket/manager.py
import asyncio
import json
from datetime import datetime
import uuid
from fastapi import WebSocket
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # active_connections: {user_id: {"websocket": WebSocket, "nickname": str}}
        self.active_connections: Dict[uuid.UUID, dict] = {}
        self.offline_messages: Dict[uuid.UUID, list] = {}  # Очередь офлайн сообщений
        
    async def connect(self, websocket: WebSocket, user_id: uuid.UUID, nickname: str):
        """Добавить новое соединение"""
        # Закрываем старое соединение, если есть
        if user_id in self.active_connections:
            try:
                old_connection = self.active_connections[user_id]["websocket"]
                await old_connection.close(code=1000, reason="New connection from same user")
            except:
                pass
        
        self.active_connections[user_id] = {
            "websocket": websocket,
            "nickname": nickname,
            "connected_at": datetime.now()
        }
        
        logger.info(f"✅ User connected: {nickname} ({user_id})")
        
        # Отправляем офлайн сообщения, если есть
        if user_id in self.offline_messages and self.offline_messages[user_id]:
            await self.send_offline_messages(user_id)
        
        # Уведомляем контакты об онлайн статусе
        await self.notify_contacts_online(user_id, True)
    
    async def disconnect(self, user_id: uuid.UUID):
        """Удалить соединение"""
        if user_id in self.active_connections:
            nickname = self.active_connections[user_id]["nickname"]
            del self.active_connections[user_id]
            
            logger.info(f"👋 User disconnected: {nickname} ({user_id})")
            
            # Уведомляем контакты об офлайн статусе
            await self.notify_contacts_online(user_id, False)
    
    async def send_personal_message(self, message: dict, user_id: uuid.UUID):
    
        logger.info(f"📤 [Manager] Sending to user_id: {user_id}")
        logger.info(f"   Message type: {message.get('type')}")
    
        if user_id in self.active_connections:
            connection_info = self.active_connections[user_id]
            logger.info(f"   User {connection_info['nickname']} is online")
        
            try:
                websocket = connection_info["websocket"]
                await websocket.send_json(message)
                logger.info(f"✅ Message delivered to {connection_info['nickname']}")
                return True
            except Exception as e:
                logger.error(f"❌ Error sending to {user_id}: {str(e)}")
                await self.disconnect(user_id)
                return False
        else:
            logger.warning(f"⚠️ User {user_id} is offline")
            await self.save_offline_message(message, user_id)
            return False
    
    
    async def broadcast(self, message: dict):
        """Отправить сообщение всем подключенным пользователям"""
        disconnected_users = []
        
        for user_id, connection_data in self.active_connections.items():
            try:
                websocket = connection_data["websocket"]
                await websocket.send_json(message)
            except:
                disconnected_users.append(user_id)
        
        # Удаляем отключенных пользователей
        for user_id in disconnected_users:
            await self.disconnect(user_id)
    
    async def send_to_chat(self, message: dict, chat_id: uuid.UUID, exclude_user_id: uuid.UUID = None):
        """Отправить сообщение всем участникам чата (через внешний вызов)"""
        # Этот метод будет вызываться из handle_chat_message
        # Там уже есть логика получения участников чата
        pass
    
    async def notify_contacts_online(self, user_id: uuid.UUID, is_online: bool):
        """Уведомить контакты пользователя об изменении статуса"""
        # TODO: Получить список контактов пользователя из БД
        # Пока просто логируем
        logger.info(f"User {user_id} is now {'online' if is_online else 'offline'}")
    
    async def save_offline_message(self, message: dict, user_id: uuid.UUID):
        """Сохранить сообщение для офлайн пользователя"""
        if user_id not in self.offline_messages:
            self.offline_messages[user_id] = []
        
        # Ограничиваем очередь (последние 100 сообщений)
        if len(self.offline_messages[user_id]) >= 100:
            self.offline_messages[user_id].pop(0)
        
        self.offline_messages[user_id].append({
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"Offline message saved for user {user_id}")
    
    async def send_offline_messages(self, user_id: uuid.UUID):
        """Отправить все офлайн сообщения пользователю"""
        if user_id not in self.offline_messages or not self.offline_messages[user_id]:
            return
        
        messages = self.offline_messages[user_id].copy()
        self.offline_messages[user_id] = []
        
        logger.info(f"Sending {len(messages)} offline messages to user {user_id}")
        
        for msg_data in messages:
            try:
                await self.send_personal_message(msg_data["message"], user_id)
                await asyncio.sleep(0.1)  # Небольшая задержка между сообщениями
            except Exception as e:
                logger.error(f"Error sending offline message: {str(e)}")
    
    def is_online(self, user_id: uuid.UUID) -> bool:
        """Проверить, онлайн ли пользователь"""
        return user_id in self.active_connections
    
    def get_online_users(self) -> list:
        """Получить список онлайн пользователей"""
        return [
            {
                "user_id": user_id,
                "nickname": data["nickname"],
                "connected_at": data["connected_at"]
            }
            for user_id, data in self.active_connections.items()
        ]

# Глобальный экземпляр менеджера
manager = ConnectionManager()