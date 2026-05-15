import requests
from typing import Dict, Optional
from ..utils.text_cleaner import clean_text
from ..utils.logger import get_logger

# Initialize logger instead of using print()
logger = get_logger(__name__)

def fetch_wikipedia_summary(place_name: str) -> Optional[Dict[str, str]]:
    """Fetches a travel-focused summary from the Wikivoyage REST API."""
    
    # Wikimedia APIs prefer underscores over spaces for exact page matches
    formatted_name = place_name.replace(" ", "_")
    
    # FIX: Changed from en.wikipedia.org to en.wikivoyage.org
    url = f"https://en.wikivoyage.org/api/rest_v1/page/summary/{requests.utils.quote(formatted_name)}"
    
    try:
        headers = {'User-Agent': 'TraveloAI/1.0 (contact@travelo.ai)'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "title": data.get("title", place_name),
                "description": data.get("description", ""),
                "summary": clean_text(data.get("extract", "")),
                "url": data.get("content_urls", {}).get("desktop", {}).get("page", "")
            }
            
        elif response.status_code == 404:
            logger.info(f"Wikivoyage page not found for: {place_name}. (It might not be a major tourist destination).")
        else:
            logger.warning(f"Wikivoyage API returned status {response.status_code} for {place_name}")
            
        return None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching Wikivoyage data for {place_name}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in Wikivoyage fetch for {place_name}: {e}", exc_info=True)
        return None