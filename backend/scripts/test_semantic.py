import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.services.graph_orchestrator import run_travel_graph

async def main():
    db = SessionLocal()
    try:
        response = await run_travel_graph("I like beaches with cliff along with good amount of activities", db)
        print("Response:", response)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
