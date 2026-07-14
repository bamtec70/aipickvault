import json
import re
from pathlib import Path

html = Path(__file__).resolve().parents[1].joinpath("index.html").read_text(encoding="utf-8")
blocks = re.findall(
    r'asin:\s*"([^"]+)"\s*,\s*name:\s*"((?:\\.|[^"\\])*)"',
    html,
)
items = []
for asin, name in blocks:
    name = name.replace('\\"', '"').replace("\\'", "'")
    items.append({"id": asin, "q": name})

out = Path(__file__).with_name("catalog.json")
out.write_text(json.dumps(items, indent=2), encoding="utf-8")
print(f"Wrote {len(items)} products to {out}")
