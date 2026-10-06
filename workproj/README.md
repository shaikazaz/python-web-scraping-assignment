# Web Scraping & Data Pipeline: Books and Quotes to Scrape

Production-grade, resilient, multi-source web scraping and data consolidation pipeline that extracts book catalog data from [Books to Scrape](https://books.toscrape.com/) and literary quotes from [Quotes to Scrape](https://quotes.toscrape.com/), cleans and standardizes the records into a unified schema, performs strict data validation, deduplicates records using cryptographic composite hashing, and generates verifiable summary metrics and audit logs.

---

## 1. Project Overview

This project implements an end-to-end extraction and transformation pipeline for two distinct web sources:
- **Books to Scrape**: An e-commerce catalog featuring 1,000 books across 50 categories with prices, ratings, availability, and detailed descriptions.
- **Quotes to Scrape**: A literary quote repository containing 100 quotes across 10 paginated pages with author attributions, author biography URLs, and categorization tags.

The pipeline executes polite, robots-compliant crawling, parses raw markup with resilient DOM extraction, normalizes all attributes into a 12-column canonical schema, executes rule-based validation with granular error tracking, filters duplicates using SHA-256 composite fingerprinting, and writes both a consolidated CSV dataset and a reconciliation audit JSON report.

---

## 2. Python Version

- **Python Version**: `Python 3.11.2` (compatible with Python 3.10+)

---

## 3. Installation and Setup

1. **Clone or navigate to the repository directory**:
   ```bash
   cd scraping_assignment
   ```

2. **Create a clean virtual environment**:
   ```bash
   python3 -m venv venv
   ```

3. **Activate the virtual environment**:
   - On Linux/macOS:
     ```bash
     source venv/bin/activate
     ```
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```

4. **Install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## 4. Dependencies

Defined in `requirements.txt`:
- `requests>=2.31.0`: HTTP networking, connection pooling, and session configuration.
- `beautifulsoup4>=4.12.0`: HTML parsing, element selection, and document traversal.
- `lxml>=5.0.0`: C-based, high-performance HTML/XML parser backend.
- `pytest>=8.0.0`: Automated unit and integration testing framework.

---

## 5. How to Run

Execute the pipeline via `main.py` using standard flags:

### Basic Run (Standard Extraction)
```bash
python main.py
```

### CLI Arguments & Options
- `--with-details`: Flag enabling deep scraping of individual product detail pages on Books to Scrape to populate full book descriptions (`description` column). Default: `False` (bypassed for speed unless explicitly enabled).
- `--delay <float>`: Polite sleep delay in seconds after every HTTP request. Default: `0.5`.
- `--output-dir <path>`: Directory where `final_dataset.csv` and `summary_report.json` are written. Default: `output/`.
- `--log-level <level>`: Logging verbosity level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Default: `INFO`.
- `--sources {books,quotes,both}`: Select source(s). Default: `both`.
- `--timeout <float>`: HTTP timeout in seconds. Default: `10`.
- `--retries <int>`: Maximum HTTP retries. Default: `3`.
- `--max-pages <int>`: Optional page cap; when supplied, output is intentionally incomplete.
- `--parallel`: Run the selected sources concurrently while preserving output order. Default: off.
- `--resume`: Resume from a valid page checkpoint. Default: off.
- `--no-checkpoint`: Disable checkpoint persistence.
- `--no-state`: Disable incremental state and `new_records.csv`.
- `--db {none,postgres}`: Optional PostgreSQL persistence; CSV remains authoritative. Default: `none`.

CLI values take precedence over `SCRAPER_*` environment variables, which take precedence over built-in defaults.

### Examples
```bash
# Run with deep detail page extraction and a 1.0 second polite delay
python main.py --with-details --delay 1.0

# Run with custom output directory and debug logging
python main.py --output-dir custom_output/ --log-level DEBUG
```

### Running Automated Tests
```bash
# Run the complete test suite offline
pytest -q
```

---

## 6. Project Structure

```text
.
├── config.py                 # Central configuration constants, schemas, paths, and limits
├── main.py                   # CLI entry point, execution coordinator, and reporting
├── requirements.txt          # Production dependencies
├── docs/
│   └── site_notes.md         # Empirical inspection notes, DOM selectors, and HTTP observations
├── logs/
│   └── scraper.log           # Full timestamped execution audit log
├── output/
│   ├── final_dataset.csv     # 12-column canonical cleaned and deduplicated dataset
│   └── summary_report.json   # Machine-readable reconciliation and metrics report
├── Dockerfile                # Containerized default scraper run
├── docker-compose.yml        # Optional local PostgreSQL service
├── requirements-postgres.txt # Optional PostgreSQL dependency
├── processing/
│   ├── __init__.py
│   ├── cleaning.py           # Pure normalization functions (text, price, rating, tags, URLs)
│   ├── deduplication.py      # SHA-256 composite record fingerprinting and filtering
│   └── validation.py         # Business rule validation and reason code assignments
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py       # Core HTTP session, robots exclusion, retry, and pagination engine
│   ├── books_scraper.py      # Books to Scrape spider and category crawler
│   └── quotes_scraper.py     # Quotes to Scrape spider
└── tests/
    ├── __init__.py
    ├── test_cleaning.py      # Unit tests for text, price, rating, tag, and URL cleaning
    ├── test_deduplication.py # Unit tests for SHA-256 hashing and duplicate detection
    └── test_scrapers.py      # Offline mock unit tests for DOM parsers and pagination
```

### Additions to the Recommended Structure
- `config.py`: Consolidates all global constants (base URLs, source names, timeouts, retries, column lists, and output directories) into a single importable module, eliminating hardcoded constants across scrapers.
- `scrapers/base_scraper.py`: Extracts common HTTP concerns into an object-oriented base class (`BaseSession`, `urllib3.util.Retry`, rate limiting, `robots.txt` compliance checking, consecutive error counting, and the `paginate()` template loop) so individual scrapers focus strictly on DOM extraction rules.

---

## 7. Site Observations

Derived from empirical testing documented in `docs/site_notes.md`:

### Books to Scrape (`https://books.toscrape.com/`)
- Exactly 20 books per catalog page across 50 pages (1,000 total books).
- **Titles**: Visible link text is often truncated with ellipses (e.g. `A Light in...`), while the full title is preserved in the `title` attribute of `h3 > a`.
- **Prices**: Formatted with currency symbol `£` (e.g., `£51.77`), which can introduce encoding artifacts (`Â£`) if decoded incorrectly.
- **Ratings**: Stored as CSS classes on `p.star-rating` (`One`, `Two`, `Three`, `Four`, `Five`).
- **Availability**: Free-text containing stock counts (e.g. `In stock (22 available)`).
- **Categories**: 50 categories listed in the sidebar `div.side_categories ul li ul li a`. Books belong to single categories accessible through category pagination.
- **Product Descriptions**: Located on product detail pages under `#product_description + p`.
- **Next Page Links**: On page 1 the link is `catalogue/page-2.html`; on page 2+ it is `page-3.html`. Resolving dynamically via `urljoin` is necessary.
- **Robots.txt**: Responds with `HTTP 404 (Not Found)`, meaning crawling is unrestricted.

### Quotes to Scrape (`https://quotes.toscrape.com/`)
- Exactly 10 quotes per page across 10 pages (100 total quotes).
- **Quotes**: Enclosed in unicode curly quotes (`“` and `”`).
- **Authors**: Contained in `small.author` with corresponding biographical relative link `a[href^="/author/"]`.
- **Tags**: Multi-value links under `div.tags a.tag`.
- **Next Page Links**: Contained in `li.next > a[href]`. On page 10, the element is absent.
- **Robots.txt**: Responds with `HTTP 404 (Not Found)`, meaning crawling is unrestricted.

---

## 8. How Pagination Works

Pagination is orchestrated by `BaseScraper.paginate(start_url, parse_page, next_selector)`:
1. **Loop Execution**: Tracks `visited` URLs in a `set` to prevent cyclical redirects.
2. **Fetch and Parse**: Fetches the page markup, verifies HTTP status, decodes as UTF-8, parses with `lxml`, and passes the parsed document to `parse_page()`.
3. **Selector Following**: Searches for the next link element matching `next_selector` (`li.next > a`). If found, resolves the relative `href` against the current page URL using `urllib.parse.urljoin()` and advances to the next page.
4. **Termination**: When `next_selector` yields `None`, the loop terminates cleanly.
5. **Failure Recovery & Circuit Breaking**: If an HTTP request fails, the failure is recorded in `failed_pages`, `consecutive_failures` increments, and `guess_next()` predicts the next sequential URL (e.g., transforming `/page/1/` to `/page/2/`). If `consecutive_failures >= MAX_CONSECUTIVE_FAILURES` (3), pagination terminates to protect against infinite loops or unresponsive servers.

---

## 9. Data Model

The pipeline maps all scraped entities into a unified 12-column canonical schema:

| Column | Books to Scrape | Quotes to Scrape | Description / Rationale |
|---|:---:|:---:|---|
| `source` | `"Books to Scrape"` | `"Quotes to Scrape"` | Origin identifier. |
| `name_or_title` | Book Title (string) | Quote Text (string) | Primary textual identifier; outer quotation marks stripped on quotes. |
| `category` | Book Category (string) | `None` (empty) | Product taxonomy from sidebar crawl. |
| `price` | Float (e.g. `51.77`) | `None` (empty) | Cleaned decimal currency amount. |
| `rating` | Integer `1`..`5` | `None` (empty) | Star rating converted from word values. |
| `author` | `None` (empty) | Author Name (string) | Author attribution. |
| `tags` | `None` (empty) | Semicolon list (`"tag1;tag2"`) | Lowercase, deduplicated, sorted tag string. |
| `source_url` | Book Detail URL | Quote Listing Page URL | URL where record was found. Quotes do not have dedicated single-quote pages, so `source_url` points to the paginated page where the quote appeared. |
| `scraped_at` | ISO 8601 UTC Timestamp | ISO 8601 UTC Timestamp | Exact UTC extraction time (`YYYY-MM-DDTHH:MM:SS+00:00`). |
| `description` | Product Description | `None` (empty) | Extracted from detail page when `--with-details` is enabled. Added to support full text analysis. |
| `availability` | In Stock Status (string) | `None` (empty) | Inventory availability state from product pod. Added to support inventory tracking. |
| `author_url` | `None` (empty) | Absolute Author Bio URL | Absolute link to author biography. Added to support author disambiguation. |

---

## 10. Cleaning Approach

Implemented as pure, side-effect-free functions in `processing/cleaning.py`:
- `clean_text(value)`: Returns `None` for non-strings/None, replaces non-breaking spaces `\xa0` with ASCII spaces, collapses internal whitespace, strips edges, and converts empty strings to `None`.
- `strip_quotes(value)`: Cleans text, strips straight double quotes `"` and Unicode curly quotes (`\u201c`, `\u201d`, `\u2018`, `\u2019`), and collapses whitespace.
- `clean_price(raw)`: Strips commas, extracts the first matching floating-point pattern using regex `(\d+(?:\.\d+)?)`, rounds to 2 decimal places, and handles dirty encodings like `Â£`. Returns `None` if absent.
- `clean_rating(raw)`: Maps English number words (`one`, `two`, `three`, `four`, `five`) case-insensitively to integers `1` through `5`.
- `clean_tags(tags)`: Normalizes each tag in list or semicolon string, converts to lowercase, deduplicates via set, sorts alphabetically, and joins with `;`. Returns `None` if empty.
- `normalize_url(url, base)`: Resolves relative URLs using `urljoin`, validates scheme (`http` or `https`) and presence of `netloc`. Disallows `ftp://` or invalid schemes.

---

## 11. Validation Approach

Implemented in `processing/validation.py`. Every cleaned record is checked against business rules and data constraints. If any rule fails, the record is rejected, a `WARNING` is logged, and failure reasons are categorized:

| Reason Code | Trigger Condition |
|---|---|
| `invalid_source` | `source` is not in `config.VALID_SOURCES`. |
| `missing_name_or_title` | `name_or_title` is None, non-string, or blank. |
| `invalid_source_url` | `source_url` is missing or does not start with `http://` or `https://`. |
| `invalid_scraped_at` | `scraped_at` is missing or not a valid ISO 8601 timestamp string. |
| `invalid_price` | Source is Books and `price` is None, not numeric, or negative. |
| `invalid_rating` | Source is Books and `rating` is not an integer in `1`..`5`. |
| `missing_category` | Source is Books and `category` is missing or blank. |
| `missing_author` | Source is Quotes and `author` is missing or blank. |
| `invalid_author_url` | Source is Quotes and `author_url` is present but does not begin with `http://` or `https://`. |
| `cleaning_error` | Assigned by `process_source` if `clean_fn` raises an unhandled exception. |

---

## 12. Deduplication Approach

Implemented in `processing/deduplication.py`:
- **Composite Key Generation**:
  - **Books**: `source | title`
  - **Quotes**: `source | author | quote_text`
- **Normalization Rules**: Lowercase, remove all punctuation using regex `[^\w\s]`, and collapse all whitespace before hashing.
- **Cryptographic Fingerprint**: The normalized components are joined with `|` and hashed via SHA-256 (`hashlib.sha256().hexdigest()`).
- **Deduplication Strategy**: Records are filtered in-place preserving the first occurrence. Duplicate records are removed from the final dataset rather than merely flagged so downstream analytical tools receive clean, unique entities. Each duplicate is logged at `WARNING`.
- **Empirical Results**: On the live `books.toscrape.com` site, exactly **1 duplicate** is present in the source catalog (*"The Star-Touched Queen"*). The pipeline correctly isolated and removed this duplicate, yielding 999 unique books and 100 quotes (1,099 total records). Unit tests in `tests/test_deduplication.py` rigorously prove the hashing and partitioning logic.

---

## 13. Error-Handling Approach

- **Resilient HTTP Session**: `requests.Session` mounted with `urllib3.util.Retry(total=3, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])`.
- **Error Isolation**: `process_source()` wraps each data source in independent `try...except` blocks. If Quotes fails or returns 404, Books continues uninterrupted.
- **Record-Level Isolation**: Individual parsing or cleaning errors skip only the affected record and log a warning; remaining records on the page continue processing.
- **Fail-Safe Missing Pages**: Unreachable pages trigger `guess_next()` to skip ahead, while circuit breaking triggers if 3 consecutive pages fail.

---

## 14. Output Description

- `output/final_dataset.csv`: Cleaned, validated, and deduplicated records with exact 12-column header.
- `output/summary_report.json`: Structured operational metrics including start time, end time, duration in seconds, per-source breakdown (collected, cleaned, rejected, rejected_by_reason, duplicates_removed, final_count), totals, reconciliation verification (`reconciles: true`), and failed URL logs.
- `logs/scraper.log`: Timestamped audit trail tracking every page crawl, HTTP status, robots.txt event, warning, and summary output.

---

## 15. Assumptions

1. Target websites remain online at `https://books.toscrape.com/` and `https://quotes.toscrape.com/`.
2. Target websites continue to allow public crawling without requiring authentication or cookies.
3. Currency across Books to Scrape is British Pounds Sterling (`£`).
4. English rating words remain within `One` through `Five`.
5. Quote authors are non-empty string entities.

---

## 16. Known Limitations

- **Book Descriptions**: Set to `None` by default to avoid making 1,000 additional HTTP requests. Can be populated by passing `--with-details` (adds ~8–10 minutes with polite delay).
- **Author Detail Pages**: The scraper captures `author_url` but does not crawl author biography pages for birth dates or locations.
- **Synchronous Execution**: The crawler operates sequentially with a 0.5s polite delay; asynchronous concurrency is omitted to prioritize target server politeness.
- **Markup Coupling**: Selectors rely on current HTML class structures (`article.product_pod`, `div.quote`). Major DOM redesigns will require selector updates.

---

## 17. AI Usage Summary

This application was engineered using Google AI Studio (Gemini 3.8 Flash) via structured, prompt-driven iteration. Every module was generated against explicit contracts, reviewed, executed live, and validated with offline unit tests.

---

## 18. What I Would Change for Production

1. **Distributed Queue & Concurrency**: Replace sequential synchronous scraping with an asynchronous engine (`asyncio` / `aiohttp` or `Scrapy` with `Celery`/`Redis`) while respecting domain-specific rate limits.
2. **Proxy & IP Rotation**: Integrate rotating residential proxies to mitigate IP blocking or cloud firewall rate limiting.
3. **Headless Browser Fallback**: Introduce Playwright or Puppeteer integration for pages utilizing client-side JavaScript rendering (SPA).
4. **Database Storage**: Replace CSV output with direct ingestion into PostgreSQL / BigQuery with schema migrations and upsert deduplication.
5. **Observability & Alerting**: Export Prometheus metrics and integrate Sentry for real-time alerting on schema drift or elevated failure rates.


## 12. Bonus Features Implemented

The project now includes the requested optional bonus features while preserving the original 12-column `final_dataset.csv` schema:

- **B1 Configurable settings + CLI**: `SCRAPER_DELAY`, `SCRAPER_TIMEOUT`, `SCRAPER_MAX_RETRIES`, `SCRAPER_OUTPUT_DIR`, and `SCRAPER_LOG_LEVEL`; CLI values take precedence over environment values. Added `--sources`, `--timeout`, `--retries`, and `--max-pages`.
- **B2 Thread-safe rate limiting**: `utils/rate_limiter.py` reserves request slots so concurrent scrapers remain polite.
- **B3 Retry proof tests**: offline tests cover 503 retry/success, repeated 500, non-retried 404, adapter settings, and connection refusal.
- **B4 Page checkpoints/resume**: `utils/checkpoint.py` stores atomic page-level JSON checkpoints. Use `--resume` to continue an incomplete run and `--no-checkpoint` to disable checkpoint persistence. Book category crawling is intentionally not checkpointed.
- **B5 Incremental state**: `utils/state.py` tracks SHA-256 fingerprints between runs. When a previous state exists, `new_records.csv` contains only new records; `final_dataset.csv` is never changed by incremental mode. Use `--no-state` to disable it. State is saved only after a successful CSV/summary run without failed/incomplete pages. Every listing page is still fetched because the practice sites do not expose a modified-since API.
- **B6 Parallel sources**: `--parallel` uses one worker per selected source and preserves source order in the final result. Each scraper owns its own session and rate limiter.
- **B7 Optional PostgreSQL**: `--db postgres` enables lazy PostgreSQL persistence using `DATABASE_URL`. The `records` table uses the SHA-256 fingerprint as its primary key and parameterized `INSERT ... ON CONFLICT DO UPDATE` upserts. CSV output remains authoritative and database failures do not change the process success decision. Install `requirements-postgres.txt` only when database mode is needed.
- **B8 Documentation**: this README and `AI_USAGE.md` document the implemented bonus features and verification commands.
- **B9 Regression**: the complete offline suite remains green alongside the bonus tests, and Python compilation succeeds.

### Bonus command examples

```bash
python main.py
python main.py --sources quotes --delay 0.2
python main.py --max-pages 5
python main.py --resume
python main.py --no-checkpoint --no-state
python main.py --parallel
python main.py --db postgres
```

`DATABASE_URL` is read only from the environment; secrets are never placed in source code or reports.

### Offline verification

```bash
pytest -q
python -m compileall -q .
# `compare_runs.py` is an internal verification helper and is intentionally not included in the submission ZIP.
```

The regression comparator ignores `scraped_at` and checks the original summary keys and totals.
