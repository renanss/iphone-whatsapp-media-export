# QA — Duplicate Detection

**Branch:** `feature/loop-03-05-09`
**PR:** https://github.com/renanss/iphone-whatsapp-media-export/pull/5
**Dev completed by:** Agent 2

---

## What was built

- Added in-run duplicate detection based on `Manifest.db` `fileID` values.
- Duplicate file IDs are skipped after the first copy or resume skip.
- Duplicate entries are logged as `[DUPLICATE]`.
- Added a `Duplicates skipped` counter to the final report.

---

## Definition of Done

- [ ] Run an extraction against a backup that contains forwarded/repeated media entries with the same `fileID`.

  Tester note: after the first occurrence, repeated entries should log `[DUPLICATE]`.

- [ ] Confirm the final report includes `Duplicates skipped` with the expected count.

  Tester note: duplicates should not increase the `Processed` count.

- [ ] Confirm duplicate files are not copied into additional contact folders.

  Tester note: only the first occurrence of each `fileID` should produce or resume an output file.

- [ ] Run with `--dry-run` and confirm duplicate entries are still identified as `[DUPLICATE]`.

  Tester note: dry-run should not copy files but should still preview duplicate behavior.
