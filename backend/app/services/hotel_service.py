from serpapi import GoogleSearch
from typing import List, Dict, Any, Optional
from datetime import date, timedelta
from ..config import settings
from .cache_service import cached_serpapi_call, TTL_1H, TTL_6H
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
            existing.price = str(h.get("price"))
            existing.rating = h.get("rating")
            existing.reviews_count = h.get("reviews")
            existing.description = h.get("description")
            existing.thumbnail = h.get("thumbnail")
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

import math

def search_hotels(
    destination: str,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    adults: int = 2,
    budget: Optional[int] = None,
    traveler_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Searches for hotels using SerpAPI and applies a 6-factor scoring engine."""
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
        results = cached_serpapi_call("hotels", params, ttl=TTL_1H)
        
        properties = results.get("properties", [])
        
        scored_hotels = []
        for hotel in properties[:20]:  # Fetch up to 20 for scoring
            # 1. Rating Score (out of 10)
            rating = hotel.get("overall_rating") or 0.0
            rating_score = (rating / 5.0) * 10
            
            # 2. Review Count Score (out of 10, log scale)
            reviews = hotel.get("reviews") or 0
            review_score = min(10, math.log10(reviews + 1) * 2.5)
            
            # 3. Value/Budget Score (out of 10)
            rate = hotel.get("rate_per_night", {})
            price_str = rate.get("lowest", "0").replace('₹', '').replace(',', '').strip()
            try:
                price_val = int(price_str)
            except:
                price_val = 0
                
            value_score = 5 # Default
            if budget and price_val > 0:
                diff = abs(budget - price_val)
                # 0 diff = 10, >= budget diff = 0
                value_score = max(0, 10 - (diff / budget) * 10)
                
            # 4 & 6. Traveler Type & Context Relevance (out of 10)
            desc_text = (hotel.get("description", "") + " " + hotel.get("name", "")).lower()
            traveler_score = 0
            if traveler_type:
                tt = traveler_type.lower()
                if tt == "family" and any(k in desc_text for k in ["family", "kids", "children", "spacious"]):
                    traveler_score = 10
                elif tt == "couple" and any(k in desc_text for k in ["romantic", "couple", "honeymoon", "adults"]):
                    traveler_score = 10
                elif tt == "business" and any(k in desc_text for k in ["business", "desk", "conference", "work"]):
                    traveler_score = 10
                elif tt == "solo" and any(k in desc_text for k in ["solo", "hostel", "backpacker", "safe"]):
                    traveler_score = 10
                elif tt == "budget" and any(k in desc_text for k in ["budget", "cheap", "affordable", "hostel"]):
                    traveler_score = 10
                    
            # 5. Amenities Score (out of 10)
            amenities = hotel.get("amenities", [])
            amenities_str = " ".join([a.lower() for a in amenities]) + desc_text
            amenities_score = 0
            if "wifi" in amenities_str or "wi-fi" in amenities_str: amenities_score += 3
            if "pool" in amenities_str: amenities_score += 3
            if "breakfast" in amenities_str: amenities_score += 4
            
            total_score = rating_score + review_score + value_score + traveler_score + amenities_score
            
            scored_hotels.append({
                "name": hotel.get("name", "Unknown Hotel"),
                "price": rate.get("lowest", "N/A"),
                "rating": rating,
                "reviews": reviews,
                "description": hotel.get("description", ""),
                "link": hotel.get("link", ""),
                "thumbnail": hotel.get("images", [{}])[0].get("thumbnail", "") if hotel.get("images") else "",
                "check_in": check_in,
                "check_out": check_out,
                "property_token": hotel.get("property_token"),
                "total_score": total_score
            })
            
        # Rank and return top 5
        scored_hotels.sort(key=lambda x: x["total_score"], reverse=True)
        return scored_hotels[:5]
        
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
        results = cached_serpapi_call("hotel_reviews", params, ttl=TTL_6H)
        reviews_data = results.get("reviews", [])
        
        # Extract the review text from the top reviews
        reviews = [r.get("snippet") for r in reviews_data if r.get("snippet")]
        return reviews[:50]
        
    except Exception as e:
        print(f"Hotel reviews search error: {e}")
        return []
