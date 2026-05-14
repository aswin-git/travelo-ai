from serpapi import GoogleSearch
from typing import List, Dict, Any, Optional
from ..config import settings
from sqlalchemy.orm import Session
from ..models.place_model import Restaurant
import uuid

def save_restaurants_to_db(db: Session, restaurants_data: List[Dict[str, Any]], place_id: uuid.UUID):
    """Saves restaurant results to the database for future use, avoiding duplicates."""
    for r in restaurants_data:
        data_id = r.get("data_id")
        if not data_id:
            continue
            
        existing = db.query(Restaurant).filter(Restaurant.data_id == data_id).first()
        if existing:
            existing.rating = r.get("rating")
            existing.reviews_count = r.get("reviews")
            existing.description = r.get("description")
            existing.thumbnail = r.get("thumbnail")
            existing.price_level = r.get("price_level")
            continue
            
        new_rest = Restaurant(
            name=r.get("name"),
            place_id=place_id,
            rating=r.get("rating"),
            reviews_count=r.get("reviews"),
            description=r.get("description"),
            thumbnail=r.get("thumbnail"),
            data_id=data_id,
            price_level=r.get("price_level")
        )
        db.add(new_rest)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error saving restaurants to DB: {e}")

def search_restaurants(destination: str) -> List[Dict[str, Any]]:
    """Searches for top restaurants in a city using SerpAPI's Google Maps engine.
    
    Args:
        destination: City or place name to search restaurants in.
    
    Returns:
        List of restaurant dicts with name, rating, description, thumbnail, price_level, and data_id.
    """
    api_key = settings.SERPAPI_KEY
    if not api_key:
        print("Restaurant search error: SERPAPI_KEY not configured")
        return []

    params = {
        "engine": "google_maps",
        "q": f"top rated restaurants in {destination}",
        "type": "search",
        "hl": "en",
        "gl": "in",
        "api_key": api_key,
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        
        locals_results = results.get("local_results", [])
        
        restaurants = []
        for loc in locals_results[:5]:  # Return top 5 restaurants
            restaurants.append({
                "name": loc.get("title", "Unknown Restaurant"),
                "rating": loc.get("rating"),
                "reviews": loc.get("reviews"),
                "description": loc.get("description", ""),
                "thumbnail": loc.get("thumbnail", ""),
                "data_id": loc.get("data_id"),
                "price_level": loc.get("price", "")
            })
        
        return restaurants
        
    except Exception as e:
        print(f"Restaurant search error: {e}")
        return []

def get_restaurant_reviews(data_id: str) -> List[str]:
    """Fetches up to 50 reviews for a restaurant using its data_id."""
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
        search = GoogleSearch(params)
        results = search.get_dict()
        reviews_data = results.get("reviews", [])
        
        # Extract the review text from the top reviews
        reviews = []
        for r in reviews_data:
            text = r.get("snippet") or r.get("text")
            if text:
                reviews.append(text)
        return reviews[:50]
        
    except Exception as e:
        print(f"Restaurant reviews search error: {e}")
        return []
