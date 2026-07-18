import os
from serpapi import GoogleSearch
from app.config import settings

def test_hotel_reviews(hotel_name, place_name):
    print(f"Testing reviews for {hotel_name} in {place_name}")
    api_key = settings.SERPAPI_KEY
    # Search for the hotel in Google Maps
    params = {
        "engine": "google_maps",
        "q": f"{hotel_name} {place_name}",
        "api_key": api_key,
    }
    search = GoogleSearch(params)
    results = search.get_dict()
    
    local_results = results.get("local_results", [])
    if not local_results:
        place_results = results.get("place_results", {})
        if place_results:
            local_results = [place_results]
            
    if local_results:
        first_result = local_results[0]
        data_id = first_result.get("data_id")
        if data_id:
            print(f"Found data_id: {data_id}")
            # Now fetch reviews
            review_params = {
                "engine": "google_maps_reviews",
                "data_id": data_id,
                "api_key": api_key,
            }
            review_search = GoogleSearch(review_params)
            review_results = review_search.get_dict()
            reviews = review_results.get("reviews", [])
            print(f"Found {len(reviews)} reviews")
            for r in reviews[:2]:
                print(r.get("snippet"))
        else:
            print("No data_id found")
    else:
        print("No local results found")

test_hotel_reviews("Taj Mahal Palace", "Mumbai")
