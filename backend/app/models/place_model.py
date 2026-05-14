import uuid
from sqlalchemy import Column, String, Float, Text, BigInteger, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from ..database import Base
from pydantic import BaseModel, ConfigDict
from typing import Optional

class Place(Base):
    __tablename__ = "places"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    city = Column(String(255))
    category = Column(String(255))
    description = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    source = Column(String(50), default="system")
    wikipedia_url = Column(String(500))
    osm_id = Column(BigInteger)
    created_at = Column(DateTime, default=datetime.utcnow)

class Hotel(Base):
    __tablename__ = "hotels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    place_id = Column(UUID(as_uuid=True), ForeignKey("places.id"))
    price = Column(String(100))
    rating = Column(Float)
    reviews_count = Column(BigInteger)
    description = Column(Text)
    link = Column(Text)
    thumbnail = Column(Text)
    property_token = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Attraction(Base):
    __tablename__ = "attractions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    place_id = Column(UUID(as_uuid=True), ForeignKey("places.id"))
    rating = Column(Float)
    reviews_count = Column(BigInteger)
    description = Column(Text)
    thumbnail = Column(Text)
    data_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    place_id = Column(UUID(as_uuid=True), ForeignKey("places.id"))
    rating = Column(Float)
    reviews_count = Column(BigInteger)
    description = Column(Text)
    thumbnail = Column(Text)
    data_id = Column(String(255))
    price_level = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ReviewSummary(Base):
    __tablename__ = "review_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id = Column(UUID(as_uuid=True)) # Can be Place.id or Hotel.id
    subject_type = Column(String(50)) # 'place' or 'hotel'
    summary = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Pydantic models for API
class PlaceResponse(BaseModel):
    id: uuid.UUID
    name: str
    city: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source: Optional[str] = None
    wikipedia_url: Optional[str] = None
    osm_id: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)

class ChatRequest(BaseModel):
    message: str
    budget: Optional[int] = None

class HotelResult(BaseModel):
    name: str
    price: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    description: Optional[str] = None
    link: Optional[str] = None
    thumbnail: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    property_token: Optional[str] = None

class AttractionResult(BaseModel):
    name: str
    rating: Optional[float] = None
    reviews: Optional[int] = None
    description: Optional[str] = None
    thumbnail: Optional[str] = None
    data_id: Optional[str] = None

class RestaurantResult(BaseModel):
    name: str
    rating: Optional[float] = None
    reviews: Optional[int] = None
    description: Optional[str] = None
    thumbnail: Optional[str] = None
    data_id: Optional[str] = None
    price_level: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    source: str
    place_info: Optional[PlaceResponse] = None
    hotels: Optional[list[HotelResult]] = None
    attractions: Optional[list[AttractionResult]] = None
    restaurants: Optional[list[RestaurantResult]] = None
    show_review_prompt: Optional[bool] = False
    show_attractions_prompt: Optional[bool] = False
    show_restaurants_prompt: Optional[bool] = False
