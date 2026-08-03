#!/usr/bin/env python3
"""
Build (and optionally send) a plain-English email when price audit needs a
human eBay cart check (pin_undercut / similar).

Every item block leads with the **site product name** (description), not only
the ASIN, so the subject and body make clear what to open on aipickvault.com.

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
    "pin_undercut": "Cheaper eBay listing found than our pin — cart-check before switching",
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
    # v1|parent|var → parent (and var if non-zero)
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


def build_email(
    report: dict[str, Any],
    run_url: str = "",
    site_names: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Return (subject, plain_text_body). Subject always names the product(s)."""
    names = site_names if site_names is not None else load_site_product_names()
    checks = cart_check_errors(report)
    n = len(checks)

    if n == 0:
        subject = "AI Pick Vault: price audit needs attention"
    elif n == 1:
        subject = f"AI Pick Vault: cart check — {product_label(checks[0], names)}"
    else:
        first = product_label(checks[0], names)
        subject = f"AI Pick Vault: cart check — {first} (+{n - 1} more)"

    lines: list[str] = [
        "Hi,",
        "",
        "A price scan found eBay listing(s) that need a human cart check.",
        "Do not change pins until you open the links and confirm the item is real.",
        "",
        "WHAT THIS MEANS",
        "---------------",
        "We keep a preferred eBay listing (pin) for some products. Search found a",
        "much cheaper free-ship New match. That can be a real deal - or a wrong",
        "SKU, open-box, one-off, or bad seller. You must verify in a browser.",
        "",
        f"Snapshot time: {report.get('snapshotUpdatedAt') or 'unknown'}",
        f"eBay OK rate:  {report.get('ebayOk')}/{report.get('catalogSize')}",
        "",
    ]

    if not checks:
        # Still list any other product-level errors so the email is useful
        other = [
            e
            for e in (report.get("errors") or [])
            if isinstance(e, dict) and str(e.get("asin") or "") not in ("", "*")
        ]
        if other:
            lines += [
                "AUDIT ERRORS (no pin_undercut rows — still name each product)",
                "-------------------------------------------------------------",
            ]
            for i, e in enumerate(other[:15], 1):
                label = product_label(e, names)
                asin = e.get("asin") or "?"
                lines += [
                    "",
                    f"{i}) PRODUCT: {label}",
                    f"   ASIN:    {asin}",
                    f"   Amazon:  https://www.amazon.com/dp/{asin}",
                    f"   Issue:   [{e.get('code')}] {e.get('message') or ''}",
                ]
            lines.append("")
        else:
            lines += [
                "No product-level cart-check rows were found in the report.",
                "Open the GitHub Actions run for the full failure reason.",
                "",
            ]
    else:
        lines.append("ITEMS TO CHECK (by product name)")
        lines.append("--------------------------------")
        for i, e in enumerate(checks, 1):
            label = product_label(e, names)
            asin = str(e.get("asin") or "?")
            code = str(e.get("code") or "")
            why = CODE_LABELS.get(code) or str(e.get("message") or code)
            pin_p = e.get("pinPrice")
            alt_p = e.get("altPrice")
            pin_url = str(e.get("pinUrl") or "").strip()
            alt_url = str(e.get("altUrl") or "").strip()
            if not alt_url and e.get("altItemId"):
                alt_url = _ebay_itm_url(e.get("altItemId"))
            if not pin_url and e.get("ebayItemId"):
                pin_url = _ebay_itm_url(e.get("ebayItemId"))
            pin_title = str(e.get("pinTitle") or e.get("ebayTitle") or "").strip()
            alt_title = str(e.get("altTitle") or "").strip()
            q = str(e.get("q") or "").strip()
            amz = str(e.get("amazonUrl") or f"https://www.amazon.com/dp/{asin}")

            lines += [
                "",
                f"{i}) PRODUCT: {label}",
                f"   Why:           {why}",
                f"   ASIN:          {asin}",
                f"   Amazon page:   {amz}",
                f"   Site search q: {q}" if q else "",
                f"   Audit code:    {code}",
                f"   Detail:        {e.get('message') or ''}",
            ]
            if pin_p is not None:
                lines.append(f"   Pinned price:  ${pin_p}")
            if pin_title:
                lines.append(f"   Pinned title:  {pin_title[:100]}")
            if pin_url:
                lines.append(f"   Pinned eBay:   {pin_url}")
            if alt_p is not None:
                lines.append(f"   Cheaper alt:   ${alt_p}")
            if e.get("savingsPct") is not None:
                lines.append(f"   Savings vs pin:{e.get('savingsPct')}%")
            if alt_title:
                lines.append(f"   Alt title:     {alt_title[:100]}")
            if alt_url:
                lines.append(f"   Alt listing:   {alt_url}")

            lines += [
                "",
                "   CHECKLIST (2-3 minutes):",
                "   [ ] Open the cheaper (or problem) eBay link while logged in",
                "   [ ] Confirm this is the SAME product as the site name above",
                "   [ ] Condition is New (not open box / used / refurbished)",
                "   [ ] Title is the REAL product (not a case, cable, or bag)",
                "   [ ] Free shipping (or note paid ship) to a US address",
                "   [ ] Seller looks legitimate; quantity not a sketchy one-off if that matters",
                "   [ ] Add to cart - confirm price + ship still match",
                "",
                "   THEN:",
                "   * If the cheap listing is GOOD: update pin to that item ID",
                "   * If BAD / OOS / one-off junk: block that item ID (ebayExcludeItemIds)",
                "     and keep or replace the pin with a known-good listing",
            ]

    lines += [
        "",
        "GITHUB RUN",
        "----------",
        run_url or "(open GitHub -> Actions -> Price scan audit for this run)",
        "",
        "This email is only for human cart checks. Automated matching will not",
        "switch pins by itself.",
        "",
        "- AI Pick Vault price audit",
    ]
    # Drop blank optional fields we inserted as ""
    body = "\n".join(line for line in lines if line is not None)
    # Collapse triple blank lines
    while "\n\n\n" in body:
        body = body.replace("\n\n\n", "\n\n")
    return subject, body


def send_gmail_smtp(to: str, subject: str, body: str) -> None:
    """Send via Gmail SMTP using an App Password (recommended path to bamtec70@gmail.com)."""
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
    """
    Prefer Gmail SMTP (works with From=your Gmail, To=your Gmail).
    Fall back to Resend only if Gmail secrets are absent.
    Returns transport name used.
    """
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
    args = parser.parse_args(argv)

    if not args.report.is_file():
        print(f"No report at {args.report} — nothing to email", file=sys.stderr)
        return 0

    report = load_report(args.report)
    site_names = load_site_product_names(args.index)
    checks = cart_check_errors(report)
    subject, body = build_email(
        report,
        args.run_url or os.environ.get("RUN_URL", ""),
        site_names=site_names,
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
        except Exception as exc:  # noqa: BLE001 — surface transport errors
            print(f"ERROR sending email: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
