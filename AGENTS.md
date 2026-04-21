# Agent Coordination

This file coordinates parallel work between two AI agents on the
`iphone-whatsapp-media-export` project.

Each agent works in its own **git worktree** — a separate directory on disk
that shares the same repo. No shared files, no conflicts, clean PRs.

---

## Task lifecycle — MANDATORY

```
TASKS/TODO/   →   (agent picks up task)   →   TASKS/QA/   →   (tester approves)   →   TASKS/DONE/
```

**Every agent must follow this on completion:**

1. Copy the task spec from `TASKS/TODO/<task>.md` into `TASKS/QA/<task>.md`
2. Replace the content with a QA card using the template below
3. Delete the original from `TASKS/TODO/`
4. Commit the file move as part of your feature commit (or as a follow-up commit on the same branch)

**QA card template** (`TASKS/QA/<task>.md`):

```markdown
# QA — Task <N>: <Title>

**Branch:** `feature/...`
**PR:** https://github.com/renanss/iphone-whatsapp-media-export/pull/<N>
**Dev completed by:** Agent <1 or 2>

---

## What was built
<!-- 3–6 bullet points describing what changed and why -->

---

## Definition of Done
<!-- Concrete, runnable checks. Each line is a checkbox the tester will tick. -->
- [ ] ...
- [ ] ...
```

After the tester approves, the file is moved to `TASKS/DONE/` and the PR is merged.

---

## Project structure (read this first)

```
whatsapp_extractor/
  constants.py     — FILE_TYPES, APPLE_EPOCH, DEFAULT_TYPES, GIF_MESSAGE_TYPES
  utils.py         — pure helpers (dates, JID parsing, safe names)
  metadata.py      — EXIF + macOS xattr/Spotlight writing; XMP sidecar on Windows/Linux
  backup.py        — find_backup_path() (cross-platform), find_chatstorage()
  database.py      — Manifest.db and ChatStorage queries
  extractor.py     — build_dest_path(), extract() loop
  cli.py           — argparse for extract_whatsapp_media.py
  contacts_cli.py  — argparse for list_contacts.py
  gui.py           — tkinter GUI (zero extra deps)

extract_whatsapp_media.py   ← thin entry point (3 lines)
list_contacts.py            ← thin entry point (3 lines)
gui.py                      ← thin entry point (3 lines)

TASKS/
  TODO/   ← specs for features not yet started
  QA/     ← dev-complete features awaiting tester sign-off
  DONE/   ← tester-approved, merged features
```

---

## Round 1 — Parallel (zero file overlap)

### Agent 1 — Claude  ✅ COMPLETE — awaiting QA

Tasks 10 and 11 are done. QA cards are in `TASKS/QA/`.

---

### Agent 2 — Codex (task 12)

**Worktree setup** (run once from the main project directory):
```bash
git checkout main
git pull
git worktree add ../wa-feature-12 -b feature/12-android-support
```

Working directory: `../wa-feature-12`

**Task spec:** `TASKS/TODO/12-android-support.md`

**Summary:**
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

**When done:**
```bash
# from ../wa-feature-12
git add -p
git commit -m "feat: Android backup support"
git push -u origin feature/12-android-support
# open a PR on GitHub
```

**Then move the task to QA** — follow the lifecycle instructions at the top of this file.

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
