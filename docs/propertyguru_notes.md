# PropertyGuru scraper notes

**Status: UNVERIFIED.** The search-URL query parameters and CSS selectors in
`src/property_monitor/scrapers/propertyguru.py` are best-effort placeholders
written without access to the live site. Before relying on this scraper,
manually verify the following against the real site and update this file
with the date you confirmed it:

## To verify

1. **Search URL construction** (`_build_search_url`)
   - Perform a manual search on propertyguru.com.sg with a location, price
     range, and property type filter, then inspect the resulting URL's query
     parameters (names and value formats for min/max price, property type
     codes, rent-vs-sale path segment).
   - Confirm whether results can be forced to sort newest-first via a URL
     param (needed since v1 only checks page 1).

2. **Listing card selector** (`LISTING_CARD_SELECTOR`)
   - Open browser dev tools on a real search results page and find a stable
     attribute identifying each result card -- prefer `data-testid`/`aria-*`
     attributes over hashed/utility CSS class names, which churn between
     deployments.

3. **Per-card field selectors** (`_parse_card`)
   - Title, price, location, and bedroom-count element selectors.
   - Confirm whether price is plain text or split across nested spans
     (e.g. currency symbol in its own element).
   - Confirm whether bedroom count is exposed via an `aria-label` or as
     plain text next to an icon.

4. **Listing ID extraction** (`_extract_listing_id`)
   - Confirm the numeric ID actually appears at the end of listing URLs in
     the assumed format; adjust the regex if not.

## Verification log

| Date | Verified by | Notes |
|------|-------------|-------|
| _(none yet)_ | | Placeholders only -- do not trust in production until this table has an entry. |
