"""
Friday News Aggregator
----------------------
Fetches worldwide news from multiple free RSS/Atom sources.
- No API key needed (uses free RSS feeds)
- Smart deduplication
- AI-powered summaries for verbal briefings
- Categorized: World, Tech, Science, Sports, Finance
"""

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import feedparser
import httpx
from loguru import logger

from config.loader import get as cfg


@dataclass
class NewsItem:
    title: str
    source: str
    url: str
    summary: str = ""
    published: Optional[datetime] = None
    category: str = "world"
    id: str = field(default="", init=False)

    def __post_init__(self):
        self.id = hashlib.md5(self.url.encode()).hexdigest()[:8]

    def to_spoken(self) -> str:
        """Format for voice readout."""
        time_str = ""
        if self.published:
            delta = datetime.now(timezone.utc) - self.published.replace(tzinfo=timezone.utc) if self.published.tzinfo is None else datetime.now(timezone.utc) - self.published
            hours = int(delta.total_seconds() / 3600)
            if hours < 1:
                time_str = "just now"
            elif hours < 24:
                time_str = f"{hours} hour{'s' if hours > 1 else ''} ago"
        return f"From {self.source}: {self.title}. {time_str}"

    def to_display(self) -> str:
        """Format for HUD display."""
        return f"[{self.source}] {self.title}"


# ──────────────────────────────────────────────────────────────
# RSS Feed Sources (all free, no API key)
# ──────────────────────────────────────────────────────────────

DEFAULT_FEEDS = [
    # World News
    {"name": "BBC World",        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",        "category": "world"},
    {"name": "Reuters",          "url": "https://feeds.reuters.com/reuters/topNews",          "category": "world"},
    {"name": "AP News",          "url": "https://rsshub.app/apnews/topics/apf-topnews",       "category": "world"},
    # Technology
    {"name": "Hacker News",      "url": "https://hnrss.org/frontpage",                        "category": "tech"},
    {"name": "TechCrunch",       "url": "https://techcrunch.com/feed/",                       "category": "tech"},
    {"name": "The Verge",        "url": "https://www.theverge.com/rss/index.xml",             "category": "tech"},
    {"name": "Ars Technica",     "url": "https://feeds.arstechnica.com/arstechnica/index",    "category": "tech"},
    # Science
    {"name": "Science Daily",    "url": "https://www.sciencedaily.com/rss/all.xml",           "category": "science"},
    {"name": "NASA News",        "url": "https://www.nasa.gov/news-release/feed/",            "category": "science"},
    # Finance
    {"name": "CNBC Top News",    "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "category": "finance"},
]


class NewsAggregator:
    """
    Multi-source news aggregator with smart deduplication and caching.
    """

    def __init__(self):
        self._cache: dict[str, NewsItem] = {}  # id → NewsItem
        self._last_fetch: float = 0
        self._refresh_interval = cfg("news.refresh_interval_minutes", 30) * 60
        self._max_headlines = cfg("news.max_headlines", 10)

        # Load configured sources or use defaults
        configured = cfg("news.sources", [])
        if configured:
            self._feeds = [
                {"name": f["name"], "url": f["url"], "category": "world"}
                for f in configured
            ]
        else:
            self._feeds = DEFAULT_FEEDS

        logger.info(f"News aggregator initialized | {len(self._feeds)} sources")

    def _fetch_feed(self, feed: dict, timeout: int = 10) -> list[NewsItem]:
        """Fetch and parse a single RSS feed."""
        items = []
        try:
            # feedparser handles most RSS/Atom formats
            parsed = feedparser.parse(feed["url"])
            if parsed.bozo and not parsed.entries:
                logger.warning(f"Feed parse error for {feed['name']}: {parsed.bozo_exception}")
                return []

            for entry in parsed.entries[:5]:  # Max 5 per source
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                summary = entry.get("summary", "")[:300]

                if not title or not link:
                    continue

                # Parse publish time
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])

                item = NewsItem(
                    title=title,
                    source=feed["name"],
                    url=link,
                    summary=summary,
                    published=published,
                    category=feed.get("category", "world"),
                )
                items.append(item)

            logger.debug(f"Fetched {len(items)} items from {feed['name']}")
        except Exception as e:
            logger.warning(f"Failed to fetch {feed['name']}: {e}")
        return items

    def fetch(self, force: bool = False) -> list[NewsItem]:
        """
        Fetch news from all sources.
        Returns cached results if within refresh interval.
        """
        now = time.time()
        if not force and (now - self._last_fetch) < self._refresh_interval and self._cache:
            logger.debug("Returning cached news")
            return list(self._cache.values())

        logger.info(f"Fetching news from {len(self._feeds)} sources...")
        all_items = []
        for feed in self._feeds:
            items = self._fetch_feed(feed)
            all_items.extend(items)

        # Deduplicate by ID
        new_items: dict[str, NewsItem] = {}
        for item in all_items:
            if item.id not in new_items:
                new_items[item.id] = item

        self._cache = new_items
        self._last_fetch = time.time()
        logger.info(f"News updated: {len(self._cache)} unique items")
        return list(self._cache.values())

    def get_by_category(self, category: str) -> list[NewsItem]:
        """Get news filtered by category."""
        items = self.fetch()
        return [i for i in items if i.category == category]

    def get_top(self, n: int | None = None) -> list[NewsItem]:
        """Get top N headlines (most recent first)."""
        n = n or self._max_headlines
        items = self.fetch()
        # Sort by publish time (most recent first)
        sorted_items = sorted(
            items,
            key=lambda x: x.published or datetime.min,
            reverse=True,
        )
        return sorted_items[:n]

    def get_ticker_text(self) -> str:
        """
        Get a continuous ticker string for the HUD.
        Example: "[BBC] Trump signs deal ... | [Reuters] Markets rally ..."
        """
        items = self.get_top(8)
        if not items:
            return "No news available - fetching..."
        return "   ●   ".join(item.to_display() for item in items)

    def morning_briefing_text(self, n: int = 5) -> str:
        """
        Generate a spoken morning briefing script.
        """
        items = self.get_top(n)
        if not items:
            return "I wasn't able to fetch news right now. I'll try again in a moment."

        lines = ["Here's your morning briefing:"]
        for i, item in enumerate(items, 1):
            lines.append(f"{i}. {item.to_spoken()}")
        lines.append("That's the top news. Have a great day.")
        return " ".join(lines)

    def search(self, query: str) -> list[NewsItem]:
        """Simple keyword search in fetched news."""
        items = self.fetch()
        query_lower = query.lower()
        return [
            item for item in items
            if query_lower in item.title.lower() or query_lower in item.summary.lower()
        ]


# ──────────────────────────────────────────────────────────────
# Weather (free, no API key - uses open-meteo.com)
# ──────────────────────────────────────────────────────────────

class WeatherFetcher:
    """Free weather from Open-Meteo API - no API key needed."""

    def __init__(self):
        self._cache: dict | None = None
        self._cache_time: float = 0
        self._cache_ttl = 3600  # 1 hour

    def _get_location(self) -> tuple[float, float, str]:
        """Auto-detect location from IP (free, no key)."""
        override = cfg("weather.location")
        if override:
            # Geocode the location name
            return self._geocode(override)
        try:
            r = httpx.get("http://ip-api.com/json/", timeout=5)
            data = r.json()
            return data["lat"], data["lon"], f"{data['city']}, {data['country']}"
        except Exception:
            return 40.7128, -74.0060, "New York, US"  # Default fallback

    def _geocode(self, location: str) -> tuple[float, float, str]:
        """Geocode a location name to lat/lon."""
        try:
            r = httpx.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": location, "count": 1},
                timeout=5,
            )
            results = r.json().get("results", [])
            if results:
                r = results[0]
                return r["latitude"], r["longitude"], location
        except Exception:
            pass
        return 40.7128, -74.0060, location

    def get(self) -> dict:
        """Fetch current weather. Returns dict with temp, condition, etc."""
        now = time.time()
        if self._cache and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        try:
            lat, lon, city = self._get_location()
            r = httpx.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current_weather": True,
                    "hourly": "relative_humidity_2m",
                    "temperature_unit": "celsius",
                    "wind_speed_unit": "kmh",
                    "timezone": "auto",
                },
                timeout=8,
            )
            data = r.json()
            weather = data.get("current_weather", {})
            result = {
                "city": city,
                "temp_c": weather.get("temperature", "--"),
                "temp_f": round(weather.get("temperature", 0) * 9 / 5 + 32, 1),
                "wind_kmh": weather.get("windspeed", "--"),
                "condition_code": weather.get("weathercode", 0),
                "condition": _weather_code_to_text(weather.get("weathercode", 0)),
                "is_day": weather.get("is_day", 1),
            }
            self._cache = result
            self._cache_time = now
            return result
        except Exception as e:
            logger.warning(f"Weather fetch failed: {e}")
            return {"city": "Unknown", "temp_c": "--", "condition": "unavailable"}

    def spoken(self) -> str:
        """Return weather as a spoken sentence."""
        w = self.get()
        return (
            f"In {w['city']}, it's {w['temp_c']} degrees Celsius, {w['condition']}. "
            f"Wind at {w.get('wind_kmh', '--')} kilometers per hour."
        )


def _weather_code_to_text(code: int) -> str:
    """Convert WMO weather interpretation code to text."""
    codes = {
        0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
        45: "foggy", 48: "icy fog",
        51: "light drizzle", 53: "moderate drizzle", 55: "heavy drizzle",
        61: "light rain", 63: "moderate rain", 65: "heavy rain",
        71: "light snow", 73: "moderate snow", 75: "heavy snow",
        80: "light showers", 81: "moderate showers", 82: "heavy showers",
        95: "thunderstorm", 96: "thunderstorm with hail", 99: "heavy thunderstorm",
    }
    return codes.get(code, "mixed conditions")


# Global singletons
_news_instance: NewsAggregator | None = None
_weather_instance: WeatherFetcher | None = None


def get_news() -> NewsAggregator:
    global _news_instance
    if _news_instance is None:
        _news_instance = NewsAggregator()
    return _news_instance


def get_weather() -> WeatherFetcher:
    global _weather_instance
    if _weather_instance is None:
        _weather_instance = WeatherFetcher()
    return _weather_instance
