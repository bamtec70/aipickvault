#!/usr/bin/env python3
"""
Build (and optionally send) a short plain-text email when price audit needs a
human eBay cart check. Reply commands (KEEP/SWITCH/EXCLUDE/DROP) are processed
by process_cart_check_replies.py.

Usage:
  python notify_cart_check_email.py --report _audit/report.json
  python notify_cart_check_email.py --report _audit/report.json --send

Env for --send (preferred: Gmail SMTP to bamtec70@gmail.com):
  CART_CHECK_EMAIL_TO   recipient (default: bamtec70@gmail.com)
  GMAIL_USER            Gmail address used as From (e.g. bamtec70@gmail.com)
  GMAIL_APP_PASSWORD    Google App Password (16 chars, not account password)

Fallback Resend (needs verified domain From — not onboarding@resend.dev):
  RESEND_API_KEY
  RESEND_FROM
"""

from __future__ import annotations

import argparse
import json
import os
import re
import smtplib
import sys
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path
from typing import Any

DEFAULT_TO = "bamtec70@gmail.com"

# Human cart-check / pin health codes (product-level — always name the product)
CART_CHECK_CODES = frozenset(
    {
        "pin_undercut",
        "pin_invalid",
        "pin_dead",
        "pin_not_used",
        "pin_item_mismatch",
        "pin_live_not_ok",
        "pin_not_free_ship",
        "pin_not_new",
        "pin_missing_require_tokens",
        "pin_product_no_ebay",
    }
)

CODE_LABELS = {
    "pin_undercut": "Cheaper eBay listing than our pin — cart-check before switching",
    "pin_invalid": "Pinned eBay listing is invalid",
    "pin_dead": "Pinned eBay listing is dead / unavailable",
    "pin_not_used": "Pin not used — site fell back to search",
    "pin_item_mismatch": "Snapshot item ID does not match catalog pin",
    "pin_live_not_ok": "Pinned listing failed live fetch",
    "pin_not_free_ship": "Pinned listing is not free shipping",
    "pin_not_new": "Pinned listing is not New condition",
    "pin_missing_require_tokens": "Pinned listing title missing required model tokens",
    "pin_product_no_ebay": "Pinned product has no eBay match",
}

# Prefer these codes when merging duplicate ASIN rows
_CODE_PRIORITY = {
    "pin_undercut": 100,
    "pin_item_mismatch": 90,
    "pin_not_used": 80,
    "pin_live_not_ok": 70,
    "pin_dead": 60,
    "pin_invalid": 50,
    "pin_not_free_ship": 40,
    "pin_not_new": 30,
    "pin_missing_require_tokens": 20,
    "pin_product_no_ebay": 10,
}


def load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_site_product_names(index_path: Path | None = None) -> dict[str, str]:
    """ASIN → site product name from index.html."""
    path = index_path or Path(__file__).resolve().parent.parent / "index.html"
    if not path.is_file():
        return {}
    try:
        html = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    pattern = re.compile(
        r'asin:\s*"([^"]+)"\s*,\s*name:\s*"((?:\\.|[^"\\])*)"',
        re.M,
    )
    out: dict[str, str] = {}
    for m in pattern.finditer(html):
        asin = m.group(1).strip()
        name = m.group(2).replace('\\"', '"').replace("\\n", " ").strip()
        if asin and name:
            out[asin] = name
    return out


def load_catalog_pins(catalog_path: Path | None = None) -> dict[str, str]:
    """ASIN → ebayPreferItemId from worker catalog."""
    root = Path(__file__).resolve().parent
    path = catalog_path or (root / "src" / "catalog.json")
    if not path.is_file():
        path = root / "catalog.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, str] = {}
    if not isinstance(data, list):
        return out
    for row in data:
        if not isinstance(row, dict):
            continue
        asin = str(row.get("id") or "").strip()
        pin = str(row.get("ebayPreferItemId") or row.get("ebayPinItemId") or "").strip()
        if asin and pin:
            out[asin] = pin
    return out


def product_label(e: dict[str, Any], site_names: dict[str, str] | None = None) -> str:
    """Best human description for an audit error row."""
    names = site_names or {}
    asin = str(e.get("asin") or "").strip()
    for key in ("productName", "name", "siteName"):
        val = str(e.get(key) or "").strip()
        if val:
            return val
    if asin and names.get(asin):
        return names[asin]
    q = str(e.get("q") or e.get("productQuery") or "").strip()
    if q:
        return q
    if asin and asin != "*":
        return f"Unknown product (ASIN {asin})"
    return "Site-wide / unknown product"


def cart_check_errors(report: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for e in report.get("errors") or []:
        if not isinstance(e, dict):
            continue
        code = str(e.get("code") or "")
        msg = str(e.get("message") or "").lower()
        if code in CART_CHECK_CODES or "cart-check" in msg or "cart check" in msg:
            out.append(e)
    return out


def _ebay_itm_url(item_id: Any) -> str:
    if not item_id:
        return ""
    s = str(item_id).strip()
    m = re.fullmatch(r"v1\|(\d+)\|(\d+)", s, re.I)
    if m:
        parent, var = m.group(1), m.group(2)
        if var == "0":
            return f"https://www.ebay.com/itm/{parent}"
        return f"https://www.ebay.com/itm/{parent}?var={var}"
    if re.fullmatch(r"\d+\|\d+", s):
        parent, var = s.split("|", 1)
        return f"https://www.ebay.com/itm/{parent}?var={var}"
    key = s.replace("v1|", "").split("|")[0]
    if key.isdigit():
        return f"https://www.ebay.com/itm/{key}"
    return ""


def _first_expected_pin(e: dict[str, Any], catalog_pins: dict[str, str]) -> str:
    pins = e.get("expectedPins")
    if isinstance(pins, list) and pins:
        return str(pins[0]).strip()
    if isinstance(pins, str) and pins.strip():
        return pins.strip()
    for key in ("ebayPreferItemId", "ebayPinItemId"):
        val = str(e.get(key) or "").strip()
        if val:
            return val
    asin = str(e.get("asin") or "").strip()
    if asin and catalog_pins.get(asin):
        return catalog_pins[asin]
    return ""


def _same_item(a: Any, b: Any) -> bool:
    def norm(raw: Any) -> str:
        if not raw:
            return ""
        s = str(raw).strip()
        m = re.fullmatch(r"v1\|(\d+)\|(\d+)", s, re.I)
        if m:
            parent, var = m.group(1), m.group(2)
            return parent if var == "0" else f"{parent}|{var}"
        if re.fullmatch(r"\d+\|\d+", s):
            parent, var = s.split("|", 1)
            return parent if var == "0" else f"{parent}|{var}"
        if re.fullmatch(r"\d+", s):
            return s
        digits = re.findall(r"\d{6,}", s)
        return digits[-1] if digits else s

    na, nb = norm(a), norm(b)
    return bool(na and nb and na == nb)


def resolve_pin_and_alt(
    e: dict[str, Any],
    catalog_pins: dict[str, str] | None = None,
) -> tuple[str, str, str, str]:
    """
    Return (pin_url, alt_url, pin_id, alt_id).

    For pin_not_used / pin_live_not_ok: Current pin = catalog expectedPins /
    ebayPreferItemId (NOT search fallback). Alternate = snapshot/search id.
    """
    pins_map = catalog_pins or {}
    code = str(e.get("code") or "")
    catalog_pin = _first_expected_pin(e, pins_map)

    alt_id = str(e.get("altItemId") or "").strip()
    snap_id = str(e.get("ebayItemId") or "").strip()

    if code in ("pin_not_used", "pin_live_not_ok", "pin_dead", "pin_invalid"):
        pin_id = catalog_pin
        pin_url = _ebay_itm_url(pin_id) if pin_id else ""
        cand = alt_id or snap_id
        if cand and not _same_item(cand, pin_id):
            alt_id = cand
            alt_url = str(e.get("altUrl") or "").strip() or _ebay_itm_url(cand)
        else:
            alt_id = alt_id or ""
            alt_url = str(e.get("altUrl") or "").strip() or (
                _ebay_itm_url(alt_id) if alt_id else ""
            )
        return (
            pin_url or "(none / dead)",
            alt_url or "(none)",
            pin_id,
            alt_id,
        )

    pin_id = catalog_pin
    pin_url = str(e.get("pinUrl") or "").strip()
    if not pin_url and pin_id:
        pin_url = _ebay_itm_url(pin_id)
    # Do NOT fall back to ebayItemId when we have a catalog pin — that was the bug
    if not pin_url and not pin_id and snap_id:
        pin_url = _ebay_itm_url(snap_id)
        pin_id = snap_id

    alt_url = str(e.get("altUrl") or "").strip()
    if not alt_url and alt_id:
        alt_url = _ebay_itm_url(alt_id)
    if not alt_url and snap_id and pin_id and not _same_item(snap_id, pin_id):
        alt_id = snap_id
        alt_url = _ebay_itm_url(snap_id)

    return (
        pin_url or "(none / dead)",
        alt_url or "(none)",
        pin_id,
        alt_id,
    )


def one_line_reason(e: dict[str, Any], codes: list[str] | None = None) -> str:
    codes = codes or [str(e.get("code") or "")]
    labels = []
    for c in codes:
        if not c:
            continue
        labels.append(CODE_LABELS.get(c) or c)
    msg = str(e.get("message") or "").strip()
    if e.get("pinPrice") is not None and e.get("altPrice") is not None:
        try:
            return (
                f"Pin ${float(e['pinPrice']):.2f} vs alt ${float(e['altPrice']):.2f}"
                + (
                    f" ({e.get('savingsPct')}% cheaper)"
                    if e.get("savingsPct") is not None
                    else ""
                )
            )
        except (TypeError, ValueError):
            pass
    if labels:
        base = labels[0]
        if len(labels) > 1:
            extra = ", ".join(codes[1:])
            return f"{base} (+{extra})"
        if len(msg) > 120:
            return base
        return base if not msg or msg.lower().startswith(base[:20].lower()) else msg[:120]
    return msg[:120] or "Needs cart check"


def dedupe_cart_checks(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One block per ASIN — merge pin_not_used + pin_live_not_ok (and others)."""
    by_asin: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    merge_keys = (
        "pinUrl",
        "altUrl",
        "altItemId",
        "altPrice",
        "pinPrice",
        "pinTitle",
        "altTitle",
        "expectedPins",
        "ebayItemId",
        "ebayPreferItemId",
        "savingsPct",
        "productName",
        "q",
        "amazonUrl",
    )
    for e in checks:
        asin = str(e.get("asin") or "").strip() or "?"
        if asin not in by_asin:
            by_asin[asin] = dict(e)
            by_asin[asin]["_codes"] = [str(e.get("code") or "")]
            order.append(asin)
            continue
        cur = by_asin[asin]
        codes: list[str] = list(cur.get("_codes") or [])
        code = str(e.get("code") or "")
        if code and code not in codes:
            codes.append(code)
        cur["_codes"] = codes
        cur_pri = _CODE_PRIORITY.get(str(cur.get("code") or ""), 0)
        new_pri = _CODE_PRIORITY.get(code, 0)
        if new_pri > cur_pri:
            merged = dict(e)
            merged["_codes"] = codes
            for k in merge_keys:
                if merged.get(k) in (None, "", [], {}) and cur.get(k) not in (
                    None,
                    "",
                    [],
                    {},
                ):
                    merged[k] = cur[k]
            by_asin[asin] = merged
        else:
            for k in merge_keys:
                if cur.get(k) in (None, "", [], {}) and e.get(k) not in (
                    None,
                    "",
                    [],
                    {},
                ):
                    cur[k] = e[k]
            ep_cur = cur.get("expectedPins") or []
            ep_new = e.get("expectedPins") or []
            if isinstance(ep_cur, str):
                ep_cur = [ep_cur]
            if isinstance(ep_new, str):
                ep_new = [ep_new]
            if ep_new:
                merged_pins = list(ep_cur)
                for p in ep_new:
                    if p not in merged_pins:
                        merged_pins.append(p)
                cur["expectedPins"] = merged_pins
    return [by_asin[a] for a in order]


def build_email(
    report: dict[str, Any],
    run_url: str = "",
    site_names: dict[str, str] | None = None,
    catalog_pins: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Return (subject, plain_text_body). Short reply-driven template."""
    names = site_names if site_names is not None else load_site_product_names()
    pins_map = catalog_pins if catalog_pins is not None else load_catalog_pins()
    checks = dedupe_cart_checks(cart_check_errors(report))
    n = len(checks)

    if n == 0:
        subject = "AI Pick Vault: cart check — (none)"
    elif n == 1:
        subject = f"AI Pick Vault: cart check — {product_label(checks[0], names)}"
    else:
        first = product_label(checks[0], names)
        subject = f"AI Pick Vault: cart check — {first} (+{n - 1} more)"

    lines: list[str] = [
        "AI Pick Vault — cart check needed",
        "",
        "Do these in order. Then REPLY to this email with the commands at the bottom.",
        "",
    ]

    if not checks:
        lines += [
            "No product-level cart-check rows were found in the report.",
            "Open the GitHub Actions run for the full failure reason.",
            "",
        ]
        if run_url:
            lines += [f"Run: {run_url}", ""]
        return subject, "\n".join(lines).rstrip() + "\n"

    for i, e in enumerate(checks, 1):
        label = product_label(e, names)
        asin = str(e.get("asin") or "?")
        codes = list(e.get("_codes") or [str(e.get("code") or "")])
        why = one_line_reason(e, codes)
        pin_url, alt_url, _pin_id, _alt_id = resolve_pin_and_alt(e, pins_map)

        lines += [
            "────────────────────────────────",
            f"{i}) PRODUCT: {label}",
            f"   WHY: {why}",
            f"   ASIN: {asin}",
            f"   Amazon: https://www.amazon.com/dp/{asin}",
            "",
            "   VERIFY (open in browser):",
            f"   A. Current pin: {pin_url}",
            f"   B. Alternate:   {alt_url}",
            "",
            "   Check: New? Free shipping? Correct model? Not accessory/open-box?",
            "────────────────────────────────",
            "",
        ]

    lines += [
        "HOW TO REPLY (one line per product — copy/paste):",
        "KEEP {asin}     → keep pin; set ebaySkipPinUndercut true (stops undercut alerts)",
        "SWITCH {asin}   → point pin at the alternate listing from this email",
        "EXCLUDE {asin}  → keep pin; add alternate item id to ebayExcludeItemIds",
        "DROP {asin}     → remove ebayPreferItemId (search-only)",
        "",
        "Example:",
        "KEEP B07R295MLS",
        "SWITCH B0FDWMP57L",
        "",
        "Subject of your reply can stay Re: … — we parse the body only.",
    ]
    if run_url:
        lines += ["", f"GitHub run: {run_url}"]

    body = "\n".join(lines)
    while "\n\n\n" in body:
        body = body.replace("\n\n\n", "\n\n")
    return subject, body


def send_gmail_smtp(to: str, subject: str, body: str) -> None:
    """Send via Gmail SMTP using an App Password."""
    user = (os.environ.get("GMAIL_USER") or "").strip()
    password = (os.environ.get("GMAIL_APP_PASSWORD") or "").strip().replace(" ", "")
    if not user or not password:
        raise RuntimeError("GMAIL_USER and GMAIL_APP_PASSWORD required for Gmail SMTP")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"AI Pick Vault <{user}>"
    msg["To"] = to
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=45) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)
    print(f"Gmail SMTP: sent From={user} To={to}")


def send_resend(to: str, subject: str, body: str) -> None:
    api_key = (os.environ.get("RESEND_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("RESEND_API_KEY not set")
    frm = (os.environ.get("RESEND_FROM") or "").strip()
    if not frm:
        raise RuntimeError(
            "RESEND_FROM not set. Prefer Gmail SMTP (GMAIL_USER + GMAIL_APP_PASSWORD) "
            "instead of Resend if you only need mail to Gmail."
        )
    if "onboarding@resend.dev" in frm.lower():
        raise RuntimeError(
            "RESEND_FROM still uses onboarding@resend.dev — rejected by Cloudflare/Resend. "
            "Use Gmail SMTP secrets instead."
        )
    payload = json.dumps(
        {
            "from": frm,
            "to": [to],
            "subject": subject,
            "text": body,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            print("Resend response:", res.read().decode("utf-8", "replace")[:300])
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"Resend HTTP {exc.code}: {detail}") from exc


def send_email(to: str, subject: str, body: str) -> str:
    """Prefer Gmail SMTP; fall back to Resend only if Gmail secrets are absent."""
    gmail_user = (os.environ.get("GMAIL_USER") or "").strip()
    gmail_pass = (os.environ.get("GMAIL_APP_PASSWORD") or "").strip()
    if gmail_user and gmail_pass:
        send_gmail_smtp(to, subject, body)
        return "gmail_smtp"
    if (os.environ.get("RESEND_API_KEY") or "").strip():
        send_resend(to, subject, body)
        return "resend"
    raise RuntimeError(
        "No email transport configured. Set GitHub secrets "
        "GMAIL_USER + GMAIL_APP_PASSWORD (recommended), or RESEND_API_KEY + RESEND_FROM."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cart-check email from audit report")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None, help="Write body to this file")
    parser.add_argument(
        "--send",
        action="store_true",
        help="Send email (Gmail SMTP preferred; Resend fallback)",
    )
    parser.add_argument(
        "--force-send",
        action="store_true",
        help="Send even if no cart-check errors (test)",
    )
    parser.add_argument("--run-url", default="")
    parser.add_argument(
        "--index",
        type=Path,
        default=None,
        help="Path to index.html for product names (default: repo root index.html)",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="Path to catalog.json for pin resolution (default: src/catalog.json)",
    )
    args = parser.parse_args(argv)

    if not args.report.is_file():
        print(f"No report at {args.report} — nothing to email", file=sys.stderr)
        return 0

    report = load_report(args.report)
    site_names = load_site_product_names(args.index)
    catalog_pins = load_catalog_pins(args.catalog)
    checks = dedupe_cart_checks(cart_check_errors(report))
    subject, body = build_email(
        report,
        args.run_url or os.environ.get("RUN_URL", ""),
        site_names=site_names,
        catalog_pins=catalog_pins,
    )

    out = args.out or args.report.with_name("cart_check_email.txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"Subject: {subject}\n\n{body}\n", encoding="utf-8")
    print(f"Wrote {out}")
    print(f"Subject: {subject}")
    print(f"Cart-check items: {len(checks)}")
    for e in checks:
        print(f"  - {product_label(e, site_names)} ({e.get('asin')}) [{e.get('code')}]")

    if not checks and not args.force_send:
        print("No cart-check errors — email body written; not sending.")
        return 0

    if args.send or args.force_send:
        to = (os.environ.get("CART_CHECK_EMAIL_TO") or DEFAULT_TO).strip()
        try:
            transport = send_email(to, subject, body)
            print(f"Email sent via {transport} to {to}")
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR sending email: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
