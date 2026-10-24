#!/usr/bin/env python3
"""Rebuild sitemap.xml and llms.txt from the HTML pages actually in the repo.

- Includes only indexable pages (skips meta robots noindex and meta-refresh redirects).
- <lastmod> = date of the last git commit that touched the file (today if uncommitted).
- Run after any build script:  python3 scripts/build_seo_files.py
"""
import html, re, subprocess, datetime, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://aipickvault.com"
SKIP_DIRS = ("tiktok/", "videos/", "docs/", "ebay-worker/", "node_modules/", ".git/", "Price Change Reports/")
TODAY = datetime.date.today().isoformat()

def url_for(rel):
    u = "/" + rel
    return u[:-len("index.html")] if u.endswith("/index.html") or u == "/index.html" else u

def lastmod(rel):
    dirty = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if dirty:
        return TODAY
    out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", rel], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return out or TODAY

def meta(s, name):
    m = re.search(r'<meta\s+name="%s"\s+content="([^"]*)"' % name, s, re.I)
    return html.unescape(m.group(1)) if m else ""

def pages():
    out = []
    for p in sorted(ROOT.rglob("*.html")):
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith(SKIP_DIRS):
            continue
        s = p.read_text(encoding="utf-8", errors="replace")
        if re.search(r'<meta[^>]+name="robots"[^>]+noindex', s, re.I) or re.search(r'http-equiv="refresh"', s, re.I):
            continue
        t = re.search(r"<title>(.*?)</title>", s, re.S)
        title = html.unescape(t.group(1).strip()) if t else rel
        title = re.sub(r"\s*[|·]\s*AI Pick Vault.*$", "", title)
        out.append(dict(rel=rel, url=url_for(rel), title=title, desc=meta(s, "description"), mod=lastmod(rel), videos=videos(s)))
    return out

def videos(s):
    """VideoObject JSON-LD blocks on the page (for <video:video> sitemap entries)."""
    out = []
    for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S):
        if '"VideoObject"' not in b: continue
        try: d = json.loads(b)
        except ValueError: continue
        if d.get("@type") == "VideoObject" and d.get("embedUrl"): out.append(d)
    return out

def video_xml(v):
    e = lambda x: html.escape(str(x), quote=True)
    thumb = v["thumbnailUrl"][0] if isinstance(v["thumbnailUrl"], list) else v["thumbnailUrl"]
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", v.get("duration", ""))
    secs = sum(int(x or 0) * k for x, k in zip(m.groups(), (3600, 60, 1))) if m else 0
    out = ["    <video:video>", f"      <video:thumbnail_loc>{e(thumb)}</video:thumbnail_loc>", f"      <video:title>{e(v['name'])}</video:title>",
           f"      <video:description>{e(v['description'])}</video:description>",
           f"      <video:content_loc>{e(v['contentUrl'])}</video:content_loc>" if v.get("contentUrl") else None,
           f"      <video:player_loc>{e(v['embedUrl'])}</video:player_loc>",
           f"      <video:duration>{secs}</video:duration>" if secs else None,
           f"      <video:publication_date>{e(v['uploadDate'])}</video:publication_date>" if v.get("uploadDate") else None,
           "      <video:family_friendly>yes</video:family_friendly>", "    </video:video>"]
    return [x for x in out if x]

def order(pg):
    u = pg["url"]
    if u == "/": return (0, u)
    if u in ("/local-ai/", "/ai-for-beginners/"): return (1, u)
    if u.startswith(("/local-ai/", "/ai-for-beginners/")): return (2, u)
    if u.startswith("/picks/category/"): return (4, u)
    if u.startswith("/picks/"): return (5, u)
    return (3, u)

def prio(u):
    if u == "/": return "1.0"
    if u in ("/local-ai/", "/ai-for-beginners/"): return "0.9"
    if u.startswith(("/local-ai/", "/ai-for-beginners/")): return "0.8"
    if u.startswith("/picks/"): return "0.5"
    return "0.3"

def write_sitemap(ps):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">']
    for p in ps:
        lines += ["  <url>", f"    <loc>{html.escape(SITE + p['url'])}</loc>", f"    <lastmod>{p['mod']}</lastmod>",
                  f"    <priority>{prio(p['url'])}</priority>"]
        for v in p.get("videos", []): lines += video_xml(v)
        lines.append("  </url>")
    lines.append("</urlset>\n")
    (ROOT / "sitemap.xml").write_text("\n".join(lines), encoding="utf-8")

def write_llms(ps):
    def sec(name, pred, with_desc=True):
        rows = [p for p in ps if pred(p["url"])]
        if not rows: return []
        return ["", f"## {name}"] + [f"- [{p['title']}]({SITE}{p['url']})" + (f": {p['desc']}" if with_desc and p["desc"] else "") for p in rows]
    out = ["# AI Pick Vault", "",
           "> Plain-words guides for running AI on your own Windows PC on a budget (Ollama, RAM/VRAM, budget GPUs, mini PCs, setup) "
           "and a gentle AI for Beginners section. Amazon Associate site (tag wethepeopl0b9-20); we do not list prices, check the retailer for current pricing."]
    out += sec("Start here", lambda u: u == "/")
    out += sec("AI for Beginners", lambda u: u.startswith("/ai-for-beginners/"))
    out += sec("Local AI guides", lambda u: u.startswith("/local-ai/"))
    out += sec("Gear pick categories", lambda u: u.startswith("/picks/category/"))
    out += sec("Gear picks (older catalog)", lambda u: u.startswith("/picks/") and "/category/" not in u, with_desc=False)
    out += sec("Other", lambda u: not u.startswith(("/picks/", "/local-ai/", "/ai-for-beginners/")) and u != "/")
    out += [f"- [Sitemap]({SITE}/sitemap.xml)", ""]
    (ROOT / "llms.txt").write_text("\n".join(out), encoding="utf-8")

if __name__ == "__main__":
    ps = sorted(pages(), key=order)
    write_sitemap(ps); write_llms(ps)
    print(f"sitemap.xml + llms.txt: {len(ps)} indexable pages")
