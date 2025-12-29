# app/models/user.py
from sqlalchemy import String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
import uuid
from datetime import datetime
from app.database import Base

class User(Base):
    __tablename__ = "users"
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    device_id: Mapped[str] = mapped_column(  # НОВОЕ ПОЛЕ!
        String(255), 
        nullable=False, 
        unique=True,
        index=True,
        default="Error"
    )
    nickname: Mapped[str] = mapped_column(
        String(50), 
        nullable=False, 
        index=True
    )
    public_key: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        nullable=False, 
        index=True
    )
    
    def __repr__(self):
        return f"<User {self.nickname} ({self.user_id})>"