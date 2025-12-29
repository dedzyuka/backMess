# app/schemas/contact.py
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime

class ContactRequestCreate(BaseModel):
    to_user_id: uuid.UUID = Field(..., description="UUID пользователя, которому отправляем запрос")

class ContactRequestResponse(BaseModel):
    id: uuid.UUID
    from_user_id: uuid.UUID
    from_nickname: str
    to_user_id: uuid.UUID
    to_nickname: str
    status: str = Field(..., description="pending, accepted, declined")
    created_at: datetime
    responded_at: Optional[datetime] = None

class ContactRequestListResponse(BaseModel):
    requests: List[ContactRequestResponse]
    total_count: int

class ContactResponse(BaseModel):
    user_id: uuid.UUID
    nickname: str
    public_key: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class ContactListResponse(BaseModel):
    contacts: List[ContactResponse]
    total_count: int