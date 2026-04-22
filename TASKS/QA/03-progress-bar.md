# QA — Progress Bar: Replace Per-File Output

**Branch:** `feature/loop-03-05-09`
**PR:** https://github.com/renanss/iphone-whatsapp-media-export/pull/5
**Dev completed by:** Agent 2

---

## What was built

- Added optional `tqdm` support inside `whatsapp_extractor/extractor.py`.
- Real extractions use a progress bar when `tqdm` is installed.
- If `tqdm` is not installed, extraction falls back to the existing line-by-line output.
- Dry-run and explicit `verbose=True` preserve detailed per-file output for debugging.

---

## Definition of Done

- [ ] `PYTHONPYCACHEPREFIX=/tmp/wa-loop-pycache python3 -m py_compile whatsapp_extractor/extractor.py` succeeds.

  Tester note: this should exit with no output and no syntax/import errors.

- [ ] With `tqdm` installed, run `python3 extract_whatsapp_media.py --backup /path/to/backup --output /tmp/wa-progress-test --type img` and confirm a progress bar is shown instead of a printed line for every copied file.

  Tester note: duplicate, skipped, and not-found messages may still be emitted as progress-safe log lines.

- [ ] Without `tqdm` installed, run the same command and confirm the extractor still uses line-by-line output.

  Tester note: the extractor must not fail if `tqdm` is absent.

- [ ] Run `python3 extract_whatsapp_media.py --backup /path/to/backup --output /tmp/wa-progress-dry --type img --dry-run` and confirm dry-run still prints each destination path.

  Tester note: this preserves the existing dry-run preview behavior.
