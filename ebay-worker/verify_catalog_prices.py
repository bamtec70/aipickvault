#!/usr/bin/env python3
"""
Fail-safe after add/remove products: site, catalog, Amazon, and eBay must line up.

Gates:
  1) Every ASIN in index.html is in ebay-worker catalog (and vice versa)
  2) Live worker health.catalogSize == catalog length
  3) Snapshot has a row for every catalog ASIN
  4) Live Amazon price within threshold of site price/compare.amazon
     (skipped or soft if Amazon blocks the runner)

Usage:
  python ebay-worker/verify_catalog_prices.py
  python ebay-worker/verify_catalog_prices.py --skip-amazon
  python ebay-worker/verify_catalog_prices.py --fail-on-amazon --report _audit/verify.json

Exit codes:
  0 = all hard gates passed
  1 = verification failures (prices/catalog out of sync)
  2 = infrastructure / input error
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
CATALOG = ROOT / "src" / "catalog.json"
DEFAULT_BASE = "https://ebay-api.aipickvault.com"

# Match amazon_snapshot_watch material thresholds
MIN_ABS_DELTA = 2.0
MIN_PCT_DELTA = 0.05
# Amazon fetch must succeed for this share of catalog or we soft-skip Amazon gate
MIN_AMAZON_FETCH_RATE = 0.35
# Snapshot should not be older than this for eBay coverage gate to be strict
SNAPSHOT_MAX_AGE_HOURS = 48.0

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _http_json(url: str, timeout: int = 45) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "aipickvault-verify-catalog/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def extract_site_products(html: str) -> list[dict[str, Any]]:
    """Parse product cards from index.html (same shape as amazon_snapshot_watch)."""
    pattern = re.compile(
        r'asin:\s*"([^"]+)"\s*,\s*name:\s*"((?:\\.|[^"\\])*)"[\s\S]*?'
        r"price:\s*([0-9.]+)\s*,\s*list:\s*([^,\n]+),[\s\S]*?"
        r"compare:\s*\{\s*amazon:\s*([0-9.]+|null)\s*,\s*walmart:\s*([0-9.]+|null)"
        r"\s*,\s*ebay:\s*([0-9.]+|null)\s*\}",
        re.M,
    )
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for m in pattern.finditer(html):
        asin = m.group(1)
        if asin in seen:
            continue
        seen.add(asin)
        items.append(
            {
                "asin": asin,
                "name": m.group(2).replace('\\"', '"'),
                "price": float(m.group(3)),
                "list": None if m.group(4).strip() == "null" else float(m.group(4)),
                "amazon": None if m.group(5) == "null" else float(m.group(5)),
                "ebay": None if m.group(7) == "null" else float(m.group(7)),
            }
        )
    return items


def load_catalog(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"catalog must be a JSON list: {path}")
    return [row for row in data if isinstance(row, dict) and row.get("id")]


def is_material(old: float, new: float) -> bool:
    delta = abs(new - old)
    if delta >= MIN_ABS_DELTA:
        return True
    if old > 0 and delta / old >= MIN_PCT_DELTA:
        return True
    return False


def fetch_amazon_price(asin: str) -> dict[str, Any]:
    """Lightweight Amazon product price (reuse snapshot-watch logic via import)."""
    try:
        from amazon_snapshot_watch import fetch_live_price  # type: ignore
    except ImportError:
        sys.path.insert(0, str(ROOT))
        from amazon_snapshot_watch import fetch_live_price  # type: ignore
    return fetch_live_price(asin)


def parse_snapshot_age_hours(updated_at: str | None) -> float | None:
    if not updated_at:
        return None
    try:
        text = updated_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
    except ValueError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify catalog + Amazon/eBay prices after product add/remove"
    )
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument(
        "--skip-amazon",
        action="store_true",
        help="Skip live Amazon fetch (catalog + eBay snapshot only)",
    )
    parser.add_argument(
        "--fail-on-amazon",
        action="store_true",
        help="Fail when Amazon material drift found (default: fail)",
    )
    parser.add_argument(
        "--no-fail-on-amazon",
        action="store_true",
        help="Report Amazon drift but do not fail the job",
    )
    parser.add_argument(
        "--amazon-sleep",
        type=float,
        default=0.9,
        help="Delay between Amazon product fetches",
    )
    parser.add_argument(
        "--soft-amazon-fetch",
        action="store_true",
        default=True,
        help="If Amazon fetch rate is low, skip Amazon fail gate (default on)",
    )
    parser.add_argument(
        "--no-soft-amazon-fetch",
        action="store_true",
        help="Fail if Amazon fetch rate is below floor",
    )
    args = parser.parse_args(argv)

    fail_on_amazon = not args.no_fail_on_amazon
    soft_amazon = not args.no_soft_amazon_fetch

    errors: list[str] = []
    warnings: list[str] = []
    report: dict[str, Any] = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "gates": {},
        "errors": [],
        "warnings": [],
    }

    # --- Load site + catalog ---
    if not args.index.is_file():
        print(f"ERROR: index not found: {args.index}", file=sys.stderr)
        return 2
    if not args.catalog.is_file():
        print(f"ERROR: catalog not found: {args.catalog}", file=sys.stderr)
        return 2

    try:
        site = extract_site_products(args.index.read_text(encoding="utf-8"))
        catalog = load_catalog(args.catalog)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    site_ids = {p["asin"] for p in site}
    cat_ids = {str(r["id"]).strip() for r in catalog}
    missing_from_catalog = sorted(site_ids - cat_ids)
    extra_in_catalog = sorted(cat_ids - site_ids)

    print("=" * 64)
    print("AI Pick Vault — catalog / price fail-safe")
    print("=" * 64)
    print(f"Site products : {len(site)}")
    print(f"Catalog rows  : {len(catalog)}")
    print(f"Base URL      : {args.base_url.rstrip('/')}")
    print()

    # Gate 1: site ↔ catalog
    gate1_ok = not missing_from_catalog and not extra_in_catalog and len(site) > 0
    report["gates"]["site_catalog_sync"] = {
        "ok": gate1_ok,
        "siteCount": len(site),
        "catalogCount": len(catalog),
        "missingFromCatalog": missing_from_catalog,
        "extraInCatalog": extra_in_catalog,
    }
    if not site:
        errors.append("No products parsed from index.html")
    if missing_from_catalog:
        errors.append(
            "In index.html but NOT in catalog (run extract_catalog.py): "
            + ", ".join(missing_from_catalog)
        )
    if extra_in_catalog:
        errors.append(
            "In catalog but NOT in index.html: " + ", ".join(extra_in_catalog)
        )
    print(
        f"[1] Site ↔ catalog sync: "
        f"{'PASS' if gate1_ok else 'FAIL'} "
        f"(missing={len(missing_from_catalog)} extra={len(extra_in_catalog)})"
    )

    # Gate 2+3: worker health + snapshot coverage
    base = args.base_url.rstrip("/")
    health: dict[str, Any] = {}
    snap: dict[str, Any] = {}
    try:
        health = _http_json(f"{base}/health")
        snap = _http_json(f"{base}/v1/snapshot")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        errors.append(f"Worker API unreachable: {exc}")
        print(f"[2] Worker health/snapshot: FAIL ({exc})")
        report["gates"]["worker"] = {"ok": False, "error": str(exc)}
    else:
        catalog_size = int(health.get("catalogSize") or 0)
        snap_count = int(snap.get("count") or len(snap.get("prices") or {}))
        prices = snap.get("prices") or {}
        if not isinstance(prices, dict):
            prices = {}

        size_ok = catalog_size == len(catalog) and catalog_size == len(site)
        if catalog_size != len(catalog):
            errors.append(
                f"Worker catalogSize={catalog_size} != local catalog {len(catalog)} "
                "(deploy worker after extract_catalog.py)"
            )
        if catalog_size != len(site):
            warnings.append(
                f"Worker catalogSize={catalog_size} != site products {len(site)}"
            )

        missing_snap = sorted(cat_ids - set(prices.keys()))
        # Also flag site ASINs missing from snapshot
        missing_snap_site = sorted(site_ids - set(prices.keys()))
        missing_snap = sorted(set(missing_snap) | set(missing_snap_site))

        age_h = parse_snapshot_age_hours(
            str(snap.get("updatedAt") or health.get("lastSnapshotAt") or "")
        )
        stale = age_h is not None and age_h > SNAPSHOT_MAX_AGE_HOURS
        if stale:
            warnings.append(
                f"Snapshot age {age_h:.1f}h > {SNAPSHOT_MAX_AGE_HOURS}h "
                "(run Daily price refresh)"
            )

        ebay_ok_n = sum(
            1
            for pid, row in prices.items()
            if pid in cat_ids and isinstance(row, dict) and row.get("ebayOk") is True
        )
        ebay_fail_n = sum(
            1
            for pid, row in prices.items()
            if pid in cat_ids and isinstance(row, dict) and row.get("ebayOk") is False
        )
        no_row = len(missing_snap)

        # Hard fail: missing snapshot rows for catalog products
        coverage_ok = no_row == 0 and size_ok
        if no_row:
            errors.append(
                f"Snapshot missing {no_row} catalog ASIN(s): "
                + ", ".join(missing_snap[:15])
                + ("..." if no_row > 15 else "")
                + " — deploy catalog + run Daily price refresh"
            )

        # Soft: many ebayOk false is a warning (match quality), not always block
        if cat_ids and ebay_ok_n / max(len(cat_ids), 1) < 0.35:
            warnings.append(
                f"ebayOk rate low: {ebay_ok_n}/{len(cat_ids)} "
                "(check pins/queries; daily refresh may still be green if ≥35%)"
            )

        report["gates"]["worker"] = {
            "ok": coverage_ok,
            "catalogSize": catalog_size,
            "snapshotCount": snap_count,
            "snapshotAgeHours": age_h,
            "missingFromSnapshot": missing_snap,
            "ebayOkCount": ebay_ok_n,
            "ebayFailCount": ebay_fail_n,
            "updatedAt": snap.get("updatedAt") or health.get("lastSnapshotAt"),
        }
        print(
            f"[2] Worker catalogSize={catalog_size} snapshot={snap_count} "
            f"age={age_h if age_h is not None else '?' }h: "
            f"{'PASS' if size_ok and no_row == 0 else 'FAIL'}"
        )
        print(
            f"[3] eBay snapshot coverage: missing_rows={no_row} "
            f"ebayOk={ebay_ok_n} ebayFail={ebay_fail_n} "
            f"{'PASS' if no_row == 0 else 'FAIL'}"
        )

    # Gate 4: live Amazon vs site
    amazon_rows: list[dict[str, Any]] = []
    amazon_material: list[dict[str, Any]] = []
    amazon_gate_ok = True
    amazon_skipped = False

    if args.skip_amazon:
        amazon_skipped = True
        print("[4] Amazon live check: SKIPPED (--skip-amazon)")
        report["gates"]["amazon"] = {"ok": True, "skipped": True}
    else:
        print("[4] Amazon live check: fetching…")
        ok_n = 0
        for i, prod in enumerate(site, 1):
            asin = prod["asin"]
            site_amz = (
                prod["amazon"] if prod["amazon"] is not None else prod["price"]
            )
            row: dict[str, Any] = {
                "asin": asin,
                "name": prod["name"],
                "site": site_amz,
                "live": None,
                "ok": False,
                "material": False,
                "error": None,
            }
            try:
                live = fetch_amazon_price(asin)
                if live.get("price") is not None:
                    row["live"] = float(live["price"])
                    row["ok"] = True
                    row["source"] = live.get("source")
                    ok_n += 1
                    if is_material(float(site_amz), float(live["price"])):
                        row["material"] = True
                        row["delta"] = round(float(live["price"]) - float(site_amz), 2)
                        amazon_material.append(row)
                else:
                    row["error"] = live.get("error") or "no_price"
            except Exception as exc:  # noqa: BLE001 — collect per-ASIN
                row["error"] = str(exc)[:120]
            amazon_rows.append(row)
            flag = (
                "MATERIAL"
                if row["material"]
                else ("ok" if row["ok"] else f"FAIL {row.get('error')}")
            )
            print(
                f"  [{i:02d}/{len(site)}] {asin} site=${site_amz} "
                f"live=${row.get('live')} {flag}",
                flush=True,
            )
            time.sleep(max(0.35, args.amazon_sleep))

        fetch_rate = ok_n / len(site) if site else 0.0
        if fetch_rate < MIN_AMAZON_FETCH_RATE:
            msg = (
                f"Amazon fetch rate {fetch_rate:.0%} < {MIN_AMAZON_FETCH_RATE:.0%} "
                "(bot block / rate limit)"
            )
            if soft_amazon:
                warnings.append(msg + " — Amazon fail gate soft-skipped")
                amazon_gate_ok = True
                amazon_skipped = True
                print(f"[4] Amazon: SOFT-SKIP ({msg})")
            else:
                errors.append(msg)
                amazon_gate_ok = False
                print(f"[4] Amazon: FAIL ({msg})")
        elif amazon_material:
            amazon_gate_ok = not fail_on_amazon
            lines = [
                f"{m['asin']}: ${m['site']} → ${m['live']} ({m.get('delta'):+})"
                for m in amazon_material
            ]
            msg = f"Amazon material drift on {len(amazon_material)} product(s): " + "; ".join(
                lines[:8]
            )
            if fail_on_amazon:
                errors.append(msg + " — run amazon snapshot apply or update index.html")
                print(f"[4] Amazon: FAIL ({len(amazon_material)} material)")
            else:
                warnings.append(msg)
                print(f"[4] Amazon: WARN ({len(amazon_material)} material, not failing)")
        else:
            print(f"[4] Amazon: PASS (fetch {ok_n}/{len(site)}, no material drift)")

        report["gates"]["amazon"] = {
            "ok": amazon_gate_ok,
            "skipped": amazon_skipped,
            "fetchOk": ok_n,
            "fetchRate": round(ok_n / len(site), 3) if site else 0,
            "materialCount": len(amazon_material),
            "material": [
                {
                    "asin": m["asin"],
                    "name": m["name"],
                    "site": m["site"],
                    "live": m["live"],
                    "delta": m.get("delta"),
                }
                for m in amazon_material
            ],
            "rows": amazon_rows,
        }

    report["errors"] = errors
    report["warnings"] = warnings
    report["ok"] = len(errors) == 0

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Report → {args.report}")

    print()
    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"  ⚠ {w}")
    if errors:
        print("Failures:")
        for e in errors:
            print(f"  ✗ {e}")
        print()
        print("RESULT: FAIL — fix catalog/prices before treating add/remove as done")
        return 1

    print("RESULT: PASS — site, catalog, and price gates OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
