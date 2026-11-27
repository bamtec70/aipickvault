#!/usr/bin/env python3
"""Visual QA: python3 visual_qa.py <base_url> [outdir]. Reads <base>/sitemap.xml.
Also fails if the Ko-fi donation link or "Help Kellie help seniors" goal is missing."""
import sys, re, os, urllib.request
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
base = sys.argv[1].rstrip('/'); out = sys.argv[2] if len(sys.argv) > 2 else '/workspace/apv/qa'
os.makedirs(out, exist_ok=True)
sm = urllib.request.urlopen(base + '/sitemap.xml').read().decode()
paths = [urlparse(u).path or '/' for u in re.findall(r'<loc>(.*?)</loc>', sm)]
JS = r"""() => {
 const r=[]; const W=document.documentElement.clientWidth;
 if (document.documentElement.scrollWidth > W+1) r.push(['overflow', 'scrollWidth '+document.documentElement.scrollWidth+' > '+W]);
 const cont = el => { let p=el.parentElement; while(p && p!==document.body){const s=getComputedStyle(p); if(s.display!=='contents' && p.getBoundingClientRect().width>0) return p; p=p.parentElement;} return document.body; };
 const desc = el => el.tagName.toLowerCase()+(el.id?'#'+el.id:'')+(el.className&&typeof el.className==='string'?'.'+el.className.trim().split(/\s+/).join('.'):'');
 document.querySelectorAll('video, figure, .card, section > h2, .sec > h2, main > h2').forEach(el=>{
  const b=el.getBoundingClientRect(); if(!b.width||getComputedStyle(el).visibility==='hidden') return;
  const c=cont(el); const cb=c.getBoundingClientRect(); const cs=getComputedStyle(c);
  const L=cb.left+parseFloat(cs.paddingLeft), R=cb.right-parseFloat(cs.paddingRight);
  // skip grid/flex row items (multiple siblings side-by-side): check centre only if element is alone on its row
  const sibs=[...c.children].filter(s=>s!==el && s.getBoundingClientRect().width>0 && Math.abs(s.getBoundingClientRect().top-b.top)<4);
  if (sibs.length) return;
  if (el.tagName==='H2' && getComputedStyle(el).textAlign!=='center' && b.width>=R-L-2) return; // full-width left heading is fine
  const d=Math.abs((b.left+b.right)/2-(L+R)/2);
  if (d>8) r.push(['off-center', desc(el)+' off by '+d.toFixed(0)+'px']);
 });
 document.querySelectorAll('img').forEach(i=>{ if(i.complete && i.naturalWidth===0 && i.getAttribute('loading')!=='lazy') r.push(['broken-img', i.src]); });
 document.querySelectorAll('a[href*="amazon."]').forEach(a=>{ if(!a.href.includes('tag=wethepeopl0b9-20')) r.push(['untagged-amazon', a.href]);
   const rel=(a.rel||''); if(!/nofollow/.test(rel)||!/sponsored/.test(rel)) r.push(['bad-rel', a.href]); });
 const path=location.pathname;
 if (path.indexOf('td-player')===-1) {
   const kofi=[...document.querySelectorAll('a[href*="ko-fi.com/bamtx"]')];
   if (!kofi.length) r.push(['missing-kofi', 'no ko-fi.com/bamtx link']);
   else {
     const inChrome=kofi.some(a=>a.closest('header, nav'));
     if (document.querySelector('header, nav') && !inChrome) r.push(['missing-kofi-nav', 'Ko-fi link not in header or nav']);
     const body=document.body.innerText||'';
     const needsGoal=/^\/$|^\/index\.html$|\/local-ai\/|\/ai-for-beginners\/|\/picks\/|\/check-my-pc\/|\/about\/|contact\.html|deals\.html/.test(path);
     if (needsGoal && body.indexOf('Help Kellie help seniors')===-1) r.push(['missing-kofi-goal', 'Help Kellie help seniors not visible']);
   }
 }
 return r; }"""
fails = 0; lines = []
with sync_playwright() as p:
    br = p.chromium.launch()
    for w in (390, 1280):
        ctx = br.new_context(viewport={'width': w, 'height': 900})
        for path in paths:
            pg = ctx.new_page(); errs = []
            pg.on('console', lambda m: m.type == 'error' and errs.append(m.text))
            pg.on('pageerror', lambda e: errs.append(str(e)))
            bad = []
            pg.on('response', lambda r: r.request.resource_type == 'image' and r.status >= 400 and bad.append(r.url))
            pg.goto(base + path, wait_until='networkidle')
            pg.evaluate("()=>document.querySelectorAll('img[loading=lazy]').forEach(i=>i.loading='eager')")
            pg.wait_for_timeout(400)
            iss = pg.evaluate(JS) + [['console', e] for e in errs] + [['broken-img', u] for u in bad]
            name = (path.strip('/').replace('/', '_').replace('.html', '') or 'home') + f'_{w}.png'
            pg.screenshot(path=f'{out}/{name}', full_page=True)
            st = 'PASS' if not iss else 'FAIL'; fails += bool(iss)
            lines.append(f'{st} {w:>4} {path}  ->  {out}/{name}')
            lines += [f'      [{k}] {v}' for k, v in iss]
            pg.close()
        ctx.close()
    br.close()
print('\n'.join(lines)); print(f'\nRESULT: {"PASS" if not fails else "FAIL"} ({fails} page/width combos with issues, {len(paths)*2} checked)')
sys.exit(1 if fails else 0)
