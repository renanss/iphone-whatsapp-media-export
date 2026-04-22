# QA — Task 12: Android Backup Support

**Branch:** `feature/12-android-support`
**PR:** https://github.com/renanss/iphone-whatsapp-media-export/pull/2
**Dev completed by:** Agent 2

---

## What was built

- Added `whatsapp_extractor/android_extractor.py` for Android WhatsApp media extraction from `msgstore.db`, `wa.db`, and filesystem media.
- Added root entry point `extract_android.py` with Android CLI flags mirroring the iPhone extractor where applicable.
- Runtime schema introspection supports common `messages`, `chat_list`, contact, timestamp, direction, and media-path column variants.
- Reused existing package helpers for file types, destination paths, metadata writing, and file type detection.
- Updated `README.md` with Android usage and the `--platform android` detection note.

---

## Definition of Done

- [ ] `python3 extract_android.py --help` shows `--backup`, `--output`, `--dry-run`, `--contact`, `--from`, `--to`, `--type`, `--exclude-type`, `--random`, and `--inspect-db`.

  Tester note: paste the help output or confirm all listed flags are present.

- [ ] `PYTHONPYCACHEPREFIX=/tmp/wa-feature-12-pycache python3 -m py_compile extract_android.py whatsapp_extractor/android_extractor.py` succeeds.

  Tester note: this should exit with no output and no Python syntax/import errors.

- [ ] With a local Android WhatsApp folder containing `msgstore.db`, `wa.db`, and `Media/`, `python3 extract_android.py --backup /path/to/WhatsApp --dry-run` finds media and prints destination paths without copying files.

  Tester note: confirm the log prints `msgstore.db`, `wa.db` when present, one or more media folders, `Media selected`, and destination paths marked `(dry-run)`.

- [ ] Contact filtering works with contact names from `wa.db` and with raw JIDs as a fallback.

  Tester note: run one test with `--contact` matching a display name and one with a JID/phone fragment; both should reduce `Media selected`.

- [ ] Date filtering with `--from YYYY-MM-DD --to YYYY-MM-DD` includes only media in the requested range.

  Tester note: compare the printed destination filenames/month folders against the requested range; rows with no timestamp should be excluded when a date range is set.

- [ ] File type filtering with `--type img video audio doc webp gif` and `--exclude-type` includes/excludes the expected extensions.

  Tester note: run at least one positive filter such as `--type img` and one exclusion such as `--exclude-type audio`; selected files should match the expected extensions.

- [ ] A real non-dry-run extraction copies files into the same contact/month folder structure as the iPhone extractor and writes metadata via `set_rich_metadata`.

  Tester note: verify files are created under `<output>/<contact>/<YYYY-MM>/` or `<output>/_Documents/<contact>/<YYYY-MM>/`, and check filesystem timestamp/metadata on at least one copied file.
