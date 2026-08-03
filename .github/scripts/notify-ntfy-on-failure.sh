#!/usr/bin/env bash
# Send a short ntfy push with job failure details only.
# Requires env: NTFY_TOPIC (required), NTFY_TOKEN (optional),
#               NTFY_TITLE, GITHUB_REPOSITORY, GITHUB_RUN_ID, GITHUB_SERVER_URL
set -euo pipefail

if [ -z "${NTFY_TOPIC:-}" ]; then
  echo "NTFY_TOPIC not set — skip phone notify"
  exit 0
fi

TITLE="${NTFY_TITLE:-AI Pick Vault: check failed}"
RUN_URL="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:-}/actions/runs/${GITHUB_RUN_ID:-}"

# Prefer audit report errors if present (name products by description, not ASIN alone)
BODY=""
if [ -f ebay-worker/_audit/report.json ]; then
  BODY=$(python3 - <<'PY'
import json
import re
from pathlib import Path

def site_names():
    p = Path("index.html")
    if not p.is_file():
        return {}
    html = p.read_text(encoding="utf-8", errors="replace")
    out = {}
    for m in re.finditer(r'asin:\s*"([^"]+)"\s*,\s*name:\s*"((?:\\.|[^"\\])*)"', html):
        out[m.group(1)] = m.group(2).replace('\\"', '"').strip()
    return out

p = Path("ebay-worker/_audit/report.json")
try:
    d = json.loads(p.read_text(encoding="utf-8"))
except Exception as e:
    print(f"Could not read audit report: {e}")
    raise SystemExit(0)
names = site_names()
errs = d.get("errors") or []
lines = []
for e in errs[:8]:
    asin = e.get("asin") or "?"
    label = (
        e.get("productName")
        or e.get("q")
        or names.get(asin)
        or asin
    )
    lines.append(f"• {label}")
    lines.append(f"  [{e.get('code')}] ASIN {asin}")
    msg = str(e.get("message") or "")[:120]
    if msg:
        lines.append(f"  {msg}")
if not lines:
    lines.append("Job failed (see Actions run). No ERROR rows in audit report.")
print("\n".join(lines))
if len(errs) > 8:
    print(f"…and {len(errs) - 8} more")
print(f"\nupdatedAt: {d.get('snapshotUpdatedAt')}")
print(f"ebayOk: {d.get('ebayOk')}/{d.get('catalogSize')}")
PY
  ) || BODY="Job failed. Open the Actions run for details."
else
  BODY="Job failed before/without an audit report. Open the Actions run for logs."
fi

BODY="${BODY}"$'\n\n'"Run: ${RUN_URL}"

# ntfy limits: keep under ~4k; trim if needed
BODY=$(printf '%s' "$BODY" | head -c 3500)

AUTH_ARGS=()
if [ -n "${NTFY_TOKEN:-}" ]; then
  AUTH_ARGS=(-H "Authorization: Bearer ${NTFY_TOKEN}")
fi

curl -fsS \
  -H "Title: ${TITLE}" \
  -H "Priority: high" \
  -H "Tags: warning,aipickvault" \
  "${AUTH_ARGS[@]}" \
  -d "$BODY" \
  "https://ntfy.sh/${NTFY_TOPIC}"

echo "ntfy notify sent"
