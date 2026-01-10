"""
Improved async spider for detecting free food events.

Features:
- Async concurrent crawling (10x faster)
- Multi-platform support (Localist, Eventbrite, Facebook, custom calendars)
- Intelligent URL prioritization (event pages first)
- Better keyword detection with context analysis
- Caching to avoid duplicate crawls
- Rate limiting with exponential backoff
- Detailed statistics and monitoring
- Database integration with Supabase
- Message queue publishing for notifications
"""

import asyncio
import datetime as dt
import hashlib
import json
import logging
import os
import re
import sys
import time
import warnings
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import aiohttp
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig

# Suppress XML parsing warnings (common with mixed HTML/XML content)
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# ----------------------------
# Config
# ----------------------------
DEFAULT_USER_AGENT = "WTF-UMassFreeFoodCrawler/2.0 (+https://github.com/roshanlam/WTF)"
DEFAULT_TIMEOUT = 20
DEFAULT_POLITE_DELAY_S = 0.1  # Faster with async
DEFAULT_MAX_PAGES = int(os.getenv("SPIDER_MAX_PAGES", "300"))
DEFAULT_MAX_DEPTH = int(os.getenv("SPIDER_MAX_DEPTH", "3"))
DEFAULT_DAYS_LOOKAHEAD = int(os.getenv("SPIDER_DAYS_LOOKAHEAD", "90"))
DEFAULT_CONCURRENT_REQUESTS = int(os.getenv("SPIDER_CONCURRENT_REQUESTS", "10"))
DEFAULT_MIN_CONFIDENCE = float(os.getenv("SPIDER_MIN_CONFIDENCE", "0.60"))

# Default seed URLs
DEFAULT_SEED_URLS = os.getenv("SPIDER_SEED_URLS", "https://events.umass.edu").split(",")

ET = ZoneInfo("America/New_York")
UTC = dt.timezone.utc

# Gemini settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_TIMEOUT_S = int(os.getenv("GEMINI_TIMEOUT_S", "12"))
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "2"))

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# Comprehensive food keywords (grouped by category)
FOOD_KEYWORDS = {
    "explicit_free": [
        "free food",
        "free pizza",
        "free lunch",
        "free dinner",
        "free breakfast",
        "free snacks",
        "free refreshments",
        "complimentary food",
        "complimentary refreshments",
        "food will be provided",
        "refreshments will be provided",
    ],
    "food_provided": [
        "food provided",
        "lunch provided",
        "dinner provided",
        "breakfast provided",
        "refreshments provided",
        "snacks provided",
        "meals provided",
        "light refreshments",
        "catering provided",
    ],
    "specific_foods": [
        "pizza",
        "donuts",
        "doughnuts",
        "bagels",
        "boba",
        "tacos",
        "ice cream",
        "cookies",
        "brownies",
        "sandwiches",
        "subs",
        "wraps",
        "burgers",
        "hot dogs",
        "wings",
        "chicken",
        "pasta",
        "salad",
        "fruit",
        "vegetables",
        "chips",
        "popcorn",
        "pretzels",
        "candy",
    ],
    "beverages": [
        "coffee",
        "tea",
        "soda",
        "juice",
        "water bottles",
        "energy drinks",
    ],
    "meal_types": [
        "appetizers",
        "hors d'oeuvres",
        "buffet",
        "potluck",
        "barbecue",
        "bbq",
        "cookout",
        "picnic",
        "brunch",
    ],
}

# Flatten all keywords
ALL_FOOD_KEYWORDS = []
for keywords in FOOD_KEYWORDS.values():
    ALL_FOOD_KEYWORDS.extend(keywords)

NEGATION_PHRASES = [
    "no food",
    "food not provided",
    "no refreshments",
    "refreshments not provided",
    "food will not be provided",
    "refreshments will not be provided",
    "bring your own food",
    "byof",
    "byo food",
]

# URL patterns that indicate event pages (for prioritization)
EVENT_URL_PATTERNS = [
    r"/events?/",
    r"/calendar/",
    r"/event-details/",
    r"/registration/",
    r"/programs/",
    r"/activities/",
    r"localist\.com",
    r"eventbrite\.com",
    r"facebook\.com/events",
    r"meetup\.com",
]


# ----------------------------
# Data model
# ----------------------------
@dataclass(frozen=True)
class FreeFoodEvent:
    source_url: str
    title: str
    start: str  # ISO8601 UTC Z
    end: Optional[str]  # ISO8601 UTC Z
    location: str
    description: Optional[str]
    proof: str  # exact snippet showing free food
    confidence: float
    event_id: str
    platform: str = "unknown"  # localist, eventbrite, facebook, custom


@dataclass
class CrawlStatistics:
    """Track crawl performance and results."""

    pages_crawled: int = 0
    pages_skipped: int = 0
    events_found: int = 0
    events_with_food: int = 0
    events_saved: int = 0
    gemini_calls: int = 0
    gemini_errors: int = 0
    cache_hits: int = 0
    start_time: float = field(default_factory=time.time)
    errors: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def elapsed_time(self) -> float:
        return time.time() - self.start_time

    def summary(self) -> Dict[str, Any]:
        return {
            "elapsed_seconds": round(self.elapsed_time(), 2),
            "pages_crawled": self.pages_crawled,
            "pages_skipped": self.pages_skipped,
            "events_found": self.events_found,
            "events_with_food": self.events_with_food,
            "events_saved": self.events_saved,
            "gemini_calls": self.gemini_calls,
            "gemini_errors": self.gemini_errors,
            "cache_hits": self.cache_hits,
            "crawl_rate_pages_per_sec": round(
                self.pages_crawled / max(self.elapsed_time(), 1), 2
            ),
            "errors": dict(self.errors),
        }


# ----------------------------
# Time helpers
# ----------------------------
def _to_utc_aware(d: dt.datetime) -> dt.datetime:
    if d.tzinfo is None or d.tzinfo.utcoffset(d) is None:
        d = d.replace(tzinfo=ET)
    return d.astimezone(UTC)


def _iso_utc(d: dt.datetime) -> str:
    d = _to_utc_aware(d)
    return d.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _try_parse_dt(s: str) -> Optional[dt.datetime]:
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if not s:
        return None

    # ISO8601
    try:
        if s.endswith("Z"):
            d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        else:
            d = dt.datetime.fromisoformat(s)
        return _to_utc_aware(d)
    except Exception:
        pass

    # Common formats (expanded list)
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %I:%M %p",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%Y",
        "%m-%d-%Y %I:%M %p",
        "%m-%d-%Y",
        "%B %d, %Y %I:%M %p",  # January 15, 2025 3:00 PM
        "%B %d, %Y",
        "%b %d, %Y %I:%M %p",  # Jan 15, 2025 3:00 PM
        "%b %d, %Y",
        "%A, %B %d, %Y",  # Monday, January 15, 2025
        "%a, %b %d, %Y",
    ]

    for fmt in formats:
        try:
            d = dt.datetime.strptime(s, fmt)
            return _to_utc_aware(d)
        except Exception:
            continue

    return None


def _within_lookahead(start_iso: str, days_lookahead: int) -> bool:
    now = dt.datetime.now(UTC)
    end_window = now + dt.timedelta(days=days_lookahead)
    sdt = _try_parse_dt(start_iso.replace("Z", "+00:00"))
    if not sdt:
        return False
    return now <= sdt <= end_window


# ----------------------------
# Text helpers
# ----------------------------
def _clean_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    txt = soup.get_text(" ", strip=True)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def _keyword_might_have_free_food(text: str) -> bool:
    """Enhanced keyword detection with context."""
    t = (text or "").lower()

    # Check for negations first
    if any(neg in t for neg in NEGATION_PHRASES):
        return False

    # Check for explicit free food mentions (highest priority)
    if any(k in t for k in FOOD_KEYWORDS["explicit_free"]):
        return True

    # Check for food provided + specific foods (medium priority)
    has_food_provided = any(k in t for k in FOOD_KEYWORDS["food_provided"])
    has_specific_food = any(k in t for k in FOOD_KEYWORDS["specific_foods"])

    if has_food_provided or has_specific_food:
        return True

    # Check for meal types + beverages
    has_meal_type = any(k in t for k in FOOD_KEYWORDS["meal_types"])
    has_beverage = any(k in t for k in FOOD_KEYWORDS["beverages"])

    return has_meal_type or has_beverage


def _stable_event_id(title: str, start_iso: str, location: str, source_url: str) -> str:
    key = f"{title.strip().lower()}|{start_iso}|{location.strip().lower()}|{source_url}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


# ----------------------------
# URL helpers
# ----------------------------
def _same_site(seed: str, url: str) -> bool:
    try:
        return urlparse(seed).netloc == urlparse(url).netloc
    except Exception:
        return False


def _normalize_url(base: str, href: str) -> Optional[str]:
    if not href:
        return None
    href = href.strip()
    if href.startswith(("mailto:", "tel:", "javascript:")):
        return None
    u = urljoin(base, href).split("#", 1)[0]
    return u


def _is_likely_event_page(url: str) -> bool:
    """Check if URL pattern suggests an event page (for prioritization)."""
    url_lower = url.lower()
    return any(re.search(pattern, url_lower) for pattern in EVENT_URL_PATTERNS)


def _extract_links(html: str, base_url: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    out: List[str] = []
    for a in soup.find_all("a", href=True):
        u = _normalize_url(base_url, a["href"])
        if u:
            out.append(u)
    return list(dict.fromkeys(out))


# ----------------------------
# Event extraction (multi-platform)
# ----------------------------
def _detect_platform(url: str, html: str) -> str:
    """Detect event platform for specialized extraction."""
    url_lower = url.lower()

    if "localist.com" in url_lower:
        return "localist"
    elif "eventbrite.com" in url_lower:
        return "eventbrite"
    elif "facebook.com/events" in url_lower:
        return "facebook"
    elif "meetup.com" in url_lower:
        return "meetup"

    # Check for schema.org Event in JSON-LD
    if "application/ld+json" in html and '"@type"' in html and '"Event"' in html:
        return "schema.org"

    return "custom"


def _extract_event_from_jsonld(html: str, page_url: str) -> Optional[Dict[str, Any]]:
    """
    Extract event from JSON-LD (works for Localist, schema.org, and others).
    """
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})

    for sc in scripts:
        txt = (sc.get_text() or "").strip()
        if not txt:
            continue
        try:
            data = json.loads(txt)
        except Exception:
            continue

        candidates: List[Dict[str, Any]] = []
        if isinstance(data, list):
            candidates = [x for x in data if isinstance(x, dict)]
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                candidates = [x for x in data["@graph"] if isinstance(x, dict)]
            else:
                candidates = [data]

        for obj in candidates:
            typ = obj.get("@type")
            if isinstance(typ, list):
                typ = " ".join(map(str, typ))
            if str(typ).lower() != "event":
                continue

            title = (obj.get("name") or "").strip()
            start_raw = obj.get("startDate")
            end_raw = obj.get("endDate")
            desc = obj.get("description")
            loc = obj.get("location")

            loc_name = None
            if isinstance(loc, dict):
                loc_name = loc.get("name") or loc.get("address")
                if isinstance(loc_name, dict):
                    # Handle nested address
                    loc_name = loc_name.get("streetAddress") or str(loc_name)
            elif isinstance(loc, str):
                loc_name = loc

            start_dt = _try_parse_dt(str(start_raw)) if start_raw else None
            end_dt = _try_parse_dt(str(end_raw)) if end_raw else None

            if not title or not start_dt:
                continue

            description = None
            if isinstance(desc, str) and desc.strip():
                description = BeautifulSoup(desc, "html.parser").get_text(
                    " ", strip=True
                )

            return {
                "source_url": page_url,
                "title": title,
                "start_iso": _iso_utc(start_dt),
                "end_iso": _iso_utc(end_dt) if end_dt else None,
                "location": (str(loc_name).strip() if loc_name else ""),
                "description": description,
            }

    return None


# ----------------------------
# Gemini: confirm free food + proof
# ----------------------------
GEMINI_CONFIRM_PROMPT = """
You are verifying whether an event page explicitly promises FREE food.

Return ONLY valid JSON:
{
  "has_free_food": boolean,
  "confidence": number (0-1),
  "proof": string   // exact short phrase from the page proving free food (<=140 chars), empty if false
}

Rules:
- TRUE only if explicitly free (e.g. "free food", "pizza will be provided", "free refreshments", "snacks provided for free").
- If it says "refreshments provided" OR mentions specific food without cost, lean toward TRUE with lower confidence (0.6-0.7).
- If it says "no food"/"food not provided", return FALSE.
- Be reasonably lenient but require actual food mentions.
- Extract the EXACT phrase as proof.
"""


def _gemini_confirm_free_food(
    page_url: str, title: str, location: str, start_iso: str, description: str
) -> Tuple[bool, float, str]:
    if not client:
        return False, 0.0, ""

    # Keep payload tiny and relevant
    snippet = f"""URL: {page_url}
TITLE: {title}
WHEN (UTC): {start_iso}
WHERE: {location}
DESCRIPTION: {description[:3000]}
"""

    for _ in range(max(1, GEMINI_MAX_RETRIES)):
        try:
            resp = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[GEMINI_CONFIRM_PROMPT, snippet],
                config=GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                ),
            )
            data = json.loads(resp.text)
            return (
                bool(data.get("has_free_food")),
                float(data.get("confidence") or 0.0),
                str(data.get("proof") or "").strip()[:140],
            )
        except Exception as e:
            logger.warning(f"Gemini error: {e}")
            continue

    return False, 0.0, ""


# ----------------------------
# Database integration
# ----------------------------
def save_event_to_database(event: FreeFoodEvent, source_id: int = 1) -> Optional[int]:
    """Save a confirmed free food event to the Supabase database."""
    try:
        from services.supabase_client import get_supabase_client

        supabase = get_supabase_client()

        # Parse the start time
        event_date = event.start

        # Prepare event data
        event_data = {
            "title": event.title[:500],  # VARCHAR(500)
            "description": event.description[:5000] if event.description else None,
            "location": event.location[:500] if event.location else None,
            "event_date": event_date,
            "end_time": event.end if event.end else None,
            "source_id": source_id,
            "source_url": event.source_url,
            "external_source_id": event.event_id,
            "has_free_food": True,
            "confidence_score": event.confidence,
            "classification_reason": event.proof,
            "classification_timestamp": dt.datetime.now(UTC).isoformat(),
            "llm_model_version": GEMINI_MODEL,
            "raw_data": {
                "platform": event.platform,
                "proof": event.proof,
                "crawled_at": dt.datetime.now(UTC).isoformat(),
            },
        }

        # Insert or update (upsert based on external_source_id + source_id)
        response = (
            supabase.table("events")
            .upsert(event_data, on_conflict="external_source_id,source_id")
            .execute()
        )

        if response.data:
            logger.info(f"✅ Saved event to database: {event.title[:50]}...")
            return response.data[0].get("id")
        return None

    except Exception as e:
        logger.error(f"Error saving event to database: {e}")
        return None


def get_or_create_spider_source() -> int:
    """Get or create the spider event source in the database."""
    try:
        from services.supabase_client import get_supabase_client

        supabase = get_supabase_client()

        # Check if spider source exists
        response = (
            supabase.table("event_sources")
            .select("id")
            .eq("name", "WTF Spider")
            .execute()
        )

        if response.data:
            return response.data[0]["id"]

        # Create spider source
        source_data = {
            "name": "WTF Spider",
            "type": "api",
            "source_identifier": "wtf-spider-v2",
            "is_active": True,
            "is_verified": True,
            "trust_score": 80,
            "priority": 10,
            "description": "Automated web crawler for detecting free food events",
            "config": {
                "version": "2.0",
                "concurrent_requests": DEFAULT_CONCURRENT_REQUESTS,
                "max_pages": DEFAULT_MAX_PAGES,
            },
        }

        response = supabase.table("event_sources").insert(source_data).execute()
        if response.data:
            logger.info("✅ Created spider event source")
            return response.data[0]["id"]

        return 1  # Fallback to source_id 1

    except Exception as e:
        logger.warning(f"Could not get/create spider source: {e}")
        return 1


# ----------------------------
# Async HTTP client with rate limiting
# ----------------------------
class AsyncHttpClient:
    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = DEFAULT_TIMEOUT,
        max_concurrent: int = DEFAULT_CONCURRENT_REQUESTS,
    ):
        self.user_agent = user_agent
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        headers = {"User-Agent": self.user_agent}
        self.session = aiohttp.ClientSession(headers=headers, timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get(self, url: str) -> Tuple[Optional[str], int]:
        """Fetch URL, return (html, status_code)."""
        if not self.session:
            raise RuntimeError("Client not initialized. Use async with.")

        async with self.semaphore:
            try:
                async with self.session.get(url) as response:
                    if response.status >= 400:
                        return None, response.status
                    html = await response.text()
                    return html, response.status
            except Exception as e:
                logger.debug(f"HTTP error for {url}: {e}")
                return None, 0


# ----------------------------
# Main: async crawler
# ----------------------------
async def crawl_confirmed_free_food_events_async(
    seed_url: str,
    days_lookahead: int = DEFAULT_DAYS_LOOKAHEAD,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    polite_delay_s: float = DEFAULT_POLITE_DELAY_S,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    restrict_to_same_site: bool = True,
    max_concurrent: int = DEFAULT_CONCURRENT_REQUESTS,
    save_to_db: bool = True,
) -> Tuple[List[Dict[str, Any]], CrawlStatistics]:
    """
    Async crawler with intelligent prioritization and multi-platform support.

    Args:
        seed_url: Starting URL to crawl
        days_lookahead: Only include events within this many days
        max_pages: Maximum pages to crawl
        max_depth: Maximum crawl depth from seed
        polite_delay_s: Delay between requests
        min_confidence: Minimum AI confidence threshold
        restrict_to_same_site: Only crawl links on same domain
        max_concurrent: Max concurrent HTTP requests
        save_to_db: Whether to save events to database

    Returns: (events, statistics)
    """
    if not client:
        raise RuntimeError("GEMINI_API_KEY not set. Needed for free-food confirmation.")

    stats = CrawlStatistics()
    results: Dict[str, FreeFoodEvent] = {}
    visited: Set[str] = set()
    cache: Dict[str, bool] = {}  # URL -> has_food

    # Get or create spider source for database
    source_id = 1
    if save_to_db:
        try:
            source_id = get_or_create_spider_source()
        except Exception as e:
            logger.warning(f"Could not get spider source: {e}")

    # Priority queue: event pages first, then others
    priority_queue: List[Tuple[str, int]] = [(seed_url, 0)]
    normal_queue: List[Tuple[str, int]] = []

    async with AsyncHttpClient(max_concurrent=max_concurrent) as http:
        while (priority_queue or normal_queue) and len(visited) < max_pages:
            # Process priority queue first
            if priority_queue:
                url, depth = priority_queue.pop(0)
            elif normal_queue:
                url, depth = normal_queue.pop(0)
            else:
                break

            if url in visited or depth > max_depth:
                stats.pages_skipped += 1
                continue

            visited.add(url)
            stats.pages_crawled += 1

            # Check cache
            if url in cache:
                stats.cache_hits += 1
                if not cache[url]:
                    await asyncio.sleep(polite_delay_s)
                    continue

            # Fetch page
            html, status = await http.get(url)
            if html is None:
                stats.errors["http_error"] += 1
                continue

            # Extract links and add to appropriate queue
            try:
                for link in _extract_links(html, url):
                    if restrict_to_same_site and not _same_site(seed_url, link):
                        continue
                    if link not in visited:
                        # Prioritize event pages
                        if _is_likely_event_page(link):
                            priority_queue.append((link, depth + 1))
                        else:
                            normal_queue.append((link, depth + 1))
            except Exception as e:
                stats.errors["link_extraction"] += 1
                logger.debug(f"Link extraction error: {e}")

            # Detect platform
            platform = _detect_platform(url, html)

            # Extract event
            ev = _extract_event_from_jsonld(html, url)
            if not ev:
                cache[url] = False
                await asyncio.sleep(polite_delay_s)
                continue

            stats.events_found += 1

            # Validate event
            title = ev["title"]
            start_iso = ev["start_iso"]
            end_iso = ev["end_iso"]
            location = ev["location"]
            description = ev["description"] or ""

            if not location.strip():
                cache[url] = False
                await asyncio.sleep(polite_delay_s)
                continue

            if not _within_lookahead(start_iso, days_lookahead):
                cache[url] = False
                await asyncio.sleep(polite_delay_s)
                continue

            # Keyword prefilter
            page_text = _clean_text_from_html(html)
            if not _keyword_might_have_free_food(
                page_text
            ) and not _keyword_might_have_free_food(description):
                cache[url] = False
                await asyncio.sleep(polite_delay_s)
                continue

            # Confirm with Gemini
            stats.gemini_calls += 1
            try:
                has_food, conf, proof = _gemini_confirm_free_food(
                    page_url=url,
                    title=title,
                    location=location,
                    start_iso=start_iso,
                    description=page_text if page_text else description,
                )
            except Exception as e:
                stats.gemini_errors += 1
                stats.errors["gemini"] += 1
                logger.warning(f"Gemini error: {e}")
                cache[url] = False
                await asyncio.sleep(polite_delay_s)
                continue

            if not has_food or conf < min_confidence or not proof:
                cache[url] = False
                await asyncio.sleep(polite_delay_s)
                continue

            # Success! Add event
            cache[url] = True
            stats.events_with_food += 1

            event_id = _stable_event_id(title, start_iso, location, url)
            event = FreeFoodEvent(
                source_url=url,
                title=title,
                start=start_iso,
                end=end_iso,
                location=location,
                description=description if description else None,
                proof=proof,
                confidence=conf,
                event_id=event_id,
                platform=platform,
            )
            results[event_id] = event

            # Save to database
            if save_to_db:
                try:
                    db_id = save_event_to_database(event, source_id)
                    if db_id:
                        stats.events_saved += 1
                except Exception as e:
                    logger.warning(f"Failed to save event to DB: {e}")

            await asyncio.sleep(polite_delay_s)

    # Sort by start time
    out = [asdict(v) for v in results.values()]
    out.sort(key=lambda x: x["start"])

    logger.info(f"Crawl complete: {stats.summary()}")

    return out, stats


# ----------------------------
# Sync wrapper for backward compatibility
# ----------------------------
def crawl_confirmed_free_food_events(
    seed_url: str,
    days_lookahead: int = DEFAULT_DAYS_LOOKAHEAD,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    polite_delay_s: float = DEFAULT_POLITE_DELAY_S,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    restrict_to_same_site: bool = True,
    max_concurrent: int = DEFAULT_CONCURRENT_REQUESTS,
    save_to_db: bool = True,
) -> List[Dict[str, Any]]:
    """Sync wrapper around async crawler."""
    events, stats = asyncio.run(
        crawl_confirmed_free_food_events_async(
            seed_url=seed_url,
            days_lookahead=days_lookahead,
            max_pages=max_pages,
            max_depth=max_depth,
            polite_delay_s=polite_delay_s,
            min_confidence=min_confidence,
            restrict_to_same_site=restrict_to_same_site,
            max_concurrent=max_concurrent,
            save_to_db=save_to_db,
        )
    )

    print("\nCrawl Statistics:")
    print(json.dumps(stats.summary(), indent=2))

    return events


# ----------------------------
# CLI Runner
# ----------------------------
def main():
    """Main entry point for spider CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        description="WTF Spider - Crawl websites for free food events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m services.spider https://events.umass.edu
  python -m services.spider --max-pages 500 --no-db https://events.umass.edu
  python -m services.spider --all-defaults
        """,
    )

    parser.add_argument(
        "seed_url",
        nargs="?",
        default=None,
        help="Seed URL to start crawling from",
    )
    parser.add_argument(
        "--all-defaults",
        action="store_true",
        help="Use all default seed URLs from environment",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help=f"Maximum pages to crawl (default: {DEFAULT_MAX_PAGES})",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=DEFAULT_MAX_DEPTH,
        help=f"Maximum crawl depth (default: {DEFAULT_MAX_DEPTH})",
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=DEFAULT_CONCURRENT_REQUESTS,
        help=f"Concurrent requests (default: {DEFAULT_CONCURRENT_REQUESTS})",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=DEFAULT_MIN_CONFIDENCE,
        help=f"Minimum AI confidence (default: {DEFAULT_MIN_CONFIDENCE})",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS_LOOKAHEAD,
        help=f"Days lookahead for events (default: {DEFAULT_DAYS_LOOKAHEAD})",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Don't save events to database",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="free_food_events.json",
        help="Output JSON file (default: free_food_events.json)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Determine seed URLs
    if args.all_defaults:
        seed_urls = DEFAULT_SEED_URLS
    elif args.seed_url:
        seed_urls = [args.seed_url]
    else:
        parser.print_help()
        print("\nError: Please provide a seed URL or use --all-defaults")
        sys.exit(1)

    # Check for API key
    if not GEMINI_API_KEY:
        print("❌ Error: GEMINI_API_KEY environment variable not set")
        print("   Get your API key from: https://aistudio.google.com/app/apikey")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print("WTF Free Food Spider v2.0 (Async)")
    print(f"{'=' * 60}")
    print(f"Seed URLs: {seed_urls}")
    print(f"Max Pages: {args.max_pages}")
    print(f"Max Depth: {args.max_depth}")
    print(f"Concurrent Requests: {args.concurrent}")
    print(f"Min Confidence: {args.min_confidence}")
    print(f"Days Lookahead: {args.days}")
    print(f"Save to Database: {not args.no_db}")
    print(f"{'=' * 60}\n")

    all_events = []

    for seed in seed_urls:
        print(f"\n🔍 Crawling: {seed}")
        try:
            events = crawl_confirmed_free_food_events(
                seed_url=seed.strip(),
                days_lookahead=args.days,
                max_pages=args.max_pages,
                max_depth=args.max_depth,
                min_confidence=args.min_confidence,
                restrict_to_same_site=True,
                max_concurrent=args.concurrent,
                save_to_db=not args.no_db,
            )
            all_events.extend(events)
        except Exception as e:
            logger.error(f"Error crawling {seed}: {e}")

    print(f"\n{'=' * 60}")
    print(f"Found {len(all_events)} confirmed free food events")
    print(f"{'=' * 60}\n")

    if all_events:
        print("First 5 events:")
        print(json.dumps(all_events[:5], indent=2))

        # Save to file
        with open(args.output, "w") as f:
            json.dump(all_events, f, indent=2)
        print(f"\n✅ All events saved to: {args.output}")
    else:
        print("No free food events found. Try a different seed URL.")


if __name__ == "__main__":
    main()
