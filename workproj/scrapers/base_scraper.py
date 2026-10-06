"""Common HTTP, retry, robots, rate limiting, and checkpoint-aware pagination."""

from __future__ import annotations

import logging
import urllib.robotparser
from typing import Callable, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class BaseScraper:
    def __init__(
        self,
        base_url: str,
        delay: float = config.REQUEST_DELAY,
        check_robots: bool = True,
    ) -> None:
        self.base_url = base_url
        self.delay = max(0.0, float(delay))
        self.check_robots = check_robots
        self.failed_pages: list[str] = []
        self.had_failures = False
        self.checkpoint = None
        self.resumed = False

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.USER_AGENT})
        retry_strategy = Retry(
            total=config.MAX_RETRIES,
            backoff_factor=config.BACKOFF_FACTOR,
            status_forcelist=config.RETRY_STATUS,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.rate_limiter = RateLimiter(self.delay)

        self.robot_parser: Optional[urllib.robotparser.RobotFileParser] = (
            self._load_robots() if self.check_robots else None
        )

    def _get(self, url: str) -> requests.Response:
        """Perform one network GET after reserving a rate-limit slot."""
        self.rate_limiter.wait()
        return self.session.get(url, timeout=config.TIMEOUT)

    def _load_robots(self) -> Optional[urllib.robotparser.RobotFileParser]:
        robots_url = urljoin(self.base_url, "/robots.txt")
        try:
            resp = self._get(robots_url)
            if resp.status_code == 200:
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(resp.text.splitlines())
                logger.info("Loaded robots.txt from %s", robots_url)
                return parser
            logger.info(
                "Robots.txt missing or returned HTTP %s for %s; no restrictions applied",
                resp.status_code, robots_url,
            )
        except requests.RequestException as exc:
            logger.warning("Could not fetch robots.txt from %s (%s); proceeding without restrictions",
                           robots_url, exc)
        return None

    def allowed(self, url: str) -> bool:
        if not self.check_robots or self.robot_parser is None:
            return True
        return self.robot_parser.can_fetch(config.USER_AGENT, url)

    def fetch(self, url: str) -> Optional[BeautifulSoup]:
        if not self.allowed(url):
            logger.warning("URL disallowed by robots.txt: %s", url)
            self.failed_pages.append(url)
            self.had_failures = True
            return None
        try:
            resp = self._get(url)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as exc:
            logger.error("Failed to fetch %s: %s", url, exc)
            self.failed_pages.append(url)
            self.had_failures = True
            return None

    def guess_next(self, url: str) -> Optional[str]:
        return None

    def paginate(
        self,
        start_url: str,
        parse_page: Callable[[BeautifulSoup, str], list[dict]],
        next_selector: str = "li.next > a",
        *,
        use_checkpoint: bool = False,
        checkpoint=None,
    ) -> list[dict]:
        """Paginate, optionally persisting page-level progress for resume."""
        from utils.checkpoint import PageCheckpoint

        cp = checkpoint or (PageCheckpoint(start_url, self.__class__.__name__) if use_checkpoint else None)
        self.checkpoint = cp
        self.resumed = False

        visited: set[str] = set()
        all_records: list[dict] = []
        current_url: Optional[str] = start_url
        page_num = 1
        consecutive_failures = 0

        if cp is not None and getattr(self, "resume", False):
            loaded = cp.load()
            if loaded and loaded.get("start_url") == start_url:
                if loaded.get("complete"):
                    logger.info("Complete checkpoint found for %s; returning checkpoint records", start_url)
                    self.resumed = True
                    return list(loaded.get("records", []))
                all_records = list(loaded.get("records", []))
                current_url = loaded.get("next_url") or start_url
                page_num = int(loaded.get("next_page", 1))
                self.resumed = bool(all_records or page_num > 1)
                logger.info("Resuming %s from page %s", start_url, page_num)
            elif loaded:
                logger.warning("Checkpoint mismatch for %s; starting fresh", start_url)
                cp.clear()

        while current_url and (config.MAX_PAGES is None or page_num <= config.MAX_PAGES):
            if current_url in visited:
                logger.warning("Cycle detected at URL: %s. Stopping pagination.", current_url)
                break
            visited.add(current_url)
            logger.info("Page %d: %s", page_num, current_url)
            soup = self.fetch(current_url)

            if soup is None:
                consecutive_failures += 1
                if consecutive_failures >= config.MAX_CONSECUTIVE_FAILURES:
                    logger.error("Reached maximum consecutive failures (%d).", config.MAX_CONSECUTIVE_FAILURES)
                    if cp is not None:
                        cp.save(all_records, current_url, page_num, complete=False, had_failures=True,
                                start_url=start_url)
                    break
                current_url = self.guess_next(current_url)
                page_num += 1
                if cp is not None:
                    cp.save(all_records, current_url, page_num, complete=False, had_failures=True,
                            start_url=start_url)
                continue

            consecutive_failures = 0
            try:
                page_records = parse_page(soup, current_url)
                all_records.extend(page_records)
            except Exception:
                logger.exception("Error parsing page %s", current_url)
                self.had_failures = True

            next_el = soup.select_one(next_selector)
            if next_el and next_el.get("href"):
                next_url = urljoin(current_url, next_el.get("href"))
                next_page = page_num + 1
            else:
                next_url = None
                next_page = page_num

            if cp is not None:
                cp.save(all_records, next_url, next_page, complete=(next_url is None and not self.had_failures),
                        had_failures=self.had_failures, start_url=start_url)

            if next_url is None:
                break
            current_url = next_url
            page_num = next_page

        if current_url and config.MAX_PAGES is not None and page_num > config.MAX_PAGES:
            logger.warning("Maximum pages limit reached at %d; output is incomplete.", config.MAX_PAGES)
            self.had_failures = True
        return all_records
