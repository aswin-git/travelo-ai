from serpapi import GoogleSearch
import os
import json
from dotenv import load_dotenv

load_dotenv()

params = {
  "engine": "google_events",
  "q": "events in Kochi",
  "hl": "en",
  "gl": "in",
  "api_key": os.getenv("SERPAPI_KEY")
}

search = GoogleSearch(params)
results = search.get_dict()
print(json.dumps(results.get("events_results", [])[:2], indent=2))
