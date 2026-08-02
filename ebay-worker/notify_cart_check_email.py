#!/usr/bin/env python3
"""
Build (and optionally send) a plain-English email when price audit needs a
human eBay cart check (pin_undercut / similar).

Usage:
  python notify_cart_check_email.py --report _audit/report.json
  python notify_cart_check_email.py --report _audit/report.json --send

Env for --send (optional):
  CART_CHECK_EMAIL_TO   recipient (default: contact@aipickvault.com)
  RESEND_API_KEY        if set, send via Resend API
  RESEND_FROM           default: AI Pick Vault <onboarding@resend.dev>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def cart_check_errors(report: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for e in report.get("errors") or []:
        if not isinstance(e, dict):
            continue
        code = str(e.get("code") or "")
        if code in {"pin_undercut", "pin_invalid", "pin_dead"} or "cart-check" in str(
            e.get("message") or ""
        ).lower():
            out.append(e)
    return out


def build_email(report: dict[str, Any], run_url: str = "") -> tuple[str, str]:
    """Return (subject, plain_text_body)."""
    checks = cart_check_errors(report)
    n = len(checks)
    subject = (
        f"AI Pick Vault: cart check needed ({n} listing{'s' if n != 1 else ''})"
        if n
        else "AI Pick Vault: price audit needs attention"
    )

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
        lines += [
            "No pin_undercut rows were found in the report.",
            "Open the GitHub Actions run for the full failure reason.",
            "",
        ]
    else:
        lines.append("ITEMS TO CHECK")
        lines.append("--------------")
        for i, e in enumerate(checks, 1):
            asin = e.get("asin") or "?"
            pin_p = e.get("pinPrice")
            alt_p = e.get("altPrice")
            pin_url = e.get("pinUrl") or ""
            alt_url = e.get("altUrl") or ""
            # Reconstruct pin URL from message if missing
            if not alt_url and e.get("altItemId"):
                key = str(e["altItemId"]).replace("v1|", "").split("|")[0]
                if key.isdigit():
                    alt_url = f"https://www.ebay.com/itm/{key}"
            lines += [
                "",
                f"{i}) ASIN {asin}",
                f"   Product / note: {e.get('message') or e.get('code')}",
                f"   Pinned price:   ${pin_p}" if pin_p is not None else "   Pinned price:   (see report)",
                f"   Cheaper alt:    ${alt_p}" if alt_p is not None else "",
                f"   Alt listing:    {alt_url}" if alt_url else "",
                f"   Search query:   {e.get('q') or ''}",
                "",
                "   CHECKLIST (2-3 minutes):",
                "   [ ] Open the cheaper link while logged into eBay",
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
    # drop empty strings from optional fields carefully
    body = "\n".join(line for line in lines if line is not None)
    return subject, body


def send_resend(to: str, subject: str, body: str) -> None:
    api_key = (os.environ.get("RESEND_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("RESEND_API_KEY not set")
    frm = (os.environ.get("RESEND_FROM") or "AI Pick Vault <onboarding@resend.dev>").strip()
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
    with urllib.request.urlopen(req, timeout=30) as res:
        print("Resend response:", res.read().decode("utf-8", "replace")[:300])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cart-check email from audit report")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None, help="Write body to this file")
    parser.add_argument("--send", action="store_true", help="Send via Resend if configured")
    parser.add_argument("--run-url", default="")
    args = parser.parse_args(argv)

    if not args.report.is_file():
        print(f"No report at {args.report} — nothing to email", file=sys.stderr)
        return 0

    report = load_report(args.report)
    checks = cart_check_errors(report)
    subject, body = build_email(report, args.run_url or os.environ.get("RUN_URL", ""))

    out = args.out or args.report.with_name("cart_check_email.txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"Subject: {subject}\n\n{body}\n", encoding="utf-8")
    print(f"Wrote {out}")
    print(f"Cart-check items: {len(checks)}")

    if not checks and not args.send:
        print("No cart-check errors — email body still written for the run artifact.")
        return 0

    if args.send:
        to = (os.environ.get("CART_CHECK_EMAIL_TO") or "contact@aipickvault.com").strip()
        if not (os.environ.get("RESEND_API_KEY") or "").strip():
            print(
                "RESEND_API_KEY not set — skip send. Artifact has the full email text.",
                file=sys.stderr,
            )
            return 0
        try:
            send_resend(to, subject, body)
            print(f"Email sent to {to}")
        except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as exc:
            print(f"ERROR sending email: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
