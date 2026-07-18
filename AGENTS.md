# AI Pick Vault — agent notes

## Pricing / match quality

- **Recurring checklist:** `docs/PRICE_MATCH_CHECKLIST.md`  
  Run the “Every 3 days” section when asked about prices, match quality, or when a scheduled reminder fires.
- **eBay API:** `https://ebay-api.aipickvault.com`  
  Matching: accessory filters, model-token title require, free-ship **verified on item detail**, optional `requireTokens`, optional **`ebayPreferItemId` pin** in `ebay-worker/src/catalog.json`.  
  Responses include `rejected[]` reasons when no match.  
  Site must **not** keep stale eBay snapshots when live returns no match / sanity-filter fail — show **No free-ship New match**.  
  Deploy from `ebay-worker/` with portable Node + `wrangler.js deploy` if `src/` changes.
- **Batch / catalog size (do not regress):**  
  - Live site **always chunks** `POST /v1/prices` (~15 items). Never send the whole catalog in one unchunked client call.  
  - Reason for small chunks: Cloudflare Worker **subrequest limits** — one big batch can die mid-run even when status is 200.  
  - **Daily `POST /v1/refresh` is also chunked:** full refresh orchestrates ~6 products per Worker invocation (self-fetch with `X-Refresh-Token` + `X-Refresh-Chunk`). Do not reintroduce a single-invocation full-catalog crawl.  
  - Worker accepts large live batches (up to `absoluteMaxBatch` ~250); only that abuse ceiling returns `too_many_items`.  
  - Adding products must **never** surface **“eBay API offline”** solely because the catalog grew.  
  - Client also adapts if the server returns `too_many_items` (re-splits using `max` / `preferredBatch`) and continues other chunks if one fails.  
  - GitHub Action `daily-price-refresh.yml` must fail on subrequest errors or ebayOk rate &lt; 35%.
- **Amazon:** Snapshots in `index.html` until PA-API (10 sales/30d). Prefer camelcamelcamel over scraping Amazon.
- **Never** blindly write eBay lows into the catalog without title + free-ship checks (Klein bit problem).
- **Pin a known-good listing:** set `"ebayPreferItemId": "206001104339"` (and optional `"requireTokens": ["f7n","rear"]`) on the catalog row, redeploy worker.

## Adding a product (required sequence)

1. Add the product object in `index.html` (asin, prices, `ebayQ`, `scoreWhy`, compare, etc.).
2. `python ebay-worker/extract_catalog.py` — syncs `catalog.json` + `src/catalog.json`, keeps pins.
3. Deploy worker: `node ebay-worker/node_modules/wrangler/bin/wrangler.js deploy` (from `ebay-worker/`).
4. Refresh snapshot: `curl.exe -sS -X POST https://ebay-api.aipickvault.com/v1/refresh`
5. Commit + push `index.html` (and worker catalog if changed) so GitHub Pages updates.

## TikTok / site

- Site root: `index.html` (GitHub Pages).  
- Affiliate tags and eBay campid live in `index.html` JS constants.
