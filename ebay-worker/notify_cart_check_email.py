#!/usr/bin/env python3
"""
Build (and optionally send) a plain-English email when price audit needs a
human eBay cart check (pin_undercut / similar).

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
import smtplib
import sys
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path
from typing import Any

DEFAULT_TO = "bamtec70@gmail.com"


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
