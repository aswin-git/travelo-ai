import requests
from typing import Dict, Any, Optional

def fetch_osm_data(place_name: str) -> Optional[Dict[str, Any]]:
    """Fetches location data from OpenStreetMap's Overpass API."""
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json];
    (
      node["name"~"{place_name}", i]["tourism"];
      node["name"~"{place_name}", i]["place"~"city|town"];
      way["name"~"{place_name}", i]["place"~"city|town"];
      rel["name"~"{place_name}", i]["place"~"city|town"];
    );
    out center 1;
    """
    try:
        headers = {'User-Agent': 'TraveloAI/1.0 (contact@travelo.ai)'}
        response = requests.post(overpass_url, data={'data': overpass_query}, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'elements' in data and len(data['elements']) > 0:
            element = data['elements'][0]
            tags = element.get("tags", {})
            return {
                "name": tags.get("name", place_name),
                "latitude": element.get("lat") or element.get("center", {}).get("lat"),
                "longitude": element.get("lon") or element.get("center", {}).get("lon"),
                "category": tags.get("tourism") or tags.get("place"),
                "osm_id": element.get("id")
            }
        return None
    except Exception as e:
        print(f"OSM fetch error: {e}")
        return None
