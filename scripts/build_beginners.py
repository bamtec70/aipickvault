#!/usr/bin/env python3
"""Build the gentle AI for Beginners hub (/ai-for-beginners/) and its 4 guides."""
import json, sys, html
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from yt_video import yt_embed, video_ld
from build_local_ai import head, foot, btn, amz, REL, DISC, ROOT, svg, CHECK_CTA

BASE = "https://aipickvault.com/ai-for-beginners/"
CHECKED = "October 2026"
TRUSTB = """<div class="trust"><div class="ic">""" + svg("wrench") + """</div><div><p><strong>Who writes this:</strong> Blake, the guy behind AI Pick Vault. He has spent 47 years fixing things and sorting out PCs for regular people. He is 56 and still learning AI too, so these pages explain things the way he wishes someone had explained them to him.</p><p class="meta">Some links go to Amazon. As an Amazon Associate we earn from qualifying purchases, at no extra cost to you. You never need to buy anything to use the free tools on these pages.</p></div></div>"""

def ld(objs): return "\n".join(f'<script type="application/ld+json">{json.dumps(o)}</script>' for o in objs)
def crumbs(name, url):
    items=[("Home","https://aipickvault.com/"),("AI for Beginners",BASE)] + ([(name,url)] if url!=BASE else [])
    return {"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":i+1,"name":n,"item":u} for i,(n,u) in enumerate(items)]}
def faq_ld(faq): return {"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":q,"acceptedAnswer":{"@type":"Answer","text":a}} for q,a in faq]}
def faq_html(faq): return '<h2>Common questions</h2><div class="faq">' + "".join(f"<details><summary>{html.escape(q)}</summary><p>{html.escape(a)}</p></details>" for q,a in faq) + "</div>"
def art_ld(title, desc, url, published=None, modified="2026-10-23"):
    a = {"@context":"https://schema.org","@type":"Article","headline":title,"description":desc,"url":url,"dateModified":modified,"author":{"@type":"Person","name":"Blake"},"publisher":{"@type":"Organization","name":"AI Pick Vault"}}
    if published: a = {**{k:a[k] for k in ("@context","@type","headline","description","url")}, "datePublished":published, **{k:a[k] for k in ("dateModified","author","publisher")}}
    return a

def gear(items):
    rows = "".join(f'<div class="gear-item"><h3>{n}</h3><p>{w}</p><a class="btn sm" href="{amz(q)}" {REL}>See options on Amazon</a></div>' for n,w,q in items)
    return f'<section class="gear"><p class="kicker">Optional, only if it helps</p><h2>Gear that can make this easier</h2><p>You do not need any of this to get started. These are simple add-ons that people often find helpful. Read reviews and check the return policy first.</p><div class="gear-grid">{rows}</div></section>'

NEXT = [("what-is-ai.html","What is AI, really?"),("is-ai-spying-on-me.html","Is AI spying on me?"),("what-is-ollama.html","What is Ollama? Models explained"),("ai-for-seniors-and-disabilities.html","AI that helps with vision, hearing, hands and memory"),("ai-on-your-phone/","AI on your phone"),("ai-helpers-for-seniors-living-alone.html","AI helpers for seniors who live alone"),("local-ai-memory-for-cloud-ai.html","Give your cloud AI a long-term memory")]
def nextnav(cur):
    return '<nav class="b-next" aria-label="More beginner guides"><p class="kicker">Keep reading</p>' + "".join(f'<a href="/ai-for-beginners/{f}">{t} &rarr;</a>' for f,t in NEXT if f!=cur) + "</nav>"

import re
def label_tables(h):
    def one(m):
        t=m.group(0); ths=[re.sub(r'<[^>]+>','',x) for x in re.findall(r'<th>(.*?)</th>',t)]
        def row(r):
            i=[0]
            def td(c):
                lab=ths[i[0]] if i[0]<len(ths) else ""; i[0]+=1
                return f'<td data-label="{lab}">'
            return re.sub(r'<td>',td,r.group(0))
        return re.sub(r'<tr>.*?</tr>',row,t,flags=re.S)
    return re.sub(r'<table>.*?</table>',one,h,flags=re.S)
def page(fn, title, h1, desc, lead, body, faq, sticky, extra_ld=(), published=None, modified="2026-10-23", top="", og=None):
    slug = fn[:-len("index.html")] if fn.endswith("/index.html") else fn
    url = BASE + slug
    hd = head(title, desc, url, ld([crumbs(h1,url), art_ld(h1,desc,url,published,modified)] + list(extra_ld) + ([faq_ld(faq)] if faq else []) + ([video_ld()] if "class=\"yt\"" in body else [])), og)
    hd = hd.replace('<a href="/local-ai/" class="on">','<a href="/local-ai/">').replace('<a href="/ai-for-beginners/">','<a href="/ai-for-beginners/" class="on">')
    out = f"""<section class="hero"><div class="wrap"><p class="kicker"><a href="/">Home</a> &middot; <a href="/ai-for-beginners/">AI for Beginners</a></p>
<h1>{h1}</h1><p class="lead">{lead}</p><p class="meta">Last checked {CHECKED}. Written in plain words. No question is silly.</p></div></section>
<main class="wrap"><article class="beginner">
{top}{label_tables(body)}
{faq_html(faq) if faq else ""}
{CHECK_CTA}
{TRUSTB}
{nextnav(slug)}
{DISC}
</article></main>
"""
    (ROOT/"ai-for-beginners"/fn).parent.mkdir(parents=True, exist_ok=True)
    (ROOT/"ai-for-beginners"/fn).write_text(hd + out + foot(*sticky), encoding="utf-8")

# ---------------- 1. What is AI ----------------
P1 = """<div class="calm"><p><strong>The short version:</strong> AI is a computer program that has read a huge amount of text and learned to guess the next word. It is very good at guessing. It does not think, feel or want anything. It is a tool, like a very clever autocomplete.</p></div>
<h2>What AI really is</h2>
<p>You know how your phone suggests the next word when you type a text? Modern AI chat programs work on the same idea, just much bigger.</p>
<p>They were trained on books, websites and articles. From all that reading, they learned patterns. When you ask a question, they predict a likely answer one word at a time.</p>
<p>That is why the answers sound so natural. It is also why AI can be confidently wrong. It is guessing what sounds right, not checking what is true.</p>
<p><strong>It is not a mind.</strong> It has no feelings, no wishes and no plans. When you close the window, it is not thinking about you.</p>
<h2>What AI can do well</h2>
<ul class="big-list"><li>Explain a confusing letter, bill or form in plain words.</li><li>Help you write an email, a note or a thank you card.</li><li>Summarize a long article so you get the main points.</li><li>Read text out loud, or describe a photo, with the right app.</li><li>Answer "how do I" questions, like how to change a setting on your phone.</li><li>Brainstorm: gift ideas, recipes from what is in your fridge, trip plans.</li></ul>
<h2>What AI cannot do (or should not be trusted to do)</h2>
<ul class="big-list"><li>It cannot be sure it is right. Always double check facts, dates, phone numbers and anything about money or health.</li><li>It is not your doctor, lawyer or banker. Use it to prepare questions, then ask a real person.</li><li>It does not know you unless you tell it. It does not read your mind or watch you.</li><li>Most AI cannot act on its own. It answers when you ask. It does not wander off and do things.</li></ul>
<h2>Myths vs facts</h2>
<div class="tbl"><table><thead><tr><th>What people worry about</th><th>The honest answer</th></tr></thead><tbody>
<tr><td><strong>"AI is spying on me."</strong></td><td>Online AI services do keep what you type, at least for a while, like most websites. That is a real privacy question, not spying in the movie sense. You can turn some of it off, or use AI that runs only on your own computer. <a href="/ai-for-beginners/is-ai-spying-on-me.html">Full privacy guide</a>.</td></tr>
<tr><td><strong>"AI is going to take over."</strong></td><td>Today's AI predicts words. It has no wants and no goals of its own. Experts do debate long term risks, and that debate is worth following, but the chat program on your computer is not plotting anything.</td></tr>
<tr><td><strong>"AI will take everyone's job."</strong></td><td>Some tasks are changing, especially paperwork and writing. Most jobs are changing rather than vanishing. Learning the basics, like you are doing now, is the best protection.</td></tr>
<tr><td><strong>"AI knows everything."</strong></td><td>No. It can make things up and sound sure about it. People call this "hallucinating." Check anything important.</td></tr>
<tr><td><strong>"I am too old or not techy enough."</strong></td><td>If you can type a text message or talk to your phone, you can use AI. You just ask in normal words.</td></tr>
</tbody></table></div>
<h2>How to use AI safely</h2>
<ol class="big-list"><li><strong>Never type passwords, bank numbers, your Social Security number or card numbers</strong> into an AI chat.</li><li><strong>Check important answers</strong> with a second source or a real person.</li><li><strong>Watch for scams.</strong> Criminals now use AI to fake voices and write convincing emails. If a "grandchild" or "bank" calls asking for money in a hurry, hang up and call back on a number you already know.</li><li><strong>Start small.</strong> Ask it to explain something you already understand, so you can see how it does.</li><li><strong>Want full privacy?</strong> Use AI that runs on your own computer. Nothing you type leaves the machine. See <a href="/ai-for-beginners/what-is-ollama.html">What is Ollama?</a></li></ol>
<h2>Try it: your first question</h2>
<p>Open any AI chat (or install one on your own PC) and type something like:</p>
<p class="say">"Explain what a 401k is in simple words, like you are talking to a friend."</p>
<p>Then ask a follow up: <em>"Can you make that shorter?"</em> That back and forth is the whole trick.</p>"""
F1 = [("Is AI alive or conscious?","No. Today's AI is a program that predicts likely words based on patterns it learned from text. It has no feelings, wishes or awareness."),
      ("Can AI make mistakes?","Yes, often. It can state wrong facts in a confident voice. Always double check anything about health, money, legal matters, dates or phone numbers."),
      ("Is it safe for older adults to use AI?","Yes, with the same common sense you use online. Never share passwords or bank details, check important answers, and be alert to scam calls and emails that use fake voices."),
      ("Do I need to pay for AI?","No. There are free versions of online AI chat, and free programs like Ollama that run AI on your own computer with no monthly fee.")]

# ---------------- 2. Spying ----------------
P2 = """<div class="calm"><p><strong>The honest answer:</strong> Online AI is not secretly watching you through your camera. But when you type into an online AI, the company receives what you type and usually keeps it for a while. You have choices: turn off some settings, be careful what you share, or run AI on your own computer so nothing leaves your house.</p></div>
<h2>Two kinds of AI: online and on your own computer</h2>
<div class="tbl"><table><thead><tr><th></th><th>Online (cloud) AI</th><th>Local AI on your PC</th></tr></thead><tbody>
<tr><td><strong>Examples</strong></td><td>ChatGPT, Gemini, Copilot, Grok, Claude</td><td>Ollama with a free model like Llama, Gemma or Qwen</td></tr>
<tr><td><strong>Where your words go</strong></td><td>Sent over the internet to the company's computers</td><td>Stay on your computer</td></tr>
<tr><td><strong>Who can see them</strong></td><td>The company, under its privacy policy. Some chats may be reviewed by staff to improve the service.</td><td>Only people who use your computer</td></tr>
<tr><td><strong>Works without internet</strong></td><td>No</td><td>Yes, once it is set up</td></tr>
<tr><td><strong>How smart</strong></td><td>The smartest and fastest options</td><td>Good for everyday tasks. Smaller and a bit slower.</td></tr>
<tr><td><strong>Cost</strong></td><td>Free tiers, or a monthly fee for more</td><td>Free software. Uses the PC you already own.</td></tr>
</tbody></table></div>
<h2>What online AI companies usually keep</h2>
<ul class="big-list"><li><strong>Your chats.</strong> Most keep your conversation history so you can come back to it. Many keep chats for a time even after you delete them, often for safety and abuse checks.</li><li><strong>Your account details.</strong> Email, name, and sometimes phone number.</li><li><strong>Basic device info.</strong> Like any website: browser, rough location from your internet connection, and when you used it.</li><li><strong>Files and photos you upload.</strong> If you share a picture of a letter, the company receives that picture.</li></ul>
<p>Details change often, so read each company's privacy page. Look for the words "data controls," "training," and "retention."</p>
<h2>Settings worth turning off</h2>
<p>Menu names change, but the idea is the same everywhere. Look in <strong>Settings</strong>, then <strong>Privacy</strong> or <strong>Data controls</strong>.</p>
<ul class="big-list"><li><strong>"Use my chats to improve the model"</strong> (or similar). Turn this off if you do not want your chats used for training. ChatGPT, Gemini, Copilot, Grok and Claude all offer a version of this switch.</li><li><strong>Chat history or activity.</strong> Some apps let you turn history off, or use a temporary chat that is not saved to your list.</li><li><strong>Memory.</strong> Some AI apps remember facts about you across chats. You can view, delete or turn this off.</li><li><strong>Microphone and camera.</strong> On your phone or PC, you control which apps can use them. On Windows: Settings, Privacy and security, Microphone or Camera. On a phone: Settings, Privacy.</li></ul>
<h2>Is AI listening through my phone or camera?</h2>
<p>An AI chat app can only hear you when you allow its microphone and press the button to talk. Phones show a small colored dot or icon when the microphone or camera is in use. If you see it and did not expect it, check which app is using it in your privacy settings.</p>
<h2>Why local AI keeps everything private</h2>
<p>A free program called <a href="/ai-for-beginners/what-is-ollama.html">Ollama</a> lets you download an AI model onto your own Windows PC or Mac. After the download, it runs entirely on your machine. You can even unplug the internet and it still works.</p>
<p>That means your letters, health questions and family notes never go to a company. The trade off: local models are a bit less clever than the big online ones, and you need a reasonably modern PC. Many PCs with 16GB of memory can run a good small model. <a href="/local-ai/how-much-ram-vram-for-ollama.html">Check what your PC can run</a>.</p>
<h2>Simple privacy rules</h2>
<ol class="big-list"><li>Do not type anything into online AI you would not put in an email to a stranger.</li><li>Never share passwords, bank or card numbers, or your Social Security number with any AI.</li><li>Black out account numbers before you photograph a letter for AI to read.</li><li>For private things, use local AI on your own computer.</li></ol>
<p>Thinking about an AI companion or check-in service for a parent? Our guide to <a href="/ai-for-beginners/ai-helpers-for-seniors-living-alone.html">AI helpers for seniors who live alone</a> lists the privacy questions to ask first.</p>"""
F2 = [("Is ChatGPT or other AI spying on me?","Not in the sense of secretly watching you. But online AI services receive and usually store what you type and upload, under their privacy policies. You can turn off training on your chats in settings, and avoid sharing private details."),
      ("Can I use AI without sending my data to a company?","Yes. Free software like Ollama runs AI models entirely on your own computer. After the model is downloaded, your chats stay on your PC and it works without internet."),
      ("Which privacy settings should I change?","Look for Settings, then Privacy or Data controls. Turn off using your chats to improve or train the model, review or turn off memory, and use temporary chats for anything sensitive."),
      ("Does deleting a chat erase it completely?","Not always right away. Many services keep deleted chats for a period for safety reviews. Check the company's privacy page for its retention time.")]

# ---------------- 3. Ollama ----------------
MODELS = [
 ("Llama 3.2 (Meta)","llama3.2","1B, 3B","Small, friendly all rounder. Good first model on an older PC.","Fast","Basic","8GB"),
 ("Llama 3.1 (Meta)","llama3.1","8B","Solid everyday helper for writing and questions.","Medium","Good","16GB"),
 ("Qwen 3 / Qwen 3.5 (Alibaba)","qwen3, qwen3.5","0.6B to 235B","Very capable all rounders. Qwen 3.5 can also look at pictures. Many languages.","Varies","Good to very good","8 to 32GB+"),
 ("Gemma 3 / Gemma 4 (Google)","gemma3, gemma4","1B to 31B","Clear writing and can read pictures. Gemma 4 is the newest.","Varies","Good to very good","8 to 32GB"),
 ("Mistral (Mistral AI)","mistral","7B","Quick, plain spoken helper. Mistral Small 24B is the bigger sibling.","Fast","Good","16GB"),
 ("Phi 4 / Phi 4 mini (Microsoft)","phi4, phi4-mini","3.8B, 14B","Small but good at math and reasoning.","Fast (mini)","Good","8 to 16GB"),
 ("DeepSeek-R1","deepseek-r1","1.5B to 671B","A 'thinking' model. It reasons step by step before answering. Slower, better for tricky problems.","Slow","Very good at logic","16 to 32GB (8B to 14B)"),
 ("LLaVA, Qwen VL, Gemma 3 (vision)","llava, qwen3-vl, gemma3","2B to 34B","Look at a photo and describe it, or read the text in it.","Medium","Good","8 to 16GB"),
 ("Qwen 2.5 Coder, Qwen 3 Coder","qwen2.5-coder","0.5B to 32B","Writes and fixes computer code.","Medium","Good at code","16 to 32GB"),
 ("Embedding models","nomic-embed-text, embeddinggemma","Tiny","Not for chatting. They help apps search your own notes and documents.","Very fast","N/A","Any"),
]
def mtable():
    r = "".join(f'<tr><td><strong>{n}</strong><br><code>{c}</code></td><td>{s}</td><td>{w}</td><td>{sp}</td><td>{sm}</td><td>{ram}</td></tr>' for n,c,s,w,sp,sm,ram in MODELS)
    return f'<div class="tbl"><table><thead><tr><th>Model family</th><th>Sizes</th><th>What it is good at</th><th>Speed</th><th>Smarts</th><th>Computer memory</th></tr></thead><tbody>{r}</tbody></table></div>'
TASKS = [("Chat, questions, writing emails","llama3.1:8b or qwen3:8b","llama3.2:3b on an 8GB PC"),
 ("Read a letter or describe a photo","gemma3:4b or qwen2.5vl:7b","llava:7b"),
 ("Math, planning, tricky logic","deepseek-r1:8b or phi4","deepseek-r1:14b if you have 32GB"),
 ("Help writing or fixing code","qwen2.5-coder:7b","qwen2.5-coder:14b with 32GB"),
 ("Translate or other languages","qwen3:8b","gemma3:12b"),
 ("Old or slow computer","llama3.2:3b or phi4-mini","gemma3:1b"),
 ("Search your own documents","nomic-embed-text (plus an app like Open WebUI)","embeddinggemma")]
def ttable():
    r="".join(f"<tr><td><strong>{a}</strong></td><td><code>{b}</code></td><td><code>{c}</code></td></tr>" for a,b,c in TASKS)
    return f'<div class="tbl"><table><thead><tr><th>I want to...</th><th>Try first</th><th>Also good</th></tr></thead><tbody>{r}</tbody></table></div>'
P3 = """<div class="calm"><p><strong>The short version:</strong> Ollama is a free program that lets you run AI on your own computer, privately. Think of it like a record player. Ollama is the player. The "models" are the records. You pick a record for the job you want done.</p></div>
<h2>What is Ollama, in plain words?</h2>
<p>Ollama is free software for Windows, Mac and Linux. You install it like any other program. Then you download an AI "model," which is the actual brain file. After that, everything runs on your computer.</p>
<ul class="big-list"><li><strong>Private:</strong> your words never leave your PC.</li><li><strong>Free:</strong> no monthly bill.</li><li><strong>Works offline:</strong> no internet needed once a model is downloaded.</li></ul>
<p>Ollama has its own simple chat window, so you can type questions right away. Step by step setup is in our <a href="/local-ai/install-ollama-open-webui-windows.html">Windows install guide</a>.</p>
<h2>What is a "model"?</h2>
<p>A model is the file that holds what the AI learned. Different companies make different models, and each has its own strengths. Some are better at writing, some at pictures, some at code.</p>
<h2>What do the numbers mean? (size vs speed vs smarts)</h2>
<p>You will see names like <code>llama3.2:3b</code> or <code>qwen3:14b</code>. The "b" stands for <strong>billion</strong>. It is the number of "parameters," which is a rough measure of how much the model learned.</p>
<div class="tbl"><table><thead><tr><th>Size</th><th>Speed</th><th>Smarts</th><th>Memory needed (roughly)</th></tr></thead><tbody>
<tr><td><strong>1B to 4B</strong> (small)</td><td>Fast, even on older PCs</td><td>Fine for simple questions and short writing</td><td>Fits on 8GB computers</td></tr>
<tr><td><strong>7B to 9B</strong> (medium)</td><td>Good on most modern PCs</td><td>The sweet spot for everyday help</td><td>16GB is comfortable</td></tr>
<tr><td><strong>12B to 14B</strong> (large)</td><td>Slower without a graphics card</td><td>Noticeably smarter and more careful</td><td>32GB, or a 12GB+ graphics card</td></tr>
<tr><td><strong>27B to 32B</strong> (very large)</td><td>Slow unless you have a strong graphics card</td><td>Close to the online services for many tasks</td><td>32GB+ and a 16GB to 24GB graphics card</td></tr>
</tbody></table></div>
<p>A simple rule: a model needs about <strong>0.6GB of memory for every billion</strong> parameters in the usual download size. More detail in <a href="/local-ai/how-much-ram-vram-for-ollama.html">How much RAM and VRAM for Ollama</a>.</p>
<h2>Which model does what</h2>
<p>These are popular families in the <a href="https://ollama.com/library" target="_blank" rel="noopener">Ollama model library</a>, checked """ + CHECKED + """. New ones arrive every few weeks. The <code>code</code> name is what you type to download it.</p>
""" + mtable() + """
<p class="meta">Source: <a href="https://ollama.com/library" target="_blank" rel="noopener">ollama.com/library</a>, checked """ + CHECKED + """. Sizes are the versions listed there. Memory guide assumes the default download.</p>
<h2>What fits on my computer?</h2>
<ul class="big-list"><li><strong>8GB of memory:</strong> stick to small models: <code>llama3.2:3b</code>, <code>gemma3:4b</code>, <code>phi4-mini</code>, <code>qwen3:4b</code>.</li><li><strong>16GB:</strong> the 7B to 9B models run well: <code>llama3.1:8b</code>, <code>qwen3:8b</code>, <code>mistral</code>, <code>deepseek-r1:8b</code>.</li><li><strong>32GB:</strong> step up to 12B to 14B: <code>gemma3:12b</code>, <code>qwen3:14b</code>, <code>phi4</code>, <code>deepseek-r1:14b</code>.</li></ul>
<p>Not sure how much memory you have? On Windows, press <strong>Ctrl + Shift + Esc</strong>, click <strong>Performance</strong>, then <strong>Memory</strong>. The number at the top right is your total.</p>
<h2>Pick by task</h2>
""" + ttable() + """
<h2>Special helpers worth knowing about</h2>
<ul class="big-list"><li><strong>"Thinking" models</strong> like DeepSeek-R1 show their reasoning before the answer. Good for puzzles and planning. Slower.</li><li><strong>Vision models</strong> can look at a photo you give them. Handy for reading small print on a label or a letter.</li><li><strong>Embedding models</strong> work behind the scenes so an app can search your own files. You do not chat with them.</li><li><strong>One model per job is fine.</strong> Many people keep a small fast model for quick questions and a bigger one for careful work.</li></ul>
<h2>Your first 3 steps</h2>
<ol class="big-list"><li>Download Ollama from <a href="https://ollama.com" target="_blank" rel="noopener">ollama.com</a> and install it.</li><li>Open it and choose a small model like <code>gemma3:4b</code> or <code>llama3.2:3b</code>.</li><li>Type a question in plain words. That is it.</li></ol>"""
F3 = [("Is Ollama free?","Yes. Ollama is free software. The models in its library are free to download. You only need a computer to run them on."),
      ("Does Ollama send my chats to the internet?","When you use a model downloaded to your computer, the chat runs on your PC. Ollama also offers optional cloud models, which do go online, so pick a regular downloaded model if privacy matters."),
      ("Which Ollama model should a beginner start with?","On an 8GB computer, try llama3.2:3b or gemma3:4b. With 16GB, llama3.1:8b or qwen3:8b are good everyday helpers."),
      ("What does 8b or 14b mean in a model name?","It means 8 billion or 14 billion parameters, a rough measure of the model's size. Bigger models are usually smarter but slower and need more memory.")]

# ---------------- 4. Accessibility ----------------
P4 = """<div class="calm"><p><strong>The short version:</strong> Some of the most useful AI is already built into your phone and computer, for free. It may help you read small print, follow conversations, type without a keyboard, and remember things. It is not perfect, and it does not replace advice from your doctor or an occupational therapist, but it is worth trying.</p></div>
<p>Each section below lists free tools first. Features change, so names may look a little different on your device.</p>
<h2>Low vision: reading and seeing</h2>
<ul class="big-list"><li><strong>Seeing AI</strong> (free from Microsoft, iPhone and Android). Point your camera at mail, a menu or a label and it reads it out loud. It can also describe a photo or a scene.</li><li><strong>Be My Eyes</strong> (free). Its "Be My AI" feature describes photos and documents. It can also connect you to a volunteer by video for a quick hand.</li><li><strong>Built into your phone:</strong> Magnifier turns the camera into a magnifying glass. Spoken content reads the screen aloud (Speak Screen on iPhone, Select to Speak on Android).</li><li><strong>Built into Windows:</strong> Magnifier (Windows key + plus sign) and Narrator (Windows key + Ctrl + Enter), which reads the screen. On Windows 11, Narrator can describe images with Copilot when you ask it to.</li><li><strong>Private option:</strong> on your own PC, Ollama with a vision model like <code>gemma3:4b</code> can read a photo of a letter without uploading it anywhere. See <a href="/ai-for-beginners/what-is-ollama.html">What is Ollama?</a></li></ul>
<h2>Hearing loss: live captions</h2>
<ul class="big-list"><li><strong>Windows 11 Live Captions</strong> puts words on screen for any sound playing on your PC, like video calls and YouTube. Turn it on with Windows key + Ctrl + L. Microsoft says the audio is processed on your device and not sent to the cloud. It can also caption your microphone for in-person chats.</li><li><strong>Phones:</strong> Live Caption on Android and Live Captions on iPhone caption videos, calls and more. Android's Live Transcribe captions a conversation in the room.</li><li>Captions can mishear names and accents. Use them as help, not as a record you rely on for important details.</li></ul>
<h2>Arthritis, tremors and limited mobility</h2>
<ul class="big-list"><li><strong>Windows Voice Access</strong> lets you open apps, click, scroll and type by talking. It works offline on Windows 11.</li><li><strong>Dictation:</strong> press Windows key + H on any PC to type by speaking. On phones, tap the microphone on the keyboard.</li><li><strong>Voice Control (iPhone) and Voice Access (Android)</strong> run the whole phone by voice.</li><li>Ask your occupational therapist which setup suits your hands. They may also suggest a large-key keyboard or a stand that holds a tablet at the right angle.</li></ul>
<h2>Memory: reminders and notes</h2>
<ul class="big-list"><li>Ask your phone's assistant: <em>"Remind me to take my pills at 8 AM every day."</em></li><li>Use an AI chat to turn a messy list into a clear checklist: <em>"Make this into a simple daily list."</em></li><li>Ask AI to summarize a doctor visit from your own notes, then check it with the office.</li><li>Keep a simple notes app with a big font. Many let you add notes by voice.</li><li>Reminders support your memory. They do not replace medication systems your pharmacist or doctor recommends.</li><li>Live alone, or worried about someone who does? See <a href="/ai-for-beginners/ai-helpers-for-seniors-living-alone.html">AI helpers for seniors who live alone</a>: talking tablets, daily check-in calls and camera-free sensors.</li></ul>
<h2>Dyslexia and reading or writing difficulty</h2>
<ul class="big-list"><li><strong>Immersive Reader</strong> (in Microsoft Edge, Word and OneNote) reads text aloud, highlights each word and can space out lines.</li><li><strong>Read aloud</strong> in Edge reads any web page to you.</li><li>Ask an AI chat: <em>"Rewrite this letter in short, simple sentences"</em> or <em>"Fix my spelling but keep my words."</em></li></ul>
<h2>Honest limits</h2>
<ul class="big-list"><li>AI may misread small print, numbers or handwriting. Check anything important, like doses, amounts due and dates.</li><li>Nothing here is medical advice. These tools may help day to day. Ask your doctor or an occupational therapist what fits your needs.</li><li>Online AI features send what they see or hear to a company. For private paperwork, use the on-device options above or local AI.</li></ul>
<div class="warn"><h2>Stay safe: scams and fake voices</h2>
<ul class="big-list"><li>Scammers can now copy a voice from a short clip. If a "family member" calls in trouble and needs money now, hang up and call them back on their usual number.</li><li>Agree on a family "safe word" that only you know.</li><li>No real bank, government office or tech company will ask for your password, PIN or full card number by phone, text or chat.</li><li><strong>Never give bank information to an AI, a caller or a pop-up.</strong> If unsure, call the number on the back of your card.</li></ul></div>"""
F4 = [("What free AI tools help people with low vision?","Seeing AI and Be My Eyes are free apps that read text and describe photos. Phones and Windows also have built-in Magnifier and screen readers like Narrator."),
      ("Does Windows have free live captions?","Yes. Windows 11 Live Captions shows captions for audio playing on your PC and can caption your microphone. Turn it on with Windows key + Ctrl + L. Microsoft says the audio is processed on the device."),
      ("Can I control my computer by voice?","Yes. Windows 11 Voice Access lets you open apps, click and type by speaking. Windows key + H starts dictation in any text box. iPhone and Android have similar voice control."),
      ("Is AI a replacement for medical or therapy advice?","No. These tools may help with daily tasks, but ask your doctor or an occupational therapist what fits your situation.")]

GEAR_ALL = [("USB speakerphone or microphone","Clearer voice typing and video calls. A speakerphone is easy if headsets are uncomfortable.","USB speakerphone for computer"),
            ("Large-button keyboard","Big, high contrast keys that are easier to see and press.","large print keyboard high contrast"),
            ("Document camera or webcam","Holds steady over a letter so reading apps get a clear picture.","document camera USB"),
            ("Tablet stand","Holds a tablet or phone at eye level, so you do not need to grip it.","adjustable tablet stand"),
            ("Small mini PC for private AI","A quiet little computer that can run local AI like Ollama, if your current PC is too old.","mini PC 32GB RAM")]

# ---------------- 5. AI on your phone ----------------
APP = lambda href, label: f'<a href="{href}" target="_blank" rel="noopener">{label}</a>'
P5 = f"""<div class="calm"><p><strong>The short version:</strong> Your phone can do AI two ways. It can send your words to a big AI on the internet, or it can run a small AI right on the phone, private and even with no signal. Small phone AI is handy for quick jobs. For bigger, smarter AI at home, use your computer.</p></div>
<h2>Two kinds of AI on a phone</h2>
<div class="tbl"><table><thead><tr><th></th><th>Online assistant apps</th><th>AI that runs on the phone itself</th></tr></thead><tbody>
<tr><td><strong>Examples</strong></td><td>ChatGPT, Gemini, Copilot, Grok and Claude apps</td><td>PocketPal AI, Private LLM, Locally AI, and parts of Apple Intelligence and Gemini Nano</td></tr>
<tr><td><strong>Where your words go</strong></td><td>Sent over the internet to the company</td><td>Stay on your phone</td></tr>
<tr><td><strong>Works with no signal</strong></td><td>No</td><td>Yes, once the model is downloaded</td></tr>
<tr><td><strong>How smart</strong></td><td>The smartest</td><td>Fine for short, simple jobs</td></tr>
<tr><td><strong>Battery</strong></td><td>Light</td><td>Heavy. The phone gets warm.</td></tr>
</tbody></table></div>
<h2>Built into your phone already</h2>
<ul class="big-list">
<li><strong>iPhone: Apple Intelligence.</strong> Writing help, summaries and photo clean up, much of it on the phone itself. Needs an iPhone 15 Pro or 15 Pro Max, or any iPhone 16 or newer. {APP("https://www.apple.com/apple-intelligence/", "Apple's page")}.</li>
<li><strong>Android: Gemini Nano.</strong> Google's small on-phone AI. It powers things like summaries, proofreading and smart replies on newer high-end phones, such as Pixel 9 and newer and Samsung Galaxy S25 and newer. Which features you get depends on the phone. {APP("https://developer.android.com/ai/gemini-nano", "Google's page")}.</li>
</ul>
<h2>Free apps that run AI on the phone itself</h2>
<p>These download a small AI model onto your phone. After that, your chats stay on the phone and work in airplane mode.</p>
<div class="tbl"><table><thead><tr><th>App</th><th>Phones</th><th>What it is like</th><th>Get it</th></tr></thead><tbody>
<tr><td><strong>PocketPal AI</strong></td><td>iPhone and Android</td><td>Free. You pick a small model (like Llama 3.2 1B or Gemma) and chat. Good first try.</td><td>{APP("https://apps.apple.com/us/app/pocketpal-ai/id6502579498", "App Store")} &middot; {APP("https://play.google.com/store/apps/details?id=com.pocketpalai", "Google Play")}</td></tr>
<tr><td><strong>Private LLM</strong></td><td>iPhone and iPad (also Mac)</td><td>Paid once, no subscription. Polished and simple.</td><td>{APP("https://apps.apple.com/us/app/private-llm-local-ai-chat/id6448106860", "App Store")} &middot; {APP("https://privatellm.app/", "Website")}</td></tr>
<tr><td><strong>Locally AI</strong></td><td>iPhone and iPad</td><td>Free. Clean and easy.</td><td>{APP("https://apps.apple.com/us/app/locally-ai-local-ai-chat/id6741426692", "App Store")}</td></tr>
<tr><td><strong>Google AI Edge Gallery</strong></td><td>Android</td><td>Free, from Google. Try small Gemma models on your phone. A bit more techy.</td><td>{APP("https://play.google.com/store/apps/details?id=com.google.ai.edge.gallery", "Google Play")}</td></tr>
</tbody></table></div>
<p class="meta">Checked {CHECKED}. App names and prices can change. Always get apps from the official App Store or Google Play.</p>
<h2>What a phone can handle</h2>
<ul class="big-list">
<li><strong>Small models only.</strong> Phones run tiny models, about 1 to 4 billion "parameters" (think: brain size). They are good for short notes, simple questions and rewording. They make more mistakes than big AI.</li>
<li><strong>Memory matters.</strong> A phone with 6GB of memory can run the smallest models. 8GB or more is better. Most phones from the last two or three years at the higher end have 8GB or more.</li>
<li><strong>Storage.</strong> Each model takes about 1 to 3GB of space on your phone.</li>
<li><strong>Battery and heat.</strong> Running AI on the phone works it hard. It uses battery fast and gets warm. That is normal. Plug in for long chats, and take it out of a thick case if it gets hot.</li>
</ul>
<h2>Privacy, in plain words</h2>
<ul class="big-list">
<li>On-phone apps keep your chats on the phone. Good for private notes and health questions.</li>
<li>Online assistant apps send what you type to the company. Do not type passwords, card numbers or your Social Security number. More in {APP("/ai-for-beginners/is-ai-spying-on-me.html", "Is AI spying on me?").replace(' target="_blank" rel="noopener"', '')}.</li>
<li>Only install apps from the official App Store or Google Play.</li>
</ul>
<h2>Try it: your first phone AI</h2>
<ol class="big-list"><li>Install <strong>PocketPal AI</strong> from your app store.</li><li>Open it and download the smallest model it suggests. Use Wi-Fi; it is a big download.</li><li>Turn on airplane mode, then ask:</li></ol>
<p class="say">"Write a short thank you note to my neighbor for watching my dog."</p>
<p>It answers with no internet at all. That is AI running on your phone.</p>
<h2>For bigger AI, use your computer</h2>
<p>A home computer has much more memory than a phone, so it can run AI that is a lot smarter, still private. Our free tool checks your PC or Mac in about a minute.</p>
<p><a class="btn" href="/check-my-pc/">Check my PC or Mac &rarr;</a></p>"""
F5 = [("Can my phone run AI without the internet?","Yes, with an app that runs AI on the phone, such as PocketPal AI, Private LLM or Locally AI. Download a small model once over Wi-Fi, and after that it works in airplane mode."),
      ("Is AI on my phone private?","On-phone apps keep your chats on the phone. Online assistant apps like ChatGPT or Gemini send what you type to the company. Never type passwords or card numbers into any AI."),
      ("Which phones have built-in AI?","Apple Intelligence needs an iPhone 15 Pro or 15 Pro Max, or an iPhone 16 or newer. Google's Gemini Nano runs on newer high-end Android phones, such as Pixel 9 and newer and Samsung Galaxy S25 and newer."),
      ("Why does my phone get hot when running AI?","Running an AI model works the phone's chip hard, like a big game. Warmth and faster battery use are normal. Plug in for long chats."),
      ("Is phone AI as smart as ChatGPT?","No. Phones can only run small models, so answers are simpler and make more mistakes. For smarter private AI, a home computer works much better. Try our free Check My PC tool.")]

# ---------------- 6. AI helpers for seniors who live alone ----------------
SRC = {
 "joy_pr":"https://www.einpresswire.com/article/950902772/onscreen-releases-joytablet-7-to-help-seniors-and-people-with-i-dd-live-more-independently-and-reduce-loneliness",
 "joy_blog":"https://onscreeninc.com/blogs/news/joytablet-7-0",
 "joy_site":"https://joytablet.com/",
 "loved_pr":"https://www.prnewswire.com/news-releases/kindable-launches-loved-an-ai-powered-care-app-that-calls-seniors-daily--keeps-families-connected-302901363.html",
 "loved_site":"https://loved.co/",
 "hmd":"https://intouch.family/en/blog/hmd-2660-flip-senior-edition-mary-ai-companion",
 "havn_pr":"https://www.prnewswire.com/news-releases/cortekai-launches-havn-a-home-wellness-service-that-helps-older-adults-live-independently-302915601.html",
 "havn_site":"https://www.havnwellness.com/",
}
def S(k, label): return f'<a href="{SRC[k]}" target="_blank" rel="noopener">{label}</a>'
P6_TOP = '<p class="disc">Affiliate note: as an Amazon Associate I earn from qualifying purchases, at no extra cost to you. No company on this page paid to be included. We only list a price when the maker shows it on its own website, checked October 30, 2026.</p>'
P6 = f"""<div class="calm"><p><strong>The short answer:</strong> Four new AI helpers arrived in fall 2026 for older adults who live on their own. <strong>JoyTablet 7</strong> turns a tablet you already own into a talking companion with reminders and auto-answer family video calls. <strong>Loved</strong> has an AI voice named Claire phone your loved one on a schedule and send the family a short summary. The <strong>HMD 2660 Flip Senior Edition</strong> puts an AI companion named Mary behind one button, but it is only a small trial in France and the UK. <strong>havn</strong> uses small room sensors with no cameras to spot falls or unusual quiet, and it reaches the US on November 30, 2026. None of them replace family, a doctor or 911.</p></div>
<h2>The four helpers at a glance</h2>
<div class="tbl"><table><thead><tr><th>Helper</th><th>What it is</th><th>What your loved one does</th><th>Where you can get it</th><th>Cost shown by the maker (Oct 30, 2026)</th></tr></thead><tbody>
<tr><td><strong>JoyTablet 7</strong> (ONSCREEN)</td><td>An app that turns an iPad or Android tablet into a talking companion named Joy</td><td>Says "Hey Joy" from across the room. No tapping needed.</td><td>Available now for iPad and Android tablets</td><td>14-day free trial, then $19.99 a month</td></tr>
<tr><td><strong>Loved</strong> (Kindable)</td><td>A family app plus an AI voice named Claire who phones your loved one</td><td>Answers a normal phone call. Works on any cell phone or landline.</td><td>Available now. The family app is on iPhone and Android.</td><td>Free plan has no calls with Claire. Premium is $29.99 a month with 120 minutes of calls, 7-day trial.</td></tr>
<tr><td><strong>HMD 2660 Flip Senior Edition with Mary</strong> (HMD and inTouch)</td><td>A simple flip phone with one button that starts a chat with an AI companion named Mary</td><td>Presses the Mary button and talks.</td><td><strong>Limited trial in France and the UK only.</strong> Not sold in the US.</td><td>Phone &euro;79.90 or &pound;79.99, 5 free hours with Mary, then &euro;19.90 or &pound;16.90 a month</td></tr>
<tr><td><strong>havn</strong> (cortekAI)</td><td>Small plug-in sensors, one per room, that learn the daily routine. No cameras, nothing to wear.</td><td>Nothing. It works in the background. They can also talk to family through the sensor.</td><td>US availability starts November 30, 2026</td><td>Two subscription plans. No price shown on the maker's site yet.</td></tr>
</tbody></table></div>
<h2>JoyTablet 7: a talking companion on a tablet you already own</h2>
<p>ONSCREEN released JoyTablet 7 on October 19, 2026. It is an app, not a new gadget. A family member installs it on an iPad or Android tablet, plugs it in, and the tablet becomes a simple screen built around one person.</p>
<ul class="big-list"><li><strong>"Hey Joy" works hands free.</strong> Your loved one can talk from across the room without touching the screen. That helps with arthritis, shaky hands or low vision.</li><li><strong>Spoken reminders and timers.</strong> One time, daily or weekly, such as "Every day at 9 a.m., remind me to take my pills."</li><li><strong>Music, videos, local news and weather</strong> just by asking. Safe Search is always on.</li><li><strong>Family video calls answer by themselves</strong> when they come from approved family in the ONSCREEN JoyFamily app. Family can also send photos and home screen messages.</li><li><strong>Also built for people with intellectual and developmental disabilities (I/DD).</strong> ONSCREEN says it co-designed these features with an I/DD service provider.</li></ul>
<p><strong>Good to know:</strong> the tablet needs Wi-Fi, and ONSCREEN's own FAQ says Joy is an AI, not a person, and "not a substitute for a caregiver or emergency help." Check that your tablet is on the compatible list in the App Store or Google Play before you start the trial.</p>
<p class="meta">Sources: {S("joy_blog","ONSCREEN's JoyTablet 7.0 announcement")}, {S("joy_pr","ONSCREEN press release (EIN Presswire, Oct 21, 2026)")}, {S("joy_site","joytablet.com")} for the trial and monthly price.</p>
<h2>Loved: Claire calls every day and tells the family how it went</h2>
<p>Kindable launched the Loved app on October 8, 2026. Your loved one does not need a smartphone or any new device. Claire, an AI voice, simply calls at the times your family picks.</p>
<ul class="big-list"><li><strong>A friendly daily check-in call.</strong> Claire asks about sleep, mood, appetite and medicines, gives reminders, and remembers earlier calls.</li><li><strong>A short summary goes to the family</strong>, who Kindable calls the "care circle." The app tracks changes over time.</li><li><strong>Needs turn into to-do items.</strong> If your mom mentions a leaking faucet or a ride to the doctor, it becomes a shared task the family can claim.</li><li><strong>Missed-call alerts</strong> let the family know if a call was not answered.</li><li>Your loved one can also call Claire any time of day.</li></ul>
<p><strong>Good to know:</strong> the free plan has no calls with Claire. The calls are part of Premium, which includes 120 minutes of calls a month. Loved says full call transcripts are stored but not viewable in the app by anyone, and the family sees only summaries, based on permissions the account owner sets. Loved says it gives observational insight, not medical advice.</p>
<p class="meta">Sources: {S("loved_pr","Kindable press release (PR Newswire, Oct 8, 2026)")}, {S("loved_site","loved.co")} for plans, prices and the privacy FAQ.</p>
<h2>HMD 2660 Flip Senior Edition with Mary: one button, but not in the US</h2>
<p>HMD and inTouch announced this phone on October 21, 2026. It is a familiar flip phone with one extra button. Press it and Mary, an AI companion, starts a conversation. She can answer questions, help recall information and simply chat, 24 hours a day.</p>
<p><strong>Important:</strong> this is a <strong>limited-edition trial in France and the UK only</strong>. It is not sold in the US. We include it because it shows where this is heading: AI help on a phone older adults already know how to use.</p>
<p><strong>Good to know:</strong> inTouch says conversations are encrypted and stored in the EU under GDPR, and personal data is not sold or used for advertising. They also say plainly that "Mary is a companion, not an emergency service."</p>
<p class="meta">Source: {S("hmd","inTouch announcement with HMD (Oct 21, 2026)")}, which also lists the trial prices.</p>
<h2>havn: camera-free sensors that notice when something is wrong</h2>
<p>cortekAI announced havn on October 26, 2026. It is different from the others. It is not mainly a chat companion. You put one small sensor in each room your loved one uses. It learns their normal routine from motion and sound, then alerts family and caregivers if something changes, such as a fall or an unusual stretch of no activity.</p>
<ul class="big-list"><li><strong>No cameras, nothing to wear, nothing to charge.</strong> The maker's site also says no conversations are recorded.</li><li><strong>Serious alerts go to caregivers first, then emergency services (EMS)</strong>, according to cortekAI.</li><li><strong>Family can talk into the room</strong> through the sensor, and leave voice reminders.</li><li><strong>Setup takes minutes per room</strong> with an app, no tools needed.</li></ul>
<p><strong>Good to know:</strong> havn will be available in the US starting <strong>November 30, 2026</strong>, from havnwellness.com and through partners like home care agencies. There are two plans, Essentials (up to four sensors) and Whole House (no limit). The maker has not posted prices yet, so ask before you sign up.</p>
<p class="meta">Sources: {S("havn_pr","cortekAI press release (PR Newswire, Oct 26, 2026)")}, {S("havn_site","havnwellness.com")}.</p>
<div class="warn"><h2>Questions to ask before you sign up</h2>
<ol class="big-list"><li><strong>Privacy:</strong> Is anything recorded? Where is it stored, and for how long? Is it ever sold or used for ads? Can we delete it?</li><li><strong>Who hears the calls:</strong> Which family members see summaries or transcripts? Can any company staff listen in? Does my loved one know, and agree, that family will get updates?</li><li><strong>Monthly cost:</strong> What is the price after the free trial? Is there a limit on minutes or sensors? How do I cancel, and is there a contract?</li><li><strong>Emergencies:</strong> What happens if my loved one falls or says they feel sick? Does it call anyone, or only send an app alert? Most AI companions are <em>not</em> emergency services. Keep a real medical alert plan in place.</li><li><strong>Internet and power:</strong> What happens if the Wi-Fi or power goes out?</li><li><strong>Comfort:</strong> Will my loved one feel cared for, or watched? Ask them first. A helper they agreed to is one they will actually use.</li></ol></div>
<h2>None of these run privately on your own PC</h2>
<p>All four helpers work through the company's online service. What your loved one says, or what the sensors notice, goes to that company under its privacy policy. That is normal for this kind of service, but it is worth knowing. Read more in <a href="/ai-for-beginners/is-ai-spying-on-me.html">Is AI spying on me?</a></p>
<p>If privacy matters most, the private alternative is AI that runs on a computer at home, where nothing leaves the house. It will not phone anyone or watch for falls, but it can chat, read letters out loud and help with reminders and notes. Start with <a href="/ai-for-beginners/what-is-ollama.html">What is Ollama?</a> or our <a href="/local-ai/">Local AI hub</a>. For free tools already on your phone or PC, see <a href="/ai-for-beginners/ai-for-seniors-and-disabilities.html">AI that helps with vision, hearing, hands and memory</a>.</p>
<h2>Blake's honest take</h2>
<p>I live alone too, with my cat. If I were choosing for a parent, I would start with the one that asks the least of them. Loved works on the phone they already have. JoyTablet reuses a tablet in the drawer. havn asks nothing at all once it is set up. Whatever you pick, use the free trial, sit with your loved one for the first few days, and keep calling them yourself. These are helpers, not replacements for you.</p>"""
F6 = [("What is the best AI helper for a senior who lives alone?","It depends on what they are comfortable with. Loved works on any phone or landline because Claire simply calls. JoyTablet 7 suits someone who would enjoy a talking tablet with video calls from family. havn suits families who mainly want to know about falls or unusual quiet, without cameras. Start with a free trial and ask your loved one first."),
      ("Is the HMD flip phone with Mary available in the US?","No. As of October 30, 2026, the HMD 2660 Flip Senior Edition with Mary is a limited-edition trial in France and the UK only."),
      ("When can I get havn in the US?","cortekAI says havn will be available in the US starting November 30, 2026, directly at havnwellness.com and through partners such as in-home care agencies. Prices were not posted on the maker's site when we checked."),
      ("Can these AI helpers call 911?","Do not count on it. ONSCREEN says Joy is not a substitute for emergency help, and inTouch says Mary is not an emergency service. cortekAI says havn escalates critical alerts to caregivers first, then EMS. Keep a real emergency plan in place either way."),
      ("Do these AI helpers keep what my parent says private?","They all work through the company's online service, so the company handles the data under its privacy policy. Loved says full transcripts are not viewable in its app and family see summaries. inTouch says Mary's conversations are encrypted and stored in the EU. havn says it uses no cameras and records no conversations. For fully private AI, use local AI on your own computer.")]
P6_LIST = {"@context":"https://schema.org","@type":"ItemList","name":"AI helpers for seniors who live alone, fall 2026","itemListElement":[
  {"@type":"ListItem","position":1,"name":"JoyTablet 7 (ONSCREEN)","url":"https://joytablet.com/"},
  {"@type":"ListItem","position":2,"name":"Loved app with Claire (Kindable)","url":"https://loved.co/"},
  {"@type":"ListItem","position":3,"name":"HMD 2660 Flip Senior Edition with Mary (HMD and inTouch)","url":"https://intouch.family/en/blog/hmd-2660-flip-senior-edition-mary-ai-companion"},
  {"@type":"ListItem","position":4,"name":"havn (cortekAI)","url":"https://www.havnwellness.com/"}]}
GEAR6 = [("Android tablet","JoyTablet runs on a compatible Android tablet. Check the app's compatibility list before you buy.","Android tablet 10 inch"),
         ("iPad","JoyTablet also runs on a compatible iPad. An older iPad already in a drawer may work.","Apple iPad"),
         ("Tablet stand","Keeps the tablet upright on a counter so Joy and video calls are easy to see.","adjustable tablet stand"),
         ("Big-button amplified phone","Loved's Claire calls any phone or landline. A loud, simple phone helps if hearing is a problem.","amplified big button phone for seniors")]

# ---------------- 7. Local memory partner for cloud AI ----------------
def X(href, label): return f'<a href="{href}" target="_blank" rel="noopener">{label}</a>'
P7_TOP = """<div class="calm"><p><strong>The short answer:</strong> Cloud AI assistants forget. They see only a small slice of your history at the start of each chat, so they repeat mistakes you already corrected, then apologize. A <strong>local memory partner</strong> is an AI you run on your own PC. It keeps your full project history privately and hands your cloud AI a short, sourced brief before each job. It will not stop every mistake, but it should stop many of the repeat ones.</p></div>
"""
P7 = f"""<h2>The problem: your cloud AI only sees a small slice</h2>
<p>Cloud AI assistants often load only a little memory when a new chat starts, such as the last few days plus a handful of key facts. Older notes may be saved somewhere, but the assistant only looks them up when it thinks to. When it does not, a lesson you taught it weeks ago never comes up.</p>
<p><strong>A real example from my own setup.</strong> My cloud assistants (Grok Bot) hold about 700 saved notes, but each chat starts with only the latest few days plus key facts. On October 31, 2026, I had to correct them on all of these in one day:</p>
<div class="tbl"><table><thead><tr><th>What the bot did</th><th>What I had already decided</th></tr></thead><tbody>
<tr><td>Suggested YouTube for a news video on my news site</td><td>Host the video file myself on GitHub Pages with a plain HTML5 player</td></tr>
<tr><td>Put my news site's signoff line in my lawn business posts</td><td>That signoff belongs to the news site only</td></tr>
<tr><td>Left the service towns out of the lawn posts and wrote "even in the rain"</td><td>Name the towns, skip the rain wording</td></tr>
<tr><td>Gave time estimates in human "days"</td><td>No human day estimates</td></tr>
<tr><td>Said "that's exactly why" after being corrected</td><td>Just fix it, do not spin it</td></tr>
</tbody></table></div>
<p>Every one led to an apology and a redo. The bot was not lazy. It simply did not have those old decisions in front of it.</p>

<h2>I am not the only one noticing</h2>
<blockquote><p>"The Apology: that's one thing AI agents and chatbots have nailed, annoyingly so!"</p><p class="meta">AmberMac, The AmberMac Show with @jeffmacarthur, on X, October 31, 2026. {X("https://x.com/ambermac/status/2116506582947115451","See the post")}</p></blockquote>
<p>Long-term memory for AI is a busy area right now. A few examples I came across while researching this:</p>
<ul class="big-list"><li><strong>Mem0</strong> shut down its OpenMemory project on July 29, 2026.</li><li><strong>Graphiti</strong> stores facts with dates attached, so it can tell old facts from new ones.</li><li><strong>Basic Memory</strong> keeps memory as plain Markdown files plus a small SQLite database on your own computer.</li><li>People on X are talking about a "swappable second brain" that works across different AI providers. {X("https://x.com/lindavivah/status/2081781884074311957","Example post")}.</li></ul>

<h2>What is a local memory partner?</h2>
<p>It is an AI assistant you run on your own PC. You name it whatever you like, and you can build your own. It keeps your full project history privately on your computer and hands your cloud AI a short brief before each job. The cloud AI still does the heavy lifting online. The local partner is its long-term memory.</p>
<p><strong>Mine is named Kellie</strong>, and this guide uses her as the example. Kellie runs on a free local AI program called <a href="/ai-for-beginners/what-is-ollama.html">Ollama</a> with a desktop app. She drafts posts, makes images, handles reminders, reads files and does voice work, and her memory stays on my computer.</p>

<h2>How it works, step by step</h2>
<ol class="big-list">
<li><strong>Your cloud AI gets a job.</strong> For example, "write this week's lawn posts."</li>
<li><strong>It asks the local partner for a one-page brief</strong> about that project before it starts.</li>
<li><strong>The local partner answers with sourced rules and history.</strong> It quotes what it stored, with dates and where it came from. If something is missing, it says "not in memory" instead of guessing.</li>
<li><strong>The cloud AI does the job.</strong></li>
<li><strong>It sends a short job report back.</strong> The local partner files it by project: decisions, rules, failures, files and next steps, each with a date and a source.</li>
</ol>
<p><strong>One important rule:</strong> only your own words become confirmed rules. The bots can report what happened, but they cannot write rules for you.</p>

<h2>Before and after</h2>
<div class="tbl"><table><thead><tr><th></th><th>Before</th><th>With a local memory partner</th></tr></thead><tbody>
<tr><td><strong>Start of a job</strong></td><td>Recent days plus key facts</td><td>A one-page brief for this project</td></tr>
<tr><td><strong>Older lessons</strong></td><td>Found only if the bot thinks to search</td><td>Pulled into the brief</td></tr>
<tr><td><strong>Missing info</strong></td><td>The bot may guess</td><td>Says "not in memory"</td></tr>
<tr><td><strong>Where rules come from</strong></td><td>Mixed</td><td>Only your own words</td></tr>
</tbody></table></div>

<h2>My build: what Kellie's memory looks like</h2>
<ul class="big-list">
<li><strong>Hardware:</strong> my everyday home PC with an NVIDIA RTX 2060 (6GB). Not a special AI machine. Not sure what yours can run? Try our free <a href="/check-my-pc/">Check My PC</a> tool.</li>
<li><strong>Light on the graphics card:</strong> the memory search runs on a tiny "embedding" model, not the big chat model, so it does not fight my games for the GPU.</li>
<li><strong>Tested on paper first:</strong> I had the design attacked in 4 rounds of "how could this go wrong" review, and 10 problems were fixed before any code was written.</li>
</ul>
<p><strong>Three practice briefs</strong> I ran against the design, and what each one pulled up:</p>
<div class="tbl"><table><thead><tr><th>Job</th><th>What the brief surfaced</th></tr></thead><tbody>
<tr><td>Publish a news flash video</td><td>The rule to host the video file myself on GitHub Pages</td></tr>
<tr><td>Write lawn business posts</td><td>No news-site signoff, name the service towns, no rain wording</td></tr>
<tr><td>Test Kellie</td><td>Keep her window visible, no games running, do not close my window</td></tr>
</tbody></table></div>
<p><strong>Status as of October 31, 2026:</strong> the design (version 0.2) is done and the first working version is being built. Next come a memory tab in Kellie's desktop app, loading in past project history, and connecting my other bots.</p>

<div class="warn"><h2>Honest limits</h2>
<ul class="big-list"><li><strong>It reduces repeat mistakes. It will not end every error or every apology.</strong> A brief only helps if the right rule was stored and the cloud AI actually follows it.</li><li><strong>It is only as good as what goes in.</strong> If you never stated a rule, it cannot be in memory.</li><li><strong>This is a build-it-yourself project today.</strong> Mine is still being built. There is no one-click app for this yet.</li><li><strong>Private stays private only on your side.</strong> The memory lives on your PC, but whatever goes into a brief is sent to your cloud AI for that job. Keep passwords and account numbers out of it.</li><li><strong>Your PC has to be on</strong> for the cloud AI to ask it for a brief.</li></ul></div>

<h2>Want to try this yourself?</h2>
<ol class="big-list"><li>Start with a local AI. Our guide <a href="/ai-for-beginners/what-is-ollama.html">What is Ollama?</a> explains it in plain words, and <a href="/local-ai/install-ollama-open-webui-windows.html">this setup guide</a> walks through installing it on Windows.</li><li>Keep one simple notes file per project with your rules and decisions, in your own words, with a date on each.</li><li>Before each job, paste the short version into your cloud AI, or have your local AI write that short version for you.</li><li>After each job, add what changed. That habit is the heart of it, whatever tools you use.</li></ol>
<p>Curious about privacy in general? Read <a href="/ai-for-beginners/is-ai-spying-on-me.html">Is AI spying on me?</a> or visit our <a href="/local-ai/">Local AI hub</a>.</p>
"""
F7 = [("Why does my AI keep apologizing for the same mistakes?","Most cloud AI assistants only load a small slice of memory at the start of each chat. Lessons you taught it earlier may be saved but never looked up, so the same mistake comes back."),
      ("What is a local memory partner?","An AI assistant you run on your own PC that keeps your full project history privately and gives your cloud AI a short, sourced brief before each job. You can name it anything and build your own."),
      ("Will this stop every AI mistake?","No. It should cut down repeat mistakes, but it will not end every error or apology. It only helps when the right rule was stored and the cloud AI follows it."),
      ("Do I need an expensive PC?","Not for the memory part. Blake's build runs on an everyday PC with an RTX 2060 (6GB), using a tiny embedding model for memory search. Try the free Check My PC tool to see what yours can do."),
      ("Is my data private?","The memory stays on your own PC. Whatever goes into a brief is sent to your cloud AI for that job, so keep passwords and account numbers out of it.")]

# ---------------- Hub ----------------
CARDS = [("what-is-ai.html","bulb","Start here","What is AI, really?","A plain-words explanation. What it can and cannot do, and the honest truth about the scary headlines."),
         ("is-ai-spying-on-me.html","shield","Privacy","Is AI spying on me?","What companies keep, which settings to turn off, and how to use AI with nothing leaving your computer."),
         ("what-is-ollama.html","box","Free and private","What is Ollama? Models explained","Run AI on your own PC. Which model does what, and what fits 8, 16 or 32GB."),
         ("ai-for-seniors-and-disabilities.html","heart","Everyday help","AI that helps with vision, hearing, hands and memory","Free tools that may help you read mail, follow conversations and type by voice."),
         ("ai-on-your-phone/","phone","On the go","AI on your phone","Which phone AI is built in, free apps that run AI on the phone itself, and what a phone can handle."),
         ("ai-helpers-for-seniors-living-alone.html","home","New this fall","AI helpers for seniors who live alone","JoyTablet 7, daily calls from Claire, the Mary flip phone and camera-free havn sensors, with questions to ask first."),
         ("local-ai-memory-for-cloud-ai.html","spark","New: memory","Give your cloud AI a long-term memory","Why cloud AI keeps repeating mistakes, and how a local AI on your own PC can hand it a short brief before each job.")]
def icon(n):
    paths={"bulb":'<path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z"/>',
           "shield":'<path d="M12 2l8 4v6c0 5-3.5 9-8 10-4.5-1-8-5-8-10V6z"/><path d="M9 12l2 2 4-4"/>',
           "phone":'<rect x="6" y="2" width="12" height="20" rx="2.5"/><path d="M11 18h2"/>',
           "home":'<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>',
           "heart":'<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8z"/>'}
    if n in paths: return f'<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths[n]}</svg>'
    return svg(n)
FH = [("I am nervous about AI. Where should I start?","Start with What is AI, really? It explains in plain words what AI is, what it cannot do, and how to stay safe. You can go at your own pace."),
      ("Do I have to buy anything?","No. Everything on these pages can be tried with free tools on the phone or computer you already own.")]
def hub():
    url=BASE; t="AI for Beginners: A Gentle, Honest Introduction | AI Pick Vault"
    d="New to AI or worried about it? Plain-words guides on what AI is, privacy, free private AI with Ollama, and tools that help with vision, hearing and mobility."
    il={"@context":"https://schema.org","@type":"ItemList","name":"AI for Beginners guides","itemListElement":[{"@type":"ListItem","position":i+1,"name":c[3],"url":BASE+c[0]} for i,c in enumerate(CARDS)]}
    hd=head(t,d,url,ld([crumbs("AI for Beginners",url),il,faq_ld(FH)])).replace('property="og:type" content="article"','property="og:type" content="website"').replace('<a href="/local-ai/" class="on">','<a href="/local-ai/">').replace('<a href="/ai-for-beginners/">','<a href="/ai-for-beginners/" class="on">')
    cards='<div class="grid two">'+"".join(f'<a class="card" href="/ai-for-beginners/{f}"><div class="ico">{icon(i)}</div><p class="kicker" style="margin-top:8px">{k}</p><h3>{h}</h3><p>{p}</p><span class="go">Read, at your own pace &rarr;</span></a>' for f,i,k,h,p in CARDS)+'</div>'
    body=f"""<section class="hero"><div class="wrap"><p class="kicker"><a href="/">Home</a> &middot; AI for Beginners</p>
<h1>New to AI? Start here, gently.</h1>
<p class="lead">Plenty of people feel uneasy about AI. That is normal. These short guides explain what it really is, what it is not, and how it may make everyday life a little easier. Plain words, no jargon, no pressure.</p>
<div class="cta-row"><a class="btn" href="/ai-for-beginners/what-is-ai.html">Start with the basics</a><a class="btn ghost" href="/ai-for-beginners/is-ai-spying-on-me.html">Worried about privacy?</a></div>
<div class="pills"><span>Plain words</span><span>Honest about limits</span><span>Free tools first</span></div></div></section>
<main class="wrap"><div class="beginner">
<div class="calm"><p><strong>A note from Blake:</strong> I am 56 and I have been fixing things for people for 47 years. I am learning AI too. I built these pages for folks like my neighbors and family, people who are smart and capable but were never told what this stuff actually is. Take your time.</p></div>
<a class="card feature" href="/check-my-pc/"><div class="ico">{icon("chip")}</div><div><p class="kicker">Free, private tool</p><h3>Can my computer run AI at home?</h3><p>Our gentle Check My PC tool looks at your computer's memory and graphics, in plain words, and tells you what it can do and what (if anything) to upgrade. Nothing to download. Nothing leaves your computer.</p><span class="go">Check my PC &rarr;</span></div></a>
<h2>Seven short guides</h2>
{cards}
{gear(GEAR_ALL)}
{faq_html(FH)}
{DISC}
</div></main>
"""
    (ROOT/"ai-for-beginners"/"index.html").write_text(hd+body+foot("Helpful extra: USB speakerphone","USB speakerphone for computer"),encoding="utf-8")

def build():
    page("what-is-ai.html","What Is AI, Really? A Gentle Beginner's Guide | AI Pick Vault","What is AI, really?",
         "A plain-words guide to what AI really is, what it can and cannot do, myths vs facts about spying and takeover, and how to use it safely.",
         "A calm, plain-words explanation for anyone who feels unsure about AI. No jargon, no hype.",
         P1+gear(GEAR_ALL[:1]+GEAR_ALL[3:4]),F1,("Helpful extra: USB speakerphone","USB speakerphone for computer"))
    page("is-ai-spying-on-me.html","Is AI Spying on Me? An Honest Privacy Guide | AI Pick Vault","Is AI spying on me?",
         "An honest, plain-words AI privacy guide: what online AI companies keep, settings to turn off, and how local AI with Ollama keeps everything on your own PC.",
         "An honest answer, without scare stories or sales talk. What really happens to what you type, and how to keep it private.",
         P2+gear(GEAR_ALL[4:5]),F2,("Private AI box: mini PC","mini PC 32GB RAM"))
    page("what-is-ollama.html","What Is Ollama? AI Models in Plain Words | AI Pick Vault","What is Ollama? The AI models explained",
         "What Ollama is in plain words, which model does what (Llama, Qwen, Gemma, Mistral, DeepSeek), what fits 8, 16 or 32GB, and how to pick by task.",
         "Free, private AI on your own computer, explained without the jargon. Plus which model to use for which job.",
         P3+yt_embed(276, kicker="Watch: run AI on your own PC", note="This part shows installing Ollama. Scroll back to the start for what hardware you need.")+gear(GEAR_ALL[4:5]),F3,("Private AI box: mini PC","mini PC 32GB RAM"))
    page("ai-for-seniors-and-disabilities.html","AI for Seniors and Disabilities: Free Tools | AI Pick Vault","AI that may help with vision, hearing, hands and memory",
         "Honest ways AI may help with low vision, hearing loss, limited mobility, memory and dyslexia: free tools like Seeing AI, Be My Eyes and Live Captions.",
         "Free, practical tools for reading mail, following conversations, typing by voice and remembering things. With honest limits.",
         P4+gear(GEAR_ALL[:4]),F4,("Helpful extra: document camera","document camera USB"))
    page("ai-on-your-phone/index.html","AI on Your Phone: Private, Free and Offline | AI Pick Vault","AI on your phone",
         "AI on your phone in plain words: built-in Apple Intelligence and Gemini Nano, free apps that run AI on the phone itself and offline, what phones can handle, battery and privacy.",
         "What your phone can already do, free apps that keep AI private on the phone, and when to use your computer instead.",
         P5,F5,("Bigger private AI: mini PC","mini PC 32GB RAM"))
    page("ai-helpers-for-seniors-living-alone.html","AI Helpers for Seniors Who Live Alone (Fall 2026) | AI Pick Vault","AI helpers for seniors who live alone: what's new in fall 2026",
         "JoyTablet 7, Loved's daily calls from Claire, the HMD flip phone with Mary and havn's camera-free sensors, in plain words, plus questions to ask first.",
         "A plain-words look at four new AI companions and check-in services for older adults living on their own, for seniors and the family who worry about them.",
         P6+gear(GEAR6),F6,("JoyTablet needs a tablet","Android tablet 10 inch"),extra_ld=[P6_LIST],published="2026-10-30",modified="2026-10-30",top=P6_TOP)
    page("local-ai-memory-for-cloud-ai.html","Give Your Cloud AI a Long-Term Memory With Local AI | AI Pick Vault","How to give your cloud AI a long-term memory with a local AI on your PC",
         "Cloud AI forgets and apologizes. A local memory partner on your PC keeps your project history and hands it a short brief before each job. Honest limits.",
         "Why cloud AI keeps repeating mistakes you already corrected, and how a local AI on your own PC can be its long-term memory. With my real build as the example.",
         P7,F7,("Run local AI: mini PC","mini PC 32GB RAM"),published="2026-10-31",modified="2026-10-31",top=P7_TOP,og="https://aipickvault.com/images/og-local-ai-memory.png")
    hub(); print("ok")

if __name__=="__main__": build()
