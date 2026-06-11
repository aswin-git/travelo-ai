# geo_routing_service.py
"""
Geographical intelligence layer for itinerary planning.

Provides:
- Geocoding via OSM Nominatim (with destination bias)
- Haversine straight-line distance between coordinates
- Nearest-neighbor stop ordering from a given origin
- Restaurant interleaving at meal slots based on proximity
"""

import math
import time
from typing import Optional
from ..utils.logger import get_logger
from .osm_service import fetch_osm_data

logger = get_logger(__name__)


# ─── Haversine Distance ───────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates the great-circle distance between two points on Earth (in km).

    Uses the Haversine formula — accurate enough for routing within a city/region
    and requires zero API calls.
    """
    R = 6371.0  # Earth's mean radius in km

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ─── Geocoding ─────────────────────────────────────────────────────────────────

def resolve_destination(destination: str) -> Optional[dict]:
    """Resolves a destination name to coordinates using OSM Nominatim.

    Used to establish the geographic anchor for all subsequent geocoding.
    Tries increasingly broad queries to handle locally-known names that OSM
    may only recognize under a different spelling (e.g., Wagamon → Vagamon).

    Returns:
        Dict with latitude, longitude — or None if unresolvable.
    """
    queries = [
        destination,
        f"{destination}, Kerala",
        f"{destination}, India",
    ]
    for q in queries:
        try:
            result = fetch_osm_data(q)
            if result and result.get("latitude") and result.get("longitude"):
                logger.info(f"Destination '{destination}' resolved via query '{q}' → ({result['latitude']:.4f}, {result['longitude']:.4f})")
                return result
        except Exception:
            pass
    logger.warning(f"Could not resolve destination '{destination}' to coordinates.")
    return None


def _nominatim_viewbox_search(place_name: str, center_lat: float, center_lon: float, radius_deg: float = 0.5) -> Optional[dict]:
    """Searches Nominatim with a bounding-box bias around known coordinates.

    This is the last-resort fallback when query-based geocoding fails. It tells
    Nominatim to prioritise results within a box around the destination centre,
    which dramatically improves hit rates for obscure local place names.
    """
    import requests
    url = "https://nominatim.openstreetmap.org/search"
    viewbox = (
        f"{center_lon - radius_deg},{center_lat + radius_deg},"
        f"{center_lon + radius_deg},{center_lat - radius_deg}"
    )
    params = {
        "q": place_name,
        "format": "json",
        "limit": 1,
        "bounded": 0,          # Don't restrict to box, just bias toward it
        "viewbox": viewbox,
        "addressdetails": 1,
    }
    try:
        headers = {"User-Agent": "TraveloAI/1.0 (contact@travelo.ai)"}
        response = requests.get(url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data:
            el = data[0]
            return {
                "name": el.get("name", place_name),
                "latitude": float(el["lat"]),
                "longitude": float(el["lon"]),
            }
    except Exception as e:
        logger.debug(f"Viewbox geocode failed for '{place_name}': {e}")
    return None


def geocode_place(
    place_name: str,
    near_city: str = "",
    dest_lat: Optional[float] = None,
    dest_lon: Optional[float] = None,
) -> Optional[dict]:
    """Geocodes a place name using a 3-tier fallback strategy.

    Tier 1 — Exact query:  "{name}, {destination}"
    Tier 2 — Region query: "{name}, Kerala, India"
    Tier 3 — Viewbox bias: Nominatim search centred on dest coordinates

    Args:
        place_name: Name of the place (e.g., "Eravikulam National Park").
        near_city:  Destination city to bias the search (e.g., "Munnar").
        dest_lat:   Resolved latitude of the destination (enables Tier 3).
        dest_lon:   Resolved longitude of the destination (enables Tier 3).

    Returns:
        Dict with keys: name, latitude, longitude — or None if all tiers fail.
    """
    # Tier 1: exact destination-scoped query
    queries_tier1 = [
        f"{place_name}, {near_city}" if near_city else place_name,
        place_name,
    ]
    for q in queries_tier1:
        try:
            result = fetch_osm_data(q)
            if result and result.get("latitude") and result.get("longitude"):
                return {"name": place_name, "latitude": result["latitude"], "longitude": result["longitude"]}
        except Exception:
            pass

    # Tier 2: broader regional query (drop the specific city, use state)
    regional_queries = [
        f"{place_name}, Kerala, India",
        f"{place_name}, India",
    ]
    for q in regional_queries:
        try:
            result = fetch_osm_data(q)
            if result and result.get("latitude") and result.get("longitude"):
                logger.info(f"  ↳ Geocoded '{place_name}' via regional fallback")
                return {"name": place_name, "latitude": result["latitude"], "longitude": result["longitude"]}
        except Exception:
            pass

    # Tier 3: coordinate-biased viewbox search centred on the destination
    if dest_lat is not None and dest_lon is not None:
        result = _nominatim_viewbox_search(place_name, dest_lat, dest_lon)
        if result:
            logger.info(f"  ↳ Geocoded '{place_name}' via viewbox bias around ({dest_lat:.3f}, {dest_lon:.3f})")
            return {"name": place_name, "latitude": result["latitude"], "longitude": result["longitude"]}

    return None


def batch_geocode(
    places: list[dict],
    destination: str,
    delay: float = 0.3,
    dest_lat: Optional[float] = None,
    dest_lon: Optional[float] = None,
) -> list[dict]:
    """Geocodes a list of place dicts, adding lat/lon to each.

    Resolves the destination coordinates once (if not supplied) and passes
    them into ``geocode_place`` to enable the Tier-3 viewbox fallback.

    Args:
        places:      List of dicts, each must have a 'name' key.
        destination: City name to bias geocoding (e.g., "Munnar").
        delay:       Seconds to wait between Nominatim requests.
        dest_lat:    Pre-resolved destination latitude (optional).
        dest_lon:    Pre-resolved destination longitude (optional).

    Returns:
        A new list containing only the places that were successfully geocoded,
        each augmented with 'latitude' and 'longitude' keys.
    """
    # Resolve destination anchor once — avoids re-querying on every iteration
    if dest_lat is None or dest_lon is None:
        dest_info = resolve_destination(destination)
        if dest_info:
            dest_lat = dest_info["latitude"]
            dest_lon = dest_info["longitude"]
        else:
            logger.warning(f"batch_geocode: could not resolve destination '{destination}' — Tier 3 disabled")

    geocoded = []
    for p in places:
        name = p.get("name", "")
        if not name:
            continue

        # ── Fast path: SerpAPI already gave us coordinates ─────────────────
        if p.get("latitude") and p.get("longitude"):
            enriched = {**p}
            geocoded.append(enriched)
            logger.info(f"  ✓ Using SerpAPI coords for '{name}' → ({p['latitude']:.4f}, {p['longitude']:.4f})")
            continue

        # ── Slow path: fall back to Nominatim with 3-tier strategy ─────────
        result = geocode_place(name, near_city=destination, dest_lat=dest_lat, dest_lon=dest_lon)
        if result:
            # Sanity-check: reject if the resolved point is unreasonably far
            # from the destination anchor (catches wrong cities, e.g. Mumbai)
            if dest_lat is not None and dest_lon is not None:
                dist_km = haversine_km(dest_lat, dest_lon, result["latitude"], result["longitude"])
                if dist_km > 150:
                    logger.warning(
                        f"  ✗ Rejected geocode for '{name}' — resolved {dist_km:.0f} km away "
                        f"from {destination} (likely wrong city)"
                    )
                    continue

            enriched = {**p, "latitude": result["latitude"], "longitude": result["longitude"]}
            geocoded.append(enriched)
            logger.info(f"  ✓ Geocoded '{name}' via Nominatim → ({result['latitude']:.4f}, {result['longitude']:.4f})")
        else:
            logger.warning(f"  ✗ Could not geocode '{name}' — skipping from route")

        # Respect Nominatim's 1 req/sec rate limit (only on actual Nominatim calls)
        time.sleep(delay)

    return geocoded


# ─── Nearest-Neighbor Ordering ────────────────────────────────────────────────

def nearest_neighbor_order(
    places: list[dict], origin_lat: float, origin_lon: float
) -> list[dict]:
    """Orders places using a greedy nearest-neighbor algorithm.

    Starting from the origin coordinates, repeatedly picks the closest
    unvisited place. This produces a zigzag-free route that respects
    geographic proximity.

    Args:
        places: List of dicts with 'latitude' and 'longitude' keys.
        origin_lat: Starting point latitude.
        origin_lon: Starting point longitude.

    Returns:
        A new list with the same dicts, reordered by proximity.
    """
    if not places:
        return []

    remaining = list(places)
    ordered = []
    current_lat, current_lon = origin_lat, origin_lon

    while remaining:
        # Find the nearest unvisited place
        best_idx = 0
        best_dist = float("inf")

        for i, p in enumerate(remaining):
            dist = haversine_km(current_lat, current_lon, p["latitude"], p["longitude"])
            if dist < best_dist:
                best_dist = dist
                best_idx = i

        # Move to the nearest place
        chosen = remaining.pop(best_idx)
        ordered.append(chosen)
        current_lat = chosen["latitude"]
        current_lon = chosen["longitude"]

        logger.debug(
            f"  Route → '{chosen['name']}' (dist from prev: {best_dist:.1f} km)"
        )

    return ordered


# ─── Restaurant Interleaving ──────────────────────────────────────────────────

def _midpoint(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    """Returns the geographic midpoint between two coordinates."""
    return ((lat1 + lat2) / 2, (lon1 + lon2) / 2)


def interleave_restaurants(
    ordered_attractions: list[dict],
    restaurants: list[dict],
    slots_per_day: int,
    meal_preference: str = "fixed",
) -> list[dict]:
    """Inserts restaurants into the ordered attraction sequence at meal positions.

    Strategy:
    - For each meal slot (Breakfast, Lunch, Dinner), picks the restaurant
      nearest to the midpoint between the previous activity and the next activity.
    - Each restaurant is used at most once.
    - If meal_preference is "flexible", restaurants are placed dynamically
      based on route proximity rather than fixed time slots.

    Args:
        ordered_attractions: Pre-ordered list of attraction dicts (with lat/lon).
        restaurants: Pool of geocoded restaurant dicts (with lat/lon).
        slots_per_day: Number of activity slots per day (determines meal insertion points).
        meal_preference: "fixed" for fixed Breakfast/Lunch/Dinner times,
                         "flexible" for on-route placement.

    Returns:
        A fully interleaved list of dicts, each with an added 'category' key
        ('attraction' or 'restaurant') and a 'meal_type' key for restaurants.
    """
    if not ordered_attractions:
        return []

    # Tag all attractions with their category
    tagged_attractions = []
    for a in ordered_attractions:
        tagged_attractions.append({**a, "category": "attraction"})

    available_restaurants = list(restaurants)  # Copy so we can pop

    if not available_restaurants:
        return tagged_attractions

    # Determine meal insertion indices based on the number of attractions per day
    # For "fixed" mode: insert Breakfast before first activity, Lunch in the middle, Dinner after last
    # For "flexible" mode: insert restaurants at positions where they're closest to the route

    result = []

    if meal_preference == "flexible":
        # In flexible mode, we simply insert restaurants at the point in the
        # attraction sequence where they are geographically closest
        result = list(tagged_attractions)

        for restaurant in list(available_restaurants):
            best_pos = 0
            best_dist = float("inf")

            for i in range(len(result) + 1):
                # Calculate distance from the previous stop (or start) and next stop (or end)
                if i == 0:
                    ref_lat, ref_lon = result[0]["latitude"], result[0]["longitude"]
                elif i == len(result):
                    ref_lat, ref_lon = result[-1]["latitude"], result[-1]["longitude"]
                else:
                    ref_lat, ref_lon = _midpoint(
                        result[i - 1]["latitude"], result[i - 1]["longitude"],
                        result[i]["latitude"], result[i]["longitude"],
                    )

                dist = haversine_km(ref_lat, ref_lon, restaurant["latitude"], restaurant["longitude"])
                if dist < best_dist:
                    best_dist = dist
                    best_pos = i

            tagged_rest = {**restaurant, "category": "restaurant", "meal_type": "meal"}
            result.insert(best_pos, tagged_rest)

    else:
        # Fixed mode: split attractions into day-sized chunks and insert meals
        # at standardized positions (Breakfast → activities → Lunch → activities → Dinner)
        result = []

        for i, attr in enumerate(tagged_attractions):
            # Before the first activity of each "logical day" block → Breakfast
            if i % slots_per_day == 0 and available_restaurants:
                ref_lat, ref_lon = attr["latitude"], attr["longitude"]
                best_r = _pick_nearest_restaurant(ref_lat, ref_lon, available_restaurants)
                if best_r:
                    result.append({**best_r, "category": "restaurant", "meal_type": "Breakfast"})

            result.append(attr)

            # After the middle activity → Lunch
            if i % slots_per_day == slots_per_day // 2 and available_restaurants:
                # Midpoint between current and next attraction
                if i + 1 < len(tagged_attractions):
                    mid_lat, mid_lon = _midpoint(
                        attr["latitude"], attr["longitude"],
                        tagged_attractions[i + 1]["latitude"], tagged_attractions[i + 1]["longitude"],
                    )
                else:
                    mid_lat, mid_lon = attr["latitude"], attr["longitude"]

                best_r = _pick_nearest_restaurant(mid_lat, mid_lon, available_restaurants)
                if best_r:
                    result.append({**best_r, "category": "restaurant", "meal_type": "Lunch"})

            # After the last activity of each day block → Dinner
            if (i + 1) % slots_per_day == 0 and available_restaurants:
                ref_lat, ref_lon = attr["latitude"], attr["longitude"]
                best_r = _pick_nearest_restaurant(ref_lat, ref_lon, available_restaurants)
                if best_r:
                    result.append({**best_r, "category": "restaurant", "meal_type": "Dinner"})

        # If there are trailing attractions that didn't complete a full day block,
        # add a Dinner after the last one
        if len(tagged_attractions) % slots_per_day != 0 and available_restaurants:
            last = tagged_attractions[-1]
            best_r = _pick_nearest_restaurant(last["latitude"], last["longitude"], available_restaurants)
            if best_r:
                result.append({**best_r, "category": "restaurant", "meal_type": "Dinner"})

    return result


def _pick_nearest_restaurant(
    ref_lat: float, ref_lon: float, pool: list[dict]
) -> Optional[dict]:
    """Picks and removes the nearest restaurant from the pool.

    Returns the restaurant dict, or None if the pool is empty.
    Mutates the pool list (removes the chosen restaurant).
    """
    if not pool:
        return None

    best_idx = 0
    best_dist = float("inf")

    for i, r in enumerate(pool):
        dist = haversine_km(ref_lat, ref_lon, r["latitude"], r["longitude"])
        if dist < best_dist:
            best_dist = dist
            best_idx = i

    chosen = pool.pop(best_idx)
    logger.info(
        f"  🍽️ Picked restaurant '{chosen['name']}' ({best_dist:.1f} km from ref point)"
    )
    return chosen


# ─── Day Splitting ─────────────────────────────────────────────────────────────

def split_into_days(
    interleaved_stops: list[dict], num_days: int
) -> list[list[dict]]:
    """Splits the interleaved stop sequence into day-wise buckets.

    Distributes stops as evenly as possible across the requested number of days.

    Args:
        interleaved_stops: The fully ordered + interleaved list of stops.
        num_days: Number of days to split into.

    Returns:
        A list of lists, where each inner list is one day's stops.
    """
    if not interleaved_stops or num_days <= 0:
        return []

    total = len(interleaved_stops)
    base_size = total // num_days
    remainder = total % num_days

    days = []
    idx = 0
    for d in range(num_days):
        # Distribute remainder across the first few days
        day_size = base_size + (1 if d < remainder else 0)
        days.append(interleaved_stops[idx : idx + day_size])
        idx += day_size

    return days
