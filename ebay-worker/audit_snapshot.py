#!/usr/bin/env python3
"""
Post-scan accuracy audit for AI Pick Vault.

Layer 2 redundancy: after the daily eBay snapshot is written, re-check
identity and pin health so wrong-product prices cannot sit unnoticed.

Usage:
  python audit_snapshot.py
  python audit_snapshot.py --snapshot /tmp/snap.json --catalog src/catalog.json
  python audit_snapshot.py --base-url https://ebay-api.aipickvault.com --fail-on warning

Exit codes:
  0 = pass (no errors; warnings allowed unless --fail-on warning)
  1 = audit failures (P0/P1 errors)
  2 = infrastructure / input error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_BASE = "https://ebay-api.aipickvault.com"
HIGH_TICKET_USD = 200.0
SNAPSHOT_MAX_AGE_HOURS = 36.0
# Pin snapshot price may lag live item by a little; larger = pin broken or wrong row
PIN_PRICE_DELTA_USD = 15.0
PIN_PRICE_DELTA_PCT = 0.08

ACCESSORY_ONLY_RE = re.compile(
    r"\b(storage\s*bag|carrying\s*case|case\s*for|bag\s*for|cover\s*for|"
    r"power\s*cord\s*for|cable\s*for|solar\s*panel\s*for)\b",
    re.I,
)
POWER_STATION_UNIT_RE = re.compile(
    r"\b(power\s*station|portable\s*power|solar\s*generator)\b", re.I
)
WH_CAPACITY_RE = re.compile(r"\b(\d{3,5}\s*wh|\d{3,5}wh|lifepo4?)\b", re.I)


def _http_json(url: str, timeout: int = 45, retries: int = 3) -> dict[str, Any]:
    """GET JSON with light retry on 429 (Worker rate limits)."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "aipickvault-audit/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code == 429 and attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(1.0 * (attempt + 1))
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("http_json failed without exception")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def title_has_model_token(title: str, model: str) -> bool:
    """Mirror Worker boundary rules: 2000 not inside 2000W; 1070 may match 1070Wh."""
    t = (title or "").lower()
    m = re.escape((model or "").lower().strip())
    if not m:
        return True
    pat = (
        r"(?:^|[^a-z0-9])"
        + m
        + r"(?:\s*v\s*\d+|v\d+)?(?:\s*(?:wh|mah))?(?:[^a-z0-9]|$)"
    )
    return bool(re.search(pat, t, re.I))


def required_model_tokens(q: str) -> list[str]:
    return re.findall(r"\b[a-z]*\d{4,}[a-z0-9]*\b", (q or "").lower())


def normalize_item_id(raw: str | None) -> str:
    """Canonical compare key for eBay REST / legacy / variation ids."""
    if not raw:
        return ""
    s = str(raw).strip()
    # v1|parent|var or v1|legacy|0
    m = re.fullmatch(r"v1\|(\d+)\|(\d+)", s, re.I)
    if m:
        parent, var = m.group(1), m.group(2)
        if var == "0":
            return parent
        return f"{parent}|{var}"
    # parent|var (catalog pin form for variations)
    if re.fullmatch(r"\d+\|\d+", s):
        parent, var = s.split("|", 1)
        if var == "0":
            return parent
        return f"{parent}|{var}"
    if re.fullmatch(r"\d+", s):
        return s
    # Fallback: last long digit group
    m2 = re.findall(r"\d{6,}", s)
    return m2[-1] if m2 else s


def pin_ids_from_catalog(pin_field: str | None) -> list[str]:
    """
    Return pin lookup strings for /v1/item.

    Catalog uses:
      - plain legacy id: 377192086395
      - variation id:    133809507780|433256177972  (parent|variation — ONE listing)
    Do not split variation pins into two independent listings.
    """
    if not pin_field:
        return []
    s = str(pin_field).strip()
    if not s:
        return []
    if re.fullmatch(r"\d+\|\d+", s) or re.fullmatch(r"\d+", s):
        return [s]
    if re.fullmatch(r"v1\|\d+\|\d+", s, re.I):
        return [s]
    # Rare future form: comma-separated alternate pins
    parts = [p.strip() for p in re.split(r"\s*,\s*", s) if p.strip()]
    return parts or [s]


def parse_updated_at(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        text = iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def issue(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    asin: str,
    message: str,
    **extra: Any,
) -> None:
    row = {
        "severity": severity,
        "code": code,
        "asin": asin,
        "message": message,
    }
    row.update(extra)
    findings.append(row)


def audit(
    snap: dict[str, Any],
    catalog: list[dict[str, Any]],
    *,
    base_url: str,
    check_live_pins: bool,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    prices = snap.get("prices") if isinstance(snap.get("prices"), dict) else {}
    cat_by_id = {
        str(e.get("id")): e for e in catalog if isinstance(e, dict) and e.get("id")
    }

    # --- Snapshot freshness / coverage ---
    updated = parse_updated_at(snap.get("updatedAt"))
    now = datetime.now(timezone.utc)
    age_h = None
    if updated:
        age_h = (now - updated).total_seconds() / 3600.0
        if age_h > SNAPSHOT_MAX_AGE_HOURS:
            issue(
                findings,
                "error",
                "snapshot_stale",
                "*",
                f"Snapshot age {age_h:.1f}h exceeds {SNAPSHOT_MAX_AGE_HOURS:.0f}h "
                f"(updatedAt={snap.get('updatedAt')})",
            )
    else:
        issue(
            findings,
            "error",
            "snapshot_missing_updated_at",
            "*",
            "Snapshot missing updatedAt",
        )

    catalog_size = int(snap.get("catalogSize") or len(cat_by_id) or 0)
    ebay_ok = sum(
        1 for p in prices.values() if isinstance(p, dict) and p.get("ebayOk") is True
    )
    if catalog_size and ebay_ok / catalog_size < 0.70:
        issue(
            findings,
            "error",
            "ebay_ok_rate_low",
            "*",
            f"ebayOk rate {ebay_ok}/{catalog_size} below 70% floor",
            ebayOk=ebay_ok,
            catalogSize=catalog_size,
        )
    elif catalog_size and ebay_ok / catalog_size < 0.85:
        issue(
            findings,
            "warning",
            "ebay_ok_rate_soft",
            "*",
            f"ebayOk rate {ebay_ok}/{catalog_size} below 85% soft target",
            ebayOk=ebay_ok,
            catalogSize=catalog_size,
        )

    # --- Per-product checks ---
    for asin, entry in cat_by_id.items():
        row = prices.get(asin) if isinstance(prices.get(asin), dict) else None
        q = str(entry.get("q") or (row or {}).get("q") or asin)
        pin_field = entry.get("ebayPreferItemId") or entry.get("ebayPinItemId")
        pins = pin_ids_from_catalog(pin_field)
        require_tokens = entry.get("requireTokens") or []
        if not isinstance(require_tokens, list):
            require_tokens = []

        if row is None:
            issue(
                findings,
                "error",
                "missing_snapshot_row",
                asin,
                f"Catalog product missing from snapshot: {q}",
            )
            continue

        ebay_ok_flag = row.get("ebayOk") is True
        title = str(row.get("ebayTitle") or "")
        ebay_price = row.get("ebay")
        try:
            ebay_price_f = float(ebay_price) if ebay_price is not None else None
        except (TypeError, ValueError):
            ebay_price_f = None
        source = str(row.get("ebaySource") or "")
        snap_item = normalize_item_id(row.get("ebayItemId"))
        high_ticket = ebay_price_f is not None and ebay_price_f >= HIGH_TICKET_USD

        # Pinned product must win via pin when eBay is OK
        if pins and ebay_ok_flag:
            if source != "pin":
                issue(
                    findings,
                    "error",
                    "pin_not_used",
                    asin,
                    f"Pinned product used search fallback (source={source or 'none'}) "
                    f"instead of pin; title={title[:80]!r}",
                    expectedPins=pins,
                    ebayItemId=row.get("ebayItemId"),
                    ebay=ebay_price_f,
                    q=q,
                )
            else:
                pin_keys = {normalize_item_id(p) for p in pins}
                if snap_item and normalize_item_id(snap_item) not in pin_keys:
                    # Also accept raw forms
                    raw_ok = any(
                        normalize_item_id(row.get("ebayItemId")) == normalize_item_id(p)
                        for p in pins
                    )
                    if not raw_ok:
                        issue(
                            findings,
                            "error",
                            "pin_item_mismatch",
                            asin,
                            f"Snapshot pin item {row.get('ebayItemId')!r} not in catalog pins {pins}",
                            ebayTitle=title[:100],
                            ebay=ebay_price_f,
                            q=q,
                        )

            if check_live_pins:
                # Multi-pin catalog values: try each id until one live listing works.
                # Pace requests to stay under Worker rate limits.
                live = None
                pin_id = None
                fetch_errors: list[str] = []
                saw_rate_limit = False
                for candidate in pins:
                    time.sleep(0.75)
                    try:
                        cand_live = _http_json(
                            f"{base_url.rstrip('/')}/v1/item?id={urllib.parse.quote(candidate)}"
                        )
                    except urllib.error.HTTPError as exc:
                        if exc.code == 429:
                            saw_rate_limit = True
                        fetch_errors.append(f"{candidate}: HTTP {exc.code}")
                        continue
                    except (
                        urllib.error.URLError,
                        TimeoutError,
                        json.JSONDecodeError,
                    ) as exc:
                        fetch_errors.append(f"{candidate}: {exc}")
                        continue
                    if isinstance(cand_live, dict) and cand_live.get("ok"):
                        live = cand_live
                        pin_id = candidate
                        break
                    fetch_errors.append(
                        f"{candidate}: {cand_live.get('error') if isinstance(cand_live, dict) else cand_live}"
                    )

                if live is None:
                    # Rate-limit / transport issues are warnings so CI does not
                    # false-fail when the Worker is protecting itself; definitive
                    # dead pins remain errors when we got a non-429 response.
                    sev = "warning" if saw_rate_limit else "error"
                    issue(
                        findings,
                        sev,
                        "pin_live_not_ok",
                        asin,
                        f"No healthy pinned listing among {pins}; tried: {'; '.join(fetch_errors)[:240]}",
                        q=q,
                    )
                else:
                    live_title = str(live.get("title") or "")
                    live_price = live.get("price")
                    try:
                        live_price_f = float(live_price) if live_price is not None else None
                    except (TypeError, ValueError):
                        live_price_f = None
                    free = bool(live.get("freeShipping")) or live.get("shippingCost") in (
                        0,
                        0.0,
                    )
                    cond = str(live.get("condition") or "").lower()
                    if not free:
                        issue(
                            findings,
                            "error",
                            "pin_not_free_ship",
                            asin,
                            f"Pinned item {pin_id} is not free shipping",
                            liveTitle=live_title[:100],
                            q=q,
                        )
                    if cond and "new" not in cond:
                        issue(
                            findings,
                            "error",
                            "pin_not_new",
                            asin,
                            f"Pinned item {pin_id} condition={live.get('condition')!r}",
                            q=q,
                        )
                    for tok in require_tokens:
                        tok_s = str(tok).strip()
                        if not tok_s:
                            continue
                        if re.search(r"\d", tok_s):
                            ok_tok = title_has_model_token(live_title, tok_s)
                        else:
                            ok_tok = tok_s.lower() in live_title.lower()
                        if not ok_tok:
                            issue(
                                findings,
                                "error",
                                "pin_missing_require_tokens",
                                asin,
                                f"Pinned item title missing token {tok_s!r}: {live_title[:90]!r}",
                                q=q,
                            )
                    # Snapshot should track pin price closely when source=pin
                    if (
                        source == "pin"
                        and ebay_price_f is not None
                        and live_price_f is not None
                        and normalize_item_id(snap_item) == normalize_item_id(pin_id)
                    ):
                        delta = abs(ebay_price_f - live_price_f)
                        pct = delta / max(live_price_f, 0.01)
                        if delta > PIN_PRICE_DELTA_USD and pct > PIN_PRICE_DELTA_PCT:
                            issue(
                                findings,
                                "warning",
                                "pin_price_drift",
                                asin,
                                f"Snapshot eBay ${ebay_price_f:.2f} vs live pin ${live_price_f:.2f} "
                                f"(delta ${delta:.2f})",
                                q=q,
                                pinId=pin_id,
                            )

        # Title identity for successful matches
        if ebay_ok_flag and title:
            models = required_model_tokens(q)
            for m in models:
                if not title_has_model_token(title, m):
                    sev = "error" if high_ticket else "warning"
                    issue(
                        findings,
                        sev,
                        "missing_model_token",
                        asin,
                        f"Title missing model token {m!r}: {title[:90]!r}",
                        ebay=ebay_price_f,
                        q=q,
                        highTicket=high_ticket,
                    )

            for tok in require_tokens:
                tok_s = str(tok).strip()
                if not tok_s:
                    continue
                if re.search(r"\d", tok_s):
                    ok_tok = title_has_model_token(title, tok_s)
                else:
                    ok_tok = tok_s.lower() in title.lower()
                if not ok_tok:
                    sev = "error" if (high_ticket or pins) else "warning"
                    issue(
                        findings,
                        sev,
                        "missing_require_token",
                        asin,
                        f"Title missing requireTokens {tok_s!r}: {title[:90]!r}",
                        ebay=ebay_price_f,
                        q=q,
                    )

            # High-ticket accessory-shaped titles
            if high_ticket and ACCESSORY_ONLY_RE.search(title):
                if not (
                    POWER_STATION_UNIT_RE.search(title) and WH_CAPACITY_RE.search(title)
                ):
                    issue(
                        findings,
                        "error",
                        "high_ticket_accessory_title",
                        asin,
                        f"High-ticket eBay title looks like accessory: {title[:90]!r}",
                        ebay=ebay_price_f,
                        q=q,
                    )

            # Power-station queries should show a unit with Wh when matched
            if re.search(r"power\s*station|explorer|solix|bluetti", q, re.I):
                if ebay_ok_flag and not WH_CAPACITY_RE.search(title):
                    # Official kits usually include Wh; warn if missing on expensive units
                    if high_ticket:
                        issue(
                            findings,
                            "warning",
                            "power_station_missing_wh",
                            asin,
                            f"Power-station match lacks Wh capacity in title: {title[:90]!r}",
                            ebay=ebay_price_f,
                            q=q,
                        )

        elif row.get("ebayOk") is False and pins:
            issue(
                findings,
                "warning",
                "pin_product_no_ebay",
                asin,
                f"Pinned catalog product has no eBay match: {row.get('ebayError') or 'ebayOk=false'}",
                q=q,
                expectedPins=pins,
            )

    errors = [f for f in findings if f["severity"] == "error"]
    warnings = [f for f in findings if f["severity"] == "warning"]

    return {
        "ok": len(errors) == 0,
        "generatedAt": now.isoformat(),
        "snapshotUpdatedAt": snap.get("updatedAt"),
        "snapshotAgeHours": round(age_h, 2) if age_h is not None else None,
        "catalogSize": catalog_size or len(cat_by_id),
        "snapshotCount": len(prices),
        "ebayOk": ebay_ok,
        "errorCount": len(errors),
        "warningCount": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "baseUrl": base_url,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Post-scan eBay snapshot accuracy audit")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE,
        help=f"Worker base URL (default {DEFAULT_BASE})",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        help="Path to snapshot JSON (default: GET {base}/v1/snapshot)",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path(__file__).resolve().parent / "src" / "catalog.json",
        help="Path to worker catalog.json",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Write full JSON report to this path",
    )
    parser.add_argument(
        "--fail-on",
        choices=("error", "warning"),
        default="error",
        help="Minimum severity that fails the process (default: error)",
    )
    parser.add_argument(
        "--skip-live-pins",
        action="store_true",
        help="Do not call /v1/item for each pin (snapshot-only checks)",
    )
    args = parser.parse_args(argv)

    if not args.catalog.is_file():
        print(f"ERROR: catalog not found: {args.catalog}", file=sys.stderr)
        return 2

    try:
        catalog = _load_json(args.catalog)
        if not isinstance(catalog, list):
            print("ERROR: catalog.json must be a JSON array", file=sys.stderr)
            return 2
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read catalog: {exc}", file=sys.stderr)
        return 2

    try:
        if args.snapshot:
            snap = _load_json(args.snapshot)
        else:
            snap = _http_json(f"{args.base_url.rstrip('/')}/v1/snapshot")
    except (OSError, urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot load snapshot: {exc}", file=sys.stderr)
        return 2

    if not isinstance(snap, dict) or not snap.get("ok"):
        print(f"ERROR: snapshot not ok: {snap!r}"[:500], file=sys.stderr)
        return 2

    report = audit(
        snap,
        catalog,
        base_url=args.base_url,
        check_live_pins=not args.skip_live_pins,
    )

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== AI Pick Vault post-scan audit ===")
    print(f"snapshotUpdatedAt: {report.get('snapshotUpdatedAt')}")
    print(f"snapshotAgeHours:  {report.get('snapshotAgeHours')}")
    print(
        f"coverage:          ebayOk={report.get('ebayOk')}/"
        f"{report.get('catalogSize')} (snapshot rows={report.get('snapshotCount')})"
    )
    print(f"errors:            {report.get('errorCount')}")
    print(f"warnings:          {report.get('warningCount')}")

    for f in report.get("errors") or []:
        print(
            f"ERROR [{f.get('code')}] {f.get('asin')}: {f.get('message')}",
            file=sys.stderr,
        )
    for f in report.get("warnings") or []:
        print(f"WARN  [{f.get('code')}] {f.get('asin')}: {f.get('message')}")

    if args.report:
        print(f"report:            {args.report}")

    fail_warnings = args.fail_on == "warning"
    if report["errorCount"] > 0:
        print("RESULT: FAIL (errors)")
        return 1
    if fail_warnings and report["warningCount"] > 0:
        print("RESULT: FAIL (warnings)")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
