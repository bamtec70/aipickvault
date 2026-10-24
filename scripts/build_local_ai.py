#!/usr/bin/env python3
"""Rebuild /local-ai/ guide pages into the conversion layout (quick pick, compare table,
sticky CTA, video, trust box). Idempotent: reads the <article> body from each guide."""
import json, re, html
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
TAG = "wethepeopl0b9-20"
REL = 'target="_blank" rel="nofollow sponsored noopener"'
def amz(q): return f"https://www.amazon.com/s?k={q.replace(' ','+')}&amp;tag={TAG}"
def btn(q, label="Check price on Amazon", cls="btn"): return f'<a class="{cls}" href="{amz(q)}" {REL}>{label}</a>'

GUIDES = {
 "best-budget-gpu-for-ollama.html": dict(
  title="Best Budget GPU for Ollama (2026): RTX 3060 12GB vs 16GB vs 3090",
  desc="Best budget GPU for Ollama and local LLMs on a Windows PC: RTX 3060 12GB, RTX 5060 Ti 16GB, RTX 4060 Ti 16GB and used RTX 3090 compared by VRAM and what models each runs.",
  short="Best budget GPU for Ollama", cat="Hardware",
  picks=[("Best value","NVIDIA RTX 3060 12GB","Cheapest card that runs 8B to 14B models fully on GPU.","RTX 3060 12GB graphics card"),
         ("Best new card","NVIDIA RTX 5060 Ti 16GB","16GB of fast memory. Fits 14B and 20B models.","RTX 5060 Ti 16GB graphics card"),
         ("Big models","NVIDIA RTX 3090 24GB","24GB VRAM for 30B class models. Needs a 750W+ PSU.","RTX 3090 24GB graphics card")],
  cols=["Card","VRAM","Runs well","Power"],
  rows=[("RTX 3060 12GB","12GB","8B to 14B","170W","RTX 3060 12GB graphics card"),
        ("RTX 5060 Ti 16GB","16GB","14B to 20B","180W","RTX 5060 Ti 16GB graphics card"),
        ("RTX 4060 Ti 16GB","16GB","14B to 20B (slower)","165W","RTX 4060 Ti 16GB graphics card"),
        ("RTX 3090 24GB (used)","24GB","30B to 32B","350W","RTX 3090 24GB graphics card")],
  video="best-budget-gpu-for-ollama", vcap="40 second version: which GPU to buy for local AI, and the one mistake to avoid."),
 "best-mini-pc-for-local-ai.html": dict(
  title="Best Mini PC for Local AI and Ollama (2026): 3 Picks Compared",
  desc="Best mini PC for running Ollama and local AI at home: Beelink SER8, GMKtec EVO-X2 and Mac mini compared on memory, model size, noise and who should skip each.",
  short="Best mini PC for local AI", cat="Hardware",
  picks=[("Best value","Beelink SER8 (Ryzen 7 8845HS)","Upgradeable DDR5. Runs 7B to 14B models quietly 24/7.","Beelink SER8 8845HS mini PC"),
         ("Big models","GMKtec EVO-X2 (Ryzen AI Max+ 395)","Up to 128GB unified memory for 30B to 70B models.","GMKtec EVO-X2 Ryzen AI Max+ 395 128GB"),
         ("Quietest","Apple Mac mini","Easy, silent, strong unified memory. Not Windows.","Mac mini M6 32GB")],
  cols=["Mini PC","Memory","Best for","OS"],
  rows=[("Beelink SER8","Upgradeable DDR5","7B to 14B, budget","Windows","Beelink SER8 8845HS mini PC"),
        ("GMKtec EVO-X2","Up to 128GB unified","30B to 70B","Windows","GMKtec EVO-X2 Ryzen AI Max+ 395 128GB"),
        ("Mac mini","Unified, pick 32GB+","Quiet desk setup","macOS","Mac mini M6 32GB")],
  video="best-mini-pc-for-local-ai", vcap="40 second version: what to look for in a mini PC for local AI."),
 "how-much-ram-vram-for-ollama.html": dict(
  title="How Much RAM and VRAM for Ollama? Model Size Chart (2026)",
  desc="How much RAM and VRAM you need for Ollama models from 4B to 70B, with a simple size chart, the 0.6GB per billion rule and the cheapest upgrade for a Windows PC.",
  short="How much RAM and VRAM for Ollama", cat="Guide",
  picks=[("Cheapest upgrade","32GB DDR5 SO-DIMM kit","For laptops and mini PCs with 16GB. Unlocks 14B models.","32GB DDR5 SODIMM kit 2x16GB"),
         ("Desktop DDR5","32GB DDR5 desktop kit (2x16GB)","Newer desktops. Check your board's QVL.","32GB DDR5 desktop RAM kit 2x16GB"),
         ("Older desktop","32GB DDR4 3200 kit (2x16GB)","Most 2017 to 2022 desktops. Cheap and effective.","32GB DDR4 3200 desktop RAM kit 2x16GB")],
  cols=["Your memory","Model size","Example","Upgrade"],
  rows=[("16GB","7B to 8B","llama3.1:8b","32GB kit","32GB RAM kit"),
        ("32GB","14B, efficient 20B to 30B","qwen3:14b","GPU with 12GB+","RTX 3060 12GB graphics card"),
        ("12GB VRAM","8B to 14B on GPU","qwen3:14b","16GB GPU","RTX 5060 Ti 16GB graphics card"),
        ("24GB VRAM","30B to 32B on GPU","qwen3:30b","Used RTX 3090","RTX 3090 24GB graphics card")],
  video="how-much-ram-vram-for-ollama", vcap="40 second version: how much memory your AI model really needs."),
 "best-ollama-models-16gb-ram.html": dict(
  title="Best Ollama Models for 16GB RAM on Windows (and When to Upgrade)",
  desc="The best Ollama models for a Windows PC with 16GB RAM, what not to run, and the cheapest upgrades (32GB RAM, NVMe SSD, 12GB GPU) when you outgrow it.",
  short="Best Ollama models for 16GB RAM", cat="Models",
  picks=[("Best upgrade","32GB RAM kit","The cheapest jump from 8B models to 14B models.","32GB RAM kit"),
         ("Faster loads","1TB NVMe SSD","Models are big. Fast storage loads them quicker.","1TB NVMe SSD"),
         ("Real speed","RTX 3060 12GB","Moves 8B models onto the GPU for fast replies.","RTX 3060 12GB graphics card")],
  cols=["Upgrade","Why","Effect"],
  rows=[("32GB RAM kit","More room for models","14B models usable","32GB RAM kit"),
        ("1TB NVMe SSD","Space plus fast loading","Keep many models","1TB NVMe SSD"),
        ("RTX 3060 12GB","12GB VRAM","Much faster replies","RTX 3060 12GB graphics card")]),
 "budget-ai-pc-under-1000.html": dict(
  title="Budget AI PC Under $1,000 for Ollama: Build, Buy or Upgrade",
  desc="Three ways to get a budget AI PC under $1,000 for local chat and coding help: buy a 32GB mini PC, upgrade the PC you own, or add a used 12GB GPU.",
  short="Budget AI PC under $1,000", cat="Hardware",
  picks=[("Easiest","Mini PC with 32GB RAM","Plug in, install Ollama, done. Quiet and low power.","mini PC 32GB RAM"),
         ("Cheapest","Upgrade to 32GB RAM","Often the best value if your PC is under 6 years old.","32GB RAM kit"),
         ("Fastest","Add an RTX 3060 12GB","Fast replies on 8B to 14B models.","RTX 3060 12GB graphics card")],
  cols=["Path","What you buy","Good for"],
  rows=[("1. Mini PC","32GB mini PC","Quiet daily chat","mini PC 32GB RAM"),
        ("2. Upgrade","32GB RAM + 1TB NVMe","Best value","32GB RAM kit"),
        ("3. Tower + GPU","12GB GPU","Speed on 8B to 14B","RTX 3060 12GB graphics card")]),
 "install-ollama-open-webui-windows.html": dict(
  title="Install Ollama and Open WebUI on Windows (Step by Step + Fixes)",
  desc="Step by step: install Ollama and Open WebUI on Windows 10 or 11, plus fixes for port conflicts, firewall, GPU drivers and Windows Defender.",
  short="Install Ollama + Open WebUI on Windows", cat="Setup",
  picks=[("Most useful","32GB RAM kit","Stops slowdowns when the model and browser share memory.","32GB RAM kit"),
         ("Storage","1TB NVMe SSD","Model files add up fast. Keep them on fast storage.","1TB NVMe SSD"),
         ("Speed","RTX 3060 12GB","Ollama uses NVIDIA GPUs automatically.","RTX 3060 12GB graphics card")],
  cols=["Part","Why it helps install day","Get it"],
  rows=[("32GB RAM kit","Room for model plus Open WebUI","","32GB RAM kit"),
        ("1TB NVMe SSD","Space for several models","","1TB NVMe SSD"),
        ("RTX 3060 12GB","GPU acceleration","","RTX 3060 12GB graphics card")]),
}
ORDER = ["how-much-ram-vram-for-ollama.html","best-budget-gpu-for-ollama.html","best-mini-pc-for-local-ai.html",
         "budget-ai-pc-under-1000.html","best-ollama-models-16gb-ram.html","install-ollama-open-webui-windows.html"]

def svg(name):
    d = {"wrench":'<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z"/>',
         "chip":'<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
         "gpu":'<rect x="2" y="6" width="20" height="11" rx="2"/><circle cx="8" cy="11.5" r="2.5"/><circle cx="16" cy="11.5" r="2.5"/><path d="M5 17v3"/>',
         "box":'<rect x="4" y="7" width="16" height="10" rx="2"/><path d="M8 14h3"/>',
         "ram":'<rect x="2" y="7" width="20" height="9" rx="1"/><path d="M6 16v3M10 16v3M14 16v3M18 16v3M6 10h2M11 10h2M16 10h2"/>',
         "spark":'<path d="M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z"/>',
         "tool":'<path d="M4 20h16M6 16l6-12 6 12"/><path d="M9 11h6"/>',
         "down":'<path d="M12 3v12M7 10l5 5 5-5M4 20h16"/>',
         "money":'<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="3"/>'}[name]
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{d}</svg>'
ICON = {"how-much-ram-vram-for-ollama.html":"ram","best-budget-gpu-for-ollama.html":"gpu","best-mini-pc-for-local-ai.html":"box",
        "budget-ai-pc-under-1000.html":"money","best-ollama-models-16gb-ram.html":"spark","install-ollama-open-webui-windows.html":"down"}

TRUST = """<div class="trust"><div class="ic">""" + svg("wrench") + """</div><div><p><strong>Who picks these:</strong> Blake, the guy behind AI Pick Vault. 47 years of hands-on fixing things and troubleshooting PCs. These picks come from what actually fits in memory and what is least likely to cause headaches on a normal Windows PC, not from lab benchmarks.</p><p class="meta">No brand pays for placement. Amazon links are affiliate links.</p></div></div>"""
DISC = '<p class="disc">Affiliate note: as an Amazon Associate I earn from qualifying purchases, at no extra cost to you. Prices change constantly, so we do not list them. Click through for the current price.</p>'

def head(title, desc, canon, ld, og_img=None):
    img = f'\n<meta property="og:image" content="{og_img}">' if og_img else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{canon}">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta name="theme-color" content="#0f172a">
<meta property="og:type" content="article">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{canon}">
<meta property="og:site_name" content="AI Pick Vault">{img}
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/assets/site.css">
{ld}
</head>
<body>
<header class="nav"><div class="wrap"><a class="logo" href="/">AI <span>Pick</span> Vault</a><nav><a href="/" class="hide-m">Home</a><a href="/local-ai/" class="on">Local AI</a><a href="/local-ai/#start">Start here</a></nav></div></header>
"""

def foot(sticky_label, sticky_q):
    return f"""<footer><div class="wrap"><p><strong>Affiliate disclosure:</strong> As an Amazon Associate I earn from qualifying purchases. AI Pick Vault may also earn commissions from other retailers via affiliate links, at no extra cost to you.</p>
<p>AI Pick Vault: run AI on your own Windows PC on a budget. Picks by Blake.</p>
<p><a href="/">Home</a><a href="/local-ai/">Local AI hub</a><a href="/contact.html">Contact</a><a href="/llms.txt">llms.txt</a></p></div></footer>
<div class="sticky"><span>{html.escape(sticky_label)}</span>{btn(sticky_q,"Check price on Amazon","btn sm")}</div>
</body>
</html>
"""

def quick(g):
    rows = "".join(f'<div class="row"><div><span class="badge">{html.escape(b)}</span><b>{html.escape(n)}</b><small>{html.escape(w)}</small></div>{btn(q)}</div>' for b,n,w,q in g["picks"])
    return f'<section class="quick" aria-label="Quick picks"><p class="lab">Quick pick: short on time?</p><div class="qp">{rows}</div></section>'

def table(g):
    cols = g["cols"]
    th = "".join(f"<th>{c}</th>" for c in cols) + ("<th>Price</th>" if cols[-1] != "Get it" else "")
    if cols[-1] == "Get it": th = "".join(f"<th>{c}</th>" for c in cols)
    trs = ""
    for r in g["rows"]:
        cells = list(r[:-1]); q = r[-1]
        if cols[-1] == "Get it": cells = cells[:-1]
        tds = f"<td><b>{html.escape(cells[0])}</b></td>" + "".join(f"<td>{html.escape(c)}</td>" for c in cells[1:])
        trs += f"<tr>{tds}<td>{btn(q,'Check price','btn sm')}</td></tr>"
    return f'<div class="sec-h" id="compare" style="margin-top:36px"><p class="kicker">Side by side</p><h2>Comparison at a glance</h2></div><div class="tbl"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>'

def video(g):
    v = g.get("video")
    if not v: return ""
    return f'<div class="vid"><video controls preload="none" playsinline poster="/videos/{v}.jpg" width="360" height="640"><source src="/videos/{v}.mp4" type="video/mp4"></video><div><p class="kicker">Watch</p><p><strong>{html.escape(g["vcap"])}</strong></p><p class="meta">Prefer reading? The full guide is below.</p></div></div>'

def clean_article(a):
    a = re.sub(r'<p><strong>(Quick pick|Short answer):</strong>', r'<p><strong>\1:</strong>', a)
    a = a.replace(" \u2014 ", ", ").replace("\u2014", ", ")
    a = re.sub(r'class="[^"]*\b(text-sm text-slate-[45]00[^"]*)"', 'class="text-sm"', a)
    def fix(m):
        t = m.group(0)
        t = re.sub(r'\s(target|rel)="[^"]*"', "", t)
        return t[:-1] + f" {REL}>"
    a = re.sub(r'<a\s[^>]*href="https://www\.amazon\.com[^"]*"[^>]*>', fix, a)
    return a

def ld_blocks(s):
    out=[]
    for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S):
        out.append(b.strip())
    return out

def build_guide(fn, g):
    p = ROOT/"local-ai"/fn
    s = p.read_text(encoding="utf-8")
    art = re.search(r'<article[^>]*>(.*?)</article>', s, re.S).group(1)
    upd = re.search(r'Updated ([A-Z][a-z]{2} \d{1,2}, \d{4})', s)
    canon = f"https://aipickvault.com/local-ai/{fn}"
    lds = [b for b in ld_blocks(s) if '"ItemList"' not in b]
    items = [{"@type":"ListItem","position":i+1,"name":n,"url":canon+"#compare"} for i,(_,n,_,_) in enumerate(g["picks"])]
    lds.append(json.dumps({"@context":"https://schema.org","@type":"ItemList","name":g["short"]+": quick picks","itemListElement":items}))
    # refresh headline/description inside Article schema
    lds = [re.sub(r'"headline": "[^"]*"', '"headline": '+json.dumps(g["title"]), b) for b in lds]
    ld = "\n".join(f'<script type="application/ld+json">{b}</script>' for b in lds)
    h1 = html.unescape(re.search(r'<h1[^>]*>(.*?)</h1>', s, re.S).group(1)).strip()
    v = g.get("video")
    out = head(g["title"]+" | AI Pick Vault", g["desc"], canon, ld, f"https://aipickvault.com/videos/{v}.jpg" if v else None)
    others = "".join(f'<li><a href="/local-ai/{o}">{html.escape(GUIDES[o]["short"])}</a></li>' for o in ORDER if o != fn)
    out += f"""<section class="hero sm"><div class="wrap narrow">
<p class="kicker"><a href="/local-ai/">Local AI</a> &middot; {g['cat']}</p>
<h1>{html.escape(h1)}</h1>
<p class="meta">Updated {upd.group(1) if upd else 'Oct 23, 2026'} &middot; By Blake, AI Pick Vault &middot; <a href="#compare">Jump to comparison</a></p>
</div></section>
<main class="wrap narrow">
{DISC}
{quick(g)}
{table(g)}
{video(g)}
<article>
{clean_article(art)}
</article>
<section class="quick" aria-label="Ready to buy"><p class="lab">Ready to buy?</p><div class="qp">{"".join(f'<div class="row"><div><b>{html.escape(n)}</b><small>{html.escape(w)}</small></div>{btn(q)}</div>' for _,n,w,q in g["picks"])}</div></section>
{TRUST}
<aside class="more"><p class="kicker">Keep reading</p><ul><li><a href="/local-ai/">&larr; Local AI hub and Start here path</a></li>{others}</ul></aside>
</main>
"""
    out += foot(g["picks"][0][1], g["picks"][0][3])
    p.write_text(out, encoding="utf-8")

if __name__ == "__main__":
    for fn, g in GUIDES.items(): build_guide(fn, g)
    print("built", len(GUIDES))
