"""
Itinerary replan service — reschedules remaining slots for the current day
when the user falls behind schedule.

Uses the same Gemini model pattern as edit_itinerary_service.py.
"""
import json
from typing import Dict, Any, List, Optional
from ..utils.logger import get_logger
from .gemini_service import model
from .routing_service import get_driving_duration_str

logger = get_logger(__name__)


async def replan_remaining_day(
    itinerary: dict,
    current_day: int,
    current_time: str,
    user_lat: float,
    user_lon: float,
    places_to_remove: Optional[List[str]] = None,
) -> dict:
    """Reschedules the remaining unvisited slots for the current day.

    Args:
        itinerary: Full itinerary dict (ItineraryResult format).
        current_day: The day_number the user is currently on.
        current_time: Current time string (e.g., "02:30 PM").
        user_lat: User's current latitude.
        user_lon: User's current longitude.
        places_to_remove: Optional list of place names the user wants to skip.

    Returns:
        Updated itinerary dict with the current day's remaining slots rescheduled.
    """
    if not itinerary or not itinerary.get("days"):
        return itinerary

    # Find the current day
    day_data = None
    day_index = -1
    for idx, day in enumerate(itinerary["days"]):
        if day.get("day_number") == current_day:
            day_data = day
            day_index = idx
            break

    if day_data is None:
        logger.warning(f"Day {current_day} not found in itinerary")
        return itinerary

    # Remove places if specified
    if places_to_remove:
        remove_set = {name.lower() for name in places_to_remove}
        day_data["slots"] = [
            slot for slot in day_data["slots"]
            if slot.get("activity_name", "").lower() not in remove_set
        ]
        logger.info(f"Removed {len(places_to_remove)} places from Day {current_day}")

    # Calculate travel times from user's current position to remaining places
    remaining_context = []
    for slot in day_data["slots"]:
        lat = slot.get("latitude")
        lon = slot.get("longitude")
        travel_str = ""
        if lat and lon:
            travel_str = get_driving_duration_str(user_lat, user_lon, lat, lon)
        remaining_context.append({
            "name": slot.get("activity_name", ""),
            "category": slot.get("category", "attraction"),
            "rating": slot.get("rating"),
            "latitude": lat,
            "longitude": lon,
            "thumbnail": slot.get("thumbnail"),
            "crowd_status": slot.get("crowd_status"),
            "travel_from_user": travel_str,
        })

    prompt = f"""You are an expert travel planner. The traveler is BEHIND SCHEDULE on Day {current_day} of their trip.

CURRENT SITUATION:
- Current time: {current_time}
- User's current location: ({user_lat:.4f}, {user_lon:.4f})
- Destination: {itinerary.get('destination', '')}

REMAINING PLACES TO VISIT TODAY (with travel time from user's current location):
{json.dumps(remaining_context, indent=2)}

YOUR TASK:
1. Create a realistic RESCHEDULED plan for the remaining places, starting from {current_time}
2. Account for travel times between places (use the travel_from_user for the first place, then estimate between subsequent places)
3. Keep meal slots (Breakfast/Lunch/Dinner) at reasonable times
4. If it's too late for some activities (e.g., attractions close by 6 PM), note this in the description
5. End the day with dinner and hotel as usual
6. PRESERVE all metadata (latitude, longitude, thumbnail, crowd_status, rating) from the original slots

Return ONLY the updated "slots" array as JSON — a list of slot objects with this exact structure:
[
  {{
    "time_slot": "Afternoon",
    "time_label": "{current_time}",
    "activity_name": "Name",
    "description": "Rescheduled description noting the late start",
    "duration_minutes": 90,
    "cost_estimate": "₹500",
    "category": "attraction",
    "rating": 4.5,
    "travel_to_next": "🚗 15 mins drive",
    "latitude": 10.0,
    "longitude": 76.0,
    "thumbnail": "url_or_null",
    "crowd_status": "status_or_null"
  }}
]

RULES:
- Start from {current_time}, not from morning
- Be realistic about what can be accomplished in the remaining daylight
- Keep the same places in the same geographic order (they're already optimized)
- Update time_labels to reflect the new schedule
- Return ONLY valid JSON array, no markdown"""

    try:
        response = await model.generate_content_async(
            prompt,
            generation_config={"response_mime_type": "application/json"},
        )
        decoder = json.JSONDecoder()
        new_slots, _ = decoder.raw_decode(response.text.strip())

        if isinstance(new_slots, list):
            # Update the day's slots in the itinerary
            itinerary["days"][day_index]["slots"] = new_slots
            logger.info(
                f"Successfully replanned Day {current_day}: "
                f"{len(new_slots)} slots starting from {current_time}"
            )
        else:
            logger.error("Replan returned non-list response")

    except Exception as e:
        logger.error(f"Failed to replan Day {current_day}: {e}", exc_info=True)

    return itinerary
