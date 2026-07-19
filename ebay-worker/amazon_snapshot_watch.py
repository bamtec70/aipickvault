#!/usr/bin/env python3
"""
Amazon snapshot watcher (pre-PA-API).

Compares catalog Amazon prices in index.html against public sources:
  1) Amazon product page JSON (priceAmount) — preferred
  2) camelcamelcamel buy-box — fallback

Reports material drift and can apply updates to index.html.

Usage:
  python amazon_snapshot_watch.py
  python amazon_snapshot_watch.py --apply
  python amazon_snapshot_watch.py --fail-on-material --report _amazon_watch_report.json

Exit codes:
  0 = no material drift
  1 = material drift (--fail-on-material)
  2 = infra / fetch success rate too low
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
INDEX = REPO / "index.html"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}

MIN_ABS_DELTA = 2.0
MIN_PCT_DELTA = 0.05
SOFT_ABS_DELTA = 0.50


def extract_products(html: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r'asin:\s*"([^"]+)"\s*,\s*name:\s*"((?:\\.|[^"\\])*)"[\s\S]*?'
        r"price:\s*([0-9.]+)\s*,\s*list:\s*([^,\n]+),[\s\S]*?"
        r"compare:\s*\{\s*amazon:\s*([0-9.]+|null)\s*,\s*walmart:\s*([0-9.]+|null)"
        r"\s*,\s*ebay:\s*([0-9.]+|null)\s*\}",
        re.M,
    )
    items = []
    for m in pattern.finditer(html):
        items.append(
            {
                "asin": m.group(1),
                "name": m.group(2).replace('\\"', '"'),
                "price": float(m.group(3)),
                "list": None if m.group(4).strip() == "null" else float(m.group(4)),
                "amazon": None if m.group(5) == "null" else float(m.group(5)),
                "walmart": None if m.group(6) == "null" else float(m.group(6)),
                "ebay": None if m.group(7) == "null" else float(m.group(7)),
            }
        )
    return items


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=40) as res:
        return res.read().decode("utf-8", errors="replace")


def _money(s: str) -> float | None:
    try:
        return float((s or "").strip().replace(",", ""))
    except ValueError:
        return None


def parse_amazon_product(html: str) -> dict[str, Any]:
    """Extract live-ish price from Amazon product HTML (when not blocked)."""
    low = html[:4000].lower()
    if (
        "opfcaptcha" in low
        or "api-services-support@amazon.com" in html
        or "enter the characters you see" in low
        or "sorry, we just need to make sure you're not a robot" in low
    ):
        return {"price": None, "list": None, "source": None, "error": "amazon_bot_check"}

    price = None
    source = None

    # Most reliable embedded fields when page is real product HTML
    for pat, src in (
        (r'"priceAmount"\s*:\s*([0-9]+\.[0-9]{2})', "priceAmount"),
        (
            r'"price"\s*:\s*\{\s*"displayAmount"\s*:\s*"\$([0-9,]+\.[0-9]{2})"',
            "displayAmount",
        ),
        (
            r'data-a-color="price"[\s\S]{0,200}?class="a-offscreen">\s*\$([0-9,]+\.[0-9]{2})',
            "a_offscreen",
        ),
        (
            r'class="a-price aok-align-center[^"]*"[\s\S]{0,120}?class="a-offscreen">\s*\$([0-9,]+\.[0-9]{2})',
            "a_price",
        ),
        (
            r'id="priceblock_ourprice"[^>]*>\s*\$([0-9,]+\.[0-9]{2})',
            "priceblock_our",
        ),
        (
            r'id="priceblock_dealprice"[^>]*>\s*\$([0-9,]+\.[0-9]{2})',
            "priceblock_deal",
        ),
    ):
        m = re.search(pat, html, re.I)
        if m:
            price = _money(m.group(1))
            if price is not None and price > 0:
                source = "amazon_" + src
                break

    list_price = None
    for pat in (
        r'"listPrice"\s*:\s*\{\s*"amount"\s*:\s*([0-9]+\.[0-9]{2})',
        r'"basisPrice"\s*:\s*\{\s*"moneyValueOrRanges"\s*:\s*\{\s*"value"\s*:\s*\{\s*"amount"\s*:\s*([0-9]+\.[0-9]{2})',
        r'class="a-price a-text-price"[^>]*>[\s\S]{0,80}?class="a-offscreen">\s*\$([0-9,]+\.[0-9]{2})',
        r'data-a-strike="true"[\s\S]{0,80}?\$([0-9,]+\.[0-9]{2})',
    ):
        m = re.search(pat, html, re.I)
        if m:
            list_price = _money(m.group(1))
            if list_price is not None:
                break

    if price is None:
        return {
            "price": None,
            "list": list_price,
            "source": None,
            "error": "amazon_no_price",
        }
    return {"price": price, "list": list_price, "source": source, "error": None}


def parse_camel(html: str) -> dict[str, Any]:
    if "Just a moment" in html or "cf-browser-verification" in html:
        return {"price": None, "list": None, "source": None, "error": "camel_cloudflare"}
    if "Page not found" in html or "We couldn" in html:
        return {"price": None, "list": None, "source": None, "error": "camel_not_found"}

    cells = re.findall(
        r'<span class="[^"]*bgp[^"]*">\s*([^<]+)</span>\s*<br\s*/?>\s*'
        r'<span class="price-type-label">\s*([^<]+)</span>',
        html,
        re.I,
    )
    amazon_price = None
    third_new = None
    for raw_price, label in cells:
        label_l = label.strip().lower()
        raw = raw_price.strip()
        if re.search(r"out\s*of\s*stock", raw, re.I):
            continue
        m = re.search(r"\$?\s*([0-9,]+\.[0-9]{2})", raw)
        if not m:
            continue
        val = _money(m.group(1))
        if val is None:
            continue
        if "amazon price" in label_l:
            amazon_price = val
        elif "3rd party new" in label_l or label_l == "new":
            third_new = val

    price = None
    source = None
    if amazon_price is not None:
        price, source = amazon_price, "camel_amazon"
    elif third_new is not None:
        price, source = third_new, "camel_3p_new"

    if price is None:
        m = re.search(
            r'id="buy-box"[\s\S]{0,1200}?<span class="[^"]*bgp[^"]*">\s*\$([0-9,]+\.[0-9]{2})</span>',
            html,
            re.I,
        )
        if m:
            price = _money(m.group(1))
            source = "camel_buybox"

    if price is None:
        return {"price": None, "list": None, "source": None, "error": "camel_no_price"}
    return {"price": price, "list": None, "source": source, "error": None}


def fetch_live_price(asin: str) -> dict[str, Any]:
    """Try Amazon first, then camel. Returns unified dict."""
    errors: list[str] = []

    # 1) Amazon product page
    try:
        amz_html = fetch(f"https://www.amazon.com/dp/{asin}?th=1&psc=1")
        parsed = parse_amazon_product(amz_html)
        if parsed.get("price") is not None:
            return parsed
        errors.append(parsed.get("error") or "amazon_fail")
    except urllib.error.HTTPError as e:
        errors.append(f"amazon_HTTP_{e.code}")
    except Exception as e:
        errors.append(f"amazon_{str(e)[:60]}")

    time.sleep(0.4)

    # 2) camelcamelcamel
    try:
        camel_html = fetch(f"https://camelcamelcamel.com/product/{asin}")
        parsed = parse_camel(camel_html)
        if parsed.get("price") is not None:
            return parsed
        errors.append(parsed.get("error") or "camel_fail")
    except urllib.error.HTTPError as e:
        errors.append(f"camel_HTTP_{e.code}")
    except Exception as e:
        errors.append(f"camel_{str(e)[:60]}")

    return {
        "price": None,
        "list": None,
        "source": None,
        "error": "+".join(errors)[:160],
    }


def is_material(old: float, new: float) -> bool:
    delta = abs(new - old)
    if delta >= MIN_ABS_DELTA:
        return True
    if old > 0 and delta / old >= MIN_PCT_DELTA:
        return True
    return False


def apply_updates(html: str, moves: list[dict[str, Any]]) -> tuple[str, int]:
    changed = 0
    for m in moves:
        asin = m["asin"]
        new_p = m["live_price"]
        start = html.find(f'asin: "{asin}"')
        if start < 0:
            continue
        next_m = re.search(r'\nasin:\s*"B[0-9A-Z]{9}"', html[start + 10 :])
        end = start + 10 + next_m.start() if next_m else min(len(html), start + 2500)
        chunk = html[start:end]
        chunk2 = re.sub(r"price:\s*[0-9.]+", f"price: {new_p}", chunk, count=1)
        chunk2 = re.sub(
            r"(compare:\s*\{\s*amazon:\s*)(?:[0-9.]+|null)",
            rf"\g<1>{new_p}",
            chunk2,
            count=1,
        )
        if chunk2 != chunk:
            html = html[:start] + chunk2 + html[end:]
            changed += 1
    return html, changed


def write_checklist(path: Path, items: list[dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    """Human-friendly checklist with deep links (always useful if auto-fetch is blocked)."""
    by_asin = {r["asin"]: r for r in rows}
    lines = [
        "# Amazon snapshot checklist (pre-PA-API)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Open each Amazon link. If the **item** price (not tax total) differs by ≥ $2 or ≥ 5% from Site, update `index.html` (`price` + `compare.amazon`).",
        "",
        "| ASIN | Site $ | Live $ | Δ | Name | Links |",
        "|------|--------|--------|---|------|-------|",
    ]
    for it in items:
        asin = it["asin"]
        r = by_asin.get(asin, {})
        site = r.get("site_amazon", it.get("amazon") or it.get("price"))
        live = r.get("live_price")
        delta = r.get("delta")
        live_s = f"${live:.2f}" if isinstance(live, (int, float)) else (r.get("error") or "—")
        delta_s = f"{delta:+.2f}" if isinstance(delta, (int, float)) else "—"
        name = (it.get("name") or "")[:40].replace("|", "/")
        amz = f"https://www.amazon.com/dp/{asin}"
        camel = f"https://camelcamelcamel.com/product/{asin}"
        lines.append(
            f"| `{asin}` | ${site} | {live_s} | {delta_s} | {name} | [Amazon]({amz}) · [Camel]({camel}) |"
        )
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Watch Amazon snapshots (pre-PA-API)")
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--report", type=Path, default=ROOT / "_amazon_watch_report.json")
    parser.add_argument(
        "--checklist",
        type=Path,
        default=ROOT / "_amazon_watch_checklist.md",
    )
    parser.add_argument("--sleep", type=float, default=1.15)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--fail-on-material", action="store_true")
    parser.add_argument(
        "--fail-on-fetch-rate",
        type=float,
        default=0.35,
        help="Exit 2 if live fetch success rate below this",
    )
    parser.add_argument(
        "--soft-fetch-fail",
        action="store_true",
        help="If fetch rate is low, exit 0 after writing checklist (no CI red / no ntfy spam)",
    )
    args = parser.parse_args(argv)

    if not args.index.is_file():
        print(f"ERROR: index not found: {args.index}", file=sys.stderr)
        return 2

    html = args.index.read_text(encoding="utf-8")
    items = extract_products(html)
    if args.limit and args.limit > 0:
        items = items[: args.limit]
    if not items:
        print("ERROR: no products extracted", file=sys.stderr)
        return 2

    rows: list[dict[str, Any]] = []
    for i, it in enumerate(items, 1):
        asin = it["asin"]
        site_amz = it["amazon"] if it["amazon"] is not None else it["price"]
        row: dict[str, Any] = {
            "asin": asin,
            "name": it["name"],
            "site_price": it["price"],
            "site_amazon": site_amz,
            "site_list": it["list"],
            "live_price": None,
            "live_list": None,
            "source": None,
            "ok": False,
            "error": None,
            "delta": None,
            "material": False,
            "soft": False,
        }
        live = fetch_live_price(asin)
        if live.get("price") is not None:
            row["live_price"] = live["price"]
            row["live_list"] = live.get("list")
            row["source"] = live.get("source")
            row["ok"] = True
            old = float(site_amz)
            new = float(live["price"])
            delta = round(new - old, 2)
            row["delta"] = delta
            row["material"] = is_material(old, new)
            row["soft"] = (not row["material"]) and abs(delta) >= SOFT_ABS_DELTA
        else:
            row["error"] = live.get("error") or "no_price"

        rows.append(row)
        if row["ok"]:
            flag = "MATERIAL" if row["material"] else ("soft" if row["soft"] else "ok")
            print(
                f"[{i:02d}/{len(items)}] {asin} site=${row['site_amazon']} "
                f"live=${row['live_price']} ({row['source']}) {flag}",
                flush=True,
            )
        else:
            print(f"[{i:02d}/{len(items)}] {asin} FAIL {row['error']}", flush=True)
        time.sleep(max(0.35, args.sleep))

    ok_n = sum(1 for r in rows if r["ok"])
    material = [r for r in rows if r.get("material")]
    soft = [r for r in rows if r.get("soft")]
    fetch_rate = ok_n / len(rows) if rows else 0.0

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "index": str(args.index),
        "count": len(rows),
        "okCount": ok_n,
        "fetchRate": round(fetch_rate, 3),
        "materialCount": len(material),
        "softCount": len(soft),
        "thresholds": {
            "minAbsDelta": MIN_ABS_DELTA,
            "minPctDelta": MIN_PCT_DELTA,
            "softAbsDelta": SOFT_ABS_DELTA,
        },
        "material": [
            {
                "asin": r["asin"],
                "name": r["name"],
                "site": r["site_amazon"],
                "live": r["live_price"],
                "camel": r["live_price"],  # alias for notify script compatibility
                "delta": r["delta"],
                "source": r["source"],
            }
            for r in material
        ],
        "soft": [
            {
                "asin": r["asin"],
                "name": r["name"],
                "site": r["site_amazon"],
                "live": r["live_price"],
                "delta": r["delta"],
            }
            for r in soft
        ],
        "errors": [
            {"asin": r["asin"], "name": r["name"], "error": r["error"]}
            for r in rows
            if not r["ok"]
        ],
        "rows": rows,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_checklist(args.checklist, items, rows)

    print()
    print(
        f"fetch {ok_n}/{len(rows)} ({fetch_rate:.0%})  "
        f"material={len(material)} soft={len(soft)}"
    )
    print(f"report → {args.report}")
    print(f"checklist → {args.checklist}")
    for r in material:
        print(
            f"  MATERIAL {r['asin']}: ${r['site_amazon']} → ${r['live_price']} "
            f"({r['delta']:+})  {r['name'][:48]}"
        )

    if args.apply and material:
        moves = [
            {"asin": r["asin"], "live_price": r["live_price"]}
            for r in material
            if r.get("live_price") is not None
        ]
        new_html, applied = apply_updates(html, moves)
        if applied:
            args.index.write_text(new_html, encoding="utf-8")
            print(f"Applied {applied} Amazon snapshot update(s) to {args.index}")
        else:
            print("WARNING: apply made 0 edits", file=sys.stderr)

    if fetch_rate < args.fail_on_fetch_rate:
        msg = (
            f"Live fetch rate {fetch_rate:.0%} below {args.fail_on_fetch_rate:.0%} "
            f"(bot blocking). Checklist still written."
        )
        if args.soft_fetch_fail:
            print("SOFT: " + msg)
            print("RESULT: OK (soft-fetch-fail; no material check)")
            return 0
        print("ERROR: " + msg, file=sys.stderr)
        return 2

    if args.fail_on_material and material:
        print("RESULT: MATERIAL Amazon drift detected")
        return 1

    print("RESULT: OK" if not material else "RESULT: material found (not failing)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
