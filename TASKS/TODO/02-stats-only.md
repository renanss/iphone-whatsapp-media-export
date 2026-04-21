# `--stats-only` — Backup Report Without Extracting

## What
Add a `--stats-only` flag that prints a full report of the backup without copying any files.

## Why
Users want to understand what's in their backup before committing to a full extraction — total size, files per contact, date range, type breakdown.

## How
- Skip all file copying
- Query `Manifest.db` + `ChatStorage.sqlite` and print:
  - Total files per type (img, video, audio, doc)
  - Total size per type
  - Top contacts by file count
  - Date range of the backup (earliest → latest message)
  - Files per year/month

## Notes
- Faster than `--dry-run` — no need to iterate files individually
- Could optionally export to CSV/JSON with `--stats-output report.json`
