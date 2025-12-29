# app/api/routes/user.py
from fastapi import APIRouter, Depends, HTTPException, Query, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import logging

from app.schemas.chat import ChatInviteRequest, ChatInviteResponse
from app.schemas.user import UserCreate, UserPublicResponse, UserResponse, UserUpdate
from app.crud.user import UserCRUD
from app.crud.chat import ChatCRUD
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

async def get_device_id(x_device_id: str = Header(..., description="Идентификатор устройства")):
    return x_device_id

@router.post(
    "/register", 
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового пользователя",
    response_description="Пользователь успешно зарегистрирован"
)
async def register_user(
    user_data: UserCreate,
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Регистрация анонимного пользователя в системе.
    
    - **nickname**: Отображаемое имя пользователя (1-50 символов)
    - **public_key**: Публичный ключ в PEM формате для шифрования
    - **device_id**: Идентификатор устройства (в теле запроса)
    
    User_id генерируется автоматически на сервере и возвращается в ответе.
    Требует заголовок X-Device-ID с идентификатором устройства.
    """
    try:
        # Проверяем, что device_id в заголовке совпадает с device_id в теле
        if user_data.device_id != device_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Device ID in header does not match device ID in body"
            )
            
        user_crud = UserCRUD(db)
        user = await user_crud.create_user(user_data)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during registration"
        )

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Получить текущего пользователя по device_id из заголовка",
    response_description="Информация о текущем пользователе"
)
async def get_current_user(
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить информацию о текущем пользователе на основе device_id из заголовка X-Device-ID.
    """
    user_crud = UserCRUD(db)
    user = await user_crud.get_user_by_device_id(device_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found for this device"
        )
    
    return user

@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Обновить публичный ключ текущего пользователя",
    response_description="Пользователь успешно обновлен"
)
async def update_current_user_public_key(
    user_update: UserUpdate,
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Обновить публичный ключ текущего пользователя.
    
    - **public_key**: Новый публичный ключ в PEM формате
    """
    user_crud = UserCRUD(db)
    
    # Сначала получаем пользователя
    user = await user_crud.get_user_by_device_id(device_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found for this device"
        )
    
    try:
        # Обновляем публичный ключ
        user.public_key = user_update.public_key
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"User {user.nickname} ({user.user_id}) updated public key for device {device_id}")
        return user
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating user public key: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating user"
        )

@router.get(
    "/search",
    response_model=list[UserPublicResponse],
    summary="Поиск пользователей по частичному совпадению nickname",
    response_description="Список пользователей, чей nickname содержит запрос"
)
async def search_users(
    query: str = Query(..., min_length=1, max_length=50, description="Часть никнейма для поиска"),
    limit: int = Query(15, ge=1, le=50, description="Лимит результатов (1-50)"),
    offset: int = Query(0, ge=0, description="Смещение для пагинации"),
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Поиск пользователей по частичному совпадению nickname.
    
    Возвращает список пользователей, чей nickname содержит запрошенную строку.
    
    - **query**: Часть никнейма для поиска (регистронезависимо)
    - **limit**: Максимальное количество результатов (по умолчанию 15, максимум 50)
    - **offset**: Смещение для пагинации
    
    Требует заголовок X-Device-ID с идентификатором устройства.
    """
    try:
        # Проверяем, что пользователь с таким device_id существует (авторизован)
        user_crud = UserCRUD(db)
        current_user = await user_crud.get_user_by_device_id(device_id)
        
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Device not registered or unauthorized"
            )
        
        # Ищем пользователей по частичному nickname
        users = await user_crud.search_users_by_nickname_partial(
            partial_nickname=query,
            exclude_user_id=current_user.user_id,
            limit=limit,
            offset=offset
        )
        
        # Преобразуем в UserPublicResponse
        result = []
        for user in users:
            result.append(UserPublicResponse(
                user_id=user.user_id,
                nickname=user.nickname,
                public_key=user.public_key
            ))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during user search"
        )

@router.get(
    "/by-device/{device_id}",
    response_model=UserResponse,
    summary="Получить пользователя по device_id",
    response_description="Информация о пользователе"
)
async def get_user_by_device_id(
    device_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить информацию о пользователе по идентификатору устройства.
    
    - **device_id**: Идентификатор устройства
    """
    user_crud = UserCRUD(db)
    user = await user_crud.get_user_by_device_id(device_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user

@router.get(
    "/by-nickname/{nickname}",
    response_model=UserResponse,
    summary="Получить пользователя по никнейму",
    response_description="Информация о пользователе"
)
async def get_user_by_nickname(
    nickname: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить информацию о пользователе по никнейму.
    
    - **nickname**: Отображаемое имя пользователя
    """
    user_crud = UserCRUD(db)
    user = await user_crud.get_user_by_nickname(nickname)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user

@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Получить пользователя по ID",
    response_description="Информация о пользователе"
)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить информацию о пользователе по его уникальному идентификатору.
    
    - **user_id**: UUID пользователя
    """
    user_crud = UserCRUD(db)
    user = await user_crud.get_user(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user

# Заменяем invite_user_to_chat на использование схем:

@router.post(
    "/{chat_id}/invite",
    response_model=ChatInviteResponse,
    status_code=status.HTTP_200_OK,
    summary="Пригласить пользователя в чат",
    response_description="Пользователь успешно приглашен в чат"
)
async def invite_user_to_chat(
    chat_id: uuid.UUID,
    invite_data: ChatInviteRequest,  # Теперь используем схему
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Пригласить пользователя в чат.
    
    - **user_id**: UUID пользователя, которого приглашаем
    
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
        invited_user = await user_crud.get_user(invite_data.user_id)
        if not invited_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invited user not found"
            )
        
        # 5. Проверяем, не является ли пользователь уже участником
        if await chat_crud.is_user_chat_member(chat_id, invite_data.user_id, invited_user.device_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this chat"
            )
        
        # 6. Добавляем пользователя в чат
        result = await chat_crud.invite_user_to_chat(
            chat_id=chat_id,
            user_id=invite_data.user_id,
            inviter_device_id=device_id
        )
        
        logger.info(f"User {invited_user.nickname} ({invite_data.user_id}) invited to chat {chat_id} by {inviting_user.nickname}")
        
        return ChatInviteResponse(
            success=True,
            message=f"User {invited_user.nickname} successfully invited to chat",
            chat_id=chat_id,
            invited_user_id=invite_data.user_id,
            invited_user_nickname=invited_user.nickname
        )
        
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