"""Unit tests for the data cleaning and transformation module."""

import config
from processing.cleaning import (
    clean_book,
    clean_price,
    clean_quote,
    clean_rating,
    clean_tags,
    clean_text,
    normalize_url,
    strip_quotes,
)


def test_clean_text() -> None:
    """Test text cleaning, whitespace collapsing, and non-breaking space replacement."""
    assert clean_text("Hello World") == "Hello World"
    assert clean_text("  Spaced   out \t text \n") == "Spaced out text"
    assert clean_text("Non\xa0breaking\xa0space") == "Non breaking space"
    assert clean_text("") is None
    assert clean_text("    ") is None
    assert clean_text(None) is None


def test_strip_quotes() -> None:
    """Test stripping straight and curly quotation marks."""
    assert strip_quotes('"Quoted string"') == "Quoted string"
    assert strip_quotes("“Curly quotes”") == "Curly quotes"
    assert strip_quotes("\u201cUnicode curly\u201d") == "Unicode curly"
    assert strip_quotes("  “ Trimmed quotes ”  ") == "Trimmed quotes"
    assert strip_quotes("") is None
    assert strip_quotes(None) is None


def test_clean_price() -> None:
    """Test price parsing from various currency strings and malformed encodings."""
    assert clean_price("£51.77") == 51.77
    assert clean_price("Â£51.77") == 51.77
    assert clean_price("$19.99") == 19.99
    assert clean_price("1,250.50") == 1250.50
    assert clean_price(42) == 42.0
    assert clean_price("Free") is None
    assert clean_price("") is None
    assert clean_price(None) is None


def test_clean_rating() -> None:
    """Test word ratings conversion and resilience against unknown words."""
    assert clean_rating("star-rating One") == 1
    assert clean_rating("star-rating Three") == 3
    assert clean_rating("FIVE") == 5
    assert clean_rating("Rating: Two stars") == 2
    assert clean_rating("star-rating Zero") is None
    assert clean_rating("star-rating Ten") is None
    assert clean_rating("unknown") is None
    assert clean_rating("") is None
    assert clean_rating(None) is None


def test_clean_tags() -> None:
    """Test tag list deduplication, lowercasing, sorting, and semicolon joining."""
    raw_list = ["World", "deep-thoughts", "World", "thinking", "  change  "]
    assert clean_tags(raw_list) == "change;deep-thoughts;thinking;world"
    assert clean_tags("banana; apple; Cherry ;apple") == "apple;banana;cherry"
    assert clean_tags([]) is None
    assert clean_tags(["", "   "]) is None
    assert clean_tags(None) is None


def test_normalize_url() -> None:
    """Test URL normalization, relative resolution, and scheme filtering."""
    assert normalize_url("https://quotes.toscrape.com/page/1/") == "https://quotes.toscrape.com/page/1/"
    assert (
        normalize_url("/author/Albert-Einstein", base="https://quotes.toscrape.com/")
        == "https://quotes.toscrape.com/author/Albert-Einstein"
    )
    # Reject non-http schemes
    assert normalize_url("ftp://example.com/file.txt") is None
    assert normalize_url("javascript:void(0)") is None
    # Relative URL without base is missing netloc
    assert normalize_url("/relative/path") is None
    assert normalize_url("") is None
    assert normalize_url(None) is None


def test_clean_book_contract() -> None:
    """Ensure clean_book produces every key in config.COLUMNS."""
    raw_book = {
        "title": "A Light in the Attic",
        "source_url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
        "price_raw": "£51.77",
        "rating_raw": "star-rating Three",
        "availability_raw": "In stock (22 available)",
        "category_raw": "Poetry",
        "description_raw": "A classic poetry collection.",
    }
    cleaned = clean_book(raw_book)

    # Validate all columns exist
    for col in config.COLUMNS:
        assert col in cleaned

    assert cleaned["source"] == config.BOOKS_SOURCE
    assert cleaned["name_or_title"] == "A Light in the Attic"
    assert cleaned["price"] == 51.77
    assert cleaned["rating"] == 3
    assert cleaned["category"] == "Poetry"
    assert cleaned["author"] is None
    assert cleaned["tags"] is None
    assert cleaned["scraped_at"] is not None


def test_clean_quote_contract() -> None:
    """Ensure clean_quote produces every key in config.COLUMNS."""
    raw_quote = {
        "quote_raw": "“The world as we have created it...”",
        "author_raw": "Albert Einstein",
        "tags_raw": ["change", "world"],
        "author_url": "/author/Albert-Einstein",
        "source_url": "https://quotes.toscrape.com/page/1/",
    }
    cleaned = clean_quote(raw_quote)

    for col in config.COLUMNS:
        assert col in cleaned

    assert cleaned["source"] == config.QUOTES_SOURCE
    assert cleaned["name_or_title"] == "The world as we have created it..."
    assert cleaned["author"] == "Albert Einstein"
    assert cleaned["tags"] == "change;world"
    assert cleaned["author_url"] == "https://quotes.toscrape.com/author/Albert-Einstein"
    assert cleaned["price"] is None
    assert cleaned["rating"] is None
    assert cleaned["scraped_at"] is not None
