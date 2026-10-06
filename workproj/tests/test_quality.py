"""Unit tests for the data-quality profiling module."""

import config
from processing.quality import build_quality_report


def test_empty_input() -> None:
    """Empty record list returns zero counts and None for price stats."""
    report = build_quality_report([])
    assert report["total_records"] == 0
    assert report["books"]["count"] == 0
    assert report["books"]["price"] is None
    assert report["books"]["categories_total"] == 0
    assert report["books"]["top_categories"] == []
    assert report["quotes"]["count"] == 0
    assert report["quotes"]["unique_authors"] == 0
    assert report["quotes"]["unique_tags"] == 0
    for col in config.COLUMNS:
        assert report["null_counts"][col]["null"] == 0
        assert report["null_counts"][col]["null_pct"] == 0.0


def test_null_counting() -> None:
    """Treats None and empty strings as null and computes accurate percentages."""
    records = [
        {"source": config.BOOKS_SOURCE, "price": 10.0, "description": "Good", "category": ""},
        {"source": config.BOOKS_SOURCE, "price": None, "description": None, "category": "Fiction"},
        {"source": config.BOOKS_SOURCE, "price": 20.0, "description": "", "category": None},
        {"source": config.BOOKS_SOURCE, "price": 30.0, "description": "Present", "category": "Fiction"},
    ]
    report = build_quality_report(records)
    assert report["total_records"] == 4
    # price has 1 null out of 4 (25.0%)
    assert report["null_counts"]["price"] == {"null": 1, "null_pct": 25.0}
    # description has 2 nulls (1 None, 1 "") out of 4 (50.0%)
    assert report["null_counts"]["description"] == {"null": 2, "null_pct": 50.0}
    # category has 2 nulls (1 None, 1 "") out of 4 (50.0%)
    assert report["null_counts"]["category"] == {"null": 2, "null_pct": 50.0}


def test_price_stats() -> None:
    """Computes min, max, mean, and median rounded to 2 decimal places."""
    records = [
        {"source": config.BOOKS_SOURCE, "price": 10.50},
        {"source": config.BOOKS_SOURCE, "price": 20.00},
        {"source": config.BOOKS_SOURCE, "price": 30.25},
        {"source": config.BOOKS_SOURCE, "price": 40.00},
    ]
    report = build_quality_report(records)
    price = report["books"]["price"]
    assert price is not None
    assert price["min"] == 10.50
    assert price["max"] == 40.00
    assert price["mean"] == 25.19
    assert price["median"] == 25.12


def test_rating_distribution() -> None:
    """Accurately tallies rating distribution buckets 1 to 5."""
    records = [
        {"source": config.BOOKS_SOURCE, "rating": 1},
        {"source": config.BOOKS_SOURCE, "rating": 3},
        {"source": config.BOOKS_SOURCE, "rating": 3},
        {"source": config.BOOKS_SOURCE, "rating": 5},
    ]
    report = build_quality_report(records)
    dist = report["books"]["rating_distribution"]
    assert dist == {"1": 1, "2": 0, "3": 2, "4": 0, "5": 1}


def test_top_ordering_with_ties() -> None:
    """Ties in frequency counts are resolved alphabetically."""
    records = [
        {"source": config.BOOKS_SOURCE, "category": "Science"},
        {"source": config.BOOKS_SOURCE, "category": "Art"},
        {"source": config.BOOKS_SOURCE, "category": "Art"},
        {"source": config.BOOKS_SOURCE, "category": "Science"},
        {"source": config.BOOKS_SOURCE, "category": "History"},
    ]
    report = build_quality_report(records)
    top_cats = report["books"]["top_categories"]
    # Art and Science both have count 2. Art must appear before Science.
    assert top_cats[0] == {"category": "Art", "count": 2}
    assert top_cats[1] == {"category": "Science", "count": 2}
    assert top_cats[2] == {"category": "History", "count": 1}


def test_books_only_input() -> None:
    """Books-only input populates books stats and zeroes out quotes."""
    records = [
        {"source": config.BOOKS_SOURCE, "price": 15.00, "rating": 4, "category": "Tech"}
    ]
    report = build_quality_report(records)
    assert report["books"]["count"] == 1
    assert report["quotes"]["count"] == 0
    assert report["quotes"]["unique_authors"] == 0
    assert report["quotes"]["unique_tags"] == 0


def test_quotes_only_input() -> None:
    """Quotes-only input populates quotes authors/tags and leaves books price as None."""
    records = [
        {"source": config.QUOTES_SOURCE, "author": "Mark Twain", "tags": "humor;books"},
        {"source": config.QUOTES_SOURCE, "author": "Mark Twain", "tags": "life"},
        {"source": config.QUOTES_SOURCE, "author": "Albert Einstein", "tags": "science;life"},
    ]
    report = build_quality_report(records)
    assert report["books"]["count"] == 0
    assert report["books"]["price"] is None
    assert report["quotes"]["count"] == 3
    assert report["quotes"]["unique_authors"] == 2
    assert report["quotes"]["top_authors"][0] == {"author": "Mark Twain", "count": 2}
    assert report["quotes"]["top_authors"][1] == {"author": "Albert Einstein", "count": 1}
    # Tags: humor (1), books (1), life (2), science (1)
    assert report["quotes"]["unique_tags"] == 4
    top_tags = report["quotes"]["top_tags"]
    assert top_tags[0] == {"tag": "life", "count": 2}
    # books, humor, science all have count 1 -> sorted alphabetically
    assert top_tags[1] == {"tag": "books", "count": 1}
    assert top_tags[2] == {"tag": "humor", "count": 1}
    assert top_tags[3] == {"tag": "science", "count": 1}
