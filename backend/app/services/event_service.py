from serpapi import GoogleSearch
from typing import List, Dict, Any
from ..config import settings
from .cache_service import cached_serpapi_call, TTL_2H
from sqlalchemy.orm import Session
from ..models.place_model import Event
import uuid

def save_events_to_db(db: Session, events_data: List[Dict[str, Any]], place_id: uuid.UUID):
    """Saves event results to the database for future use, avoiding duplicates."""
    for e in events_data:
        link = e.get("link")
        if not link:
            continue
            
        existing = db.query(Event).filter(Event.link == link).first()
        if existing:
            existing.date_string = e.get("date_string")
            existing.description = e.get("description")
            existing.thumbnail = e.get("thumbnail")
            existing.venue_name = e.get("venue_name")
            continue
            
        new_event = Event(
            title=e.get("title"),
            place_id=place_id,
            date_string=e.get("date_string"),
            address=e.get("address"),
            link=link,
            description=e.get("description"),
            thumbnail=e.get("thumbnail"),
            venue_name=e.get("venue_name")
        )
        db.add(new_event)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        print(f"Error saving events to DB: {exc}")

def search_events(destination: str) -> List[Dict[str, Any]]:
    """Searches for events in a city using SerpAPI's Google Events engine.
    
    Args:
        destination: City or place name to search events in.
    
    Returns:
        List of event dicts with title, date_string, address, link, description, thumbnail, and venue_name.
    """
    api_key = settings.SERPAPI_KEY
    if not api_key:
        print("Event search error: SERPAPI_KEY not configured")
        return []

    params = {
        "engine": "google_events",
        "q": f"events in {destination}",
        "hl": "en",
        "gl": "in",
        "api_key": api_key,
    }

    try:
        results = cached_serpapi_call("events", params, ttl=TTL_2H)
        
        events_results = results.get("events_results", [])
        
        events = []
        for e in events_results[:5]:  # Return top 5 events
            date_info = e.get("date", {})
            date_string = date_info.get("when", date_info.get("start_date", ""))
            
            address_list = e.get("address", [])
            address_str = ", ".join(address_list) if isinstance(address_list, list) else str(address_list)
            
            venue_info = e.get("venue", {})
            venue_name = venue_info.get("name", "")
            
            events.append({
                "title": e.get("title", "Unknown Event"),
                "date_string": date_string,
                "address": address_str,
                "link": e.get("link", ""),
                "description": e.get("description", ""),
                "thumbnail": e.get("thumbnail", ""),
                "venue_name": venue_name
            })
        
        return events
        
    except Exception as exc:
        print(f"Event search error: {exc}")
        return []
