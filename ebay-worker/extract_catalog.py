"""
Sync product list from site index.html → worker catalog JSON.

Preserves per-ASIN match pins (ebayPreferItemId, requireTokens) from the
existing src/catalog.json so re-extract does not wipe hand-tuned matches.

Writes both:
  ebay-worker/catalog.json
  ebay-worker/src/catalog.json  (what wrangler deploys)

After running:
  node node_modules/wrangler/bin/wrangler.js deploy
  curl -X POST https://ebay-api.aipickvault.com/v1/refresh

Live site pricing auto-chunks /v1/prices — catalog size growth alone must
not cause "eBay API offline" (see index.html refreshLiveEbayPrices).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT.parent / "index.html"
OUT_ROOT = ROOT / "catalog.json"
OUT_SRC = ROOT / "src" / "catalog.json"

# Abuse ceiling on worker POST /v1/prices — site chunks (~15) well below this.
ABSOLUTE_MAX_BATCH = 250
PREFERRED_LIVE_CHUNK = 15


def load_pins(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    pins: dict[str, dict] = {}
    if not isinstance(data, list):
        return pins
    for row in data:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id") or "").strip()
        if not rid:
            continue
        keep = {}
        if row.get("ebayPreferItemId"):
            keep["ebayPreferItemId"] = str(row["ebayPreferItemId"]).strip()
        if row.get("requireTokens"):
            toks = row["requireTokens"]
            if isinstance(toks, list):
                keep["requireTokens"] = [str(t).strip() for t in toks if str(t).strip()]
        if row.get("ebayAllowPaidShip") or row.get("allowPaidShip"):
            keep["ebayAllowPaidShip"] = True
        # Keep pin as source of truth; do not flag search undercuts for this ASIN
        if row.get("ebaySkipPinUndercut") or row.get("skipPinUndercut"):
            keep["ebaySkipPinUndercut"] = True
        # Blocklist bad/OOS/one-off eBay listings (never pin or search-match these)
        excl = row.get("ebayExcludeItemIds") or row.get("ebayBlockItemIds")
        if excl:
            if isinstance(excl, list):
                keep["ebayExcludeItemIds"] = [
                    str(x).strip() for x in excl if str(x).strip()
                ]
            elif str(excl).strip():
                keep["ebayExcludeItemIds"] = [
                    p.strip() for p in str(excl).split(",") if p.strip()
                ]
        if keep:
            pins[rid] = keep
    return pins


def main() -> int:
    if not SITE.is_file():
        print(f"ERROR: site not found: {SITE}", file=sys.stderr)
        return 1

    html = SITE.read_text(encoding="utf-8")
    # Prefer ebayQ when present on the same product object (better match query).
    # Fall back to name. Order follows product appearance in index.html.
    # Walk every asin: in this site the product list is not always `const products = [...]`.
    items: list[dict] = []
    seen: set[str] = set()
    for asin_m in re.finditer(r'asin:\s*"([^"]+)"', html):
        asin = asin_m.group(1)
        if asin in seen:
            continue
        window = html[asin_m.start() : asin_m.start() + 2500]
        # Stop window at next product asin if closer than 2500 chars
        next_asin = re.search(r'asin:\s*"', window[10:])
        if next_asin:
            window = window[: 10 + next_asin.start()]
        ebay_q = re.search(r'ebayQ:\s*"((?:\\.|[^"\\])*)"', window)
        name_m = re.search(r'name:\s*"((?:\\.|[^"\\])*)"', window)
        raw_q = (ebay_q.group(1) if ebay_q else None) or (
            name_m.group(1) if name_m else asin
        )
        q = raw_q.replace('\\"', '"').replace("\\'", "'")
        # Amazon snapshot baseline for eBay price-band filtering (55%–275%).
        # Prefer compare.amazon, then card price.
        amazon_price = None
        cmp_amz = re.search(
            r"compare:\s*\{\s*amazon:\s*([0-9.]+|null)",
            window,
        )
        if cmp_amz and cmp_amz.group(1) != "null":
            try:
                amazon_price = float(cmp_amz.group(1))
            except ValueError:
                amazon_price = None
        if amazon_price is None:
            price_m = re.search(r"price:\s*([0-9.]+)\s*,", window)
            if price_m:
                try:
                    amazon_price = float(price_m.group(1))
                except ValueError:
                    amazon_price = None
        seen.add(asin)
        row: dict = {"id": asin, "q": q}
        if amazon_price is not None and amazon_price > 0:
            row["amazonPrice"] = round(amazon_price, 2)
        items.append(row)

    pins = load_pins(OUT_SRC) or load_pins(OUT_ROOT)
    for row in items:
        extra = pins.get(row["id"])
        if extra:
            row.update(extra)

    text = json.dumps(items, indent=2) + "\n"
    OUT_ROOT.write_text(text, encoding="utf-8")
    OUT_SRC.parent.mkdir(parents=True, exist_ok=True)
    OUT_SRC.write_text(text, encoding="utf-8")

    n = len(items)
    print(f"Wrote {n} products to {OUT_ROOT}")
    print(f"Wrote {n} products to {OUT_SRC}")
    if pins:
        print(f"Preserved pins/tokens for {len(pins)} ASIN(s)")
    if n > ABSOLUTE_MAX_BATCH:
        print(
            f"WARNING: catalog size {n} exceeds worker absoluteMaxBatch "
            f"({ABSOLUTE_MAX_BATCH}). Live site still chunks, but POST of "
            f"entire catalog in one call would fail. Raise ABSOLUTE_MAX_BATCH "
            f"in ebay-worker/src/index.js if needed.",
            file=sys.stderr,
        )
        return 2
    print(
        "OK: live site auto-chunks /v1/prices — adding products will not "
        "cause batch-limit 'eBay API offline'."
    )
    print("Next: deploy worker + refresh snapshot if you changed products:")
    print("  node node_modules/wrangler/bin/wrangler.js deploy")
    print("  # then chunked refresh — or GitHub Action: Daily price refresh")
    print("REQUIRED fail-safe after add/remove (must exit 0):")
    print("  python verify_catalog_prices.py")
    print("  python verify_catalog_prices.py --skip-amazon   # catalog+eBay only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
