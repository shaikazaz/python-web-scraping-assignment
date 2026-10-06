"""CLI entry point for the resilient multi-source scraping pipeline."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import config
from processing.cleaning import clean_book, clean_quote
from processing.deduplication import find_duplicates, make_fingerprint
from processing.quality import build_quality_report
from processing.validation import validate_record
from scrapers.books_scraper import BooksScraper
from scrapers.quotes_scraper import QuotesScraper
from utils.checkpoint import PageCheckpoint
from utils.state import compare_fingerprints, load_previous_fingerprints, save_fingerprints

logger = logging.getLogger("scraper_pipeline")


def setup_logging(level: str = config.LOG_LEVEL) -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = config.LOG_DIR / "scraper.log"
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


def apply_overrides(args: argparse.Namespace) -> None:
    """Apply CLI settings before any scraper is constructed."""
    config.REQUEST_DELAY = max(0.0, float(args.delay))
    config.TIMEOUT = float(args.timeout)
    config.MAX_RETRIES = int(args.retries)
    if args.max_pages is not None:
        config.MAX_PAGES = int(args.max_pages)
    if args.output_dir:
        config.OUTPUT_DIR = Path(args.output_dir).expanduser()
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def process_source(
    name: str,
    scrape_fn: Callable[[], list[dict[str, Any]]],
    clean_fn: Callable[[dict[str, Any]], dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    stats: dict[str, Any] = {
        "collected": 0, "cleaned": 0, "rejected": 0, "rejected_by_reason": {},
    }
    valid_records: list[dict[str, Any]] = []
    try:
        raw_records = scrape_fn()
    except Exception:
        logger.exception("Scraper failed unexpectedly for source: %s", name)
        return stats, valid_records
    stats["collected"] = len(raw_records)
    for raw in raw_records:
        try:
            cleaned = clean_fn(raw)
        except Exception as exc:
            stats["rejected"] += 1
            stats["rejected_by_reason"]["cleaning_error"] = stats["rejected_by_reason"].get("cleaning_error", 0) + 1
            logger.warning("Cleaning error for record in %s: %s", name, exc)
            continue
        stats["cleaned"] += 1
        reasons = validate_record(cleaned)
        if reasons:
            stats["rejected"] += 1
            for reason in reasons:
                stats["rejected_by_reason"][reason] = stats["rejected_by_reason"].get(reason, 0) + 1
            logger.warning("Rejected record from %s: %s (record: %s)", name, ", ".join(reasons), cleaned.get("name_or_title"))
        else:
            valid_records.append(cleaned)
    return stats, valid_records


def run_sources(jobs: list[dict[str, Any]], parallel: bool = False) -> list[dict[str, Any]]:
    """Run source jobs and return results in the original job order."""
    results: list[dict[str, Any] | None] = [None] * len(jobs)

    def run_one(job: dict[str, Any]) -> dict[str, Any]:
        scraper = job["scraper_factory"]()
        stats, records = process_source(job["name"], scraper.scrape, job["clean_fn"])
        return {"name": job["name"], "stats": stats, "records": records, "scraper": scraper}

    if not parallel:
        for idx, job in enumerate(jobs):
            try:
                results[idx] = run_one(job)
            except Exception:
                logger.exception("Source job failed: %s", job["name"])
                results[idx] = {
                    "name": job["name"],
                    "stats": {"collected": 0, "cleaned": 0, "rejected": 0, "rejected_by_reason": {}},
                    "records": [], "scraper": None,
                }
        return [r for r in results if r is not None]

    with ThreadPoolExecutor(max_workers=len(jobs) or 1) as executor:
        futures = {executor.submit(run_one, job): idx for idx, job in enumerate(jobs)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception:
                logger.exception("Source job failed: %s", jobs[idx]["name"])
                results[idx] = {
                    "name": jobs[idx]["name"],
                    "stats": {"collected": 0, "cleaned": 0, "rejected": 0, "rejected_by_reason": {}},
                    "records": [], "scraper": None,
                }
    return [r for r in results if r is not None]


def write_csv(records: list[dict[str, Any]], path: Path | str) -> None:
    target_path = Path(path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=config.COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def print_summary(summary: dict[str, Any]) -> None:
    per_source = summary.get("per_source", {})
    totals = summary.get("totals", {})
    duration = summary.get("duration_seconds", 0.0)
    reconciles_str = "OK" if totals.get("reconciles", False) else "MISMATCH"
    header_fmt = "{:<20} {:>10} {:>9} {:>10} {:>12} {:>8}"
    sep = "-" * 73
    print(header_fmt.format("Source", "Collected", "Cleaned", "Rejected", "Duplicates", "Final"))
    print(sep)
    for name, data in per_source.items():
        if isinstance(data, dict):
            print(header_fmt.format(name[:20], data.get("collected", 0), data.get("cleaned", 0),
                                     data.get("rejected", 0), data.get("duplicates_removed", 0),
                                     data.get("final_count", 0)))
    print(sep)
    print(header_fmt.format("Totals", totals.get("collected", 0), totals.get("cleaned", 0),
                            totals.get("rejected", 0), totals.get("duplicates_detected", 0),
                            totals.get("final_record_count", 0)))
    print(sep)
    print(f"Reconciles: {reconciles_str} | Duration: {duration}s")
    print("Files: output/final_dataset.csv | output/summary_report.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Multi-source web scraping and data consolidation pipeline.",
        epilog="Precedence: CLI flags > SCRAPER_* environment variables > built-in defaults.",
    )
    parser.add_argument("--with-details", action="store_true", help="Fetch individual book detail pages for descriptions.")
    parser.add_argument("--delay", type=float, default=config.REQUEST_DELAY, help="Request delay in seconds.")
    parser.add_argument("--output-dir", type=str, default=str(config.OUTPUT_DIR), help="Output directory.")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default=config.LOG_LEVEL)
    parser.add_argument("--sources", choices=["books", "quotes", "both"], default="both", help="Run only selected sources.")
    parser.add_argument("--timeout", type=float, default=config.TIMEOUT, help="HTTP timeout in seconds.")
    parser.add_argument("--retries", type=int, default=config.MAX_RETRIES, help="Maximum HTTP retries.")
    parser.add_argument("--max-pages", type=int, default=None, help="Maximum pages per paginated scraper; warning means output may be incomplete.")
    parser.add_argument("--parallel", action="store_true", help="Run selected source scrapers concurrently.")
    parser.add_argument("--resume", action="store_true", help="Resume from page checkpoints when available.")
    parser.add_argument("--no-checkpoint", action="store_true", help="Disable page checkpoint persistence.")
    parser.add_argument("--no-state", action="store_true", help="Disable incremental fingerprint state and new_records.csv.")
    parser.add_argument("--db", choices=["none", "postgres"], default="none", help="Optional database persistence; CSV remains authoritative.")
    return parser


def _empty_result(name: str) -> dict[str, Any]:
    return {"name": name, "stats": {"collected": 0, "cleaned": 0, "rejected": 0, "rejected_by_reason": {}},
            "records": [], "scraper": None}


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Validate CLI values without allowing bad values to reach requests.
    if args.delay < 0 or args.timeout <= 0 or args.retries < 0 or (args.max_pages is not None and args.max_pages <= 0):
        parser.error("--delay >= 0, --timeout > 0, --retries >= 0, and --max-pages > 0 are required")

    apply_overrides(args)
    setup_logging(args.log_level)
    start_time = datetime.now(timezone.utc)
    logger.info("Starting web scraping pipeline...")

    selected = {config.BOOKS_SOURCE, config.QUOTES_SOURCE}
    if args.sources == "books":
        selected = {config.BOOKS_SOURCE}
    elif args.sources == "quotes":
        selected = {config.QUOTES_SOURCE}

    checkpoint_enabled = not args.no_checkpoint
    if args.resume and args.no_checkpoint:
        logger.warning("--resume requested with --no-checkpoint; checkpoints remain disabled.")
        checkpoint_enabled = False

    jobs: list[dict[str, Any]] = []
    if config.BOOKS_SOURCE in selected:
        def books_factory() -> BooksScraper:
            cp = PageCheckpoint(config.BOOKS_URL, "BooksScraper") if checkpoint_enabled else None
            return BooksScraper(delay=config.REQUEST_DELAY, fetch_details=args.with_details,
                                checkpoint=cp, resume=args.resume)
        jobs.append({"name": config.BOOKS_SOURCE, "scraper_factory": books_factory, "clean_fn": clean_book})
    if config.QUOTES_SOURCE in selected:
        def quotes_factory() -> QuotesScraper:
            cp = PageCheckpoint(config.QUOTES_URL, "QuotesScraper") if checkpoint_enabled else None
            return QuotesScraper(delay=config.REQUEST_DELAY, checkpoint=cp, resume=args.resume)
        jobs.append({"name": config.QUOTES_SOURCE, "scraper_factory": quotes_factory, "clean_fn": clean_quote})

    results = run_sources(jobs, parallel=args.parallel)
    by_name = {r["name"]: r for r in results}

    books_result = by_name.get(config.BOOKS_SOURCE, _empty_result(config.BOOKS_SOURCE))
    quotes_result = by_name.get(config.QUOTES_SOURCE, _empty_result(config.QUOTES_SOURCE))
    combined_valid = books_result["records"] + quotes_result["records"]
    unique_records, duplicate_records = find_duplicates(combined_valid)

    for dup in duplicate_records:
        logger.warning("Duplicate record detected and removed: %s from %s", dup.get("name_or_title"), dup.get("source"))

    source_dups = {
        config.BOOKS_SOURCE: sum(1 for d in duplicate_records if d.get("source") == config.BOOKS_SOURCE),
        config.QUOTES_SOURCE: sum(1 for d in duplicate_records if d.get("source") == config.QUOTES_SOURCE),
    }
    source_final = {
        source: sum(1 for u in unique_records if u.get("source") == source)
        for source in (config.BOOKS_SOURCE, config.QUOTES_SOURCE)
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "final_dataset.csv"
    write_csv(unique_records, csv_path)

    total_collected = books_result["stats"]["collected"] + quotes_result["stats"]["collected"]
    total_cleaned = books_result["stats"]["cleaned"] + quotes_result["stats"]["cleaned"]
    total_rejected = books_result["stats"]["rejected"] + quotes_result["stats"]["rejected"]
    duplicates_detected = len(duplicate_records)
    final_record_count = len(unique_records)
    reconciles = (total_collected - total_rejected - duplicates_detected) == final_record_count

    failed_pages = {
        config.BOOKS_SOURCE: list(getattr(books_result["scraper"], "failed_pages", [])),
        config.QUOTES_SOURCE: list(getattr(quotes_result["scraper"], "failed_pages", [])),
    }
    had_failures = any(bool(getattr(r["scraper"], "had_failures", False)) for r in results if r["scraper"] is not None)
    if args.max_pages is not None:
        logger.warning("--max-pages=%d may produce incomplete output.", args.max_pages)
        had_failures = True

    incremental_info: dict[str, Any] = {
        "enabled": not args.no_state,
        "previous_run_available": False,
        "new_records": 0,
        "unchanged_records": 0,
        "no_longer_present": 0,
    }
    current_fingerprints: set[str] = set()
    state_path = config.STATE_DIR / "fingerprints.json"
    if not args.no_state:
        previous = load_previous_fingerprints(state_path)
        current_fingerprints = {make_fingerprint(record) for record in unique_records}
        if previous is None:
            incremental_info.update({"previous_run_available": False, "new_records": len(current_fingerprints)})
        else:
            new_fps = current_fingerprints - previous
            unchanged = current_fingerprints & previous
            gone = previous - current_fingerprints
            incremental_info.update({
                "previous_run_available": True,
                "new_records": len(new_fps),
                "unchanged_records": len(unchanged),
                "no_longer_present": len(gone),
            })
            new_records = [r for r in unique_records if make_fingerprint(r) in new_fps]
            write_csv(new_records, output_dir / "new_records.csv")

    quality_report = build_quality_report(unique_records)
    end_time = datetime.now(timezone.utc)
    duration_seconds = round((end_time - start_time).total_seconds(), 2)

    summary_report: dict[str, Any] = {
        "start_time": start_time.isoformat(timespec="seconds"),
        "end_time": end_time.isoformat(timespec="seconds"),
        "duration_seconds": duration_seconds,
        "per_source": {
            config.BOOKS_SOURCE: {**books_result["stats"], "duplicates_removed": source_dups[config.BOOKS_SOURCE], "final_count": source_final[config.BOOKS_SOURCE]},
            config.QUOTES_SOURCE: {**quotes_result["stats"], "duplicates_removed": source_dups[config.QUOTES_SOURCE], "final_count": source_final[config.QUOTES_SOURCE]},
        },
        "totals": {
            "collected": total_collected, "cleaned": total_cleaned, "rejected": total_rejected,
            "duplicates_detected": duplicates_detected, "final_record_count": final_record_count, "reconciles": reconciles,
        },
        "failed_pages": failed_pages,
        "data_quality": quality_report,
        "settings": {
            "delay": config.REQUEST_DELAY, "timeout": config.TIMEOUT, "retries": config.MAX_RETRIES,
            "max_pages": args.max_pages, "sources": args.sources, "parallel": args.parallel,
        },
        "incremental": incremental_info,
        "checkpoint": {
            "enabled": checkpoint_enabled,
            "resumed": {r["name"]: bool(getattr(r["scraper"], "resumed", False)) for r in results if r["scraper"] is not None},
        },
        "database": {"mode": args.db, "status": "disabled" if args.db == "none" else "not attempted"},
    }

    json_path = output_dir / "summary_report.json"
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary_report, f, indent=4)
    except OSError:
        logger.exception("Could not write summary report")
        return 1

    # Optional persistence is deliberately best-effort; CSV/summary remain authoritative.
    if args.db == "postgres":
        try:
            from storage.postgres import PostgresStore
            dsn = __import__("os").environ.get("DATABASE_URL")
            if not dsn:
                raise RuntimeError("DATABASE_URL is required for --db postgres")
            store = PostgresStore(dsn)
            db_result = store.upsert_records(unique_records, [make_fingerprint(r) for r in unique_records])
            summary_report["database"] = {"mode": "postgres", "status": "success", "inserted": db_result["inserted"], "updated": db_result["updated"]}
            store.close()
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(summary_report, f, indent=4)
        except Exception as exc:
            logger.exception("PostgreSQL persistence failed; CSV output is still valid.")
            summary_report["database"] = {"mode": "postgres", "status": "failed", "error": str(exc)}
            try:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(summary_report, f, indent=4)
            except OSError:
                logger.exception("Could not update summary after database failure")

    if not args.no_state and not had_failures:
        try:
            save_fingerprints(state_path, current_fingerprints)
        except OSError:
            logger.exception("Could not save incremental state; continuing without failing the run.")

    print_summary(summary_report)
    return 0 if final_record_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
