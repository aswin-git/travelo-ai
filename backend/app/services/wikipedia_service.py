import requests
from typing import Dict, Optional
from ..utils.text_cleaner import clean_text
from ..utils.logger import get_logger

# Initialize logger instead of using print()
logger = get_logger(__name__)

def fetch_full_wikivoyage_content(place_name: str) -> Optional[Dict[str, str]]:
    """Fetches the full plain-text travel guide from the Wikivoyage Action API."""
    
    url = "https://en.wikivoyage.org/w/api.php"
    
    params = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "titles": place_name,
        "explaintext": True,      # Returns clean, plain text instead of messy HTML
        "exintro": False,         # False returns the FULL page content, not just the intro
        "redirects": 1,           # Automatically follow page redirects
    }
    
    try:
        headers = {'User-Agent': 'TraveloAI/1.0 (contact@travelo.ai)'}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            pages = data.get("query", {}).get("pages", {})
            
            # The API returns pages keyed by their page ID
            page_id = next(iter(pages))
            page_data = pages[page_id]
            
            if page_id == "-1":
                logger.info(f"Wikivoyage page not found for: {place_name}")
                return None
                
            return {
                "title": page_data.get("title", place_name),
                "summary": page_data.get("extract", ""),  # Using 'summary' key to minimize downstream breakage, but it contains full text
                "url": f"https://en.wikivoyage.org/wiki/{requests.utils.quote(page_data.get('title', place_name))}"
            }
            
        return None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching Wikivoyage data for {place_name}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in Wikivoyage fetch for {place_name}: {e}", exc_info=True)
        return None