from sqlalchemy.orm import Session
from .place_service import get_place_by_name, create_place
from .osm_service import fetch_osm_data
from .wikipedia_service import fetch_wikipedia_summary
from .gemini_service import summarize_place, chat_with_context
from .chroma_service import add_document, query_documents
from .weather_service import fetch_weather
from .review_service import get_place_description
from ..utils.logger import get_logger

logger = get_logger(__name__)

def process_chat_query(db: Session, message: str, place_name: str) -> dict:
    """Orchestrates the RAG flow for a chat query."""
    logger.info(f"Processing chat query for place: {place_name}")
    
    # 1. Check PostgreSQL Database
    logger.info(f"Checking PostgreSQL for {place_name}...")
    existing_place = get_place_by_name(db, place_name)
    
    if existing_place:
        logger.info(f"Found {place_name} in database. Retrieving context from ChromaDB...")
        # Place exists: Retrieve vectors from Chroma
        chroma_results = query_documents(place_name)
        context = ""
        if chroma_results and chroma_results['documents'] and chroma_results['documents'][0]:
            context = chroma_results['documents'][0][0]
            
        # Append real-time weather data
        if existing_place.latitude and existing_place.longitude:
            weather_info = fetch_weather(lat=existing_place.latitude, lon=existing_place.longitude)
        else:
            weather_info = fetch_weather(place_name=place_name)
        if weather_info:
            context += f" | {weather_info}"
            
        # Generate final response
        bot_response = chat_with_context(message, context)
        return {
            "response": bot_response,
            "source": "database_and_rag",
            "place_info": existing_place
        }
    
    logger.info(f"{place_name} not found in local DB. Fetching from external sources (OSM, Wikipedia, Weather)...")
    # 2. Place does not exist: Fetch from external sources
    osm_data = fetch_osm_data(place_name)
    wiki_data = fetch_wikipedia_summary(place_name)
    
    if wiki_data:
        logger.info(f"Successfully fetched Wikipedia summary for {place_name}")
        raw_context += f"Wikipedia Summary: {wiki_data['summary']} "
    if osm_data:
        raw_context += f"Category: {osm_data.get('category', 'tourist attraction')}."
        # Try to append weather if coordinates exist
        lat, lon = osm_data.get('latitude'), osm_data.get('longitude')
        if lat and lon:
            weather_info = fetch_weather(lat=lat, lon=lon)
        else:
            weather_info = fetch_weather(place_name=place_name)
        if weather_info:
            raw_context += f" | {weather_info}"
    else:
        # No OSM data at all, still try weather by place name
        weather_info = fetch_weather(place_name=place_name)
        if weather_info:
            raw_context += f" | {weather_info}"
            
    # 3. Fallback: Try SerpAPI description if still empty
    if not wiki_data and not osm_data:
        serp_desc = get_place_description(place_name)
        if serp_desc:
            raw_context += f" Search Result Info: {serp_desc}"
        
    if not raw_context:
        return {
            "response": f"I couldn't find enough information about {place_name} to give you a good summary.",
            "source": "none",
            "place_info": None
        }

    # 3. Summarize using Gemini
    clean_description = summarize_place(place_name, raw_context)
    
    # 4. Save to PostgreSQL
    new_place_data = {
        "name": wiki_data.get("title", place_name) if wiki_data else place_name,
        "description": clean_description,
        "source": "external_api",
    }
    
    if osm_data:
        new_place_data["latitude"] = osm_data.get("latitude")
        new_place_data["longitude"] = osm_data.get("longitude")
        new_place_data["category"] = osm_data.get("category")
        new_place_data["osm_id"] = osm_data.get("osm_id")
        
    if wiki_data:
        new_place_data["wikipedia_url"] = wiki_data.get("url")
        
    saved_place = create_place(db, new_place_data)
    logger.info(f"Saved new place data for {place_name} to PostgreSQL (ID: {saved_place.id})")
    
    # 5. Save embeddings to ChromaDB
    doc_id = str(saved_place.id)
    doc_text = f"{saved_place.name}. {saved_place.description}"
    logger.info(f"Indexing {place_name} in ChromaDB...")
    add_document(
        doc_id=doc_id,
        text=doc_text,
        metadata={"name": saved_place.name, "category": saved_place.category or ""}
    )
    
    # 6. Return response
    bot_response = chat_with_context(message, doc_text)
    
    return {
        "response": bot_response,
        "source": "fetched_and_saved",
        "place_info": saved_place
    }
