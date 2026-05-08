import requests
from typing import Dict, Any, Optional
from ..utils.text_cleaner import clean_text

def fetch_wikipedia_summary(place_name: str) -> Optional[Dict[str, str]]:
    """Fetches a summary from Wikipedia REST API."""
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(place_name)}"
    try:
        headers = {'User-Agent': 'TraveloAI/1.0 (contact@travelo.ai)'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                "title": data.get("title", place_name),
                "summary": clean_text(data.get("extract", "")),
                "url": data.get("content_urls", {}).get("desktop", {}).get("page", "")
            }
        return None
    except Exception as e:
        print(f"Wikipedia fetch error: {e}")
        return None
