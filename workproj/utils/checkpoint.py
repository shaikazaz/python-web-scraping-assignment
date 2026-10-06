"""Atomic page-level checkpoint persistence."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import config


class PageCheckpoint:
    def __init__(self, start_url: str, scraper_name: str, directory: Path | None = None) -> None:
        self.start_url = start_url
        self.scraper_name = scraper_name
        self.directory = Path(directory or config.CHECKPOINT_DIR)
        self.slug = self._slug(start_url, scraper_name)
        self.path = self.directory / f"{self.slug}.pages.json"

    @staticmethod
    def _slug(start_url: str, scraper_name: str) -> str:
        digest = hashlib.sha256(start_url.encode("utf-8")).hexdigest()[:12]
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", scraper_name).strip("-").lower()
        return f"{safe}-{digest}"

    def save(
        self,
        records: list[dict[str, Any]],
        next_url: str | None,
        next_page: int,
        *,
        complete: bool,
        had_failures: bool,
        start_url: str | None = None,
    ) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "slug": self.slug,
            "scraper_name": self.scraper_name,
            "start_url": start_url or self.start_url,
            "next_url": next_url,
            "next_page": next_page,
            "complete": bool(complete),
            "had_failures": bool(had_failures),
            "count": len(records),
            "records": records,
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def load(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        try:
            with open(self.path, encoding="utf-8") as f:
                payload = json.load(f)
            if (
                payload.get("version") != 1
                or payload.get("slug") != self.slug
                or payload.get("scraper_name") != self.scraper_name
                or payload.get("start_url") != self.start_url
                or not isinstance(payload.get("records"), list)
                or payload.get("count", len(payload.get("records", []))) != len(payload.get("records", []))
            ):
                import logging
                logging.getLogger(__name__).warning("Invalid checkpoint metadata in %s", self.path)
                return None
            return payload
        except (OSError, json.JSONDecodeError, TypeError):
            return None

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
