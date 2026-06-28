# rag_service.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session
from .place_service import get_place_by_name, create_place
from .osm_service import fetch_osm_data
from .wikipedia_service import fetch_full_wikivoyage_content
from .gemini_service import summarize_place, chat_with_context, synthesize_place_knowledge, discover_and_recommend
from .chroma_service import add_document, query_documents
from ..database import SessionLocal
from .weather_service import fetch_weather
from .review_service import get_place_description
from ..utils.logger import get_logger

logger = get_logger(__name__)

# FIX 5: Minimum cosine similarity score to trust a Chroma retrieval result
CHROMA_SIMILARITY_THRESHOLD = 0.5

# Shared thread pool for concurrent external fetches
_executor = ThreadPoolExecutor(max_workers=4)


def _safe_fetch_wikipedia(place_name: str) -> dict | None:
    """Wraps Wikipedia fetch with fault tolerance."""
    try:
        return fetch_full_wikivoyage_content(place_name)
    except Exception as e:
        logger.warning(f"Wikipedia fetch failed for '{place_name}': {e}", exc_info=True)
        return None


def _safe_fetch_osm(place_name: str) -> dict | None:
    """Wraps OSM fetch with fault tolerance."""
    try:
        return fetch_osm_data(place_name)
    except Exception as e:
        logger.warning(f"OSM fetch failed for '{place_name}': {e}", exc_info=True)
        return None


def _safe_fetch_serp_description(place_name: str) -> str | None:
    """Wraps SerpAPI description fetch with fault tolerance."""
    try:
        return get_place_description(place_name)
    except Exception as e:
        logger.warning(f"SerpAPI description fetch failed for '{place_name}': {e}", exc_info=True)
        return None


def _safe_fetch_weather(*, lat: float = None, lon: float = None, place_name: str = None) -> str | None:
    """Wraps weather fetch with fault tolerance."""
    try:
        if lat and lon:
            return fetch_weather(lat=lat, lon=lon)
        return fetch_weather(place_name=place_name)
    except Exception as e:
        logger.warning(f"Weather fetch failed: {e}", exc_info=True)
        return None


async def process_chat_query(db: Session, message: str, place_name: str, history: list = None) -> dict:
    """Orchestrates the RAG flow for a chat query."""
    logger.info(f"Processing chat query for place: {place_name}")

    # 1. Check PostgreSQL
    logger.info(f"Checking PostgreSQL for {place_name}...")
    existing_place = get_place_by_name(db, place_name)

    if existing_place:
        logger.info(f"Found {place_name} in database. Retrieving context from ChromaDB...")

        context = existing_place.description or ""
        
        # Active RAG: Always query ChromaDB using the user's actual question to fetch
        # specific raw facts (from Wikivoyage) that might not be in the general DB description.
        try:
            # Query using the user's message, not just the place name
            chroma_results = query_documents(message, n_results=5)
            if chroma_results and chroma_results.get("documents") and chroma_results["documents"][0]:
                docs = chroma_results["documents"][0]
                retrieved_facts = "\n\n".join(docs)
                
                # Combine base description with specific retrieved facts
                context = f"=== General Description ===\n{context}\n\n=== Specific Retrieved Facts ===\n{retrieved_facts}"
                logger.info(f"Appended {len(docs)} relevant chunks from ChromaDB for query: '{message}'")
        except Exception as e:
            logger.warning(f"ChromaDB query failed: {e}", exc_info=True)

        # FIX 2: Fetch weather at runtime and inject — never persist it
        weather_info = _safe_fetch_weather(
            lat=existing_place.latitude,
            lon=existing_place.longitude,
            place_name=place_name,
        )
        runtime_context = context
        if weather_info:
            runtime_context += f" | {weather_info}"

        bot_response = await chat_with_context(message, runtime_context, history=history)
        return {
            "response": bot_response,
            "source": "database_and_rag",
            "place_info": existing_place,
        }

    # 2. Place not in DB — fetch from external sources
    logger.info(
        f"{place_name} not found in local DB. "
        "Fetching from external sources (OSM, Wikipedia)..."
    )

    # FIX 4: Run Wikipedia and OSM concurrently instead of sequentially
    # FIX 3: Each fetch is individually fault-tolerant via _safe_fetch_* wrappers
    loop = asyncio.new_event_loop()
    try:
        wiki_future = _executor.submit(_safe_fetch_wikipedia, place_name)
        osm_future = _executor.submit(_safe_fetch_osm, place_name)
        wiki_data = wiki_future.result(timeout=15)
        osm_data = osm_future.result(timeout=15)
    except Exception as e:
        logger.error(f"Concurrent external fetch error: {e}", exc_info=True)
        wiki_data, osm_data = None, None
    finally:
        loop.close()

    if wiki_data:
        logger.info(f"Successfully fetched Wikipedia summary for {place_name}")
    if osm_data:
        logger.info(f"Successfully fetched OSM data for {place_name}")

    # FIX 1: Initialize raw_context before any conditional appends
    raw_context = ""

    if wiki_data:
        raw_context += f"Wikivoyage Summary: {wiki_data['summary']} "

    if osm_data:
        raw_context += f"Category: {osm_data.get('category', 'tourist attraction')}. "

    # FIX 3: Fetch weather with fault tolerance
    # FIX 2: Weather is appended to raw_context for LLM use but NOT written to DB later
    lat = osm_data.get("latitude") if osm_data else None
    lon = osm_data.get("longitude") if osm_data else None
    weather_info = _safe_fetch_weather(lat=lat, lon=lon, place_name=place_name)

    # 3. Fallback to SerpAPI if both primary sources failed
    if not wiki_data and not osm_data:
        serp_desc = _safe_fetch_serp_description(place_name)
        if serp_desc:
            raw_context += f"Search Result Info: {serp_desc} "

    if not raw_context.strip():
        return {
            "response": (
                f"I couldn't find enough information about {place_name} "
                "to give you a good summary."
            ),
            "source": "none",
            "place_info": None,
        }

    # 4. Summarize with Gemini — pass weather into the prompt but NOT into stored description
    # FIX 2: raw_context_for_llm includes weather; stored clean_description does not
    raw_context_for_llm = raw_context
    if weather_info:
        raw_context_for_llm += f" | {weather_info}"

    synthesized_data = await synthesize_place_knowledge(place_name, raw_context)
    
    clean_description = ""
    for key, value in synthesized_data.items():
        clean_description += f"### {key.replace('_', ' ').title()}\n{value}\n\n"

    # 5. Save to PostgreSQL (without weather data)
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

    # FIX 3: Wrap DB save in fault-tolerant try/except — still return a response on failure
    try:
        saved_place = create_place(db, new_place_data)
        logger.info(f"Saved new place '{place_name}' to PostgreSQL (ID: {saved_place.id})")
    except Exception as e:
        logger.error(f"Failed to save place '{place_name}' to DB: {e}", exc_info=True)
        bot_response = await chat_with_context(message, raw_context_for_llm, history=history)
        return {
            "response": bot_response,
            "source": "external_api_no_save",
            "place_info": None,
        }

    # 6. Save embeddings to ChromaDB — store only static description, not weather
    try:
        logger.info(f"Indexing '{place_name}' in ChromaDB in chunks...")
        for key, value in synthesized_data.items():
            doc_chunk_id = f"{saved_place.id}-{key}"
            doc_text = f"{saved_place.name} - {key.replace('_', ' ').title()}: {value}"
            add_document(
                doc_id=doc_chunk_id,
                text=doc_text,
                metadata={"name": saved_place.name, "category": saved_place.category or "", "section": key},
            )
    except Exception as e:
        # FIX 3: ChromaDB failure should not crash the entire response
        logger.error(f"ChromaDB chunk indexing failed for '{place_name}': {e}", exc_info=True)

    # 7. Generate and return response using weather-enriched context
    bot_response = await chat_with_context(message, raw_context_for_llm, history=history)

    return {
        "response": bot_response,
        "source": "fetched_and_saved",
        "place_info": saved_place,
    }

async def _background_ingest(place_name: str):
    """Background task to ingest a place into the database."""
    db = SessionLocal()
    try:
        logger.info(f"Starting background ingestion for {place_name}")
        await process_chat_query(db, f"Tell me about {place_name}", place_name)
    except Exception as e:
        logger.error(f"Background ingestion failed for {place_name}: {e}")
    finally:
        db.close()

async def semantic_place_discovery(message: str) -> str:
    """Searches ChromaDB for a vibe/preference and uses Gemini to recommend."""
    logger.info(f"Semantic discovery for: {message}")
    try:
        chroma_results = query_documents(message, n_results=5)
        
        retrieved_context = ""
        if chroma_results and chroma_results.get("documents") and chroma_results["documents"][0]:
            docs = chroma_results["documents"][0]
            metadatas = chroma_results.get("metadatas", [[]])[0]
            
            for i, doc in enumerate(docs):
                place_name = metadatas[i].get("name", "Unknown") if metadatas and len(metadatas) > i else "Unknown"
                retrieved_context += f"- Match {i+1} ({place_name}): {doc}\n"
        
        if not retrieved_context:
            retrieved_context = "No close matches found in database."
            
        gemini_result = await discover_and_recommend(message, retrieved_context)
        
        # Check for cold start ingestion
        places_to_ingest = gemini_result.get("trigger_ingestion", [])
        if places_to_ingest:
            logger.info(f"Triggering background ingestion for: {places_to_ingest}")
            for place in places_to_ingest:
                asyncio.create_task(_background_ingest(place))
                
        return gemini_result.get("response", "I found some great options!")
        
    except Exception as e:
        logger.error(f"Semantic discovery failed: {e}", exc_info=True)
        return "I'm having trouble searching for that vibe right now."