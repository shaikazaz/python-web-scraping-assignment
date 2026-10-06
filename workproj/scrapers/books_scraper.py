"""Books to Scrape source scraper module."""

from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

import config
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class BooksScraper(BaseScraper):
    """Scraper for https://books.toscrape.com extracting raw book records and categories."""

    def __init__(
        self,
        delay: float = config.REQUEST_DELAY,
        check_robots: bool = True,
        fetch_details: bool = False,
        checkpoint=None,
        resume: bool = False,
    ) -> None:
        """Initialize BooksScraper targeting config.BOOKS_URL.

        Args:
            delay: Delay in seconds between HTTP requests.
            check_robots: Whether to check and respect robots.txt.
            fetch_details: Whether to fetch each product detail page for descriptions.
        """
        super().__init__(base_url=config.BOOKS_URL, delay=delay, check_robots=check_robots)
        self.fetch_details: bool = fetch_details
        self.checkpoint = checkpoint
        self.resume = resume

    def guess_next(self, url: str) -> Optional[str]:
        """Infer the next page URL if normal pagination selector lookup fails.

        Args:
            url: The current page URL.

        Returns:
            The predicted next page URL.
        """
        match = re.search(r"page-(\d+)\.html$", url)
        if match:
            next_num = int(match.group(1)) + 1
            return re.sub(r"page-\d+\.html$", f"page-{next_num}.html", url)
        if url.endswith("index.html"):
            return re.sub(r"index\.html$", "page-2.html", url)
        return urljoin(url, "catalogue/page-2.html")

    def parse_page(self, soup: BeautifulSoup, page_url: str) -> list[dict]:
        """Extract raw uncleaned book records from a catalog page.

        Args:
            soup: Parsed BeautifulSoup document of the catalog page.
            page_url: The absolute URL of the catalog page being parsed.

        Returns:
            List of raw uncleaned book records.
        """
        records: list[dict] = []
        product_pods = soup.select("article.product_pod")

        for pod in product_pods:
            try:
                a_tag = pod.select_one("h3 > a")
                title: Optional[str] = a_tag.get("title") if a_tag else None
                href: Optional[str] = a_tag.get("href") if a_tag else None
                source_url: Optional[str] = urljoin(page_url, href) if href else None

                price_el = pod.select_one("p.price_color")
                price_raw: Optional[str] = price_el.get_text() if price_el else None

                rating_el = pod.select_one("p.star-rating")
                rating_classes = rating_el.get("class", []) if rating_el else []
                rating_raw: Optional[str] = " ".join(rating_classes) if rating_classes else None

                avail_el = pod.select_one("p.availability")
                availability_raw: Optional[str] = avail_el.get_text() if avail_el else None

                raw_record: dict = {
                    "title": title,
                    "source_url": source_url,
                    "price_raw": price_raw,
                    "rating_raw": rating_raw,
                    "availability_raw": availability_raw,
                    "category_raw": None,
                    "description_raw": None,
                }
                records.append(raw_record)
            except Exception:
                logger.exception("Error parsing book pod on page %s", page_url)
                continue

        return records

    def scrape_categories(self) -> dict[str, str]:
        """Map every book source_url to its category by crawling category pages.

        Returns:
            Dictionary mapping absolute book product URLs to clean category names.
        """
        logger.info("Extracting category links from home page...")
        home_soup = self.fetch(self.base_url)
        if not home_soup:
            logger.error("Failed to load home page for category extraction.")
            return {}

        cat_links = home_soup.select("div.side_categories ul li ul li a")
        category_map: dict[str, str] = {}

        for link in cat_links:
            cat_name = " ".join(link.get_text().split())
            cat_href = link.get("href")
            if not cat_href:
                continue

            current_cat_url: Optional[str] = urljoin(self.base_url, cat_href)
            while current_cat_url:
                cat_soup = self.fetch(current_cat_url)
                if not cat_soup:
                    break

                for pod in cat_soup.select("article.product_pod"):
                    a_el = pod.select_one("h3 > a")
                    if a_el and a_el.get("href"):
                        book_url = urljoin(current_cat_url, a_el["href"])
                        category_map[book_url] = cat_name

                next_el = cat_soup.select_one("li.next > a")
                if next_el and next_el.get("href"):
                    current_cat_url = urljoin(current_cat_url, next_el["href"])
                else:
                    break

        logger.info("Mapped %d books to categories across %d categories", len(category_map), len(cat_links))
        return category_map

    def scrape_description(self, url: str) -> Optional[str]:
        """Extract product description from an individual product detail page.

        Args:
            url: The absolute product URL.

        Returns:
            Extracted raw description text, or None if not found or fetch fails.
        """
        soup = self.fetch(url)
        if not soup:
            return None
        desc_el = soup.select_one("#product_description + p")
        return desc_el.get_text() if desc_el else None

    def scrape(self, *, checkpoint=None, resume: bool = False) -> list[dict]:
        """Execute full scrape of the book catalog with attached category metadata.

        Returns:
            Consolidated list of raw uncleaned book records.
        """
        category_map = self.scrape_categories()
        records = self.paginate(self.base_url, self.parse_page, use_checkpoint=bool(self.checkpoint), checkpoint=self.checkpoint)

        for rec in records:
            source_url = rec.get("source_url")
            if source_url in category_map:
                rec["category_raw"] = category_map[source_url]
            if self.fetch_details and source_url:
                rec["description_raw"] = self.scrape_description(source_url)

        logger.info("Scraped %d total book records from %s", len(records), self.base_url)
        return records
