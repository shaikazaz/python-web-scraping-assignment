"""Unit tests for the record fingerprinting and deduplication module."""

import config
from processing.deduplication import (
    find_duplicates,
    make_fingerprint,
    normalize_for_key,
)


def test_normalize_for_key() -> None:
    """Test lowercasing, punctuation stripping, and whitespace collapsing."""
    assert normalize_for_key("Hello, World!") == "hello world"
    assert normalize_for_key("  Don't   panic...  ") == "dont panic"
    assert normalize_for_key("") == ""
    assert normalize_for_key(None) == ""


def test_case_and_whitespace_duplicates() -> None:
    """Case (1): Example Book Title with case and space variations yields 1 unique, 2 duplicates."""
    records = [
        {"source": config.BOOKS_SOURCE, "name_or_title": "Example Book Title", "id": 1},
        {"source": config.BOOKS_SOURCE, "name_or_title": "  Example Book Title ", "id": 2},
        {"source": config.BOOKS_SOURCE, "name_or_title": "EXAMPLE BOOK TITLE", "id": 3},
    ]
    unique, duplicates = find_duplicates(records)

    assert len(unique) == 1
    assert len(duplicates) == 2
    assert unique[0]["id"] == 1
    assert [d["id"] for d in duplicates] == [2, 3]


def test_same_quote_different_authors_not_duplicate() -> None:
    """Case (2): Identical quote text by two different authors must NOT be duplicates."""
    quote_text = "Be yourself; everyone else is already taken."
    records = [
        {
            "source": config.QUOTES_SOURCE,
            "name_or_title": quote_text,
            "author": "Oscar Wilde",
        },
        {
            "source": config.QUOTES_SOURCE,
            "name_or_title": quote_text,
            "author": "Anonymous",
        },
    ]
    unique, duplicates = find_duplicates(records)

    assert len(unique) == 2
    assert len(duplicates) == 0


def test_punctuation_differences_ignored() -> None:
    """Case (3): Punctuation variations in book titles or quotes are identified as duplicates."""
    records = [
        {"source": config.BOOKS_SOURCE, "name_or_title": "Don't Look Back!"},
        {"source": config.BOOKS_SOURCE, "name_or_title": "Dont Look Back"},
    ]
    unique, duplicates = find_duplicates(records)

    assert len(unique) == 1
    assert len(duplicates) == 1


def test_order_preserved() -> None:
    """Case (4): Original ordering is preserved in both unique and duplicate partitions."""
    records = [
        {"source": config.BOOKS_SOURCE, "name_or_title": "Book Alpha", "order": 1},
        {"source": config.BOOKS_SOURCE, "name_or_title": "Book Beta", "order": 2},
        {"source": config.BOOKS_SOURCE, "name_or_title": "Book Alpha", "order": 3},
        {"source": config.BOOKS_SOURCE, "name_or_title": "Book Gamma", "order": 4},
        {"source": config.BOOKS_SOURCE, "name_or_title": "Book Beta", "order": 5},
    ]
    unique, duplicates = find_duplicates(records)

    assert [r["order"] for r in unique] == [1, 2, 4]
    assert [r["order"] for r in duplicates] == [3, 5]
