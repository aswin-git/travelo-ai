# graph_orchestrator.py
"""
LangGraph-based travel assistant orchestrator.

Replaces the monolithic if/elif routing in chat_routes.py with a StateGraph
that models the pipeline as explicit, composable nodes and conditional edges:

    manage_history → classify_intent → route → [handlers] → save_response → END

Uses LangGraph's MemorySaver checkpointer for multi-turn conversation memory,
keyed by session_id (mapped to LangGraph's thread_id).
"""

import json
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langchain_core.runnables import RunnableConfig
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing_extensions import TypedDict

from ..models.place_model import (
    Attraction,
    AttractionResult,
    Event,
    EventResult,
    Hotel,
    HotelResult,
    PlaceResponse,
    Restaurant,
    RestaurantResult,
    ReviewSummary,
    ItineraryResult,
    ItineraryDay,
    ItinerarySlot,
)
from ..services.gemini_service import chat_with_context, model
from ..services.place_service import create_place, get_place_by_name
from ..services.rag_service import process_chat_query
from ..utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Similarity threshold for fuzzy hotel name matching (same as before)
# ---------------------------------------------------------------------------
HOTEL_NAME_SIMILARITY_THRESHOLD = 0.4


# ----------------------------- ----------------------------------------------
# State schema — flows through every node in the graph
# ---------------------------------------------------------------------------
# Maximum number of history messages to include in LLM prompts
MAX_HISTORY_MESSAGES = 20  # 10 exchanges (user + assistant)


class TravelState(TypedDict, total=False):
    # ── Inputs ──────────────────────────────────────────────────────────────
    message: str
    # NOTE: db (SQLAlchemy Session) is passed via config["configurable"]["db"],
    # NOT in state, because the checkpointer cannot serialize Session objects.

    # ── Conversation memory ─────────────────────────────────────────────────
    conversation_history: list  # list of {"role": str, "content": str} dicts

    # ── Intent classification outputs ───────────────────────────────────────
    intent: str
    forced_intent: Optional[str]
    destination: Optional[str]
    hotel_name: Optional[str]
    place_type: str
    check_in: Optional[str]
    check_out: Optional[str]
    effective_query: Optional[str]  # Reconstructed query from corrections/follow-ups

    # ── Response outputs (built by handler nodes) ───────────────────────────
    response_text: str
    source: str
    place_info: Optional[Any]
    hotels: Optional[list]
    attractions: Optional[list]
    restaurants: Optional[list]
    events: Optional[list]
    directions: Optional[list]
    show_review_prompt: bool
    show_attractions_prompt: bool
    show_restaurants_prompt: bool
    show_events_prompt: bool
    error: Optional[str]
    missing_info: Optional[list]
    budget: Optional[int]
    traveler_type: Optional[str]
    cuisine: Optional[str]
    adults: Optional[int]
    start_location: Optional[str]
    end_location: Optional[str]
    travel_mode: Optional[str]
    num_days: Optional[int]
    pacing: Optional[str]
    itinerary: Optional[dict]
    meal_preference: Optional[str]
    crowd_aware: Optional[bool]
    crowd_precision: Optional[str]  # "precise" or "approximate"

    # ── Internal routing flag ───────────────────────────────────────────────
    _hotel_found: bool  # used by handle_specific_hotel → fallback logic


# ═══════════════════════════════════════════════════════════════════════════
#  HELPER: format conversation history for LLM prompts
# ═══════════════════════════════════════════════════════════════════════════
def _format_history(history: list, max_messages: int = MAX_HISTORY_MESSAGES) -> str:
    """Formats conversation history into a string for LLM prompt injection."""
    if not history:
        return ""
    recent = history[-max_messages:]
    lines = []
    for h in recent:
        role_label = "User" if h["role"] == "user" else "Assistant"
        lines.append(f"{role_label}: {h['content']}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  NODE: manage_history  (runs first — appends current user message)
# ═══════════════════════════════════════════════════════════════════════════
async def manage_history(state: TravelState) -> dict:
    """Appends the current user message to conversation history and clears stale response keys."""
    history = list(state.get("conversation_history") or [])
    history.append({"role": "user", "content": state["message"]})
    logger.info(f"Conversation history now has {len(history)} messages")
    return {
        "conversation_history": history,
        "place_info": None,
        "hotels": None,
        "attractions": None,
        "restaurants": None,
        "events": None,
        "directions": None,
        "itinerary": None,
        "show_review_prompt": False,
        "show_attractions_prompt": False,
        "show_restaurants_prompt": False,
        "show_events_prompt": False,
        "missing_info": None,
        "error": None,
        "response_text": "",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  NODE: classify_intent
# ═══════════════════════════════════════════════════════════════════════════
async def classify_intent(state: TravelState) -> dict:
    """Calls Gemini structured output to detect intent and extract entities.
    
    Includes conversation history so the LLM can resolve references like
    'there', 'that city', 'the same place', etc.
    """
    message = state["message"]
    forced_intent = state.get("forced_intent")

    # If an intent is forced (e.g. via UI button), skip the LLM extraction
    if forced_intent:
        logger.info(f"Skipping LLM classification, forced intent: {forced_intent}")
        parsed = {
            "intent": forced_intent,
            "destination": state.get("destination"),
            "hotel_name": state.get("hotel_name"),
            "place_type": "city"
        }
    else:
        history = state.get("conversation_history") or []
        logger.info("Detecting intent and extracting info using Gemini...")

        # Build history context for coreference resolution
        history_block = ""
        if len(history) > 1:  # More than just the current message
            history_text = _format_history(history[:-1])  # Exclude current msg (it's in the prompt)
            history_block = f"""\nPrevious conversation for context (use this to resolve references like 'there', 'that place', etc.):
{history_text}
"""

        intent_prompt = f"""Analyze the user's travel-related message and return a JSON object with these fields:
- "intent": one of:
    - "general_chat" (greetings like hi/hello/hey, small talk, thank you, goodbye, how are you, or any casual non-travel-specific conversation)
    - "clarify" (USE THIS when the user's message is AMBIGUOUS or COMPLEX and could map to multiple intents. For example: "I want to explore Kochi" could mean place_info, hotel_search, itinerary, or attractions. "Help me with my trip to Goa" could be itinerary, hotels, or place_info. When unsure, ASK the user what they want instead of guessing wrong. Also use this when user says just "yes", "no", "ok", "sure" etc. WITHOUT clear context from conversation history about what they're confirming)
    - "travel_question" (user asking a SPECIFIC QUESTION about travel — feasibility, logistics, safety, language, duration, transport mode, budget estimates, best season, visa, packing tips, or any yes/no/how/can-I type question about a trip or destination. Examples: "can I complete Maharashtra in 2 weeks on a bike?", "is Ladakh safe for solo female travelers?", "what language do they speak in Goa?", "how many days do I need for Kerala?", "is monsoon a good time to visit Munnar?", "can I do Rajasthan on a budget of 20k?")
    - "hotel_search" (user asking for general hotels/accommodation in a city)
    - "specific_hotel_info" (user asking about a specific hotel by name)
    - "attraction_search" (user asking to see nearby places, top sights, or attractions for a city)
    - "restaurant_search" (user asking for places to eat, restaurants, or food in a city)
    - "event_search" (user asking for things happening, events, concerts, or festivals in a city)
    - "place_info" (user asking BROADLY about a tourist place — "tell me about X", "I want to visit X", or wanting a general overview/summary of a destination. This is NOT for specific questions — use travel_question for those)
    - "destination_discovery" (user describing their preferences/vibes without naming a specific destination, e.g. 'I want to go to a beach with cliffs')
    - "directions_search" (user asking for map directions, routes, or how to get from one place to another)
    - "itinerary_search" (user EXPLICITLY asking to plan, generate, or create a multi-day travel itinerary, trip plan, or schedule. Must use words like 'plan', 'itinerary', 'schedule', 'create a trip'. Do NOT use this for questions about trip feasibility or duration — use travel_question for those)
- "clarify_question": (ONLY when intent is "clarify") A friendly question asking the user what they'd like to do. Include specific options. Example: "I'd love to help with Kochi! Would you like me to: 🏨 Search for hotels, 🏛️ Show top attractions, 🍽️ Find restaurants, 🗺️ Plan a full itinerary, or ℹ️ Tell you about the destination?"
- "destination": the city or place name mentioned, or resolved from conversation history (or null)
- "hotel_name": the specific hotel name if mentioned (or null)
- "place_type": one of ["city", "poi"] - "city" if it's a broad region/town (e.g. Kochi, Bangalore), "poi" if it's a specific point of interest (e.g. Fort Kochi Beach).
- "check_in": check-in date in YYYY-MM-DD format if mentioned (or null)
- "check_out": check-out date in YYYY-MM-DD format if mentioned (or null)
- "budget": total budget in numbers if mentioned (or null)
- "traveler_type": one of ["solo", "couple", "family", "business", "budget"] if mentioned (or null)
- "adults": number of adults if mentioned (or null)
- "cuisine": type of food or cuisine requested if mentioned (or null)
- "start_location": starting location for directions if mentioned (or null)
- "end_location": ending location for directions if mentioned (or null)
- "travel_mode": one of ["driving", "transit", "walking", "flight"] if mentioned (or null)
- "num_days": number of days for itinerary if mentioned (or null)
- "pacing": one of ["relaxed", "packed"] if mentioned or inferred (or null)
- "meal_preference": one of ["fixed", "flexible"] if mentioned (or null). "fixed" means meals at standard Breakfast/Lunch/Dinner times, "flexible" means restaurants placed dynamically on the route
- "crowd_aware": true if user mentions wanting to avoid crowds, crowd-aware planning, less crowded spots, or quiet places (or null)
- "effective_query": the FULL reconstructed question the user is really asking. This is CRITICAL for corrections and follow-ups:
    - If user says "i mean kochi" after asking "is kooch good for tamil speakers?", effective_query = "is kochi a good place for tamil speaking people?"
    - If user says "what about hotels there?" after discussing Paris, effective_query = "what about hotels in Paris?"
    - If user message is already a complete question, effective_query = the user message as-is (with typos corrected)
    - ALWAYS produce a complete, self-contained question that makes sense without conversation history

CRITICAL — ANSWERING FOLLOW-UP QUESTIONS:
When the assistant previously asked the user for specific information (like a destination, dates, preferences, etc.) and the user's current message answers that question:
1. Look at the PREVIOUS conversation to find what the assistant asked for
2. INHERIT the intent from the original request that triggered the assistant's question
3. Use the user's answer to fill in the missing information
Examples:
- User said "hotels" → Assistant asked "which destination?" → User says "kochi" → intent = "hotel_search", destination = "Kochi"
- User said "restaurants" → Assistant asked "which city?" → User says "mumbai" → intent = "restaurant_search", destination = "Mumbai"
- User said "plan a trip" → Assistant asked "where?" → User says "goa" → intent = "itinerary_search", destination = "Goa"
- Assistant offered clarify options (hotels/attractions/etc.) → User says "hotels" → intent = "hotel_search" with the destination from context
Do NOT use "clarify" when the user is clearly answering a question the assistant just asked.

CRITICAL — CONFIRMATIONS (yes/no/ok/sure):
When the user says "yes", "sure", "ok", "yeah", "do it", "go ahead", etc.:
1. Look at the PREVIOUS conversation to find the assistant's last question or suggestion
2. If the assistant asked "Would you like me to search for hotels?", then intent = "hotel_search"
3. If the assistant offered multiple options and user picked one (e.g. "hotels"), map to that intent
4. If there's NO clear previous question to confirm, use intent = "clarify" and ask what they want

CRITICAL — CORRECTIONS & FOLLOW-UPS:
When the user says things like "i mean X", "sorry, I meant X", "no, X", or corrects a typo/name from a previous message:
1. Look at the PREVIOUS conversation to find the original question
2. Set "intent" to match the ORIGINAL question's intent (not "place_info" by default)
3. Set "destination" to the CORRECTED place name
4. Set "effective_query" to the original question with the corrected entity swapped in
Do NOT treat corrections as a brand new generic query about the place.

CRITICAL — WHEN TO USE "clarify":
- Message could reasonably map to 2+ different intents and you're not 80%+ confident
- User mentions a destination but doesn't specify what they want (e.g. "Kochi", "help me with Goa", "I'm going to Mumbai next week") AND there is NO prior intent in the conversation history to inherit
- User says "yes"/"no"/"ok" but there's no clear previous question in conversation history
- DO NOT use clarify for clear-cut requests like "hotels in Delhi", "tell me about Jaipur", "plan a 3-day trip to Kerala"
- DO NOT use clarify when the user is answering a follow-up question from the assistant (inherit the original intent instead)

Also handle TYPOS intelligently: if user writes "kooch" but likely means "Kochi", or "bnaglore" for "Bangalore", resolve to the correct spelling.
{history_block}
User message: {message}"""

        extraction_response = model.generate_content(
            intent_prompt,
            generation_config={"response_mime_type": "application/json"},
        )

        try:
            parsed = json.loads(extraction_response.text)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Failed to parse Gemini structured output: {e}", exc_info=True)
            return {
                "error": "Sorry, I had trouble understanding your request. Could you rephrase it?",
                "source": "system",
            }

    intent = parsed.get("intent", "place_info")
    destination = parsed.get("destination") or state.get("destination")
    hotel_name = parsed.get("hotel_name") or state.get("hotel_name")
    place_type = parsed.get("place_type", "poi")

    logger.info(
        f"Detected intent: {intent}, Destination: {destination}, "
        f"Hotel: {hotel_name}, Place Type: {place_type}, Full parsed: {parsed}"
    )

    # Handle clarify intent — return the clarifying question as the response
    if intent == "clarify":
        clarify_q = parsed.get("clarify_question") or (
            f"I'd love to help with {destination or 'your trip'}! What would you like me to do? "
            "🏨 Search for hotels, 🏛️ Show attractions, 🍽️ Find restaurants, "
            "🗺️ Plan an itinerary, or ℹ️ Tell you about the destination?"
        )
        logger.info(f"Clarify intent — asking user: {clarify_q}")
        return {
            "intent": "clarify",
            "response_text": clarify_q,
            "source": "clarify",
            "destination": destination,
        }

    # Remove the strict error block for missing destination here. We will handle it via missing_info.
    requires_dest = ["hotel_search", "restaurant_search", "attraction_search", "event_search", "itinerary_search", "place_info"]

    budget = parsed.get("budget") or state.get("budget")
    traveler_type = parsed.get("traveler_type") or state.get("traveler_type")
    cuisine = parsed.get("cuisine") or state.get("cuisine")
    adults = parsed.get("adults") or state.get("adults")
    check_in = parsed.get("check_in") or state.get("check_in")
    check_out = parsed.get("check_out") or state.get("check_out")
    start_location = parsed.get("start_location") or state.get("start_location")
    end_location = parsed.get("end_location") or state.get("end_location")
    travel_mode = parsed.get("travel_mode") or state.get("travel_mode")
    num_days = parsed.get("num_days") or state.get("num_days")
    pacing = parsed.get("pacing") or state.get("pacing")
    meal_preference = parsed.get("meal_preference") or state.get("meal_preference")
    crowd_aware = parsed.get("crowd_aware") if parsed.get("crowd_aware") is not None else state.get("crowd_aware")
    crowd_precision = state.get("crowd_precision")  # Only set via frontend form

    logger.info(
        f"Resolved Context -> Intent: {intent}, Dest: {destination}, Budget: {budget}, "
        f"Traveler: {traveler_type}, Dates: {check_in} to {check_out}, "
        f"Route: {start_location} to {end_location} ({travel_mode})"
    )

    # Missing info logic
    missing_info = []
    if intent == "hotel_search":
        if not check_in: missing_info.append("dates")
        if not traveler_type: missing_info.append("traveler_type")
        if not budget: missing_info.append("budget")
    elif intent == "restaurant_search":
        if not cuisine: missing_info.append("cuisine")
    elif intent == "directions_search":
        if not start_location: missing_info.append("start_location")
        if not end_location: missing_info.append("end_location")
        if not travel_mode: missing_info.append("travel_mode")
    elif intent == "itinerary_search":
        if not num_days: missing_info.append("num_days")
        if not pacing: missing_info.append("pacing")
        if not start_location: missing_info.append("itinerary_start_location")
        if not meal_preference: missing_info.append("meal_preference")
        if crowd_aware is None: missing_info.append("crowd_aware")

    if intent in requires_dest and not destination and not hotel_name:
        missing_info.insert(0, "destination")

    if missing_info:
        logger.info(f"Missing info for {intent}: {missing_info}")
        return {
            "error": "I need a few more details to find the best options for you.",
            "source": "system",
            "missing_info": missing_info,
            "intent": intent,
            "destination": destination,
            "start_location": start_location,
            "end_location": end_location,
            "travel_mode": travel_mode,
            "num_days": num_days,
            "pacing": pacing,
            "meal_preference": meal_preference,
        }

    effective_query = parsed.get("effective_query") or message
    logger.info(f"Effective query: {effective_query}")

    return {
        "intent": intent,
        "destination": destination,
        "hotel_name": hotel_name,
        "place_type": place_type,
        "check_in": check_in,
        "check_out": check_out,
        "budget": budget,
        "traveler_type": traveler_type,
        "cuisine": cuisine,
        "adults": adults,
        "start_location": start_location,
        "end_location": end_location,
        "travel_mode": travel_mode,
        "num_days": num_days,
        "pacing": pacing,
        "missing_info": None,
        "meal_preference": meal_preference,
        "effective_query": effective_query,
        "crowd_aware": crowd_aware,
        "crowd_precision": crowd_precision,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  NODE: handle_specific_hotel
# ═══════════════════════════════════════════════════════════════════════════
async def handle_specific_hotel(state: TravelState, config: RunnableConfig) -> dict:
    """Looks up a specific hotel by name (fuzzy match) and builds a contextual response."""
    db: Session = config["configurable"]["db"]
    hotel_name = state.get("hotel_name", "")
    message = state["message"]

    hotel = (
        db.query(Hotel)
        .filter(
            func.similarity(func.lower(Hotel.name), hotel_name.lower())
            > HOTEL_NAME_SIMILARITY_THRESHOLD
        )
        .order_by(
            func.similarity(func.lower(Hotel.name), hotel_name.lower()).desc()
        )
        .first()
    )

    if hotel:
        summary_record = (
            db.query(ReviewSummary)
            .filter(
                ReviewSummary.subject_id == hotel.id,
                ReviewSummary.subject_type == "hotel",
            )
            .first()
        )

        context = (
            f"Hotel Name: {hotel.name}\n"
            f"Price: {hotel.price}\n"
            f"Rating: {hotel.rating}\n"
            f"Description: {hotel.description}\n"
        )
        if summary_record:
            context += f"User Experience Summary: {summary_record.summary}"

        bot_response = await chat_with_context(
            message, context, history=state.get("conversation_history")
        )
        return {
            "response_text": bot_response,
            "source": "local_db_context",
            "hotels": [
                HotelResult(
                    name=hotel.name,
                    price=hotel.price,
                    rating=hotel.rating,
                    reviews=hotel.reviews_count,
                    description=hotel.description,
                    link=hotel.link,
                    thumbnail=hotel.thumbnail,
                    property_token=hotel.property_token,
                ).model_dump()
            ],
            "_hotel_found": True,
        }

    # Hotel not found — signal fallback to hotel_search
    logger.info(f"Hotel '{hotel_name}' not found in DB. Falling back to hotel_search.")
    destination = state.get("destination") or hotel_name
    return {
        "_hotel_found": False,
        "destination": destination,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  NODE: handle_hotel_search
# ═══════════════════════════════════════════════════════════════════════════
async def handle_hotel_search(state: TravelState, config: RunnableConfig) -> dict:
    """Searches for hotels via cache or SerpAPI and returns results."""
    from ..services.hotel_service import save_hotels_to_db, search_hotels

    db: Session = config["configurable"]["db"]
    destination = state.get("destination", "")

    place = get_place_by_name(db, destination)
    if place:
        cached_hotels = db.query(Hotel).filter(Hotel.place_id == place.id).all()
        if cached_hotels:
            last_updated = cached_hotels[0].updated_at or cached_hotels[0].created_at
            if datetime.utcnow() - last_updated < timedelta(days=2):
                logger.info(
                    f"CACHE HIT: Using cached hotels for {destination} "
                    f"(last updated {last_updated})"
                )
                hotel_results = [
                    HotelResult(
                        name=h.name,
                        price=h.price,
                        rating=h.rating,
                        reviews=h.reviews_count,
                        description=h.description,
                        link=h.link,
                        thumbnail=h.thumbnail,
                        property_token=h.property_token,
                    ).model_dump()
                    for h in cached_hotels
                ]
                return {
                    "response_text": f"Here are the top hotels in {destination} from my records! 🏨",
                    "source": "local_db_cache",
                    "hotels": hotel_results,
                }

    # Cache miss or stale: fetch fresh from SerpAPI
    logger.info(f"CACHE MISS/STALE: Fetching fresh hotel data for {destination}")
    hotels_data = search_hotels(
        destination=destination,
        check_in=state.get("check_in"),
        check_out=state.get("check_out"),
        adults=state.get("adults") or 2,
        budget=state.get("budget"),
        traveler_type=state.get("traveler_type")
    )

    if hotels_data:
        if not place:
            try:
                place = create_place(db, {"name": destination, "source": "hotel_search"})
                logger.info(f"Created placeholder place record for {destination}")
            except Exception as e:
                logger.error(
                    f"Failed to create place record for {destination}: {e}",
                    exc_info=True,
                )

        if place:
            save_hotels_to_db(db, hotels_data, place.id)
            logger.info(f"Saved/Updated {len(hotels_data)} hotels for {destination}.")

        hotel_results = [HotelResult(**h).model_dump() for h in hotels_data]
        return {
            "response_text": f"Here are the latest hotels I found in {destination}! 🏨",
            "source": "google_hotels",
            "hotels": hotel_results,
        }

    return {
        "response_text": (
            f"I couldn't find hotel listings for {destination} right now. "
            "Please make sure the SERPAPI_KEY is configured."
        ),
        "source": "google_hotels",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  NODE: handle_attractions
# ═══════════════════════════════════════════════════════════════════════════
async def handle_attractions(state: TravelState, config: RunnableConfig) -> dict:
    """Searches for nearby attractions via cache or SerpAPI."""
    from ..services.attraction_service import save_attractions_to_db, search_attractions

    db: Session = config["configurable"]["db"]
    destination = state.get("destination") or state["message"]

    place = get_place_by_name(db, destination)
    if place:
        cached = db.query(Attraction).filter(Attraction.place_id == place.id).all()
        if cached:
            last_updated = cached[0].updated_at or cached[0].created_at
            if datetime.utcnow() - last_updated < timedelta(days=2):
                logger.info(f"CACHE HIT: Using cached attractions for {destination}")
                attr_results = [
                    AttractionResult(
                        name=a.name,
                        rating=a.rating,
                        reviews=a.reviews_count,
                        description=a.description,
                        thumbnail=a.thumbnail,
                        data_id=a.data_id,
                    ).model_dump()
                    for a in cached
                ]
                return {
                    "response_text": f"Here are the top attractions in {destination}! 🏛️",
                    "source": "local_db_cache",
                    "attractions": attr_results,
                }

    # Cache miss or stale
    logger.info(f"CACHE MISS/STALE: Fetching fresh attractions for {destination}")
    attractions_data = search_attractions(destination)

    if attractions_data:
        if not place:
            try:
                place = create_place(db, {"name": destination, "source": "attractions_search"})
                logger.info(f"Created placeholder place record for {destination}")
            except Exception as e:
                logger.error(
                    f"Failed to create place record for {destination}: {e}",
                    exc_info=True,
                )

        if place:
            save_attractions_to_db(db, attractions_data, place.id)
            logger.info(f"Saved/Updated {len(attractions_data)} attractions for {destination}.")

        attr_results = [AttractionResult(**a).model_dump() for a in attractions_data]
        return {
            "response_text": f"Here are the top attractions I found in {destination}! 🏛️",
            "source": "google_maps",
            "attractions": attr_results,
        }

    return {
        "response_text": f"I couldn't find attractions for {destination} right now.",
        "source": "google_maps",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  NODE: handle_restaurants
# ═══════════════════════════════════════════════════════════════════════════
async def handle_restaurants(state: TravelState, config: RunnableConfig) -> dict:
    """Searches for restaurants via cache or SerpAPI."""
    from ..services.restaurant_service import save_restaurants_to_db, search_restaurants

    db: Session = config["configurable"]["db"]
    destination = state.get("destination") or state["message"]

    place = get_place_by_name(db, destination)
    if place:
        cached = db.query(Restaurant).filter(Restaurant.place_id == place.id).all()
        if cached:
            last_updated = cached[0].updated_at or cached[0].created_at
            if datetime.utcnow() - last_updated < timedelta(days=2):
                logger.info(f"CACHE HIT: Using cached restaurants for {destination}")
                rest_results = [
                    RestaurantResult(
                        name=r.name,
                        rating=r.rating,
                        reviews=r.reviews_count,
                        description=r.description,
                        thumbnail=r.thumbnail,
                        data_id=r.data_id,
                        price_level=r.price_level,
                    ).model_dump()
                    for r in cached
                ]
                return {
                    "response_text": f"Here are some top restaurants in {destination}! 🍽️",
                    "source": "local_db_cache",
                    "restaurants": rest_results,
                }

    # Cache miss or stale
    logger.info(f"CACHE MISS/STALE: Fetching fresh restaurants for {destination}")
    restaurants_data = search_restaurants(destination, cuisine=state.get("cuisine"))

    if restaurants_data:
        if not place:
            try:
                place = create_place(db, {"name": destination, "source": "restaurant_search"})
                logger.info(f"Created placeholder place record for {destination}")
            except Exception as e:
                logger.error(
                    f"Failed to create place record for {destination}: {e}",
                    exc_info=True,
                )

        if place:
            save_restaurants_to_db(db, restaurants_data, place.id)
            logger.info(f"Saved/Updated {len(restaurants_data)} restaurants for {destination}.")

        rest_results = [RestaurantResult(**r).model_dump() for r in restaurants_data]
        return {
            "response_text": f"Here are the top restaurants I found in {destination}! 🍽️",
            "source": "google_maps",
            "restaurants": rest_results,
        }

    return {
        "response_text": f"I couldn't find restaurants for {destination} right now.",
        "source": "google_maps",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  NODE: handle_events
# ═══════════════════════════════════════════════════════════════════════════
async def handle_events(state: TravelState, config: RunnableConfig) -> dict:
    """Searches for events via cache or SerpAPI."""
    from ..services.event_service import save_events_to_db, search_events

    db: Session = config["configurable"]["db"]
    destination = state.get("destination") or state["message"]

    place = get_place_by_name(db, destination)
    if place:
        cached = db.query(Event).filter(Event.place_id == place.id).all()
        if cached:
            last_updated = cached[0].updated_at or cached[0].created_at
            if datetime.utcnow() - last_updated < timedelta(days=2):
                logger.info(f"CACHE HIT: Using cached events for {destination}")
                event_results = [
                    EventResult(
                        title=e.title,
                        date_string=e.date_string,
                        address=e.address,
                        link=e.link,
                        description=e.description,
                        thumbnail=e.thumbnail,
                        venue_name=e.venue_name,
                    ).model_dump()
                    for e in cached
                ]
                return {
                    "response_text": f"Here are some upcoming events in {destination}! 📅",
                    "source": "local_db_cache",
                    "events": event_results,
                }

    # Cache miss or stale
    logger.info(f"CACHE MISS/STALE: Fetching fresh events for {destination}")
    events_data = search_events(destination)

    if events_data:
        if not place:
            try:
                place = create_place(db, {"name": destination, "source": "event_search"})
                logger.info(f"Created placeholder place record for {destination}")
            except Exception as e:
                logger.error(
                    f"Failed to create place record for {destination}: {e}",
                    exc_info=True,
                )

        if place:
            save_events_to_db(db, events_data, place.id)
            logger.info(f"Saved/Updated {len(events_data)} events for {destination}.")

        event_results = [EventResult(**e).model_dump() for e in events_data]
        return {
            "response_text": f"Here are the top events I found in {destination}! 📅",
            "source": "google_events",
            "events": event_results,
        }

    return {
        "response_text": f"I couldn't find events for {destination} right now.",
        "source": "google_events",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  NODE: handle_place_info
# ═══════════════════════════════════════════════════════════════════════════
async def handle_place_info(state: TravelState, config: RunnableConfig) -> dict:
    """Delegates to the existing RAG pipeline for place information."""
    db: Session = config["configurable"]["db"]
    destination = state.get("destination", "")
    place_type = state.get("place_type", "poi")
    history = state.get("conversation_history")

    # Use effective_query (reconstructed from corrections/follow-ups) if available,
    # otherwise fall back to raw message
    effective_query = state.get("effective_query") or state["message"]
    logger.info(f"handle_place_info using effective_query: {effective_query}")

    result = await process_chat_query(db, effective_query, destination, history=history)

    place_info = None
    if result.get("place_info"):
        try:
            place_info = PlaceResponse.model_validate(result["place_info"]).model_dump()
        except Exception as e:
            logger.error(f"Failed to validate place_info: {e}", exc_info=True)

    has_place = place_info is not None

    return {
        "response_text": result["response"],
        "source": result["source"],
        "place_info": place_info,
        "show_review_prompt": has_place and place_type == "poi",
        "show_attractions_prompt": has_place and place_type == "city",
        "show_restaurants_prompt": has_place and place_type == "city",
        "show_events_prompt": has_place and place_type == "city",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  NODE: handle_travel_question
# ═══════════════════════════════════════════════════════════════════════════
async def handle_travel_question(state: TravelState, config: RunnableConfig) -> dict:
    """Handles direct travel questions (feasibility, logistics, tips, etc.)
    by fetching relevant context and answering the specific question."""
    db: Session = config["configurable"]["db"]
    destination = state.get("destination", "")
    history = state.get("conversation_history")
    effective_query = state.get("effective_query") or state["message"]
    logger.info(f"handle_travel_question: {effective_query} (destination: {destination})")

    # Fetch RAG context if we have a destination
    rag_context = ""
    if destination:
        try:
            rag_result = await process_chat_query(db, effective_query, destination, history=history)
            if rag_result.get("response"):
                rag_context = rag_result["response"][:2000]
        except Exception as e:
            logger.warning(f"RAG context fetch failed for travel question: {e}")

    history_block = ""
    if history and len(history) > 1:
        history_text = _format_history(history[:-1])
        history_block = f"\nPrevious conversation:\n{history_text}\n"

    question_prompt = f"""You are Travelo AI, an expert travel assistant. The user is asking a SPECIFIC QUESTION about travel.

Your job is to ANSWER THE QUESTION DIRECTLY. Do NOT generate an itinerary. Do NOT give a generic overview of the destination. Focus ONLY on answering what the user asked.

RULES:
- Answer the user's specific question concisely and helpfully
- Use bullet points (- ) for easy scanning
- Use **bold** for key facts
- If the answer is yes/no, lead with a clear yes or no, then explain
- Include practical tips and specifics (distances, durations, costs, seasons, etc.)
- If you're unsure, say so honestly rather than making things up
- Keep the response focused — don't add unrelated tourist info
- Use a relevant emoji header (e.g. 🏍️ Bike Trip, ⏱️ Duration, 💰 Budget, 🛡️ Safety)
{history_block}
Background context about the destination (use ONLY if relevant to answering the question):
{rag_context if rag_context else 'No specific context available — use your general knowledge.'}

User's question: {effective_query}"""

    try:
        response = await model.generate_content_async(question_prompt)
        return {
            "response_text": response.text.strip(),
            "source": "travel_question",
        }
    except Exception as e:
        logger.error(f"Travel question response failed: {e}", exc_info=True)
        return {
            "response_text": "I'm sorry, I had trouble answering your question. Could you rephrase it?",
            "source": "travel_question",
        }


# ═══════════════════════════════════════════════════════════════════════════
#  NODE: handle_destination_discovery
# ═══════════════════════════════════════════════════════════════════════════
async def handle_destination_discovery(state: TravelState, config: RunnableConfig) -> dict:
    """Delegates to RAG service for semantic search and recommendation."""
    from ..services.rag_service import semantic_place_discovery
    
    message = state["message"]
    response = await semantic_place_discovery(message)
    
    return {
        "response_text": response,
        "source": "semantic_discovery"
    }


# ═══════════════════════════════════════════════════════════════════════════
#  NODE: handle_general_chat
# ═══════════════════════════════════════════════════════════════════════════
async def handle_general_chat(state: TravelState) -> dict:
    """Handles greetings, small talk, thank-yous, and other non-travel queries
    with a friendly, travel-assistant persona response."""
    message = state["message"]
    history = state.get("conversation_history") or []
    history_text = _format_history(history[:-1]) if len(history) > 1 else ""

    history_block = f"Previous conversation:\n{history_text}\n" if history_text else ""

    chat_prompt = f"""You are Travelo AI, a friendly and enthusiastic travel assistant.
Respond naturally to the user's message in a warm, conversational tone.
Keep your response concise (1-3 sentences).
If they greet you, greet them back and let them know you can help with:
- Exploring destinations and places
- Finding hotels, restaurants, and attractions
- Planning travel itineraries
- Getting directions between places

Do NOT make up travel information. Just be friendly and helpful.

{history_block}User message: {message}"""

    try:
        response = model.generate_content(chat_prompt)
        return {
            "response_text": response.text.strip(),
            "source": "general_chat",
        }
    except Exception as e:
        logger.error(f"General chat response failed: {e}", exc_info=True)
        return {
            "response_text": "Hey there! 👋 I'm your travel assistant. Ask me about any destination, hotel, or trip you're planning!",
            "source": "general_chat",
        }


# ═══════════════════════════════════════════════════════════════════════════
#  NODE: handle_directions
# ═══════════════════════════════════════════════════════════════════════════
async def handle_directions(state: TravelState, config: RunnableConfig) -> dict:
    """Fetches and compares directions using map_service."""
    from ..services.map_service import compare_directions
    
    start_location = state.get("start_location")
    end_location = state.get("end_location")
    travel_mode = state.get("travel_mode")

    logger.info(f"Fetching directions from {start_location} to {end_location} via {travel_mode}")
    directions_data = compare_directions(start_location, end_location, travel_mode)

    if directions_data:
        return {
            "response_text": f"Here are the best ways to get from {start_location} to {end_location}! 🗺️",
            "source": "google_maps_directions",
            "directions": [d.model_dump() for d in directions_data],
        }

    return {
        "response_text": f"I couldn't find any routes from {start_location} to {end_location} right now.",
        "source": "google_maps_directions",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  NODE: handle_itinerary
# ═══════════════════════════════════════════════════════════════════════════
async def handle_itinerary(state: TravelState, config: RunnableConfig) -> dict:
    """Generates a geo-optimized multi-day travel itinerary.

    Pipeline:
    1. Fetch attractions + restaurants via SerpAPI (or cache)
    2. Geocode all candidates + origin via Nominatim
    3. Order attractions using nearest-neighbor from origin
    4. Interleave restaurants at meal slots by proximity
    5. Split into days and send pre-ordered sequence to Gemini
       (Gemini only writes descriptions/timing, NOT the ordering)
    """
    from ..services.attraction_service import search_attractions
    from ..services.restaurant_service import search_restaurants
    from ..services.geo_routing_service import (
        batch_geocode,
        geocode_place,
        haversine_km,
        interleave_restaurants,
        nearest_neighbor_order,
        resolve_destination,
        split_into_days,
    )

    db: Session = config["configurable"]["db"]
    user_id = config["configurable"].get("user_id")
    destination = state.get("destination", "")
    num_days = state.get("num_days", 3)
    pacing = state.get("pacing", "relaxed")
    budget = state.get("budget")
    traveler_type = state.get("traveler_type")
    start_location = state.get("start_location")
    crowd_aware = state.get("crowd_aware", False)
    crowd_precision = state.get("crowd_precision", "approximate")
    meal_preference = state.get("meal_preference", "fixed")

    logger.info(
        f"Generating geo-optimized {num_days}-day {pacing} itinerary for {destination}"
        f" (origin: {start_location or 'destination center'}, meals: {meal_preference},"
        f" crowd_aware: {crowd_aware}, precision: {crowd_precision})"
    )

    # ── Phase 0: Fetch user's saved items for this destination ──────────────
    from ..models.user_model import SavedItem

    saved_attractions = []
    saved_restaurants = []
    saved_events = []
    saved_hotels = []

    if user_id:
        try:
            user_saved = (
                db.query(SavedItem)
                .filter(
                    SavedItem.user_id == user_id,
                    SavedItem.destination.ilike(f"%{destination}%"),
                )
                .all()
            )
            for si in user_saved:
                item = {"name": si.item_name, "pinned_day": si.pinned_day, **(si.item_data or {})}
                if si.item_type == "attraction":
                    saved_attractions.append(item)
                elif si.item_type == "restaurant":
                    saved_restaurants.append(item)
                elif si.item_type == "event":
                    saved_events.append(item)
                elif si.item_type == "hotel":
                    saved_hotels.append(item)
            logger.info(
                f"User saved items for {destination}: "
                f"{len(saved_attractions)} attractions, {len(saved_restaurants)} restaurants, "
                f"{len(saved_events)} events, {len(saved_hotels)} hotels"
            )
        except Exception as e:
            logger.warning(f"Failed to fetch saved items: {e}")

    # ── Phase 1: Fetch candidate places (PARALLEL) ──────────────────────────
    import asyncio

    loop = asyncio.get_event_loop()
    attractions_future = loop.run_in_executor(None, lambda: search_attractions(destination) or [])
    restaurants_future = loop.run_in_executor(None, lambda: search_restaurants(destination) or [])

    try:
        attractions_raw, restaurants_raw = await asyncio.gather(
            attractions_future, restaurants_future
        )
    except Exception as e:
        logger.warning(f"Parallel fetch failed, falling back: {e}")
        attractions_raw = []
        restaurants_raw = []

    logger.info(f"Fetched {len(attractions_raw)} attractions + {len(restaurants_raw)} restaurants for {destination} (parallel)")

    # Inject saved attractions/restaurants into candidate pools (at front, so they're prioritized)
    saved_attr_names = {a["name"].lower() for a in saved_attractions}
    saved_rest_names = {r["name"].lower() for r in saved_restaurants}

    for sa in saved_attractions:
        if not any(a.get("name", "").lower() == sa["name"].lower() for a in attractions_raw):
            attractions_raw.insert(0, sa)
            logger.info(f"Injected saved attraction '{sa['name']}' into candidates")

    for sr in saved_restaurants:
        if not any(r.get("name", "").lower() == sr["name"].lower() for r in restaurants_raw):
            restaurants_raw.insert(0, sr)
            logger.info(f"Injected saved restaurant '{sr['name']}' into candidates")

    # ── Phase 2: Geocode everything ────────────────────────────────────────
    # Resolve the destination ONCE — this gives us lat/lon for the Tier-3
    # viewbox fallback used inside batch_geocode and geocode_place.
    dest_anchor = resolve_destination(destination)
    dest_lat = dest_anchor["latitude"] if dest_anchor else None
    dest_lon = dest_anchor["longitude"] if dest_anchor else None

    logger.info("Geocoding attractions + restaurants (parallel)...")
    geo_attr_future = loop.run_in_executor(
        None, lambda: batch_geocode(attractions_raw[:10], destination, dest_lat=dest_lat, dest_lon=dest_lon)
    )
    geo_rest_future = loop.run_in_executor(
        None, lambda: batch_geocode(restaurants_raw[:8], destination, dest_lat=dest_lat, dest_lon=dest_lon)
    )
    geocoded_attractions, geocoded_restaurants = await asyncio.gather(
        geo_attr_future, geo_rest_future
    )
    logger.info(f"Geocoded {len(geocoded_attractions)} attractions + {len(geocoded_restaurants)} restaurants")

    # Geocode the origin (user's starting location or destination center)
    # Handle the __skip__ sentinel from the frontend's Skip button
    if start_location == "__skip__":
        start_location = None
    origin_coords = None
    if start_location:
        origin_result = geocode_place(start_location, dest_lat=dest_lat, dest_lon=dest_lon)
        if origin_result:
            origin_coords = (origin_result["latitude"], origin_result["longitude"])
            logger.info(f"Origin '{start_location}' → ({origin_coords[0]:.4f}, {origin_coords[1]:.4f})")

    if not origin_coords:
        # Fallback: use the destination anchor we already resolved
        if dest_lat and dest_lon:
            origin_coords = (dest_lat, dest_lon)
            logger.info(f"Using resolved destination center as origin → ({dest_lat:.4f}, {dest_lon:.4f})")
        elif geocoded_attractions:
            # Last resort: use the first attraction's coordinates
            origin_coords = (geocoded_attractions[0]["latitude"], geocoded_attractions[0]["longitude"])

    # ── Phase 3: Nearest-neighbor ordering ─────────────────────────────────
    if origin_coords and geocoded_attractions:
        logger.info("Running nearest-neighbor ordering from origin...")
        ordered_attractions = nearest_neighbor_order(
            geocoded_attractions, origin_coords[0], origin_coords[1]
        )
    else:
        ordered_attractions = geocoded_attractions

    # ── Phase 4: Interleave restaurants ────────────────────────────────────
    slots_per_day = 3 if pacing == "relaxed" else 5
    if ordered_attractions and geocoded_restaurants:
        logger.info(f"Interleaving restaurants (mode: {meal_preference})...")
        interleaved = interleave_restaurants(
            ordered_attractions,
            geocoded_restaurants,
            slots_per_day=slots_per_day,
            meal_preference=meal_preference,
        )
    else:
        # No restaurants geocoded — just tag attractions
        interleaved = [{**a, "category": "attraction"} for a in ordered_attractions]

    # ── Phase 4.5: Fetch crowd data (if crowd_aware + precise) ─────────────
    crowd_data = {}
    if crowd_aware and crowd_precision == "precise":
        from ..services.crowd_service import batch_fetch_crowd_data
        # Build list of places with data_id for crowd lookup
        crowd_candidates = []
        for item in interleaved:
            if item.get("data_id"):
                crowd_candidates.append(item)
        if crowd_candidates:
            logger.info(f"Fetching precise crowd data for {len(crowd_candidates)} places...")
            crowd_data = batch_fetch_crowd_data(crowd_candidates)
            logger.info(f"Got crowd data for {len(crowd_data)} places")

    # ── Phase 5: Split into days ───────────────────────────────────────────
    days_split = split_into_days(interleaved, num_days)

    # ── Phase 6: Build pre-ordered context for Gemini ──────────────────────
    # Gemini's job is now ONLY to add descriptions, timing, and cost — NOT to reorder
    day_blocks = []
    for day_idx, day_stops in enumerate(days_split, 1):
        stop_lines = []
        for stop_idx, stop in enumerate(day_stops, 1):
            cat = stop.get("category", "attraction")
            meal_type = stop.get("meal_type", "")
            name = stop.get("name", "Unknown")
            rating = stop.get("rating", "N/A")
            desc = stop.get("description", "")[:100]
            lat = stop.get("latitude", 0)
            lon = stop.get("longitude", 0)

            # Append crowd info if available (precise mode)
            crowd_tag = ""
            if crowd_aware and name in crowd_data:
                cd = crowd_data[name]
                crowd_tag = f", {cd['crowd_emoji']} {cd['crowd_label']}"

            if cat == "restaurant":
                stop_lines.append(
                    f"  {stop_idx}. [RESTAURANT — {meal_type}] {name} "
                    f"(Rating: {rating}{crowd_tag}) at ({lat:.4f}, {lon:.4f}): {desc}"
                )
            else:
                stop_lines.append(
                    f"  {stop_idx}. [ATTRACTION] {name} "
                    f"(Rating: {rating}{crowd_tag}) at ({lat:.4f}, {lon:.4f}): {desc}"
                )

        day_blocks.append(f"Day {day_idx}:\n" + "\n".join(stop_lines))

    pre_ordered_context = "\n\n".join(day_blocks)

    # Also gather RAG context for richer descriptions
    rag_context = ""
    try:
        rag_result = await process_chat_query(db, f"Tell me about {destination}", destination)
        if rag_result.get("response"):
            rag_context = f"\n\nAbout {destination}:\n{rag_result['response'][:1000]}"
    except Exception as e:
        logger.warning(f"RAG context fetch failed: {e}")

    # ── Build the Gemini prompt ────────────────────────────────────────────
    budget_hint = f"The traveler has a budget of ₹{budget}." if budget else ""
    traveler_hint = f"The traveler type is: {traveler_type}." if traveler_type else ""
    origin_hint = f"The traveler is starting from {start_location}." if start_location else ""

    # Build anchored events/items section for pinned saved items
    anchored_lines = []
    for evt in saved_events:
        if evt.get("pinned_day"):
            evt_name = evt["name"]
            evt_date = evt.get("date_string", "")
            evt_desc = evt.get("description", "")[:100]
            anchored_lines.append(
                f"- Day {evt['pinned_day']}: \"{evt_name}\" (Event"
                f"{', ' + evt_date if evt_date else ''}) — {evt_desc}"
            )
    for attr in saved_attractions:
        if attr.get("pinned_day"):
            anchored_lines.append(
                f"- Day {attr['pinned_day']}: \"{attr['name']}\" (Must-visit attraction)"
            )
    for rest in saved_restaurants:
        if rest.get("pinned_day"):
            anchored_lines.append(
                f"- Day {rest['pinned_day']}: \"{rest['name']}\" (Must-visit restaurant)"
            )
    for htl in saved_hotels:
        if htl.get("pinned_day"):
            anchored_lines.append(
                f"- Day {htl['pinned_day']}: \"{htl['name']}\" (Preferred hotel)"
            )

    anchored_section = ""
    if anchored_lines:
        anchored_section = (
            "\n\nANCHORED ITEMS (MUST be scheduled on the specified day — these are NON-NEGOTIABLE):\n"
            + "\n".join(anchored_lines)
            + "\n\nIMPORTANT: If an event is anchored to a specific day, build the REST of that day's schedule AROUND it. "
            "The anchored event takes priority — place other attractions before/after it. "
            "Use the anchored hotel as the stay for that night if one is pinned.\n"
        )

    # Build saved items hint (non-pinned but saved = user wants to include them)
    saved_hint_lines = []
    for attr in saved_attractions:
        if not attr.get("pinned_day"):
            saved_hint_lines.append(f"- {attr['name']} (attraction)")
    for rest in saved_restaurants:
        if not rest.get("pinned_day"):
            saved_hint_lines.append(f"- {rest['name']} (restaurant)")
    for evt in saved_events:
        if not evt.get("pinned_day"):
            saved_hint_lines.append(f"- {evt['name']} (event)")
    for htl in saved_hotels:
        if not htl.get("pinned_day"):
            saved_hint_lines.append(f"- {htl['name']} (hotel)")

    saved_section = ""
    if saved_hint_lines:
        saved_section = (
            "\n\nUSER'S SAVED ITEMS (try to include these in the itinerary when possible):\n"
            + "\n".join(saved_hint_lines) + "\n"
        )

    # Build crowd awareness hint for prompt
    crowd_hint = ""
    if crowd_aware:
        if crowd_precision == "precise":
            crowd_hint = (
                "\nCROWD AWARENESS (ENABLED — Precise Mode):\n"
                "Crowd data tags are included next to each stop above (🟢 Not Crowded / 🟡 Moderately Crowded / 🔴 Very Crowded / ⚪ Unknown).\n"
                "For each slot in the itinerary, you MUST include a \"crowd_status\" field with the crowd label.\n"
                "If crowd data shows a place is Very Crowded, mention it in the description and suggest visiting early or late.\n"
            )
        else:
            crowd_hint = (
                "\nCROWD AWARENESS (ENABLED — Approximate Mode):\n"
                "Based on the type of attraction, its popularity (rating + reviews), the day of week, and time of visit, "
                "estimate how crowded each place is likely to be.\n"
                "For each slot, include a \"crowd_status\" field with one of: \"Not Crowded\", \"Moderately Crowded\", \"Very Crowded\".\n"
                "Use your knowledge of tourism patterns: temples/markets are crowded on weekends, "
                "beaches peak around sunset, museums are quieter on weekdays mornings, etc.\n"
            )

    # Pre-compute crowd status example value for JSON template
    crowd_status_example = '"Not Crowded"' if crowd_aware else 'null'
    crowd_rule = (
        'crowd_status is REQUIRED for every slot when crowd awareness is enabled '
        '— use the crowd tags from the route data or estimate based on place type and time'
    ) if crowd_aware else 'crowd_status should be null for all slots'

    itinerary_prompt = f"""You are an expert travel planner building a detailed, realistic {num_days}-day itinerary for {destination}.
{origin_hint}
{budget_hint}
{traveler_hint}
{crowd_hint}
{anchored_section}{saved_section}
I have pre-ordered the attractions and restaurants below by geographic proximity using nearest-neighbor routing. DO NOT reorder them.

Your job is ONLY to:
1. Slot each pre-ordered stop into a proper daily schedule with realistic time labels
2. Fill in ALL THREE meals (Breakfast, Lunch, Dinner) for every day — use the [RESTAURANT] stops from the route for one meal slot, and invent a realistic local restaurant name for the remaining meals
3. Add a hotel/accommodation recommendation at the END of each day (category: "hotel")
4. Write vivid 1-2 sentence descriptions
5. Estimate realistic duration_minutes for each stop
6. Add travel_to_next times between consecutive stops

SCHEDULING RULES (strictly enforced):
- Day start: 08:00 AM with Breakfast (30-45 min)
- Morning attractions: 09:00 AM – 12:30 PM (each attraction 90-120 min)
- Lunch: 12:30 PM – 01:30 PM (at a nearby restaurant, 60 min)
- Afternoon attractions: 02:00 PM – 05:30 PM (each attraction 90-120 min)
- Evening/Dinner: 07:00 PM – 08:30 PM (90 min)
- Hotel check-in: 09:00 PM (category: "hotel", duration_minutes: 0)
- Activities must run BACK-TO-BACK with only travel gaps — do NOT leave hours between them

PRE-ORDERED ROUTE:

{pre_ordered_context}
{rag_context}

Return a JSON object with this EXACT structure:
{{
  "destination": "{destination}",
  "total_days": {num_days},
  "pacing": "{pacing}",
  "start_location": {json.dumps(start_location)},
  "meal_preference": "{meal_preference}",
  "days": [
    {{
      "day_number": 1,
      "theme": "A short catchy theme for the day",
      "slots": [
        {{
          "time_slot": "Breakfast",
          "time_label": "08:00 AM",
          "activity_name": "Name of breakfast restaurant",
          "description": "A vivid 1-2 sentence description",
          "duration_minutes": 45,
          "cost_estimate": "₹200",
          "category": "restaurant",
          "meal_type": "Breakfast",
          "rating": null,
          "travel_to_next": "🚶 5 mins walk",
          "latitude": null,
          "longitude": null,
          "crowd_status": null
        }},
        {{
          "time_slot": "Morning",
          "time_label": "09:00 AM",
          "activity_name": "EXACT attraction name from route",
          "description": "A vivid 1-2 sentence description",
          "duration_minutes": 120,
          "cost_estimate": "₹500",
          "category": "attraction",
          "meal_type": null,
          "rating": 4.5,
          "travel_to_next": "🚗 15 mins drive",
          "latitude": 10.0870,
          "longitude": 77.0601,
          "crowd_status": {crowd_status_example}
        }},
        {{
          "time_slot": "Lunch",
          "time_label": "12:30 PM",
          "activity_name": "Name of lunch restaurant",
          "description": "Description",
          "duration_minutes": 60,
          "cost_estimate": "₹400",
          "category": "restaurant",
          "meal_type": "Lunch",
          "rating": null,
          "travel_to_next": "🚗 10 mins drive",
          "latitude": null,
          "longitude": null,
          "crowd_status": null
        }},
        {{
          "time_slot": "Dinner",
          "time_label": "07:00 PM",
          "activity_name": "Name of dinner restaurant",
          "description": "Description",
          "duration_minutes": 90,
          "cost_estimate": "₹600",
          "category": "restaurant",
          "meal_type": "Dinner",
          "rating": null,
          "travel_to_next": "🚶 5 mins walk",
          "latitude": null,
          "longitude": null,
          "crowd_status": null
        }},
        {{
          "time_slot": "Night",
          "time_label": "09:00 PM",
          "activity_name": "Name of hotel or resort in {destination}",
          "description": "Settle in for the night at this comfortable property.",
          "duration_minutes": 0,
          "cost_estimate": "₹3000",
          "category": "hotel",
          "meal_type": null,
          "rating": null,
          "travel_to_next": null,
          "latitude": null,
          "longitude": null,
          "crowd_status": null
        }}
      ]
    }}
  ]
}}

CRITICAL RULES:
- Every day MUST have exactly: Breakfast + at least 2 attractions + Lunch + at least 1 afternoon attraction + Dinner + Hotel
- Use [ATTRACTION] names EXACTLY as given in the pre-ordered route
- Use [RESTAURANT] stops from the route for ONE of Breakfast/Lunch/Dinner — use their provided lat/lon
- Invent realistic local restaurant names for the other two meal slots (set latitude/longitude to null)
- Hotel entry is REQUIRED at the end of every day — suggest a real well-known hotel/resort in {destination}
- time_slot must be one of: "Breakfast", "Morning", "Lunch", "Afternoon", "Evening", "Dinner", "Night"
- category must be one of: "attraction", "restaurant", "hotel"
- {crowd_rule}
- Return ONLY valid JSON, no markdown"""

    try:
        response = model.generate_content(
            itinerary_prompt,
            generation_config={"response_mime_type": "application/json"},
        )
        text = response.text.strip()
        decoder = json.JSONDecoder()
        raw, _ = decoder.raw_decode(text)

        # Validate with Pydantic
        itinerary = ItineraryResult(**raw)
        logger.info(f"Successfully generated {itinerary.total_days}-day geo-optimized itinerary for {destination}")

        return {
            "response_text": f"Here's your {num_days}-day {pacing} itinerary for {destination}! 🗺️✨ "
                             f"{'Starting from ' + start_location + '. ' if start_location else ''}"
                             f"All stops are optimized for minimal travel time between locations.",
            "source": "gemini_itinerary",
            "itinerary": itinerary.model_dump(),
        }
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Itinerary generation failed: {e}", exc_info=True)
        return {
            "response_text": f"I had trouble generating the itinerary for {destination}. Please try again!",
            "source": "gemini_itinerary",
        }


async def save_response(state: TravelState) -> dict:
    """Appends the assistant's response to conversation history for future turns."""
    history = list(state.get("conversation_history") or [])
    response_text = state.get("response_text") or state.get("error") or ""
    if response_text:
        history.append({"role": "assistant", "content": response_text})
    
    # Trim to prevent unbounded growth
    if len(history) > MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]
    
    logger.info(f"Saved response to history. Total messages: {len(history)}")
    return {"conversation_history": history}


# ═══════════════════════════════════════════════════════════════════════════
#  ROUTING FUNCTIONS (conditional edges)
# ═══════════════════════════════════════════════════════════════════════════
def route_by_intent(state: TravelState) -> str:
    """Routes from classify_intent to the appropriate handler node."""
    # If classify_intent set an error or a clarify response, skip to save_response
    if state.get("error") or state.get("response_text"):
        return "save_response"

    intent = state.get("intent", "place_info")

    route_map = {
        "general_chat": "handle_general_chat",
        "travel_question": "handle_travel_question",
        "specific_hotel_info": "handle_specific_hotel",
        "hotel_search": "handle_hotel_search",
        "attraction_search": "handle_attractions",
        "restaurant_search": "handle_restaurants",
        "event_search": "handle_events",
        "place_info": "handle_place_info",
        "destination_discovery": "handle_destination_discovery",
        "directions_search": "handle_directions",
        "itinerary_search": "handle_itinerary",
    }
    return route_map.get(intent, "handle_place_info")


def route_hotel_fallback(state: TravelState) -> str:
    """After handle_specific_hotel, either save_response (found) or fallback to hotel_search."""
    if state.get("_hotel_found", False):
        return "save_response"
    return "handle_hotel_search"


# ═══════════════════════════════════════════════════════════════════════════
#  GRAPH ASSEMBLY
# ═══════════════════════════════════════════════════════════════════════════
def _build_travel_graph():
    """Assembles and compiles the travel assistant StateGraph with memory."""
    graph = StateGraph(TravelState)

    # Register nodes
    graph.add_node("manage_history", manage_history)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("handle_specific_hotel", handle_specific_hotel)
    graph.add_node("handle_hotel_search", handle_hotel_search)
    graph.add_node("handle_attractions", handle_attractions)
    graph.add_node("handle_restaurants", handle_restaurants)
    graph.add_node("handle_events", handle_events)
    graph.add_node("handle_place_info", handle_place_info)
    graph.add_node("handle_destination_discovery", handle_destination_discovery)
    graph.add_node("handle_directions", handle_directions)
    graph.add_node("handle_itinerary", handle_itinerary)
    graph.add_node("handle_general_chat", handle_general_chat)
    graph.add_node("handle_travel_question", handle_travel_question)
    graph.add_node("save_response", save_response)

    # Entry: START → manage_history → classify_intent
    graph.add_edge(START, "manage_history")
    graph.add_edge("manage_history", "classify_intent")

    # Intent router (conditional edges from classify_intent)
    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "handle_specific_hotel": "handle_specific_hotel",
            "handle_hotel_search": "handle_hotel_search",
            "handle_attractions": "handle_attractions",
            "handle_restaurants": "handle_restaurants",
            "handle_events": "handle_events",
            "handle_place_info": "handle_place_info",
            "handle_destination_discovery": "handle_destination_discovery",
            "handle_directions": "handle_directions",
            "handle_itinerary": "handle_itinerary",
            "handle_general_chat": "handle_general_chat",
            "handle_travel_question": "handle_travel_question",
            "save_response": "save_response",  # error path
        },
    )

    # Specific hotel → fallback conditional edge
    graph.add_conditional_edges(
        "handle_specific_hotel",
        route_hotel_fallback,
        {
            "save_response": "save_response",
            "handle_hotel_search": "handle_hotel_search",
        },
    )

    # All handlers → save_response → END
    graph.add_edge("handle_hotel_search", "save_response")
    graph.add_edge("handle_attractions", "save_response")
    graph.add_edge("handle_restaurants", "save_response")
    graph.add_edge("handle_events", "save_response")
    graph.add_edge("handle_place_info", "save_response")
    graph.add_edge("handle_destination_discovery", "save_response")
    graph.add_edge("handle_directions", "save_response")
    graph.add_edge("handle_itinerary", "save_response")
    graph.add_edge("handle_general_chat", "save_response")
    graph.add_edge("handle_travel_question", "save_response")
    graph.add_edge("save_response", END)

    # Compile with MemorySaver for multi-turn conversation memory
    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


# Compiled graph with checkpointer — ready to invoke
travel_graph = _build_travel_graph()


# ═══════════════════════════════════════════════════════════════════════════
#  PUBLIC ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════
async def run_travel_graph(request: Any, db: Session, user: Any = None) -> dict:
    """
    Runs the LangGraph travel agent for a single user message.

    Args:
        request: The ChatRequest object containing message, budget, etc.
        db: SQLAlchemy database session.
        user: Optional authenticated user (for saved items).
    """
    thread_id = request.session_id or uuid4().hex
    user_id = str(user.id) if user else None
    config = {"configurable": {"thread_id": thread_id, "db": db, "user_id": user_id}}

    initial_state: TravelState = {
        "message": request.message,
        "forced_intent": getattr(request, "intent", None),
        "destination": getattr(request, "destination", None),
        "budget": request.budget,
        "traveler_type": request.traveler_type,
        "cuisine": request.cuisine,
        "adults": request.adults,
        "check_in": request.check_in,
        "check_out": request.check_out,
        "start_location": request.start_location,
        "end_location": request.end_location,
        "travel_mode": request.travel_mode,
        "num_days": request.num_days,
        "pacing": request.pacing,
        "meal_preference": request.meal_preference,
        "crowd_aware": request.crowd_aware,
        "crowd_precision": request.crowd_precision,
    }

    logger.info(f"Running travel graph with thread_id={thread_id}, user_id={user_id}")

    # Seed conversation_history from frontend if checkpointer has none (loaded session)
    if getattr(request, "conversation_history", None):
        try:
            saved_state = travel_graph.get_state(config)
            if not (saved_state and hasattr(saved_state, "values") and saved_state.values.get("conversation_history")):
                initial_state["conversation_history"] = request.conversation_history
                logger.info(f"Restored conversation_history from request ({len(request.conversation_history)} msgs)")
        except Exception:
            initial_state["conversation_history"] = request.conversation_history

    result = await travel_graph.ainvoke(initial_state, config)

    # Normalize: node outputs use 'response_text', but ChatResponse expects 'response'
    output = {}
    if result.get("error"):
        output["response"] = result["error"]
        output["source"] = result.get("source", "system")
    else:
        output["response"] = result.get("response_text", "")
        output["source"] = result.get("source", "unknown")

    # Pass through optional fields
    for key in (
        "place_info",
        "hotels",
        "attractions",
        "restaurants",
        "events",
        "directions",
        "itinerary",
        "show_review_prompt",
        "show_attractions_prompt",
        "show_restaurants_prompt",
        "show_events_prompt",
        "missing_info",
    ):
        if result.get(key) is not None:
            output[key] = result[key]

    return output


# ═══════════════════════════════════════════════════════════════════════════
#  PUBLIC ENTRY POINT — STREAMING (SSE)
# ═══════════════════════════════════════════════════════════════════════════
# Intents where we stream the Gemini text response token-by-token
_STREAMABLE_INTENTS = {"place_info", "travel_question", "general_chat", "destination_discovery"}

async def run_travel_graph_stream(request: Any, db: Session, user: Any = None):
    """
    SSE streaming entry point. Yields dicts for the SSE endpoint to format.

    Yields:
        {"event": "token", "data": {"text": "chunk..."}}
        {"event": "done",  "data": {full ChatResponse-like dict}}
        {"event": "error", "data": {"message": "..."}}

    For streamable intents (place_info, travel_question, general_chat, destination_discovery):
        Runs classify_intent → prepares context → streams Gemini text → emits done with metadata.
    For data-heavy intents (hotels, itinerary, etc.):
        Runs the full graph normally and emits a single done event.
    """
    from ..services.gemini_service import stream_generate, _build_chat_prompt

    thread_id = request.session_id or uuid4().hex
    user_id = str(user.id) if user else None
    config = {"configurable": {"thread_id": thread_id, "db": db, "user_id": user_id}}

    initial_state: TravelState = {
        "message": request.message,
        "forced_intent": getattr(request, "intent", None),
        "destination": getattr(request, "destination", None),
        "budget": request.budget,
        "traveler_type": request.traveler_type,
        "cuisine": request.cuisine,
        "adults": request.adults,
        "check_in": request.check_in,
        "check_out": request.check_out,
        "start_location": request.start_location,
        "end_location": request.end_location,
        "travel_mode": request.travel_mode,
        "num_days": request.num_days,
        "pacing": request.pacing,
        "meal_preference": request.meal_preference,
        "crowd_aware": request.crowd_aware,
        "crowd_precision": request.crowd_precision,
    }

    logger.info(f"[STREAM] Running with thread_id={thread_id}, user_id={user_id}")

    # ── Phase 1: Run manage_history + classify_intent to get intent ─────────
    # We manually invoke just these two nodes through a partial graph run,
    # then decide whether to stream or run the full graph.

    # Load previous state from checkpointer (since we are manually running nodes)
    try:
        saved_state = travel_graph.get_state(config)
        if saved_state and hasattr(saved_state, "values") and saved_state.values:
            for key in ["conversation_history", "destination", "hotel_name"]:
                if saved_state.values.get(key) is not None:
                    initial_state[key] = saved_state.values[key]
    except Exception as e:
        logger.warning(f"Failed to load previous state for stream: {e}")

    # If checkpointer had no conversation_history, seed from frontend (loaded session)
    if not initial_state.get("conversation_history") and getattr(request, "conversation_history", None):
        logger.info(f"[STREAM] Restoring conversation_history from request ({len(request.conversation_history)} msgs)")
        initial_state["conversation_history"] = request.conversation_history

    # Run manage_history
    history_state = initial_state.copy()
    history_result = await manage_history(history_state)
    state_after_history = {**history_state, **history_result}

    # Run classify_intent
    intent_result = await classify_intent(state_after_history)
    state_after_intent = {**state_after_history, **intent_result}

    intent = state_after_intent.get("intent", "place_info")
    logger.info(f"[STREAM] Intent: {intent}")

    # ── Helper: persist state to checkpointer on early-return paths ──────────
    def _save_checkpoint(state_dict):
        """Save state to LangGraph checkpointer so conversation history persists."""
        try:
            travel_graph.update_state(config, state_dict)
        except Exception as e:
            logger.warning(f"[STREAM] Failed to save checkpoint on early return: {e}")

    # ── Check for errors, missing info, or clarify responses from classify_intent ──
    if state_after_intent.get("error"):
        # Save history so next turn has context
        _save_checkpoint(state_after_intent)
        yield {"event": "done", "data": {
            "response": state_after_intent["error"],
            "source": state_after_intent.get("source", "system"),
            "missing_info": state_after_intent.get("missing_info"),
        }}
        return

    if state_after_intent.get("response_text") and intent == "clarify":
        # Save the clarify response to history AND persist to checkpointer
        state_after_intent["conversation_history"].append({"role": "assistant", "content": state_after_intent["response_text"]})
        _save_checkpoint(state_after_intent)
        yield {"event": "done", "data": {
            "response": state_after_intent["response_text"],
            "source": state_after_intent.get("source", "clarify"),
        }}
        return

    if state_after_intent.get("missing_info"):
        # Save history + intent so next turn knows what was being asked
        _save_checkpoint(state_after_intent)
        yield {"event": "done", "data": {
            "response": state_after_intent.get("error", "I need a few more details."),
            "source": "system",
            "missing_info": state_after_intent["missing_info"],
        }}
        return

    # ── Phase 2: Route based on intent ─────────────────────────────────────
    if intent not in _STREAMABLE_INTENTS:
        # Data-heavy intent: run full graph normally, emit done
        logger.info(f"[STREAM] Non-streamable intent '{intent}', running full graph")
        result = await travel_graph.ainvoke(initial_state, config)

        output = {}
        if result.get("error"):
            output["response"] = result["error"]
            output["source"] = result.get("source", "system")
        else:
            output["response"] = result.get("response_text", "")
            output["source"] = result.get("source", "unknown")

        for key in (
            "place_info", "hotels", "attractions", "restaurants",
            "events", "directions", "itinerary",
            "show_review_prompt", "show_attractions_prompt",
            "show_restaurants_prompt", "show_events_prompt",
            "missing_info",
        ):
            if result.get(key) is not None:
                output[key] = result[key]

        yield {"event": "done", "data": output}
        return

    # ── Phase 3: Streamable intent — prepare context, then stream ──────────
    destination = state_after_intent.get("destination", "")
    history = state_after_intent.get("conversation_history", [])
    effective_query = state_after_intent.get("effective_query") or request.message
    prompt = None
    extra_data = {}  # Non-text data to include in done event

    if intent == "place_info":
        # Fetch RAG context (non-streaming)
        rag_result = await process_chat_query(db, effective_query, destination, history=history)
        context = rag_result.get("response", "") if rag_result else ""

        if rag_result and rag_result.get("place_info"):
            try:
                place_info = PlaceResponse.model_validate(rag_result["place_info"]).model_dump()
                extra_data["place_info"] = place_info
                place_type = state_after_intent.get("place_type", "poi")
                extra_data["show_review_prompt"] = place_type == "poi"
                extra_data["show_attractions_prompt"] = place_type == "city"
                extra_data["show_restaurants_prompt"] = place_type == "city"
                extra_data["show_events_prompt"] = place_type == "city"
            except Exception:
                pass

        prompt = _build_chat_prompt(effective_query, context, history=history)

    elif intent == "travel_question":
        # Fetch RAG context
        rag_context = ""
        if destination:
            try:
                rag_result = await process_chat_query(db, effective_query, destination, history=history)
                if rag_result and rag_result.get("response"):
                    rag_context = rag_result["response"][:2000]
            except Exception as e:
                logger.warning(f"RAG context fetch failed for stream: {e}")

        history_block = ""
        if history and len(history) > 1:
            history_text = _format_history(history[:-1])
            history_block = f"\nPrevious conversation:\n{history_text}\n"

        prompt = f"""You are Travelo AI, an expert travel assistant. The user is asking a SPECIFIC QUESTION about travel.

Your job is to ANSWER THE QUESTION DIRECTLY. Do NOT generate an itinerary. Do NOT give a generic overview of the destination. Focus ONLY on answering what the user asked.

RULES:
- Answer the user's specific question concisely and helpfully
- Use bullet points (- ) for easy scanning
- Use **bold** for key facts
- If the answer is yes/no, lead with a clear yes or no, then explain
- Include practical tips and specifics (distances, durations, costs, seasons, etc.)
- If you're unsure, say so honestly rather than making things up
- Keep the response focused — don't add unrelated tourist info
- Use a relevant emoji header (e.g. 🏍️ Bike Trip, ⏱️ Duration, 💰 Budget, 🛡️ Safety)
{history_block}
Background context about the destination (use ONLY if relevant to answering the question):
{rag_context if rag_context else 'No specific context available — use your general knowledge.'}

User's question: {effective_query}"""

    elif intent == "general_chat":
        history_text = _format_history(history[:-1]) if len(history) > 1 else ""
        history_block = f"Previous conversation:\n{history_text}\n" if history_text else ""

        prompt = f"""You are Travelo AI, a friendly and enthusiastic travel assistant.
Respond naturally to the user's message in a warm, conversational tone.
Keep your response concise (1-3 sentences).
If they greet you, greet them back and let them know you can help with:
- Exploring destinations and places
- Finding hotels, restaurants, and attractions
- Planning travel itineraries
- Getting directions between places

Do NOT make up travel information. Just be friendly and helpful.

{history_block}User message: {request.message}"""

    elif intent == "destination_discovery":
        from ..services.rag_service import semantic_place_discovery
        # For discovery, run the full pipeline non-streaming (it uses JSON parsing)
        response_text = await semantic_place_discovery(request.message)
        yield {"event": "done", "data": {
            "response": response_text,
            "source": "semantic_discovery",
        }}
        return

    if not prompt:
        yield {"event": "error", "data": {"message": "Failed to build prompt."}}
        return

    # ── Phase 4: Stream Gemini tokens ──────────────────────────────────────
    full_text = ""
    async for chunk in stream_generate(prompt):
        full_text += chunk
        yield {"event": "token", "data": {"text": chunk}}

    # ── Phase 5: Update conversation history in the checkpointer ───────────
    # Append assistant response to history for multi-turn memory
    history.append({"role": "assistant", "content": full_text})
    if len(history) > MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]

    # Save state to checkpointer for multi-turn continuity
    try:
        save_state = {
            **state_after_intent,
            "conversation_history": history,
            "response_text": full_text,
        }
        # Use the official LangGraph API to update state
        travel_graph.update_state(config, save_state)
    except Exception as e:
        logger.warning(f"[STREAM] Failed to save checkpoint: {e}")

    # ── Emit done event with full response + structured data ───────────────
    done_data = {
        "response": full_text,
        "source": f"stream_{intent}",
        **extra_data,
    }
    yield {"event": "done", "data": done_data}
