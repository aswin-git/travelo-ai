import asyncio
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.place_model import ChatRequest
from app.services.graph_orchestrator import run_travel_graph
import json

async def main():
    db = SessionLocal()
    try:
        # Create a mock request
        request = ChatRequest(
            message="plan a trip to munnar starting from alappuzha",
            num_days=3,
            pacing="relaxed",
            start_location="alappuzha",
            session_id="test-session-alappuzha-munnar-3"
        )
        print("Running travel graph...")
        result = await run_travel_graph(request, db)
        
        # Verify itinerary output
        itinerary = result.get("itinerary")
        if itinerary:
            print("\nGenerated Itinerary Successfully:")
            print(f"Destination: {itinerary.get('destination')}")
            for day in itinerary.get("days", []):
                print(f"\n--- Day {day.get('day_number')}: {day.get('theme')} ---")
                for slot in day.get("slots", []):
                    time_label = slot.get("time_label")
                    time_slot = slot.get("time_slot")
                    act = slot.get("activity_name")
                    cat = slot.get("category")
                    travel = slot.get("travel_to_next") or "End of Day"
                    print(f" [{time_slot} | {time_label}] {act} ({cat}) -> Travel: {travel}")
        else:
            print("Failed to generate itinerary. Response:")
            print(result.get("response"))
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
