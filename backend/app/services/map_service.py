from typing import List, Dict, Any, Optional
import urllib.parse
from ..config import settings
from ..utils.logger import get_logger
from ..models.place_model import DirectionResult
from serpapi import GoogleSearch
from .cache_service import cached_serpapi_call, TTL_1H

logger = get_logger(__name__)

def compare_directions(start_addr: str, end_addr: str, travel_mode: str) -> List[DirectionResult]:
    """Queries SerpAPI Google Maps Directions and extracts comparative routes."""
    api_key = settings.SERPAPI_MAPS_KEY or settings.SERPAPI_KEY
    if not api_key:
        logger.error("Directions search error: SERPAPI_MAPS_KEY not configured")
        return []

    # Map our generic modes to SerpAPI travel_mode ints
    # 0 - Driving, 1 - Cycling, 2 - Walking, 3 - Transit, 4 - Flight, 6 - Best
    mode_mapping = {
        "driving": 0,
        "cycling": 1,
        "walking": 2,
        "transit": 3,
        "flight": 4,
        "best": 6
    }
    mode_int = mode_mapping.get(travel_mode.lower(), 6)

    params = {
        "engine": "google_maps_directions",
        "start_addr": start_addr,
        "end_addr": end_addr,
        "travel_mode": str(mode_int),
        "hl": "en",
        "gl": "us",
        "api_key": api_key,
    }

    try:
        results = cached_serpapi_call("directions", params, ttl=TTL_1H)
        
        directions_list = results.get("directions", [])
        
        # Fallback to "Best" (mode 6) if no directions found and we didn't already request Best
        if not directions_list and mode_int != 6:
            logger.info(f"No directions found for mode '{travel_mode}'. Falling back to 'Best' (mode 6).")
            params["travel_mode"] = "6"
            travel_mode = "best"
            mode_int = 6
            results = cached_serpapi_call("directions", params, ttl=TTL_1H)
            directions_list = results.get("directions", [])

        if not directions_list:
            logger.info("No directions found even after fallback.")
            return []
            
        parsed_routes = []
        for i, route in enumerate(directions_list):
            duration_str = route.get("formatted_duration", "")
            distance_str = route.get("formatted_distance", "")
            
            # Simple heuristic for price if available
            price_str = None
            
            # For transit, count steps that are actual transit (not walking)
            transfers = 0
            summary = route.get("summary", "")
            
            transit_details = []
            steps_list = []
            
            if "trip_details" in route:
                for step in route.get("trip_details", []):
                    if step.get("type") == "Transit":
                        transfers += 1
                        transit_info = step.get("transit_details", {})
                        line_name = transit_info.get("line", {}).get("name", "")
                        dep = transit_info.get("departure_stop", {}).get("name", "")
                        arr = transit_info.get("arrival_stop", {}).get("name", "")
                        if line_name:
                            transit_details.append(line_name)
                            if dep and arr:
                                steps_list.append(f"🚆 Take {line_name} from {dep} to {arr}")
                            else:
                                steps_list.append(f"🚆 Take {line_name}")
                        
                        # Extract price if present
                        if "price" in step:
                            price_str = step["price"]
                    elif step.get("type") == "Walk":
                        dur = step.get("formatted_duration", "")
                        steps_list.append(f"🚶 Walk for {dur}" if dur else "🚶 Walk")
                    elif "instructions" in step:
                        steps_list.append(step["instructions"])
            
            if not steps_list:
                steps_list.append("Follow Google Maps for step-by-step directions.")
            
            if transit_details and not summary:
                summary = " via " + ", ".join(transit_details)
            elif not summary:
                summary = f"Route {i+1}"
                
            parsed_routes.append({
                "duration_str": duration_str,
                "distance_str": distance_str,
                "transfers": transfers,
                "price": price_str,
                "summary": summary,
                "steps": steps_list,
                # Try to parse duration to seconds for sorting
                "duration_seconds": route.get("duration", 0),
            })
            
        if not parsed_routes:
            return []

        results_out = []
        
        # Build base google maps URL
        encoded_start = urllib.parse.quote(start_addr)
        encoded_end = urllib.parse.quote(end_addr)
        gmaps_url = f"https://www.google.com/maps/dir/?api=1&origin={encoded_start}&destination={encoded_end}&travelmode={travel_mode}"
        
        # Fastest
        parsed_routes.sort(key=lambda x: x["duration_seconds"])
        fastest = parsed_routes[0]
        results_out.append(DirectionResult(
            route_type="Fastest ⚡",
            mode=travel_mode.capitalize(),
            duration=fastest["duration_str"],
            distance=fastest["distance_str"],
            transfers=fastest["transfers"],
            price=fastest["price"],
            summary=fastest["summary"],
            link=gmaps_url,
            steps=fastest["steps"]
        ))
        
        # If Transit, find fewest transfers (if different from fastest)
        if mode_int == 3 and len(parsed_routes) > 1:
            parsed_routes.sort(key=lambda x: x["transfers"])
            fewest = parsed_routes[0]
            if fewest["summary"] != fastest["summary"]:
                results_out.append(DirectionResult(
                    route_type="Fewest Transfers 🚶‍♂️",
                    mode=travel_mode.capitalize(),
                    duration=fewest["duration_str"],
                    distance=fewest["distance_str"],
                    transfers=fewest["transfers"],
                    price=fewest["price"],
                    summary=fewest["summary"],
                    link=gmaps_url,
                    steps=fewest["steps"]
                ))
                
        # If there's an explicit price, find the cheapest
        routes_with_price = [r for r in parsed_routes if r["price"] is not None]
        if routes_with_price and len(parsed_routes) > 1:
            # Simple string sort for price (assuming same currency format)
            routes_with_price.sort(key=lambda x: float(''.join(c for c in x["price"] if c.isdigit() or c=='.')))
            cheapest = routes_with_price[0]
            if cheapest["summary"] != fastest["summary"] and (mode_int != 3 or cheapest["summary"] != fewest["summary"]):
                results_out.append(DirectionResult(
                    route_type="Cheapest 💵",
                    mode=travel_mode.capitalize(),
                    duration=cheapest["duration_str"],
                    distance=cheapest["distance_str"],
                    transfers=cheapest["transfers"],
                    price=cheapest["price"],
                    summary=cheapest["summary"],
                    link=gmaps_url,
                    steps=cheapest["steps"]
                ))
        
        # If we only have 1 result but there were more, just add the second one as an Alternative
        if len(results_out) == 1 and len(parsed_routes) > 1:
            alt = parsed_routes[1]
            results_out.append(DirectionResult(
                route_type="Alternative 🛣️",
                mode=travel_mode.capitalize(),
                duration=alt["duration_str"],
                distance=alt["distance_str"],
                transfers=alt["transfers"],
                price=alt["price"],
                summary=alt["summary"],
                link=gmaps_url,
                steps=alt["steps"]
            ))

        return results_out
        
    except Exception as e:
        logger.error(f"Error fetching directions: {e}", exc_info=True)
        return []
