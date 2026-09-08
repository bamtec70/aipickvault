#!/usr/bin/env python3
"""
Process Gmail replies to cart-check emails and apply pin actions.

Commands (one per line in the reply body, case-insensitive):
  KEEP {ASIN}     → set ebaySkipPinUndercut true (keep pin, stop undercut alerts)
  SWITCH {ASIN}   → set ebayPreferItemId to the alternate listing from the report
  EXCLUDE {ASIN}  → keep pin; add alternate item id to ebayExcludeItemIds
  DROP {ASIN}     → remove ebayPreferItemId (search-only)

Usage:
  python process_cart_check_replies.py
  python process_cart_check_replies.py --dry-run
  python process_cart_check_replies.py --report _audit/report.json --no-imap

Env:
  GMAIL_USER
  GMAIL_APP_PASSWORD
"""

from __future__ import annotations

import argparse
import email
import email.header
import imaplib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.message import Message
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CATALOG_SRC = ROOT / "src" / "catalog.json"
CATALOG_ROOT = ROOT / "catalog.json"
INDEX_HTML = REPO / "index.html"
AUDIT_DIR = ROOT / "_audit"
DEFAULT_REPORT = AUDIT_DIR / "report.json"
REPLY_LOG = AUDIT_DIR / "reply_actions.json"

CMD_RE = re.compile(
    r"^(KEEP|SWITCH|EXCLUDE|DROP)\s+(B0[A-Z0-9]{8,})\b",
    re.I | re.M,
)
SUBJECT_HINT = "AI Pick Vault: cart check"
ASIN_RE = re.compile(r"^B0[A-Z0-9]{8,}$", re.I)

PRICE_API_DEFAULT = "https://ebay-api.aipickvault.com"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode_header(raw: str | None) -> str:
    if not raw:
        return ""
    parts = email.header.decode_header(raw)
    out: list[str] = []
    for text, charset in parts:
        if isinstance(text, bytes):
            out.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


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


def normalize_item_id(raw: str | None) -> str:
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


def catalog_pin_form(item_id: str) -> str:
    """Prefer plain legacy / parent|var form for catalog storage."""
    s = str(item_id or "").strip()
    m = re.fullmatch(r"v1\|(\d+)\|(\d+)", s, re.I)
    if m:
        parent, var = m.group(1), m.group(2)
        return parent if var == "0" else f"{parent}|{var}"
    return s


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_catalog(path: Path) -> list[dict[str, Any]]:
    data = load_json(path)
    if not isinstance(data, list):
        raise RuntimeError(f"Catalog is not a list: {path}")
    return data


def save_catalog(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def find_row(catalog: list[dict[str, Any]], asin: str) -> dict[str, Any] | None:
    asin_u = asin.upper()
    for row in catalog:
        if str(row.get("id") or "").upper() == asin_u:
            return row
    return None


def build_alt_map(
    report: dict[str, Any] | None,
    snapshot: dict[str, Any] | None,
    catalog: list[dict[str, Any]],
) -> dict[str, str]:
    """ASIN → alternate eBay item id for SWITCH/EXCLUDE."""
    out: dict[str, str] = {}
    if report:
        for e in (report.get("errors") or []) + (report.get("warnings") or []):
            if not isinstance(e, dict):
                continue
            asin = str(e.get("asin") or "").strip().upper()
            if not ASIN_RE.match(asin):
                continue
            alt = str(e.get("altItemId") or "").strip()
            if not alt:
                # For pin_not_used: snapshot/search id is the alternate
                code = str(e.get("code") or "")
                if code in ("pin_not_used", "pin_live_not_ok", "pin_item_mismatch"):
                    alt = str(e.get("ebayItemId") or "").strip()
            if alt:
                out[asin] = catalog_pin_form(alt)

    prices = (snapshot or {}).get("prices") or {}
    if isinstance(prices, dict):
        for asin, row in prices.items():
            if not isinstance(row, dict):
                continue
            key = str(asin).strip().upper()
            if key in out:
                continue
            alt = str(row.get("ebayAltItemId") or "").strip()
            if alt:
                out[key] = catalog_pin_form(alt)
                continue
            # Search fallback when pin not used
            if str(row.get("ebaySource") or "") != "pin":
                snap_id = str(row.get("ebayItemId") or "").strip()
                pin_field = ""
                crow = find_row(catalog, key)
                if crow:
                    pin_field = str(
                        crow.get("ebayPreferItemId") or crow.get("ebayPinItemId") or ""
                    ).strip()
                if snap_id and normalize_item_id(snap_id) != normalize_item_id(pin_field):
                    out[key] = catalog_pin_form(snap_id)
    return out


def fetch_snapshot(base_url: str) -> dict[str, Any] | None:
    url = f"{base_url.rstrip('/')}/v1/snapshot"
    try:
        with urllib.request.urlopen(url, timeout=45) as res:
            return json.loads(res.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        print(f"WARN: could not fetch live snapshot: {exc}", file=sys.stderr)
        return None


def parse_commands_from_body(body: str) -> list[tuple[str, str]]:
    body = (body or "").lstrip("\ufeff")
    cmds: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for m in CMD_RE.finditer(body or ""):
        action = m.group(1).upper()
        asin = m.group(2).upper()
        key = (action, asin)
        if key in seen:
            continue
        seen.add(key)
        cmds.append((action, asin))
    return cmds


def _get_body_text(msg: Message) -> str:
    if msg.is_multipart():
        texts: list[str] = []
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp.lower():
                continue
            if ctype == "text/plain":
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                texts.append(payload.decode(charset, errors="replace"))
            elif ctype == "text/html" and not texts:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                html = payload.decode(charset, errors="replace")
                # Crude HTML → text
                html = re.sub(r"(?i)<br\s*/?>", "\n", html)
                html = re.sub(r"(?i)</p>", "\n", html)
                html = re.sub(r"<[^>]+>", "", html)
                texts.append(html)
        return "\n".join(texts)
    payload = msg.get_payload(decode=True)
    if payload is None:
        return str(msg.get_payload() or "")
    charset = msg.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def _subject_matches(subject: str) -> bool:
    s = subject or ""
    return SUBJECT_HINT.lower() in s.lower()


def fetch_imap_replies(
    user: str,
    password: str,
    *,
    mark_seen: bool = True,
    add_label: bool = True,
) -> list[dict[str, Any]]:
    """Return list of {uid, subject, body, commands} for matching UNSEEN (and recent) replies."""
    password = password.replace(" ", "")
    results: list[dict[str, Any]] = []
    with imaplib.IMAP4_SSL("imap.gmail.com", 993) as imap:
        imap.login(user, password)
        typ, _ = imap.select("INBOX")
        if typ != "OK":
            raise RuntimeError("Could not select INBOX")

        # UNSEEN first; also recent ALL with subject search as fallback window
        uids: list[bytes] = []
        for criteria in (
            '(UNSEEN SUBJECT "AI Pick Vault: cart check")',
            '(UNSEEN SUBJECT "cart check")',
            '(RECENT SUBJECT "AI Pick Vault: cart check")',
        ):
            typ, data = imap.uid("search", None, criteria)
            if typ == "OK" and data and data[0]:
                for u in data[0].split():
                    if u not in uids:
                        uids.append(u)

        # If still empty, scan last ~40 unseen regardless of subject (threading)
        if not uids:
            typ, data = imap.uid("search", None, "UNSEEN")
            if typ == "OK" and data and data[0]:
                uids = data[0].split()[-40:]

        for uid in uids:
            typ, data = imap.uid("fetch", uid, "(RFC822)")
            if typ != "OK" or not data or not data[0]:
                continue
            raw = data[0][1]
            if not isinstance(raw, (bytes, bytearray)):
                continue
            msg = email.message_from_bytes(raw)
            subject = _decode_header(msg.get("Subject"))
            in_reply_to = _decode_header(msg.get("In-Reply-To"))
            references = _decode_header(msg.get("References"))
            body = _get_body_text(msg)
            cmds = parse_commands_from_body(body)
            # Accept if subject matches OR body has commands (reply may strip subject nuance)
            if not (_subject_matches(subject) or cmds):
                # Threading hint: In-Reply-To / References alone not enough without cmds
                if not cmds and "cart check" not in (in_reply_to + references).lower():
                    continue
                if not cmds:
                    continue
            if not cmds:
                print(f"Skip uid={uid.decode()} subject={subject!r} (no commands)")
                continue
            results.append(
                {
                    "uid": uid.decode() if isinstance(uid, bytes) else str(uid),
                    "subject": subject,
                    "body": body,
                    "commands": cmds,
                    "message_id": _decode_header(msg.get("Message-ID")),
                }
            )
            if mark_seen:
                imap.uid("store", uid, "+FLAGS", "(\\Seen)")
            if add_label:
                # Gmail label via store X-GM-LABELS if available; ignore failures
                try:
                    imap.uid("store", uid, "+X-GM-LABELS", "(cart-check-processed)")
                except imaplib.IMAP4.error:
                    pass
        imap.logout()
    return results


def update_index_html(asin: str, *, prefer: str | None = None, drop_prefer: bool = False,
                      skip_undercut: bool | None = None, exclude_id: str | None = None) -> bool:
    """
    Update product object in index.html if pin fields live there.
    Returns True if file changed.
    """
    if not INDEX_HTML.is_file():
        return False
    html = INDEX_HTML.read_text(encoding="utf-8")
    # Find product window starting at this asin
    m = re.search(rf'asin:\s*"{re.escape(asin)}"', html, re.I)
    if not m:
        return False
    start = m.start()
    # Window until next asin or reasonable bound
    next_m = re.search(r'asin:\s*"', html[m.end() :])
    end = m.end() + (next_m.start() if next_m else min(3500, len(html) - m.end()))
    window = html[start:end]
    original = window
    changed = False

    def set_bool_field(src: str, field: str, value: bool) -> str:
        nonlocal changed
        pat = re.compile(rf'{field}:\s*(true|false)', re.I)
        if pat.search(src):
            new_src, n = pat.subn(f"{field}: {str(value).lower()}", src, count=1)
            if n:
                changed = True
            return new_src
        if value:
            # Insert after asin line
            new_src, n = re.subn(
                rf'(asin:\s*"{re.escape(asin)}"\s*,)',
                rf'\1\n    {field}: true,',
                src,
                count=1,
                flags=re.I,
            )
            if n:
                changed = True
            return new_src
        return src

    def set_string_field(src: str, field: str, value: str) -> str:
        nonlocal changed
        pat = re.compile(rf'{field}:\s*"([^"]*)"')
        if pat.search(src):
            new_src, n = pat.subn(f'{field}: "{value}"', src, count=1)
            if n:
                changed = True
            return new_src
        new_src, n = re.subn(
            rf'(asin:\s*"{re.escape(asin)}"\s*,)',
            rf'\1\n    {field}: "{value}",',
            src,
            count=1,
            flags=re.I,
        )
        if n:
            changed = True
        return new_src

    def remove_field(src: str, field: str) -> str:
        nonlocal changed
        pat = re.compile(rf'\s*{field}:\s*"[^"]*"\s*,?', re.M)
        new_src, n = pat.subn("", src, count=1)
        if n:
            changed = True
        return new_src

    def add_exclude(src: str, item_id: str) -> str:
        nonlocal changed
        # ebayExcludeItemIds: ["a", "b"] or missing
        pat = re.compile(r'ebayExcludeItemIds:\s*\[([^\]]*)\]', re.S)
        m2 = pat.search(src)
        if m2:
            inner = m2.group(1)
            existing = re.findall(r'"([^"]+)"', inner)
            if item_id in existing or any(
                normalize_item_id(x) == normalize_item_id(item_id) for x in existing
            ):
                return src
            existing.append(item_id)
            new_inner = ", ".join(f'"{x}"' for x in existing)
            changed = True
            return src[: m2.start(1)] + new_inner + src[m2.end(1) :]
        new_src, n = re.subn(
            rf'(asin:\s*"{re.escape(asin)}"\s*,)',
            rf'\1\n    ebayExcludeItemIds: ["{item_id}"],',
            src,
            count=1,
            flags=re.I,
        )
        if n:
            changed = True
        return new_src

    # Only mutate if pin-related fields already exist OR we're explicitly setting them
    has_pin_fields = bool(
        re.search(
            r"ebayPreferItemId|ebayExcludeItemIds|ebaySkipPinUndercut|ebayPinItemId",
            window,
        )
    )
    # Pins live in catalog.json; only touch index.html when pin fields already exist there.
    if not has_pin_fields:
        return False

    if drop_prefer:
        window = remove_field(window, "ebayPreferItemId")
        window = remove_field(window, "ebayPinItemId")
    elif prefer is not None:
        if re.search(r"ebayPreferItemId|ebayPinItemId", window) or True:
            if re.search(r"ebayPreferItemId:", window):
                window = set_string_field(window, "ebayPreferItemId", prefer)
            elif re.search(r"ebayPinItemId:", window):
                window = set_string_field(window, "ebayPinItemId", prefer)
            else:
                window = set_string_field(window, "ebayPreferItemId", prefer)

    if skip_undercut is True:
        window = set_bool_field(window, "ebaySkipPinUndercut", True)
    if exclude_id:
        window = add_exclude(window, exclude_id)

    if not changed or window == original:
        return False
    html = html[:start] + window + html[end:]
    INDEX_HTML.write_text(html, encoding="utf-8")
    return True


def apply_command(
    action: str,
    asin: str,
    catalog: list[dict[str, Any]],
    alt_map: dict[str, str],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    row = find_row(catalog, asin)
    if row is None:
        return {
            "action": action,
            "asin": asin,
            "ok": False,
            "error": "ASIN not found in catalog",
        }

    result: dict[str, Any] = {
        "action": action,
        "asin": asin,
        "ok": True,
        "before": {
            "ebayPreferItemId": row.get("ebayPreferItemId"),
            "ebaySkipPinUndercut": row.get("ebaySkipPinUndercut"),
            "ebayExcludeItemIds": list(row.get("ebayExcludeItemIds") or []),
        },
    }

    if action == "KEEP":
        plan = f"KEEP {asin}: set ebaySkipPinUndercut=true (pin stays {row.get('ebayPreferItemId')!r})"
        print(plan)
        result["plan"] = plan
        if not dry_run:
            row["ebaySkipPinUndercut"] = True
            update_index_html(asin, skip_undercut=True)
        return result

    if action == "DROP":
        plan = f"DROP {asin}: remove ebayPreferItemId (was {row.get('ebayPreferItemId')!r})"
        print(plan)
        result["plan"] = plan
        if not dry_run:
            row.pop("ebayPreferItemId", None)
            row.pop("ebayPinItemId", None)
            update_index_html(asin, drop_prefer=True)
        return result

    alt = alt_map.get(asin.upper()) or alt_map.get(asin)
    if action in ("SWITCH", "EXCLUDE") and not alt:
        err = f"{action} {asin}: no resolved alternate item id — refusing"
        print(err, file=sys.stderr)
        return {
            "action": action,
            "asin": asin,
            "ok": False,
            "error": "no resolved alternate item id",
        }

    if action == "SWITCH":
        pin_form = catalog_pin_form(alt)  # type: ignore[arg-type]
        plan = (
            f"SWITCH {asin}: ebayPreferItemId "
            f"{row.get('ebayPreferItemId')!r} → {pin_form!r} "
            f"({_ebay_itm_url(pin_form)})"
        )
        print(plan)
        result["plan"] = plan
        result["altItemId"] = pin_form
        if not dry_run:
            row["ebayPreferItemId"] = pin_form
            # Switching implies we care about undercuts again unless KEEP was also sent
            update_index_html(asin, prefer=pin_form)
        return result

    if action == "EXCLUDE":
        pin_form = catalog_pin_form(alt)  # type: ignore[arg-type]
        excl = list(row.get("ebayExcludeItemIds") or [])
        if not any(normalize_item_id(x) == normalize_item_id(pin_form) for x in excl):
            excl.append(pin_form)
        plan = (
            f"EXCLUDE {asin}: keep pin {row.get('ebayPreferItemId')!r}; "
            f"ebayExcludeItemIds += {pin_form!r}"
        )
        print(plan)
        result["plan"] = plan
        result["altItemId"] = pin_form
        if not dry_run:
            row["ebayExcludeItemIds"] = excl
            update_index_html(asin, exclude_id=pin_form)
        return result

    return {"action": action, "asin": asin, "ok": False, "error": "unknown action"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply cart-check email reply commands")
    parser.add_argument("--dry-run", action="store_true", help="Print actions only")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=None,
        help="Local snapshot JSON (else fetch live if needed)",
    )
    parser.add_argument(
        "--no-imap",
        action="store_true",
        help="Do not check IMAP; use --commands-file or stdin",
    )
    parser.add_argument(
        "--commands-file",
        type=Path,
        default=None,
        help="Text file of KEEP/SWITCH/EXCLUDE/DROP lines (skip IMAP)",
    )
    parser.add_argument(
        "--commands",
        default="",
        help="Inline commands separated by newlines/semicolons",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("PRICE_API_URL") or PRICE_API_DEFAULT,
    )
    parser.add_argument(
        "--no-mark-seen",
        action="store_true",
        help="Do not mark processed emails as Seen",
    )
    args = parser.parse_args(argv)

    if not CATALOG_SRC.is_file() and not CATALOG_ROOT.is_file():
        print("ERROR: no catalog.json found", file=sys.stderr)
        return 1

    catalog_path = CATALOG_SRC if CATALOG_SRC.is_file() else CATALOG_ROOT
    catalog = load_catalog(catalog_path)

    report: dict[str, Any] | None = None
    if args.report.is_file():
        try:
            report = load_json(args.report)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARN: bad report {args.report}: {exc}", file=sys.stderr)

    snapshot: dict[str, Any] | None = None
    if args.snapshot and args.snapshot.is_file():
        try:
            snapshot = load_json(args.snapshot)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARN: bad snapshot: {exc}", file=sys.stderr)
    elif (AUDIT_DIR / "snapshot.json").is_file():
        try:
            snapshot = load_json(AUDIT_DIR / "snapshot.json")
        except (OSError, json.JSONDecodeError):
            snapshot = None

    # Collect commands
    all_cmds: list[tuple[str, str]] = []
    mail_meta: list[dict[str, Any]] = []

    if args.commands_file and args.commands_file.is_file():
        all_cmds.extend(parse_commands_from_body(args.commands_file.read_text(encoding="utf-8-sig")))
    if args.commands.strip():
        all_cmds.extend(parse_commands_from_body(args.commands.replace(";", "\n")))

    if not args.no_imap and not args.commands_file and not args.commands.strip():
        user = (os.environ.get("GMAIL_USER") or "").strip()
        password = (os.environ.get("GMAIL_APP_PASSWORD") or "").strip()
        if not user or not password:
            print(
                "ERROR: GMAIL_USER and GMAIL_APP_PASSWORD required for IMAP "
                "(or pass --commands / --commands-file / --no-imap)",
                file=sys.stderr,
            )
            return 1
        try:
            mail_meta = fetch_imap_replies(
                user,
                password,
                mark_seen=not args.no_mark_seen and not args.dry_run,
                add_label=not args.dry_run,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: IMAP failed: {exc}", file=sys.stderr)
            return 1
        for m in mail_meta:
            all_cmds.extend(m["commands"])

    # Dedupe preserving order (last action per ASIN wins if conflicting — keep sequence)
    # Actually: apply in order; later commands can override earlier for same ASIN
    if not all_cmds:
        print("no replies")
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        log = {
            "ok": True,
            "applied": 0,
            "message": "no replies",
            "at": _now_iso(),
            "dryRun": args.dry_run,
        }
        REPLY_LOG.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")
        return 0

    # Ensure we can resolve alts for SWITCH/EXCLUDE
    need_alt = any(a in ("SWITCH", "EXCLUDE") for a, _ in all_cmds)
    if need_alt and snapshot is None:
        snapshot = fetch_snapshot(args.base_url)

    alt_map = build_alt_map(report, snapshot, catalog)
    print(f"Commands to apply: {len(all_cmds)}")
    for action, asin in all_cmds:
        print(f"  {action} {asin}  alt={alt_map.get(asin.upper()) or '(none)'}")

    applied: list[dict[str, Any]] = []
    hard_fail = False
    for action, asin in all_cmds:
        res = apply_command(action, asin, catalog, alt_map, dry_run=args.dry_run)
        applied.append(res)
        if not res.get("ok"):
            # Missing alt is a soft skip for that command; unknown ASIN soft
            if res.get("error") == "no resolved alternate item id":
                continue
            if res.get("error") == "ASIN not found in catalog":
                continue

    ok_count = sum(1 for r in applied if r.get("ok"))
    if ok_count and not args.dry_run:
        save_catalog(catalog_path, catalog)
        # Keep root + src in sync (extract_catalog pattern)
        other = CATALOG_ROOT if catalog_path.resolve() != CATALOG_ROOT.resolve() else CATALOG_SRC
        if other.parent.is_dir():
            save_catalog(other, catalog)
            print(f"Wrote {catalog_path} and {other}")
        else:
            print(f"Wrote {catalog_path}")

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    log = {
        "ok": True,
        "applied": ok_count,
        "dryRun": args.dry_run,
        "at": _now_iso(),
        "mail": [
            {"uid": m.get("uid"), "subject": m.get("subject"), "commands": m.get("commands")}
            for m in mail_meta
        ],
        "actions": applied,
        "failed": [r for r in applied if not r.get("ok")],
    }
    REPLY_LOG.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {REPLY_LOG}")

    if ok_count == 0 and any(not r.get("ok") for r in applied):
        # All commands failed — not a hard IMAP failure, exit 0 with message
        print("No commands applied successfully")
        return 0
    if hard_fail:
        return 1
    print(f"Applied {ok_count} command(s)" + (" (dry-run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
