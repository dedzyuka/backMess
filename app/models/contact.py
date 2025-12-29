from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
from datetime import datetime
from app.database import Base

class ContactRequest(Base):
    __tablename__ = "contact_requests"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    from_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.user_id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    to_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.user_id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), 
        nullable=False, 
        default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    from_user = relationship("User", foreign_keys=[from_user_id])
    to_user = relationship("User", foreign_keys=[to_user_id])
    
    __table_args__ = (
        UniqueConstraint('from_user_id', 'to_user_id', name='uq_contact_request_from_to'),
    )

class Contact(Base):
    __tablename__ = "contacts"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.user_id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    contact_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.user_id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        nullable=False
    )
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    contact_user = relationship("User", foreign_keys=[contact_user_id])
    
    __table_args__ = (
        UniqueConstraint('user_id', 'contact_user_id', name='uq_user_contact'),
    )