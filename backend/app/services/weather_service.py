import requests
from typing import Optional
from ..config import settings

def fetch_weather(lat: float = None, lon: float = None, place_name: str = None) -> Optional[str]:
    """Fetches current weather information from OpenWeather API.
    
    Can use either lat/lon coordinates or a place name as fallback.
    """
    api_key = settings.OPENWEATHER_API_KEY
    if not api_key:
        return None

    # Build URL based on available data
    if lat is not None and lon is not None:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
    elif place_name:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={requests.utils.quote(place_name)}&appid={api_key}&units=metric"
    else:
        return None

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            description = data.get("weather", [{}])[0].get("description", "unknown")
            temp = data.get("main", {}).get("temp", "unknown")
            humidity = data.get("main", {}).get("humidity", "unknown")
            return f"Current Weather: {temp}°C, {description}, humidity {humidity}%"
        return None
    except Exception as e:
        print(f"Weather fetch error: {e}")
        return None
