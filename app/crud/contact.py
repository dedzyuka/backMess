# app/crud/contact.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from app.models.contact import ContactRequest, Contact
from app.models.user import User
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ContactCRUD:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_contact_request(self, from_user_id: uuid.UUID, to_user_id: uuid.UUID, request_id: uuid.UUID = None) -> ContactRequest:
        """Создать запрос на добавление в контакты"""
        try:
            logger.info(f"CRUD: Creating contact request from {from_user_id} to {to_user_id}")
            
            if request_id is None:
                request_id = uuid.uuid4()
            
            logger.info(f"CRUD: Using request_id: {request_id}")
            
            # Проверяем, что пользователи существуют
            from_user_query = select(User).where(User.user_id == from_user_id)
            to_user_query = select(User).where(User.user_id == to_user_id)
            
            from_user = (await self.db.execute(from_user_query)).scalar_one_or_none()
            to_user = (await self.db.execute(to_user_query)).scalar_one_or_none()
            
            if not from_user or not to_user:
                raise ValueError("One or both users not found")
            
            # Проверяем, что запрос не самому себе
            if from_user_id == to_user_id:
                raise ValueError("Cannot send contact request to yourself")
            
            # Проверяем, не существует ли уже запрос с таким ID
            existing_id_query = select(ContactRequest).where(
                ContactRequest.id == request_id
            )
            existing_id_request = (await self.db.execute(existing_id_query)).scalar_one_or_none()
            
            if existing_id_request:
                logger.warning(f"CRUD: Request with ID {request_id} already exists")
                return existing_id_request
            
            # Проверяем, не существует ли уже запрос между этими пользователями
            existing_request_query = select(ContactRequest).where(
                and_(
                    ContactRequest.from_user_id == from_user_id,
                    ContactRequest.to_user_id == to_user_id,
                    ContactRequest.status == "pending"
                )
            )
            existing_request = (await self.db.execute(existing_request_query)).scalar_one_or_none()
            
            if existing_request:
                logger.warning(f"CRUD: Request already exists between these users: {existing_request.id}")
                return existing_request
            
            # Проверяем, не являются ли уже контактами
            existing_contact_query = select(Contact).where(
                or_(
                    and_(
                        Contact.user_id == from_user_id,
                        Contact.contact_user_id == to_user_id
                    ),
                    and_(
                        Contact.user_id == to_user_id,
                        Contact.contact_user_id == from_user_id
                    )
                )
            )
            existing_contact = (await self.db.execute(existing_contact_query)).scalar_one_or_none()
            
            if existing_contact:
                raise ValueError("Users are already contacts")
            
            # Создаем запрос с указанным ID
            contact_request = ContactRequest(
                id=request_id,  # Используем переданный ID!
                from_user_id=from_user_id,
                to_user_id=to_user_id,
                status="pending"
            )
            
            self.db.add(contact_request)
            await self.db.commit()
            await self.db.refresh(contact_request)
            
            logger.info(f"CRUD: Contact request created with ID: {contact_request.id}")
            return contact_request
            
        except IntegrityError as e:
            await self.db.rollback()
            logger.error(f"CRUD: Integrity error creating contact request: {str(e)}")
            raise ValueError("Failed to create contact request")
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"CRUD: Database error creating contact request: {str(e)}")
            raise RuntimeError("Database error during contact request creation")
    
    async def get_pending_requests(self, user_id: uuid.UUID) -> list[ContactRequest]:
        """Получить входящие запросы на контакт"""
        try:
            query = select(ContactRequest).where(
                and_(
                    ContactRequest.to_user_id == user_id,
                    ContactRequest.status == "pending"
                )
            ).order_by(ContactRequest.created_at.desc())
            
            result = await self.db.execute(query)
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting pending requests: {str(e)}")
            raise
    
    async def respond_to_contact_request(
        self, 
        request_id: uuid.UUID, 
        responder_id: uuid.UUID, 
        status: str
    ) -> ContactRequest:
        """Ответить на запрос на контакт (принять/отклонить)"""
        try:
            logger.info(f"CRUD: Responding to request {request_id} with status {status}")
            
            if status not in ["accepted", "declined"]:
                raise ValueError("Status must be 'accepted' or 'declined'")
            
            # Используем правильное имя столбца: to_user_id
            query = select(ContactRequest).where(
                and_(
                    ContactRequest.id == request_id,
                    ContactRequest.to_user_id == responder_id,  # Только получатель может ответить
                    ContactRequest.status == "pending"
                )
            )
            
            result = await self.db.execute(query)
            contact_request = result.scalar_one_or_none()
            
            logger.info(f"CRUD: Found request: {contact_request}")
            
            if not contact_request:
                raise ValueError("Contact request not found or already processed")
            
            # Обновляем статус
            contact_request.status = status
            contact_request.updated_at = datetime.utcnow()
            contact_request.responded_at = datetime.utcnow()
            
            # Если приняли, создаем контакт для обоих пользователей
            if status == "accepted":
                logger.info(f"CRUD: Creating contacts between {contact_request.from_user_id} and {contact_request.to_user_id}")
                
                # Проверяем, не существует ли уже контакта
                existing_contact_query = select(Contact).where(
                    or_(
                        and_(
                            Contact.user_id == contact_request.from_user_id,
                            Contact.contact_user_id == contact_request.to_user_id
                        ),
                        and_(
                            Contact.user_id == contact_request.to_user_id,
                            Contact.contact_user_id == contact_request.from_user_id
                        )
                    )
                )
                existing_result = await self.db.execute(existing_contact_query)
                existing_contact = existing_result.scalar_one_or_none()
                
                if existing_contact:
                    logger.warning(f"CRUD: Contact already exists between these users")
                else:
                    # Контакт для инициатора
                    contact1 = Contact(
                        user_id=contact_request.from_user_id,
                        contact_user_id=contact_request.to_user_id
                    )
                    
                    # Контакт для получателя
                    contact2 = Contact(
                        user_id=contact_request.to_user_id,
                        contact_user_id=contact_request.from_user_id
                    )
                    
                    self.db.add_all([contact1, contact2])
                    logger.info(f"CRUD: Contacts created")
            
            await self.db.commit()
            await self.db.refresh(contact_request)
            
            logger.info(f"CRUD: Request {request_id} {status} by {responder_id}")
            return contact_request
            
        except IntegrityError as e:
            await self.db.rollback()
            logger.error(f"CRUD: Integrity error responding to contact request: {str(e)}")
            raise ValueError("Failed to respond to contact request - integrity error")
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"CRUD: Database error responding to contact request: {str(e)}")
            raise RuntimeError("Database error during contact request response")
    
    async def get_contacts(self, user_id: uuid.UUID) -> list[User]:
        """Получить список контактов пользователя"""
        try:
            query = select(User).join(
                Contact, Contact.contact_user_id == User.user_id
            ).where(
                Contact.user_id == user_id
            ).order_by(User.nickname)
            
            result = await self.db.execute(query)
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting contacts: {str(e)}")
            raise
    
    async def remove_contact(self, user_id: uuid.UUID, contact_user_id: uuid.UUID) -> bool:
        """Удалить контакт (для обоих пользователей)"""
        try:
            # Удаляем контакт в обе стороны
            delete_query1 = delete(Contact).where(
                and_(
                    Contact.user_id == user_id,
                    Contact.contact_user_id == contact_user_id
                )
            )
            
            delete_query2 = delete(Contact).where(
                and_(
                    Contact.user_id == contact_user_id,
                    Contact.contact_user_id == user_id
                )
            )
            
            await self.db.execute(delete_query1)
            await self.db.execute(delete_query2)
            await self.db.commit()
            
            logger.info(f"Contact removed between {user_id} and {contact_user_id}")
            return True
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error(f"Error removing contact: {str(e)}")
            raise