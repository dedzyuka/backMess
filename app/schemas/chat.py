# app/schemas/chat.py
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
from datetime import datetime

class ChatBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Название чата")

class ChatCreate(ChatBase):
    creator_id: uuid.UUID = Field(..., description="UUID создателя чата")

class ChatResponse(ChatBase):
    chat_id: uuid.UUID
    creator_id: uuid.UUID
    created_at: datetime
    member_count: int = Field(..., description="Количество участников")
    
    class Config:
        from_attributes = True

class ChatInviteResponse(BaseModel):
    chat_id: uuid.UUID
    invite_key: str = Field(..., description="Ключ для приглашения в чат")
    created_at: datetime

class ChatJoinRequest(BaseModel):
    user_id: uuid.UUID = Field(..., description="UUID пользователя, который присоединяется")
    invite_key: str = Field(..., description="Ключ приглашения")

class ChatJoinResponse(BaseModel):
    chat_id: uuid.UUID
    user_id: uuid.UUID
    joined_at: datetime
    status: str = Field(..., description="Статус присоединения")

class ChatMemberResponse(BaseModel):
    user_id: uuid.UUID
    nickname: str
    joined_at: datetime

class ChatDetailResponse(ChatResponse):
    members: List[ChatMemberResponse] = Field(..., description="Список участников чата")

class ChatLeaveResponse(BaseModel):
    success: bool = Field(..., description="Успешность выхода из чата")
    message: str = Field(..., description="Сообщение о результате")
    chat_id: uuid.UUID

class ChatLeaveAllResponse(BaseModel):
    success: bool = Field(..., description="Успешность выхода из всех чатов")
    message: str = Field(..., description="Сообщение о результате")
    left_chats: int = Field(..., description="Количество покинутых чатов")

class ChatMemberDetailedResponse(BaseModel):
    user_id: uuid.UUID
    nickname: str
    public_key: str
    joined_at: datetime
    device_id: str = Field(..., description="Идентификатор устройства участника")

class ChatMembersResponse(BaseModel):
    chat_id: uuid.UUID
    members: List[ChatMemberDetailedResponse] = Field(..., description="Детальный список участников")
    total_members: int = Field(..., description="Общее количество участников")

class ChatInviteRequest(BaseModel):
    user_id: uuid.UUID = Field(..., description="UUID пользователя, которого приглашаем")