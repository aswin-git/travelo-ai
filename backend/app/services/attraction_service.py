from serpapi import GoogleSearch
from typing import List, Dict, Any, Optional
from ..config import settings
from .cache_service import cached_serpapi_call, TTL_6H
from sqlalchemy.orm import Session
from ..models.place_model import Attraction
import uuid

def save_attractions_to_db(db: Session, attractions_data: List[Dict[str, Any]], place_id: uuid.UUID):
    """Saves attraction results to the database for future use, avoiding duplicates."""
    for a in attractions_data:
        data_id = a.get("data_id")
        if not data_id:
            continue
            
        existing = db.query(Attraction).filter(Attraction.data_id == data_id).first()
        if existing:
            existing.rating = a.get("rating")
            existing.reviews_count = a.get("reviews")
            existing.description = a.get("description")
            existing.thumbnail = a.get("thumbnail")
            continue
            
        new_attr = Attraction(
            name=a.get("name"),
            place_id=place_id,
            rating=a.get("rating"),
            reviews_count=a.get("reviews"),
            description=a.get("description"),
            thumbnail=a.get("thumbnail"),
            data_id=data_id
        )
        db.add(new_attr)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error saving attractions to DB: {e}")

def search_attractions(
    destination: str,
    interests: Optional[str] = None,
    activity_level: Optional[str] = None,
    kids_friendly: Optional[bool] = None
) -> List[Dict[str, Any]]:
    """Searches for top attractions in a city using SerpAPI's Google Maps engine.
    
    Args:
        destination: City or place name to search attractions in.
        interests: Optional keywords like 'history', 'nature', etc.
        activity_level: Optional 'high' or 'low'.
        kids_friendly: True to filter for family-friendly places.
    
    Returns:
        List of attraction dicts with name, rating, description, thumbnail, and data_id.
    """
    api_key = settings.SERPAPI_KEY
    if not api_key:
        print("Attraction search error: SERPAPI_KEY not configured")
        return []

    query_parts = ["top rated"]
    if kids_friendly:
        query_parts.append("family friendly kids")
    if interests:
        query_parts.append(interests)
    if activity_level == "high":
        query_parts.append("active outdoor")
    elif activity_level == "low":
        query_parts.append("relaxed indoor")
    query_parts.append("attractions in")
    query_parts.append(destination)
    
    query_str = " ".join(query_parts)

    params = {
        "engine": "google_maps",
        "q": query_str,
        "type": "search",
        "hl": "en",
        "gl": "in",
        "api_key": api_key,
    }

    try:
        results = cached_serpapi_call("attractions", params, ttl=TTL_6H)
        
        locals_results = results.get("local_results", [])
        
        attractions = []
        for loc in locals_results[:10]:
            gps = loc.get("gps_coordinates") or {}
            attractions.append({
                "name": loc.get("title", "Unknown Attraction"),
                "rating": loc.get("rating"),
                "reviews": loc.get("reviews"),
                "description": loc.get("description", ""),
                "thumbnail": loc.get("thumbnail", ""),
                "data_id": loc.get("data_id"),
                "latitude": gps.get("latitude"),
                "longitude": gps.get("longitude"),
            })
        
        return attractions
        
    except Exception as e:
        print(f"Attraction search error: {e}")
        return []

def get_attraction_reviews(data_id: str) -> List[str]:
    """Fetches up to 50 reviews for an attraction using its data_id."""
    api_key = settings.SERPAPI_KEY
    if not api_key:
        return []

    params = {
        "engine": "google_maps_reviews",
        "data_id": data_id,
        "hl": "en",
        "gl": "in",
        "api_key": api_key,
    }

    try:
        results = cached_serpapi_call("attraction_reviews", params, ttl=TTL_6H)
        reviews_data = results.get("reviews", [])
        
        # Extract the review text from the top reviews
        reviews = []
        for r in reviews_data:
            text = r.get("snippet") or r.get("text")
            if text:
                reviews.append(text)
        return reviews[:50]
        
    except Exception as e:
        print(f"Attraction reviews search error: {e}")
        return []
