# Amazon snapshot: detect vs apply (live site)

Two different workflows. Do not mix them up.

| Workflow | What it does | Writes live site? |
|----------|----------------|-------------------|
| **Amazon snapshot watch** | Compares catalog vs live Amazon; fails (exit 1) when prices moved | **No** |
| **Amazon snapshot apply** | Updates `index.html` and **pushes to main** → Pages rebuild | **Yes** |

---

## Button order on GitHub (apply prices to the live site)

1. Open **https://github.com/bamtec70/aipickvault**
2. Click **Actions**
3. Left sidebar → **Amazon snapshot apply**
4. Click **Run workflow**
5. Options:
   - **source**
     - `live-fetch` — re-check Amazon now, then write `index.html` (recommended default)
     - `latest-watch-artifact` — reuse the newest **Amazon snapshot watch** artifact (no re-fetch)
   - **dry_run**
     - leave **unchecked** to commit + push (live site)
     - check **true** to preview only (no push)
6. Click green **Run workflow**
7. Wait for the run to finish **green**
8. Confirm a second run under **pages build and deployment** (GitHub Pages)
9. Hard-refresh the site (**Ctrl+F5**)

After apply succeeds, optional check:

1. Actions → **Amazon snapshot watch** → **Run workflow**
2. Expect **success** / no MATERIAL rows (or only brand-new moves)

---

## Using a report you already downloaded

If you unzipped **amazon-snapshot-watch** from a failed/successful watch run:

```powershell
cd C:\Users\bamte\aipickvault
python ebay-worker\amazon_snapshot_watch.py `
  --index index.html `
  --from-report "C:\path\to\amazon_watch_report.json" `
  --apply
git add index.html
git commit -m "chore: apply Amazon snapshot prices to index.html"
git push
```

Dry-run (no file write):

```powershell
python ebay-worker\amazon_snapshot_watch.py `
  --index index.html `
  --from-report "C:\path\to\amazon_watch_report.json" `
  --apply --dry-run
```

---

## What gets edited

For each **material** ASIN in the report (≥ $2 or ≥ 5% change):

- `price: …`
- `compare.amazon: …`

Only `index.html` is committed by the apply workflow.

---

## Exit codes (watch only)

| Code | Meaning |
|------|---------|
| 0 | Clean / soft-blocked fetch |
| 1 | Material drift detected (**alert**, not auto-apply) |
| 2 | Fetch/infra problem or bad report |

The **apply** workflow does **not** use `--fail-on-material`, so finding drifts and writing them is success.
