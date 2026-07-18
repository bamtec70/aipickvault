# AI Pick Vault — Security

This site is **static HTML + one Cloudflare Worker**. That is already a strong
design: no user logins, no password database, no checkout on aipickvault.com.

Two risks still matter:

1. **API abuse** — someone hammering the price/TikTok Worker to burn eBay quota  
2. **Account takeover** — someone taking GitHub / Cloudflare / eBay / Amazon / email

---

## API abuse (Worker)

### Protections (deployed)

| Control | What it does |
|---------|----------------|
| **Refresh auth (fail-closed)** | `POST /v1/refresh` and `/v1/tiktok/refresh` require header `X-Refresh-Token` matching Worker secret `REFRESH_TOKEN`. If the secret is missing, refresh is **locked** (503). |
| **No query-string tokens** | `?token=` is rejected (tokens must not appear in URLs / logs). |
| **No public force-refresh** | Empty snapshot does **not** auto-run a full eBay crawl. `GET /v1/tiktok?refresh=1` requires the same refresh auth. |
| **Per-IP rate limits** | KV-backed limits on snapshot, prices, price, tiktok, and a global cap. Abusive clients get **429**. |
| **CORS allowlist** | Browser calls only allowed from `aipickvault.com`, `www`, and GitHub Pages by default. Override with Worker env/secret `ALLOWED_ORIGINS` (comma-separated). |
| **Batch ceiling** | `POST /v1/prices` still rejects absurd body sizes. |

### One-time setup (required)

Generate a long random token and store it in **two** places: Cloudflare + GitHub.

```powershell
cd C:\Users\bamte\aipickvault\ebay-worker

# 1) Create a strong token (save it temporarily)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 2) Put it on the Worker (paste when prompted)
node .\node_modules\wrangler\bin\wrangler.js secret put REFRESH_TOKEN

# 3) GitHub repo → Settings → Secrets and variables → Actions
#    New repository secret name: REFRESH_TOKEN
#    Value: same token as step 2
```

Optional: allow extra browser origins

```powershell
node .\node_modules\wrangler\bin\wrangler.js secret put ALLOWED_ORIGINS
# example: https://aipickvault.com,https://www.aipickvault.com,https://bamtec70.github.io
```

### Manual refresh (after token is set)

```powershell
# Full catalog (Worker orchestrates small chunks so each stays under subrequest limits)
curl.exe -X POST "https://ebay-api.aipickvault.com/v1/refresh" `
  -H "X-Refresh-Token: YOUR_TOKEN_HERE"

# Optional: one slice only (merge into KV). Used internally by full refresh.
curl.exe -X POST "https://ebay-api.aipickvault.com/v1/refresh" `
  -H "X-Refresh-Token: YOUR_TOKEN_HERE" `
  -H "Content-Type: application/json" `
  -H "X-Refresh-Chunk: 1" `
  -d "{\"partial\":true,\"offset\":0,\"limit\":6,\"reset\":true}"
```

Daily GitHub Actions (`daily-price-refresh.yml` and `sync-tiktok.yml`) send this header when the `REFRESH_TOKEN` repo secret exists. The price workflow also fails if the snapshot still has subrequest errors or a very low eBay match rate.

### What the public site still can do (by design)

- Read daily **snapshot** (cached prices)  
- Request small **live eBay price batches** for the catalog  
- Read **cached TikTok** list  

Those stay public so the site works without logging anyone in. Rate limits stop bulk scraping.

---

## Account takeover (you + platform settings)

Code cannot turn on 2FA for you. Do this checklist once:

### Must-do (today)

| Account | Action |
|---------|--------|
| **GitHub** (`bamtec70`) | Password manager + **2FA** + review SSH keys / PATs / collaborators |
| **Cloudflare** | Password manager + **2FA** + review members / API tokens |
| **Domain / DNS** | Registrar lock if available; strong email on the account |
| **Email** for `contact@aipickvault.com` | Unique password + 2FA (Google/Microsoft/etc.) |
| **eBay Developer** | 2FA on eBay; never commit Client Secret |
| **Amazon Associates / PA-API** | 2FA on Amazon; never commit Access/Secret keys |
| **Facebook / TikTok / YouTube** | 2FA; recovery codes offline |

### Git hygiene

- Never commit: `.env`, `*.pem`, wrangler state with secrets, API dump HTML  
- Worker secrets **only** via `wrangler secret put`  
- Affiliate **tags** in `index.html` are public by design (not API keys)

### If you suspect compromise

1. Rotate **REFRESH_TOKEN**, eBay Client Secret, Amazon keys  
2. Sign out all sessions on GitHub + Cloudflare  
3. Review recent git commits and Cloudflare Worker versions  
4. Change email password first if recovery mail is at risk  

---

## What we deliberately do *not* add

- User logins on aipickvault.com (would increase takeover surface)  
- Storing customer card data  
- Unofficial TikTok/Facebook scrapers on the page  
- Putting API secrets in front-end JavaScript  

---

## Quick self-test

```powershell
# Should be 401 or 503 without the header (not 200 with a full refresh)
curl.exe -i -X POST "https://ebay-api.aipickvault.com/v1/refresh"

# Should still work for the public site
curl.exe -i "https://ebay-api.aipickvault.com/health"
curl.exe -i "https://ebay-api.aipickvault.com/v1/snapshot"
```

Re-check this file after any new form, login, or payment feature.
