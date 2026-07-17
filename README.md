# AI Pick Vault

**Smart deals. AI curated. Real value.**

Grok-powered product picks for gig workers, DIYers, van lifers, and independent hustlers.

## Live site

**https://aipickvault.com**  
Fallback: https://bamtec70.github.io/aipickvault/

- TikTok: [@aipickvault](https://www.tiktok.com/@aipickvault)

## From the Vault (TikTok)

The homepage **From the Vault** section loads the latest `@aipickvault` posts automatically:

| Layer | What it does |
|-------|----------------|
| **Live API** | `GET https://ebay-api.aipickvault.com/v1/tiktok` (cached ~3h on the Worker) |
| **Repo snapshot** | `tiktok/videos.json` + covers under `tiktok/covers/vault-*.jpg` |
| **Auto sync** | GitHub Action `.github/workflows/sync-tiktok.yml` every 6 hours |

After you post a new TikTok:

```powershell
cd C:\Users\bamte\aipickvault
python tiktok/sync_videos.py
# then commit + push tiktok/videos.json and any new vault-*.jpg covers
```

Or run the **Sync TikTok vault** workflow manually on GitHub (Actions → workflow_dispatch).

## Local

```powershell
cd C:\Users\bamte\aipickvault
start index.html
```

## Amazon Associates tag

Edit **one line** near the top of the script in `index.html`:

```js
const AMAZON_TAG = "yourtag-20";
```

All Shop on Amazon buttons pick it up automatically.

## Live / daily prices (Amazon + eBay)

The site uses the Cloudflare Worker at **https://ebay-api.aipickvault.com**:

| Source | Behavior |
|--------|----------|
| **eBay** | Live on each page load + full catalog refresh **daily** (cron) |
| **Amazon** | Daily refresh when Product Advertising API secrets are set (see `ebay-worker/README.md`) |
| **Fallback** | Catalog `compare.*` snapshots in `index.html` if APIs are down |

```js
const EBAY_PRICE_API = "https://ebay-api.aipickvault.com";
```

Leave it as `""` for snapshots only. Shop eBay links always open filtered search (New + free US ship) regardless.

## Affiliate disclosure

As an Amazon Associate and eBay Partner Network member we earn from qualifying purchases. Disclosures are shown on the site.

## Stack

- Static HTML + Tailwind CDN + Font Awesome → GitHub Pages (`main` root)
- Optional: Cloudflare Worker (`ebay-worker/`) → eBay Browse API for live price compares
