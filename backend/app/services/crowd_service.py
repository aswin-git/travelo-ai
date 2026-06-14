# crowd_service.py
"""
Fetches crowd/busyness data for places using SerpAPI Google Maps Place API.

Uses `popular_times` from the Place result to determine how crowded a
location typically is at a given day+hour. Supports an in-memory TTL cache
so repeated requests within 2 hours don't burn extra API credits.
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from serpapi import GoogleSearch

from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# In-memory cache: key = data_id, value = { "data": ..., "ts": unix_time }
# TTL = 2 hours (crowd patterns don't change that fast)
# ---------------------------------------------------------------------------
_crowd_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 2 * 60 * 60  # 2 hours


def _get_cached(data_id: str) -> Optional[dict]:
    """Return cached crowd data if fresh, else None."""
    entry = _crowd_cache.get(data_id)
    if entry and (time.time() - entry["ts"]) < CACHE_TTL_SECONDS:
        logger.info(f"Crowd cache HIT for {data_id}")
        return entry["data"]
    return None


def _set_cache(data_id: str, data: dict):
    _crowd_cache[data_id] = {"data": data, "ts": time.time()}


# ---------------------------------------------------------------------------
# Score → label mapping
# ---------------------------------------------------------------------------
def _score_to_label(score: int) -> str:
    if score <= 30:
        return "Not Crowded"
    elif score <= 60:
        return "Moderately Crowded"
    else:
        return "Very Crowded"


def _score_to_emoji(score: int) -> str:
    if score <= 30:
        return "🟢"
    elif score <= 60:
        return "🟡"
    else:
        return "🔴"


# ---------------------------------------------------------------------------
# Core: fetch popular_times for a single place via data_id
# ---------------------------------------------------------------------------
DAY_NAMES = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]


def fetch_crowd_data(data_id: str, visit_hour: int = None) -> Optional[dict]:
    """Fetch crowd data for a place using its data_id.

    Args:
        data_id: Google Maps data_id for the place.
        visit_hour: Hour of visit (0-23). Defaults to current hour.

    Returns:
        Dict with busyness_score, crowd_label, crowd_emoji, info or None.
    """
    if not data_id:
        return None

    # Check cache first
    cached = _get_cached(data_id)
    if cached:
        return cached

    api_key = settings.SERPAPI_KEY
    if not api_key:
        logger.error("SERPAPI_KEY not configured for crowd data")
        return None

    now = datetime.now()
    day_name = DAY_NAMES[now.weekday()]  # Python: Mon=0 → we need to remap
    # Python weekday: Mon=0, Tue=1, ..., Sun=6
    # DAY_NAMES index: Sun=0, Mon=1, ..., Sat=6
    day_index_map = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 0}
    day_name = DAY_NAMES[day_index_map[now.weekday()]]

    if visit_hour is None:
        visit_hour = now.hour

    try:
        params = {
            "engine": "google_maps",
            "type": "place",
            "data_id": data_id,
            "hl": "en",
            "api_key": api_key,
        }
        search = GoogleSearch(params)
        results = search.get_dict()

        place = results.get("place_results", {})
        popular_times = place.get("popular_times", {})
        graph = popular_times.get("graph_results", {})

        day_data = graph.get(day_name, [])
        if not day_data:
            logger.info(f"No popular_times data for {data_id} on {day_name}")
            result = {
                "busyness_score": None,
                "crowd_label": "Unknown",
                "crowd_emoji": "⚪",
                "info": "No crowd data available",
            }
            _set_cache(data_id, result)
            return result

        # Find the closest hour entry
        best_entry = None
        for entry in day_data:
            time_str = entry.get("time", "")
            # Parse "6 AM", "10 AM", "2 PM" etc.
            try:
                entry_hour = _parse_hour(time_str)
                if entry_hour is not None and entry_hour == visit_hour:
                    best_entry = entry
                    break
            except Exception:
                continue

        if not best_entry:
            # Fallback: find nearest hour
            best_diff = 999
            for entry in day_data:
                time_str = entry.get("time", "")
                entry_hour = _parse_hour(time_str)
                if entry_hour is not None:
                    diff = abs(entry_hour - visit_hour)
                    if diff < best_diff:
                        best_diff = diff
                        best_entry = entry

        if best_entry:
            score = best_entry.get("busyness_score", 0)
            info = best_entry.get("info", "")
            result = {
                "busyness_score": score,
                "crowd_label": _score_to_label(score),
                "crowd_emoji": _score_to_emoji(score),
                "info": info or f"Busyness score: {score}/100",
            }
        else:
            result = {
                "busyness_score": None,
                "crowd_label": "Unknown",
                "crowd_emoji": "⚪",
                "info": "No crowd data available for this hour",
            }

        _set_cache(data_id, result)
        logger.info(f"Crowd data for {data_id}: {result['crowd_label']} (score: {result['busyness_score']})")
        return result

    except Exception as e:
        logger.error(f"Crowd data fetch failed for {data_id}: {e}", exc_info=True)
        return None


def _parse_hour(time_str: str) -> Optional[int]:
    """Parse '6 AM', '10 AM', '2 PM' → 24h int."""
    if not time_str:
        return None
    time_str = time_str.strip().upper()
    parts = time_str.replace("  ", " ").split(" ")
    if len(parts) != 2:
        return None
    hour = int(parts[0])
    ampm = parts[1]
    if ampm == "PM" and hour != 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    return hour


# ---------------------------------------------------------------------------
# Batch: fetch crowd data for multiple places
# ---------------------------------------------------------------------------
def batch_fetch_crowd_data(
    places: List[dict], visit_hours: Optional[Dict[str, int]] = None
) -> Dict[str, dict]:
    """Fetch crowd data for a list of places.

    Args:
        places: List of place dicts, each must have 'name' and 'data_id'.
        visit_hours: Optional mapping of place name → expected visit hour.

    Returns:
        Dict mapping place name → crowd data dict.
    """
    crowd_map = {}
    for place in places:
        name = place.get("name", "Unknown")
        data_id = place.get("data_id")
        if not data_id:
            logger.info(f"No data_id for '{name}', skipping crowd fetch")
            crowd_map[name] = {
                "busyness_score": None,
                "crowd_label": "Unknown",
                "crowd_emoji": "⚪",
                "info": "No data_id available",
            }
            continue

        hour = (visit_hours or {}).get(name)
        result = fetch_crowd_data(data_id, visit_hour=hour)
        crowd_map[name] = result or {
            "busyness_score": None,
            "crowd_label": "Unknown",
            "crowd_emoji": "⚪",
            "info": "Fetch failed",
        }

    return crowd_map
