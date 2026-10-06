"""Deduplication module using SHA-256 composite record fingerprinting."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Optional

import config


def normalize_for_key(text: Optional[str]) -> str:
    """Normalize text for deduplication: lowercase, strip punctuation, and collapse spaces.

    Args:
        text: Input string or None.

    Returns:
        Cleaned, punctuation-free string, or empty string if input was None or blank.
    """
    if text is None or not isinstance(text, str):
        return ""
    # Lowercase
    lowered = text.lower()
    # Remove punctuation using [^\w\s]
    no_punct = re.sub(r"[^\w\s]", "", lowered)
    # Collapse whitespace
    collapsed = " ".join(no_punct.split())
    return collapsed


def make_fingerprint(rec: dict[str, Any]) -> str:
    """Generate SHA-256 fingerprint hex digest for a record.

    Books key: source | title
    Quotes key: source | author | full quote text
    Each component is normalized with normalize_for_key.

    Args:
        rec: Record dictionary.

    Returns:
        64-character SHA-256 hexadecimal string.
    """
    source = rec.get("source") or ""

    if source == config.BOOKS_SOURCE:
        parts = [source, rec.get("name_or_title")]
    elif source == config.QUOTES_SOURCE:
        parts = [source, rec.get("author"), rec.get("name_or_title")]
    else:
        # Fallback for generic records
        parts = [source, rec.get("name_or_title")]

    normalized_parts = [normalize_for_key(p) for p in parts]
    composite_key = "|".join(normalized_parts)
    return hashlib.sha256(composite_key.encode("utf-8")).hexdigest()


def find_duplicates(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Partition records into unique and duplicate lists while preserving order.

    The first occurrence of each unique fingerprint is retained; subsequent
    occurrences are classified as duplicates.

    Args:
        records: List of record dictionaries.

    Returns:
        Tuple of (unique_records, duplicate_records).
    """
    seen_fingerprints: set[str] = set()
    unique: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []

    for rec in records:
        fp = make_fingerprint(rec)
        if fp in seen_fingerprints:
            duplicates.append(rec)
        else:
            seen_fingerprints.add(fp)
            unique.append(rec)

    return unique, duplicates
