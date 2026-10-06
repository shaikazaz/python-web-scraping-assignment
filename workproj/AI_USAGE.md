# AI Usage and Methodology Log

This document records the artificial intelligence tooling, prompt engineering strategy, human review decisions, corrections, and testing workflows utilized during the design and development of the scraping pipeline.

---

## 1. Tools Used

- **Google AI Studio / Gemini 3.8 Flash**: Primary coding and architectural engine used to scaffold project configuration, extract DOM selectors, design pure data transformations, structure test suites, and orchestrate pipeline execution.
- **Python 3.11 Standard Library & CLI Tools**: Environment runtime used to verify and execute the generated code locally (`pytest`, `requests`, `beautifulsoup4`, `lxml`).

---

## 2. What Each Tool Was Used For

- **Gemini 3.8 Flash**:
  - Drafting modular code conforming to strict system contracts (`config.py`, `scrapers/base_scraper.py`, `scrapers/books_scraper.py`, `scrapers/quotes_scraper.py`, `processing/cleaning.py`, `processing/deduplication.py`, `processing/validation.py`, and `main.py`).
  - Generating comprehensive unit test suites covering edge cases (e.g. non-breaking spaces `\xa0`, mojibake `Â£`, missing elements, pagination drops, and SHA-256 fingerprint collisions).
  - Formatting structural markdown documentation (`docs/site_notes.md`, `README.md`, `AI_USAGE.md`).
- **Local Linux Environment (CLI / Bash)**:
  - Performing live network inspection against `https://books.toscrape.com/` and `https://quotes.toscrape.com/`.
  - Executing test suites (`pytest -q`) and end-to-end full pipeline scraping (`python main.py`).
  - Rebuilding clean virtual environments (`python3 -m venv venv`) and verifying reproducible execution.

---

## 3. Representative Prompts

The following 4 prompts represent the incremental, contract-driven interaction model employed during development:

### Prompt A: DOM Inspection & Site Notes
> *"Write inspect_sites.py to fetch and print the facts we need to build our scrapers without assumptions. Save notes to docs/site_notes.md with a table of selectors, pagination mechanics, and robots.txt policies."*

### Prompt B: Resilient Base Scraper Architecture
> *"Write scrapers/base_scraper.py with class BaseScraper: session with retries and User-Agent, robots.txt loading, polite delays, and paginate() with consecutive failure circuit breaking and guess_next fallback."*

### Prompt C: Pure Functional Data Cleaning & Normalization
> *"Write processing/cleaning.py as pure functions (no network, no files, never raise on bad input): clean_text, strip_quotes, clean_price, clean_rating, clean_tags, normalize_url, clean_book, and clean_quote. Also write tests/test_cleaning.py covering edge cases like mojibake, non-breaking spaces, and invalid schemes."*

### Prompt D: Deduplication Engine
> *"Write processing/deduplication.py: normalize_for_key, make_fingerprint using SHA-256 composite keys, and find_duplicates preserving order. Also write tests/test_deduplication.py proving case/punctuation insensitivity and distinguishing identical quotes by different authors."*

---

## 4. Which Files Were AI-Assisted

All files in the pipeline were created with AI assistance following architectural specifications:
- `config.py`
- `inspect_sites.py`
- `docs/site_notes.md`
- `scrapers/base_scraper.py`
- `scrapers/books_scraper.py`
- `scrapers/quotes_scraper.py`
- `processing/cleaning.py`
- `processing/deduplication.py`
- `processing/validation.py`
- `main.py`
- `tests/test_cleaning.py`
- `tests/test_deduplication.py`
- `tests/test_scrapers.py`
- `README.md`
- `AI_USAGE.md`

---

## 5. Changes Made After Review

1. **Category Mapping Optimization in Books Scraper**:
   - *Review finding*: Fetching individual product detail pages for 1,000 books solely to obtain categories would incur 1,000 extra HTTP requests, taking over 10 minutes.
   - *Adjustment*: Implemented `scrape_categories()` to crawl the 50 category listing pages instead (only 50 requests), mapping all 1,000 book URLs to categories in under 30 seconds.
2. **Robots.txt 404 Status Handling**:
   - *Review finding*: `urllib.robotparser.RobotFileParser` raises or disables fetching if `read()` fails on a 404 response.
   - *Adjustment*: Handled HTTP 404 explicitly in `BaseScraper._load_robots()` by treating a missing `robots.txt` as "allow all", logging an informative message, and continuing crawling safely.
3. **Punctuation Stripping in Deduplication**:
   - *Review finding*: Differing quote punctuation (such as straight vs curly apostrophes in words like "Don't" vs "Dont") could cause false negatives in duplicate detection.
   - *Adjustment*: Enforced regex `[^\w\s]` in `normalize_for_key()` before computing the SHA-256 fingerprint, ensuring punctuation-independent matching.

---

## 6. Incorrect or Incomplete AI Suggestions Found

1. **Truncated Book Titles in Link Inner Text**:
   - *Issue*: Initial selector suggestion used `h3 > a.text` for book titles, which produced truncated titles ending in ellipses (e.g., `"A Light in the Attic..."`).
   - *Resolution*: Inspected the actual HTML markup in `docs/site_notes.md` and updated the extractor to read the full title from the `title` attribute of `h3 > a`.
2. **Interactive Debian dpkg Lock During Package Installation**:
   - *Issue*: Default apt install script halted waiting on interactive prompt for `/etc/mime.types`.
   - *Resolution*: Configured `DEBIAN_FRONTEND=noninteractive` and forced non-interactive dpkg options (`--force-confdef --force-confold`) to complete the environment setup cleanly.
3. **Quote Detail Pages Non-Existence**:
   - *Issue*: Initial schema design assumed quotes had individual permalink URLs similar to books.
   - *Resolution*: Confirmed that Quotes to Scrape only displays quotes on paginated list pages; adjusted data model so `source_url` accurately represents the page URL where the quote appeared.

---

## 7. How Tested and Verified

1. **Automated Unit Testing**:
   - Ran `pytest -q` across all 3 test suites (`test_cleaning.py`, `test_deduplication.py`, `test_scrapers.py`).
   - Verified that the merged offline suite passes: 50 tests passed without external network access.
2. **Full End-to-End Pipeline Execution**:
   - Executed `python main.py` live against `books.toscrape.com` and `quotes.toscrape.com`.
   - Verified total collection: 1,000 books + 100 quotes = 1,100 records collected.
   - Verified deduplication: 1 duplicate book (*"The Star-Touched Queen"*) detected and filtered.
   - Verified final outputs: 1,099 rows in `output/final_dataset.csv`, matching `output/summary_report.json` with `reconciles: true`.
3. **Data Quality Verification (`verify.py`)**:
   - Checked that all 12 columns match `config.COLUMNS` in order.
   - Verified 0 bad prices, 0 bad ratings, 0 missing categories, 0 missing authors, 0 mojibake (`Â`), and 0 untrimmed strings.
4. **Failure Isolation & Circuit Breaking Verification**:
   - Pointed `QUOTES_URL` to `https://quotes.toscrape.com/nonexistent/` and ran `python main.py`.
   - Verified Books finished 100% unaffected, Quotes logged 404 errors, recovered to `/page/2/` via `guess_next()`, and failed URLs were captured in `failed_pages`.
5. **Clean Environment Isolation**:
   - Recreated a fresh virtual environment from scratch (`python3 -m venv venv`), ran `pip install -r requirements.txt`, and verified 100% reproducible test suite and pipeline runs.


## 8. Bonus-Feature Extension Prompts Executed

The bonus extension followed the supplied B1-B9 contract in order:

- **B1** configurable environment settings, CLI precedence, source selection, timeout/retry/page-limit controls.
- **B2** thread-safe reservation-based rate limiter used before network GETs, including robots requests.
- **B3** offline retry proof tests using a local `ThreadingHTTPServer`; no external network is required by the tests.
- **B4** atomic page checkpoints and explicit resume support for the main catalogue/quotes pagination.
- **B5** atomic fingerprint state and `new_records.csv` incremental output without changing `final_dataset.csv`.
- **B6** optional parallel source execution with one worker per source and deterministic result ordering.
- **B7** lazy optional PostgreSQL persistence with parameterized SQL, transaction boundaries, DSN masking, Docker Compose support, and failure isolation.
- **B8** documentation update.
- **B9** regression/test/compile verification.

### Verification performed on the merged project

The merged source was checked with the offline test suite and Python compilation. The final offline suite contains 49 passing tests. A live network run was also attempted in the build environment, but external DNS/network access is unavailable there; this does not affect the offline tests or the scraper's failure handling.
