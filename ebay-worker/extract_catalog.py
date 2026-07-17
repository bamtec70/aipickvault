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
    product_blocks = re.findall(
        r"\{\s*asin:\s*\"([^\"]+)\"[\s\S]*?\n\s*\},?",
        html,
    )
    # Fallback simple scan if block regex misses
    if not product_blocks:
        pairs = re.findall(
            r'asin:\s*"([^"]+)"\s*,\s*name:\s*"((?:\\.|[^"\\])*)"',
            html,
        )
        items = []
        for asin, name in pairs:
            name = name.replace('\\"', '"').replace("\\'", "'")
            items.append({"id": asin, "q": name})
    else:
        items = []
        seen: set[str] = set()
        for block in product_blocks:
            # block is just asin from first group if we used wrong pattern — re-parse full products
            pass
        # Re-do with full product objects from products array region
        m = re.search(r"const\s+products\s*=\s*\[", html)
        if not m:
            pairs = re.findall(
                r'asin:\s*"([^"]+)"\s*,\s*name:\s*"((?:\\.|[^"\\])*)"',
                html,
            )
            for asin, name in pairs:
                name = name.replace('\\"', '"').replace("\\'", "'")
                if asin in seen:
                    continue
                seen.add(asin)
                items.append({"id": asin, "q": name})
        else:
            # Walk each asin in order; for each, grab nearest ebayQ or name
            for asin_m in re.finditer(r'asin:\s*"([^"]+)"', html[m.start() :]):
                asin = asin_m.group(1)
                if asin in seen:
                    continue
                # window after this asin for fields belonging to this product
                start = m.start() + asin_m.start()
                window = html[start : start + 2500]
                ebay_q = re.search(r'ebayQ:\s*"((?:\\.|[^"\\])*)"', window)
                name_m = re.search(r'name:\s*"((?:\\.|[^"\\])*)"', window)
                raw_q = (ebay_q.group(1) if ebay_q else None) or (
                    name_m.group(1) if name_m else asin
                )
                q = raw_q.replace('\\"', '"').replace("\\'", "'")
                seen.add(asin)
                items.append({"id": asin, "q": q})

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
    print("  curl.exe -sS -X POST https://ebay-api.aipickvault.com/v1/refresh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
