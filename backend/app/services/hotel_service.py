from serpapi import GoogleSearch
from typing import List, Dict, Any, Optional
from datetime import date, timedelta
from ..config import settings
from sqlalchemy.orm import Session
from ..models.place_model import Hotel
import uuid

def save_hotels_to_db(db: Session, hotels_data: List[Dict[str, Any]], place_id: uuid.UUID):
    """Saves hotel results to the database for future use, avoiding duplicates."""
    for h in hotels_data:
        token = h.get("property_token")
        if not token:
            continue
            
        # Check if hotel with this token already exists
        existing = db.query(Hotel).filter(Hotel.property_token == token).first()
        if existing:
            continue
            
        new_hotel = Hotel(
            name=h.get("name"),
            place_id=place_id,
            price=str(h.get("price")),
            rating=h.get("rating"),
            reviews_count=h.get("reviews"),
            description=h.get("description"),
            link=h.get("link"),
            thumbnail=h.get("thumbnail"),
            property_token=token
        )
        db.add(new_hotel)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error saving hotels to DB: {e}")

def search_hotels(
    destination: str,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    adults: int = 2
) -> List[Dict[str, Any]]:
    """Searches for hotels using SerpAPI's Google Hotels engine.
    
    Args:
        destination: City or place name to search hotels in.
        check_in: Check-in date in YYYY-MM-DD format. Defaults to tomorrow.
        check_out: Check-out date in YYYY-MM-DD format. Defaults to check_in + 2 nights.
        adults: Number of adults. Defaults to 2.
    
    Returns:
        List of hotel dicts with name, price, rating, description, link, thumbnail.
    """
    api_key = settings.SERPAPI_KEY
    if not api_key:
        print("Hotel search error: SERPAPI_KEY not configured")
        return []

    # Default dates: tomorrow + 2 nights
    if not check_in:
        check_in = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    if not check_out:
        check_in_date = date.fromisoformat(check_in)
        check_out = (check_in_date + timedelta(days=2)).strftime("%Y-%m-%d")

    params = {
        "engine": "google_hotels",
        "q": f"Hotels in {destination}",
        "check_in_date": check_in,
        "check_out_date": check_out,
        "adults": str(adults),
        "currency": "INR",
        "hl": "en",
        "gl": "in",
        "api_key": api_key,
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        
        properties = results.get("properties", [])
        
        hotels = []
        for hotel in properties[:5]:  # Return top 5 hotels
            rate = hotel.get("rate_per_night", {})
            hotels.append({
                "name": hotel.get("name", "Unknown Hotel"),
                "price": rate.get("lowest", "N/A"),
                "rating": hotel.get("overall_rating"),
                "reviews": hotel.get("reviews"),
                "description": hotel.get("description", ""),
                "link": hotel.get("link", ""),
                "thumbnail": hotel.get("images", [{}])[0].get("thumbnail", "") if hotel.get("images") else "",
                "check_in": check_in,
                "check_out": check_out,
                "property_token": hotel.get("property_token"),
            })
        
        return hotels
        
    except Exception as e:
        print(f"Hotel search error: {e}")
        return []

def get_hotel_reviews(property_token: str) -> List[str]:
    """Fetches up to 50 reviews for a hotel using its property_token."""
    api_key = settings.SERPAPI_KEY
    if not api_key:
        return []

    params = {
        "engine": "google_hotels_reviews",
        "property_token": property_token,
        "hl": "en",
        "gl": "in",
        "api_key": api_key,
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        reviews_data = results.get("reviews", [])
        
        # Extract the review text from the top reviews
        reviews = [r.get("snippet") for r in reviews_data if r.get("snippet")]
        return reviews[:50]
        
    except Exception as e:
        print(f"Hotel reviews search error: {e}")
        return []
