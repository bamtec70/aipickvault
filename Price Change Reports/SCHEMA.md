# Price Change Reports — schema for agents

**Location:** `aipickvault/Price Change Reports/`  
**Purpose:** Machine-scannable history of AI Pick Vault Amazon snapshot passes so future sessions can compare runs without re-reading chat logs.

## File naming

```text
YYYY-MM-DD-amazon-pass.json
YYYY-MM-DD-<short-label>.json   # optional specials
```

Examples:
- `2026-07-16-amazon-pass.json`
- `2026-07-20-prime-day-check.json`

## One report = one JSON object

| Field | Type | Meaning |
|-------|------|---------|
| `schema_version` | int | Currently `1` |
| `report_type` | string | Always `aipickvault_price_change` |
| `report_id` | string | Stable id, usually same as filename without `.json` |
| `generated_at` | ISO-8601 UTC | When this file was written |
| `pass_date` | `YYYY-MM-DD` | Calendar day of the price pass |
| `repo_commit` / `repo_commit_short` | string | Git commit that landed site updates (if any) |
| `site` | string | Live site URL |
| `data_sources` | object | How Amazon/eBay were obtained |
| `rules` | object | Thresholds used to decide “apply” |
| `summary` | object | Counts and extremes for quick glance |
| `applied_changes` | array | **Primary scan target** — products written to `index.html` |
| `soft_drifts` | array | Fetched delta under threshold (not applied) |
| `all_products` | array | Full catalog snapshot for this pass |
| `notes` | string[] | Human caveats |

## Product record (each item in the arrays)

| Field | Type | Meaning |
|-------|------|---------|
| `asin` | string | Amazon ASIN (join key across reports) |
| `name` | string | Catalog product name |
| `ok` | bool | Live fetch succeeded |
| `error` | string\|null | Fetch/parse failure reason |
| `old_price` / `old_amazon` / `old_list` | number\|null | Values **before** this pass (`index.html`) |
| `old_walmart` / `old_ebay_snapshot` | number\|null | Other compare fields before pass |
| `new_amazon` / `new_list` | number\|null | Live Amazon (and list if seen) |
| `delta_usd` | number\|null | `new_amazon - old_amazon` |
| `delta_pct` | number\|null | Percent change (e.g. `20.1` = +20.1%) |
| `direction` | `up`\|`down`\|`flat`\|null | Sign of delta |
| `material_move` | bool | Met apply threshold |
| `applied_to_site` | bool | Written into `index.html` this pass |
| `source` | string | e.g. `displayPrice`, `camel`, `manual` |

## How to scan in a future session

1. List files in this folder (newest `pass_date` / filename first).
2. Load latest JSON; read `summary` then `applied_changes`.
3. To detect multi-pass trends, join on `asin` across reports and compare `new_amazon` (or `old_amazon` of next vs `new_amazon` of prior).
4. Do **not** treat `old_ebay_snapshot` as live eBay — that is a catalog fallback only. Live eBay is the worker API.

## Related code / commands

- Extract catalog: `python ebay-worker/price_pass_extract.py`
- Apply movers: `python ebay-worker/apply_price_moves.py` (threshold $2 / 5%)
- Site file: `index.html`
- Checklist: `docs/PRICE_MATCH_CHECKLIST.md`

## What not to put here

- Secrets, PA-API keys, eBay client secrets  
- Binary dumps, full Amazon HTML  
- TikTok / marketing content  
