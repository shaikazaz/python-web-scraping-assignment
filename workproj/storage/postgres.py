"""Optional PostgreSQL persistence with lazy driver loading and safe upserts."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse, urlunparse

import config
from processing.deduplication import make_fingerprint


class StoreError(RuntimeError):
    """Raised when optional database persistence fails."""


def mask_dsn(dsn: str) -> str:
    try:
        parsed = urlparse(dsn)
        if parsed.password is None:
            return dsn
        username = parsed.username or ""
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        netloc = f"{username}:***@{host}{port}"
        return urlunparse(parsed._replace(netloc=netloc))
    except Exception:
        return re.sub(r"(://[^:/]+:)[^@]+@", r"\1***@", dsn)


class PostgresStore:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.masked_dsn = mask_dsn(dsn)
        self.connection = None
        self._driver = None

    def connect(self) -> None:
        if self.connection is not None:
            return
        try:
            import psycopg2
        except ImportError as exc:
            raise StoreError(
                "psycopg2 is not installed; pip install -r requirements-postgres.txt"
            ) from exc
        try:
            self._driver = psycopg2
            self.connection = psycopg2.connect(self.dsn)
        except Exception as exc:
            raise StoreError(f"PostgreSQL connection failed for {self.masked_dsn}: {exc}") from exc

    def ensure_schema(self) -> None:
        self.connect()
        sql = """
        CREATE TABLE IF NOT EXISTS records (
            fingerprint TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            name_or_title TEXT NOT NULL,
            category TEXT,
            price NUMERIC(10,2),
            rating SMALLINT,
            author TEXT,
            tags TEXT,
            source_url TEXT NOT NULL,
            scraped_at TIMESTAMPTZ,
            description TEXT,
            availability TEXT,
            author_url TEXT,
            first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_records_source ON records(source);
        """
        try:
            with self.connection:
                with self.connection.cursor() as cur:
                    cur.execute(sql)
        except Exception as exc:
            raise StoreError(f"Schema creation failed for {self.masked_dsn}: {exc}") from exc

    def upsert_records(
        self,
        records: list[dict[str, Any]],
        fingerprints: list[str] | None = None,
    ) -> dict[str, int]:
        self.ensure_schema()
        fps = fingerprints or [make_fingerprint(record) for record in records]
        if len(fps) != len(records):
            raise StoreError("Fingerprint count does not match record count")

        sql = """
        INSERT INTO records (
            fingerprint, source, name_or_title, category, price, rating, author,
            tags, source_url, scraped_at, description, availability, author_url,
            last_seen_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (fingerprint) DO UPDATE SET
            source = EXCLUDED.source,
            name_or_title = EXCLUDED.name_or_title,
            category = EXCLUDED.category,
            price = EXCLUDED.price,
            rating = EXCLUDED.rating,
            author = EXCLUDED.author,
            tags = EXCLUDED.tags,
            source_url = EXCLUDED.source_url,
            scraped_at = EXCLUDED.scraped_at,
            description = EXCLUDED.description,
            availability = EXCLUDED.availability,
            author_url = EXCLUDED.author_url,
            last_seen_at = now()
        RETURNING (xmax = 0) AS inserted
        """
        inserted = updated = 0
        try:
            with self.connection:
                with self.connection.cursor() as cur:
                    for record, fingerprint in zip(records, fps):
                        values = [
                            fingerprint,
                            record.get("source"), record.get("name_or_title"), record.get("category"),
                            record.get("price"), record.get("rating"), record.get("author"),
                            record.get("tags"), record.get("source_url"), record.get("scraped_at"),
                            record.get("description"), record.get("availability"), record.get("author_url"),
                        ]
                        cur.execute(sql, values)
                        row = cur.fetchone()
                        if row and row[0]:
                            inserted += 1
                        else:
                            updated += 1
        except Exception as exc:
            raise StoreError(f"Record upsert failed for {self.masked_dsn}: {exc}") from exc
        return {"inserted": inserted, "updated": updated}

    def close(self) -> None:
        if self.connection is not None:
            try:
                self.connection.close()
            finally:
                self.connection = None

    def __enter__(self) -> "PostgresStore":
        self.connect()
        self.ensure_schema()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
