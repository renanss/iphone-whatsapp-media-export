# QA — Resume: Skip Already Extracted Files

**Branch:** `feature/loop-03-05-09`
**PR:** https://github.com/renanss/iphone-whatsapp-media-export/pull/TBD
**Dev completed by:** Agent 2

---

## What was built

- Added default resume behavior in `whatsapp_extractor/extractor.py`.
- Existing destination files are skipped when their size matches the source file.
- Existing destination files with a different size are overwritten instead of skipped.
- Added a `Skipped` counter to the final report.

---

## Definition of Done

- [ ] Run a real extraction once, then run the same command again with the same `--output` path.

  Tester note: the second run should show `[SKIPPED]` entries for files that already exist with matching size.

- [ ] Confirm the second run's final report includes `Skipped` with a non-zero value.

  Tester note: `Processed` should count newly copied files, not already-existing skipped files.

- [ ] Corrupt or truncate one exported file, then rerun the same extraction command.

  Tester note: the mismatched file should be copied again rather than skipped.

- [ ] Confirm repeated runs do not create `_1`, `_2`, or other collision-suffixed copies for normal resume cases.

  Tester note: resume compares against the canonical destination path before collision avoidance.
