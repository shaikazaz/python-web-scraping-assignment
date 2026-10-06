"""Data cleaning and normalization functions for scraped book and quote records.

Pure functions only: no file access, no network calls, and guaranteed never
to raise exceptions on invalid or malformed input.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional, Union
from urllib.parse import urljoin, urlparse

import config


def clean_text(value: Optional[str]) -> Optional[str]:
    """Clean string by replacing non-breaking spaces, collapsing whitespace, and stripping.

    Args:
        value: Input string or None.

    Returns:
        Cleaned collapsed string, or None if input was None or empty.
    """
    if value is None or not isinstance(value, str):
        return None
    normalized = value.replace("\xa0", " ")
    collapsed = " ".join(normalized.split())
    return collapsed if collapsed else None


def strip_quotes(value: Optional[str]) -> Optional[str]:
    """Strip curly and straight quotation marks from the start and end of text.

    Args:
        value: Input quote text or None.

    Returns:
        Cleaned text with outer quotation marks stripped, or None.
    """
    cleaned = clean_text(value)
    if not cleaned:
        return None
    # Strip straight double quotes and unicode curly quotation marks
    stripped = cleaned.strip('"\'\u201c\u201d\u2018\u2019«»')
    return clean_text(stripped)


def clean_price(raw: Optional[Union[str, float, int]]) -> Optional[float]:
    """Extract and parse floating-point price from currency strings.

    Args:
        raw: Raw price string (e.g. '£51.77', 'Â£51.77') or numeric.

    Returns:
        Rounded float value (2 decimal places) or None if no numeric price found.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return round(float(raw), 2)
    if not isinstance(raw, str):
        return None

    # Remove commas and search for the first valid decimal number
    sanitized = raw.replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)", sanitized)
    if match:
        try:
            return round(float(match.group(1)), 2)
        except ValueError:
            return None
    return None


def clean_rating(raw: Optional[Union[str, int, float]]) -> Optional[int]:
    """Convert written word ratings (one through five) or integers into 1-5 scale.

    Args:
        raw: Rating input string (e.g. 'star-rating Three') or numeric.

    Returns:
        Integer rating from 1 to 5, or None if unrecognized.
    """
    if raw is None:
        return None
    if isinstance(raw, int) and 1 <= raw <= 5:
        return raw

    word_map = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
    }

    if isinstance(raw, str):
        words = re.findall(r"[a-zA-Z]+", raw.lower())
        for word in words:
            if word in word_map:
                return word_map[word]

    return None


def clean_tags(tags: Optional[Union[list[Any], str]]) -> Optional[str]:
    """Normalize, lowercase, deduplicate, sort, and join tag items with semicolons.

    Args:
        tags: List of tag strings or a semicolon-separated string.

    Returns:
        Semicolon-separated sorted tag string, or None if empty.
    """
    if tags is None:
        return None

    raw_items: list[str] = []
    if isinstance(tags, list):
        for item in tags:
            if isinstance(item, str):
                raw_items.append(item)
    elif isinstance(tags, str):
        raw_items = tags.split(";")
    else:
        return None

    cleaned_set: set[str] = set()
    for item in raw_items:
        clean_item = clean_text(item)
        if clean_item:
            cleaned_set.add(clean_item.lower())

    if not cleaned_set:
        return None

    sorted_tags = sorted(cleaned_set)
    return ";".join(sorted_tags)


def normalize_url(url: Optional[str], base: Optional[str] = None) -> Optional[str]:
    """Resolve relative URLs against a base and validate http/https scheme.

    Args:
        url: The candidate URL string.
        base: Optional base URL for resolving relative links.

    Returns:
        Absolute normalized URL string, or None if invalid scheme/netloc.
    """
    cleaned_url = clean_text(url)
    if not cleaned_url:
        return None

    if base:
        cleaned_base = clean_text(base)
        if cleaned_base:
            cleaned_url = urljoin(cleaned_base, cleaned_url)

    try:
        parsed = urlparse(cleaned_url)
        if parsed.scheme.lower() in ("http", "https") and parsed.netloc:
            return parsed.geturl()
    except Exception:
        return None

    return None


def clean_book(raw: dict[str, Any]) -> dict[str, Any]:
    """Transform a raw scraped book dictionary into a standardized cleaned record.

    Args:
        raw: Raw book dictionary returned by BooksScraper.

    Returns:
        Dictionary adhering to config.COLUMNS schema.
    """
    scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    return {
        "source": config.BOOKS_SOURCE,
        "name_or_title": clean_text(raw.get("title")),
        "category": clean_text(raw.get("category_raw")),
        "price": clean_price(raw.get("price_raw")),
        "rating": clean_rating(raw.get("rating_raw")),
        "author": None,
        "tags": None,
        "source_url": normalize_url(raw.get("source_url")),
        "scraped_at": scraped_at,
        "description": clean_text(raw.get("description_raw")),
        "availability": clean_text(raw.get("availability_raw")),
        "author_url": None,
    }


def clean_quote(raw: dict[str, Any]) -> dict[str, Any]:
    """Transform a raw scraped quote dictionary into a standardized cleaned record.

    Args:
        raw: Raw quote dictionary returned by QuotesScraper.

    Returns:
        Dictionary adhering to config.COLUMNS schema.
    """
    scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    page_url = raw.get("source_url")

    return {
        "source": config.QUOTES_SOURCE,
        "name_or_title": strip_quotes(raw.get("quote_raw")),
        "category": None,
        "price": None,
        "rating": None,
        "author": clean_text(raw.get("author_raw")),
        "tags": clean_tags(raw.get("tags_raw")),
        "source_url": normalize_url(page_url),
        "scraped_at": scraped_at,
        "description": None,
        "availability": None,
        "author_url": normalize_url(raw.get("author_url"), base=page_url),
    }
