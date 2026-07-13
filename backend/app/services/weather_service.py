import requests
from typing import Optional, List, Dict
from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


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
        logger.error(f"Weather fetch error: {e}")
        return None


def fetch_multi_day_forecast(
    lat: float = None,
    lon: float = None,
    place_name: str = None,
    num_days: int = 5,
) -> List[Dict]:
    """Fetches multi-day weather forecast from OpenWeather 5-day/3-hour API.

    Groups 3-hour intervals into daily summaries with avg temp, conditions,
    humidity, and wind speed. Max 5 days (API limit for free tier).

    Args:
        lat: Latitude of the destination.
        lon: Longitude of the destination.
        place_name: Fallback — city name for geocoding by OpenWeather.
        num_days: Number of forecast days (capped at 5).

    Returns:
        List of dicts, one per day:
        [
            {
                "day_number": 1,
                "date": "2026-07-12",
                "avg_temp_c": 28.5,
                "min_temp_c": 24.0,
                "max_temp_c": 33.0,
                "condition": "light rain",
                "humidity_pct": 78,
                "wind_kmh": 15.2,
                "icon": "🌧️",
                "summary": "Light rain, 24-33°C, humidity 78%",
                "tip": "Carry an umbrella and prefer indoor attractions in the morning."
            },
            ...
        ]
    """
    api_key = settings.OPENWEATHER_API_KEY
    if not api_key:
        logger.warning("OPENWEATHER_API_KEY not set — skipping forecast")
        return []

    num_days = min(num_days, 5)  # Free tier limit

    if lat is not None and lon is not None:
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric"
    elif place_name:
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={requests.utils.quote(place_name)}&appid={api_key}&units=metric"
    else:
        return []

    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            logger.warning(f"Weather forecast API returned {response.status_code}: {response.text[:200]}")
            return []

        data = response.json()
        forecasts = data.get("list", [])
        if not forecasts:
            return []

        # Group 3-hour entries by date
        from collections import defaultdict
        daily: Dict[str, list] = defaultdict(list)
        for entry in forecasts:
            date_str = entry.get("dt_txt", "")[:10]  # "2026-07-12"
            if date_str:
                daily[date_str].append(entry)

        # Build daily summaries (up to num_days)
        result = []
        for day_idx, (date_str, entries) in enumerate(sorted(daily.items())):
            if day_idx >= num_days:
                break

            temps = [e["main"]["temp"] for e in entries if "main" in e]
            humidities = [e["main"]["humidity"] for e in entries if "main" in e]
            winds = [e.get("wind", {}).get("speed", 0) for e in entries]

            # Most common weather condition
            conditions = [
                e["weather"][0]["description"]
                for e in entries
                if e.get("weather")
            ]
            # Pick the most frequent condition
            if conditions:
                from collections import Counter
                main_condition = Counter(conditions).most_common(1)[0][0]
            else:
                main_condition = "unknown"

            avg_temp = round(sum(temps) / len(temps), 1) if temps else 0
            min_temp = round(min(temps), 1) if temps else 0
            max_temp = round(max(temps), 1) if temps else 0
            avg_humidity = round(sum(humidities) / len(humidities)) if humidities else 0
            avg_wind = round((sum(winds) / len(winds)) * 3.6, 1) if winds else 0  # m/s → km/h

            icon = _condition_to_icon(main_condition)
            tip = _generate_weather_tip(main_condition, max_temp, avg_humidity, avg_wind)

            summary = f"{main_condition.capitalize()}, {min_temp}-{max_temp}°C, humidity {avg_humidity}%"

            result.append({
                "day_number": day_idx + 1,
                "date": date_str,
                "avg_temp_c": avg_temp,
                "min_temp_c": min_temp,
                "max_temp_c": max_temp,
                "condition": main_condition,
                "humidity_pct": avg_humidity,
                "wind_kmh": avg_wind,
                "icon": icon,
                "summary": summary,
                "tip": tip,
            })

        logger.info(f"Fetched {len(result)}-day forecast for {'coords' if lat else place_name}")
        return result

    except Exception as e:
        logger.error(f"Weather forecast fetch error: {e}", exc_info=True)
        return []


def _condition_to_icon(condition: str) -> str:
    """Maps OpenWeather condition string to emoji icon."""
    c = condition.lower()
    if "thunderstorm" in c:
        return "⛈️"
    elif "drizzle" in c:
        return "🌦️"
    elif "rain" in c or "shower" in c:
        return "🌧️"
    elif "snow" in c:
        return "🌨️"
    elif "mist" in c or "fog" in c or "haze" in c:
        return "🌫️"
    elif "cloud" in c or "overcast" in c:
        return "☁️"
    elif "clear" in c:
        return "☀️"
    else:
        return "🌤️"


def _generate_weather_tip(condition: str, max_temp: float, humidity: int, wind_kmh: float) -> str:
    """Generates actionable weather tips for travelers."""
    tips = []
    c = condition.lower()

    # Precipitation tips
    if any(w in c for w in ["rain", "drizzle", "shower", "thunderstorm"]):
        tips.append("Carry an umbrella and prefer indoor attractions during peak rain hours.")
        if "thunderstorm" in c:
            tips.append("Avoid hilltop viewpoints and open areas during storms.")
    elif "snow" in c:
        tips.append("Wear layered warm clothing and waterproof boots.")

    # Temperature tips
    if max_temp >= 35:
        tips.append("Extreme heat — stay hydrated, wear sunscreen, and avoid outdoor activities between 12-3 PM.")
    elif max_temp >= 30:
        tips.append("Hot weather — carry water, wear light clothing, and take breaks in shade.")
    elif max_temp <= 10:
        tips.append("Cold weather — pack warm layers and a windproof jacket.")

    # Humidity tips
    if humidity >= 80 and max_temp >= 28:
        tips.append("High humidity — expect sweating; lightweight breathable fabrics recommended.")

    # Wind tips
    if wind_kmh >= 30:
        tips.append("Strong winds expected — secure loose items and be cautious at elevated viewpoints.")

    # Visibility tips
    if any(w in c for w in ["mist", "fog", "haze"]):
        tips.append("Low visibility — scenic viewpoints may be obscured; plan indoor alternatives.")

    if not tips:
        tips.append("Pleasant weather — great conditions for outdoor sightseeing!")

    return " ".join(tips)
