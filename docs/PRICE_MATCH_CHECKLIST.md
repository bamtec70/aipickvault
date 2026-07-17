# AI Pick Vault — price match checklist

**Purpose:** Keep Amazon snapshots and eBay matches honest without PA-API yet.  
**Cadence:** Light check **every 3 days**; deeper Amazon pass **weekly** (or after big sales/Prime Day).  
**Owner:** You + Grok (when reminded or when you ask “run the price checklist”).

---

## Already automated (do not redo daily)

| What | How | Notes |
|------|-----|--------|
| eBay catalog refresh | GitHub Action daily ~8 AM CT → `POST /v1/refresh` | New + free ship + title/model filters + **item-detail free-ship verify** |
| Live eBay on site | Page load hits `ebay-api.aipickvault.com` | **Auto-chunks** `/v1/prices` so catalog growth never shows “eBay API offline”; also rejects eBay far below/above Amazon (~55%–275%) |
| Amazon live | Blocked until PA-API (10 sales / 30 days) | Snapshots only until then |

Worker: `https://ebay-api.aipickvault.com`  
Repo workflow: `.github/workflows/daily-price-refresh.yml`

---

## Every 3 days (~15 minutes) — match health

### 1. Confirm daily refresh is healthy
```bash
curl -sS "https://ebay-api.aipickvault.com/health"
curl -sS "https://ebay-api.aipickvault.com/v1/snapshot" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('updatedAt'), d.get('count'), 'errors sample', (d.get('errors') or [])[:3])"
```
- **Pass:** `updatedAt` within ~48h, `count` ≈ catalog size (see `catalogSize` on `/health`).
- **Fail:** empty snapshot / old date → `curl -sS -X POST "https://ebay-api.aipickvault.com/v1/refresh"` and recheck GH Action runs.

### 2. Spot-check 5 products (rotate categories)
Always include at least one **tool with a model number** (e.g. Klein `32500`, DEWALT kit).

```bash
# Example: Klein must be full set free-ship, not a bit
curl -sS "https://ebay-api.aipickvault.com/v1/price?fresh=1&id=B0015SBILG&q=Klein%20Tools%2032500%2011-in-1%20Screwdriver"
```

For each spot-check, open the returned `itemWebUrl` and confirm:
- [ ] Title is the **whole product** (not replacement bit / cover / cable only)
- [ ] **Free shipping** US
- [ ] Price within ~55%–275% of Amazon snapshot on the site
- [ ] Model number in title when relevant

**Rotation idea (cycle each visit):**
1. Tools: Klein or DEWALT combo  
2. Gig: tire inflator or dash cam  
3. Home: walking pad or eufy  
4. Tech: Anker / EcoFlow power bank  
5. Van: BougeRV fridge or Jackery  

### 3. Scan for “too good to be true” eBay
On [aipickvault.com](https://aipickvault.com), glance at compare strips. Flag any eBay that looks **&lt; half of Amazon** — site should filter; if one slips through, note ASIN and fix query in `ebay-worker/src/catalog.json`.

### 4. Optional: one Amazon sanity check (high movers)
Pick 3–5 high-traffic ASINs and verify on camelcamelcamel or Amazon:
- Tire inflator, DEWALT combo, Coleman chair, Jackery, Anker SOLIX  
- If delta ≥ ~$2 or ~5%, update `index.html` snapshot (price + `compare.amazon`).

---

## Weekly (~30–45 minutes) — full pass lite

1. Run extract:  
   `python ebay-worker/price_pass_extract.py`  
2. Sample camelcamelcamel for **material movers** (power stations, tools on deal, anything user reported wrong).  
3. Apply only verified changes to `index.html`; commit/push.  
4. `POST /v1/refresh` so eBay KV snapshot is fresh.  
5. Deploy worker only if `ebay-worker/src/index.js` or `catalog.json` `q` strings changed.

Do **not** bulk-apply eBay prices into `index.html` without title checks (false matches).

---

## When something looks wrong

| Symptom | Action |
|---------|--------|
| Wrong eBay SKU (bit, cover, cable) | Tighten `q` in `ebay-worker/src/catalog.json` + `src/catalog.json`; redeploy worker; `?fresh=1` retest |
| Free-ship lie | Worker already verifies item detail; if still wrong, note itemId and add title reject keyword |
| Amazon way off | Update snapshot via camel; don’t scrape Amazon HTML |
| Snapshot stale | Trigger GH Action “Daily price refresh” or POST `/v1/refresh` |
| Site ignores live eBay | Check client filter `ebayPriceLooksSane` vs Amazon; may be intentional |

---

## Commands cheat sheet (Windows)

Portable Node (if needed):
```powershell
$env:Path = "C:\Users\bamte\AppData\Local\nodejs\node-v24.18.0-win-x64;" + $env:Path
```

Worker deploy (only after code/query changes):
```powershell
cd C:\Users\bamte\aipickvault\ebay-worker
node .\node_modules\wrangler\bin\wrangler.js deploy
```

Refresh + Klein smoke test:
```powershell
curl.exe -sS -X POST "https://ebay-api.aipickvault.com/v1/refresh"
curl.exe -sS "https://ebay-api.aipickvault.com/v1/price?fresh=1&id=B0015SBILG&q=Klein%20Tools%2032500%2011-in-1%20Screwdriver"
```

Lookup one eBay item (debug):
```powershell
curl.exe -sS "https://ebay-api.aipickvault.com/v1/item?id=147380418292"
```

---

## Prompt to paste for Grok

```
Read C:\Users\bamte\aipickvault\docs\PRICE_MATCH_CHECKLIST.md and run the
"Every 3 days" checklist for AI Pick Vault. Fix only real mismatches.
Report: health/snapshot age, 5 spot-checks (ASIN, eBay price, title ok?),
any catalog q fixes or snapshot edits, and whether you refreshed/deployed.
```

---

## Reminder policy

- **Automated daily:** GH Action refresh (eBay).  
- **Every 3 days:** This checklist (Grok reminder or you paste the prompt).  
- **Weekly:** Amazon snapshot pass on movers.  
- **After PA-API unlock:** Prefer Worker Amazon secrets; checklist shrinks to eBay match QA + outliers.
