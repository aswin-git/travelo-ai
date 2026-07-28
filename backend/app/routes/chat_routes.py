# chat_routes.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.place_model import (
    ChatRequest, ChatResponse, PlaceResponse, HotelResult, Hotel,
    ReviewSummary, Attraction, AttractionResult, Restaurant, RestaurantResult,
    Event, EventResult, SimilarPlacesRequest, EditItineraryRequest, ItineraryResult
)
from ..services.graph_orchestrator import run_travel_graph, run_travel_graph_stream
from ..services.review_service import get_and_summarize_reviews, save_summary_to_db
from ..services.place_service import get_place_by_name
from ..services.edit_itinerary_service import get_similar_places, insert_places_into_itinerary
from ..services.route_geometry_service import get_route_geometry
from ..services.replan_service import replan_remaining_day
from ..auth.dependencies import get_optional_user
from ..models.user_model import User
from ..utils.logger import get_logger
from pydantic import BaseModel as _BaseModel
from typing import List as _List, Optional as _Optional
import json as _json


class RouteGeometryRequest(_BaseModel):
    waypoints: _List[dict]  # List of {"lat": float, "lon": float}


class ReplanRequest(_BaseModel):
    itinerary_data: dict
    current_day: int
    current_time: str
    user_lat: float
    user_lon: float
    places_to_remove: _Optional[_List[str]] = None

logger = get_logger(__name__)

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "healthy"}


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_optional_user),
):
    """Main chat endpoint — delegates all orchestration to the LangGraph travel agent."""
    logger.info(f"Incoming chat request: {request.message}")
    try:
        result = await run_travel_graph(request, db, user=user)

        # Build ChatResponse from graph output, filtering to valid fields only
        response_fields = {
            k: v for k, v in result.items() if k in ChatResponse.model_fields
        }
        return ChatResponse(**response_fields)

    except Exception as e:
        logger.error(f"Unhandled error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/chat/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_optional_user),
):
    """SSE streaming chat endpoint — streams AI text tokens in real-time.
    
    Emits SSE events:
        event: token   → {"text": "chunk..."}
        event: done    → {full response JSON with structured data}
        event: error   → {"message": "..."}
    """
    logger.info(f"Incoming stream request: {request.message}")

    async def sse_generator():
        try:
            async for event in run_travel_graph_stream(request, db, user=user):
                event_type = event.get("event", "token")
                data = _json.dumps(event.get("data", {}), default=str)
                yield f"event: {event_type}\ndata: {data}\n\n"
        except Exception as e:
            logger.error(f"SSE stream error: {e}", exc_info=True)
            error_data = _json.dumps({"message": "Stream error"})
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/itinerary/search-similar")
async def search_similar_endpoint(request: SimilarPlacesRequest):
    try:
        results = await get_similar_places(request.destination, request.query)
        return results
    except Exception as e:
        logger.error(f"Error in search_similar_endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error searching similar places")

@router.post("/itinerary/edit", response_model=ItineraryResult)
async def edit_itinerary_endpoint(request: EditItineraryRequest):
    try:
        updated_itinerary = await insert_places_into_itinerary(
            request.existing_itinerary.model_dump(),
            request.added_places
        )
        return ItineraryResult(**updated_itinerary)
    except Exception as e:
        logger.error(f"Error in edit_itinerary_endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error editing itinerary")


@router.post("/itinerary/route-geometry")
async def route_geometry_endpoint(request: RouteGeometryRequest):
    """Returns OSRM-decoded polyline coordinates for rendering on a map."""
    try:
        geometry = get_route_geometry(request.waypoints)
        if geometry:
            return {"coordinates": geometry}
        return {"coordinates": []}
    except Exception as e:
        logger.error(f"Error fetching route geometry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching route geometry")


@router.post("/itinerary/replan")
async def replan_endpoint(request: ReplanRequest):
    """Replans the remaining slots for the current day when user is behind schedule."""
    try:
        updated = await replan_remaining_day(
            itinerary=request.itinerary_data,
            current_day=request.current_day,
            current_time=request.current_time,
            user_lat=request.user_lat,
            user_lon=request.user_lon,
            places_to_remove=request.places_to_remove,
        )
        return updated
    except Exception as e:
        logger.error(f"Error replanning itinerary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error replanning itinerary")


# FIX 3: Changed from POST to GET — this is a read-only fetch operation
@router.get("/place/search", response_model=PlaceResponse)
def search_place_endpoint(place_name: str, db: Session = Depends(get_db)):
    place = get_place_by_name(db, place_name)
    if not place:
        raise HTTPException(status_code=404, detail="Place not found in local DB")
    return PlaceResponse.model_validate(place)


@router.post("/chat/summarize-hotel", response_model=ChatResponse)
async def summarize_hotel_endpoint(hotel_name: str, property_token: str, db: Session = Depends(get_db)):
    try:
        logger.info(f"Checking cache for hotel: {hotel_name} (token: {property_token[:15]}...)")

        hotel = db.query(Hotel).filter(Hotel.property_token == property_token).first()
        if hotel:
            logger.info(f"Hotel found in DB (ID: {hotel.id}). Checking for saved summary...")
            cached = db.query(ReviewSummary).filter(
                ReviewSummary.subject_id == hotel.id,
                ReviewSummary.subject_type == "hotel"
            ).first()
            if cached:
                logger.info(f"CACHE HIT: Returning saved summary for {hotel_name}")
                return ChatResponse(response=cached.summary, source="local_db_cache")
            else:
                logger.info("CACHE MISS: No saved summary found for this hotel record.")
        else:
            logger.warning(f"CACHE MISS: Hotel '{hotel_name}' not found in DB yet.")

        summary = await get_and_summarize_reviews(hotel_name, hotel_token=property_token)

        if hotel:
            save_summary_to_db(db, hotel.id, "hotel", summary)

        return ChatResponse(response=summary, source="google_hotels_reviews")

    except Exception as e:
        # FIX 4: Replace print() with structured logging
        logger.error(f"Error summarizing hotel reviews for '{hotel_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error summarizing reviews")


@router.post("/chat/summarize-place", response_model=ChatResponse)
async def summarize_place_endpoint(place_name: str, db: Session = Depends(get_db)):
    try:
        place = get_place_by_name(db, place_name)
        if place:
            cached = db.query(ReviewSummary).filter(
                ReviewSummary.subject_id == place.id,
                ReviewSummary.subject_type == "place"
            ).first()
            if cached:
                logger.info(f"Returning cached summary for place: {place_name}")
                return ChatResponse(response=cached.summary, source="local_db_cache")

        summary = await get_and_summarize_reviews(place_name)

        if place:
            save_summary_to_db(db, place.id, "place", summary)

        return ChatResponse(response=summary, source="google_maps_reviews")

    except Exception as e:
        # FIX 4: Replace print() with structured logging
        logger.error(f"Error summarizing place reviews for '{place_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error summarizing reviews")


@router.post("/chat/summarize-attraction", response_model=ChatResponse)
async def summarize_attraction_endpoint(attraction_name: str, data_id: str, db: Session = Depends(get_db)):
    try:
        logger.info(f"Checking cache for attraction: {attraction_name} (data_id: {data_id})")

        attraction = db.query(Attraction).filter(Attraction.data_id == data_id).first()
        if attraction:
            logger.info(f"Attraction found in DB (ID: {attraction.id}). Checking for saved summary...")
            cached = db.query(ReviewSummary).filter(
                ReviewSummary.subject_id == attraction.id,
                ReviewSummary.subject_type == "attraction"
            ).first()
            if cached:
                logger.info(f"CACHE HIT: Returning saved summary for {attraction_name}")
                return ChatResponse(response=cached.summary, source="local_db_cache")
            else:
                logger.info("CACHE MISS: No saved summary found for this attraction record.")
        else:
            logger.warning(f"CACHE MISS: Attraction '{attraction_name}' not found in DB yet.")

        summary = await get_and_summarize_reviews(attraction_name, data_id=data_id)

        if attraction:
            save_summary_to_db(db, attraction.id, "attraction", summary)

        return ChatResponse(response=summary, source="google_maps_reviews")

    except Exception as e:
        logger.error(f"Error summarizing attraction reviews for '{attraction_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error summarizing reviews")


@router.post("/chat/summarize-restaurant", response_model=ChatResponse)
async def summarize_restaurant_endpoint(restaurant_name: str, data_id: str, db: Session = Depends(get_db)):
    try:
        logger.info(f"Checking cache for restaurant: {restaurant_name} (data_id: {data_id})")

        restaurant = db.query(Restaurant).filter(Restaurant.data_id == data_id).first()
        if restaurant:
            logger.info(f"Restaurant found in DB (ID: {restaurant.id}). Checking for saved summary...")
            cached = db.query(ReviewSummary).filter(
                ReviewSummary.subject_id == restaurant.id,
                ReviewSummary.subject_type == "restaurant"
            ).first()
            if cached:
                logger.info(f"CACHE HIT: Returning saved summary for {restaurant_name}")
                return ChatResponse(response=cached.summary, source="local_db_cache")
            else:
                logger.info("CACHE MISS: No saved summary found for this restaurant record.")
        else:
            logger.warning(f"CACHE MISS: Restaurant '{restaurant_name}' not found in DB yet.")

        summary = await get_and_summarize_reviews(restaurant_name, restaurant_data_id=data_id)

        if restaurant:
            save_summary_to_db(db, restaurant.id, "restaurant", summary)

        return ChatResponse(response=summary, source="google_maps_reviews")

    except Exception as e:
        logger.error(f"Error summarizing restaurant reviews for '{restaurant_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error summarizing reviews")