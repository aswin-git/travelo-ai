import requests
from typing import Dict, Any, Optional
from ..utils.logger import get_logger

logger = get_logger(__name__)

def fetch_osm_data(place_name: str) -> Optional[Dict[str, Any]]:
    """Fetches fast location data (Lat/Lng) using OSM Nominatim."""
    url = "https://nominatim.openstreetmap.org/search"
    
    params = {
        "q": place_name,
        "format": "json",
        "limit": 1,
        "addressdetails": 1
    }
    
    try:
        # Nominatim requires a valid User-Agent
        headers = {'User-Agent': 'TraveloAI/1.0 (contact@travelo.ai)'}
        
        # 5 seconds is more than enough for Nominatim
        response = requests.get(url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        
        if data and len(data) > 0:
            element = data[0]
            
            # Nominatim provides category via 'class' and 'type'
            category = element.get("class", "place")
            if element.get("type"):
                category += f"/{element.get('type')}"
                
            return {
                "name": element.get("name", place_name),
                "latitude": float(element.get("lat")),
                "longitude": float(element.get("lon")),
                "category": category,
                "osm_id": element.get("osm_id")
            }
            
        logger.info(f"OSM Nominatim found no results for: {place_name}")
        return None
        
    except requests.exceptions.RequestException as e:
        # Replaced print() with proper logging
        logger.error(f"OSM fetch error for {place_name}: {e}")
        return None