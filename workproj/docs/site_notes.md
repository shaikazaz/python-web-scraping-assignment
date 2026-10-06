# Site Inspection Notes & Verified Selectors

This document records the exact DOM structures, selectors, pagination mechanics, and robot policies discovered by inspecting the live target sites: **Books to Scrape** (`https://books.toscrape.com/`) and **Quotes to Scrape** (`https://quotes.toscrape.com/`).

---

## 1. Verified Selectors Summary Table

| Field / Feature | Target Site | Verified CSS Selector / Attribute | Sample Value | Notes / Nuances |
|---|---|---|---|---|
| **Book Record Container** | Books to Scrape | `article.product_pod` | N/A | Exactly 20 records per page. |
| **Book Title** | Books to Scrape | `h3 > a[title]` (attribute: `title`) | `"A Light in the Attic"` | Inner text may be truncated with ellipses (`...`). Always extract the `title` attribute for the full title. |
| **Book Product URL** | Books to Scrape | `h3 > a[href]` | `"catalogue/a-light-in-the-attic_1000/index.html"` | Relative URL; must be joined with current page URL via `urllib.parse.urljoin`. |
| **Book Price** | Books to Scrape | `p.price_color` | `"£51.77"` | Includes currency symbol (`£`). Raw extraction keeps raw string. |
| **Book Rating** | Books to Scrape | `p.star-rating` (class attribute) | `"star-rating Three"` | Rating value is embedded as the second CSS class (`One`, `Two`, `Three`, `Four`, `Five`). |
| **Book Availability** | Books to Scrape | `p.instock.availability` or `p.availability` | `"In stock (22 available)"` | Raw text contains leading/trailing whitespace and icon element. |
| **Book Category** | Books to Scrape | `ul.breadcrumb > li:nth-of-type(3) > a` | `"Poetry"` | Found on the individual product detail page. |
| **Book Description** | Books to Scrape | `#product_description ~ p` | `"It's hard to imagine..."` | Sibling `<p>` immediately following `#product_description` header on product page. Nullable if book has no description. |
| **Category Sidebar** | Books to Scrape | `div.side_categories ul.nav-list > li > ul > li > a` | `"Travel"`, `"Mystery"` | Lists all 50 categories with their sub-links. |
| **Book Next Page** | Books to Scrape | `li.next > a[href]` | `"catalogue/page-2.html"` / `"page-3.html"` | Relative link. On page 1 it is `catalogue/page-2.html`, on page 2+ it is `page-3.html`. Dynamic `urljoin` is required. |
| **Quote Record Container** | Quotes to Scrape | `div.quote` | N/A | Exactly 10 records per page. |
| **Quote Text** | Quotes to Scrape | `span.text` | `“The world as we have created it...”` | Enclosed with curly quotes (`“` and `”`). Raw extraction keeps full text. |
| **Quote Author** | Quotes to Scrape | `small.author` | `"Albert Einstein"` | Text node within author span. |
| **Author URL** | Quotes to Scrape | `span > a[href*="/author/"]` | `"/author/Albert-Einstein"` | Relative link labeled `(about)`. Must be converted to absolute URL via `urljoin`. |
| **Quote Tags** | Quotes to Scrape | `div.tags > a.tag` | `["change", "deep-thoughts", "thinking", "world"]` | Multiple tags per quote element. Extracted as a list of strings. |
| **Quote Next Page** | Quotes to Scrape | `li.next > a[href]` | `"/page/2/"` | Absent on the last page (page 10). |

---

## 2. Pagination Behavior & Last Page Termination

### Books to Scrape
- Each page lists 20 books.
- The next page link exists inside `<li class="next"><a href="...">next</a></li>`.
- Relative links vary between the root page (`catalogue/page-2.html`) and paginated URLs (`page-3.html`). Resolving with `urllib.parse.urljoin(current_url, next_href)` handles both accurately.
- On the final catalog page (page 50), the `<li class="next">` element is completely absent from the DOM, terminating pagination.

### Quotes to Scrape
- Each page lists 10 quotes.
- The next page link exists inside `<li class="next"><a href="/page/2/">Next ...</a></li>`.
- On the final page (`https://quotes.toscrape.com/page/10/`), `b.select_one("li.next")` returns `None` (empty list `[]`).
- Checking `if not next_el:` reliably terminates the crawl without relying on hardcoded page thresholds.

---

## 3. Robots.txt Inspection & Policies

- **Books to Scrape (`https://books.toscrape.com/robots.txt`)**: Returns **HTTP 404 (Not Found)**.
- **Quotes to Scrape (`https://quotes.toscrape.com/robots.txt`)**: Returns **HTTP 404 (Not Found)**.
- **Interpretation**: Under the robots exclusion standard, a 404 response signifies that no scraping restrictions or disallow rules exist on either site. The scrapers are permitted to crawl all public pages while adhering to ethical scraping policies (e.g., 0.5s polite delay between requests, descriptive User-Agent header).
