"""Validation rules for cleaned book and quote records."""

from __future__ import annotations

from typing import Any

import config


def validate_record(rec: dict[str, Any]) -> list[str]:
    """Validate a cleaned record dictionary against required schemas and constraints.

    Args:
        rec: Cleaned record dictionary.

    Returns:
        List of failure reason codes (empty list if valid).
    """
    reasons: list[str] = []
    source = rec.get("source")

    if source not in config.VALID_SOURCES:
        reasons.append("invalid_source")

    name_or_title = rec.get("name_or_title")
    if not name_or_title or not isinstance(name_or_title, str) or not name_or_title.strip():
        reasons.append("missing_name_or_title")

    source_url = rec.get("source_url")
    if not source_url or not isinstance(source_url, str) or not (
        source_url.startswith("http://") or source_url.startswith("https://")
    ):
        reasons.append("invalid_source_url")

    scraped_at = rec.get("scraped_at")
    if not scraped_at or not isinstance(scraped_at, str):
        reasons.append("invalid_scraped_at")

    if source == config.BOOKS_SOURCE:
        price = rec.get("price")
        if price is None or not isinstance(price, (int, float)) or price < 0:
            reasons.append("invalid_price")

        rating = rec.get("rating")
        if rating is None or not isinstance(rating, int) or rating not in (1, 2, 3, 4, 5):
            reasons.append("invalid_rating")

        category = rec.get("category")
        if not category or not isinstance(category, str) or not category.strip():
            reasons.append("missing_category")

    elif source == config.QUOTES_SOURCE:
        author = rec.get("author")
        if not author or not isinstance(author, str) or not author.strip():
            reasons.append("missing_author")

        author_url = rec.get("author_url")
        if author_url is not None and (
            not isinstance(author_url, str)
            or not (author_url.startswith("http://") or author_url.startswith("https://"))
        ):
            reasons.append("invalid_author_url")

    return reasons
