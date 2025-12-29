# app/api/routes/chats.py
from datetime import datetime
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.crud.user import UserCRUD
from app.schemas.chat import (
    ChatCreate,
    ChatLeaveAllResponse,
    ChatLeaveResponse,
    ChatMemberDetailedResponse,
    ChatMembersResponse, 
    ChatResponse, 
    ChatInviteResponse,
    ChatJoinRequest,
    ChatJoinResponse,
    ChatDetailResponse,
    ChatMemberResponse
)
from app.crud.chat import ChatCRUD
from app.database import get_db
# Правильный логгер
logger = logging.getLogger(__name__)

router = APIRouter()

async def get_device_id(x_device_id: str = Header(..., description="Идентификатор устройства")):  # НОВАЯ DEPENDENCY!
    return x_device_id

@router.post(
    "/",
    response_model=ChatInviteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый чат",
    response_description="Чат создан и возвращен invite key"
)
async def create_chat(
    chat_data: ChatCreate,
    device_id: str = Depends(get_device_id),  # ДОБАВЛЕН device_id!
    db: AsyncSession = Depends(get_db)
):
    """
    Создание нового чата.
    
    - **name**: Название чата
    - **creator_id**: UUID создателя чата
    
    Требует заголовок X-Device-ID с идентификатором устройства.
    """
    try:
        chat_crud = ChatCRUD(db)
        chat_invite = await chat_crud.create_chat(chat_data, device_id)  # ПЕРЕДАЕМ device_id!
        return chat_invite
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during chat creation"
        )

@router.post(
    "/{chat_id}/join",
    response_model=ChatJoinResponse,
    summary="Присоединиться к чату по invite key",
    response_description="Успешное присоединение к чату"
)
async def join_chat(
    chat_id: uuid.UUID,
    join_data: ChatJoinRequest,
    device_id: str = Depends(get_device_id),  # ДОБАВЛЕН device_id!
    db: AsyncSession = Depends(get_db)
):
    """
    Присоединение к существующему чату.
    
    - **user_id**: UUID пользователя, который присоединяется
    - **invite_key**: Ключ приглашения
    
    Требует заголовок X-Device-ID с идентификатором устройства.
    """
    try:
        chat_crud = ChatCRUD(db)
        result = await chat_crud.join_chat(chat_id, join_data, device_id)  # ПЕРЕДАЕМ device_id!
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during chat join"
        )

@router.get(
    "/",
    response_model=list[ChatResponse],
    summary="Получить список чатов пользователя",
    response_description="Список чатов, где пользователь является участником НА ЭТОМ УСТРОЙСТВЕ"
)
async def get_user_chats(
    user_id: uuid.UUID,
    device_id: str = Depends(get_device_id),  # ДОБАВЛЕН device_id!
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Получить все чаты, в которых участвует пользователь НА ЭТОМ УСТРОЙСТВЕ"""
    try:
        chat_crud = ChatCRUD(db)
        chats = await chat_crud.get_user_chats(user_id, device_id, skip=skip, limit=limit)  # ПЕРЕДАЕМ device_id!
        
        # Преобразуем в ChatResponse с подсчетом участников
        chat_responses = []
        for chat in chats:
            members = await chat_crud.get_chat_members(chat.chat_id)
            chat_response = ChatResponse(
                chat_id=chat.chat_id,
                name=chat.name,
                creator_id=chat.creator_id,
                created_at=chat.created_at,
                member_count=len(members)
            )
            chat_responses.append(chat_response)
        
        return chat_responses
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user chats"
        )

@router.delete(
    "/{chat_id}/leave",
    response_model=ChatLeaveResponse,
    summary="Выйти из чата",
    response_description="Успешный выход из чата"
)
async def leave_chat(
    chat_id: uuid.UUID,
    user_id: uuid.UUID,  # Будем передавать как query параметр
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Выйти из чата.
    
    - **chat_id**: UUID чата
    - **user_id**: UUID пользователя (query параметр)
    
    Удаляет пользователя из участников чата на этом устройстве.
    """
    try:
        chat_crud = ChatCRUD(db)
        success = await chat_crud.leave_chat(chat_id, user_id, device_id)
        
        return ChatLeaveResponse(
            success=True,
            message="Successfully left the chat",
            chat_id=chat_id
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during chat leave"
        )

@router.delete(
    "/leave_all",
    response_model=ChatLeaveAllResponse,
    summary="Выйти из всех чатов",
    response_description="Успешный выход из всех чатов"
)
async def leave_all_chats(
    user_id: uuid.UUID,  # Query параметр
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Выйти из всех чатов.
    
    - **user_id**: UUID пользователя (query параметр)
    
    Удаляет пользователя из всех чатов на этом устройстве.
    """
    try:
        chat_crud = ChatCRUD(db)
        result = await chat_crud.leave_all_chats(user_id, device_id)
        
        return ChatLeaveAllResponse(
            success=True,
            message=result["message"],
            left_chats=result["left_chats"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during leaving all chats"
        )

@router.get(
    "/{chat_id}/members/detailed",
    response_model=ChatMembersResponse,  # ИСПРАВЛЕНО: ChatMembersResponse вместо ChatMemberDetailedResponse
    summary="Получить детальный список участников чата",
    response_description="Детальная информация об участниках чата"
)
async def get_chat_members_detailed(
    chat_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Получить детальную информацию обо всех участниках чата"""
    try:
        logger.info(f"API call: get_chat_members_detailed for chat {chat_id}")
        
        chat_crud = ChatCRUD(db)
        
        # Проверяем существование чата
        chat = await chat_crud.get_chat(chat_id)
        if not chat:
            logger.warning(f"Chat {chat_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )
        
        # Получаем детальную информацию об участниках
        members_data = await chat_crud.get_chat_members_detailed(chat_id)
        logger.info(f"Retrieved {len(members_data)} members from database")
        
        # Преобразуем в response модель
        members_response = []
        for member in members_data:
            try:
                # Проверяем, что joined_at является datetime
                joined_at = member["joined_at"]
                if not isinstance(joined_at, datetime):
                    logger.warning(f"Invalid joined_at type for user {member['user_id']}: {type(joined_at)}")
                    joined_at = datetime.utcnow()
                
                member_response = ChatMemberDetailedResponse(
                    user_id=member["user_id"],
                    nickname=member["nickname"],
                    public_key=member["public_key"],
                    joined_at=joined_at,
                    device_id=member["device_id"]
                )
                members_response.append(member_response)
                
            except Exception as e:
                logger.error(f"Error processing member {member.get('user_id', 'unknown')}: {str(e)}")
                continue  # Пропускаем проблемного пользователя
        
        logger.info(f"Successfully created response for {len(members_response)} members")
        
        return ChatMembersResponse(
            chat_id=chat_id,
            members=members_response,
            total_members=len(members_response)
        )
        
    except HTTPException:
        logger.info("HTTPException raised, re-raising")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_chat_members_detailed endpoint: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

# Дополняем существующий эндпоинт get_chat_members
@router.get(
    "/{chat_id}/members",
    response_model=list[ChatMemberResponse],
    summary="Получить участников чата (базовый список)",
    response_description="Базовый список участников чата"
)
async def get_chat_members(
    chat_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Получить базовый список всех участников чата"""
    try:
        chat_crud = ChatCRUD(db)
        members = await chat_crud.get_chat_members(chat_id)
        
        # Преобразуем в ChatMemberResponse
        members_response = []
        for member in members:
            # TODO: Получить реальное время присоединения из ChatMember
            member_response = ChatMemberResponse(
                user_id=member.user_id,
                nickname=member.nickname,
                joined_at=datetime.now()
            )
            members_response.append(member_response)
        
        return members_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving chat members"
        )

@router.post(
    "/{chat_id}/invite",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Пригласить пользователя в чат",
    response_description="Пользователь успешно приглашен в чат"
)
async def invite_user_to_chat(
    chat_id: uuid.UUID,
    invite_data: dict,
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Пригласить пользователя в чат.
    
    - **user_id**: UUID пользователя, которого приглашаем
    - **chat_id**: UUID чата (в URL)
    
    Тело запроса:
    {
        "user_id": "uuid-пользователя"
    }
    
    Требует заголовок X-Device-ID с идентификатором устройства приглашающего.
    """
    try:
        chat_crud = ChatCRUD(db)
        user_crud = UserCRUD(db)
        
        # 1. Проверяем существование чата
        chat = await chat_crud.get_chat(chat_id)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found"
            )
        
        # 2. Получаем приглашающего пользователя по device_id
        inviting_user = await user_crud.get_user_by_device_id(device_id)
        if not inviting_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inviting user not found"
            )
        
        # 3. Проверяем, что приглашающий является участником чата
        if not await chat_crud.is_user_chat_member(chat_id, inviting_user.user_id, device_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this chat"
            )
        
        # 4. Получаем приглашаемого пользователя
        user_id_str = invite_data.get("user_id")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_id is required in request body"
            )
        
        try:
            invited_user_id = uuid.UUID(user_id_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user_id format"
            )
        
        invited_user = await user_crud.get_user(invited_user_id)
        if not invited_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invited user not found"
            )
        
        # 5. Проверяем, не является ли пользователь уже участником на этом устройстве
        if await chat_crud.is_user_chat_member(chat_id, invited_user_id, invited_user.device_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this chat on this device"
            )
        
        # 6. Добавляем пользователя в чат через invite_user_to_chat
        result = await chat_crud.invite_user_to_chat(
            chat_id=chat_id,
            user_id=invited_user_id,
            inviter_device_id=device_id
        )
        
        logger.info(f"User {invited_user.nickname} ({invited_user_id}) invited to chat {chat_id} by {inviting_user.nickname}")
        
        return {
            "success": True,
            "message": f"User {invited_user.nickname} successfully invited to chat",
            "chat_id": chat_id,
            "invited_user_id": invited_user_id,
            "invited_user_nickname": invited_user.nickname
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inviting user to chat: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )