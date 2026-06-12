"""
SQLAlchemy models and Pydantic schemas for user management.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from ..database import Base
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any


# ═══════ SQLAlchemy Models ═══════

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supabase_uid = Column(Text, unique=True, nullable=False)
    email = Column(Text, unique=True)
    display_name = Column(Text)
    avatar_url = Column(Text)
    preferences = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    saved_itineraries = relationship("SavedItinerary", back_populates="user", cascade="all, delete-orphan")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(Text, nullable=False)
    title = Column(Text, default="New Chat")
    messages = Column(JSONB, default=[])
    destination = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="chat_sessions")


class SavedItinerary(Base):
    __tablename__ = "saved_itineraries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(Text, nullable=False)
    destination = Column(Text, nullable=False)
    itinerary_data = Column(JSONB, nullable=False)
    total_days = Column(Integer)
    pacing = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="saved_itineraries")


# ═══════ Pydantic Schemas ═══════

class UserResponse(BaseModel):
    id: uuid.UUID
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    preferences: Optional[dict] = {}
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    preferences: Optional[dict] = None


class ChatSessionListItem(BaseModel):
    id: uuid.UUID
    session_id: str
    title: Optional[str] = "New Chat"
    destination: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ChatSessionResponse(BaseModel):
    id: uuid.UUID
    session_id: str
    title: Optional[str] = "New Chat"
    messages: List[Any] = []
    destination: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SaveItineraryRequest(BaseModel):
    title: str
    destination: str
    itinerary_data: dict
    total_days: Optional[int] = None
    pacing: Optional[str] = None


class SavedItineraryListItem(BaseModel):
    id: uuid.UUID
    title: str
    destination: str
    total_days: Optional[int] = None
    pacing: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SavedItineraryResponse(BaseModel):
    id: uuid.UUID
    title: str
    destination: str
    itinerary_data: dict
    total_days: Optional[int] = None
    pacing: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SaveChatRequest(BaseModel):
    session_id: str
    title: Optional[str] = "New Chat"
    messages: list = []
    destination: Optional[str] = None
