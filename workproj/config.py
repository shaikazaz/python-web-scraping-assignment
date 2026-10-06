"""Central configuration for the scraping and data pipeline."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"
CHECKPOINT_DIR = BASE_DIR / "checkpoints"
STATE_DIR = BASE_DIR / "state"

for _directory in (OUTPUT_DIR, LOG_DIR):
    _directory.mkdir(parents=True, exist_ok=True)

BOOKS_URL = "https://books.toscrape.com/"
QUOTES_URL = "https://quotes.toscrape.com/"
BOOKS_SOURCE = "Books to Scrape"
QUOTES_SOURCE = "Quotes to Scrape"
VALID_SOURCES = {BOOKS_SOURCE, QUOTES_SOURCE}

USER_AGENT = "ScrapingAssignment/1.0 (learning project)"
REQUEST_DELAY = 0.5
TIMEOUT = 10.0
MAX_RETRIES = 3
BACKOFF_FACTOR = 1.0
RETRY_STATUS = [429, 500, 502, 503, 504]
MAX_PAGES: int | None = None
MAX_CONSECUTIVE_FAILURES = 3

COLUMNS = [
    "source", "name_or_title", "category", "price", "rating", "author",
    "tags", "source_url", "scraped_at", "description", "availability", "author_url",
]


def _warn_invalid(name: str, raw: str, default: Any, reason: str) -> Any:
    logging.getLogger(__name__).warning(
        "Invalid %s=%r (%s); using default %r", name, raw, reason, default
    )
    return default


def _env_float(name: str, default: float, minimum: float = 0.0, strictly_positive: bool = False) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
        if strictly_positive and value <= 0:
            raise ValueError("must be > 0")
        if not strictly_positive and value < minimum:
            raise ValueError(f"must be >= {minimum}")
        return value
    except (TypeError, ValueError) as exc:
        return _warn_invalid(name, raw, default, str(exc))


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
        if value < minimum:
            raise ValueError(f"must be >= {minimum}")
        return value
    except (TypeError, ValueError) as exc:
        return _warn_invalid(name, raw, default, str(exc))


def _env_choice(name: str, default: str, choices: set[str]) -> str:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    value = raw.strip().upper()
    if value not in choices:
        return _warn_invalid(name, raw, default, f"must be one of {sorted(choices)}")
    return value


REQUEST_DELAY = _env_float("SCRAPER_DELAY", REQUEST_DELAY, minimum=0.0)
TIMEOUT = _env_float("SCRAPER_TIMEOUT", TIMEOUT, strictly_positive=True)
MAX_RETRIES = _env_int("SCRAPER_MAX_RETRIES", MAX_RETRIES, minimum=0)
OUTPUT_DIR = Path(os.getenv("SCRAPER_OUTPUT_DIR", str(OUTPUT_DIR))).expanduser()
LOG_LEVEL = _env_choice("SCRAPER_LOG_LEVEL", "INFO", {"DEBUG", "INFO", "WARNING", "ERROR"})

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
