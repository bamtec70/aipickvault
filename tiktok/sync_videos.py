#!/usr/bin/env python3
"""
Sync @aipickvault TikTok posts into videos.json + local cover images.

Usage:
  python tiktok/sync_videos.py
  python tiktok/sync_videos.py --max 6
  python tiktok/sync_videos.py --username aipickvault

The site reads tiktok/videos.json for the "From the Vault" section.
Run locally after posting, or let GitHub Actions run it on a schedule.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIKTOK_DIR = ROOT / "tiktok"
COVERS_DIR = TIKTOK_DIR / "covers"
OUT_JSON = TIKTOK_DIR / "videos.json"
DEFAULT_USERNAME = "aipickvault"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


def fetch_text(url: str, referer: str | None = None) -> str:
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/json,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", "replace")


def fetch_bytes(url: str, referer: str | None = None) -> bytes:
    headers = {
        "User-Agent": UA,
        "Accept": "image/avif,image/webp,image/*,*/*",
    }
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def extract_video_list(html: str) -> list[dict]:
    """Parse TikTok creator embed HTML for videoList."""
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)
    for raw in scripts:
        if "videoList" not in raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        # Frontity-style embed payload
        source = (data.get("source") or {}).get("data") or {}
        for key, page in source.items():
            if not isinstance(page, dict):
                continue
            videos = page.get("videoList")
            if isinstance(videos, list) and videos:
                return videos
    # Fallback: pull video ids from /@user/video/ID links
    ids = re.findall(r"/@[\w.]+/video/(\d{15,})", html)
    return [{"id": i, "desc": "", "coverUrl": ""} for i in dict.fromkeys(ids)]


def title_from_desc(desc: str, fallback: str) -> str:
    if not desc:
        return fallback
    # Drop hashtags / mentions for the card title
    text = re.sub(r"[#@]\S+", " ", desc)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Prefer a short hook ending in ! or ?
    m = re.match(r"^(.{10,72}?)[!?]", text)
    if m:
        text = m.group(1).strip()
    else:
        for sep in (". ", " — ", " - ", "\n"):
            if sep in text:
                text = text.split(sep, 1)[0].strip()
                break
    # Soft length cap for the card (keep product names readable)
    if len(text) > 68:
        cut = text[:65].rsplit(" ", 1)[0]
        text = (cut or text[:65]).rstrip(".,;:") + "…"
    return text or fallback


def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return (s[:40] or "video").strip("-")


def sync(username: str, max_videos: int, download_covers: bool) -> dict:
    embed_url = f"https://www.tiktok.com/embed/@{username}"
    print(f"Fetching {embed_url} …")
    try:
        html = fetch_text(embed_url)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"TikTok embed HTTP {e.code}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise SystemExit(f"TikTok embed network error: {e.reason}") from e

    raw_list = extract_video_list(html)
    if not raw_list:
        raise SystemExit(
            "No videos found in TikTok embed HTML. "
            "TikTok may have changed the page or blocked this runner."
        )

    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    videos: list[dict] = []

    for item in raw_list[:max_videos]:
        vid = str(item.get("id") or "").strip()
        if not vid:
            continue
        desc = str(item.get("desc") or "")
        title = title_from_desc(desc, f"TikTok · @{username}")
        cover_remote = (
            item.get("coverUrl")
            or item.get("originCoverUrl")
            or item.get("dynamicCoverUrl")
            or ""
        )
        cover_name = f"vault-{vid}.jpg"
        cover_path = COVERS_DIR / cover_name
        cover_rel = f"tiktok/covers/{cover_name}"

        if download_covers and cover_remote:
            if not cover_path.exists() or cover_path.stat().st_size < 1000:
                try:
                    blob = fetch_bytes(
                        cover_remote,
                        referer=f"https://www.tiktok.com/@{username}",
                    )
                    cover_path.write_bytes(blob)
                    print(f"  cover {cover_name} ({len(blob)} bytes)")
                except Exception as err:  # noqa: BLE001 — keep going
                    print(f"  warn: cover download failed for {vid}: {err}")
            else:
                print(f"  cover {cover_name} (cached)")

        # Prefer local cover when present; else remote (may expire)
        if cover_path.exists() and cover_path.stat().st_size > 1000:
            cover = cover_rel
        else:
            cover = cover_remote or "images/dewalt.jpg"

        videos.append(
            {
                "id": vid,
                "title": title,
                "url": f"https://www.tiktok.com/@{username}/video/{vid}",
                "cover": cover,
                "desc": desc[:280],
            }
        )

    payload = {
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "username": username,
        "profileUrl": f"https://www.tiktok.com/@{username}",
        "maxDisplay": max_videos,
        "videos": videos,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_JSON.relative_to(ROOT)} ({len(videos)} videos)")
    return payload


def main() -> int:
    p = argparse.ArgumentParser(description="Sync TikTok videos for From the Vault")
    p.add_argument("--username", default=DEFAULT_USERNAME)
    p.add_argument("--max", type=int, default=6, help="Max videos to keep (default 6)")
    p.add_argument(
        "--no-covers",
        action="store_true",
        help="Skip downloading cover images",
    )
    args = p.parse_args()
    sync(args.username, max(1, args.max), download_covers=not args.no_covers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
