import asyncio
import json
import os
from app.services.gemini_service import model

async def main():
    message = "how is idukki"
    intent_prompt = f"""Analyze the user's travel-related message and return a JSON object with these fields:
- "intent": one of:
    - "hotel_search" (user asking for general hotels/accommodation in a city)
    - "specific_hotel_info" (user asking about a specific hotel by name)
    - "nearby_attractions" (user asking to see nearby places, top sights, or attractions for a city)
    - "place_info" (user asking about a tourist place, destination, weather, things to do)
- "destination": the city or place name mentioned (or null)
- "hotel_name": the specific hotel name if mentioned (or null)
- "place_type": one of ["city", "poi"] - "city" if it's a broad region/town (e.g. Kochi, Bangalore), "poi" if it's a specific point of interest (e.g. Fort Kochi Beach).
- "check_in": check-in date in YYYY-MM-DD format if mentioned (or null)
- "check_out": check-out date in YYYY-MM-DD format if mentioned (or null)

User message: {message}"""

    response = model.generate_content(
        intent_prompt,
        generation_config={"response_mime_type": "application/json"},
    )
    print(response.text)

if __name__ == "__main__":
    asyncio.run(main())
