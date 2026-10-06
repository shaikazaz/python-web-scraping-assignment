"""Quotes to Scrape source scraper module."""

from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

import config
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class QuotesScraper(BaseScraper):
    """Scraper for https://quotes.toscrape.com extracting raw quote records."""

    def __init__(
        self,
        delay: float = config.REQUEST_DELAY,
        check_robots: bool = True,
        checkpoint=None,
        resume: bool = False,
    ) -> None:
        """Initialize QuotesScraper targeting config.QUOTES_URL.

        Args:
            delay: Delay in seconds between requests.
            check_robots: Whether to check robots.txt before crawling.
        """
        super().__init__(base_url=config.QUOTES_URL, delay=delay, check_robots=check_robots)
        self.checkpoint = checkpoint
        self.resume = resume

    def guess_next(self, url: str) -> Optional[str]:
        """Infer the next page URL if normal pagination element lookup fails.

        Args:
            url: The page URL that failed.

        Returns:
            The predicted next page URL.
        """
        match = re.search(r"/page/(\d+)/?", url)
        if match:
            next_num = int(match.group(1)) + 1
            return urljoin(url, f"/page/{next_num}/")
        return urljoin(url, "/page/2/")

    def parse_page(self, soup: BeautifulSoup, page_url: str) -> list[dict]:
        """Extract raw uncleaned quote records from a parsed page.

        Args:
            soup: Parsed BeautifulSoup document of the quotes page.
            page_url: The absolute URL of the page being parsed.

        Returns:
            List of raw quote dictionary records.
        """
        records: list[dict] = []
        quote_elements = soup.select("div.quote")

        for quote_el in quote_elements:
            try:
                # Text node
                text_el = quote_el.select_one("span.text")
                quote_raw: Optional[str] = text_el.get_text() if text_el else None

                # Author node
                author_el = quote_el.select_one("small.author")
                author_raw: Optional[str] = author_el.get_text() if author_el else None

                # Tags nodes
                tag_elements = quote_el.select("div.tags a.tag")
                tags_raw: list[str] = [t.get_text() for t in tag_elements]

                # Author link node (relative href converted to absolute)
                author_link_el = quote_el.select_one('a[href^="/author/"]')
                author_url: Optional[str] = None
                if author_link_el and author_link_el.get("href"):
                    author_url = urljoin(page_url, author_link_el.get("href"))

                raw_record: dict = {
                    "quote_raw": quote_raw,
                    "author_raw": author_raw,
                    "tags_raw": tags_raw,
                    "author_url": author_url,
                    "source_url": page_url,
                }
                records.append(raw_record)
            except Exception:
                logger.exception("Error parsing quote element on page %s", page_url)
                continue

        return records

    def scrape(self, *, checkpoint=None, resume: bool = False) -> list[dict]:
        """Execute full pagination crawl across all available quotes pages.

        Returns:
            Consolidated list of raw quote records.
        """
        records = self.paginate(self.base_url, self.parse_page, use_checkpoint=bool(self.checkpoint), checkpoint=self.checkpoint)
        logger.info("Scraped %d raw quote records from %s", len(records), self.base_url)
        return records
