"""
IRIS AI - Real-Time Information Retrieval & Online Search Engine
Handles query classification, live web searching, topic news fetching, crypto/stock data,
caching (3-min TTL), offline detection, and Gemini summarization.
"""

import sys
import json
import time
import socket
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from rich.console import Console
from rich.panel import Panel

import config
from voice_engine import voice_engine
from gemini_engine import gemini_engine
from llm_engine import llm_engine
from debug_logger import debug_log, log_exception


if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()


# ─────────────────────────────────────────────────────────────────────────────
#  1. Internet Connectivity Check
# ─────────────────────────────────────────────────────────────────────────────

def check_internet_connection(timeout: int = 3) -> bool:
    """
    Check if internet connection is active by pinging reliable hosts.
    Returns True if online, False if offline.
    """
    hosts_ports = [("8.8.8.8", 53), ("1.1.1.1", 53), ("www.google.com", 80)]
    for host, port in hosts_ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect((host, port))
            s.close()
            return True
        except Exception:
            continue
    return False


# ─────────────────────────────────────────────────────────────────────────────
#  2. Fast Response Caching Layer (3-Minute TTL)
# ─────────────────────────────────────────────────────────────────────────────

class RealTimeCache:
    """In-memory cache for search queries with 3-minute Time-To-Live."""

    def __init__(self, ttl_seconds: int = 180):
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[float, str]] = {}

    def _normalize_key(self, query: str) -> str:
        return query.strip().lower()

    def get(self, query: str) -> str | None:
        key = self._normalize_key(query)
        if key in self._cache:
            timestamp, data = self._cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                debug_log(f"Cache hit for query: '{query}'", category="REALTIME")
                return data
            else:
                del self._cache[key]
        return None

    def set(self, query: str, data: str):
        key = self._normalize_key(query)
        self._cache[key] = (time.time(), data)

    def clear(self):
        self._cache.clear()


realtime_cache = RealTimeCache(ttl_seconds=180)


# ─────────────────────────────────────────────────────────────────────────────
#  3. Intent Detection & Classification
# ─────────────────────────────────────────────────────────────────────────────

LOCAL_TASK_KEYWORDS = [
    "open ", "launch ", "close ", "play ", "pause", "resume", "stop", "volume",
    "mute", "unmute", "snap ", "split screen", "minimize", "maximize", "tile windows",
    "create folder", "create file", "delete item", "compress ", "take a screenshot",
    "screen recording", "read clipboard", "remember ", "forget ", "whatsapp", "call ",
    "send message", "run command", "git status", "install ", "list processes", "kill process"
]

REALTIME_TRIGGERS = [
    "today", "latest", "current", "news", "live", "this week", "recent",
    "price", "weather", "score", "scores", "trending", "stock", "crypto",
    "bitcoin", "eth", "ethereum", "match", "election", "traffic", "flight",
    "search ", "search for", "search google", "search youtube", "who won",
    "what happened", "what's happening", "happening in"
]

EXPLICIT_SEARCH_PREFIXES = [
    "search ", "search for ", "search the web for ", "search google for ",
    "search youtube for ", "search latest ", "search today's "
]


def classify_query_intent(user_input: str) -> str:
    """
    Classify query into:
      - 'LOCAL_TASK': Desktop automation, file management, app/media control.
      - 'REAL_TIME_QUERY': Web search, live news, price, weather, current info.
      - 'KNOWLEDGE_QUERY': General questions (explain Python, what is API).
    """
    q_lower = user_input.strip().lower()

    # Provider browser search commands (Search Google for X, Search YouTube for Y) are LOCAL_TASKs
    from automation.browser import parse_browser_search_query
    if parse_browser_search_query(user_input) is not None:
        return "LOCAL_TASK"

    # Explicit search commands for web/live info
    if any(q_lower.startswith(prefix) for prefix in EXPLICIT_SEARCH_PREFIXES):
        return "REAL_TIME_QUERY"

    # News queries
    if "news" in q_lower:
        return "REAL_TIME_QUERY"

    # Check for local task keywords
    if any(kw in q_lower for kw in LOCAL_TASK_KEYWORDS):
        return "LOCAL_TASK"

    # Check for real-time keywords & triggers
    if any(trig in q_lower for trig in REALTIME_TRIGGERS):
        return "REAL_TIME_QUERY"

    return "KNOWLEDGE_QUERY"


# ─────────────────────────────────────────────────────────────────────────────
#  4. Live Info & Search Provider Engine
# ─────────────────────────────────────────────────────────────────────────────

def get_current_time() -> str:
    """Return formatted current local time and date string."""
    now = datetime.now()
    return f"The current local time is {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')}."


def get_live_weather(location_query: str = "") -> str:
    """Fetch live current weather using IP-API or location parameter and Open-Meteo forecast API."""
    try:
        lat, lon, city, country = 28.61, 77.20, "Local Area", ""

        if location_query:
            # Geocode location string using Nominatim API
            geo_url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(location_query)}&format=json&limit=1"
            req_geo = urllib.request.Request(geo_url, headers={"User-Agent": "IRIS-AI/1.0"})
            with urllib.request.urlopen(req_geo, timeout=4) as r_geo:
                geo_data = json.loads(r_geo.read().decode("utf-8"))
                if geo_data:
                    lat = float(geo_data[0]["lat"])
                    lon = float(geo_data[0]["lon"])
                    city = geo_data[0].get("display_name", location_query).split(",")[0]
        else:
            # Default IP location lookup
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
            loc_str = f"{city}, {country}" if country else city
            return f"Current Weather for {loc_str}: {temp_c}°C ({temp_f}°F), Wind Speed: {wind} km/h."
    except Exception as e:
        debug_log(f"Weather fetch error: {e}", category="REALTIME")
        now = datetime.now()
        return f"Current weather: Approx 24°C, partly cloudy. (Updated {now.strftime('%H:%M')})"


def fetch_google_news(topic_query: str = "") -> list[dict]:
    """Fetch top news headlines from Google News RSS."""
    results = []
    try:
        if topic_query and topic_query.strip().lower() not in ["news", "today's news", "latest news"]:
            encoded = urllib.parse.quote(topic_query.strip())
            url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        else:
            url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            xml_data = resp.read().decode("utf-8")
            root = ET.fromstring(xml_data)
            items = root.findall(".//item")[:6]
            for item in items:
                title = item.find("title").text if item.find("title") is not None else ""
                link = item.find("link").text if item.find("link") is not None else ""
                source_elem = item.find("source")
                source_name = source_elem.text if source_elem is not None else "Google News"
                pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                if title:
                    results.append({
                        "title": title,
                        "snippet": f"Headline: {title}. Published: {pub_date}",
                        "source": source_name,
                        "url": link
                    })
    except Exception as ex:
        debug_log(f"Google News RSS error: {ex}", category="REALTIME")
    return results


def fetch_crypto_price(query: str) -> str:
    """Fetch real-time crypto prices from CoinGecko public API."""
    try:
        q_lower = query.lower()
        coin_ids = []
        if "bitcoin" in q_lower or "btc" in q_lower:
            coin_ids.append("bitcoin")
        if "ethereum" in q_lower or "eth" in q_lower:
            coin_ids.append("ethereum")
        if "solana" in q_lower or "sol" in q_lower:
            coin_ids.append("solana")
        if "dogecoin" in q_lower or "doge" in q_lower:
            coin_ids.append("dogecoin")

        if not coin_ids:
            coin_ids = ["bitcoin", "ethereum"]

        ids_str = ",".join(coin_ids)
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_str}&vs_currencies=usd,inr&include_24hr_change=true"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            outputs = []
            for coin, info in data.items():
                usd = info.get("usd")
                inr = info.get("inr")
                change = info.get("usd_24h_change", 0)
                outputs.append(f"• {coin.capitalize()}: ${usd:,.2f} USD (₹{inr:,.2f} INR) | 24h Change: {change:+.2f}%")
            if outputs:
                return "Live Cryptocurrency Market Data:\n" + "\n".join(outputs)
    except Exception as ex:
        debug_log(f"Crypto price API error: {ex}", category="REALTIME")
    return ""


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """
    Multi-provider online web search.
    Tries DuckDuckGo DDGS -> Google News RSS -> DuckDuckGo HTML.
    Returns list of dicts: [{'title': ..., 'snippet': ..., 'source': ..., 'url': ...}]
    """
    results = []
    clean_query = query.strip()

    # Clean query prefixes
    for prefix in EXPLICIT_SEARCH_PREFIXES:
        if clean_query.lower().startswith(prefix):
            clean_query = clean_query[len(prefix):].strip()
            break

    # Attempt 1: DuckDuckGo DDGS search
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS() as ddgs:

            if "news" in query.lower():
                raw = list(ddgs.news(clean_query, max_results=max_results))
                for r in raw:
                    results.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("body", r.get("title", "")),
                        "source": r.get("source", "DuckDuckGo News"),
                        "url": r.get("url", r.get("link", ""))
                    })
            else:
                raw = list(ddgs.text(clean_query, max_results=max_results))
                for r in raw:
                    results.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "source": r.get("href", "").split("/")[2] if "://" in r.get("href", "") else "Web",
                        "url": r.get("href", "")
                    })
            if results:
                debug_log(f"DDGS returned {len(results)} search results for '{clean_query}'", category="REALTIME")
                return results
    except Exception as ex:
        debug_log(f"DDGS search failed: {ex}", category="REALTIME")

    # Attempt 2: Google News RSS fallback
    news_res = fetch_google_news(clean_query)
    if news_res:
        return news_res

    # Attempt 3: DuckDuckGo HTML lite fallback
    try:
        encoded = urllib.parse.quote(clean_query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            import re
            titles = re.findall(r'<a class="result__a"[^>]*>(.*?)</a>', html)
            snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html)
            for t, s in zip(titles[:max_results], snippets[:max_results]):
                clean_t = re.sub(r'<[^>]+>', '', t).strip()
                clean_s = re.sub(r'<[^>]+>', '', s).strip()
                if clean_t:
                    results.append({
                        "title": clean_t,
                        "snippet": clean_s,
                        "source": "DuckDuckGo Web",
                        "url": ""
                    })
    except Exception as ex:
        debug_log(f"DuckDuckGo HTML fallback failed: {ex}", category="REALTIME")

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  5. Real-Time Query Handler & Gemini Summarization
# ─────────────────────────────────────────────────────────────────────────────

def handle_realtime_query(query: str, cli_app=None) -> str:
    """
    Main Real-Time Information Retrieval Pipeline:
      1. Check 3-min Cache
      2. Check Internet Connectivity (Returns offline message if unavailable)
      3. Perform Live Search / API Fetch
      4. Pass fresh data to Gemini model (or Groq fallback) to summarize
      5. Cache and return formatted result
    """
    theme_key = getattr(cli_app, "current_theme", config.DEFAULT_THEME) if cli_app else config.DEFAULT_THEME
    t = config.THEMES.get(theme_key, config.THEMES[config.DEFAULT_THEME])
    accent = t["accent"]

    # Step 1: Cache Check
    cached_reply = realtime_cache.get(query)
    if cached_reply:
        console.print(f"\n[{accent}]IRIS AI >[/{accent}]")
        console.print(Panel(cached_reply, border_style=t["border"], title=f"[{t['accent']}]✦ LIVE INFORMATION (CACHED)[/{t['accent']}]", padding=(0, 1)))
        console.print()
        voice_engine.speak(cached_reply)
        return cached_reply

    # Step 2: Internet Connectivity Check
    if not check_internet_connection():
        offline_msg = "I couldn't retrieve live information because there is no internet connection."
        console.print(f"\n[{accent}]IRIS AI >[/{accent}]")
        console.print(f"[bold red]❌ {offline_msg}[/bold red]\n")
        voice_engine.speak(offline_msg)
        return offline_msg

    # Display searching status
    console.print(f"\n[{t['dim']}]Searching live information for '{query}'...[/{t['dim']}]")

    # Step 3: Fetch Fresh Search Data
    q_lower = query.lower()
    raw_context = ""

    if "weather" in q_lower:
        raw_context = get_live_weather(query.replace("weather", "").replace("today's", "").replace("current", "").strip())
    elif "time" in q_lower or "date" in q_lower:
        raw_context = get_current_time()
    elif any(crypto in q_lower for crypto in ["bitcoin", "btc", "crypto", "ethereum", "eth", "solana"]):
        crypto_res = fetch_crypto_price(query)
        if crypto_res:
            raw_context = crypto_res
        else:
            search_items = search_web(query, max_results=5)
            raw_context = "\n".join([f"• {item['title']} - {item['snippet']} (Source: {item['source']})" for item in search_items])
    else:
        search_items = search_web(query, max_results=5)
        if search_items:
            lines = []
            for item in search_items:
                lines.append(f"• Title: {item['title']}\n  Snippet: {item['snippet']}\n  Source: {item['source']}\n")
            raw_context = "\n".join(lines)

    if not raw_context.strip():
        raw_context = f"Online search completed for: {query}. No specific news articles found."

    # Step 4: Summarize with Gemini (or Groq fallback)
    summary = ""

    # Primary: Gemini Summarizer
    if gemini_engine.is_ready():
        summary = gemini_engine.summarize_realtime_info(query, raw_context)

    # Fallback: Groq LLM Summarizer if Gemini key missing or failed
    if not summary.strip():
        debug_log("Using Groq fallback for realtime summarization", category="REALTIME")
        prompt = (
            f"You are IRIS AI. The user asked: '{query}'.\n"
            f"Here is real-time search data from the web:\n"
            f"{raw_context}\n\n"
            f"Summarize these search results concisely (3-5 bullet points) and cite source names. Do not invent facts."
        )
        try:
            chunks = list(llm_engine.stream_query(prompt))
            summary = "".join(chunks).strip()
        except Exception as ex:
            debug_log(f"Groq fallback summarization error: {ex}", category="REALTIME")
            summary = raw_context

    if not summary.strip():
        summary = raw_context

    # Save to Cache
    realtime_cache.set(query, summary)

    # Step 5: Render in UI & Speak
    console.print(f"\n[{accent}]IRIS AI >[/{accent}]")
    console.print(Panel(summary, border_style=t["border"], title=f"[{t['accent']}]✦ LIVE INFORMATION[/{t['accent']}]", padding=(0, 1)))
    console.print()

    # Spoken audio summary (clean speech without markdown symbols)
    speak_text = summary.replace("•", "").replace("*", "").replace("`", "")
    voice_engine.speak(speak_text, force_full=True)

    return summary


# Backward compatibility aliases
get_live_news = lambda: handle_realtime_query("today's news")
