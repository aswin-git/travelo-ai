"""
User management routes — profile, chat sessions, saved itineraries.
All endpoints require authentication via Supabase JWT.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from ..database import get_db
from ..auth.dependencies import get_current_user
from ..models.user_model import (
    User, ChatSession, SavedItinerary, SavedItem,
    UserResponse, UpdateUserRequest,
    ChatSessionListItem, ChatSessionResponse, SaveChatRequest,
    SaveItineraryRequest, SavedItineraryListItem, SavedItineraryResponse,
    SaveItemRequest, UpdatePinRequest, SavedItemResponse,
)
from ..utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/user", tags=["user"])


# ═══════ Profile ═══════

@router.get("/me", response_model=UserResponse)
def get_profile(user: User = Depends(get_current_user)):
    """Get the current user's profile."""
    return user


@router.put("/me", response_model=UserResponse)
def update_profile(
    body: UpdateUserRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current user's display name, avatar, or preferences."""
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url
    if body.preferences is not None:
        user.preferences = body.preferences
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user


# ═══════ Chat Sessions ═══════

@router.get("/chat-sessions", response_model=List[ChatSessionListItem])
def list_chat_sessions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all chat sessions for the current user, newest first."""
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return sessions


@router.get("/chat-sessions/{session_id}", response_model=ChatSessionResponse)
def get_chat_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Load a full chat session with all messages."""
    session = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id, ChatSession.session_id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


@router.post("/chat-sessions", response_model=ChatSessionResponse)
def save_chat_session(
    body: SaveChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update a chat session."""
    session = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id, ChatSession.session_id == body.session_id)
        .first()
    )
    if session:
        session.messages = body.messages
        if body.title and body.title != "New Chat":
            session.title = body.title
        if body.destination:
            session.destination = body.destination
        session.updated_at = datetime.utcnow()
    else:
        session = ChatSession(
            user_id=user.id,
            session_id=body.session_id,
            title=body.title or "New Chat",
            messages=body.messages,
            destination=body.destination,
        )
        db.add(session)

    db.commit()
    db.refresh(session)
    return session


@router.delete("/chat-sessions/{session_id}")
def delete_chat_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a chat session."""
    session = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id, ChatSession.session_id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    db.delete(session)
    db.commit()
    return {"status": "deleted"}


# ═══════ Saved Itineraries ═══════

@router.post("/itineraries", response_model=SavedItineraryResponse)
def save_itinerary(
    body: SaveItineraryRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save an itinerary for the current user."""
    itinerary = SavedItinerary(
        user_id=user.id,
        title=body.title,
        destination=body.destination,
        itinerary_data=body.itinerary_data,
        total_days=body.total_days,
        pacing=body.pacing,
    )
    db.add(itinerary)
    db.commit()
    db.refresh(itinerary)
    logger.info(f"Saved itinerary '{body.title}' for user {user.email}")
    return itinerary


@router.get("/itineraries", response_model=List[SavedItineraryListItem])
def list_itineraries(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all saved itineraries for the current user, newest first."""
    itineraries = (
        db.query(SavedItinerary)
        .filter(SavedItinerary.user_id == user.id)
        .order_by(SavedItinerary.created_at.desc())
        .all()
    )
    return itineraries


@router.get("/itineraries/{itinerary_id}", response_model=SavedItineraryResponse)
def get_itinerary(
    itinerary_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Load a full saved itinerary."""
    itinerary = (
        db.query(SavedItinerary)
        .filter(SavedItinerary.user_id == user.id, SavedItinerary.id == itinerary_id)
        .first()
    )
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    return itinerary


@router.delete("/itineraries/{itinerary_id}")
def delete_itinerary(
    itinerary_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a saved itinerary."""
    itinerary = (
        db.query(SavedItinerary)
        .filter(SavedItinerary.user_id == user.id, SavedItinerary.id == itinerary_id)
        .first()
    )
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    db.delete(itinerary)
    db.commit()
    return {"status": "deleted"}


# ═══════ Saved Items ═══════

@router.post("/saved-items", response_model=SavedItemResponse)
def save_item(
    body: SaveItemRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save a hotel/attraction/restaurant/event. Upserts if already saved."""
    existing = (
        db.query(SavedItem)
        .filter(
            SavedItem.user_id == user.id,
            SavedItem.item_type == body.item_type,
            SavedItem.item_name == body.item_name,
        )
        .first()
    )
    if existing:
        # Update existing saved item
        existing.item_data = body.item_data
        existing.destination = body.destination or existing.destination
        if body.pinned_day is not None:
            existing.pinned_day = body.pinned_day
        if body.notes is not None:
            existing.notes = body.notes
        db.commit()
        db.refresh(existing)
        logger.info(f"Updated saved item '{body.item_name}' for user {user.email}")
        return existing

    item = SavedItem(
        user_id=user.id,
        item_type=body.item_type,
        item_name=body.item_name,
        destination=body.destination,
        item_data=body.item_data,
        pinned_day=body.pinned_day,
        notes=body.notes,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    logger.info(f"Saved item '{body.item_name}' ({body.item_type}) for user {user.email}")
    return item


@router.get("/saved-items", response_model=List[SavedItemResponse])
def list_saved_items(
    destination: str = None,
    item_type: str = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List saved items, optionally filtered by destination and/or item_type."""
    query = db.query(SavedItem).filter(SavedItem.user_id == user.id)
    if destination:
        query = query.filter(SavedItem.destination.ilike(f"%{destination}%"))
    if item_type:
        query = query.filter(SavedItem.item_type == item_type)
    return query.order_by(SavedItem.created_at.desc()).all()


@router.patch("/saved-items/{item_id}/pin", response_model=SavedItemResponse)
def pin_saved_item(
    item_id: str,
    body: UpdatePinRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pin or unpin a saved item to a specific itinerary day."""
    item = (
        db.query(SavedItem)
        .filter(SavedItem.user_id == user.id, SavedItem.id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Saved item not found")
    item.pinned_day = body.pinned_day
    db.commit()
    db.refresh(item)
    logger.info(f"{'Pinned' if body.pinned_day else 'Unpinned'} item '{item.item_name}' to Day {body.pinned_day}")
    return item


@router.delete("/saved-items/{item_id}")
def delete_saved_item(
    item_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a saved item."""
    item = (
        db.query(SavedItem)
        .filter(SavedItem.user_id == user.id, SavedItem.id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Saved item not found")
    db.delete(item)
    db.commit()
    return {"status": "deleted"}
