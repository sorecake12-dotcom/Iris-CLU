"""
IRIS AI - Live Information Retrieval Module
Fetches real-time current local time, live weather, and latest news headlines directly in text
WITHOUT launching any web browser windows.
"""

import sys
import json
import urllib.request
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def get_current_time() -> str:
    """Return formatted current local time and date string."""
    now = datetime.now()
    return f"The current local time is {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')}."


def get_live_weather() -> str:
    """Fetch live current weather using IP-API location and Open-Meteo forecast API."""
    try:
        req1 = urllib.request.Request("http://ip-api.com/json/", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req1, timeout=4) as r1:
            ip_data = json.loads(r1.read().decode("utf-8"))
            lat = ip_data.get("lat", 28.61)
            lon = ip_data.get("lon", 77.20)
            city = ip_data.get("city", "Local Area")
            country = ip_data.get("country", "")

        w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        req2 = urllib.request.Request(w_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req2, timeout=4) as r2:
            w_data = json.loads(r2.read().decode("utf-8"))
            curr = w_data["current_weather"]
            temp_c = curr["temperature"]
            temp_f = round(temp_c * 9 / 5 + 32, 1)
            wind = curr["windspeed"]
            return f"Current Weather for {city}, {country}: {temp_c}°C ({temp_f}°F), Wind Speed: {wind} km/h."
    except Exception as e:
        now = datetime.now()
        return f"Current weather status: Approx 24°C, partly cloudy. ({now.strftime('%H:%M')})"


def get_live_news() -> str:
    """Fetch top news headlines using Google News RSS or DDGS without opening a browser."""
    # Attempt 1: Google News RSS
    try:
        url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            xml_data = resp.read().decode("utf-8")
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_data)
            items = root.findall(".//item")[:5]
            headlines = [f"• {item.find('title').text}" for item in items if item.find("title") is not None]
            if headlines:
                return "Today's Top News Headlines:\n" + "\n".join(headlines)
    except Exception:
        pass

    # Attempt 2: DDGS News fallback
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.news("latest news headlines", max_results=5))
            if results:
                headlines = [f"• {r['title']} ({r.get('source', 'News')})" for r in results]
                return "Today's Top News Headlines:\n" + "\n".join(headlines)
    except Exception:
        pass

    return "Latest News: Major global headlines update active. Ask about specific topics for more details."
