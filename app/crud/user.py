# app/crud/user.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from app.models.user import User
from app.schemas.user import UserCreate
import uuid
import logging

logger = logging.getLogger(__name__)

class UserCRUD:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user(self, user_id: uuid.UUID) -> User | None:
        """Получить пользователя по ID"""
        try:
            query = select(User).where(User.user_id == user_id)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Error getting user {user_id}: {str(e)}")
            raise
    
    async def get_user_by_device_id(self, device_id: str) -> User | None:
        """Получить пользователя по device_id"""
        try:
            query = select(User).where(User.device_id == device_id)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Error getting user by device_id {device_id}: {str(e)}")
            raise
    
    async def get_user_by_nickname(self, nickname: str) -> User | None:
        """Получить пользователя по никнейму"""
        try:
            query = select(User).where(User.nickname == nickname)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Error getting user by nickname {nickname}: {str(e)}")
            raise
    
    async def create_user(self, user_data: UserCreate) -> User:
        """Создать нового пользователя"""
        try:
            # Проверяем, существует ли пользователь с таким device_id
            existing_device = await self.get_user_by_device_id(user_data.device_id)
        
            # Проверяем, существует ли пользователь с таким nickname
            existing_nickname = await self.get_user_by_nickname(user_data.nickname)
        
            # Ситуация 1: Пользователь с таким device_id уже существует
            if existing_device:
                # Если этот пользователь пытается зарегистрироваться под своим же nickname
                if existing_nickname and existing_nickname.user_id == existing_device.user_id:
                    # Обновляем public_key если нужно
                    if existing_device.public_key != user_data.public_key:
                        existing_device.public_key = user_data.public_key
                        await self.db.commit()
                        await self.db.refresh(existing_device)
                        logger.info(f"User {existing_device.nickname} updated public key")
                    return existing_device
                # Если device_id существует, но с другим nickname
                else:
                    raise ValueError(f"Device {user_data.device_id} is already registered with another nickname")
        
            # Ситуация 2: Пользователь с таким nickname существует, но device_id другой
            if existing_nickname:
                # nickname уже занят другим устройством
                raise ValueError(f"Nickname {user_data.nickname} is already taken by another device")
        
            # Ситуация 3: Создаем нового пользователя (оба параметра уникальны)
            user_id = uuid.uuid4()
            db_user = User(
                user_id=user_id,
                device_id=user_data.device_id,
                nickname=user_data.nickname,
                public_key=user_data.public_key
            )
        
            self.db.add(db_user)
            await self.db.commit()
            await self.db.refresh(db_user)
        
            logger.info(f"User {user_data.nickname} ({user_id}) created for device {user_data.device_id}")
            return db_user
        
        except IntegrityError as e:
            await self.db.rollback()
            logger.error(f"Integrity error creating user: {str(e)}")
            raise ValueError("User with this device_id or nickname already exists")
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Database error creating user: {str(e)}")
            raise RuntimeError("Database error during user creation")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Unexpected error creating user: {str(e)}")
            raise
    
    async def update_user_public_key(self, user_id: uuid.UUID, public_key: str) -> User | None:
        """Обновить публичный ключ пользователя"""
        try:
            user = await self.get_user(user_id)
            if not user:
                return None
            
            user.public_key = public_key
            await self.db.commit()
            await self.db.refresh(user)
            return user
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Error updating user {user_id}: {str(e)}")
            raise
    
    async def delete_user(self, user_id: uuid.UUID) -> bool:
        """Удалить пользователя"""
        try:
            user = await self.get_user(user_id)
            if not user:
                return False
            
            await self.db.delete(user)
            await self.db.commit()
            return True
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Error deleting user {user_id}: {str(e)}")
            raise

        
    async def search_users_by_nickname_partial(
    self, 
    partial_nickname: str, 
    exclude_user_id: uuid.UUID = None,
    limit: int = 15,
    offset: int = 0
) -> list[User]:
    
        try:
            query = select(User).where(
            User.nickname.ilike(f"%{partial_nickname}%")  # Частичное совпадение, регистронезависимо
        )
        
        # Исключаем текущего пользователя из результатов
            if exclude_user_id:
                query = query.where(User.user_id != exclude_user_id)
        
        # Сортируем по nickname и применяем лимит
            query = query.order_by(User.nickname).offset(offset).limit(limit)
        
            result = await self.db.execute(query)
            users = result.scalars().all()
        
            return users
        
        except SQLAlchemyError as e:
            logger.error(f"Error searching users by partial nickname {partial_nickname}: {str(e)}")
            raise