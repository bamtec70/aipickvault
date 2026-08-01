# Amazon snapshot: detect vs apply (live site)

Two workflows. Your **PC does not need to be on** — both run on GitHub’s servers.

| Workflow | What it does | Writes live site? | When it runs |
|----------|----------------|-------------------|--------------|
| **Amazon snapshot watch** | Compares catalog vs live Amazon; red X when prices moved | **No** | Schedule (~every 2 days) |
| **Amazon snapshot apply** | Updates `index.html`, **pushes `main`**, Pages rebuilds | **Yes** | **Automatically after watch** finishes, or manual |

You do **not** need to download/unzip artifacts on this computer for day-to-day use. That was only for a one-time manual apply.

---

## Fully automatic (PC off)

1. GitHub runs **Amazon snapshot watch** on a schedule.
2. When that run finishes (even if red from material drift), GitHub starts **Amazon snapshot apply**.
3. Apply reads the watch **artifact** (zip is handled on the runner — no Downloads folder).
4. If there are material price moves and fetch rate is healthy (≥ 35%):
   - edits `index.html`
   - commits + pushes `main`
5. **pages build and deployment** publishes https://aipickvault.com

If there is nothing to change, apply exits cleanly with no push.

---

## Manual buttons (optional)

### A. Apply now (live re-check Amazon)

1. Open **https://github.com/bamtec70/aipickvault**
2. **Actions** → **Amazon snapshot apply**
3. **Run workflow**
4. **source** = `live-fetch`
5. **dry_run** = unchecked
6. Green **Run workflow**

### B. Apply from the latest watch artifact (no re-scrape)

Same as A, but **source** = `latest-watch-artifact`.

### C. Detect only (no site write)

**Actions** → **Amazon snapshot watch** → **Run workflow**.

---

## One-time PC apply from Downloads (not required anymore)

Only if you already unzipped a watch artifact on this machine:

```powershell
cd C:\Users\bamte\aipickvault
python ebay-worker\amazon_snapshot_watch.py `
  --index index.html `
  --from-report "$env:USERPROFILE\Downloads\amazon-snapshot-watch\amazon_watch_report.json" `
  --apply
git add index.html
git commit -m "chore: apply Amazon snapshot prices to index.html"
git push
```

---

## What gets edited

For each **material** ASIN (≥ $2 or ≥ 5% change):

- `price: …`
- `compare.amazon: …`

Only `index.html` is committed by the apply workflow.

---

## Exit codes (watch only)

| Code | Meaning |
|------|---------|
| 0 | Clean / soft-blocked fetch |
| 1 | Material drift (**alert**; apply may still run and update the site) |
| 2 | Fetch/infra problem — apply will **not** write bad prices if rate is low |
