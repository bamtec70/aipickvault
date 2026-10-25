#!/usr/bin/env python3
"""Rebuild /local-ai/ guide pages into the conversion layout (quick pick, compare table,
sticky CTA, video, trust box). Idempotent: reads the <article> body from each guide."""
import json, re, html, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from yt_video import yt_embed, video_ld
ROOT = Path(__file__).resolve().parent.parent
TAG = "wethepeopl0b9-20"
REL = 'target="_blank" rel="nofollow sponsored noopener"'
def amz(q): return f"https://www.amazon.com/s?k={q.replace(' ','+')}&amp;tag={TAG}"
def btn(q, label="Check price on Amazon", cls="btn"): return f'<a class="{cls}" href="{amz(q)}" {REL}>{label}</a>'

GUIDES = {
 "best-budget-gpu-for-ollama.html": dict(
  title="Best Budget GPU for Ollama (2026): RTX 3060 12GB vs 16GB vs 3090",
  seo="Best Budget GPU for Ollama (2026)",
  desc="Best budget GPU for Ollama on a Windows PC: RTX 3060 12GB, RTX 5060 Ti 16GB, RTX 4060 Ti 16GB and a used RTX 3090 compared by VRAM and models.",
  short="Best budget GPU for Ollama", cat="Hardware",
  yt=140, picks=[("Best value","NVIDIA RTX 3060 12GB","Cheapest card that runs 8B to 14B models fully on GPU.","RTX 3060 12GB graphics card"),
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
  seo="Best Mini PC for Local AI and Ollama (2026)",
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
  seo="How Much RAM and VRAM for Ollama? (2026 Chart)",
  desc="How much RAM and VRAM you need for Ollama models from 4B to 70B, with a simple size chart, the 0.6GB per billion rule and the cheapest upgrade for a Windows PC.",
  short="How much RAM and VRAM for Ollama", cat="Guide",
  yt=41, picks=[("Cheapest upgrade","32GB DDR5 SO-DIMM kit","For laptops and mini PCs with 16GB. Unlocks 14B models.","32GB DDR5 SODIMM kit 2x16GB"),
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
  seo="Best Ollama Models for 16GB RAM on Windows",
  desc="The best Ollama models for a Windows PC with 16GB RAM, what not to run, and the cheapest upgrades (32GB RAM, NVMe SSD, 12GB GPU) when you outgrow it.",
  short="Best Ollama models for 16GB RAM", cat="Models",
  picks=[("Best upgrade","32GB RAM kit (DDR4 or DDR5)","Cheapest jump from 8B to 14B models. Match your PC type below.","32GB DDR5 desktop RAM kit 2x16GB"),
         ("Faster loads","1TB NVMe SSD","Models are big. Fast storage loads them quicker.","1TB NVMe SSD"),
         ("Real speed","RTX 3060 12GB","Moves 8B models onto the GPU for fast replies.","RTX 3060 12GB graphics card")],
  cols=["Upgrade","Why","Effect"],
  rows=[("32GB RAM kit","More room for models","14B models usable","32GB RAM kit"),
        ("1TB NVMe SSD","Space plus fast loading","Keep many models","1TB NVMe SSD"),
        ("RTX 3060 12GB","12GB VRAM","Much faster replies","RTX 3060 12GB graphics card")]),
 "budget-ai-pc-under-1000.html": dict(
  title="Budget AI PC Under $1,000 for Ollama: Build, Buy or Upgrade",
  seo="Budget AI PC Under $1,000 for Ollama",
  desc="Three ways to get a budget AI PC under $1,000 for local chat and coding help: buy a 32GB mini PC, upgrade the PC you own, or add a used 12GB GPU.",
  short="Budget AI PC under $1,000", cat="Hardware",
  yt=233, picks=[("Easiest","Mini PC with 32GB RAM","Plug in, install Ollama, done. Quiet and low power.","mini PC 32GB RAM"),
         ("Cheapest","Upgrade to 32GB RAM","Best value if your PC is under 6 years old. Check DDR4 or DDR5 below.","32GB DDR4 3200 desktop RAM kit 2x16GB"),
         ("Fastest","Add an RTX 3060 12GB","Fast replies on 8B to 14B models.","RTX 3060 12GB graphics card")],
  cols=["Path","What you buy","Good for"],
  rows=[("1. Mini PC","32GB mini PC","Quiet daily chat","mini PC 32GB RAM"),
        ("2. Upgrade","32GB RAM + 1TB NVMe","Best value","32GB RAM kit"),
        ("3. Tower + GPU","12GB GPU","Speed on 8B to 14B","RTX 3060 12GB graphics card")]),
 "install-ollama-open-webui-windows.html": dict(
  title="Install Ollama and Open WebUI on Windows (Step by Step + Fixes)",
  seo="Install Ollama + Open WebUI on Windows",
  desc="Step by step: install Ollama and Open WebUI on Windows 10 or 11, plus fixes for port conflicts, firewall, GPU drivers and Windows Defender.",
  short="Install Ollama + Open WebUI on Windows", cat="Setup",
  picks=[("Most useful","32GB RAM kit","Stops slowdowns when the model and browser share memory.","32GB RAM kit"),
         ("Storage","1TB NVMe SSD","Model files add up fast. Keep them on fast storage.","1TB NVMe SSD"),
         ("Speed","RTX 3060 12GB","Ollama uses NVIDIA GPUs automatically.","RTX 3060 12GB graphics card")],
  cols=["Part","Why it helps install day","Get it"],
  rows=[("32GB RAM kit","Room for model plus Open WebUI","","32GB RAM kit"),
        ("1TB NVMe SSD","Space for several models","","1TB NVMe SSD"),
        ("RTX 3060 12GB","GPU acceleration","","RTX 3060 12GB graphics card")]),
"local-ai-vs-cloud-ai-cost.html": dict(
  title="Local AI vs Cloud AI Cost (2026): Break-Even Calculator vs ChatGPT, Claude, Gemini and Grok",
  seo="Local AI vs Cloud AI Cost: Break-Even Calculator",
  desc="Is local AI worth it? ChatGPT, Claude, Gemini and SuperGrok plans vs a one-time GPU upgrade, plus electricity cost and a break-even calculator.",
  short="Is local AI worth it? Cost vs cloud", cat="Cost",
  yt=0, picks=[("Best payback","NVIDIA RTX 3060 12GB","Cheapest card that runs 8B to 14B models fast. Breaks even fastest.","RTX 3060 12GB graphics card"),
         ("More headroom","NVIDIA RTX 5060 Ti 16GB","16GB for 14B to 20B models. Longer payback, more capable.","RTX 5060 Ti 16GB graphics card"),
         ("Cheapest start","32GB RAM kit","Run 14B models slowly on the PC you own for very little.","32GB RAM kit")],
  cols=["Hardware path","One-time cost","Runs well"],
  rows=[("RTX 3060 12GB upgrade","Check price","8B to 14B fast","RTX 3060 12GB graphics card"),
        ("RTX 5060 Ti 16GB upgrade","Check price","14B to 20B fast","RTX 5060 Ti 16GB graphics card"),
        ("32GB RAM only","Check price","14B, slow","32GB RAM kit")]),
 "small-business-ai-server.html": dict(title="Private AI for Small Business: One Server, Every Desk",
 seo="Private AI for Small Business: One Server, Every Desk",
 desc="Run private AI for your whole office on one local server. No per-seat fees, data stays in the building. GPU VRAM tiers, Ollama plus Open WebUI setup and security basics.",
 short="Private AI for small business", cat="Business",
 picks=[("Starter","NVIDIA RTX 3060 12GB","1 to 4 light users on 8B to 14B models.","RTX 3060 12GB graphics card"),
  ("Best for most offices","NVIDIA RTX 5060 Ti 16GB","5 to 10 users on 14B to 20B models.","RTX 5060 Ti 16GB graphics card"),
  ("Power office","NVIDIA RTX 3090 24GB","10+ users or smarter 30B class models. Needs a 750W+ PSU.","RTX 3090 24GB graphics card")],
 cols=["Tier","VRAM","Office size","Runs well"],
 rows=[("Starter","12GB","1 to 4 users","8B to 14B","RTX 3060 12GB graphics card"),
  ("Sweet spot","16GB","5 to 10 users","14B to 20B","RTX 5060 Ti 16GB graphics card"),
  ("Power","24GB","10+ users","30B to 32B","RTX 3090 24GB graphics card"),
  ("Server RAM","32GB to 64GB","Any","Room for models and apps","64GB DDR5 desktop RAM kit 2x32GB"),
  ("Battery backup","UPS","Any","Rides out power flickers","UPS battery backup 1500VA")])
}
ORDER = ["local-ai-vs-cloud-ai-cost.html","how-much-ram-vram-for-ollama.html","best-budget-gpu-for-ollama.html","best-mini-pc-for-local-ai.html",
         "budget-ai-pc-under-1000.html","best-ollama-models-16gb-ram.html","install-ollama-open-webui-windows.html","small-business-ai-server.html"]

def svg(name):
    d = {"wrench":'<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z"/>',
         "chip":'<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
         "gpu":'<rect x="2" y="6" width="20" height="11" rx="2"/><circle cx="8" cy="11.5" r="2.5"/><circle cx="16" cy="11.5" r="2.5"/><path d="M5 17v3"/>',
         "box":'<rect x="4" y="7" width="16" height="10" rx="2"/><path d="M8 14h3"/>',
         "ram":'<rect x="2" y="7" width="20" height="9" rx="1"/><path d="M6 16v3M10 16v3M14 16v3M18 16v3M6 10h2M11 10h2M16 10h2"/>',
         "spark":'<path d="M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z"/>',
         "tool":'<path d="M4 20h16M6 16l6-12 6 12"/><path d="M9 11h6"/>',
         "down":'<path d="M12 3v12M7 10l5 5 5-5M4 20h16"/>',
         "cloud":'<path d="M7 18h10a4 4 0 0 0 .5-8A6 6 0 0 0 6 9.5 4.3 4.3 0 0 0 7 18z"/>',
         "money":'<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="3"/>'}[name]
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{d}</svg>'
ICON = {"local-ai-vs-cloud-ai-cost.html":"cloud","how-much-ram-vram-for-ollama.html":"ram","best-budget-gpu-for-ollama.html":"gpu","best-mini-pc-for-local-ai.html":"box",
        "budget-ai-pc-under-1000.html":"money","best-ollama-models-16gb-ram.html":"spark","install-ollama-open-webui-windows.html":"down","small-business-ai-server.html":"chip"}

TRUST = """<div class="trust"><div class="ic">""" + svg("wrench") + """</div><div><p><strong>Who picks these:</strong> Blake, the guy behind AI Pick Vault. 47 years of hands-on fixing things and troubleshooting PCs. These picks come from what actually fits in memory and what is least likely to cause headaches on a normal Windows PC, not from lab benchmarks.</p><p class="meta">No brand pays for placement. Amazon links are affiliate links.</p></div></div>"""
DISC = '<p class="disc">Affiliate note: as an Amazon Associate I earn from qualifying purchases, at no extra cost to you. Prices change constantly, so we do not list them. Click through for the current price.</p>'

SUFFIX = " | AI Pick Vault"
DEFAULT_OG = "https://aipickvault.com/images/og-image.png"

def seo_title(t):
    """Keep <title> at or under ~65 chars: drop the brand suffix if it would overflow."""
    base = t[:-len(SUFFIX)] if t.endswith(SUFFIX) else t
    return base + SUFFIX if len(base + SUFFIX) <= 65 else base

def head(title, desc, canon, ld, og_img=None):
    title = seo_title(title)
    og_img = og_img or DEFAULT_OG
    img = (f'\n<meta property="og:image" content="{og_img}">'
           f'\n<meta name="twitter:title" content="{html.escape(title)}">'
           f'\n<meta name="twitter:description" content="{html.escape(desc)}">'
           f'\n<meta name="twitter:image" content="{og_img}">')
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
<header class="nav"><div class="wrap"><a class="logo" href="/">AI <span>Pick</span> Vault</a><nav><a href="/" class="hide-m">Home</a><a href="/local-ai/" class="on">Local AI</a><a href="/ai-for-beginners/">New to AI</a><a href="/check-my-pc/">Check PC</a></nav></div></header>
"""

def foot(sticky_label, sticky_q):
    return f"""<footer><div class="wrap"><p><strong>Affiliate disclosure:</strong> As an Amazon Associate I earn from qualifying purchases. AI Pick Vault may also earn commissions from other retailers via affiliate links, at no extra cost to you.</p>
<p>AI Pick Vault: run AI on your own Windows PC on a budget. Picks by Blake.</p>
<p><a href="/">Home</a><a href="/local-ai/">Local AI hub</a><a href="/contact.html">Contact</a><a href="/llms.txt">llms.txt</a></p></div></footer>
<div class="sticky"><span>{html.escape(sticky_label)}</span>{btn(sticky_q,"Check price on Amazon","btn sm")}</div>
</body>
</html>
"""

RAMBTNS = [("Desktop DDR4 (DIMM)","32GB DDR4 3200 desktop RAM kit 2x16GB"),("Desktop DDR5 (DIMM)","32GB DDR5 6000 desktop RAM kit 2x16GB"),
           ("Laptop / mini PC DDR4 (SO-DIMM)","32GB DDR4 3200 SODIMM kit 2x16GB"),("Laptop / mini PC DDR5 (SO-DIMM)","32GB DDR5 5600 SODIMM kit 2x16GB")]
def ram_btns():
    return '<div class="ram-btns">' + "".join(f'<div><b>{html.escape(l)}</b>{btn(q,"Check matched 2x16GB kit","btn sm")}</div>' for l,q in RAMBTNS) + '</div>'
RAMFIT_FULL = """<section class="ramfit" id="ram-compat"><p class="kicker">Before you buy RAM</p><h2>Will this RAM work in my PC?</h2>
<p>RAM is the cheapest local AI upgrade, but only if you buy the right type. Five checks:</p>
<ol>
<li><strong>DDR4 vs DDR5 are not interchangeable.</strong> The notch is in a different place, so a DDR5 stick will not fit a DDR4 slot. Your CPU platform and motherboard decide which one you need. AMD AM4 (Ryzen 1000 to 5000) is DDR4. AMD AM5 (Ryzen 7000 and newer) is DDR5 only. Intel 12th to 14th gen boards are either DDR4 or DDR5 depending on the board model, never both, so check yours.</li>
<li><strong>Desktop vs laptop size.</strong> Desktops use full size DIMMs. Laptops and most mini PCs use the short SO-DIMM. Same DDR type, different size, not swappable.</li>
<li><strong>Soldered memory cannot be upgraded.</strong> Many thin laptops and some mini PCs (and every Mac mini) use LPDDR5 soldered to the board. If the spec sheet says LPDDR or "onboard", there are no slots, so buy enough memory up front: 32GB minimum for local AI, 64GB or more for 30B+ models.</li>
<li><strong>Speed runs at the slowest link.</strong> RAM runs at the lowest speed supported by the CPU, the motherboard and the kit. A faster kit just downclocks, which is safe. Out of the box most kits run at a slower JEDEC default speed (for example DDR4 2133 or DDR5 4800). To get the rated speed, turn on XMP (Intel) or EXPO (AMD) in the BIOS.</li>
<li><strong>Capacity limits.</strong> Every board has a max per slot and a max total (common examples: 32GB per slot and 64GB total on older DDR4 boards, 48GB per slot and 192GB total on newer DDR5 boards; many mini PCs top out at 64GB or 96GB). The board maker's spec page lists it.</li>
</ol>
<h3>How to check what you have (2 minutes)</h3>
<ul>
<li><strong>Task Manager &gt; Performance &gt; Memory</strong> shows your total RAM, speed, slots used (for example "2 of 4") and form factor (DIMM or SO-DIMM).</li>
<li><strong>CPU-Z</strong> (free) &gt; Memory and SPD tabs show DDR4 or DDR5 and the exact sticks installed.</li>
<li><strong>msinfo32</strong> (press Windows key, type msinfo32) shows your motherboard maker and model ("BaseBoard Product"). Search that model plus "specifications" or "QVL" on the maker's site to see the supported RAM type, speed and max capacity.</li>
</ul>
<p><strong>Buy a matched kit.</strong> Mixing different kits, even the same size and speed, can cause crashes, failed boots or forced slow speeds. Replace with one matched 2 stick kit instead of adding a single stick to what you have.</p>
""" 
RAMFIT_SHORT = """<section class="ramfit" id="ram-compat"><p class="kicker">Before you buy RAM</p><h2>Will this RAM work in my PC?</h2>
<ul>
<li><strong>Match the type:</strong> DDR4 and DDR5 do not fit each other's slots. AM4 is DDR4, AM5 is DDR5, Intel 12th to 14th gen boards are one or the other.</li>
<li><strong>Match the size:</strong> desktops take DIMMs, laptops and mini PCs take SO-DIMMs. Soldered LPDDR5 cannot be upgraded at all.</li>
<li><strong>Check in 2 minutes:</strong> Task Manager &gt; Performance &gt; Memory shows speed, slots used and form factor. msinfo32 shows your board model, so you can check its spec or QVL page.</li>
<li><strong>Buy one matched kit</strong> and enable XMP or EXPO in the BIOS to get the rated speed. <a href="/local-ai/how-much-ram-vram-for-ollama.html#ram-compat">Full RAM compatibility checklist</a>.</li>
</ul>
"""
RAMFIT = {"how-much-ram-vram-for-ollama.html":"full","best-mini-pc-for-local-ai.html":"full","budget-ai-pc-under-1000.html":"full","best-ollama-models-16gb-ram.html":"short"}
def ramfit(fn):
    k = RAMFIT.get(fn)
    if not k: return ""
    return (RAMFIT_FULL if k=="full" else RAMFIT_SHORT) + ram_btns() + "</section>"

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
    return f'<figure class="vid"><video controls preload="none" playsinline poster="/videos/{v}.jpg" width="360" height="640"><source src="/videos/{v}.mp4" type="video/mp4"></video><figcaption><p class="kicker">Watch</p><p><strong>{html.escape(g["vcap"])}</strong></p><p class="meta">Prefer reading? The full guide is below.</p></figcaption></figure>'

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

CHECK_CTA = ('<a class="card feature" href="/check-my-pc/"><div class="ico">' + svg("chip") + '</div><div><p class="kicker">Free tool</p>'
             '<h3>Will AI run on my PC? Check in 1 minute.</h3><p>Our free tool looks at your computer and tells you, in plain words, what AI it can run today and the one thing to add if it needs help. Nothing to download. Nothing leaves your PC.</p>'
             '<span class="go">Check my PC &rarr;</span></div></a>')
CHECK_ON = tuple(ORDER)

def build_guide(fn, g):
    p = ROOT/"local-ai"/fn
    s = p.read_text(encoding="utf-8")
    art = re.search(r'<article[^>]*>(.*?)</article>', s, re.S).group(1).strip()
    upd = re.search(r'Updated ([A-Z][a-z]{2} \d{1,2}, \d{4})', s)
    canon = f"https://aipickvault.com/local-ai/{fn}"
    lds = [b for b in ld_blocks(s) if '"ItemList"' not in b and '"VideoObject"' not in b]
    items = [{"@type":"ListItem","position":i+1,"name":n,"url":canon+"#compare"} for i,(_,n,_,_) in enumerate(g["picks"])]
    lds.append(json.dumps({"@context":"https://schema.org","@type":"ItemList","name":g["short"]+": quick picks","itemListElement":items}))
    # refresh headline/description inside Article schema
    lds = [re.sub(r'"headline": "[^"]*"', '"headline": '+json.dumps(g["title"]), b) for b in lds]
    if "yt" in g: lds.append(json.dumps(video_ld()))
    ld = "\n".join(f'<script type="application/ld+json">{b}</script>' for b in lds)
    h1 = html.unescape(re.search(r'<h1[^>]*>(.*?)</h1>', s, re.S).group(1)).strip()
    v = g.get("video")
    out = head(g.get("seo", g["title"])+" | AI Pick Vault", g["desc"], canon, ld, f"https://aipickvault.com/videos/{v}.jpg" if v else None)
    others = "".join(f'<li><a href="/local-ai/{o}">{html.escape(GUIDES[o]["short"])}</a></li>' for o in ORDER if o != fn)
    out += f"""<section class="hero sm"><div class="wrap narrow">
<p class="kicker"><a href="/local-ai/">Local AI</a> &middot; {g['cat']}</p>
<h1>{html.escape(h1)}</h1>
<p class="meta">Updated {upd.group(1) if upd else 'Oct 23, 2026'} &middot; By Blake, AI Pick Vault &middot; <a href="#compare">Jump to comparison</a></p>
</div></section>
<main class="wrap narrow">
{DISC}
{CHECK_CTA if fn in CHECK_ON else ''}
{quick(g)}
{table(g)}
{ramfit(fn)}
{video(g)}
{yt_embed(g["yt"] or None) if "yt" in g else ""}
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
