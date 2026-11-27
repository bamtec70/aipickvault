#!/usr/bin/env python3
"""Fail if the Ko-fi donation link drops out of AI Pick Vault layouts or pages.

Run from the repo root:
  python3 tests/test_kofi_links.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KOFI = "https://ko-fi.com/bamtx"
GOAL = "Help Kellie help seniors"
SKIP_HTML = {
    "td-player.html",  # We The People Press player, not an AI Pick Vault page
}

# Source-of-truth templates. A rewrite that drops the partial must fail even
# before HTML is regenerated.
LAYOUT_FILES = [
    "scripts/kofi.py",
    "scripts/build_local_ai.py",
    "scripts/site_footer_tailwind.html",
    "scripts/generate_static_pages.py",
]

# Pages that should show the mid-page support block (or the same goal copy).
SUPPORT_BLOCK_PREFIXES = (
    "local-ai/",
    "ai-for-beginners/",
    "picks/",
    "check-my-pc/",
    "about/",
    "index.html",
    "contact.html",
)


def html_pages() -> list[Path]:
    pages = []
    for p in ROOT.rglob("*.html"):
        if ".git" in p.parts or p.parts[0] == "scripts" or p.name in SKIP_HTML:
            # allow scripts/site_footer_tailwind.html via LAYOUT_FILES only
            if "scripts" in p.parts:
                continue
            if p.name in SKIP_HTML:
                continue
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith("scripts/"):
            continue
        pages.append(p)
    return sorted(pages)


def has_header_chrome(text: str) -> bool:
    low = text.lower()
    return "<header" in low or '<nav class="' in low or "<nav>" in low


def kofi_in_header(text: str) -> bool:
    low = text.lower()
    for tag, close in (("<header", "</header>"), ("<nav", "</nav>")):
        start = 0
        while True:
            i = low.find(tag, start)
            if i < 0:
                break
            j = low.find(close, i)
            chunk = text[i : (j + len(close) if j >= 0 else i + 2000)]
            if KOFI in chunk:
                return True
            start = i + 1
    return False


def needs_support_block(rel: str) -> bool:
    if rel == "deals.html":
        return True
    return any(rel == p or rel.startswith(p) for p in SUPPORT_BLOCK_PREFIXES)


def main() -> int:
    errors: list[str] = []

    for rel in LAYOUT_FILES:
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"missing layout file: {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        if rel in ("scripts/kofi.py", "scripts/site_footer_tailwind.html"):
            if KOFI not in text:
                errors.append(f"layout missing {KOFI}: {rel}")
            if GOAL not in text:
                errors.append(f"layout missing goal {GOAL!r}: {rel}")
        elif KOFI not in text and "KOFI_" not in text:
            errors.append(f"layout missing Ko-fi include or {KOFI}: {rel}")

    # head() and foot() in the shared builder must both contain the link
    builder = (ROOT / "scripts/build_local_ai.py").read_text(encoding="utf-8")
    if "KOFI_NAV" not in builder:
        errors.append("scripts/build_local_ai.py head/nav no longer includes KOFI_NAV")
    if "KOFI_BLOCK" not in builder or "KOFI_FOOTER_INNER" not in builder:
        errors.append("scripts/build_local_ai.py foot() no longer includes the Ko-fi block/footer")

    pages = html_pages()
    if len(pages) < 20:
        errors.append(f"expected many HTML pages, found {len(pages)}")

    for path in pages:
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        if KOFI not in text:
            errors.append(f"page missing {KOFI}: {rel}")
            continue
        if has_header_chrome(text) and not kofi_in_header(text):
            errors.append(f"header/nav missing {KOFI}: {rel}")
        if needs_support_block(rel) and GOAL not in text:
            errors.append(f"support block missing {GOAL!r}: {rel}")
        if "You decide what to trust." in text:
            errors.append(f"WTP-only line appeared on AI Pick Vault page: {rel}")

    if errors:
        print("FAIL: Ko-fi donation link check")
        for e in errors:
            print(" -", e)
        print(f"{len(errors)} issue(s), {len(pages)} pages scanned")
        return 1
    print(f"PASS: {KOFI} present in {len(LAYOUT_FILES)} layouts and {len(pages)} pages")
    print(f"PASS: {GOAL!r} present on guides, picks, hubs and footer layouts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
