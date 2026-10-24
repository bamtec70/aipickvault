#!/usr/bin/env python3
"""Build the conversion-focused home page (/) and Local AI hub (/local-ai/)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from build_local_ai import head, foot, btn, TRUST, DISC, GUIDES, ORDER, ROOT

TOP = [("Best value GPU","NVIDIA RTX 3060 12GB","Cheapest way to run 8B to 14B models fast on a Windows PC.","RTX 3060 12GB graphics card","/local-ai/best-budget-gpu-for-ollama.html"),
       ("Cheapest upgrade","32GB RAM kit","If you have 16GB, this is the first thing to buy. Unlocks 14B models.","32GB RAM kit","/local-ai/how-much-ram-vram-for-ollama.html"),
       ("Best new GPU","NVIDIA RTX 5060 Ti 16GB","16GB of fast memory for 14B and 20B models, with a warranty.","RTX 5060 Ti 16GB graphics card","/local-ai/best-budget-gpu-for-ollama.html"),
       ("No tower? Mini PC","Beelink SER8 mini PC","Small, quiet, upgradeable RAM. Good 24/7 Ollama box.","Beelink SER8 8845HS mini PC","/local-ai/best-mini-pc-for-local-ai.html")]

def topbox():
    rows = "".join(f'<div class="row"><div><span class="badge">{b}</span><b>{n}</b><small>{w} <a href="{g}">Why?</a></small></div>{btn(q)}</div>' for b,n,w,q,g in TOP)
    return f'<section class="quick" id="top-picks" aria-label="Top picks"><p class="lab">Top picks for running AI at home</p><div class="qp">{rows}</div></section>'

def compare():
    rows = [("Have 16GB RAM, no GPU","32GB RAM kit","14B models (slow but works)","32GB RAM kit"),
            ("Have a desktop with a free PCIe slot","RTX 3060 12GB","Fast 8B to 14B","RTX 3060 12GB graphics card"),
            ("Want more headroom, new card","RTX 5060 Ti 16GB","Fast 14B to 20B","RTX 5060 Ti 16GB graphics card"),
            ("Want 30B models, have 750W PSU","Used RTX 3090 24GB","30B to 32B on GPU","RTX 3090 24GB graphics card"),
            ("Laptop only, want a quiet box","Mini PC with 32GB","7B to 14B, 24/7","mini PC 32GB RAM")]
    trs = "".join(f"<tr><td>{a}</td><td><b>{b}</b></td><td>{c}</td><td>{btn(q,'Check price','btn sm')}</td></tr>" for a,b,c,q in rows)
    return f'<h2 id="compare">What should you buy? Match your situation</h2><div class="tbl"><table><thead><tr><th>Your situation</th><th>Buy this</th><th>What it runs</th><th>Price</th></tr></thead><tbody>{trs}</tbody></table></div>'

START = """<h2 id="start">Start here: 3 steps</h2>
<ol class="steps">
<li><a href="/local-ai/how-much-ram-vram-for-ollama.html">Check what your PC can run</a><br>Look up your RAM and GPU memory in our chart. Takes 2 minutes.</li>
<li><a href="/local-ai/install-ollama-open-webui-windows.html">Install Ollama for free</a><br>Try a small model on the PC you already own before buying anything.</li>
<li><a href="/local-ai/budget-ai-pc-under-1000.html">Upgrade only what is holding you back</a><br>Usually RAM first, then a 12GB+ GPU. Skip the $3,000 AI workstation.</li>
</ol>"""

def cards():
    return '<div class="grid">' + "".join(f'<a class="card" href="/local-ai/{o}"><p class="kicker">{GUIDES[o]["cat"]}</p><h3>{GUIDES[o]["short"]}</h3><p>{GUIDES[o]["desc"][:120].rsplit(" ",1)[0]}...</p></a>' for o in ORDER) + "</div>"

def vids():
    out = []
    for o in ["best-budget-gpu-for-ollama.html","how-much-ram-vram-for-ollama.html","best-mini-pc-for-local-ai.html"]:
        g = GUIDES[o]; v = g["video"]
        out.append(f'<div class="card"><video controls preload="none" playsinline poster="/videos/{v}.jpg" width="360" height="640" style="width:100%;border-radius:12px;aspect-ratio:9/16;background:#000"><source src="/videos/{v}.mp4" type="video/mp4"></video><h3><a href="/local-ai/{o}">{g["short"]}</a></h3><p>{g["vcap"]}</p></div>')
    return '<h2 id="videos">40 second videos</h2><div class="grid">' + "".join(out) + "</div>"

FAQ = [("Can I run AI on my own Windows PC?","Yes. Free tools like Ollama run open models such as Llama, Qwen and Mistral on Windows 10 and 11. 16GB of RAM handles 7B to 8B models. A GPU with 12GB or more of VRAM makes replies much faster."),
       ("What is the cheapest upgrade for local AI?","For most PCs with 16GB of RAM, a 32GB RAM kit is the cheapest upgrade. For speed, a 12GB graphics card like the RTX 3060 12GB is the best value."),
       ("Do I need an expensive AI PC?","No. For chat and coding help with 8B to 14B models, a normal PC with 32GB of RAM or a 12GB GPU is enough. Big 70B models are where costs jump.")]
def faq_html(): return '<h2 id="faq">Quick answers</h2>' + "".join(f"<h3>{q}</h3><p>{a}</p>" for q,a in FAQ)
def faq_ld(): return {"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":q,"acceptedAnswer":{"@type":"Answer","text":a}} for q,a in FAQ]}

def itemlist(url):
    return {"@context":"https://schema.org","@type":"ItemList","name":"Top picks for running AI on a Windows PC","itemListElement":[{"@type":"ListItem","position":i+1,"name":n,"url":"https://aipickvault.com"+g} for i,(_,n,_,_,g) in enumerate(TOP)]}

def ld(objs): return "\n".join(f'<script type="application/ld+json">{json.dumps(o)}</script>' for o in objs)

ORG = {"@context":"https://schema.org","@type":"WebSite","name":"AI Pick Vault","url":"https://aipickvault.com/","description":"Run AI on your own Windows PC on a budget.","publisher":{"@type":"Person","name":"Blake"}}

def home():
    t = "Run AI on Your Own Windows PC on a Budget | AI Pick Vault"
    d = "Run AI like ChatGPT on your own Windows PC without a $3,000 workstation. What your PC can run, the cheapest upgrades (32GB RAM, RTX 3060 12GB) and free setup guides."
    h = head(t, d, "https://aipickvault.com/", ld([ORG, itemlist("/"), faq_ld()]), "https://aipickvault.com/videos/best-budget-gpu-for-ollama.jpg").replace('property="og:type" content="article"','property="og:type" content="website"').replace('<a href="/" >','').replace('<a href="/local-ai/" class="on">','<a href="/local-ai/">')
    body = f"""<main class="wrap">
<section class="hero"><p class="kicker">AI Pick Vault</p>
<h1>Run AI on your own Windows PC, on a budget.</h1>
<p class="lead">Private AI chat and coding help that runs on your computer, with no monthly fee. We tell you what your PC can already run and the cheapest part to buy when it can't.</p>
<p><a class="btn" href="#start">Start here</a> &nbsp; <a class="btn ghost" href="#top-picks">See top picks</a></p></section>
{DISC}
{topbox()}
{START}
{compare()}
{TRUST}
{vids()}
<h2 id="guides">All guides</h2>
{cards()}
{faq_html()}
<p class="meta" style="margin-top:28px">Looking for our older tool, car and power station picks? They are in the <a href="/deals.html">gear archive</a>.</p>
</main>
"""
    (ROOT/"index.html").write_text(h + body + foot("Top pick: RTX 3060 12GB", "RTX 3060 12GB graphics card"), encoding="utf-8")

def hub():
    t = "Local AI on Windows: Hardware and Setup Guides (Ollama) | AI Pick Vault"
    d = "Everything you need to run local AI with Ollama on a Windows PC on a budget: how much RAM and VRAM, best budget GPU, best mini PC, a sub $1,000 AI PC and a step by step install."
    crumbs = {"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":"https://aipickvault.com/"},{"@type":"ListItem","position":2,"name":"Local AI","item":"https://aipickvault.com/local-ai/"}]}
    guides = {"@context":"https://schema.org","@type":"ItemList","name":"Local AI guides","itemListElement":[{"@type":"ListItem","position":i+1,"name":GUIDES[o]["short"],"url":f"https://aipickvault.com/local-ai/{o}"} for i,o in enumerate(ORDER)]}
    h = head(t, d, "https://aipickvault.com/local-ai/", ld([crumbs, guides, itemlist("/local-ai/"), faq_ld()]), "https://aipickvault.com/videos/how-much-ram-vram-for-ollama.jpg").replace('property="og:type" content="article"','property="og:type" content="website"')
    body = f"""<main class="wrap">
<section class="hero"><p class="kicker"><a href="/">Home</a> &middot; Local AI</p>
<h1>Local AI for Windows PCs on a budget</h1>
<p class="lead">Run Ollama and open models on the PC you already have. Find out what it can handle, then buy only the one part that is holding you back.</p></section>
{DISC}
{topbox()}
{START}
{compare()}
<h2 id="guides">The guides</h2>
{cards()}
{TRUST}
{vids()}
{faq_html()}
</main>
"""
    (ROOT/"local-ai"/"index.html").write_text(h + body + foot("Top pick: RTX 3060 12GB", "RTX 3060 12GB graphics card"), encoding="utf-8")

if __name__ == "__main__":
    home(); hub(); print("ok")
