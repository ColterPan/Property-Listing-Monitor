# 99.co scraper notes

Verified 2026-07-05 by fetching real search-result pages with Playwright and
inspecting the rendered DOM (see method below). Unlike PropertyGuru, 99.co
did **not** present a bot-check challenge to a plain headless browser with a
standard desktop user-agent -- it served real listing content directly.

## Confirmed

- **Search URL** is built from `https://www.99.co/singapore/{sale|rent}`
  plus query params. Confirmed by using the site's own search box (typed
  "Tampines", pressed Enter) and reading the resulting URL:
  ```
  https://www.99.co/singapore/sale?keywords=Tampines&main_category=all&name=Singapore
    &page_num=1&page_size=36&property_segments=residential&query_ids=singapore
    &query_name=Singapore&query_type=city&sort_field=relevance&sort_order=desc
  ```
  - `keywords` = freetext location string -- confirmed working (36 real
    Tampines-area listings returned).
  - `price_min` / `price_max` -- confirmed working: setting a narrow
    50,000,000-60,000,000 range dropped the result count from 36 to 4.
  - `query_type=city`, `query_ids=singapore`, `query_name=Singapore` -- kept
    fixed; these come from the site defaulting to city-wide scope when the
    typed keyword doesn't match a specific area/project suggestion exactly.
  - `page_size` -- confirmed working (row count matches).
- **Listing card container**: `[data-cy="listingCard"]` (also has
  `data-testid="grid-item-card-container"`). 36/36 cards found for the test
  query.
- **Title / address / detail URL**: a single element with
  `data-cy="listingName"` carries both the `href` to the listing detail page
  *and* the address text in a nested `<span>`, e.g.:
  ```html
  <h3 href="/singapore/sale/property/165-bukit-batok-west-avenue-8-hdb-bKkQB8cCtKqkJuHAFNUFN2"
      data-cy="listingName">
    <span>165 Bukit Batok West Avenue 8, 650165</span>
  </h3>
  ```
- **Listing ID**: the trailing alphanumeric segment of the URL path after
  the last hyphen (e.g. `bKkQB8cCtKqkJuHAFNUFN2`) -- NOT numeric like
  PropertyGuru. Confirmed consistent across 10+ sampled listing URLs (a
  mixed-case token of roughly 20 characters).
- **Price**: element with `data-cy="listingPsfPrice"` contains a `<ul>` with
  three `<li>` items: hidden currency code, the actual price (e.g.
  `S$ 520,000`), and the per-square-foot price (e.g. `S$ 465 psf`). Extract
  the `<li>` matching `S$ <digits with commas>` that does NOT end in `psf`.

## NOT confirmed / known gaps

- **Property type sub-filtering**: `property_segments=hdb` / `condo` /
  `landed` all returned zero results with an empty page title -- these are
  the wrong slugs. Only `property_segments=residential` (the site's own
  default) was confirmed to work. **The scraper currently does not filter
  by property type at the query level** -- it fetches all residential
  listings matching location + price for a search, regardless of the
  search's configured `property_type`. This should be revisited (try
  interacting with the actual property-type filter UI control to capture
  the real param/value it sends) before relying on property-type filtering.
- **"Newest first" sort**: tried `sort_field` values `updated_at`,
  `listed_date`, `newest`, `date` (with `sort_order=desc`) -- all returned
  the identical top result as the default `relevance`, meaning none of
  these guesses were recognized; the site silently falls back to its
  default ordering for unrecognized values. **Sort order could not be
  confirmed as "newest first."** v1 relies on dedup (comparing against
  previously-seen listing IDs) rather than sort order to catch new
  listings, so this is a soft gap (a listing could theoretically fail to
  appear on page 1 by relevance and be missed) rather than a hard bug, but
  should be revisited via the site's sort-order UI control.
- **Bedroom count**: no stable `data-cy`/`data-testid` attribute found;
  extracted via a best-effort regex over the card's visible text (`"3
  Beds"`). Not tied to a specific selector, so more prone to breaking
  silently if the wording changes -- acceptable since bedroom count is a
  non-critical field (parse failure just leaves it `None`, doesn't fail the
  whole card).
- **Rent URL path** (`/singapore/rent` instead of `/singapore/sale`) was
  inferred from 99.co's conventional URL structure, not independently
  verified against a real rent search. Low risk (same query-param
  structure expected) but flagged as an assumption, not a confirmed fact.

## Verification method (for re-verifying later)

1. `playwright.chromium.launch(headless=True)`, `new_page(user_agent=<real desktop Chrome UA>)`.
2. `page.goto("https://www.99.co/singapore/sale")`, click the search input,
   type a location, press Enter, and read `page.url` for the resulting
   query params.
3. `page.content()` to dump the rendered HTML and grep for
   `data-cy="listingCard"` and related attributes.
4. Vary one query param at a time and compare result counts / top result to
   confirm whether the site actually respects it (rather than silently
   ignoring an unrecognized param).
