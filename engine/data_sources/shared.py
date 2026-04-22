"""Shared helpers for the ESPN scraper."""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

LOGGER_NAME = "golium.espn"
logger = logging.getLogger(LOGGER_NAME)

DEFAULT_TIMEOUT = 15
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 1.5
USER_AGENT = "GoliumESPN/1.0 (+https://example.local)"

BASE_SITE_API = "https://site.api.espn.com/apis/site/v2/sports/soccer"
BASE_STANDINGS_API = "https://site.api.espn.com/apis/v2/sports/soccer"

LEAGUES = {
    "laliga": {
        "key": "laliga",
        "name": "LaLiga",
        "slug": "esp.1",
    },
    "hypermotion": {
        "key": "hypermotion",
        "name": "LaLiga Hypermotion",
        "slug": "esp.2",
    },
    "epl": {
        "key": "epl",
        "name": "Premier League",
        "slug": "eng.1",
    },
    "bundesliga": {
        "key": "bundesliga",
        "name": "Bundesliga",
        "slug": "ger.1",
    },
    "seriea": {
        "key": "seriea",
        "name": "Serie A",
        "slug": "ita.1",
    },
}


class FetchError(RuntimeError):
    """Raised when a remote JSON resource cannot be fetched."""


def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp without randomness."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_url(base: str, params: dict[str, Any] | None = None) -> str:
    """Build a URL with query params if provided."""
    if not params:
        return base
    return f"{base}?{urlencode(params)}"


def fetch_json(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
) -> dict[str, Any]:
    """Fetch JSON with retries, timeout and lightweight logging."""
    last_error: Exception | None = None
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    for attempt in range(1, retries + 1):
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
                data = json.loads(payload)
                if isinstance(data, dict):
                    return data
                raise FetchError(f"Expected dict JSON from {url}, got {type(data).__name__}")
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, FetchError) as exc:
            last_error = exc
            logger.warning("Fetch attempt %s/%s failed for %s: %s", attempt, retries, url, exc)
            if attempt < retries:
                time.sleep(backoff_seconds * attempt)

    raise FetchError(f"Failed to fetch JSON from {url}: {last_error}")


def normalize_team_name(name: str) -> str:
    """Normalize team names for internal matching."""
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = text.replace("&", " and ")
    text = re.sub(r"\b(cf|fc|sc|cd|sd|rcd|rc|ac|ud|deportivo|club|the)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def safe_path(path: str | Path) -> Path:
    """Ensure parent directories exist and return a Path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def save_json(path: str | Path, payload: dict[str, Any]) -> Path:
    """Persist JSON to disk with stable formatting."""
    output_path = safe_path(path)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")
    return output_path


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logging once for CLI execution."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
