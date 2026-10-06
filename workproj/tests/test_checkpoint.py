from pathlib import Path

from bs4 import BeautifulSoup

import config
from scrapers.quotes_scraper import QuotesScraper
from utils.checkpoint import PageCheckpoint


def test_checkpoint_round_trip_and_slug(tmp_path: Path):
    cp = PageCheckpoint("https://example.com/", "QuotesScraper", tmp_path)
    cp.save([{"x": 1}], "https://example.com/page/2/", 2, complete=False, had_failures=False)
    data = cp.load()
    assert data and data["records"] == [{"x": 1}]
    assert data["next_page"] == 2
    assert cp.path.name.endswith(".pages.json")


def test_complete_checkpoint_returns_without_fetch(tmp_path: Path):
    cp = PageCheckpoint("https://quotes.toscrape.com/", "QuotesScraper", tmp_path)
    cp.save([{"quote_raw": "saved"}], None, 1, complete=True, had_failures=False)
    scraper = QuotesScraper(delay=0, check_robots=False, checkpoint=cp, resume=True)
    scraper.fetch = lambda url: (_ for _ in ()).throw(AssertionError("fetch must not run"))
    records = scraper.paginate(scraper.base_url, scraper.parse_page, use_checkpoint=True, checkpoint=cp)
    assert records == [{"quote_raw": "saved"}]
    assert scraper.resumed is True


def test_checkpoint_mismatch_starts_fresh(tmp_path: Path):
    cp = PageCheckpoint("https://quotes.toscrape.com/", "QuotesScraper", tmp_path)
    cp.save([{"bad": 1}], None, 1, complete=True, had_failures=False, start_url="https://other.example/")
    assert cp.load() is None
