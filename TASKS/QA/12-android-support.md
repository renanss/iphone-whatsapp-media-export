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
- [ ] `PYTHONPYCACHEPREFIX=/tmp/wa-feature-12-pycache python3 -m py_compile extract_android.py whatsapp_extractor/android_extractor.py` succeeds.
- [ ] With a local Android WhatsApp folder containing `msgstore.db`, `wa.db`, and `Media/`, `python3 extract_android.py --backup /path/to/WhatsApp --dry-run` finds media and prints destination paths without copying files.
- [ ] Contact filtering works with contact names from `wa.db` and with raw JIDs as a fallback.
- [ ] Date filtering with `--from YYYY-MM-DD --to YYYY-MM-DD` includes only media in the requested range.
- [ ] File type filtering with `--type img video audio doc webp gif` and `--exclude-type` includes/excludes the expected extensions.
- [ ] A real non-dry-run extraction copies files into the same contact/month folder structure as the iPhone extractor and writes metadata via `set_rich_metadata`.
