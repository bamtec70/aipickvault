# AI Pick Vault — eBay live price worker

Cloudflare Worker that calls the **eBay Browse API** and returns the lowest **New + free US shipping + Buy It Now** price for each product.

The static site (`index.html`) still works with snapshot prices if this worker is not configured.

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
- Batch max **40** products per request.
- Concurrency **3** parallel eBay searches inside the worker.

## Optional: custom domain

In Cloudflare dashboard → Workers → your worker → **Triggers** → add e.g. `ebay-api.aipickvault.com` (requires the domain on Cloudflare DNS).

## Security notes

- Never put Client Secret in `index.html` or git.
- This worker only exposes read-only price search; CORS is open (`*`) so the static site can call it.
- If abuse becomes an issue, lock CORS to `https://aipickvault.com` and add a simple rate limit.
