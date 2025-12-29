# app/crud/chat.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from app.models.chat import Chat, ChatMember
from app.models.user import User
from app.schemas.chat import ChatCreate, ChatJoinRequest, ChatJoinResponse, ChatInviteResponse, ChatResponse
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ChatCRUD:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_chat(self, chat_id: uuid.UUID) -> Chat | None:
        """Получить информацию о чате по ID"""
        try:
            query = select(Chat).where(Chat.chat_id == chat_id)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Error getting chat {chat_id}: {str(e)}")
            raise
    
    async def create_chat(self, chat_data: ChatCreate, device_id: str) -> ChatInviteResponse:
        """Создать новый чат и добавить создателя в участники"""
        try:
            # Проверяем существование пользователя-создателя
            user_query = select(User).where(User.user_id == chat_data.creator_id)
            user_result = await self.db.execute(user_query)
            creator = user_result.scalar_one_or_none()
            
            if not creator:
                raise ValueError(f"User with ID {chat_data.creator_id} not found")
            
            # Проверяем, что creator_id соответствует device_id
            if creator.device_id != device_id:
                raise ValueError("User device_id does not match")
            
            # Создаем чат
            chat_id = uuid.uuid4()
            db_chat = Chat(
                chat_id=chat_id,
                name=chat_data.name,
                creator_id=chat_data.creator_id
            )
            
            self.db.add(db_chat)
            
            # Добавляем создателя в участники чата с привязкой к устройству
            db_chat_member = ChatMember(
                chat_id=chat_id,
                user_id=chat_data.creator_id,
                device_id=device_id
            )
            self.db.add(db_chat_member)
            
            await self.db.commit()
            await self.db.refresh(db_chat)
            
            # Генерируем invite key
            invite_key = str(chat_id)
            
            logger.info(f"Chat {chat_data.name} ({chat_id}) created by user {chat_data.creator_id} on device {device_id}")
            
            return ChatInviteResponse(
                chat_id=chat_id,
                invite_key=invite_key,
                created_at=db_chat.created_at
            )
            
        except IntegrityError as e:
            await self.db.rollback()
            logger.error(f"Integrity error creating chat: {str(e)}")
            raise ValueError("Chat creation failed - integrity error")
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error creating chat: {str(e)}")
            raise RuntimeError("Database error during chat creation")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error creating chat: {str(e)}")
            raise
    
    async def create_chat(self, chat_data: ChatCreate, device_id: str) -> ChatInviteResponse:  # ДОБАВЛЕН device_id!
        """Создать новый чат и добавить создателя в участники"""
        try:
            # Проверяем существование пользователя-создателя
            user_query = select(User).where(User.user_id == chat_data.creator_id)
            user_result = await self.db.execute(user_query)
            creator = user_result.scalar_one_or_none()
            
            if not creator:
                raise ValueError(f"User with ID {chat_data.creator_id} not found")
            
            # Проверяем, что creator_id соответствует device_id
            if creator.device_id != device_id:
                raise ValueError("User device_id does not match")
            
            # Создаем чат
            chat_id = uuid.uuid4()
            db_chat = Chat(
                chat_id=chat_id,
                name=chat_data.name,
                creator_id=chat_data.creator_id
            )
            
            self.db.add(db_chat)
            
            # Добавляем создателя в участники чата с привязкой к устройству
            db_chat_member = ChatMember(
                chat_id=chat_id,
                user_id=chat_data.creator_id,
                device_id=device_id  # Сохраняем device_id участника
            )
            self.db.add(db_chat_member)
            
            await self.db.commit()
            await self.db.refresh(db_chat)
            
            # Генерируем invite key (пока просто chat_id, потом добавим шифрование)
            invite_key = str(chat_id)
            
            logger.info(f"Chat {chat_data.name} ({chat_id}) created by user {chat_data.creator_id} on device {device_id}")
            
            return ChatInviteResponse(
                chat_id=chat_id,
                invite_key=invite_key,
                created_at=db_chat.created_at
            )
            
        except IntegrityError as e:
            await self.db.rollback()
            logger.error(f"Integrity error creating chat: {str(e)}")
            raise ValueError("Chat creation failed - integrity error")
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error creating chat: {str(e)}")
            raise RuntimeError("Database error during chat creation")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error creating chat: {str(e)}")
            raise
    
    # В app/crud/chat.py, обновляем метод join_chat или добавляем новый метод:

    async def invite_user_to_chat(self, chat_id: uuid.UUID, user_id: uuid.UUID, 
                             inviter_device_id: str, invite_key: str = None) -> dict:
        try:
        # Проверяем существование чата
            chat_query = select(Chat).where(Chat.chat_id == chat_id)
            chat_result = await self.db.execute(chat_query)
            chat = chat_result.scalar_one_or_none()
        
            if not chat:
                raise ValueError(f"Chat with ID {chat_id} not found")
        
        # Проверяем существование пользователя
            user_query = select(User).where(User.user_id == user_id)
            user_result = await self.db.execute(user_query)
            user = user_result.scalar_one_or_none()
        
            if not user:
                raise ValueError(f"User with ID {user_id} not found")
        
        # Проверяем, не является ли пользователь уже участником на этом устройстве
            existing_member_query = select(ChatMember).where(
                and_(
                ChatMember.chat_id == chat_id, 
                ChatMember.user_id == user_id,
                ChatMember.device_id == user.device_id  # Проверяем именно это устройство
                )
            )
            existing_member_result = await self.db.execute(existing_member_query)
            existing_member = existing_member_result.scalar_one_or_none()
        
            if existing_member:
                raise ValueError(f"User {user_id} is already a member of chat {chat_id} on this device")
        
        # Добавляем пользователя в участники чата с привязкой к его устройству
            db_chat_member = ChatMember(
                chat_id=chat_id,
                user_id=user_id,
                device_id=user.device_id  # Используем device_id пользователя
            )
        
            self.db.add(db_chat_member)
            await self.db.commit()
            await self.db.refresh(db_chat_member)
        
            logger.info(f"User {user_id} invited to chat {chat_id} from device {inviter_device_id}")
        
            return {
            "chat_id": chat_id,
            "user_id": user_id,
            "joined_at": db_chat_member.joined_at,
            "status": "invited"
        }
        
        except ValueError as e:
            await self.db.rollback()
            raise
        except IntegrityError as e:
            await self.db.rollback()
            logger.error(f"Integrity error inviting user to chat: {str(e)}")
            raise ValueError("Chat invite failed - integrity error")
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error inviting user to chat: {str(e)}")
            raise RuntimeError("Database error during chat invite")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error inviting user to chat: {str(e)}")
            raise
    
    async def get_user_chats(self, user_id: uuid.UUID, device_id: str, skip: int = 0, limit: int = 100) -> list[Chat]:  # ДОБАВЛЕН device_id!
        """Получить список чатов пользователя ТОЛЬКО для этого устройства"""
        try:
            query = (
                select(Chat)
                .join(ChatMember, Chat.chat_id == ChatMember.chat_id)
                .where(
                    and_(
                        ChatMember.user_id == user_id,
                        ChatMember.device_id == device_id  # Только чаты на этом устройстве
                    )
                )
                .order_by(Chat.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await self.db.execute(query)
            chats = result.scalars().all()
            return chats
        except SQLAlchemyError as e:
            logger.error(f"Error getting user chats: {str(e)}")
            raise
    
    async def get_chat_members(self, chat_id: uuid.UUID, device_id: str = None) -> list[User]:  # ДОБАВЛЕН device_id!
        """Получить список участников чата (можно фильтровать по устройству)"""
        try:
            query = (
                select(User)
                .join(ChatMember, User.user_id == ChatMember.user_id)
                .where(ChatMember.chat_id == chat_id)
            )
            
            if device_id:
                query = query.where(ChatMember.device_id == device_id)
                
            result = await self.db.execute(query)
            members = result.scalars().all()
            return members
        except SQLAlchemyError as e:
            logger.error(f"Error getting chat members for chat {chat_id}: {str(e)}")
            raise
    
    async def is_user_chat_member(self, chat_id: uuid.UUID, user_id: uuid.UUID, device_id: str = None) -> bool:
        try:
            query = select(ChatMember).where(
                (ChatMember.chat_id == chat_id) & 
            (ChatMember.user_id == user_id)
            )
        
            if device_id:
                query = query.where(ChatMember.device_id == device_id)
            
            result = await self.db.execute(query)
            return result.scalar_one_or_none() is not None
        except SQLAlchemyError as e:
            logger.error(f"Error checking chat membership: {str(e)}")
            raise
        
    async def leave_chat(self, chat_id: uuid.UUID, user_id: uuid.UUID, device_id: str) -> bool:
        """Выйти из чата (удалить пользователя из участников на этом устройстве)"""
        try:
            # Находим запись участника чата для этого устройства
            query = select(ChatMember).where(
                and_(
                    ChatMember.chat_id == chat_id,
                    ChatMember.user_id == user_id,
                    ChatMember.device_id == device_id
                )
            )
            result = await self.db.execute(query)
            chat_member = result.scalar_one_or_none()
            
            if not chat_member:
                raise ValueError(f"User {user_id} is not a member of chat {chat_id} on this device")
            
            # Удаляем участника
            await self.db.delete(chat_member)
            await self.db.commit()
            
            logger.info(f"User {user_id} left chat {chat_id} from device {device_id}")
            return True
            
        except ValueError as e:
            await self.db.rollback()
            raise
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error leaving chat: {str(e)}")
            raise RuntimeError("Database error during chat leave")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error leaving chat: {str(e)}")
            raise

    async def leave_all_chats(self, user_id: uuid.UUID, device_id: str) -> dict:
        """Выйти из всех чатов (удалить пользователя из всех чатов на этом устройстве)"""
        try:
            # Находим все записи участника чата для этого устройства
            query = select(ChatMember).where(
                and_(
                    ChatMember.user_id == user_id,
                    ChatMember.device_id == device_id
                )
            )
            result = await self.db.execute(query)
            chat_members = result.scalars().all()
            
            if not chat_members:
                return {"left_chats": 0, "message": "User is not a member of any chats on this device"}
            
            # Удаляем все записи
            for chat_member in chat_members:
                await self.db.delete(chat_member)
            
            await self.db.commit()
            
            logger.info(f"User {user_id} left all {len(chat_members)} chats from device {device_id}")
            
            return {
                "left_chats": len(chat_members),
                "message": f"Successfully left {len(chat_members)} chats"
            }
            
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error leaving all chats: {str(e)}")
            raise RuntimeError("Database error during leaving all chats")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error leaving all chats: {str(e)}")
            raise

    async def get_chat_members_detailed(self, chat_id: uuid.UUID) -> list[dict]:
        """Получить детальную информацию об участниках чата"""
        try:
            logger.info(f"Getting detailed members for chat {chat_id}")
        
            query = (
            select(User, ChatMember.joined_at)
            .join(ChatMember, User.user_id == ChatMember.user_id)
            .where(ChatMember.chat_id == chat_id)
        )
        
            logger.info(f"Executing query: {query}")
            result = await self.db.execute(query)
            members_data = result.all()
        
            logger.info(f"Found {len(members_data)} members for chat {chat_id}")
        
            members = []
            for user, joined_at in members_data:
                logger.info(f"Processing user: {user.user_id}, joined_at: {joined_at}")
            
                members.append({
                "user_id": user.user_id,
                "nickname": user.nickname,
                "public_key": user.public_key,
                "joined_at": joined_at,
                "device_id": user.device_id  
            })
        
            logger.info(f"Successfully processed {len(members)} members")
            return members
        
        except Exception as e:
            logger.error(f"Error in get_chat_members_detailed for chat {chat_id}: {str(e)}")
            logger.error(f"Exception type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    