import asyncio
from app.database import SessionLocal
from app.services.rag_service import _safe_fetch_wikipedia, _safe_fetch_osm, _safe_fetch_serp_description
# from app.services.gemini_service import summarize_place
# from app.services.place_service import get_place_by_name, create_place
# from app.services.chroma_service import add_document
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ==========================================
# EDIT THIS LIST WITH THE PLACES YOU WANT TO SEED
# ==========================================
PLACES_TO_SEED = [
    "Munnar",
    "Alappuzha",
    "Wayanad",
    "Varkala",
    "Kumarakom",
    "Kovalam"
]

async def seed_place(place_name: str, db):
    logger.info(f"--- Seeding {place_name} ---")
    
    # 1. Check if already exists
    # existing = get_place_by_name(db, place_name)
    # if existing:
    #     logger.info(f"'{place_name}' is already in the database. Skipping.")
    #     return
        
    logger.info(f"Fetching external data for '{place_name}'...")
    
    # 2. Fetch from Wikipedia and OSM
    wiki_data = _safe_fetch_wikipedia(place_name)
    osm_data = _safe_fetch_osm(place_name)
    
    raw_context = ""
    if wiki_data:
        raw_context += f"Wikipedia Summary: {wiki_data['summary']}"
    if osm_data:
        raw_context += f"Category: {osm_data.get('category', 'tourist attraction')}. "

    print(raw_context)
        
    # 3. Fallback to SerpAPI if needed
    # if not wiki_data and not osm_data:
    #     serp_desc = _safe_fetch_serp_description(place_name)
    #     if serp_desc:
    #         raw_context += f"Search Result Info: {serp_desc} "
            
    # if not raw_context.strip():
    #     logger.warning(f"Could not find enough info for '{place_name}'. Skipping.")
    #     return
        
    # # 4. Summarize with Gemini
    # logger.info(f"Generating summary for '{place_name}' via Gemini...")
    # clean_description = await summarize_place(place_name, raw_context)
    
    # # 5. Save to PostgreSQL
    # new_place_data = {
    #     "name": wiki_data.get("title", place_name) if wiki_data else place_name,
    #     "description": clean_description,
    #     "source": "seed_script",
    # }

    # if osm_data:
    #     new_place_data["latitude"] = osm_data.get("latitude")
    #     new_place_data["longitude"] = osm_data.get("longitude")
    #     new_place_data["category"] = osm_data.get("category")
    #     new_place_data["osm_id"] = osm_data.get("osm_id")

    # if wiki_data:
    #     new_place_data["wikipedia_url"] = wiki_data.get("url")

    # try:
    #     saved_place = create_place(db, new_place_data)
    #     logger.info(f"Saved '{place_name}' to PostgreSQL (ID: {saved_place.id})")
        
    #     # 6. Index in ChromaDB
    #     doc_id = str(saved_place.id)
    #     doc_text = f"{saved_place.name}. {saved_place.description}"
    #     add_document(
    #         doc_id=doc_id,
    #         text=doc_text,
    #         metadata={"name": saved_place.name, "category": saved_place.category or ""}
    #     )
    #     logger.info(f"Indexed '{place_name}' in ChromaDB successfully.")
    # except Exception as e:
    #     logger.error(f"Failed to save/index '{place_name}': {e}")

async def main():
    # db = SessionLocal()
    try:
        for place in PLACES_TO_SEED:
            await seed_place(place, None)
            await asyncio.sleep(2) # Small delay to avoid API rate limits
    finally:
        print()
        # db.close()
    
    # logger.info("Database seeding process completed!")

if __name__ == "__main__":
    asyncio.run(main())
