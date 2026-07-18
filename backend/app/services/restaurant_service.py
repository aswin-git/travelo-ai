from serpapi import GoogleSearch
from typing import List, Dict, Any, Optional
from ..config import settings
from .cache_service import cached_serpapi_call, TTL_6H
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

import re

def search_restaurants(
    destination: str,
    cuisine: Optional[str] = None,
    dietary_restrictions: Optional[str] = None,
    kids_friendly: Optional[bool] = None
) -> List[Dict[str, Any]]:
    """Searches for restaurants and applies a cuisine-matching and rating scoring engine."""
    api_key = settings.SERPAPI_KEY
    if not api_key:
        print("Restaurant search error: SERPAPI_KEY not configured")
        return []

    query_parts = ["top rated"]
    if kids_friendly:
        query_parts.append("family friendly")
    if dietary_restrictions:
        query_parts.append(dietary_restrictions)
    if cuisine:
        query_parts.append(cuisine)
    query_parts.append("restaurants in")
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
        results = cached_serpapi_call("restaurants", params, ttl=TTL_6H)
        
        locals_results = results.get("local_results", [])
        
        scored_restaurants = []
        for loc in locals_results[:20]:  # Evaluate top 20
            name = loc.get("title", "Unknown Restaurant")
            desc = loc.get("description", "")
            type_str = loc.get("type", "")
            
            # 1. Base Rating Score (out of 10)
            rating = loc.get("rating") or 0.0
            rating_score = (rating / 5.0) * 10
            
            # 2. Cuisine Match Score (out of 15)
            cuisine_score = 0
            if cuisine:
                c_lower = cuisine.lower()
                combined_text = (name + " " + desc + " " + type_str).lower()
                # Exact match gets 15, partial gets 5
                if re.search(r'\b' + re.escape(c_lower) + r'\b', combined_text):
                    cuisine_score = 15
                elif c_lower in combined_text:
                    cuisine_score = 5
            
            # 3. Popularity (out of 5)
            reviews = loc.get("reviews") or 0
            pop_score = min(5, (reviews / 1000) * 5)
            
            total_score = rating_score + cuisine_score + pop_score
            
            gps = loc.get("gps_coordinates") or {}
            scored_restaurants.append({
                "name": name,
                "rating": rating,
                "reviews": reviews,
                "description": desc,
                "thumbnail": loc.get("thumbnail", ""),
                "data_id": loc.get("data_id"),
                "price_level": loc.get("price", ""),
                "latitude": gps.get("latitude"),
                "longitude": gps.get("longitude"),
                "total_score": total_score
            })
            
        scored_restaurants.sort(key=lambda x: x["total_score"], reverse=True)
        return scored_restaurants[:5]
        
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
        results = cached_serpapi_call("restaurant_reviews", params, ttl=TTL_6H)
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
