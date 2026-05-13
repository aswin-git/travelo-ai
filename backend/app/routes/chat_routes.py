# chat_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models.place_model import ChatRequest, ChatResponse, PlaceResponse, HotelResult, Hotel, ReviewSummary
from ..services.rag_service import process_chat_query
from ..services.hotel_service import search_hotels, save_hotels_to_db
from ..services.place_service import get_place_by_name, create_place
from ..services.gemini_service import model, chat_with_context
from ..services.review_service import get_and_summarize_reviews, save_summary_to_db
from ..utils.logger import get_logger
import json
from datetime import datetime, timedelta

logger = get_logger(__name__)

router = APIRouter()

# FIX 5: Similarity threshold for fuzzy hotel name matching
HOTEL_NAME_SIMILARITY_THRESHOLD = 0.4


@router.get("/health")
def health_check():
    return {"status": "healthy"}


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, db: Session = Depends(get_db)):
    logger.info(f"Incoming chat request: {request.message}")
    try:
        # Step 1: Use Gemini structured output to detect intent and extract info
        # FIX 1: Use response_mime_type for reliable JSON output — no manual stripping needed
        logger.info("Detecting intent and extracting info using Gemini...")
        intent_prompt = f"""Analyze the user's travel-related message and return a JSON object with these fields:
- "intent": one of:
    - "hotel_search" (user asking for general hotels/accommodation in a city)
    - "specific_hotel_info" (user asking about a specific hotel by name)
    - "place_info" (user asking about a tourist place, destination, weather, things to do)
- "destination": the city or place name mentioned (or null)
- "hotel_name": the specific hotel name if mentioned (or null)
- "check_in": check-in date in YYYY-MM-DD format if mentioned (or null)
- "check_out": check-out date in YYYY-MM-DD format if mentioned (or null)

User message: {request.message}"""

        extraction_response = model.generate_content(
            intent_prompt,
            generation_config={"response_mime_type": "application/json"},
        )

        # FIX 1: Structured output means we get clean JSON — but still guard against model errors
        try:
            parsed = json.loads(extraction_response.text)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Failed to parse Gemini structured output: {e}", exc_info=True)
            return ChatResponse(
                response="Sorry, I had trouble understanding your request. Could you rephrase it?",
                source="system"
            )

        intent = parsed.get("intent", "place_info")
        destination = parsed.get("destination")
        hotel_name = parsed.get("hotel_name")

        logger.info(f"Detected intent: {intent}, Destination: {destination}, Hotel: {hotel_name}")

        if not destination and not hotel_name:
            logger.warning("No destination or hotel detected in user message")
            return ChatResponse(
                response="I'm a travel assistant. Please ask me about a specific destination or hotel!",
                source="system"
            )

        # Step 2: Route based on intent
        if intent == "specific_hotel_info" and hotel_name:
            # FIX 5: Use pg_trgm similarity instead of broad wildcard ilike
            # Requires: CREATE EXTENSION IF NOT EXISTS pg_trgm; in your DB
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
                summary_record = db.query(ReviewSummary).filter(
                    ReviewSummary.subject_id == hotel.id,
                    ReviewSummary.subject_type == "hotel"
                ).first()

                context = (
                    f"Hotel Name: {hotel.name}\n"
                    f"Price: {hotel.price}\n"
                    f"Rating: {hotel.rating}\n"
                    f"Description: {hotel.description}\n"
                )
                if summary_record:
                    context += f"User Experience Summary: {summary_record.summary}"

                bot_response = chat_with_context(request.message, context)
                return ChatResponse(
                    response=bot_response,
                    source="local_db_context",
                    hotels=[HotelResult(
                        name=hotel.name, price=hotel.price, rating=hotel.rating,
                        reviews=hotel.reviews_count, description=hotel.description,
                        link=hotel.link, thumbnail=hotel.thumbnail,
                        property_token=hotel.property_token
                    )]
                )
            else:
                # Fallback: treat as general hotel search
                logger.info(f"Hotel '{hotel_name}' not found in DB. Falling back to hotel_search.")
                intent = "hotel_search"
                destination = destination or hotel_name

        if intent == "hotel_search":
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
                                name=h.name, price=h.price, rating=h.rating,
                                reviews=h.reviews_count, description=h.description,
                                link=h.link, thumbnail=h.thumbnail,
                                property_token=h.property_token
                            )
                            for h in cached_hotels
                        ]
                        return ChatResponse(
                            response=f"Here are the top hotels in {destination} from my records! 🏨",
                            source="local_db_cache",
                            hotels=hotel_results,
                        )

            # Cache miss or stale: fetch fresh from SerpAPI
            logger.info(f"CACHE MISS/STALE: Fetching fresh hotel data for {destination}")
            check_in = parsed.get("check_in")
            check_out = parsed.get("check_out")

            hotels_data = search_hotels(
                destination=destination,
                check_in=check_in,
                check_out=check_out,
            )

            if hotels_data:
                # FIX 2: Don't call process_chat_query() just to create a place record.
                # Use create_place() directly — no wasted LLM call, no service coupling.
                if not place:
                    try:
                        place = create_place(db, {"name": destination, "source": "hotel_search"})
                        logger.info(f"Created placeholder place record for {destination}")
                    except Exception as e:
                        logger.error(
                            f"Failed to create place record for {destination}: {e}",
                            exc_info=True
                        )

                if place:
                    save_hotels_to_db(db, hotels_data, place.id)
                    logger.info(f"Saved/Updated {len(hotels_data)} hotels for {destination}.")

                hotel_results = [HotelResult(**h) for h in hotels_data]
                return ChatResponse(
                    response=f"Here are the latest hotels I found in {destination}! 🏨",
                    source="google_hotels",
                    hotels=hotel_results,
                )
            else:
                return ChatResponse(
                    response=(
                        f"I couldn't find hotel listings for {destination} right now. "
                        "Please make sure the SERPAPI_KEY is configured."
                    ),
                    source="google_hotels",
                )

        else:
            # Place info RAG flow
            result = await process_chat_query(db, request.message, destination)

            place_info = None
            if result.get("place_info"):
                try:
                    place_info = PlaceResponse.model_validate(result["place_info"])
                except Exception as e:
                    logger.error(f"Failed to validate place_info: {e}", exc_info=True)

            return ChatResponse(
                response=result["response"],
                source=result["source"],
                place_info=place_info,
                show_review_prompt=place_info is not None,
            )

    except Exception as e:
        # FIX 4: Use logger.error with exc_info instead of print()
        logger.error(f"Unhandled error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


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