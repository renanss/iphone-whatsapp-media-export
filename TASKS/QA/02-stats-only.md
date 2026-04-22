# QA — `--stats-only`: Backup Report Without Extracting

**Branch:** `feature/stats-report-export`
**PR:** https://github.com/renanss/iphone-whatsapp-media-export/pull/TBD
**Dev completed by:** Agent 2

---

## What was built

- Added `--stats-only` to print aggregate backup stats without copying files.
- Stats include total files, total known size, date range, files by type, top contacts/groups, and files by month.
- Stats mode reuses the same filters as extraction before aggregating results.
- Stats mode can write JSON or CSV via `--report`.

---

## Definition of Done

- [ ] `python3 extract_whatsapp_media.py --help` shows `--stats-only`.

  Tester note: help should describe it as an aggregate report mode that does not copy files.

- [ ] `PYTHONPYCACHEPREFIX=/tmp/wa-stats-report-pycache python3 -m py_compile whatsapp_extractor/cli.py whatsapp_extractor/extractor.py` succeeds.

  Tester note: this should exit with no output and no syntax/import errors.

- [ ] Run `python3 extract_whatsapp_media.py --backup /path/to/backup --output /tmp/wa-stats-test --stats-only`.

  Tester note: output should show `BACKUP STATS`, type totals, top contacts/groups, month totals, and no per-file destination lines.

- [ ] Run `python3 extract_whatsapp_media.py --backup /path/to/backup --stats-only --type img --contact "NAME"`.

  Tester note: filters should apply before the stats are calculated.

- [ ] Confirm `/tmp/wa-stats-test` is not created or changed by stats-only mode unless it is explicitly used as a report parent path.

  Tester note: stats-only should not copy media files.
