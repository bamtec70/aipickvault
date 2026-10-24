#!/usr/bin/env python3
"""Build the gentle AI for Beginners hub (/ai-for-beginners/) and its 4 guides."""
import json, sys, html
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from build_local_ai import head, foot, btn, amz, REL, DISC, ROOT, svg

BASE = "https://aipickvault.com/ai-for-beginners/"
CHECKED = "October 2026"
TRUSTB = """<div class="trust"><div class="ic">""" + svg("wrench") + """</div><div><p><strong>Who writes this:</strong> Blake, the guy behind AI Pick Vault. He has spent 47 years fixing things and sorting out PCs for regular people. He is 56 and still learning AI too, so these pages explain things the way he wishes someone had explained them to him.</p><p class="meta">Some links go to Amazon. As an Amazon Associate we earn from qualifying purchases, at no extra cost to you. You never need to buy anything to use the free tools on these pages.</p></div></div>"""

def ld(objs): return "\n".join(f'<script type="application/ld+json">{json.dumps(o)}</script>' for o in objs)
def crumbs(name, url):
    items=[("Home","https://aipickvault.com/"),("AI for Beginners",BASE)] + ([(name,url)] if url!=BASE else [])
    return {"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":i+1,"name":n,"item":u} for i,(n,u) in enumerate(items)]}
def faq_ld(faq): return {"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":q,"acceptedAnswer":{"@type":"Answer","text":a}} for q,a in faq]}
def faq_html(faq): return '<h2>Common questions</h2><div class="faq">' + "".join(f"<details><summary>{html.escape(q)}</summary><p>{html.escape(a)}</p></details>" for q,a in faq) + "</div>"
def art_ld(title, desc, url): return {"@context":"https://schema.org","@type":"Article","headline":title,"description":desc,"url":url,"dateModified":"2026-10-23","author":{"@type":"Person","name":"Blake"},"publisher":{"@type":"Organization","name":"AI Pick Vault"}}

def gear(items):
    rows = "".join(f'<div class="gear-item"><h3>{n}</h3><p>{w}</p><a class="btn sm" href="{amz(q)}" {REL}>See options on Amazon</a></div>' for n,w,q in items)
    return f'<section class="gear"><p class="kicker">Optional, only if it helps</p><h2>Gear that can make this easier</h2><p>You do not need any of this to get started. These are simple add-ons that people often find helpful. Read reviews and check the return policy first.</p><div class="gear-grid">{rows}</div></section>'

NEXT = [("what-is-ai.html","What is AI, really?"),("is-ai-spying-on-me.html","Is AI spying on me?"),("what-is-ollama.html","What is Ollama? Models explained"),("ai-for-seniors-and-disabilities.html","AI that helps with vision, hearing, hands and memory")]
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
def page(fn, title, h1, desc, lead, body, faq, sticky):
    url = BASE + fn
    hd = head(title, desc, url, ld([crumbs(h1,url), art_ld(h1,desc,url)] + ([faq_ld(faq)] if faq else [])))
    hd = hd.replace('<a href="/local-ai/" class="on">','<a href="/local-ai/">').replace('<a href="/ai-for-beginners/">','<a href="/ai-for-beginners/" class="on">')
    out = f"""<section class="hero"><div class="wrap"><p class="kicker"><a href="/">Home</a> &middot; <a href="/ai-for-beginners/">AI for Beginners</a></p>
<h1>{h1}</h1><p class="lead">{lead}</p><p class="meta">Last checked {CHECKED}. Written in plain words. No question is silly.</p></div></section>
<main class="wrap"><article class="beginner">
{label_tables(body)}
{faq_html(faq) if faq else ""}
{TRUSTB}
{nextnav(fn)}
{DISC}
</article></main>
"""
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
<ol class="big-list"><li>Do not type anything into online AI you would not put in an email to a stranger.</li><li>Never share passwords, bank or card numbers, or your Social Security number with any AI.</li><li>Black out account numbers before you photograph a letter for AI to read.</li><li>For private things, use local AI on your own computer.</li></ol>"""
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
<ul class="big-list"><li>Ask your phone's assistant: <em>"Remind me to take my pills at 8 AM every day."</em></li><li>Use an AI chat to turn a messy list into a clear checklist: <em>"Make this into a simple daily list."</em></li><li>Ask AI to summarize a doctor visit from your own notes, then check it with the office.</li><li>Keep a simple notes app with a big font. Many let you add notes by voice.</li><li>Reminders support your memory. They do not replace medication systems your pharmacist or doctor recommends.</li></ul>
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

# ---------------- Hub ----------------
CARDS = [("what-is-ai.html","bulb","Start here","What is AI, really?","A plain-words explanation. What it can and cannot do, and the honest truth about the scary headlines."),
         ("is-ai-spying-on-me.html","shield","Privacy","Is AI spying on me?","What companies keep, which settings to turn off, and how to use AI with nothing leaving your computer."),
         ("what-is-ollama.html","box","Free and private","What is Ollama? Models explained","Run AI on your own PC. Which model does what, and what fits 8, 16 or 32GB."),
         ("ai-for-seniors-and-disabilities.html","heart","Everyday help","AI that helps with vision, hearing, hands and memory","Free tools that may help you read mail, follow conversations and type by voice.")]
def icon(n):
    paths={"bulb":'<path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z"/>',
           "shield":'<path d="M12 2l8 4v6c0 5-3.5 9-8 10-4.5-1-8-5-8-10V6z"/><path d="M9 12l2 2 4-4"/>',
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
<h2>Four short guides</h2>
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
         P3+gear(GEAR_ALL[4:5]),F3,("Private AI box: mini PC","mini PC 32GB RAM"))
    page("ai-for-seniors-and-disabilities.html","AI for Seniors and Disabilities: Free Tools | AI Pick Vault","AI that may help with vision, hearing, hands and memory",
         "Honest ways AI may help with low vision, hearing loss, limited mobility, memory and dyslexia: free tools like Seeing AI, Be My Eyes and Live Captions.",
         "Free, practical tools for reading mail, following conversations, typing by voice and remembering things. With honest limits.",
         P4+gear(GEAR_ALL[:4]),F4,("Helpful extra: document camera","document camera USB"))
    hub(); print("ok")

if __name__=="__main__": build()
