"""
Re-ingestion script for places with broken/sparse knowledge.

Purges existing data from PostgreSQL + ChromaDB, re-fetches from Wikivoyage,
and stores BOTH raw Wikivoyage text chunks AND Gemini-synthesized chunks
in ChromaDB for richer RAG context.

Usage:
    python -m evaluation.reingest_places                     # All eval places
    python -m evaluation.reingest_places --places Kovalam Alappuzha  # Specific places
    python -m evaluation.reingest_places --dry-run           # Preview only
"""

import argparse
import asyncio
import os
import re
import sys
import textwrap
import time

import requests

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.models.place_model import Place
from app.services.osm_service import fetch_osm_data
from app.services.gemini_service import synthesize_place_knowledge
from app.services.chroma_service import collection, add_document, embedding_model
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _fetch_wikivoyage_full(place_name: str) -> dict | None:
    """Fetches FULL Wikivoyage page content using the parse API.

    The extracts API only returns intro paragraphs (~200-400 chars).
    The parse API returns full wikitext (10K-50K chars) which we clean
    into plain text.
    """
    url = "https://en.wikivoyage.org/w/api.php"
    params = {
        "action": "parse",
        "format": "json",
        "page": place_name,
        "prop": "wikitext",
        "redirects": 1,
    }
    headers = {"User-Agent": "TraveloAI/1.0 (contact@travelo.ai)"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code != 200:
            return None

        data = r.json()
        if "error" in data:
            logger.warning(f"Wikivoyage error for '{place_name}': {data['error']}")
            return None

        parse_data = data.get("parse", {})
        wikitext = parse_data.get("wikitext", {}).get("*", "")
        title = parse_data.get("title", place_name)

        if not wikitext or len(wikitext) < 50:
            return None

        # Clean wikitext to plain text
        plain = _clean_wikitext(wikitext)

        return {
            "title": title,
            "summary": plain,
            "url": f"https://en.wikivoyage.org/wiki/{requests.utils.quote(title)}",
            "source": "wikivoyage_parse",
        }
    except Exception as e:
        logger.error(f"Wikivoyage parse fetch failed for '{place_name}': {e}")
        return None


def _fetch_wikipedia_content(place_name: str) -> str:
    """Fetches Wikipedia article text as supplementary factual content."""
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "titles": place_name,
        "explaintext": True,
        "redirects": 1,
    }
    headers = {"User-Agent": "TraveloAI/1.0 (contact@travelo.ai)"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code != 200:
            return ""
        data = r.json()
        pages = data.get("query", {}).get("pages", {})
        page_id = next(iter(pages))
        if page_id == "-1":
            return ""
        return pages[page_id].get("extract", "")
    except Exception as e:
        logger.warning(f"Wikipedia fetch failed for '{place_name}': {e}")
        return ""


def _clean_wikitext(wikitext: str) -> str:
    """Converts MediaWiki wikitext to readable plain text.

    Removes templates, file references, HTML tags, and wiki markup
    while preserving section headers and content.
    """
    text = wikitext

    # Remove templates like {{...}} (including nested)
    depth = 0
    result = []
    i = 0
    while i < len(text):
        if text[i:i+2] == "{{":
            depth += 1
            i += 2
        elif text[i:i+2] == "}}" and depth > 0:
            depth -= 1
            i += 2
        elif depth == 0:
            result.append(text[i])
            i += 1
        else:
            i += 1
    text = "".join(result)

    # Remove [[File:...]] and [[Image:...]]
    text = re.sub(r'\[\[(File|Image):[^\]]*\]\]', '', text, flags=re.IGNORECASE)

    # Convert [[link|display]] to display, [[link]] to link
    text = re.sub(r'\[\[[^\]]*\|([^\]]*)\]\]', r'\1', text)
    text = re.sub(r'\[\[([^\]]*)\]\]', r'\1', text)

    # Remove external links [http://... text] → text
    text = re.sub(r'\[https?://\S+\s+([^\]]*)\]', r'\1', text)
    text = re.sub(r'\[https?://\S+\]', '', text)

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Convert section headers == X == to plain text markers
    text = re.sub(r'={2,}\s*([^=]+?)\s*={2,}', r'\n\n== \1 ==\n', text)

    # Remove bold/italic markup
    text = re.sub(r"'{2,}", '', text)

    # Remove bullet/list markers at start of lines
    text = re.sub(r'^\*+\s*', '- ', text, flags=re.MULTILINE)

    # Clean up excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)

    return text.strip()


# All places in the evaluation dataset
EVAL_PLACES = ["Munnar", "Alappuzha", "Wayanad", "Varkala", "Kumarakom", "Kovalam"]

# Sections from synthesize_place_knowledge
SYNTH_SECTIONS = [
    "overview", "history_and_culture", "best_time_to_visit",
    "neighborhoods_districts", "local_delicacies", "things_to_do",
    "getting_around", "accommodation_tips", "hidden_gems", "safety_tips",
]


def _chunk_raw_text(place_name: str, raw_text: str, chunk_size: int = 800) -> list[dict]:
    """Splits raw Wikivoyage text into overlapping chunks for ChromaDB storage.

    Returns list of dicts with keys: chunk_id, text, section_label
    """
    if not raw_text or len(raw_text.strip()) < 50:
        return []

    # Split by double newlines (Wikivoyage section boundaries)
    paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]

    chunks = []
    current_chunk = ""
    current_section = "intro"
    chunk_idx = 0

    for para in paragraphs:
        # Detect section headers (Wikivoyage uses == Section == format)
        if para.startswith("==") and para.endswith("=="):
            current_section = para.strip("= ").lower().replace(" ", "_")
            continue

        # If adding this paragraph exceeds chunk_size, save current and start new
        if len(current_chunk) + len(para) > chunk_size and current_chunk:
            chunks.append({
                "chunk_id": f"{place_name.lower()}-raw-{chunk_idx}",
                "text": f"{place_name} - Raw Wikivoyage ({current_section}): {current_chunk}",
                "section_label": f"raw_{current_section}",
            })
            chunk_idx += 1
            # Overlap: keep last 200 chars for context continuity
            current_chunk = current_chunk[-200:] + "\n\n" + para
        else:
            current_chunk += ("\n\n" if current_chunk else "") + para

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append({
            "chunk_id": f"{place_name.lower()}-raw-{chunk_idx}",
            "text": f"{place_name} - Raw Wikivoyage ({current_section}): {current_chunk}",
            "section_label": f"raw_{current_section}",
        })

    return chunks


def _purge_place(place_name: str, db, dry_run: bool = False) -> Place | None:
    """Purges ChromaDB chunks for a place. Returns the existing Place record
    (if any) so it can be updated in-place (avoids FK constraint issues)."""
    # 1. Find existing PostgreSQL record (don't delete — FK constraints)
    existing = db.query(Place).filter(Place.name.ilike(f"%{place_name}%")).first()
    if existing:
        place_id = str(existing.id)
        logger.info(f"  PostgreSQL: found '{existing.name}' (ID: {place_id}) — will update in-place")
    else:
        place_id = None
        logger.info(f"  PostgreSQL: '{place_name}' not found — will create new")

    # 2. Remove all ChromaDB chunks matching this place
    try:
        # Get all docs matching this place name in metadata
        all_results = collection.get(
            where={"name": place_name},
            include=["metadatas"],
        )
        if all_results and all_results["ids"]:
            ids_to_delete = all_results["ids"]
            logger.info(f"  ChromaDB: found {len(ids_to_delete)} chunks by metadata")
            if not dry_run:
                collection.delete(ids=ids_to_delete)
                logger.info(f"  ChromaDB: deleted {len(ids_to_delete)} chunks")
        else:
            logger.info(f"  ChromaDB: no chunks found by metadata for '{place_name}'")
    except Exception as e:
        logger.warning(f"  ChromaDB metadata delete failed: {e}")

    # Also try to delete by known ID patterns (synthesized chunks use place_id-section format)
    if place_id:
        synth_ids = [f"{place_id}-{section}" for section in SYNTH_SECTIONS]
        try:
            existing_docs = collection.get(ids=synth_ids)
            found_ids = [id_ for id_ in existing_docs["ids"]] if existing_docs["ids"] else []
            if found_ids and not dry_run:
                collection.delete(ids=found_ids)
                logger.info(f"  ChromaDB: deleted {len(found_ids)} synthesized chunks by ID")
        except Exception:
            pass  # IDs may not exist, that's fine

    # Also try raw chunk IDs
    raw_ids = [f"{place_name.lower()}-raw-{i}" for i in range(100)]
    try:
        existing_raw = collection.get(ids=raw_ids)
        found_raw = [id_ for id_ in existing_raw["ids"]] if existing_raw["ids"] else []
        if found_raw and not dry_run:
            collection.delete(ids=found_raw)
            logger.info(f"  ChromaDB: deleted {len(found_raw)} raw chunks by ID")
    except Exception:
        pass


async def _ingest_place(place_name: str, db, dry_run: bool = False) -> dict:
    """Fetches fresh data and stores in PostgreSQL + ChromaDB.

    Uses Wikivoyage parse API (full page) + Wikipedia as supplementary source
    for maximum knowledge density.

    Returns a status dict with keys: place_name, wiki_chars, synth_chunks, raw_chunks, status
    """
    result = {
        "place_name": place_name,
        "wiki_chars": 0,
        "synth_chunks": 0,
        "raw_chunks": 0,
        "status": "pending",
    }

    # 1. Fetch from Wikivoyage (full page via parse API)
    logger.info(f"  Fetching full Wikivoyage content for '{place_name}'...")
    wiki_data = _fetch_wikivoyage_full(place_name)

    raw_text = ""
    if wiki_data and wiki_data.get("summary"):
        raw_text = wiki_data["summary"]
        logger.info(f"  Wikivoyage: got {len(raw_text)} chars (full page)")
    else:
        logger.warning(f"  Wikivoyage: no full page found for '{place_name}'")

    # 2. Fetch supplementary Wikipedia content
    logger.info(f"  Fetching Wikipedia content for '{place_name}'...")
    wiki_extra = _fetch_wikipedia_content(place_name)
    if wiki_extra:
        logger.info(f"  Wikipedia: got {len(wiki_extra)} chars")
        # Append Wikipedia content, clearly labeled
        raw_text += f"\n\n== Wikipedia Facts ==\n{wiki_extra}"
    else:
        logger.info(f"  Wikipedia: no content found")

    if not raw_text or len(raw_text.strip()) < 100:
        logger.error(f"  ❌ No sufficient data from any source for '{place_name}'")
        result["status"] = "wiki_failed"
        return result

    result["wiki_chars"] = len(raw_text)

    if dry_run:
        result["status"] = "dry_run"
        raw_chunks = _chunk_raw_text(place_name, raw_text)
        result["raw_chunks"] = len(raw_chunks)
        result["synth_chunks"] = len(SYNTH_SECTIONS)
        return result

    # 2. Fetch OSM data for coordinates
    logger.info(f"  Fetching OSM data for '{place_name}'...")
    try:
        osm_data = fetch_osm_data(place_name)
    except Exception as e:
        logger.warning(f"  OSM fetch failed: {e}")
        osm_data = None

    # 3. Synthesize with Gemini (truncate to ~25K chars to stay within token limits)
    logger.info(f"  Synthesizing knowledge with Gemini...")
    synthesis_text = raw_text[:25000] if len(raw_text) > 25000 else raw_text
    raw_context = f"Wikivoyage and Wikipedia Content: {synthesis_text}"
    if osm_data:
        raw_context += f" Category: {osm_data.get('category', 'tourist attraction')}."

    synthesized = await synthesize_place_knowledge(place_name, raw_context)

    # Check for failed synthesis (all values = "Information currently unavailable")
    bad_values = sum(1 for v in synthesized.values() if "unavailable" in str(v).lower() or "sorry" in str(v).lower())
    if bad_values > 5:
        logger.error(f"  ❌ Gemini synthesis mostly failed ({bad_values}/{len(synthesized)} sections)")
        result["status"] = "synth_failed"
        return result

    # 4. Build description for PostgreSQL
    clean_description = ""
    for key, value in synthesized.items():
        clean_description += f"### {key.replace('_', ' ').title()}\n{value}\n\n"

    # 5. Save to PostgreSQL (update existing or create new)
    existing_place = db.query(Place).filter(Place.name.ilike(f"%{place_name}%")).first()

    if existing_place:
        # Update existing record in-place (preserves FK references)
        existing_place.description = clean_description
        existing_place.source = "external_api"
        if wiki_data:
            existing_place.wikipedia_url = wiki_data.get("url")
        if osm_data:
            existing_place.latitude = osm_data.get("latitude")
            existing_place.longitude = osm_data.get("longitude")
            existing_place.category = osm_data.get("category")
            existing_place.osm_id = osm_data.get("osm_id")
        db.commit()
        db.refresh(existing_place)
        db_place = existing_place
        logger.info(f"  PostgreSQL: updated '{db_place.name}' (ID: {db_place.id})")
    else:
        # Create new record
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
        db_place = Place(**new_place_data)
        db.add(db_place)
        db.commit()
        db.refresh(db_place)
        logger.info(f"  PostgreSQL: created '{db_place.name}' (ID: {db_place.id})")

    # 6. Store synthesized chunks in ChromaDB
    for key, value in synthesized.items():
        if "unavailable" in str(value).lower():
            continue
        doc_id = f"{db_place.id}-{key}"
        doc_text = f"{db_place.name} - {key.replace('_', ' ').title()}: {value}"
        add_document(
            doc_id=doc_id,
            text=doc_text,
            metadata={"name": db_place.name, "category": db_place.category or "", "section": key},
        )
        result["synth_chunks"] += 1

    logger.info(f"  ChromaDB: stored {result['synth_chunks']} synthesized chunks")

    # 7. Store raw Wikivoyage text chunks in ChromaDB
    raw_chunks = _chunk_raw_text(place_name, raw_text)
    for chunk in raw_chunks:
        add_document(
            doc_id=chunk["chunk_id"],
            text=chunk["text"],
            metadata={"name": place_name, "category": db_place.category or "", "section": chunk["section_label"]},
        )
    result["raw_chunks"] = len(raw_chunks)
    logger.info(f"  ChromaDB: stored {len(raw_chunks)} raw Wikivoyage chunks")

    result["status"] = "success"
    return result


async def main():
    parser = argparse.ArgumentParser(description="Re-ingest places with fresh Wikivoyage data")
    parser.add_argument("--places", nargs="+", default=None, help="Specific places to re-ingest")
    parser.add_argument("--dry-run", action="store_true", help="Preview without modifying data")
    args = parser.parse_args()

    places = args.places or EVAL_PLACES

    print(f"\n{'='*60}")
    print(f"  🔄 Travelo AI — Place Re-Ingestion")
    print(f"{'='*60}")
    print(f"  Places: {', '.join(places)}")
    print(f"  Mode:   {'DRY RUN (no changes)' if args.dry_run else 'LIVE (will modify data)'}")
    print(f"{'='*60}\n")

    db = SessionLocal()
    results = []

    try:
        for i, place in enumerate(places):
            print(f"\n[{i+1}/{len(places)}] Processing: {place}")
            print("-" * 40)

            # Purge old data
            logger.info(f"Purging old data for '{place}'...")
            _purge_place(place, db, dry_run=args.dry_run)

            # Re-ingest
            logger.info(f"Re-ingesting '{place}'...")
            result = await _ingest_place(place, db, dry_run=args.dry_run)
            results.append(result)

            # Rate limit between places
            if i < len(places) - 1:
                time.sleep(2)

    finally:
        db.close()

    # Summary
    print(f"\n{'='*60}")
    print(f"  📊 Re-Ingestion Summary")
    print(f"{'='*60}")
    print(f"  {'Place':<15} {'Wiki Chars':>10} {'Synth':>6} {'Raw':>5} {'Status':<15}")
    print(f"  {'-'*55}")
    for r in results:
        status_icon = "✅" if r["status"] == "success" else "👀" if r["status"] == "dry_run" else "❌"
        print(f"  {r['place_name']:<15} {r['wiki_chars']:>10} {r['synth_chunks']:>6} {r['raw_chunks']:>5} {status_icon} {r['status']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
