#!/usr/bin/env python3
"""Generate crawlable static pages for AI Pick Vault (GitHub Pages).

Reads PRODUCT_CATALOG + CATEGORIES + affiliate constants from index.html, then writes:
  - robots.txt
  - sitemap.xml
  - picks/<slug>/index.html          (one per product)
  - picks/category/<id>/index.html   (one per category)
  - updates the STATIC_PICKS markers inside index.html

Usage (from repo root):
  python scripts/generate_static_pages.py
"""
from __future__ import annotations

import html
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
SITE = "https://aipickvault.com"
TODAY = date.today().isoformat()

# Markers maintained in index.html
MARK_START = "<!-- STATIC_PICKS_START -->"
MARK_END = "<!-- STATIC_PICKS_END -->"
NOSCRIPT_START = "<!-- STATIC_PICKS_NOSCRIPT_START -->"
NOSCRIPT_END = "<!-- STATIC_PICKS_NOSCRIPT_END -->"


def unescape_js_string(s: str) -> str:
    try:
        return bytes(s, "utf-8").decode("unicode_escape")
    except Exception:
        return (
            s.replace(r"\"", '"')
            .replace(r"\'", "'")
            .replace(r"\n", "\n")
            .replace(r"\\", "\\")
        )


def extract_array_literal(text: str, const_name: str) -> str | None:
    m = re.search(rf"const\s+{re.escape(const_name)}\s*=\s*\[", text)
    if not m:
        return None
    i = text.find("[", m.end() - 1)
    depth = 0
    for j in range(i, len(text)):
        c = text[j]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return text[i : j + 1]
    return None


def split_top_level_objects(array_text: str) -> list[str]:
    """Split a JS array literal into top-level `{...}` object strings."""
    objs: list[str] = []
    depth = 0
    start = None
    in_str = False
    quote = ""
    esc = False
    for j, c in enumerate(array_text):
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == quote:
                in_str = False
            continue
        if c in ('"', "'"):
            in_str = True
            quote = c
            continue
        if c == "{":
            if depth == 0:
                start = j
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start is not None:
                objs.append(array_text[start : j + 1])
                start = None
    return objs


def field_str(obj: str, key: str) -> str | None:
    m = re.search(rf'{key}\s*:\s*"((?:\\.|[^"\\])*)"', obj)
    if not m:
        return None
    return unescape_js_string(m.group(1))


def field_num(obj: str, key: str) -> float | None:
    m = re.search(rf"{key}\s*:\s*([0-9]+(?:\.[0-9]+)?|null)", obj)
    if not m or m.group(1) == "null":
        return None
    return float(m.group(1))


def field_bool(obj: str, key: str) -> bool:
    m = re.search(rf"{key}\s*:\s*(true|false)", obj)
    return bool(m and m.group(1) == "true")


def field_str_list(obj: str, key: str) -> list[str]:
    m = re.search(rf"{key}\s*:\s*\[([^\]]*)\]", obj)
    if not m:
        return []
    return re.findall(r'"((?:\\.|[^"\\])*)"', m.group(1))


def slugify(name: str, asin: str, used: set[str]) -> str:
    base = name.lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    base = re.sub(r"-{2,}", "-", base)
    if not base:
        base = asin.lower()
    slug = base
    if slug in used:
        slug = f"{base}-{asin.lower()}"
    n = 2
    while slug in used:
        slug = f"{base}-{asin.lower()}-{n}"
        n += 1
    used.add(slug)
    return slug


def parse_affiliate(text: str) -> dict:
    tags = re.findall(r'(?m)^\s*const AMAZON_TAG = "([^"]*)";', text)
    amazon_tag = tags[-1] if tags else ""
    campid = re.search(r'(?m)^\s*const EBAY_CAMPID = "([^"]*)";', text)
    mkrid = re.search(r'(?m)^\s*const EBAY_MKRID = "([^"]*)";', text)
    toolid = re.search(r'(?m)^\s*const EBAY_TOOLID = "([^"]*)";', text)
    return {
        "amazon_tag": amazon_tag,
        "ebay_campid": campid.group(1) if campid else "",
        "ebay_mkrid": mkrid.group(1) if mkrid else "711-53200-19255-0",
        "ebay_toolid": toolid.group(1) if toolid else "10001",
    }


def amazon_url(asin: str, tag: str) -> str:
    url = f"https://www.amazon.com/dp/{asin}"
    if tag.strip():
        url += f"?tag={quote(tag.strip())}"
    return url


def ebay_url(product_name: str, custom_id: str, aff: dict) -> str:
    q = quote(product_name.strip() or "deals")
    url = (
        f"https://www.ebay.com/sch/i.html?_nkw={q}"
        "&_sacat=0&LH_TitleDesc=0&LH_ItemCondition=1000&LH_FS=1"
        "&LH_PrefLoc=1&LH_BIN=1&_sop=15&rt=nc"
    )
    campid = (aff.get("ebay_campid") or "").strip()
    if campid:
        url += (
            "&mkcid=1"
            f"&mkrid={quote(aff['ebay_mkrid'])}"
            "&siteid=0"
            f"&campid={quote(campid)}"
            f"&customid={quote(str(custom_id)[:256])}"
            f"&toolid={quote(aff['ebay_toolid'])}"
            "&mkevt=1"
        )
    return url


def parse_products(text: str) -> list[dict]:
    arr = extract_array_literal(text, "PRODUCT_CATALOG")
    if not arr:
        raise SystemExit("PRODUCT_CATALOG not found in index.html")
    used: set[str] = set()
    products: list[dict] = []
    for obj in split_top_level_objects(arr):
        asin = field_str(obj, "asin")
        name = field_str(obj, "name")
        if not asin or not name:
            continue
        compare_amz = None
        m = re.search(r"compare\s*:\s*\{([^}]*)\}", obj)
        if m:
            am = re.search(r"amazon\s*:\s*([0-9.]+|null)", m.group(1))
            if am and am.group(1) != "null":
                compare_amz = float(am.group(1))
        price = field_num(obj, "price")
        products.append(
            {
                "asin": asin,
                "name": name,
                "sub": field_str(obj, "sub") or "",
                "blurb": field_str(obj, "blurb") or "",
                "scoreWhy": field_str(obj, "scoreWhy") or "",
                "why": field_str(obj, "why") or "",
                "img": field_str(obj, "img") or "",
                "badge": field_str(obj, "badge") or "",
                "score": field_str(obj, "score") or "",
                "categories": field_str_list(obj, "categories"),
                "featured": field_bool(obj, "featured"),
                "amazonOos": field_bool(obj, "amazonOos")
                or field_bool(obj, "amazonSoldOut"),
                "brandLabel": field_for_brand(obj),
                "brandAffiliateUrl": field_str(obj, "brandAffiliateUrl") or "",
                "price": price,
                "compare_amazon": compare_amz,
                "ebayQ": field_str(obj, "ebayQ") or name,
                "slug": slugify(name, asin, used),
            }
        )
    return products


def field_for_brand(obj: str) -> str:
    return field_str(obj, "brandLabel") or ""


def parse_categories(text: str) -> list[dict]:
    arr = extract_array_literal(text, "CATEGORIES")
    if not arr:
        return []
    cats: list[dict] = []
    for obj in split_top_level_objects(arr):
        cid = field_str(obj, "id")
        name = field_str(obj, "name")
        if not cid or not name:
            continue
        cats.append(
            {
                "id": cid,
                "name": name,
                "blurb": field_str(obj, "blurb") or "",
                "icon": field_str(obj, "icon") or "fa-box",
            }
        )
    return cats


def page_shell(
    title: str,
    description: str,
    canonical: str,
    body: str,
    json_ld: dict | None = None,
    extra_head: str = "",
) -> str:
    ld = ""
    if json_ld:
        ld = (
            '<script type="application/ld+json">\n'
            + json.dumps(json_ld, ensure_ascii=False, indent=2)
            + "\n</script>\n"
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content="{html.escape(description, quote=True)}" />
  <meta name="theme-color" content="#0f172a" />
  <meta name="robots" content="index,follow" />
  <link rel="canonical" href="{html.escape(canonical, quote=True)}" />
  <meta property="og:title" content="{html.escape(title, quote=True)}" />
  <meta property="og:description" content="{html.escape(description, quote=True)}" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="{html.escape(canonical, quote=True)}" />
  <title>{html.escape(title)}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" />
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600&display=swap');
    body {{ font-family: Inter, system-ui, sans-serif; }}
    .logo-font {{ font-family: 'Space Grotesk', Inter, sans-serif; font-weight: 600; }}
  </style>
  {extra_head}{ld}</head>
<body class="bg-slate-950 text-slate-200 min-h-screen">
{body}
</body>
</html>
"""


def disclosure_block() -> str:
    return """
    <aside class="mt-10 rounded-2xl border border-slate-800 bg-slate-900/70 p-5 text-sm text-slate-400 leading-relaxed">
      <p class="font-semibold text-slate-200 mb-2">Affiliate disclosure</p>
      <p>
        AI Pick Vault participates in the Amazon Services LLC Associates Program and the eBay Partner Network.
        As an Amazon Associate and eBay Partner Network member, I earn from qualifying purchases at no extra cost to you.
        Links on this page may be tracked affiliate links. See the
        <a class="text-sky-400 hover:text-sky-300" href="/#disclosures">full disclosure</a>.
      </p>
    </aside>"""


def nav_header(active: str = "") -> str:
    return f"""
  <header class="border-b border-slate-800 bg-slate-950/90 backdrop-blur sticky top-0 z-20">
    <div class="max-w-4xl mx-auto px-5 py-4 flex items-center justify-between gap-4">
      <a href="/" class="logo-font text-white text-lg tracking-tight hover:text-sky-300 transition-colors">
        AI Pick Vault
      </a>
      <nav class="flex items-center gap-4 text-sm text-slate-400">
        <a href="/#featured" class="hover:text-sky-400">Featured</a>
        <a href="/#categories" class="hover:text-sky-400 {'text-sky-400' if active=='cats' else ''}">Categories</a>
        <a href="/#disclosures" class="hover:text-sky-400">Disclosures</a>
        <a href="/contact.html" class="hover:text-sky-400">Contact</a>
      </nav>
    </div>
  </header>"""


def img_src(img: str) -> str:
    if not img:
        return ""
    if img.startswith("http://") or img.startswith("https://") or img.startswith("/"):
        return img
    return "/" + img.lstrip("./")


def product_json_ld(p: dict, canonical: str) -> dict:
    data: dict = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": p["name"],
        "sku": p["asin"],
        "mpn": p["asin"],
        "url": canonical,
        "description": (p["scoreWhy"] or p["blurb"] or p["name"])[:5000],
        "brand": {"@type": "Brand", "name": p["name"].split(" ")[0]},
    }
    img = img_src(p["img"])
    if img:
        data["image"] = SITE + img if img.startswith("/") else img
    # Use baked-in catalog snapshot price only (never invent). Omit if missing.
    price = p.get("compare_amazon") if p.get("compare_amazon") is not None else p.get("price")
    if price is not None and float(price) > 0:
        offer: dict = {
            "@type": "Offer",
            "url": amazon_url(p["asin"], ""),  # filled below with tag by caller? keep product URL
            "priceCurrency": "USD",
            "price": f"{float(price):.2f}",
            "availability": "https://schema.org/OutOfStock"
            if p.get("amazonOos")
            else "https://schema.org/InStock",
            "seller": {"@type": "Organization", "name": "Amazon"},
        }
        data["offers"] = offer
    return data


def render_product_page(p: dict, cats_by_id: dict, aff: dict) -> str:
    canonical = f"{SITE}/picks/{p['slug']}/"
    why = p["scoreWhy"] or p["why"] or p["blurb"] or "Curated pick from AI Pick Vault."
    desc = f"{p['name']} — {p['blurb'] or why}"[:300]
    amz = amazon_url(p["asin"], aff["amazon_tag"])
    ebay = ebay_url(p["ebayQ"] or p["name"], p["asin"], aff)
    cat_links = []
    for cid in p["categories"]:
        c = cats_by_id.get(cid)
        label = c["name"] if c else cid
        cat_links.append(
            f'<a class="text-sky-400 hover:text-sky-300" href="/picks/category/{html.escape(cid)}/">{html.escape(label)}</a>'
        )
    cats_html = " · ".join(cat_links) if cat_links else "Uncategorized"
    img = img_src(p["img"])
    img_html = ""
    if img:
        img_html = f"""
      <div class="rounded-3xl border border-slate-800 bg-slate-900 overflow-hidden mb-8">
        <img src="{html.escape(img)}" alt="{html.escape(p['name'])}" class="w-full max-h-[420px] object-contain bg-slate-950 p-6" loading="lazy" />
      </div>"""
    badge = ""
    if p["badge"]:
        badge = f'<span class="inline-flex px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wide bg-rose-500/20 text-rose-300 border border-rose-500/30">{html.escape(p["badge"])}</span>'
    score = ""
    if p["score"]:
        score = f'<span class="text-sm text-slate-400">Grok score <strong class="text-sky-300">{html.escape(p["score"])}/10</strong></span>'
    brand_btn = ""
    if p["brandAffiliateUrl"].startswith("https://"):
        label = p["brandLabel"] or "Official store"
        brand_btn = f"""
        <a href="{html.escape(p['brandAffiliateUrl'])}" target="_blank" rel="nofollow sponsored noopener"
           class="inline-flex items-center justify-center gap-2 rounded-2xl border border-slate-600 bg-slate-900 px-5 py-3 font-semibold text-white hover:border-sky-500 transition-colors">
          Shop {html.escape(label)}
        </a>"""
    amz_label = "Amazon sold out" if p["amazonOos"] else "Check Amazon"
    # JSON-LD offer URL should be the affiliate Amazon URL when we have a price
    ld = product_json_ld(p, canonical)
    if "offers" in ld:
        ld["offers"]["url"] = amz

    body = f"""
{nav_header()}
  <main class="max-w-4xl mx-auto px-5 py-10 md:py-14">
    <p class="text-sm text-slate-500 mb-4">
      <a href="/" class="hover:text-sky-400">Home</a>
      <span class="mx-1.5">/</span>
      <a href="/#categories" class="hover:text-sky-400">Picks</a>
      <span class="mx-1.5">/</span>
      <span class="text-slate-300">{html.escape(p['name'])}</span>
    </p>
    {img_html}
    <div class="flex flex-wrap items-center gap-3 mb-3">{badge}{score}</div>
    <h1 class="text-3xl md:text-4xl font-extrabold text-white tracking-tight mb-2">{html.escape(p['name'])}</h1>
    <p class="text-slate-400 mb-2">{html.escape(p['sub'])}</p>
    <p class="text-sm text-slate-500 mb-6">Category: {cats_html}</p>
    <p class="text-slate-200 text-lg leading-relaxed mb-4">{html.escape(p['blurb'])}</p>
    <div class="rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 p-6 mb-8">
      <h2 class="text-sm font-bold uppercase tracking-[0.14em] text-sky-400 mb-2">Why this pick</h2>
      <p class="text-slate-300 leading-relaxed whitespace-pre-wrap">{html.escape(why)}</p>
    </div>
    <div class="flex flex-col sm:flex-row gap-3 mb-4">
      <a href="{html.escape(amz)}" target="_blank" rel="nofollow sponsored noopener"
         class="inline-flex items-center justify-center gap-2 rounded-2xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold px-5 py-3 transition-colors">
        <i class="fa-brands fa-amazon"></i> {html.escape(amz_label)}
      </a>
      <a href="{html.escape(ebay)}" target="_blank" rel="nofollow sponsored noopener"
         class="inline-flex items-center justify-center gap-2 rounded-2xl bg-blue-600 hover:bg-blue-500 text-white font-bold px-5 py-3 transition-colors">
        <i class="fa-solid fa-gavel"></i> Check eBay
      </a>
      {brand_btn}
    </div>
    <p class="text-xs text-slate-500 mb-8">ASIN: {html.escape(p['asin'])} · Prices move — compare live on Amazon and eBay.</p>
    {disclosure_block()}
    <p class="mt-8 text-sm"><a class="text-sky-400 hover:text-sky-300" href="/">&larr; Back to all picks</a></p>
  </main>
"""
    return page_shell(
        title=f"{p['name']} · AI Pick Vault",
        description=desc,
        canonical=canonical,
        body=body,
        json_ld=ld,
    )


def render_category_page(cat: dict, products: list[dict], aff: dict) -> str:
    canonical = f"{SITE}/picks/category/{cat['id']}/"
    items = [p for p in products if cat["id"] in p["categories"]]
    lis = []
    for p in items:
        lis.append(
            f"""<li class="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 hover:border-sky-500/40 transition-colors">
  <a href="/picks/{html.escape(p['slug'])}/" class="block">
    <h2 class="text-lg font-bold text-white mb-1 hover:text-sky-300">{html.escape(p['name'])}</h2>
    <p class="text-sm text-slate-400 line-clamp-3">{html.escape(p['blurb'] or p['scoreWhy'][:180])}</p>
  </a>
  <div class="mt-3 flex flex-wrap gap-3 text-sm">
    <a class="text-amber-400 hover:text-amber-300" href="{html.escape(amazon_url(p['asin'], aff['amazon_tag']))}" target="_blank" rel="nofollow sponsored noopener">Amazon</a>
    <a class="text-blue-400 hover:text-blue-300" href="{html.escape(ebay_url(p['ebayQ'] or p['name'], p['asin'], aff))}" target="_blank" rel="nofollow sponsored noopener">eBay</a>
  </div>
</li>"""
        )
    body = f"""
{nav_header('cats')}
  <main class="max-w-4xl mx-auto px-5 py-10 md:py-14">
    <p class="text-sm text-slate-500 mb-4">
      <a href="/" class="hover:text-sky-400">Home</a>
      <span class="mx-1.5">/</span>
      <span class="text-slate-300">{html.escape(cat['name'])}</span>
    </p>
    <div class="uppercase tracking-[2px] text-xs font-semibold text-sky-400 mb-2">CATEGORY</div>
    <h1 class="text-3xl md:text-4xl font-extrabold text-white tracking-tight mb-3">{html.escape(cat['name'])}</h1>
    <p class="text-slate-400 mb-8">{html.escape(cat['blurb'])} · {len(items)} pick{'s' if len(items)!=1 else ''}.</p>
    <ul class="grid gap-4 list-none p-0 m-0">
      {''.join(lis) if lis else '<li class="text-slate-500">No products in this category yet.</li>'}
    </ul>
    {disclosure_block()}
    <p class="mt-8 text-sm"><a class="text-sky-400 hover:text-sky-300" href="/">&larr; Back to all picks</a></p>
  </main>
"""
    return page_shell(
        title=f"{cat['name']} picks · AI Pick Vault",
        description=f"{cat['name']} gear picks on AI Pick Vault — {cat['blurb']}",
        canonical=canonical,
        body=body,
    )


def write_robots() -> None:
    (ROOT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\nSitemap: https://aipickvault.com/sitemap.xml\n",
        encoding="utf-8",
    )


def write_sitemap(products: list[dict], categories: list[dict]) -> None:
    urls = [f"{SITE}/"]
    for c in categories:
        urls.append(f"{SITE}/picks/category/{c['id']}/")
    for p in products:
        urls.append(f"{SITE}/picks/{p['slug']}/")
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for i, u in enumerate(urls):
        # homepage slightly higher priority
        pri = "1.0" if i == 0 else ("0.7" if "/category/" in u else "0.8")
        parts.append("  <url>")
        parts.append(f"    <loc>{html.escape(u)}</loc>")
        parts.append(f"    <lastmod>{TODAY}</lastmod>")
        parts.append(f"    <changefreq>daily</changefreq>")
        parts.append(f"    <priority>{pri}</priority>")
        parts.append("  </url>")
    parts.append("</urlset>\n")
    (ROOT / "sitemap.xml").write_text("\n".join(parts), encoding="utf-8")


def static_picks_html(products: list[dict], categories: list[dict]) -> str:
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for p in products:
        key = p["categories"][0] if p["categories"] else "_other"
        by_cat[key].append(p)
    cat_name = {c["id"]: c["name"] for c in categories}
    blocks = []
    for c in categories:
        items = by_cat.get(c["id"], [])
        if not items:
            continue
        links = "\n".join(
            f'          <li><a class="text-sky-400 hover:text-sky-300" href="/picks/{html.escape(p["slug"])}/">{html.escape(p["name"])}</a></li>'
            for p in items
        )
        blocks.append(
            f"""      <div>
        <h3 class="text-sm font-bold uppercase tracking-wide text-slate-300 mb-2">
          <a class="hover:text-sky-400" href="/picks/category/{html.escape(c['id'])}/">{html.escape(c['name'])}</a>
        </h3>
        <ul class="space-y-1.5 text-sm text-slate-400">
{links}
        </ul>
      </div>"""
        )
    other = by_cat.get("_other", [])
    if other:
        links = "\n".join(
            f'          <li><a class="text-sky-400 hover:text-sky-300" href="/picks/{html.escape(p["slug"])}/">{html.escape(p["name"])}</a></li>'
            for p in other
        )
        blocks.append(
            f"""      <div>
        <h3 class="text-sm font-bold uppercase tracking-wide text-slate-300 mb-2">Other</h3>
        <ul class="space-y-1.5 text-sm text-slate-400">
{links}
        </ul>
      </div>"""
        )
    return f"""{MARK_START}
    <section id="all-picks" class="max-w-7xl mx-auto px-6 py-14 border-t border-slate-800" aria-labelledby="all-picks-heading">
      <div class="mb-8">
        <div class="uppercase tracking-[2px] text-xs font-semibold text-sky-400 mb-1">FULL VAULT</div>
        <h2 id="all-picks-heading" class="section-header text-2xl md:text-3xl font-bold text-white">All curated picks</h2>
        <p class="text-slate-400 mt-2 text-sm max-w-2xl">
          Static product pages for every ASIN in the vault — open a pick for why it made the cut, plus Amazon and eBay links.
        </p>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-8">
{''.join(blocks)}
      </div>
    </section>
{MARK_END}"""


def noscript_html(products: list[dict]) -> str:
    links = "\n".join(
        f'    <li><a href="/picks/{html.escape(p["slug"])}/">{html.escape(p["name"])}</a></li>'
        for p in products
    )
    return f"""{NOSCRIPT_START}
  <noscript>
    <div class="max-w-7xl mx-auto px-6 py-8 text-slate-300">
      <h2>All AI Pick Vault products</h2>
      <ul>
{links}
      </ul>
      <p><a href="/sitemap.xml">Sitemap</a> · <a href="/robots.txt">robots.txt</a></p>
    </div>
  </noscript>
{NOSCRIPT_END}"""


def upsert_marked_block(text: str, start: str, end: str, block: str, insert_before: str) -> str:
    if start in text and end in text:
        before = text.split(start, 1)[0]
        after = text.split(end, 1)[1]
        return before + block + after
    # insert before a landmark
    idx = text.find(insert_before)
    if idx < 0:
        raise SystemExit(f"Could not find insertion landmark: {insert_before}")
    return text[:idx] + block + "\n\n" + text[idx:]


def update_index(products: list[dict], categories: list[dict]) -> None:
    text = INDEX.read_text(encoding="utf-8")
    text = upsert_marked_block(
        text,
        MARK_START,
        MARK_END,
        static_picks_html(products, categories),
        '<!-- Affiliate / FTC disclosures',
    )
    # noscript near end of body for crawlers that skip JS grids
    text = upsert_marked_block(
        text,
        NOSCRIPT_START,
        NOSCRIPT_END,
        noscript_html(products),
        "</body>",
    )
    INDEX.write_text(text, encoding="utf-8")


def clean_picks_dir() -> None:
    picks = ROOT / "picks"
    if picks.exists():
        # Remove generated product/category pages only
        for path in picks.rglob("index.html"):
            path.unlink()
        # prune empty dirs
        for path in sorted(picks.rglob("*"), reverse=True):
            if path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass


def main() -> int:
    if not INDEX.is_file():
        print(f"ERROR: missing {INDEX}", file=sys.stderr)
        return 1
    text = INDEX.read_text(encoding="utf-8")
    aff = parse_affiliate(text)
    products = parse_products(text)
    categories = parse_categories(text)
    if not products:
        print("ERROR: no products parsed", file=sys.stderr)
        return 1

    cats_by_id = {c["id"]: c for c in categories}
    clean_picks_dir()

    for p in products:
        out = ROOT / "picks" / p["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_product_page(p, cats_by_id, aff), encoding="utf-8")

    for c in categories:
        out = ROOT / "picks" / "category" / c["id"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_category_page(c, products, aff), encoding="utf-8")

    write_robots()
    write_sitemap(products, categories)
    update_index(products, categories)

    # sidecar map for debugging / future JS linking
    map_path = ROOT / "picks" / "catalog-slugs.json"
    map_path.write_text(
        json.dumps(
            [{"asin": p["asin"], "slug": p["slug"], "name": p["name"]} for p in products],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Generated {len(products)} product pages, {len(categories)} category pages")
    print(f"Amazon tag: {aff['amazon_tag']!r}  eBay campid: {aff['ebay_campid']!r}")
    print("Wrote robots.txt, sitemap.xml, picks/*, and updated index.html static lists")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
