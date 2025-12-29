# app/api/routes/contact.py
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import logging

from app.crud.contact import ContactCRUD
from app.crud.user import UserCRUD
from app.database import get_db
from app.schemas.contact import (
    ContactRequestCreate,
    ContactRequestResponse,
    ContactRequestListResponse,
    ContactResponse,
    ContactListResponse
)

logger = logging.getLogger(__name__)
router = APIRouter()

async def get_device_id(x_device_id: str = Header(..., description="Идентификатор устройства")):
    return x_device_id


@router.post(
    "/requests",
    response_model=ContactRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Отправить запрос на добавление в контакты",
    response_description="Запрос на контакт создан"
)
async def create_contact_request(
    request_data: ContactRequestCreate,
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Отправить запрос на добавление в контакты.
    
    - **to_user_id**: UUID пользователя, которому отправляем запрос
    
    Требует заголовок X-Device-ID с идентификатором устройства отправителя.
    """
    try:
        user_crud = UserCRUD(db)
        contact_crud = ContactCRUD(db)
        
        # Получаем отправителя по device_id
        from_user = await user_crud.get_user_by_device_id(device_id)
        if not from_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found for this device"
            )
        
        # Создаем запрос
        contact_request = await contact_crud.create_contact_request(
            from_user_id=from_user.user_id,
            to_user_id=request_data.to_user_id
        )
        
        # Получаем информацию о получателе
        to_user = await user_crud.get_user(request_data.to_user_id)
        
        return ContactRequestResponse(
            id=contact_request.id,
            from_user_id=contact_request.from_user_id,
            from_nickname=from_user.nickname,
            to_user_id=contact_request.to_user_id,
            to_nickname=to_user.nickname if to_user else "Unknown",
            status=contact_request.status,
            created_at=contact_request.created_at
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating contact request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get(
    "/requests/pending",
    response_model=ContactRequestListResponse,
    summary="Получить входящие запросы на контакт",
    response_description="Список входящих запросов"
)
async def get_pending_contact_requests(
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db)
):
    """Получить список входящих запросов на добавление в контакты"""
    try:
        user_crud = UserCRUD(db)
        contact_crud = ContactCRUD(db)
        
        # Получаем текущего пользователя
        current_user = await user_crud.get_user_by_device_id(device_id)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found for this device"
            )
        
        # Получаем входящие запросы
        requests = await contact_crud.get_pending_requests(current_user.user_id)
        
        # Формируем ответ
        request_responses = []
        for req in requests:
            from_user = await user_crud.get_user(req.from_user_id)
            request_responses.append(
                ContactRequestResponse(
                    id=req.id,
                    from_user_id=req.from_user_id,
                    from_nickname=from_user.nickname if from_user else "Unknown",
                    to_user_id=req.to_user_id,
                    to_nickname=current_user.nickname,
                    status=req.status,
                    created_at=req.created_at
                )
            )
        
        return ContactRequestListResponse(
            requests=request_responses,
            total_count=len(request_responses)
        )
        
    except Exception as e:
        logger.error(f"Error getting pending requests: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# app/api/routes/contact.py
@router.post(
    "/requests/{request_id}/respond",
    response_model=ContactRequestResponse,
    summary="Ответить на запрос на контакт",
    response_description="Запрос обработан"
)
async def respond_to_contact_request(
    request_id: uuid.UUID,
    response_data: dict,  # {"status": "accepted" или "declined"}
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Принять или отклонить запрос на добавление в контакты.
    
    Тело запроса:
    {
        "status": "accepted" или "declined"
    }
    """
    try:
        logger.info(f"📥 POST /contacts/requests/{request_id}/respond")
        logger.info(f"📥 Device ID: {device_id[:8]}...")
        logger.info(f"📥 Request body: {response_data}")
        logger.info(f"📥 Request ID: {request_id}")
        
        user_crud = UserCRUD(db)
        contact_crud = ContactCRUD(db)
        
        # Получаем текущего пользователя
        current_user = await user_crud.get_user_by_device_id(device_id)
        if not current_user:
            logger.warning(f"❌ User not found for device_id: {device_id[:8]}...")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found for this device"
            )
        
        logger.info(f"✅ Current user: {current_user.nickname} ({current_user.user_id})")
        
        status_value = response_data.get("status")
        if status_value not in ["accepted", "declined"]:
            logger.error(f"❌ Invalid status: {status_value}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Status must be 'accepted' or 'declined'"
            )
        
        logger.info(f"✅ Processing request {request_id} with status: {status_value}")
        
        # Обрабатываем запрос
        contact_request = await contact_crud.respond_to_contact_request(
            request_id=request_id,
            responder_id=current_user.user_id,
            status=status_value
        )
        
        logger.info(f"✅ Request processed: {contact_request.status}")
        
        # Получаем информацию о пользователях
        from_user = await user_crud.get_user(contact_request.from_user_id)
        to_user = await user_crud.get_user(contact_request.to_user_id)
        
        response = ContactRequestResponse(
            id=contact_request.id,
            from_user_id=contact_request.from_user_id,
            from_nickname=from_user.nickname if from_user else "Unknown",
            to_user_id=contact_request.to_user_id,
            to_nickname=to_user.nickname if to_user else "Unknown",
            status=contact_request.status,
            created_at=contact_request.created_at,
            responded_at=contact_request.responded_at
        )
        
        logger.info(f"✅ Response prepared: {response}")
        return response
        
    except ValueError as e:
        logger.error(f"❌ ValueError in respond_to_contact_request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Error responding to contact request: {str(e)}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.get(
    "/",
    response_model=ContactListResponse,
    summary="Получить список контактов",
    response_description="Список контактов пользователя"
)
async def get_contacts(
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db)
):
    """Получить список контактов текущего пользователя"""
    try:
        user_crud = UserCRUD(db)
        contact_crud = ContactCRUD(db)
        
        # Получаем текущего пользователя
        current_user = await user_crud.get_user_by_device_id(device_id)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found for this device"
            )
        
        # Получаем контакты
        contacts = await contact_crud.get_contacts(current_user.user_id)
        
        # Формируем ответ
        contact_responses = []
        for contact_user in contacts:
            contact_responses.append(
                ContactResponse(
                    user_id=contact_user.user_id,
                    nickname=contact_user.nickname,
                    public_key=contact_user.public_key,
                    created_at=contact_user.created_at
                )
            )
        
        return ContactListResponse(
            contacts=contact_responses,
            total_count=len(contact_responses)
        )
        
    except Exception as e:
        logger.error(f"Error getting contacts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.delete(
    "/{contact_user_id}",
    status_code=status.HTTP_200_OK,
    summary="Удалить контакт",
    response_description="Контакт удален"
)
async def remove_contact(
    contact_user_id: uuid.UUID,
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Удалить пользователя из контактов.
    
    - **contact_user_id**: UUID пользователя, которого удаляем из контактов
    """
    try:
        user_crud = UserCRUD(db)
        contact_crud = ContactCRUD(db)
        
        # Получаем текущего пользователя
        current_user = await user_crud.get_user_by_device_id(device_id)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found for this device"
            )
        
        # Удаляем контакт
        success = await contact_crud.remove_contact(
            user_id=current_user.user_id,
            contact_user_id=contact_user_id
        )
        
        if success:
            return {"success": True, "message": "Contact removed"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to remove contact"
            )
        
    except Exception as e:
        logger.error(f"Error removing contact: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )