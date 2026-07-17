# Price Change Reports — schema for agents

**Location:** `aipickvault/Price Change Reports/`  
**Purpose:** Machine-scannable history of AI Pick Vault pricing so future sessions can compare runs without re-reading chat logs.

## File naming

```text
YYYY-MM-DD-full-site-prices.json   # preferred: ALL retailers + vs last push
YYYY-MM-DD-full-site-prices.md     # human/agent table companion
YYYY-MM-DD-amazon-pass.json        # older Amazon-only pass format (schema v1)
YYYY-MM-DD-<short-label>.json      # optional specials
```

## Preferred report: `full-site-prices` (schema_version 2)

**Report type:** `aipickvault_full_site_prices`

| Field | Meaning |
|-------|---------|
| `last_site_price_push` | Git commit that last changed `index.html` prices (baseline) |
| `summary` | Counts: catalog size, live Amazon/eBay OK, material moves vs push |
| `scan_table` | **Primary scan** — one row per product, all key prices |
| `material_amazon_vs_last_push` | Live Amazon deltas ≥ $2 or 5% vs last push |
| `products` | Full detail per ASIN |

### Each product includes

| Block | Contents |
|-------|----------|
| `site_now` | What `index.html` shows **now**: `price`, `list`, `amazon`, `walmart`, `ebay_snapshot` |
| `site_at_last_push` | Same fields from **last price push** commit |
| `live` | Market check at report time: `amazon`, `amazon_list`, `ebay`, `ebay_title`, ok flags |
| `vs_last_push` | Deltas: site field changes + live Amazon/eBay vs push baseline |
| `vs_site_now` | Live market vs current site snapshots |
| `live_retailer_compare` | Live eBay vs live Amazon (who is cheaper) |

### How to scan

1. Newest `*-full-site-prices.json` by `pass_date` / filename.
2. Read `summary`, then `scan_table` (all products, all retailers).
3. Drill into `products[i]` for titles, list prices, and exact deltas.
4. Join multi-run history on **`asin`**.
5. **Walmart** is site snapshot only (no live API yet).
6. **Live eBay** is New + free US ship + accessory filters; still verify `ebay_title` for false matches.
7. Do **not** treat `ebay_snapshot` as live eBay — that is the static catalog fallback in `index.html`.

## Legacy report: `amazon-pass` (schema_version 1)

Amazon-focused only. Fields: `applied_changes`, `soft_drifts`, `all_products` with `old_amazon` / `new_amazon` / `old_ebay_snapshot`. Kept for history; prefer full-site reports going forward.

## Related commands

```powershell
cd C:\Users\bamte\aipickvault
python ebay-worker\price_pass_extract.py
# Amazon live (PowerShell): ebay-worker\_fetch_amazon_ps.ps1
curl.exe -sS -X POST "https://ebay-api.aipickvault.com/v1/refresh"
curl.exe -sS "https://ebay-api.aipickvault.com/v1/snapshot" -o ebay-worker\_snap.json
python ebay-worker\build_full_price_report.py
```

## What not to put here

- Secrets, PA-API keys, eBay client secrets  
- Full Amazon HTML dumps  
- TikTok / marketing content  
