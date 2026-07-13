import json
import asyncio
from typing import Dict, Any, List
from ..utils.logger import get_logger
from .gemini_service import model
from .geo_routing_service import geocode_place
from .attraction_service import search_attractions

logger = get_logger(__name__)

async def get_similar_places(destination: str, query: str) -> Dict[str, Any]:
    """Uses LLM to suggest similar places, then fetches their data."""
    # 1. Fetch exact match
    exact_results = search_attractions(f"{query} in {destination}")
    exact_match = exact_results[0] if exact_results else None

    # 2. Ask LLM for similar places
    prompt = f"""You are a travel expert. The user is interested in '{query}' in '{destination}'.
    Suggest exactly 3 other similar tourist attractions or places in or near '{destination}'.
    Output ONLY a JSON list of 3 strings (the names of the places). Do not include any other text.
    Example: ["Place A", "Place B", "Place C"]
    """
    
    similar_places = []
    try:
        response = await model.generate_content_async(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        decoder = json.JSONDecoder()
        place_names, _ = decoder.raw_decode(response.text.strip())
        
        # 3. Fetch details for each similar place
        if isinstance(place_names, list):
            # Run SerpAPI searches in parallel for speed
            loop = asyncio.get_event_loop()
            futures = [
                loop.run_in_executor(None, lambda n=name: search_attractions(f"{n} in {destination}"))
                for name in place_names[:3]
            ]
            results = await asyncio.gather(*futures, return_exceptions=True)
            
            for res in results:
                if isinstance(res, list) and res:
                    similar_places.append(res[0])
    except Exception as e:
        logger.error(f"Failed to get similar places: {e}")
        
    return {
        "exact_match": exact_match,
        "similar_places": similar_places
    }

async def insert_places_into_itinerary(existing_itinerary: dict, added_places: List[dict]) -> dict:
    """Uses LLM to optimally insert new places into an existing itinerary."""
    if not added_places:
        return existing_itinerary
        
    # Geocode added places so LLM knows where they are
    dest_name = existing_itinerary.get("destination", "")
    for place in added_places:
        if not place.get("latitude") or not place.get("longitude"):
            geo = geocode_place(place.get("name", ""), near_city=dest_name)
            if geo:
                place["latitude"] = geo["latitude"]
                place["longitude"] = geo["longitude"]
                
    prompt = f"""You are an expert travel planner. You are given an EXISTING itinerary and a list of NEW places to add.
    
    EXISTING ITINERARY:
    {json.dumps(existing_itinerary, indent=2)}
    
    NEW PLACES TO ADD:
    {json.dumps(added_places, indent=2)}
    
    YOUR TASK:
    1. Insert the NEW places into the most geographically and chronologically logical spots in the existing itinerary.
    2. Try to group places that are geographically close together on the same day.
    3. Assign each new place a logical `time_slot`, `time_label`, and `duration_minutes`.
    4. You may slightly adjust the `time_label` of surrounding items if necessary to fit the new item, but you MUST keep them in the same order.
    5. CRITICAL: Do NOT delete, alter the descriptions of, or omit ANY existing places. All existing slots must remain in the itinerary.
    
    Return the fully updated itinerary as a JSON object matching the exact schema of the provided EXISTING ITINERARY.
    """
    
    try:
        response = await model.generate_content_async(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        decoder = json.JSONDecoder()
        updated_itinerary, _ = decoder.raw_decode(response.text.strip())
        return updated_itinerary
    except Exception as e:
        logger.error(f"Failed to insert places into itinerary: {e}")
        # Fallback to returning the original
        return existing_itinerary
