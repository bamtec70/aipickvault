# AI Pick Vault — agent notes

## Pricing / match quality

- **Recurring checklist:** `docs/PRICE_MATCH_CHECKLIST.md`  
  Run the “Every 3 days” section when asked about prices, match quality, or when a scheduled reminder fires.
- **eBay API:** `https://ebay-api.aipickvault.com`  
  Matching: accessory filters, model-token title require, free-ship **verified on item detail**.  
  Deploy from `ebay-worker/` with portable Node + `wrangler.js deploy` if `src/` changes.
- **Amazon:** Snapshots in `index.html` until PA-API (10 sales/30d). Prefer camelcamelcamel over scraping Amazon.
- **Never** blindly write eBay lows into the catalog without title + free-ship checks (Klein bit problem).

## TikTok / site

- Site root: `index.html` (GitHub Pages).  
- Affiliate tags and eBay campid live in `index.html` JS constants.
