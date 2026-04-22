# QA — Task 11: Tkinter GUI

**Branch:** `feature/10-11-metadata-gui`
**PR:** https://github.com/renanss/iphone-whatsapp-media-export/pull/1
**Dev completed by:** Agent 1 (Claude)

---

## What was built

- `whatsapp_extractor/gui.py` — tkinter GUI module (zero extra dependencies).
- `gui.py` — 3-line root entry point (`python3 gui.py`).

**UI elements:**
- Backup folder field (auto-detected on launch) + Browse button
- Output folder field + Browse button
- Contact name filter (case-insensitive, partial match)
- Date from / Date to fields (YYYY-MM-DD, validated before run)
- File type checkboxes: img, video, audio, doc (on by default), gif, webp (opt-in)
- Dry-run toggle
- Run / Stop buttons
- Live colour-coded log (dark theme: blue = info, teal = progress, orange = warning, red = error)

Extraction runs in a background `threading.Thread` — the UI stays responsive throughout.

---

## Definition of Done

- [ ] **Window opens**: `python3 gui.py` launches without errors and shows the main window.
- [ ] **Auto-detection**: if a backup exists in the project folder or MobileSync, the Backup field is pre-filled on launch and the log shows `[INFO] Backup auto-detected: …`.
- [ ] **Browse buttons work**: clicking Browse for Backup and Output opens a folder picker and updates the field.
- [ ] **Dry run completes**: with a valid backup selected, check Dry run, click Run — log shows file list with `(dry-run)` suffix, no files are copied to disk, Done status appears.
- [ ] **Contact filter works**: enter a partial contact name, run dry-run — only files from matching contacts appear in the log.
- [ ] **Date filter validates**: enter an invalid date (e.g. `2023-13-01`) → red error line in log, extraction does not start.
- [ ] **Date filter works**: enter a valid `--from` / `--to` range, dry-run — log shows `Date range filter` line and correct file count.
- [ ] **File type checkboxes respected**: uncheck all except img, dry-run — only image files appear in log.
- [ ] **UI stays responsive during extraction**: window can be resized and scrolled while extraction is running.
- [ ] **Log is colour-coded**: `[INFO]` lines are blue, `[WARNING]` orange, `[ERROR]` red, progress lines teal.
- [ ] **Clear log button** empties the log area.
- [ ] **No CLI regression**: `python3 extract_whatsapp_media.py --dry-run --random 5` still works normally from the terminal.
