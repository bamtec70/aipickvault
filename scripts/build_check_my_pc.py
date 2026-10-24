#!/usr/bin/env python3
"""Build /check-my-pc/ : the client-side 'Check My PC' tool for local AI (Ollama).
Logic lives in check-my-pc/engine.js (tested by tests/check_my_pc_engine.test.js) and check-my-pc/app.js.
The read-only PowerShell command is in scripts/check_my_pc_cmd.ps1."""
import json, html, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_local_ai import head, foot, btn, DISC, ROOT, REL, amz

URL = "https://aipickvault.com/check-my-pc/"
CMD = (ROOT / "scripts" / "check_my_pc_cmd.ps1").read_text(encoding="utf-8").strip()
MACCMD = (ROOT / "scripts" / "check_my_pc_cmd_mac.sh").read_text(encoding="utf-8").strip()
CHECKED = "Oct 24, 2026"

OG_IMG = "https://aipickvault.com/images/og-check-my-pc.png"
OG_TITLE = "Will AI run on my PC or Mac? Free 1-minute check"
OG_DESC = "Will AI run on my PC or Mac? Free 1-minute check. Nothing to download."
FAQ = [
 ("Is the Check My PC tool safe?", "Yes. Nothing is downloaded or installed. The quick check only reads what your browser already shares. The full check is one read-only Windows PowerShell command that uses Windows' own Get-CimInstance to read your hardware details and copy them to your clipboard. It changes nothing. Everything is worked out inside your browser and nothing is uploaded."),
 ("Why can't the website see all my hardware?", "Browsers hide most hardware details on purpose, for your privacy. For example, browsers never report more than 8GB of memory. That is why the quick check is only a first guess and the full check asks you to run one command and paste the result."),
 ("How much memory do I need to run AI on my own PC?", "Roughly, a model needs about its download size plus 1 to 2GB, either in graphics card memory (fast) or in regular memory (slower). 8GB runs small 3B models, 16GB runs 8B models, and 32GB or a 12GB graphics card handles 12B to 14B models comfortably. These are approximations."),
 ("I am not comfortable with PowerShell. Is there another way?", "Yes. Press the Windows key, type msinfo32 and press Enter. System Information shows your memory, processor and graphics card. Type those numbers into the manual boxes on this page."),
 ("Does it work on a Mac?", "Yes. Choose Mac at the top of the check. You copy one read-only Terminal command that uses the Mac's own sysctl and system_profiler tools to read the chip, memory and free space, and copies the result. Apple chip Macs (M1 and later) share memory with graphics, so about 70 percent of memory can go to AI: 8GB runs small 3B models, 16GB runs 8B models fast, 24 to 36GB runs 14B models, and 64GB or more runs 30B models. Mac memory cannot be upgraded later. Older Intel Macs work but are slow."),
 ("Can you tell me my power supply wattage?", "No. Windows cannot read the power supply. Look at the sticker on the side of the power supply inside your PC (unplug first) for a number like 500W. We list the minimum wattage for each suggested graphics card."),
]

GOALS = [
 ("writing", "Writing letters and email help", "Drafts letters, polishes emails, fixes spelling and tone.", "llama3.2:3b (~2GB), qwen3:8b (~5GB), gemma3:12b (~8GB)"),
 ("docs", "Reading and summarizing documents", "Paste a long letter, report or manual and get the key points in plain words.", "gemma3:4b (~3GB), gemma3:12b (~8GB), qwen3:14b (~9GB)"),
 ("chat", "Everyday questions and chat", "Ask questions, get recipes, explanations and ideas, privately.", "llama3.2:3b (~2GB), qwen3:8b (~5GB), qwen3:30b (~19GB)"),
 ("coding", "Coding help", "Explains code, writes small scripts and spreadsheet formulas.", "qwen2.5-coder:7b (~5GB), qwen3:14b (~9GB), qwen3-coder:30b (~19GB)"),
 ("reason", "Thinking through hard problems", "Step-by-step reasoning for math, planning and tricky questions.", "deepseek-r1:8b (~5GB), deepseek-r1:14b (~9GB), deepseek-r1:32b (~20GB)"),
 ("image", "Making pictures", "Creates images from a description. Not an Ollama model: uses Stable Diffusion with ComfyUI.", "SD 1.5 (~4 to 6GB VRAM), SDXL (~8GB+ VRAM), FLUX (~12GB+ VRAM)"),
 ("voice", "Voice: read aloud and dictation", "Reads text out loud and types what you say. Very light.", "Windows Narrator and Voice Access (built in), Piper, Whisper"),
]

def goal_cards():
    return '<div class="goals">' + "".join(
        f'<button type="button" class="goal" data-goal="{k}" aria-pressed="{"true" if k=="chat" else "false"}"><b>{html.escape(t)}</b><span>{html.escape(d)}</span><small>Models: {html.escape(m)}</small></button>'
        for k, t, d, m in GOALS) + "</div>"

CSS = """<style>
.tool .step{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);border-radius:22px;padding:22px;margin:26px 0}
.tool .step h2{margin:.2em 0 .5em}.tool .num{display:inline-grid;place-items:center;width:34px;height:34px;border-radius:50%;background:linear-gradient(135deg,#38bdf8,#6366f1);color:#fff;font-weight:800;margin-right:8px;font-size:1rem;vertical-align:middle}
.tool .big{font-size:1.05rem;padding:14px 22px}
.tool .out{background:#0b1222;border:1px solid var(--line);border-radius:14px;padding:14px 18px;margin-top:14px}
.tool pre#pscmd{white-space:pre-wrap;word-break:break-all;font-size:.72rem;max-height:120px;overflow:auto;color:#cbd5e1}
.tool ol.how li{margin:.45em 0;font-size:1.03rem}.tool kbd{background:#1e293b;border:1px solid #334155;border-radius:6px;padding:1px 6px;font-size:.9em;color:#fff}
.tool textarea{width:100%;min-height:110px;background:#0b1222;color:#e2e8f0;border:1px solid #334155;border-radius:12px;padding:12px;font:0.85rem/1.4 ui-monospace,Consolas,monospace}
.tool .err{color:#fca5a5;font-weight:700}
.tool .manual{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:12px 0}
.tool label{display:flex;flex-direction:column;gap:4px;font-weight:700;color:#e2e8f0;font-size:.95rem}
.tool input,.tool select{background:#0b1222;color:#e2e8f0;border:1px solid #334155;border-radius:10px;padding:10px;font-size:1rem}
.tool details.alt{margin-top:18px;background:rgba(255,255,255,.02);border:1px solid var(--line);border-radius:14px;padding:14px 18px}.tool details.alt summary{cursor:pointer;font-weight:800;color:#fff}
.goals{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}
.goal{text-align:left;display:flex;flex-direction:column;gap:6px;background:#0b1222;border:2px solid var(--line);border-radius:16px;padding:16px;color:var(--txt);cursor:pointer;font:inherit}
.goal b{color:#fff;font-size:1.05rem}.goal span{font-size:.93rem}.goal small{color:var(--mut);font-size:.8rem}
.goal[aria-pressed=true]{border-color:var(--cta);background:rgba(245,158,11,.08)}.goal:focus-visible{outline:3px solid var(--acc)}
.verdict{border-radius:18px;padding:20px;border:2px solid var(--acc);background:rgba(56,189,248,.06)}
.verdict h3{font-size:1.6rem;margin:.2em 0 .4em;color:#fff}.verdict.ok{border-color:#22c55e;background:rgba(34,197,94,.07)}.verdict.mem,.verdict.gpu{border-color:var(--cta)}.verdict.new{border-color:#a78bfa}
.verdict .links{display:flex;flex-wrap:wrap;gap:10px;margin:12px 0}.verdict .links .btn{width:auto}
table.fit{width:100%;border-collapse:collapse;margin:12px 0;font-size:.92rem}table.fit th,table.fit td{border-bottom:1px solid var(--line);padding:8px 6px;text-align:left;vertical-align:top}
td.fast{color:#86efac}td.ok{color:#fcd34d}td.no{color:#fca5a5}
#specs dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 14px;margin:0}#specs dt{font-weight:700;color:#e2e8f0}#specs dd{margin:0}
.privacy{border-left:4px solid #22c55e;background:rgba(34,197,94,.07);border-radius:12px;padding:12px 16px;margin:18px 0}
@media(max-width:640px){#specs dl{grid-template-columns:1fr}#specs dd{margin-bottom:6px}.tool .step{padding:16px}}
.cave{list-style:none;counter-reset:c;padding:0;margin:14px 0}.cave li{counter-increment:c;display:flex;align-items:center;gap:14px;font-size:1.25rem;line-height:1.45;margin:0 0 12px;padding:12px 14px;border:2px solid rgba(255,255,255,.14);border-radius:12px;background:rgba(255,255,255,.05)}.cave li:before{content:counter(c);flex:0 0 48px;height:48px;border-radius:50%;background:#f97316;color:#fff;font-weight:800;font-size:1.6rem;display:flex;align-items:center;justify-content:center}.cave .ico{flex:0 0 44px;width:44px;height:44px}#copy-cmd,#copy-mac,#analyze{font-size:1.3rem;padding:18px 30px;min-height:60px}@media(max-width:480px){.cave li{font-size:1.1rem;gap:10px;padding:10px}.cave li:before{flex-basis:40px;height:40px;font-size:1.3rem}.cave .ico{flex-basis:34px;width:34px;height:34px}#copy-cmd,#copy-mac,#analyze{width:100%}}.trouble{margin:6px 0 16px}.trouble li{margin:6px 0}
.tool pre#maccmd{white-space:pre-wrap;word-break:break-all;font-size:.72rem;max-height:120px;overflow:auto;color:#cbd5e1}
.ospick{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:8px 0 18px}.os-btn{display:flex;align-items:center;justify-content:center;gap:12px;font:inherit;font-size:1.35rem;font-weight:800;color:#fff;min-height:70px;padding:12px;border-radius:16px;border:3px solid var(--line);background:#0b1222;cursor:pointer}.os-btn svg{width:36px;height:36px;flex:0 0 36px}.os-btn[aria-pressed=true]{border-color:#f97316;background:rgba(249,115,22,.14)}.os-btn:focus-visible{outline:3px solid var(--acc)}
div[data-os=mac]{display:none}body.os-mac div[data-os=mac]{display:block}body.os-mac div[data-os=win]{display:none}
@media(max-width:480px){.os-btn{font-size:1.15rem;min-height:62px}}</style>"""

def build():
    app = {"@context": "https://schema.org", "@type": ["WebApplication", "SoftwareApplication"], "name": "Check My PC for Local AI",
           "url": URL, "applicationCategory": "UtilitiesApplication", "operatingSystem": "Windows 10, Windows 11, macOS (runs in any modern browser)",
           "browserRequirements": "Requires JavaScript", "isAccessibleForFree": True,
           "description": "Free, private tool that checks whether your Windows PC or Mac can run local AI models with Ollama and tells you the one upgrade you need. Runs entirely in your browser.",
           "creator": {"@type": "Person", "name": "Blake"}, "publisher": {"@type": "Organization", "name": "AI Pick Vault", "url": "https://aipickvault.com/"}}
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://aipickvault.com/"},
        {"@type": "ListItem", "position": 2, "name": "Local AI", "item": "https://aipickvault.com/local-ai/"},
        {"@type": "ListItem", "position": 3, "name": "Check My PC", "item": URL}]}
    faq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]}
    ld = "\n".join(f'<script type="application/ld+json">{json.dumps(o)}</script>' for o in (app, crumbs, faq))
    h = head("Check My PC: Can It Run Local AI? | AI Pick Vault",
             "Free, private check: can your Windows PC or Mac run local AI with Ollama? Find out in a minute and see the one upgrade you need. Nothing to download, nothing uploaded.",
             URL, ld, og_img=OG_IMG).replace('property="og:type" content="article"', 'property="og:type" content="website"')
    import re as _re
    h = _re.sub(r'<meta property="og:title" content="[^"]*">', f'<meta property="og:title" content="{OG_TITLE}">', h)
    h = _re.sub(r'<meta name="twitter:title" content="[^"]*">', f'<meta name="twitter:title" content="{OG_TITLE}">', h)
    h = _re.sub(r'<meta (property="og:description"|name="twitter:description") content="[^"]*">', lambda m: f'<meta {m.group(1)} content="{OG_DESC}">', h)
    h = h.replace(f'<meta property="og:image" content="{OG_IMG}">', f'<meta property="og:image" content="{OG_IMG}">\n<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n<meta property="og:image:alt" content="Will AI run on my PC? Free 1-minute check. Nothing to download.">', 1)
    h = h.replace('<a href="/local-ai/" class="on">', '<a href="/local-ai/">').replace('<a href="/check-my-pc/">', '<a href="/check-my-pc/" class="on">')
    h = h.replace("</head>", CSS + "\n</head>")
    psu_rows = "".join(f"<tr><td>{n}</td><td>{w}</td><td>{c}</td></tr>" for n, w, c in [
        ("RTX 3050 6GB (low profile)", "300W", "None. Powered by the slot. Fits slim office PCs."),
        ("RTX 5060 Ti 16GB", "450W", "One 8-pin PCIe cable"),
        ("RTX 3060 12GB", "550W", "One 8-pin PCIe cable"),
        ("Used RTX 3090 24GB", "750W", "Two or three 8-pin PCIe cables")])
    body = f"""<section class="hero sm"><div class="wrap narrow">
<p class="kicker"><a href="/">Home</a> &middot; <a href="/local-ai/">Local AI</a> &middot; Free tool</p>
<h1>Check My PC or Mac: can it run AI at home?</h1>
<p class="lead">Find out in about a minute whether your Windows PC or Mac can run private AI with Ollama, and exactly what to upgrade if it can't. Plain words, no downloads.</p>
<p class="meta">Last checked {CHECKED} &middot; Built by Blake, AI Pick Vault</p>
</div></section>
<main class="wrap narrow tool">
<div class="privacy"><p><strong>Your privacy:</strong> everything on this page happens inside your own browser. Nothing is downloaded to your PC, nothing is installed, and nothing you paste is uploaded or saved. Close the tab and it is gone.</p></div>

<section class="step" id="quick"><h2><span class="num">1</span>Quick check (one click)</h2>
<p>Press the button and your browser tells us what it is allowed to share: your graphics chip and roughly how much memory you have. This is a <strong>first guess</strong>, not the final answer.</p>
<button type="button" class="btn big" id="quick-btn">Run the quick check</button>
<div class="out" id="quick-out" hidden></div>
</section>

<section class="step" id="full"><h2><span class="num">2</span>Full check (about a minute)</h2>
<p class="ospick-q"><strong>What computer are you using?</strong></p>
<div class="ospick" role="group" aria-label="Choose your computer"><button type="button" class="os-btn" data-os="win" aria-pressed="true"><svg viewBox="0 0 48 48" aria-hidden="true"><path d="M6 10l15-2v15H6zM24 7.6 42 5v18H24zM6 26h15v15L6 39zM24 26h18v18l-18-2.6z" fill="#38bdf8"/></svg>Windows PC</button><button type="button" class="os-btn" data-os="mac" aria-pressed="false"><svg viewBox="0 0 48 48" aria-hidden="true"><rect x="6" y="8" width="36" height="24" rx="3" fill="none" stroke="#e2e8f0" stroke-width="3.5"/><path d="M18 40h12M24 32v8" stroke="#e2e8f0" stroke-width="3.5" stroke-linecap="round"/></svg>Mac</button></div>
<div data-os="mac">
<p>Get an exact answer in 4 easy steps. The command only <strong>reads</strong> your Mac's details. It does not change, install or send anything.</p>
<button type="button" class="btn big" id="copy-mac">Copy command</button>
<details class="alt" style="margin-top:12px"><summary>See exactly what the command does</summary><pre id="maccmd">{html.escape(MACCMD)}</pre>
<p class="meta">It reads: chip name, memory size, number of processor cores and graphics cores, Mac model, macOS version, and free disk space. Then it formats that as text and copies it.</p></details>
<h3>Step by step</h3>
<ol class="cave">
<li><svg class="ico" viewBox="0 0 48 48" aria-hidden="true"><rect x="10" y="8" width="28" height="34" rx="4" fill="#fff" stroke="#f97316" stroke-width="3"/><rect x="17" y="4" width="14" height="8" rx="2" fill="#f97316"/><path d="M16 22h16M16 29h16M16 36h10" stroke="#334155" stroke-width="3"/></svg><span>Click <strong>Copy command</strong>.</span></li>
<li><svg class="ico" viewBox="0 0 48 48" aria-hidden="true"><rect x="4" y="6" width="40" height="36" rx="7" fill="#1e293b" stroke="#94a3b8" stroke-width="3"/><path d="M12 18l7 6-7 6M22 31h12" fill="none" stroke="#fff" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/></svg><span>Open <strong>Terminal</strong>: press <kbd>Command</kbd>+<kbd>Space</kbd>, type <strong>Terminal</strong>, press <kbd>Return</kbd>.</span></li>
<li><svg class="ico" viewBox="0 0 48 48" aria-hidden="true"><rect x="3" y="8" width="42" height="32" rx="6" fill="#fff" stroke="#334155" stroke-width="3"/><path d="M34 16v10H15m5-6-6 6 6 6" fill="none" stroke="#f97316" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/></svg><span>Press <kbd>Command</kbd>+<kbd>V</kbd> to paste. Press <kbd>Return</kbd>.</span></li>
<li><svg class="ico" viewBox="0 0 48 48" aria-hidden="true"><rect x="4" y="8" width="40" height="32" rx="5" fill="#fff" stroke="#334155" stroke-width="3"/><path d="M11 18h26M11 25h20" stroke="#94a3b8" stroke-width="3"/><path d="M30 30l6 6 9-12" fill="none" stroke="#16a34a" stroke-width="4" stroke-linecap="round"/></svg><span>See <strong>Done!</strong>? Come back. Click the box below. Press <kbd>Command</kbd>+<kbd>V</kbd>. Click <strong>Check my results</strong>.</span></li>
</ol>
<details class="alt trouble"><summary>Having trouble?</summary>
<ul>
<li><strong>Nothing happened after pasting?</strong> Press <kbd>Return</kbd> once.</li>
<li><strong>The paste box says it is the command?</strong> Go back to Terminal, press <kbd>Return</kbd>, wait for Done!, then paste again.</li>
<li><strong>Paste on this page did not work?</strong> In Terminal, the line starting with <code>{{"apv":1</code> is your result. Select it with the mouse, press <kbd>Command</kbd>+<kbd>C</kbd>, and paste it here.</li>
<li><strong>Older Mac?</strong> It still works. Macs from 2020 and later with an Apple chip (M1, M2, M3, M4) are the fast ones for AI.</li>
</ul></details>
</div>
<div data-os="win">
<p>Get an exact answer in 4 easy steps. The command only <strong>reads</strong> your PC's details. It does not change, install or send anything.</p>
<button type="button" class="btn big" id="copy-cmd">Copy command</button>
<details class="alt" style="margin-top:12px"><summary>See exactly what the command does</summary><pre id="pscmd">{html.escape(CMD)}</pre>
<p class="meta">It reads: processor name and cores, motherboard maker and model, each memory stick's size, speed and type, total memory slots and the board maximum, graphics card name and memory, Windows version, whether it is a laptop, and free space on drive C:. Then it formats that as text and copies it.</p></details>
<h3>Step by step</h3>
<ol class="cave">
<li><svg class="ico" viewBox="0 0 48 48" aria-hidden="true"><rect x="10" y="8" width="28" height="34" rx="4" fill="#fff" stroke="#f97316" stroke-width="3"/><rect x="17" y="4" width="14" height="8" rx="2" fill="#f97316"/><path d="M16 22h16M16 29h16M16 36h10" stroke="#334155" stroke-width="3"/></svg><span>Click <strong>Copy command</strong>.</span></li>
<li><svg class="ico" viewBox="0 0 48 48" aria-hidden="true"><rect x="4" y="4" width="40" height="40" rx="8" fill="#0078d4"/><path d="M12 12h11v11H12zM25 12h11v11H25zM12 25h11v11H12zM25 25h11v11H25z" fill="#fff"/></svg><span><strong>Right-click</strong> the Start button. Pick <strong>Terminal</strong> or <strong>PowerShell</strong> (the blue window).</span></li>
<li><svg class="ico" viewBox="0 0 48 48" aria-hidden="true"><rect x="3" y="8" width="42" height="32" rx="6" fill="#fff" stroke="#334155" stroke-width="3"/><path d="M34 16v10H15m5-6-6 6 6 6" fill="none" stroke="#f97316" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/></svg><span><strong>Right-click</strong> in the blue window. Press <kbd>Enter</kbd>.</span></li>
<li><svg class="ico" viewBox="0 0 48 48" aria-hidden="true"><rect x="4" y="8" width="40" height="32" rx="5" fill="#fff" stroke="#334155" stroke-width="3"/><path d="M11 18h26M11 25h20" stroke="#94a3b8" stroke-width="3"/><path d="M30 30l6 6 9-12" fill="none" stroke="#16a34a" stroke-width="4" stroke-linecap="round"/></svg><span>See <strong>Done!</strong>? Come back. Click the box below. Press <kbd>Ctrl</kbd>+<kbd>V</kbd>. Click <strong>Check my results</strong>.</span></li>
</ol>
<details class="alt trouble"><summary>Having trouble?</summary>
<ul>
<li><strong>Windows asks about pasting multiple lines?</strong> Click <strong>Paste anyway</strong>. It is safe.</li>
<li><strong>Right-click did not paste?</strong> Press <kbd>Ctrl</kbd> + <kbd>V</kbd> instead.</li>
<li><strong>Only an "Admin" choice?</strong> That is fine too. You do not need Admin, but it works the same.</li>
<li><strong>Nothing happened after pasting?</strong> Press <kbd>Enter</kbd> once.</li>
<li><strong>The paste box says it is the command?</strong> Go back to PowerShell, press <kbd>Enter</kbd>, wait for Done!, then paste again.</li>
<li><strong>Paste on this page did not work?</strong> In the PowerShell window, the long line starting with <code>{{"apv":1</code> is your result. Select it with the mouse, right-click to copy, and paste it here.</li>
</ul></details>
</div>
<label for="paste">Paste your results here</label>
<textarea id="paste" placeholder='It will look like {{"apv":1,"cpu":"...","ram":[...]...}}' spellcheck="false"></textarea>
<p><button type="button" class="btn" id="analyze">Check my results</button></p>
<p class="err" id="paste-err" hidden></p>

<div data-os="win"><details class="alt" id="manual"><summary>Not comfortable with PowerShell? Use System Information instead</summary>
<ol class="how">
<li>Press the <strong>Windows key</strong>, type <code>msinfo32</code> and press <kbd>Enter</kbd>. System Information opens. It only shows information.</li>
<li>On the first page, find <strong>Installed Physical Memory (RAM)</strong> (for example "16.0 GB") and <strong>Processor</strong>.</li>
<li>On the left, open <strong>Components</strong> &gt; <strong>Display</strong>. Note the <strong>Name</strong> of each graphics adapter. (Windows often shows graphics memory wrong here; leave the memory box empty if unsure and we will estimate it from the name.)</li>
<li>Fill in the boxes below.</li>
</ol>
<div class="manual">
<label>Memory (RAM) in GB<input id="m-ram" type="number" min="1" max="1024" inputmode="numeric" placeholder="16"></label>
<label>Graphics card name<input id="m-gpu" type="text" placeholder="NVIDIA GeForce RTX 3060 (blank if Intel/AMD built-in)"></label>
<label>Graphics memory (VRAM) in GB<input id="m-vram" type="number" min="0" max="96" inputmode="numeric" placeholder="optional"></label>
<label>Processor<input id="m-cpu" type="text" placeholder="Intel Core i5-10400"></label>
<label>Type of computer<select id="m-type"><option value="desktop">Desktop tower</option><option value="laptop">Laptop</option><option value="mini">Mini PC or all-in-one</option></select></label>
<label>Memory type (if you know)<select id="m-ddr"><option value="">Not sure</option><option>DDR3</option><option>DDR4</option><option>DDR5</option><option value="soldered">Soldered / LPDDR (cannot upgrade)</option></select></label>
</div>
<p><button type="button" class="btn" id="manual-go">Check these numbers</button></p>
<p class="err" id="manual-err" hidden></p>
</details></div>
</section>

<section class="step" id="goals"><h2><span class="num">3</span>What would you like AI to help with?</h2>
<p>Pick one. Model names are the real names you type into Ollama (for example <code>ollama run qwen3:8b</code>). Sizes are approximate downloads; a model needs roughly its size plus 1 to 2GB of memory to run.</p>
{goal_cards()}
</section>

<section class="step" id="results"><h2><span class="num">4</span>Your answer</h2>
<div id="specs"></div>
<div id="verdict"></div>
<p class="meta" style="margin-top:14px">How we decide: a model fits "fast" when its size plus about 1.5GB fits in your graphics card memory, and "works, slower" when it fits in your regular memory after leaving about 4GB for Windows. These are widely used rules of thumb, not guarantees. Real speed also depends on your processor and memory speed.</p>
</section>

<section class="step" id="psu"><h2>Before you buy a graphics card: check your power supply</h2>
<p>Windows cannot see your power supply, so we cannot check it for you. It takes two minutes:</p>
<ol class="how"><li>Shut down the PC and unplug it.</li><li>Remove the side panel (usually two screws at the back).</li><li>Find the metal box where the power cord plugs in. Its sticker lists a number with a <strong>W</strong>, like <strong>500W</strong>. That is the wattage.</li><li>Look for spare cables labelled <strong>PCIe</strong> or <strong>PCI-E</strong> (6+2 pin). Most cards need one.</li></ol>
<div class="tbl"><table><thead><tr><th>Graphics card</th><th>Minimum power supply</th><th>Power cable</th></tr></thead><tbody>{psu_rows}</tbody></table></div>
<p class="meta">Minimums are the card makers' usual recommendations for a typical PC. Slim office PCs (Dell OptiPlex, HP ProDesk, Lenovo ThinkCentre) often have small 180W to 260W power supplies and short cases, so only low-profile cards without a power cable fit.</p>
</section>

<section class="step" id="ask"><h2>Rather have Blake look at it?</h2>
<p>Send your results and I will take a look and tell you, in plain words, what I would do. Run the full check first so your results are filled in. Your email app opens with everything prefilled; you can read it before sending.</p>
<p><a class="btn" id="ask-blake" href="mailto:contact@aipickvault.com">Have Blake check it for me</a></p>
<p class="meta">Prefer a form? Use the <a href="/contact.html">contact page</a> and paste your results.</p>
</section>

{DISC}
<h2>Common questions</h2><div class="faq">{"".join(f"<details><summary>{html.escape(q)}</summary><p>{html.escape(a)}</p></details>" for q, a in FAQ)}</div>
<aside class="more"><p class="kicker">Keep reading</p><ul><li><a href="/local-ai/how-much-ram-vram-for-ollama.html">How much RAM and VRAM do you need for Ollama?</a></li><li><a href="/local-ai/best-budget-gpu-for-ollama.html">Best budget GPU for Ollama</a></li><li><a href="/local-ai/install-ollama-open-webui-windows.html">Install Ollama on Windows, step by step</a></li><li><a href="/ai-for-beginners/what-is-ollama.html">What is Ollama? Models in plain words</a></li></ul></aside>
</main>
<script src="/check-my-pc/engine.js" defer></script>
<script src="/check-my-pc/app.js" defer></script>
"""
    (ROOT / "check-my-pc" / "index.html").write_text(h + body + foot("Most common upgrade: 32GB RAM", "32GB RAM kit"), encoding="utf-8")
    print("built /check-my-pc/")

if __name__ == "__main__":
    build()
