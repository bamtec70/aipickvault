# AI Pick Vault — price worker (eBay live + daily snapshots)

Cloudflare Worker that:

1. Calls the **eBay Browse API** for lowest **New + free US shipping + Buy It Now** prices  
2. Stores a **daily catalog snapshot** in Cloudflare KV (cron at 13:00 UTC)  
3. Optionally refreshes **Amazon** prices via **Product Advertising API 5.0** when secrets are set  

The static site loads `/v1/snapshot` on each visit, then also requests live eBay prices.

---

## Daily automatic refresh

| What | How |
|------|-----|
| Schedule | Cloudflare Cron `0 13 * * *` (daily ~8am US Central) |
| Storage | KV binding `PRICES` → key `daily` |
| eBay | Always (with your existing app keys) |
| Amazon | Only if PA-API secrets are configured |
| Manual run | `GET/POST https://ebay-api.aipickvault.com/v1/refresh` |

After deploy, run one manual refresh so the first snapshot exists:

```powershell
curl https://ebay-api.aipickvault.com/v1/refresh
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
- Batch max **80** products per request (site also chunks client-side).
- Concurrency **3** parallel eBay searches inside the worker.

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
