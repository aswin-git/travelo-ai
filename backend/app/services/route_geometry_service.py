"""
Route geometry service — fetches polyline coordinates from OSRM for map rendering.

Uses the same public OSRM endpoint proven in routing_service.py.
Returns decoded coordinate arrays suitable for Leaflet Polyline rendering.
"""
import requests
from typing import List, Tuple, Optional
from functools import lru_cache
from ..utils.logger import get_logger

logger = get_logger(__name__)

# OSRM returns polyline-encoded geometries; we need to decode them.
def _decode_polyline(encoded: str) -> List[Tuple[float, float]]:
    """Decodes a Google-format encoded polyline string into lat/lon tuples."""
    decoded = []
    index = 0
    lat = 0
    lng = 0

    while index < len(encoded):
        # Decode latitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        # Decode longitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng

        decoded.append((lat / 1e5, lng / 1e5))

    return decoded


def get_route_geometry(
    waypoints: List[dict],
) -> Optional[List[List[float]]]:
    """Fetches the driving route geometry between ordered waypoints from OSRM.

    Args:
        waypoints: List of dicts with 'lat' and 'lon' keys, in visit order.

    Returns:
        List of [lat, lon] coordinate pairs forming the polyline, or None on failure.
    """
    if len(waypoints) < 2:
        return None

    # OSRM expects coordinates as lon,lat pairs separated by semicolons
    coords_str = ";".join(
        f"{wp['lon']},{wp['lat']}" for wp in waypoints
    )
    url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}"
    params = {
        "overview": "full",       # Full resolution polyline
        "geometries": "polyline", # Google-encoded polyline format
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            logger.warning(f"OSRM returned no route for {len(waypoints)} waypoints")
            return None

        encoded_geometry = data["routes"][0].get("geometry", "")
        if not encoded_geometry:
            return None

        decoded = _decode_polyline(encoded_geometry)
        # Convert to [lat, lon] arrays for JSON serialization
        result = [[lat, lon] for lat, lon in decoded]
        logger.info(f"Decoded OSRM route: {len(result)} coordinate points for {len(waypoints)} waypoints")
        return result

    except requests.exceptions.RequestException as e:
        logger.error(f"OSRM route geometry error: {e}")
        return None
    except Exception as e:
        logger.error(f"Route geometry decode error: {e}", exc_info=True)
        return None
