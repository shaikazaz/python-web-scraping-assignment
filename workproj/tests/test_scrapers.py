"""Offline unit tests for BooksScraper, QuotesScraper, and BaseScraper pagination."""

from typing import Optional

from bs4 import BeautifulSoup

import config
from scrapers.books_scraper import BooksScraper
from scrapers.quotes_scraper import QuotesScraper


def test_books_scraper_parse_page() -> None:
    """Test 1: BooksScraper.parse_page extracts full title attribute, absolute URL, price, and rating."""
    html = """
    <html>
        <body>
            <article class="product_pod">
                <h3><a href="catalogue/a-light-in-the-attic_1000/index.html" title="A Light in the Attic: Full Title">A Light in...</a></h3>
                <p class="price_color">£51.77</p>
                <p class="star-rating Three"></p>
                <p class="instock availability">In stock (22 available)</p>
            </article>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    scraper = BooksScraper(delay=0, check_robots=False)
    records = scraper.parse_page(soup, "https://books.toscrape.com/index.html")

    assert len(records) == 1
    rec = records[0]
    assert rec["title"] == "A Light in the Attic: Full Title"
    assert rec["source_url"] == "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    assert rec["price_raw"] == "£51.77"
    assert rec["rating_raw"] == "star-rating Three"
    assert "In stock" in rec["availability_raw"]


def test_quotes_scraper_parse_page() -> None:
    """Test 2: QuotesScraper.parse_page extracts author, tags list, and absolute author_url."""
    html = """
    <html>
        <body>
            <div class="quote">
                <span class="text">“The world as we have created it is a process of our thinking.”</span>
                <span>by <small class="author">Albert Einstein</small>
                <a href="/author/Albert-Einstein">(about)</a>
                </span>
                <div class="tags">
                    <a class="tag" href="/tag/change">change</a>
                    <a class="tag" href="/tag/world">world</a>
                </div>
            </div>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    scraper = QuotesScraper(delay=0, check_robots=False)
    records = scraper.parse_page(soup, "https://quotes.toscrape.com/page/1/")

    assert len(records) == 1
    rec = records[0]
    assert "The world as we have created it" in rec["quote_raw"]
    assert rec["author_raw"] == "Albert Einstein"
    assert rec["tags_raw"] == ["change", "world"]
    assert rec["author_url"] == "https://quotes.toscrape.com/author/Albert-Einstein"
    assert rec["source_url"] == "https://quotes.toscrape.com/page/1/"


def test_empty_quote_pod_does_not_crash() -> None:
    """Test 3: An empty div.quote does not crash and safely yields None fields."""
    html = '<html><body><div class="quote"></div></body></html>'
    soup = BeautifulSoup(html, "lxml")
    scraper = QuotesScraper(delay=0, check_robots=False)
    records = scraper.parse_page(soup, "https://quotes.toscrape.com/")

    assert len(records) == 1
    rec = records[0]
    assert rec["quote_raw"] is None
    assert rec["author_raw"] is None
    assert rec["tags_raw"] == []
    assert rec["author_url"] is None


def test_pagination_follows_next_link() -> None:
    """Test 4: Pagination follows li.next > a across fake pages via mocked fetch."""
    page1_html = """
    <html><body>
        <div class="quote"><span class="text">Quote 1</span><small class="author">Author 1</small></div>
        <li class="next"><a href="/page/2/">Next</a></li>
    </body></html>
    """
    page2_html = """
    <html><body>
        <div class="quote"><span class="text">Quote 2</span><small class="author">Author 2</small></div>
    </body></html>
    """
    pages = {
        "https://quotes.toscrape.com/": BeautifulSoup(page1_html, "lxml"),
        "https://quotes.toscrape.com/page/2/": BeautifulSoup(page2_html, "lxml"),
    }

    scraper = QuotesScraper(delay=0, check_robots=False)
    scraper.fetch = lambda url: pages.get(url)  # type: ignore

    records = scraper.paginate("https://quotes.toscrape.com/", scraper.parse_page)
    assert len(records) == 2
    assert records[0]["quote_raw"] == "Quote 1"
    assert records[1]["quote_raw"] == "Quote 2"


def test_failed_page_skipped_via_guess_next() -> None:
    """Test 5: A transiently failed page (fetch returns None) is skipped via guess_next and subsequent pages collected."""
    page1_html = """
    <html><body>
        <div class="quote"><span class="text">Quote Page 1</span></div>
        <li class="next"><a href="/page/2/">Next</a></li>
    </body></html>
    """
    # Page 2 fails (simulated network error or drop)
    page3_html = """
    <html><body>
        <div class="quote"><span class="text">Quote Page 3</span></div>
    </body></html>
    """

    pages = {
        "https://quotes.toscrape.com/page/1/": BeautifulSoup(page1_html, "lxml"),
        # /page/2/ is None
        "https://quotes.toscrape.com/page/3/": BeautifulSoup(page3_html, "lxml"),
    }

    scraper = QuotesScraper(delay=0, check_robots=False)

    def mock_fetch(url: str) -> Optional[BeautifulSoup]:
        return pages.get(url)

    scraper.fetch = mock_fetch  # type: ignore

    records = scraper.paginate("https://quotes.toscrape.com/page/1/", scraper.parse_page)
    # Page 1 collected (1), Page 2 failed -> guessed Page 3 -> collected (1)
    assert len(records) == 2
    assert records[0]["quote_raw"] == "Quote Page 1"
    assert records[1]["quote_raw"] == "Quote Page 3"


def test_pagination_stops_after_max_consecutive_failures() -> None:
    """Test 6: Pagination stops when consecutive failures hit MAX_CONSECUTIVE_FAILURES."""
    scraper = QuotesScraper(delay=0, check_robots=False)
    fetch_calls: list[str] = []

    def failing_fetch(url: str) -> None:
        fetch_calls.append(url)
        return None

    scraper.fetch = failing_fetch  # type: ignore
    records = scraper.paginate("https://quotes.toscrape.com/page/1/", scraper.parse_page)

    assert len(records) == 0
    assert len(fetch_calls) == config.MAX_CONSECUTIVE_FAILURES
