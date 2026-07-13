# AI Pick Vault

**Smart deals. AI curated. Real value.**

Grok-powered product picks for gig workers, DIYers, van lifers, and independent hustlers.

## Live site

**https://aipickvault.com**  
Fallback: https://bamtec70.github.io/aipickvault/

- TikTok: [@aipickvault](https://www.tiktok.com/@aipickvault)

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

## Live eBay prices (New + free US shipping)

Catalog `compare.ebay` values are snapshots. For **live** lowest New + free-shipping US Buy It Now prices:

1. Deploy the Cloudflare Worker in [`ebay-worker/`](ebay-worker/) (see its README).
2. Paste the worker URL into `index.html`:

```js
const EBAY_PRICE_API = "https://ebay-api.aipickvault.com";
```

Leave it as `""` to keep snapshot prices only. Shop eBay links always open filtered search (New + free US ship) regardless.

## Affiliate disclosure

As an Amazon Associate and eBay Partner Network member we earn from qualifying purchases. Disclosures are shown on the site.

## Stack

- Static HTML + Tailwind CDN + Font Awesome → GitHub Pages (`main` root)
- Optional: Cloudflare Worker (`ebay-worker/`) → eBay Browse API for live price compares
