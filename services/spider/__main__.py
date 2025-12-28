import datetime as dt
import hashlib
import json
import os
import re
import time
import warnings
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# Gemini
from google import genai
from google.genai.types import GenerateContentConfig

# ----------------------------
# Config
# ----------------------------
DEFAULT_USER_AGENT = "WTF-UMassFreeFoodCrawler/1.1 (+https://github.com/roshanlam/WTF)"
DEFAULT_TIMEOUT = 20
DEFAULT_POLITE_DELAY_S = 0.2
DEFAULT_MAX_PAGES = 200
DEFAULT_MAX_DEPTH = 2
DEFAULT_DAYS_LOOKAHEAD = 90

ET = ZoneInfo("America/New_York")
UTC = dt.timezone.utc

# Gemini settings (make it NOT hang)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_TIMEOUT_S = int(os.getenv("GEMINI_TIMEOUT_S", "12"))  # hard cap
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "1"))

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# Heuristic prefilter
FREE_FOOD_KEYWORDS = [
    "free food",
    "food provided",
    "lunch provided",
    "dinner provided",
    "breakfast provided",
    "refreshments provided",
    "snacks provided",
    "pizza",
    "donuts",
    "doughnuts",
    "bagels",
    "boba",
    "tacos",
    "ice cream",
    "coffee",
    "tea",
    "catering",
    "light refreshments",
    "meals provided",
]
NEGATION_PHRASES = [
    "no food",
    "food not provided",
    "no refreshments",
    "refreshments not provided",
    "food will not be provided",
    "refreshments will not be provided",
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


# ----------------------------
# HTTP client
# ----------------------------
class HttpClient:
    def __init__(
        self, user_agent: str = DEFAULT_USER_AGENT, timeout: int = DEFAULT_TIMEOUT
    ):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": user_agent})
        self.timeout = timeout

    def get(self, url: str, **kwargs) -> requests.Response:
        return self.s.get(url, timeout=self.timeout, **kwargs)


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

    # Common fallbacks
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y %I:%M %p", "%m/%d/%Y"):
        try:
            d = dt.datetime.strptime(s, fmt)
            return _to_utc_aware(d)
        except Exception:
            continue

    return None


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
    t = (text or "").lower()
    if any(neg in t for neg in NEGATION_PHRASES):
        return False
    return any(k in t for k in FREE_FOOD_KEYWORDS)


def _stable_event_id(title: str, start_iso: str, location: str, source_url: str) -> str:
    key = f"{title.strip().lower()}|{start_iso}|{location.strip().lower()}|{source_url}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def _within_lookahead(start_iso: str, days_lookahead: int) -> bool:
    now = dt.datetime.now(UTC)
    end_window = now + dt.timedelta(days=days_lookahead)
    sdt = _try_parse_dt(start_iso.replace("Z", "+00:00"))
    if not sdt:
        return False
    return now <= sdt <= end_window


# ----------------------------
# Crawl helpers
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


def _extract_links(html: str, base_url: str) -> List[str]:
    # Avoid XMLParsedAsHTMLWarning spam for non-html content
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

    soup = BeautifulSoup(html, "html.parser")
    out: List[str] = []
    for a in soup.find_all("a", href=True):
        u = _normalize_url(base_url, a["href"])
        if u:
            out.append(u)
    return list(dict.fromkeys(out))


# ----------------------------
# Localist event extraction (NO LLM)
# ----------------------------
def _extract_localist_event_from_jsonld(
    html: str, page_url: str
) -> Optional[Dict[str, Any]]:
    """
    Localist pages almost always include JSON-LD Event.
    We'll extract title/start/end/location/description locally.
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
# Gemini: confirm free food + proof (SMALL request)
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
- If it only says "refreshments provided" without saying free, return FALSE.
- If it says "no food"/"food not provided", return FALSE.
- Be conservative.
"""


def _gemini_confirm_free_food(
    page_url: str, title: str, location: str, start_iso: str, description: str
) -> Tuple[bool, float, str]:
    if not client:
        return False, 0.0, ""

    # keep payload tiny and relevant
    snippet = f"""URL: {page_url}
TITLE: {title}
WHEN (UTC): {start_iso}
WHERE: {location}
DESCRIPTION: {description[:2500]}
"""

    # The google-genai client doesn't expose a per-call timeout param in the same way requests does,
    # so we enforce "won't hang forever" behavior by limiting retries + keeping payload small.
    # (The underlying httpx timeout is usually bounded, but your stack showed it could stall.)
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
        except Exception:
            continue

    return False, 0.0, ""


# ----------------------------
# Main: feed a URL, crawl, return confirmed free food events
# ----------------------------
def crawl_confirmed_free_food_events(
    seed_url: str,
    days_lookahead: int = DEFAULT_DAYS_LOOKAHEAD,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    polite_delay_s: float = DEFAULT_POLITE_DELAY_S,
    min_confidence: float = 0.60,
    restrict_to_same_site: bool = True,
) -> List[Dict[str, Any]]:
    """
    - Crawls from seed URL
    - Extracts event fields locally (JSON-LD fast path)
    - Uses Gemini ONLY to confirm free food + extract proof
    - Returns only events with: free food proof + location + date/time
    """
    if not client:
        raise RuntimeError("GEMINI_API_KEY not set. Needed for free-food confirmation.")

    http = HttpClient()
    queue: List[Tuple[str, int]] = [(seed_url, 0)]
    visited: Set[str] = set()

    results: Dict[str, FreeFoodEvent] = {}

    while queue and len(visited) < max_pages:
        url, depth = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        if depth > max_depth:
            continue

        try:
            r = http.get(url)
            if r.status_code >= 400:
                continue
            content_type = (r.headers.get("content-type") or "").lower()
            html = r.text
        except Exception:
            continue

        # Skip obvious non-html/xml docs for crawling (pdf/images/etc)
        if any(x in content_type for x in ["application/pdf", "image/", "video/"]):
            continue

        # Add links
        try:
            for link in _extract_links(html, url):
                if restrict_to_same_site and not _same_site(seed_url, link):
                    continue
                if link not in visited:
                    queue.append((link, depth + 1))
        except Exception:
            pass

        # Extract Localist Event from JSON-LD if present
        ev = _extract_localist_event_from_jsonld(html, url)
        if not ev:
            time.sleep(polite_delay_s)
            continue

        # Require location + date/time
        title = ev["title"]
        start_iso = ev["start_iso"]
        end_iso = ev["end_iso"]
        location = ev["location"]
        description = ev["description"] or ""

        if not location.strip():
            time.sleep(polite_delay_s)
            continue

        if not _within_lookahead(start_iso, days_lookahead):
            time.sleep(polite_delay_s)
            continue

        # Heuristic prefilter: only ask Gemini if page likely mentions food
        # (This prevents hangs + saves money.)
        page_text = _clean_text_from_html(html)
        if not _keyword_might_have_free_food(
            page_text
        ) and not _keyword_might_have_free_food(description):
            time.sleep(polite_delay_s)
            continue

        # Confirm with Gemini (small payload)
        has_food, conf, proof = _gemini_confirm_free_food(
            page_url=url,
            title=title,
            location=location,
            start_iso=start_iso,
            description=page_text if page_text else description,
        )

        if not has_food or conf < min_confidence or not proof:
            time.sleep(polite_delay_s)
            continue

        event_id = _stable_event_id(title, start_iso, location, url)
        results[event_id] = FreeFoodEvent(
            source_url=url,
            title=title,
            start=start_iso,
            end=end_iso,
            location=location,
            description=description if description else None,
            proof=proof,
            confidence=conf,
            event_id=event_id,
        )

        time.sleep(polite_delay_s)

    out = [asdict(v) for v in results.values()]
    out.sort(key=lambda x: x["start"])
    return out


# ----------------------------
# Runner
# ----------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python __main__.py <seed_url>")
        raise SystemExit(2)

    seed = sys.argv[1]
    events = crawl_confirmed_free_food_events(
        seed_url=seed,
        days_lookahead=90,
        max_pages=80,
        max_depth=1,
        min_confidence=0.65,
        restrict_to_same_site=True,
    )

    print(f"Confirmed free-food events found: {len(events)}")
    print(json.dumps(events[:20], indent=2))
