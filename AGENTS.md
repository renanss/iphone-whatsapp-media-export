# Agent Coordination

This file coordinates parallel work between two AI agents on the
`iphone-whatsapp-media-export` project.

Each agent works in its own **git worktree** — a separate directory on disk
that shares the same repo. No shared files, no conflicts, clean PRs.

---

## Project structure (read this first)

```
whatsapp_extractor/
  constants.py     — FILE_TYPES, APPLE_EPOCH, DEFAULT_TYPES, GIF_MESSAGE_TYPES
  utils.py         — pure helpers (dates, JID parsing, safe names)
  metadata.py      — EXIF + macOS xattr/Spotlight writing
  backup.py        — find_backup_path(), find_chatstorage()
  database.py      — Manifest.db and ChatStorage queries
  extractor.py     — build_dest_path(), extract() loop
  cli.py           — argparse for extract_whatsapp_media.py
  contacts_cli.py  — argparse for list_contacts.py

extract_whatsapp_media.py   ← thin entry point (3 lines)
list_contacts.py            ← thin entry point (3 lines)
TODO/                       ← feature specs (one file per feature)
```

---

## Round 1 — Parallel (zero file overlap)

### Agent 1 — Claude (tasks 10 + 11)

**Worktree setup** (run once from the main project directory):
```bash
git checkout main
git pull
git worktree add ../wa-feature-10-11 -b feature/10-11-metadata-gui
```

Working directory: `../wa-feature-10-11`

**Tasks:**

#### TODO/10-windows-linux-support.md
- File to edit: `whatsapp_extractor/metadata.py`
- Goal: replace the macOS-only `setxattr` calls with a cross-platform
  implementation using `sys.platform`:
  - `darwin` → keep current `setxattr` via ctypes (no change)
  - `win32` / `linux` → write an XMP sidecar file (`.xmp`) alongside each
    exported file containing the same metadata (title, keywords, date, contact)
- XMP sidecar format is standard XML/RDF; keep it simple — Lightroom and
  digiKam can read it
- The public API `set_rich_metadata(filepath, dt, contact_name, jid, direction, ftype)`
  must not change signature

#### TODO/11-gui.md
- Create a new file: `whatsapp_extractor/gui.py`
- Create a new entry point: `gui.py` in the project root (same pattern as
  `extract_whatsapp_media.py`)
- Use **tkinter** (zero extra dependencies)
- UI elements: backup folder selector, output folder selector, contact name
  filter field, date-from / date-to pickers, file type checkboxes (img, video,
  audio, doc, gif, webp), progress display (text log or progress bar), Run button
- Must call `from whatsapp_extractor.extractor import extract` — no logic duplication
- The `extract()` function is blocking; run it in a `threading.Thread` so the
  GUI doesn't freeze

**When done:**
```bash
# from ../wa-feature-10-11
git add -p
git commit -m "feat: cross-platform metadata + tkinter GUI"
git push -u origin feature/10-11-metadata-gui
# open a PR on GitHub
```

---

### Agent 2 — Codex (task 12)

**Worktree setup** (run once from the main project directory):
```bash
git checkout main
git pull
git worktree add ../wa-feature-12 -b feature/12-android-support
```

Working directory: `../wa-feature-12`

**Task:**

#### TODO/12-android-support.md
- Create a new module: `whatsapp_extractor/android_extractor.py`
- Create a new entry point: `extract_android.py` in the project root
- Android WhatsApp stores messages in `msgstore.db` (SQLite)
- Contact names come from `wa.db` (Android contacts database)
- Media files are stored directly on the filesystem (no blob indirection like
  iOS); the user points `--backup` at the root WhatsApp folder
  (`/sdcard/WhatsApp/` or a local copy of it)
- Core tables in `msgstore.db`: `messages`, `chat_list` (schema differs from
  iOS `ChatStorage.sqlite` — query the actual schema at runtime rather than
  assuming column names)
- Reuse from the existing package (do NOT duplicate):
  - `whatsapp_extractor.constants` — FILE_TYPES, DOCS_FOLDER
  - `whatsapp_extractor.utils` — safe_folder_name, safe_filename_part, get_file_type
  - `whatsapp_extractor.metadata` — set_rich_metadata
  - `whatsapp_extractor.extractor` — build_dest_path
- CLI: `python3 extract_android.py --backup /path/to/WhatsApp --output ./out`
  Mirror the same flags as `extract_whatsapp_media.py` where applicable
  (`--dry-run`, `--contact`, `--from`, `--to`, `--type`, `--random`)
- Add `--platform android` detection note in README if you update docs

**When done:**
```bash
# from ../wa-feature-12
git add -p
git commit -m "feat: Android backup support"
git push -u origin feature/12-android-support
# open a PR on GitHub
```

---

## Worktree cleanup (after PRs are merged)

```bash
# from the main project directory
git worktree remove ../wa-feature-10-11
git worktree remove ../wa-feature-12
git branch -d feature/10-11-metadata-gui
git branch -d feature/12-android-support
```

---

## Round 2 (after Round 1 merges) — planned

| Agent | Tasks | Primary files |
|-------|-------|--------------|
| 1 | 06 encrypted-backup | `backup.py` |
| 2 | 04 size-filter + 07 group-filter | `database.py`, `cli.py` |

## Round 3 (sequential only — all touch extractor.py loop)

01 since-last-run → 05 resume-skip-existing → 09 duplicate-detection → 02 stats-only → 03 progress-bar → 08 report-export
