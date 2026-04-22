# QA — `--min-size` / `--max-size`: Filter by File Size

**Branch:** `feature/size-group-filters`
**PR:** https://github.com/renanss/iphone-whatsapp-media-export/pull/TBD
**Dev completed by:** Agent 2

---

## What was built

- Added `--min-size` and `--max-size` CLI flags for iPhone extraction.
- Added human-readable size parsing for bare KB values and units like `kb`, `mb`, `gb`, and `tb`.
- Extended `load_message_info()` to include `ZWAMEDIAITEM.ZFILESIZE` when available.
- Added pre-loop size filtering and README examples.

---

## Definition of Done

- [ ] `python3 extract_whatsapp_media.py --help` shows `--min-size` and `--max-size`.

  Tester note: confirm examples mention values such as `500kb` and `10mb`.

- [ ] `PYTHONPYCACHEPREFIX=/tmp/wa-size-group-pycache python3 -m py_compile whatsapp_extractor/cli.py whatsapp_extractor/database.py whatsapp_extractor/extractor.py` succeeds.

  Tester note: this should exit with no output and no syntax/import errors.

- [ ] Run `python3 extract_whatsapp_media.py --backup /path/to/backup --output /tmp/wa-size-test --dry-run --min-size 500kb`.

  Tester note: output should include `Size range filter` and only files at least 500 KB should remain.

- [ ] Run `python3 extract_whatsapp_media.py --backup /path/to/backup --output /tmp/wa-size-test --dry-run --max-size 200kb`.

  Tester note: output should include `Size range filter` and only files at most 200 KB should remain.

- [ ] Run `python3 extract_whatsapp_media.py --backup /path/to/backup --dry-run --min-size 2mb --max-size 1mb`.

  Tester note: command should fail with `[ERROR] --min-size cannot be greater than --max-size.`
