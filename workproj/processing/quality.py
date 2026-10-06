"""Data-quality profiling module for scraped records."""

from __future__ import annotations

import collections
import statistics
from typing import Any

import config


def build_quality_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate comprehensive data quality and profiling metrics from records.

    Pure function with no external I/O, guaranteed never to raise exceptions.

    Args:
        records: List of cleaned, validated record dictionaries.

    Returns:
        Structured dictionary matching the data quality report schema.
    """
    total_records = len(records)

    # 1. Null counts for every column in config.COLUMNS (treat None and "" as null)
    null_counts: dict[str, dict[str, Any]] = {}
    for col in config.COLUMNS:
        n_count = sum(1 for r in records if r.get(col) is None or r.get(col) == "")
        n_pct = round((n_count / total_records * 100), 1) if total_records > 0 else 0.0
        null_counts[col] = {
            "null": n_count,
            "null_pct": n_pct,
        }

    # 2. Books profiling
    books = [r for r in records if r.get("source") == config.BOOKS_SOURCE]
    b_count = len(books)

    price_stats: dict[str, float] | None = None
    if b_count > 0:
        valid_prices: list[float] = []
        for r in books:
            p_val = r.get("price")
            if p_val is not None and p_val != "":
                try:
                    valid_prices.append(float(p_val))
                except (ValueError, TypeError):
                    continue

        if valid_prices:
            price_stats = {
                "min": round(min(valid_prices), 2),
                "max": round(max(valid_prices), 2),
                "mean": round(statistics.mean(valid_prices), 2),
                "median": round(statistics.median(valid_prices), 2),
            }

    rating_dist: dict[str, int] = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    categories_list: list[str] = []
    for r in books:
        r_val = str(r.get("rating"))
        if r_val in rating_dist:
            rating_dist[r_val] += 1

        cat = r.get("category")
        if cat and isinstance(cat, str) and cat.strip():
            categories_list.append(cat.strip())

    cat_counter = collections.Counter(categories_list)
    categories_total = len(cat_counter)
    # Sort by descending count, break ties alphabetically
    sorted_categories = sorted(cat_counter.items(), key=lambda item: (-item[1], item[0]))
    top_categories = [{"category": c, "count": cnt} for c, cnt in sorted_categories[:10]]

    books_summary: dict[str, Any] = {
        "count": b_count,
        "price": price_stats,
        "rating_distribution": rating_dist,
        "categories_total": categories_total,
        "top_categories": top_categories,
    }

    # 3. Quotes profiling
    quotes = [r for r in records if r.get("source") == config.QUOTES_SOURCE]
    q_count = len(quotes)

    authors_list: list[str] = []
    tags_list: list[str] = []
    for r in quotes:
        author = r.get("author")
        if author and isinstance(author, str) and author.strip():
            authors_list.append(author.strip())

        tag_field = r.get("tags")
        if tag_field and isinstance(tag_field, str):
            for t in tag_field.split(";"):
                cleaned_tag = t.strip()
                if cleaned_tag:
                    tags_list.append(cleaned_tag)

    author_counter = collections.Counter(authors_list)
    unique_authors = len(author_counter)
    sorted_authors = sorted(author_counter.items(), key=lambda item: (-item[1], item[0]))
    top_authors = [{"author": a, "count": cnt} for a, cnt in sorted_authors[:10]]

    tag_counter = collections.Counter(tags_list)
    unique_tags = len(tag_counter)
    sorted_tags = sorted(tag_counter.items(), key=lambda item: (-item[1], item[0]))
    top_tags = [{"tag": t, "count": cnt} for t, cnt in sorted_tags[:10]]

    quotes_summary: dict[str, Any] = {
        "count": q_count,
        "unique_authors": unique_authors,
        "top_authors": top_authors,
        "unique_tags": unique_tags,
        "top_tags": top_tags,
    }

    return {
        "total_records": total_records,
        "null_counts": null_counts,
        "books": books_summary,
        "quotes": quotes_summary,
    }
