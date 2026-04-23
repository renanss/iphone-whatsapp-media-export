# QA — `--since-last-run`: Incremental Extraction

**Branch:** `feature/since-last-run`
**PR:** https://github.com/renanss/whatsapp-media-export/pull/9
**Dev completed by:** Agent 2

---

## What was built
- Added `--since-last-run` to the iPhone and Android extractors.
- Added `.whatsapp_export_state.json` support in the selected output folder.
- Reads the previous `last_run` timestamp and uses it as the effective `--from` date.
- Updates state only after successful non-dry-run extraction runs.
- Prevents ambiguous date input by making `--from` and `--since-last-run` mutually exclusive.
- Documented the new incremental mode in the README.

---

## Definition of Done
- [ ] `python3 extract_whatsapp_media.py --help` shows `[--from YYYY-MM-DD | --since-last-run]`.
- [ ] `python3 extract_android.py --help` shows `[--from YYYY-MM-DD | --since-last-run]`.
- [ ] Running with both `--from 2025-01-01 --since-last-run` exits with an argparse mutual-exclusion error.
- [ ] With no existing `.whatsapp_export_state.json`, `--since-last-run --dry-run` prints that no previous state was found and does not create the state file.
- [ ] With an existing `.whatsapp_export_state.json`, `--since-last-run --dry-run` prints `[INFO] Resuming from last run: <YYYY-MM-DD>` and filters from that date.
- [ ] A successful real extraction with `--since-last-run` writes `<output>/.whatsapp_export_state.json` containing a `last_run` ISO timestamp.
