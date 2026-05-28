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
    destination: Optional[str]
    hotel_name: Optional[str]
    place_type: str
    check_in: Optional[str]
    check_out: Optional[str]

    # ── Response outputs (built by handler nodes) ───────────────────────────
    response_text: str
    source: str
    place_info: Optional[Any]
    hotels: Optional[list]
    attractions: Optional[list]
    restaurants: Optional[list]
    events: Optional[list]
    show_review_prompt: bool
    show_attractions_prompt: bool
    show_restaurants_prompt: bool
    show_events_prompt: bool
    error: Optional[str]

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
        "show_review_prompt": False,
        "show_attractions_prompt": False,
        "show_restaurants_prompt": False,
        "show_events_prompt": False,
        "error": None,
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
    - "hotel_search" (user asking for general hotels/accommodation in a city)
    - "specific_hotel_info" (user asking about a specific hotel by name)
    - "nearby_attractions" (user asking to see nearby places, top sights, or attractions for a city)
    - "restaurant_search" (user asking for places to eat, restaurants, or food in a city)
    - "event_search" (user asking for things happening, events, concerts, or festivals in a city)
    - "place_info" (user asking about a tourist place, destination, weather, things to do)
- "destination": the city or place name mentioned, or resolved from conversation history (or null)
- "hotel_name": the specific hotel name if mentioned (or null)
- "place_type": one of ["city", "poi"] - "city" if it's a broad region/town (e.g. Kochi, Bangalore), "poi" if it's a specific point of interest (e.g. Fort Kochi Beach).
- "check_in": check-in date in YYYY-MM-DD format if mentioned (or null)
- "check_out": check-out date in YYYY-MM-DD format if mentioned (or null)
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
    destination = parsed.get("destination")
    hotel_name = parsed.get("hotel_name")
    place_type = parsed.get("place_type", "poi")

    logger.info(
        f"Detected intent: {intent}, Destination: {destination}, "
        f"Hotel: {hotel_name}, Place Type: {place_type}, Full parsed: {parsed}"
    )

    if not destination and not hotel_name:
        logger.warning("No destination or hotel detected in user message")
        return {
            "error": "I'm a travel assistant. Please ask me about a specific destination or hotel!",
            "source": "system",
        }

    return {
        "intent": intent,
        "destination": destination,
        "hotel_name": hotel_name,
        "place_type": place_type,
        "check_in": parsed.get("check_in"),
        "check_out": parsed.get("check_out"),
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
    restaurants_data = search_restaurants(destination)

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
    message = state["message"]
    destination = state.get("destination", "")
    place_type = state.get("place_type", "poi")

    history = state.get("conversation_history")
    result = await process_chat_query(db, message, destination)

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
#  NODE: save_response  (runs last — appends assistant response to history)
# ═══════════════════════════════════════════════════════════════════════════
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
    # If classify_intent set an error, skip to save_response (still save to history)
    if state.get("error"):
        return "save_response"

    intent = state.get("intent", "place_info")

    route_map = {
        "specific_hotel_info": "handle_specific_hotel",
        "hotel_search": "handle_hotel_search",
        "nearby_attractions": "handle_attractions",
        "restaurant_search": "handle_restaurants",
        "event_search": "handle_events",
        "place_info": "handle_place_info",
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
    graph.add_edge("save_response", END)

    # Compile with MemorySaver for multi-turn conversation memory
    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


# Compiled graph with checkpointer — ready to invoke
travel_graph = _build_travel_graph()


# ═══════════════════════════════════════════════════════════════════════════
#  PUBLIC ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════
async def run_travel_graph(message: str, db: Session, session_id: str = None) -> dict:
    """
    Runs the LangGraph travel agent for a single user message.

    Args:
        message: The user's chat message.
        db: SQLAlchemy database session.
        session_id: Optional session identifier for multi-turn memory.
                    Maps to LangGraph's thread_id. If None, a unique
                    one-off session is created.

    Returns:
        A dict whose keys match ChatResponse fields (response, source, etc.).
    """
    thread_id = session_id or uuid4().hex
    config = {"configurable": {"thread_id": thread_id, "db": db}}

    initial_state: TravelState = {
        "message": message,
    }

    logger.info(f"Running travel graph with thread_id={thread_id}")
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
        "show_review_prompt",
        "show_attractions_prompt",
        "show_restaurants_prompt",
        "show_events_prompt",
    ):
        if result.get(key) is not None:
            output[key] = result[key]

    return output
