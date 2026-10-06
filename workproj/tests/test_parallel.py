from main import run_sources


class FakeScraper:
    def __init__(self, records):
        self.records = records
        self.failed_pages = []
        self.had_failures = False
        self.resumed = False

    def scrape(self):
        return self.records


def clean(x):
    return {
        "source": "Books to Scrape",
        "name_or_title": str(x["id"]),
        "source_url": "https://example.com",
        "scraped_at": "2026-01-01T00:00:00+00:00",
        "price": 1.0,
        "rating": 5,
        "category": "Test",
    }


def test_parallel_preserves_source_order():
    jobs = [
        {"name": "first", "scraper_factory": lambda: FakeScraper([{"id": 1}]), "clean_fn": clean},
        {"name": "second", "scraper_factory": lambda: FakeScraper([{"id": 2}]), "clean_fn": clean},
    ]
    results = run_sources(jobs, parallel=True)
    assert [r["name"] for r in results] == ["first", "second"]
    assert results[0]["records"][0]["name_or_title"] == "1"
