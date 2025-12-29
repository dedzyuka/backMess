# app/api/routes/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import json
import logging
from datetime import datetime

from app.crud.contact import ContactCRUD
from app.websocket.manager import ConnectionManager
from app.database import get_db
from app.crud.user import UserCRUD
from app.crud.chat import ChatCRUD

logger = logging.getLogger(__name__)
router = APIRouter()
manager = ConnectionManager()

# Простая проверка пользователя
async def get_current_user(device_id: str, user_id: uuid.UUID, db: AsyncSession):
    """Проверяем, что пользователь существует и device_id совпадает"""
    user_crud = UserCRUD(db)
    user = await user_crud.get_user(user_id)
    
    if not user:
        logger.warning(f"User {user_id} not found")
        return None
    
    if user.device_id != device_id:
        logger.warning(f"Device ID mismatch for user {user_id}")
        return None
    
    return user

@router.websocket("/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: uuid.UUID,
    x_device_id: str = None  # Будем получать из query параметров
):
    """
    WebSocket endpoint для обмена сообщениями
    Параметры:
    - user_id: UUID пользователя
    - x_device_id: device_id из query параметра (?device_id=...)
    """
    
    # Получаем device_id из query параметров
    query_params = dict(websocket.query_params)
    device_id = query_params.get("device_id") or x_device_id
    
    if not device_id:
        logger.error(f"No device_id provided for user {user_id}")
        await websocket.close(code=4003, reason="Device ID required")
        return
    
    logger.info(f"WebSocket connection attempt: user={user_id}, device={device_id[:8]}...")
    
    # Подключаемся к WebSocket
    await websocket.accept()
    
    # Проверяем пользователя
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        user = await get_current_user(device_id, user_id, db)
        
        if not user:
            logger.warning(f"Authentication failed for user {user_id}")
            await websocket.close(code=4001, reason="Authentication failed")
            return
    
    logger.info(f"✅ WebSocket connected: {user.nickname} ({user_id})")
    
    # Регистрируем соединение
    await manager.connect(websocket, user_id, user.nickname)
    
    try:
        while True:
            # Получаем сообщение
            try:
                data = await websocket.receive_json()
            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
                continue
                
            message_type = data.get("type")
            
            # Обрабатываем разные типы сообщений
            if message_type == "chat_message":
                await handle_chat_message(data, user_id, db)
                
            elif message_type == "contact_request":
                await handle_contact_request(data, user_id, db)
                
            elif message_type == "contact_accept":
                await handle_contact_accept(data, user_id, db)
                
            elif message_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})
                
            elif message_type == "message_ack":
                await handle_message_ack(data, user_id, db)
                
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {user.nickname} ({user_id})")
        await manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {str(e)}")
        await manager.disconnect(user_id)

async def handle_chat_message(data: dict, sender_id: uuid.UUID, db: AsyncSession):
    """Обработать сообщение чата"""
    try:
        chat_id = uuid.UUID(data.get("chat_id"))
        content = data.get("content")
        message_id = data.get("message_id") or str(uuid.uuid4())
        timestamp = data.get("timestamp") or datetime.now().isoformat()
        
        # Проверяем, что отправитель - участник чата
        chat_crud = ChatCRUD(db)
        is_member = await chat_crud.is_user_chat_member(chat_id, sender_id)
        
        if not is_member:
            logger.warning(f"User {sender_id} is not a member of chat {chat_id}")
            return
        
        # Получаем участников чата
        members = await chat_crud.get_chat_members(chat_id)
        
        # Формируем сообщение для пересылки
        message_to_forward = {
            "type": "chat_message",
            "message_id": message_id,
            "chat_id": str(chat_id),
            "sender_id": str(sender_id),
            "content": content,
            "timestamp": timestamp,
            "encrypted": data.get("encrypted", True)
        }
        
        # Отправляем всем участникам кроме отправителя
        for member in members:
            if member.user_id != sender_id:
                await manager.send_personal_message(message_to_forward, member.user_id)
        
        logger.info(f"Message forwarded in chat {chat_id} from {sender_id}")
        
    except Exception as e:
        logger.error(f"Error handling chat message: {str(e)}")

# app/api/routes/websocket.py
async def handle_contact_request(data: dict, sender_id: uuid.UUID, db: AsyncSession):
    """Обработать запрос на контакт"""
    try:
        # 1. Получаем recipient_id из сообщения
        recipient_id_str = data.get("recipient_id") or data.get("recipientId")
        
        if not recipient_id_str:
            logger.warning(f"No recipient_id in data: {data}")
            return
            
        recipient_id = uuid.UUID(recipient_id_str)
        
        # 2. КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем, что отправитель не отправляет запрос самому себе
        if sender_id == recipient_id:
            logger.warning(f"User {sender_id} tried to send contact request to themselves")
            # Отправляем ошибку отправителю
            error_msg = {
                "type": "contact_request_error",
                "error": "Cannot send contact request to yourself",
                "timestamp": datetime.now().isoformat()
            }
            await manager.send_personal_message(error_msg, sender_id)
            return
        
        # 3. Проверяем существование получателя
        user_crud = UserCRUD(db)
        recipient = await user_crud.get_user(recipient_id)
        
        if not recipient:
            logger.warning(f"Recipient {recipient_id} not found")
            # Отправляем ошибку отправителю
            error_msg = {
                "type": "contact_request_error",
                "error": "Recipient not found",
                "timestamp": datetime.now().isoformat()
            }
            await manager.send_personal_message(error_msg, sender_id)
            return
        
        # 4. Получаем информацию об отправителе
        sender = await user_crud.get_user(sender_id)
        if not sender:
            logger.warning(f"Sender {sender_id} not found")
            return
        
        # 5. Проверяем, не являются ли уже контактами
        contact_crud = ContactCRUD(db)
        try:
            existing_contact = await contact_crud.get_contacts(sender_id)
            for contact in existing_contact:
                if contact.user_id == recipient_id:
                    logger.warning(f"Users {sender_id} and {recipient_id} are already contacts")
                    error_msg = {
                        "type": "contact_request_error",
                        "error": "Users are already contacts",
                        "timestamp": datetime.now().isoformat()
                    }
                    await manager.send_personal_message(error_msg, sender_id)
                    return
        except:
            pass
        
        # 6. Создаем запрос в БД
        request_id = uuid.uuid4()
        try:
            contact_request = await contact_crud.create_contact_request(
                from_user_id=sender_id,
                to_user_id=recipient_id
            )
            request_id = contact_request.id
        except ValueError as e:
            logger.error(f"Failed to create contact request: {str(e)}")
            error_msg = {
                "type": "contact_request_error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            await manager.send_personal_message(error_msg, sender_id)
            return
        
        # 7. Формируем запрос на контакт
        contact_request_msg = {
            "type": "contact_request",
            "request_id": str(request_id),
            "sender_id": str(sender_id),
            "sender_nickname": sender.nickname,
            "sender_public_key": sender.public_key,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"📤 Contact request: {sender.nickname} → {recipient.nickname}")
        
        # 8. Отправляем ТОЛЬКО получателю
        await manager.send_personal_message(contact_request_msg, recipient_id)
        
        # 9. Отправляем подтверждение отправителю (но не запрос!)
        await manager.send_personal_message({
            "type": "contact_request_sent",
            "recipient_id": str(recipient_id),
            "recipient_nickname": recipient.nickname,
            "request_id": str(request_id),
            "timestamp": datetime.now().isoformat()
        }, sender_id)
        
        logger.info(f"✅ Contact request sent successfully")
        
    except Exception as e:
        logger.error(f"Error handling contact request: {str(e)}")

async def handle_contact_accept(data: dict, sender_id: uuid.UUID, db: AsyncSession):
    """Обработать подтверждение контакта"""
    try:
        original_sender_id = uuid.UUID(data.get("original_sender_id"))
        
        # Получаем информацию о пользователях
        user_crud = UserCRUD(db)
        sender = await user_crud.get_user(sender_id)
        original_sender = await user_crud.get_user(original_sender_id)
        
        if not sender or not original_sender:
            logger.warning(f"Users not found: sender={sender_id}, original={original_sender_id}")
            return
        
        # Формируем подтверждение
        contact_accept = {
            "type": "contact_accept",
            "accepted_user_id": str(sender_id),
            "accepted_nickname": sender.nickname,
            "accepted_public_key": sender.public_key,
            "timestamp": datetime.now().isoformat()
        }
        
        # Отправляем оригинальному отправителю
        await manager.send_personal_message(contact_accept, original_sender_id)
        
        logger.info(f"Contact accepted: {sender.nickname} accepted request from {original_sender.nickname}")
        
    except Exception as e:
        logger.error(f"Error handling contact accept: {str(e)}")

async def handle_message_ack(data: dict, ack_sender_id: uuid.UUID, db: AsyncSession):
    """Обработать подтверждение получения сообщения"""
    try:
        message_id = data.get("message_id")
        original_sender_id = uuid.UUID(data.get("original_sender_id"))
        
        ack_message = {
            "type": "message_ack",
            "message_id": message_id,
            "ack_sender_id": str(ack_sender_id),
            "timestamp": datetime.now().isoformat()
        }
        
        # Отправляем подтверждение оригинальному отправителю
        await manager.send_personal_message(ack_message, original_sender_id)
        
        logger.info(f"Message {message_id} acknowledged by {ack_sender_id}")
        
    except Exception as e:
        logger.error(f"Error handling message ack: {str(e)}")



