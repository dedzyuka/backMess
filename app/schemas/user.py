# app/schemas/user.py
from pydantic import BaseModel, Field
from typing import Optional
import uuid

class UserBase(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=255, description="Идентификатор устройства")
    nickname: str = Field(..., min_length=1, max_length=50, description="Отображаемое имя пользователя")
    public_key: str = Field(..., description="Публичный ключ в PEM формате")

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    public_key: str = Field(..., description="Публичный ключ в PEM формате")

class UserResponse(BaseModel):
    user_id: uuid.UUID
    device_id: str
    nickname: str
    public_key: str
    
    class Config:
        from_attributes = True

class UserPublicResponse(BaseModel):
    user_id: uuid.UUID
    nickname: str
    public_key: str
    
    class Config:
        from_attributes = True