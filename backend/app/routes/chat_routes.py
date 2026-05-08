from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.place_model import ChatRequest, ChatResponse, PlaceResponse, HotelResult
from ..services.rag_service import process_chat_query
from ..services.hotel_service import search_hotels, save_hotels_to_db
from ..services.gemini_service import model
from ..services.review_service import get_and_summarize_reviews, save_summary_to_db
from ..utils.logger import get_logger
import json

logger = get_logger(__name__)

router = APIRouter()

@router.get("/health")
def health_check():
    return {"status": "healthy"}

@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest, db: Session = Depends(get_db)):
    logger.info(f"Incoming chat request: {request.message}")
    try:
        # Step 1: Use Gemini to detect intent AND extract relevant info
        logger.info("Detecting intent and extracting info using Gemini...")
        intent_prompt = f"""Analyze the user's travel-related message and return a JSON object with these fields:
- "intent": 
    - "hotel_search" (user is asking for general hotels/accommodation options in a city)
    - "specific_hotel_info" (user is asking about a specific hotel by name, e.g., "how is Taj Malabar?")
    - "place_info" (user is asking about a tourist place, destination info, weather, things to do)
- "destination": the city or place name mentioned (or null)
- "hotel_name": the name of the specific hotel if mentioned (or null)
- "check_in": check-in date in YYYY-MM-DD format if mentioned (or null)
- "check_out": check-out date in YYYY-MM-DD format if mentioned (or null)

Return ONLY the raw JSON object.

User message: {request.message}"""

        extraction_result = model.generate_content(intent_prompt).text.strip()
        
        # Clean up potential markdown fences
        if extraction_result.startswith("```"):
            extraction_result = extraction_result.strip("`").strip()
            if extraction_result.startswith("json"):
                extraction_result = extraction_result[4:].strip()
        
        try:
            parsed = json.loads(extraction_result)
        except json.JSONDecodeError:
            parsed = {"intent": "place_info", "destination": extraction_result}
        
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
            # Look up specific hotel in DB
            from ..models.place_model import Hotel, ReviewSummary
            from ..services.gemini_service import chat_with_context
            
            # Search by name (fuzzy search or exact)
            hotel = db.query(Hotel).filter(Hotel.name.ilike(f"%{hotel_name}%")).first()
            
            if hotel:
                # Check for cached summary
                summary_record = db.query(ReviewSummary).filter(
                    ReviewSummary.subject_id == hotel.id,
                    ReviewSummary.subject_type == "hotel"
                ).first()
                
                context = f"Hotel Name: {hotel.name}\nPrice: {hotel.price}\nRating: {hotel.rating}\nDescription: {hotel.description}\n"
                if summary_record:
                    context += f"User Experience Summary: {summary_record.summary}"
                
                bot_response = chat_with_context(request.message, context)
                return ChatResponse(
                    response=bot_response,
                    source="local_db_context",
                    hotels=[HotelResult(
                        name=hotel.name, price=hotel.price, rating=hotel.rating,
                        reviews=hotel.reviews_count, description=hotel.description,
                        link=hotel.link, thumbnail=hotel.thumbnail, property_token=hotel.property_token
                    )]
                )
            else:
                # Fallback to general search if hotel not in DB
                logger.info(f"Hotel {hotel_name} not found in DB. Falling back to search.")
                intent = "hotel_search"
                destination = destination or hotel_name

        if intent == "hotel_search":
            # Hotel search flow (as before)
            # Hotel search flow
            check_in = parsed.get("check_in")
            check_out = parsed.get("check_out")
            
            hotels_data = search_hotels(
                destination=destination,
                check_in=check_in,
                check_out=check_out,
            )
            
            if hotels_data:
                # Save hotels to DB for future use
                from ..services.place_service import get_place_by_name
                place = get_place_by_name(db, destination)
                if place:
                    save_hotels_to_db(db, hotels_data, place.id)
                    logger.info(f"Saved {len(hotels_data)} hotels for {destination} to DB.")
                
                hotel_results = [HotelResult(**h) for h in hotels_data]
                return ChatResponse(
                    response=f"Here are the top hotels I found in {destination}! 🏨",
                    source="google_hotels",
                    hotels=hotel_results,
                )
            else:
                return ChatResponse(
                    response=f"I couldn't find hotel listings for {destination} right now. Please make sure the SERPAPI_KEY is configured.",
                    source="google_hotels",
                )
        
        else:
            # Existing place info RAG flow (unchanged)
            result = process_chat_query(db, request.message, destination)
            
            place_info = None
            if result.get("place_info"):
                place_info = PlaceResponse.model_validate(result["place_info"])
                
            return ChatResponse(
                response=result["response"],
                source=result["source"],
                place_info=place_info,
                show_review_prompt=True if place_info else False
            )
        
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/place/search", response_model=PlaceResponse)
def search_place_endpoint(place_name: str, db: Session = Depends(get_db)):
    from ..services.place_service import get_place_by_name
    place = get_place_by_name(db, place_name)
    if not place:
        raise HTTPException(status_code=404, detail="Place not found in local DB")
    return PlaceResponse.model_validate(place)

@router.post("/chat/summarize-hotel", response_model=ChatResponse)
def summarize_hotel_endpoint(hotel_name: str, property_token: str, db: Session = Depends(get_db)):
    try:
        # Step 1: Check Cache
        from ..models.place_model import Hotel, ReviewSummary
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
                return ChatResponse(
                    response=cached.summary,
                    source="local_db_cache"
                )
            else:
                logger.info("CACHE MISS: No saved summary found for this hotel record.")
        else:
            logger.warning(f"CACHE MISS: Hotel {hotel_name} not found in DB yet.")

        # Step 2: Fetch and Summarize
        summary = get_and_summarize_reviews(hotel_name, hotel_token=property_token)
        
        # Step 3: Save to Cache
        if hotel:
            save_summary_to_db(db, hotel.id, "hotel", summary)
            
        return ChatResponse(
            response=summary,
            source="google_hotels_reviews"
        )
    except Exception as e:
        print(f"Error summarizing hotel reviews: {e}")
        raise HTTPException(status_code=500, detail="Error summarizing reviews")

@router.post("/chat/summarize-place", response_model=ChatResponse)
def summarize_place_endpoint(place_name: str, db: Session = Depends(get_db)):
    try:
        # Step 1: Check Cache
        from ..services.place_service import get_place_by_name
        from ..models.place_model import ReviewSummary
        place = get_place_by_name(db, place_name)
        if place:
            cached = db.query(ReviewSummary).filter(
                ReviewSummary.subject_id == place.id,
                ReviewSummary.subject_type == "place"
            ).first()
            if cached:
                logger.info(f"Returning cached summary for place: {place_name}")
                return ChatResponse(
                    response=cached.summary,
                    source="local_db_cache"
                )

        # Step 2: Fetch and Summarize
        summary = get_and_summarize_reviews(place_name)
        
        # Step 3: Save to Cache
        if place:
            save_summary_to_db(db, place.id, "place", summary)
            
        return ChatResponse(
            response=summary,
            source="google_maps_reviews"
        )
    except Exception as e:
        print(f"Error summarizing place reviews: {e}")
        raise HTTPException(status_code=500, detail="Error summarizing reviews")
