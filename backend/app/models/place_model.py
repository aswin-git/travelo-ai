import uuid
from sqlalchemy import Column, String, Float, Text, BigInteger, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from ..database import Base
from pydantic import BaseModel, ConfigDict
from typing import Optional, List

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

class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    place_id = Column(UUID(as_uuid=True), ForeignKey("places.id"))
    date_string = Column(String(100))
    address = Column(String(500))
    link = Column(String(500))
    description = Column(Text)
    thumbnail = Column(Text)
    venue_name = Column(String(255))
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
    session_id: Optional[str] = None  # Identifies the conversation thread for multi-turn memory
    traveler_type: Optional[str] = None
    cuisine: Optional[str] = None
    adults: Optional[int] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    start_location: Optional[str] = None
    end_location: Optional[str] = None
    travel_mode: Optional[str] = None
    num_days: Optional[int] = None
    pacing: Optional[str] = None  # "relaxed" or "packed"
    meal_preference: Optional[str] = None  # "fixed" or "flexible"
    crowd_aware: Optional[bool] = None  # Whether to consider crowd data
    crowd_precision: Optional[str] = None  # "precise" (SerpAPI) or "approximate" (LLM estimate)
    conversation_history: Optional[list] = None  # Previous messages for restoring context on loaded sessions

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

class EventResult(BaseModel):
    title: str
    date_string: Optional[str] = None
    address: Optional[str] = None
    link: Optional[str] = None
    description: Optional[str] = None
    thumbnail: Optional[str] = None
    venue_name: Optional[str] = None

class DirectionResult(BaseModel):
    route_type: str  # "Fastest", "Cheapest", "Fewest Transfers"
    mode: str
    duration: str
    distance: str
    transfers: Optional[int] = None
    price: Optional[str] = None
    summary: str
    link: Optional[str] = None
    steps: Optional[list[str]] = None

class ItinerarySlot(BaseModel):
    time_slot: str       # "Morning", "Lunch", "Afternoon", "Evening", "Dinner"
    time_label: str      # "09:00 AM"
    activity_name: str
    description: str
    duration_minutes: int
    cost_estimate: Optional[str] = None
    category: str        # "attraction", "restaurant", "hotel", "travel", "activity"
    rating: Optional[float] = None
    travel_to_next: Optional[str] = None  # "🚗 15 mins drive"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    crowd_status: Optional[str] = None  # "Not Crowded" / "Moderately Crowded" / "Very Crowded" / "Unknown"

class ItineraryDay(BaseModel):
    day_number: int
    theme: str
    slots: List[ItinerarySlot]

class ItineraryResult(BaseModel):
    destination: str
    total_days: int
    pacing: str
    start_location: Optional[str] = None
    meal_preference: Optional[str] = None  # "fixed" or "flexible"
    days: List[ItineraryDay]

class ChatResponse(BaseModel):
    response: str
    source: str
    place_info: Optional[PlaceResponse] = None
    hotels: Optional[list[HotelResult]] = None
    attractions: Optional[list[AttractionResult]] = None
    restaurants: Optional[list[RestaurantResult]] = None
    events: Optional[list[EventResult]] = None
    directions: Optional[list[DirectionResult]] = None
    itinerary: Optional[ItineraryResult] = None
    show_review_prompt: Optional[bool] = False
    show_attractions_prompt: Optional[bool] = False
    show_restaurants_prompt: Optional[bool] = False
    show_events_prompt: Optional[bool] = False
    missing_info: Optional[list[str]] = None
