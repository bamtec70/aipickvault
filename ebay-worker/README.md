# AI Pick Vault — price worker (eBay live + daily snapshots)

Cloudflare Worker that:

1. Calls the **eBay Browse API** for lowest **New + free US shipping + Buy It Now** prices  
2. Stores a **daily catalog snapshot** in Cloudflare KV (cron at 13:00 UTC)  
3. Optionally refreshes **Amazon** prices via **Product Advertising API 5.0** when secrets are set  

The static site loads `/v1/snapshot` on each visit, then also requests live eBay prices.

**From the Vault (TikTok):** `GET /v1/tiktok` returns the latest `@aipickvault` posts (cached ~3 hours in KV). Force refresh with `POST /v1/tiktok/refresh` **requires** header `X-Refresh-Token` (Worker secret `REFRESH_TOKEN`). The site prefers this live feed and falls back to `tiktok/videos.json` in the repo.

**Abuse protection:** per-IP rate limits, CORS allowlist, fail-closed refresh auth. Details: [`docs/SECURITY.md`](../docs/SECURITY.md).

---

## Daily automatic refresh

| What | How |
|------|-----|
| Schedule | GitHub Actions (primary) + optional Cloudflare Cron |
| Storage | KV binding `PRICES` → key `daily` |
| eBay | Always (with your existing app keys) |
| Amazon | Only if PA-API secrets are configured |
| Manual run | `POST /v1/refresh` **with** `X-Refresh-Token` |
| Chunking | Full refresh fans out **one Worker invocation per ~6 products** (fresh subrequest budget). Partial body: `{ "partial": true, "offset": 0, "limit": 6, "reset": true }` |

**Required secret:** `REFRESH_TOKEN` on the Worker **and** as a GitHub Actions repo secret.  
The Worker uses `REFRESH_TOKEN` to call itself for each chunk, so the secret must be set on the Worker (not only in GitHub).

```powershell
# Generate a token, then:
node .\node_modules\wrangler\bin\wrangler.js secret put REFRESH_TOKEN

# Authorized full refresh (chunk-orchestrated)
curl.exe -X POST "https://ebay-api.aipickvault.com/v1/refresh" -H "X-Refresh-Token: YOUR_TOKEN"
```

## 1. Create an eBay developer app

1. Go to [developer.ebay.com](https://developer.ebay.com/) and sign in (same account as EPN is fine).
2. **Application Keys** → create a keyset for **Production** (not only Sandbox).
3. Copy:
   - **App ID (Client ID)**
   - **Cert ID (Client Secret)**
4. Under the app, ensure you can use OAuth **client credentials** with scope  
   `https://api.ebay.com/oauth/api_scope`  
   (default for Browse / public data).

> First-time apps sometimes need a short production access request for Buy APIs. If search returns `403` / insufficient scope, check the keyset status in the developer portal.

## 2. Install Wrangler and log in

```powershell
cd C:\Users\bamte\aipickvault\ebay-worker
npm install -g wrangler
npx wrangler login
```

## 3. Deploy and set secrets

```powershell
cd C:\Users\bamte\aipickvault\ebay-worker
npx wrangler deploy

npx wrangler secret put EBAY_CLIENT_ID
# paste Client ID

npx wrangler secret put EBAY_CLIENT_SECRET
# paste Client Secret

# Optional — same EPN campaign as the site (affiliate item URLs when available)
npx wrangler secret put EBAY_CAMPID
# paste 5339165183
```

Production custom domain (already configured in `wrangler.toml`):

`https://ebay-api.aipickvault.com`

## 4. Point the website at the worker

In `index.html`, set:

```js
const EBAY_PRICE_API = "https://ebay-api.aipickvault.com";
```

Commit and push so GitHub Pages picks it up.

## 5. Smoke test

```powershell
# Health
curl https://ebay-api.aipickvault.com/health

# Single product
curl "https://ebay-api.aipickvault.com/v1/price?q=Anker%20charger&id=TEST"
```

Batch:

```powershell
curl -X POST https://ebay-api.aipickvault.com/v1/prices `
  -H "Content-Type: application/json" `
  -d "{\"items\":[{\"id\":\"B0TEST\",\"q\":\"Anker charger\"}]}"
```

## API behavior

| Filter | Browse API |
|--------|------------|
| New only | `conditions:{NEW}` |
| Free shipping | `maxDeliveryCost:0` |
| US location | `itemLocationCountry:US` |
| Buy It Now | `buyingOptions:{FIXED_PRICE}` |
| Sort | `sort=price` (lowest first) |

- Results cached **6 hours** (Cloudflare Cache API).
- Preferred batch **15** (site always chunks; avoids Worker subrequest limits).
- Absolute max **250** per POST (abuse ceiling only). Normal catalog growth must not hard-fail.
- Concurrency **3** parallel eBay searches inside the worker.
- Health exposes `preferredBatch`, `absoluteMaxBatch`, and `catalogSize`.

## Optional: custom domain

In Cloudflare dashboard → Workers → your worker → **Triggers** → add e.g. `ebay-api.aipickvault.com` (requires the domain on Cloudflare DNS).

## Amazon live prices (optional but recommended)

Amazon does **not** allow scraping. You need free **Product Advertising API** access from Amazon Associates:

1. Go to [Associates Central](https://affiliate-program.amazon.com/) → **Tools** → **Product Advertising API**  
2. Request/create credentials (Access Key + Secret Key)  
3. Partner tag is your store ID (site already uses `wethepeopl0b9-20`)  
4. Set secrets:

```powershell
cd C:\Users\bamte\aipickvault\ebay-worker
npx wrangler secret put AMAZON_ACCESS_KEY
npx wrangler secret put AMAZON_SECRET_KEY
npx wrangler secret put AMAZON_PARTNER_TAG
# paste wethepeopl0b9-20
npx wrangler deploy
curl https://ebay-api.aipickvault.com/v1/refresh
```

Until PA-API is set, **eBay still auto-refreshes daily + live**; Amazon stays as catalog snapshots.

### Keep catalog in sync

When you add/remove products on the site:

```powershell
python extract_catalog.py
# copies catalog.json → then
npx wrangler deploy
curl https://ebay-api.aipickvault.com/v1/refresh
```

## Security notes

- Never put Client Secret or Amazon Secret Key in `index.html` or git.
- This worker only exposes read-only price search; CORS is open (`*`) so the static site can call it.
- Optional: `wrangler secret put REFRESH_TOKEN` to require `X-Refresh-Token` on `/v1/refresh`.
- If abuse becomes an issue, lock CORS to `https://aipickvault.com` and add a simple rate limit.
