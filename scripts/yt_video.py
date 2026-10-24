#!/usr/bin/env python3
"""Full-length AIPickVault YouTube video: responsive embed HTML + VideoObject JSON-LD.
Used by build_home_hub.py, build_local_ai.py and build_beginners.py. build_seo_files.py
reads the VideoObject JSON-LD back out of each page to add <video:video> sitemap entries."""
import html

YT = dict(
    id="QfDnFCl35sw",
    name="Run AI on Your Own PC: What You Actually Need",
    description=("Everything you need to run AI at home: what local AI is, how much RAM and VRAM you need, "
                 "the best models for 16GB, budget GPUs, mini PCs, a budget PC build, and installing Ollama with Open WebUI."),
    upload="2026-10-23T23:47:43-05:00",
    duration="PT5M20S", seconds=320,
    chapters=[(0, "Intro"), (10, "What AI at home is"), (41, "RAM and VRAM needs"), (104, "Models that fit 16GB"),
              (140, "Budget GPU"), (183, "Mini PCs"), (233, "Budget PC build"), (276, "Installing Ollama"),
              (314, "Wrap up and full guides")],
)
WATCH = f"https://www.youtube.com/watch?v={YT['id']}"
SHORT = f"https://youtu.be/{YT['id']}"
EMBED = f"https://www.youtube.com/embed/{YT['id']}"
THUMB = f"https://i.ytimg.com/vi/{YT['id']}/maxresdefault.jpg"

def chapter_name(start):
    return next((n for s, n in YT["chapters"] if s == start), None)

def yt_embed(start=None, kicker="Watch the full video", note=None):
    """Centered responsive 16:9 player with a Watch on YouTube fallback link."""
    src = EMBED + (f"?start={start}" if start else "")
    link = SHORT + (f"?t={start}" if start else "")
    ch = chapter_name(start) if start else None
    lead = note or (f"Starts at the \u201c{html.escape(ch)}\u201d part. Scroll back to watch from the beginning." if ch
                    else "Five minutes, plain words: what you need to run AI on your own PC.")
    return (f'<figure class="yt" id="video"><p class="kicker">{html.escape(kicker)}</p>'
            f'<div class="yt-frame"><iframe src="{src}" title="{html.escape(YT["name"])} (YouTube video)" loading="lazy" '
            f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
            f'referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe></div>'
            f'<figcaption><strong>{html.escape(YT["name"])}</strong> ({YT["seconds"]//60}:{YT["seconds"]%60:02d}). {lead} '
            f'Video not loading? <a href="{link}" target="_blank" rel="noopener">Watch on YouTube</a>.</figcaption></figure>')

def video_ld(page_url=None):
    ch = YT["chapters"]
    parts = []
    for i, (s, n) in enumerate(ch):
        e = ch[i + 1][0] if i + 1 < len(ch) else YT["seconds"]
        parts.append({"@type": "Clip", "name": n, "startOffset": s, "endOffset": e, "url": f"{WATCH}&t={s}"})
    d = {"@context": "https://schema.org", "@type": "VideoObject", "name": YT["name"], "description": YT["description"],
         "thumbnailUrl": [THUMB], "uploadDate": YT["upload"], "duration": YT["duration"],
         "embedUrl": EMBED, "contentUrl": WATCH,
         "publisher": {"@type": "Organization", "name": "AI Pick Vault", "url": "https://aipickvault.com/"},
         "hasPart": parts}
    return d
