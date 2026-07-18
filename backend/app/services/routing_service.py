import requests
from typing import Optional
from functools import lru_cache
from ..utils.logger import get_logger

logger = get_logger(__name__)

@lru_cache(maxsize=512)
def get_driving_duration(lat1: float, lon1: float, lat2: float, lon2: float) -> Optional[int]:
    """
    Fetches the driving duration (in seconds) between two coordinates using OSRM public API.
    Returns None if the route cannot be found or API fails.
    """
    # OSRM expects coordinates in lon,lat order
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
    params = {
        "overview": "false"
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") == "Ok" and data.get("routes"):
            duration_sec = data["routes"][0].get("duration")
            return int(duration_sec) if duration_sec is not None else None
            
        logger.warning(f"OSRM returned no route between ({lat1},{lon1}) and ({lat2},{lon2})")
        return None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"OSRM routing error: {e}")
        return None

def get_driving_duration_str(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    """Returns a formatted travel time string (e.g., '🚗 15 mins drive') or a fallback."""
    duration_sec = get_driving_duration(lat1, lon1, lat2, lon2)
    if duration_sec is None:
        return "🚗 Short drive"
        
    mins = int(duration_sec / 60)
    if mins < 1:
        return "🚶 1 min walk"
    elif mins < 5:
        return "🚶 5 mins walk"
    else:
        return f"🚗 {mins} mins drive"
