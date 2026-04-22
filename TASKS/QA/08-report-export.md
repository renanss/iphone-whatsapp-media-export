# QA — CSV / JSON Report Export

**Branch:** `feature/stats-report-export`
**PR:** https://github.com/renanss/iphone-whatsapp-media-export/pull/7
**Dev completed by:** Agent 2

---

## What was built

- Added `--report PATH` for `.json` and `.csv` report output.
- JSON reports include a `summary` object and `files` array.
- CSV reports include summary rows followed by per-file rows.
- Extraction reports include file status, contact, JID, type, date, size, direction, source, destination, and file ID.

---

## Definition of Done

- [ ] `python3 extract_whatsapp_media.py --help` shows `--report PATH`.

  Tester note: help should mention `.json` and `.csv`.

- [ ] Run `python3 extract_whatsapp_media.py --backup /path/to/backup --stats-only --report /tmp/wa-report.json`.

  Tester note: validate with `python3 -m json.tool /tmp/wa-report.json`; confirm `summary` and `files` are present.

- [ ] Run `python3 extract_whatsapp_media.py --backup /path/to/backup --output /tmp/wa-report-out --type img --report /tmp/wa-report.csv`.

  Tester note: CSV should start with summary rows, then a `files` header and file rows with statuses such as `copied`, `skipped`, `duplicate`, `not_found`, or `dry_run`.

- [ ] Run `python3 extract_whatsapp_media.py --backup /path/to/backup --dry-run --report /tmp/wa-dry-run-report.json`.

  Tester note: file rows should use status `dry_run` and include planned destination paths.

- [ ] Run `python3 extract_whatsapp_media.py --backup /path/to/backup --stats-only --report /tmp/bad.txt`.

  Tester note: command should fail with `[ERROR] --report path must end with .json or .csv.`
