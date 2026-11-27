"""Shared Ko-fi / donation markup for AI Pick Vault.

Keep this module, the layout builders, and the built HTML in sync.
tests/test_kofi_links.py fails the build if ko-fi.com/bamtx drops out of
the header, footer, or support block.
"""

KOFI_URL = "https://ko-fi.com/bamtx"
KOFI_GOAL_TITLE = "Help Kellie help seniors"
KOFI_GOAL_TEXT = (
    "If a guide or pick helped you, a tip on Ko-fi goes toward an $800, 16GB "
    "graphics card so Kellie can keep helping seniors who live alone learn AI safely."
)
KOFI_BTN_LABEL = "Support this site on Ko-fi"
KOFI_NAV_LABEL = "Support"
KOFI_STICKY_LABEL = "Support on Ko-fi"

KOFI_NAV = (
    f'<a class="kofi-nav" href="{KOFI_URL}" target="_blank" rel="noopener">'
    f"{KOFI_NAV_LABEL}</a>"
)

KOFI_NAV_TW = (
    f'<a class="kofi-nav-tw inline-block rounded-full bg-sky-500 hover:bg-sky-400 '
    f'text-slate-950 font-semibold px-3 py-1.5 text-sm whitespace-nowrap" '
    f'href="{KOFI_URL}" target="_blank" rel="noopener">{KOFI_NAV_LABEL}</a>'
)

KOFI_BTN = (
    f'<a class="btn kofi" href="{KOFI_URL}" target="_blank" rel="noopener">'
    f"{KOFI_BTN_LABEL}</a>"
)

KOFI_BTN_SM = (
    f'<a class="btn sm kofi" href="{KOFI_URL}" target="_blank" rel="noopener">'
    f"{KOFI_STICKY_LABEL}</a>"
)

KOFI_BTN_TW = (
    f'<a class="inline-block rounded-full bg-sky-500 hover:bg-sky-400 text-slate-950 '
    f'font-semibold px-5 py-2" href="{KOFI_URL}" target="_blank" rel="noopener">'
    f"{KOFI_BTN_LABEL}</a>"
)

KOFI_BLOCK = f"""<aside class="kofi-block" aria-label="Support this site">
<p class="kicker">Support the work</p>
<h2>{KOFI_GOAL_TITLE}</h2>
<p>{KOFI_GOAL_TEXT}</p>
<p>{KOFI_BTN}</p>
</aside>
"""

KOFI_BLOCK_TW = f"""
    <aside class="kofi-block-tw mt-10 rounded-2xl border border-sky-500/40 bg-gradient-to-br from-sky-500/10 to-amber-500/10 p-6 text-center" aria-label="Support this site">
      <p class="uppercase tracking-[0.14em] text-xs font-semibold text-sky-400 mb-2">Support the work</p>
      <h2 class="text-xl font-bold text-white mb-2">{KOFI_GOAL_TITLE}</h2>
      <p class="text-slate-300 mb-4 leading-relaxed">{KOFI_GOAL_TEXT}</p>
      <p>{KOFI_BTN_TW}</p>
    </aside>
"""

KOFI_FOOTER_INNER = f"""<div class="kofi-wrap">
<p class="kofi-goal"><strong>{KOFI_GOAL_TITLE}.</strong> Tips go toward an $800, 16GB graphics card so Kellie can keep helping seniors who live alone learn AI safely.</p>
<p>{KOFI_BTN}</p>
</div>
"""

KOFI_FOOTER_INNER_TW = f"""      <p class="text-slate-300">{KOFI_GOAL_TITLE}. Tips go toward an $800, 16GB graphics card so Kellie can keep helping seniors who live alone learn AI safely.</p>
      <p>{KOFI_BTN_TW}</p>
"""
