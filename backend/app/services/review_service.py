#review_service.py


from serpapi import GoogleSearch
from typing import List, Optional
from ..config import settings
from .gemini_service import summarize_reviews
from ..utils.logger import get_logger
from .cache_service import cached_serpapi_call, TTL_6H, TTL_12H
from ..models.place_model import ReviewSummary
from sqlalchemy.orm import Session
import uuid

logger = get_logger(__name__)

def save_summary_to_db(db: Session, subject_id: uuid.UUID, subject_type: str, summary: str):
    """Saves a generated review summary to the database."""
    try:
        new_summary = ReviewSummary(
            subject_id=subject_id,
            subject_type=subject_type,
            summary=summary
        )
        db.add(new_summary)
        db.commit()
        logger.info(f"Saved review summary for {subject_type} ({subject_id}) to database.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving summary to DB: {e}")

def get_place_reviews(place_name: str) -> List[str]:
    """Fetches up to 50 reviews for a tourist attraction using Google Maps.
    Includes fallbacks for city-level searches.
    """
    api_key = settings.SERPAPI_KEY
    if not api_key:
        logger.error("SerpAPI key not configured for review search")
        return []

    logger.info(f"Starting review search for: {place_name}")

    def fetch_from_params(params):
        try:
            results = cached_serpapi_call("review_lookup", params, ttl=TTL_12H)
            
            # 1. Try place_results (Specific Landmark)
            target = results.get("place_results")
            
            # 2. Try local_results (Often contains the city or main entry)
            if not target:
                locals = results.get("local_results", [])
                if locals:
                    target = locals[0]
            
            if target:
                # ONLY use data_id or place_id for reviews (kgmid is NOT for reviews)
                return target.get("data_id") or target.get("place_id")
            return None
        except Exception as e:
            print(f"Extraction error: {e}")
            return None

    # Strategy 1: Direct search on Google Maps
    print(f"Review Search Strategy 1 for: {place_name}")
    data_id = fetch_from_params({
        "engine": "google_maps",
        "q": place_name,
        "type": "search",
        "hl": "en",
        "gl": "in",
        "api_key": api_key,
    })

    # Strategy 2: City Landmark Search (for places like Alappuzha, Beach/Tourism usually have the reviews)
    if not data_id:
        print(f"Review Search Strategy 2 for: {place_name} Tourism")
        data_id = fetch_from_params({
            "engine": "google_maps",
            "q": f"{place_name} Tourism",
            "type": "search",
            "hl": "en",
            "gl": "in",
            "api_key": api_key,
        })

    # Strategy 3: Local Search via Google (sometimes finds IDs Maps search misses)
    if not data_id:
        print(f"Review Search Strategy 3 (Local Search via Google) for: {place_name}")
        data_id = fetch_from_params({
            "engine": "google",
            "q": f"{place_name} reviews",
            "hl": "en",
            "gl": "in",
            "api_key": api_key,
        })

    if not data_id:
        print(f"CRITICAL: No usable Review ID found for {place_name} after all fallbacks.")
        return []

    print(f"Found ID for reviews: {data_id}. Fetching reviews...")
    try:
        # Step 2: Fetch reviews using the ID
        review_params = {
            "engine": "google_maps_reviews",
            "data_id": data_id,
            "hl": "en",
            "gl": "in",
            "api_key": api_key,
        }
        
        review_results = cached_serpapi_call("place_reviews", review_params, ttl=TTL_12H)
        
        logger.info(f"Review API Response keys: {list(review_results.keys())}")
        reviews_data = review_results.get("reviews", [])
        
        # If no reviews found for this specific ID, try to pivot to "Top Attractions" in that city
        if not reviews_data:
            logger.info(f"No direct reviews for ID {data_id}. Pivoting to top attractions in {place_name}...")
            pivot_params = {
                "engine": "google_maps",
                "q": f"top rated attractions in {place_name}",
                "type": "search",
                "hl": "en",
                "gl": "in",
                "api_key": api_key,
            }
            pivot_results = cached_serpapi_call("review_pivot", pivot_params, ttl=TTL_12H)
            
            locals = pivot_results.get("local_results", [])
            if locals:
                best_attraction = locals[0]
                new_data_id = best_attraction.get("data_id")
                if new_data_id:
                    logger.info(f"Pivoting to reviews for: {best_attraction.get('title')} ({new_data_id})")
                    review_params["data_id"] = new_data_id
                    review_results = cached_serpapi_call("place_reviews", review_params, ttl=TTL_12H)
                    reviews_data = review_results.get("reviews", [])

        # Extract 'snippet' or 'text'
        reviews = []
        for r in reviews_data:
            text = r.get("snippet") or r.get("text")
            if text:
                reviews.append(text)
        
        return reviews[:50]

    except Exception as e:
        print(f"Place reviews search error: {e}")
        return []

async def get_and_summarize_reviews(subject_name: str, hotel_token: str = None, data_id: str = None, restaurant_data_id: str = None) -> str:
    """Orchestrates fetching and summarizing reviews."""
    if hotel_token:
        from .hotel_service import get_hotel_reviews
        logger.info(f"Fetching hotel reviews for {subject_name} using token...")
        reviews = get_hotel_reviews(hotel_token)
    elif data_id:
        from .attraction_service import get_attraction_reviews
        logger.info(f"Fetching attraction reviews for {subject_name} using data_id...")
        reviews = get_attraction_reviews(data_id)
    elif restaurant_data_id:
        from .restaurant_service import get_restaurant_reviews
        logger.info(f"Fetching restaurant reviews for {subject_name} using restaurant_data_id...")
        reviews = get_restaurant_reviews(restaurant_data_id)
    else:
        logger.info(f"Fetching place reviews for {subject_name}...")
        reviews = get_place_reviews(subject_name)
        
    if not reviews:
        logger.warning(f"No reviews found for {subject_name}")
        return f"I couldn't find any recent user reviews for {subject_name}."
        
    logger.info(f"Successfully retrieved {len(reviews)} reviews for {subject_name}. Summarizing...")
    reviews_text = "\n---\n".join(reviews)
    summary = await summarize_reviews(reviews_text, subject_name)
    return summary

def get_place_description(place_name: str) -> Optional[str]:
    """Fetches a description of a place using SerpAPI Google Search."""
    api_key = settings.SERPAPI_KEY
    if not api_key:
        return None

    params = {
        "engine": "google",
        "q": place_name,
        "hl": "en",
        "gl": "in",
        "api_key": api_key,
    }

    try:
        results = cached_serpapi_call("place_description", params, ttl=TTL_12H)
        
        # 1. Try Knowledge Graph description
        kg = results.get("knowledge_graph", {})
        if kg.get("description"):
            return kg.get("description")
            
        # 2. Try organic result snippets
        organic = results.get("organic_results", [])
        if organic:
            return organic[0].get("snippet")
            
        return None
    except Exception as e:
        print(f"SerpAPI description fetch error: {e}")
        return None
