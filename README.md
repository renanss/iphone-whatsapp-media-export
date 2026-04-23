# 📱 WhatsApp Media Export

Extract, organize, and archive your WhatsApp media from local iPhone backups or Android WhatsApp folders — with rich metadata, proper timestamps, reports, and Photos-friendly output.

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support%20this%20project-yellow?style=flat&logo=buy-me-a-coffee)](https://buymeacoffee.com/renanssn)

---

## ✨ Features

- Extracts **all media** from local iPhone backups — **encrypted or unencrypted**
- Extracts media from local **Android WhatsApp folders** with `extract_android.py --platform android`
- Supports **photos, videos, audio, documents, GIFs and stickers (webp)**
- Organizes files by **contact/group → year-month**
- Renames files with **contact name + phone number + original timestamp**
- Writes rich **EXIF metadata** (DateTimeOriginal, OffsetTimeOriginal, Artist, Description, UserComment)
- **macOS**: sets Spotlight attributes (Title, Keywords, Authors, ContentCreationDate) via `xattr`
- **Windows / Linux**: writes an **XMP sidecar** (`.xmp`) alongside each file — readable by Lightroom, digiKam and most DAM tools
- Corrects **filesystem timestamps** to the original message date
- Marks media as **sent** or **received**
- **Documents are isolated** in a `_Documents/` folder so iCloud Photos imports stay clean
- **Incremental extraction** with `--since-last-run`
- **Stats-only mode** and structured `.json` / `.csv` reports for iPhone backups
- **Resume-safe**: re-runs skip files that already exist with matching size
- **Duplicate detection** for repeated iPhone backup `fileID`s
- **Live progress bar** for iPhone extraction when `tqdm` is installed
- Supports **dry-run**, **date range**, **random sampling**, **contact filter**, **type filter** and more
- **Graphical interface** (`gui.py`) for iPhone backups — zero extra dependencies

---

## ✅ Platform Support

| Capability | iPhone CLI | Android CLI | GUI |
|---|---:|---:|---:|
| Media extraction | ✅ | ✅ | ✅ iPhone only |
| Contact/date/type/random filters | ✅ | ✅ | ✅ iPhone only |
| `--since-last-run` incremental mode | ✅ | ✅ | — |
| Rich metadata + timestamps | ✅ | ✅ | ✅ iPhone only |
| Encrypted backup support | ✅ | N/A | — |
| Stats-only and JSON/CSV reports | ✅ | — | ✅ iPhone only |
| Size filters and group-only filters | ✅ | — | — |
| Duplicate `fileID` detection | ✅ | — | ✅ iPhone only |
| `list_contacts.py` contact counts | ✅ | — | — |

Android support expects an already accessible WhatsApp folder with a readable
SQLite `msgstore.db`. Encrypted Android database exports such as
`msgstore.db.crypt12`, `.crypt14`, or `.crypt15` are not decrypted by this tool.

---

## 🔧 Requirements

- **macOS, Windows or Linux**
- For iPhone: local backup via Finder / iTunes (encrypted backups supported via `--password`)
- For Android: a local copy of the WhatsApp folder containing a readable `msgstore.db` and `Media/`
- Python 3.10+
- Optional but recommended:
  - [`piexif`](https://pypi.org/project/piexif/) for EXIF writing
  - [`tqdm`](https://pypi.org/project/tqdm/) for a live progress bar
  - [`iphone-backup-decrypt`](https://pypi.org/project/iphone-backup-decrypt/) only if your backup is encrypted

```bash
pip3 install piexif tqdm --break-system-packages
# Only if your iPhone backup is encrypted:
pip3 install iphone-backup-decrypt --break-system-packages
```

> **macOS + tkinter**: if `python3 gui.py` fails with a tkinter error, install the binding:
> ```bash
> brew install python-tk@3.14   # match your Python version
> ```

---

## 🚀 Quick Start

### 1. Prepare your WhatsApp data

For iPhone, open **Finder → your iPhone → Back Up Now**. Encrypted backups are fully supported — just pass `--password` (or `--password -` to be prompted) when running the extractor.

For Android, copy the WhatsApp folder locally. The folder should contain
`msgstore.db` and `Media/`. If you only have `msgstore.db.crypt12`,
`msgstore.db.crypt14`, or `msgstore.db.crypt15`, decrypt it first with a
separate Android backup/decryption tool.

### 2. Clone the repository

```bash
git clone https://github.com/renanss/whatsapp-media-export.git
cd whatsapp-media-export
```

### 3. List iPhone contacts

```bash
python3 list_contacts.py
```

For iPhone backups, this shows all contacts and groups with their media counts, so you can choose who to export. For Android, use `extract_android.py --dry-run` or filters directly against the Android backup folder.

### 4. Run the extractor

**Option A — Graphical interface for iPhone backups (recommended for most iPhone users):**

```bash
python3 gui.py
```

The GUI is for iPhone backups. It auto-detects backups when possible, lets you
browse contacts, apply filters, export reports, and watch the live log — no
terminal knowledge needed.

**Option B — iPhone command line:**

```bash
python3 extract_whatsapp_media.py
```

Output is saved to `./WhatsApp_Media_Export/` by default.

**Option C — Android command line:**

For Android, point `--backup` at a local copy of the WhatsApp folder that
contains `msgstore.db` and `Media/`:

```bash
python3 extract_android.py --platform android --backup /path/to/WhatsApp --output ./out
```

---

## 📁 Output Structure

```
WhatsApp_Media_Export/
├── .whatsapp_export_state.json   ← created by --since-last-run after successful runs
├── John_Smith/
│   ├── 2023-03/
│   │   ├── John_Smith_15519999999_2023-03-15_14-30-22.jpg
│   │   └── John_Smith_15519999999_2023-03-16_09-12-45.mp4
│   └── 2024-01/
│       └── John_Smith_15519999999_2024-01-08_18-45-00.jpg
├── Family_Group/
│   └── 2023-06/
│       └── ...
├── _Unknown/
│   └── ...
└── _Documents/               ← isolated from media — safe to skip on iCloud Photos import
    ├── John_Smith/
    │   └── 2023-03/
    │       └── John_Smith_15519999999_2023-03-15_10-00-00.pdf
    └── ...
```

---

## 🖥️ GUI — Graphical Interface

```bash
python3 gui.py
```

| Feature | Details |
|---|---|
| Backup folder | Auto-detected on launch; Browse button to override |
| Output folder | Configurable via Browse button |
| Contact list | Click **⟳ Load contacts** to populate a scrollable list sorted by file count |
| Multi-select | Shift-click for ranges, Cmd/Ctrl-click for individual picks; shows *"N contacts selected"* |
| Search contacts | Live filter as you type inside the contact panel |
| Date range | From / To fields with YYYY-MM-DD validation |
| File type toggles | Checkboxes matching CLI defaults (gif and webp opt-in) |
| Dry run | Toggle to preview without copying any files |
| Stats only | Print aggregate backup stats without copying files |
| Report export | Pick a `.json` or `.csv` report file and open it after the run |
| Live log | Colour-coded output (info, progress, warning, error) streamed in real time |
| Non-blocking | Extraction runs in a background thread — window stays responsive |

---

## 🏷️ Metadata Written

Each exported file gets:

| Field | macOS | Windows / Linux |
|---|---|---|
| Filename | `John_Smith_15519999999_2025-12-13_17-39-44.jpg` | same |
| EXIF DateTimeOriginal | ✅ (JPEG only) | ✅ (JPEG only) |
| EXIF OffsetTimeOriginal | ✅ | ✅ |
| EXIF Artist / Description | ✅ | ✅ |
| Spotlight xattr (Title, Keywords, Authors, ContentCreationDate) | ✅ | — |
| XMP sidecar (`.xmp`) | — | ✅ |
| Filesystem mtime | ✅ | ✅ |

**XMP sidecar** fields (Windows / Linux): `dc:title`, `dc:description`, `dc:creator`, `dc:subject` (keywords), `xmp:CreateDate` — compatible with Lightroom, digiKam, and most DAM tools.

**Example Spotlight keywords (macOS):** `WhatsApp, Contact, John Smith, 15519999999, received, img, 2025, 2025-12`

---

## ⚙️ CLI Reference

### extract_whatsapp_media.py — iPhone backups

```
python3 extract_whatsapp_media.py [options]
```

### General

| Option | Description |
|---|---|
| `--backup PATH` | Path to the iPhone backup folder. Auto-detected if omitted (checks local folder first, then `~/Library/Application Support/MobileSync/Backup/`) |
| `--output PATH` | Output folder. Default: `./WhatsApp_Media_Export` |
| `--dry-run` | Simulate the extraction without copying any files. Shows exactly what would be exported |
| `--stats-only` | Print aggregate backup statistics without copying files or printing every media item |
| `--report PATH` | Write a structured `.json` or `.csv` report for a stats-only or extraction run |
| `--since-last-run` | Read `.whatsapp_export_state.json` from the output folder and resume from the last successful extraction date |
| `--inspect-db` | Print the `ChatStorage.sqlite` schema and exit. Useful for debugging or unsupported WhatsApp versions |
| `--password PASS` | Passphrase for encrypted iPhone backups. Use `--password -` to be prompted interactively (input is hidden and never logged). Requires `iphone-backup-decrypt` |

### Filtering

| Option | Description |
|---|---|
| `--contact NAME` | Extract only files from contacts/groups whose name contains `NAME` (case-insensitive, partial match). Example: `--contact "John"` |
| `--from YYYY-MM-DD` | Extract only files sent on or after this date. Example: `--from 2023-01-01` |
| `--to YYYY-MM-DD` | Extract only files sent on or before this date (inclusive of full day). Example: `--to 2023-12-31` |
| `--min-size SIZE` | Extract only files at least this size. Accepts bare KB or units like `500kb`, `10mb`, `1gb` |
| `--max-size SIZE` | Extract only files at most this size. Accepts bare KB or units like `200kb`, `5mb`, `1gb` |
| `--no-group` | Exclude group chats and export personal chats only |
| `--only-group` / `--group` | Export group chats only. Can be combined with `--contact` for a specific group |
| `--file FILE_ID` | Extract a single file by its SHA1 `fileID` from `Manifest.db` (prefix match supported) |

### File Types

| Option | Description |
|---|---|
| `--type TYPE ...` | File types to include. Default: `img video audio doc`. Use `all` to include everything. Multiple values accepted |
| `--exclude-type TYPE ...` | File types to exclude from the selection. Applied on top of `--type` |

**Available types:**

| Type | Extensions | Default |
|---|---|---|
| `img` | `.jpg` `.jpeg` `.png` `.heic` `.tiff` `.bmp` | ✅ |
| `video` | `.mp4` `.mov` `.avi` `.mkv` `.3gp` `.m4v` `.wmv` | ✅ |
| `audio` | `.opus` `.mp3` `.m4a` `.aac` `.ogg` `.wav` `.amr` `.flac` | ✅ |
| `doc` | `.pdf` `.docx` `.xlsx` `.pptx` `.txt` `.csv` `.zip` and more | ✅ → `_Documents/` |
| `gif` | `.gif` | ❌ opt-in |
| `webp` | `.webp` (mostly stickers) | ❌ opt-in |

### Sampling

| Option | Description |
|---|---|
| `--random N` | Extract `N` randomly selected files. Combinable with `--contact`, `--type`, and date filters |

---

## ⚙️ extract_android.py — Android WhatsApp Folders

```
python3 extract_android.py --platform android --backup /path/to/WhatsApp [options]
```

The Android extractor reads `msgstore.db`, uses `wa.db` when present for
contact names, and copies media directly from the Android `Media/` folder. It
does not need an iTunes/Finder backup or `Manifest.db`.

Expected backup layout:

```
WhatsApp/
├── msgstore.db
├── wa.db                 # optional, improves contact names
└── Media/
    ├── WhatsApp Images/
    ├── WhatsApp Video/
    ├── WhatsApp Audio/
    └── ...
```

`msgstore.db` schemas vary between WhatsApp Android versions, so the extractor
inspects the `messages` and `chat_list` tables at runtime instead of assuming a
single column layout. It also accepts Android 11+ media paths such as
`Android/media/com.whatsapp/WhatsApp/Media/...`. If a database layout is not
recognized, run with `--inspect-db` and include that output when reporting the
issue.

| Option | Description |
|---|---|
| `--platform android` | Explicit platform marker for scripts or docs that distinguish Android from iPhone extraction |
| `--backup PATH` | Required path to the Android WhatsApp folder or local copy |
| `--output PATH` | Output folder. Default: `./WhatsApp_Media_Export` |
| `--dry-run` | Preview matched media and destination paths without copying files |
| `--since-last-run` | Read `.whatsapp_export_state.json` from the output folder and resume from the last successful extraction date |
| `--contact NAME` | Extract contacts/groups whose display name or raw JID contains `NAME` |
| `--from YYYY-MM-DD` | Extract only media on or after this date |
| `--to YYYY-MM-DD` | Extract only media on or before this date |
| `--type TYPE ...` | Include only selected file types: `img`, `video`, `audio`, `doc`, `gif`, `webp`, or `all` |
| `--exclude-type TYPE ...` | Exclude selected file types after `--type` is applied |
| `--random N` | Extract a random sample after all filters are applied |
| `--inspect-db` | Print Android database schema hints before extracting |

---

## 🔁 Resume, Incremental Runs & Reports

- **Resume-safe re-runs** — if the same `--output` path already contains a
  file whose size matches the source, it is logged as `[SKIPPED]` and not
  re-copied. If the size differs (e.g. truncated or corrupted file), it is
  re-copied. This currently applies to iPhone extraction.
- **Incremental runs** — add `--since-last-run` to resume from the timestamp
  saved in `<output>/.whatsapp_export_state.json`. The state file is updated
  only after successful non-dry-run extraction, so preview runs are safe.
  Supported by both iPhone and Android CLI extractors.
- **Duplicate detection** — WhatsApp stores forwarded media under the same
  `fileID`. Each `fileID` is copied at most once per run; repeats are
  logged as `[DUPLICATE]` and shown in the final report as
  `Duplicates skipped`. This is iPhone-specific because Android media is copied
  directly from filesystem paths rather than iOS backup `fileID`s.
- **Progress bar** — if `tqdm` is installed, a live progress bar replaces
  the per-file output during iPhone real extractions. Dry-run always keeps the
  per-line preview so you can audit the plan. Install with
  `pip3 install tqdm --break-system-packages`.
- **Stats-only report** — `--stats-only` prints totals by type, contact and
  month without copying files in the iPhone extractor. Combine it with
  `--report report.json` or `--report report.csv` to save structured data for
  later analysis.
- **Extraction report** — `--report` also works during real extractions and
  records each file's status (`copied`, `skipped`, `duplicate`, `not_found`,
  or `dry_run`), contact, JID, type, date, size, direction and destination.
  Report export is currently iPhone-only.

---

## 💡 Examples

```bash
# Full iPhone extraction (default: img, video, audio, doc)
python3 extract_whatsapp_media.py

# Dry run — preview without copying anything
python3 extract_whatsapp_media.py --dry-run

# Backup statistics only
python3 extract_whatsapp_media.py --stats-only

# Save backup statistics as JSON
python3 extract_whatsapp_media.py --stats-only --report report.json

# Extract only photos and videos
python3 extract_whatsapp_media.py --type img video

# Extract everything including GIFs and stickers
python3 extract_whatsapp_media.py --type all

# Skip audio messages
python3 extract_whatsapp_media.py --exclude-type audio

# Extract a specific contact
python3 extract_whatsapp_media.py --contact "John"

# Extract a specific year
python3 extract_whatsapp_media.py --from 2023-01-01 --to 2023-12-31

# Extract only media added since the last successful run
python3 extract_whatsapp_media.py --since-last-run

# Extract a specific month from one contact
python3 extract_whatsapp_media.py --contact "John" --from 2024-06-01 --to 2024-06-30

# Skip tiny media files
python3 extract_whatsapp_media.py --min-size 500kb

# Export small files only
python3 extract_whatsapp_media.py --max-size 200kb

# Personal chats only
python3 extract_whatsapp_media.py --no-group

# Group chats only
python3 extract_whatsapp_media.py --only-group

# Specific group
python3 extract_whatsapp_media.py --only-group --contact "Family"

# Random sample of 10 files for testing
python3 extract_whatsapp_media.py --random 10 --dry-run

# Encrypted backup — pass the passphrase
python3 extract_whatsapp_media.py --password "my iTunes passphrase"

# Encrypted backup — prompt for the passphrase (hidden input)
python3 extract_whatsapp_media.py --password -

# Only documents
python3 extract_whatsapp_media.py --type doc

# Custom output folder
python3 extract_whatsapp_media.py --output ~/Desktop/MyWhatsAppExport

# Save a CSV report while extracting
python3 extract_whatsapp_media.py --report report.csv

# Android local WhatsApp folder
python3 extract_android.py --platform android --backup /path/to/WhatsApp --output ./out

# Android incremental run
python3 extract_android.py --platform android --backup /path/to/WhatsApp --since-last-run
```

---

### list_contacts.py — iPhone backups

```
python3 list_contacts.py [options]
```

| Option | Description |
|---|---|
| `--backup PATH` | Path to the iPhone backup. Auto-detected if omitted |
| `--sort name\|photos` | Sort results by name or photo count. Default: `photos` |
| `--filter TEXT` | Show only contacts whose name or JID contains `TEXT` (case-insensitive) |

```bash
# List all contacts sorted by photo count
python3 list_contacts.py

# Sorted by name
python3 list_contacts.py --sort name

# Filter by name
python3 list_contacts.py --filter "john"
```

---

## 🗂️ How It Works

The tool has separate readers for iPhone and Android because WhatsApp stores the same media in different ways on each platform.

For iPhone backups, files are stored as SHA1-hashed blobs in a flat backup directory. The iPhone extractor:

1. Reads `Manifest.db` to map SHA1 hashes → original file paths
2. Reads `ChatStorage.sqlite` (WhatsApp's internal database) to get contact names, message timestamps and direction (sent/received)
3. Copies the physical files using the SHA1 hash as the source filename
4. Renames and organizes them by contact and date
5. Writes rich metadata so iCloud Photos, Finder, and Spotlight can properly index everything
6. Routes documents to a separate `_Documents/` folder to keep media imports clean

For Android folders, media files are already present under `Media/`. The Android extractor:

1. Reads `msgstore.db` for messages and media references
2. Reads `wa.db` when available for contact names
3. Resolves media files directly from the local WhatsApp `Media/` tree
4. Reuses the same output structure, naming rules and metadata writer as the iPhone extractor
5. Can resume from `.whatsapp_export_state.json` with `--since-last-run`

---

## 📲 After Export — Import to Photos

1. Open the **Photos** app on Mac
2. **File → Import** → select the `WhatsApp_Media_Export` folder
3. Photos will be organized by the original date in your timeline

> **Tip:** skip the `_Documents/` subfolder when importing to Photos — it contains PDFs and other non-media files.

To free up space on your phone after verifying the export:
**WhatsApp → Settings → Storage → Manage** → clear media per conversation.

---

## ⚠️ Notes

- This tool only reads from your backup or copied WhatsApp folder — it never modifies your phone or WhatsApp data
- Works with **both encrypted and unencrypted** iPhone backups; encrypted backups need `iphone-backup-decrypt` and `--password`
- Android support requires a readable/decrypted `msgstore.db`; encrypted `.crypt*` databases are not decrypted here
- Passwords are read via `getpass` when using `--password -`, never printed, logged, or persisted
- Tested on macOS with Python 3.13/3.14 and WhatsApp backups from 2017–2025
- The Apple timestamp epoch starts at `2001-01-01 00:00:00 UTC` (not Unix epoch)
- GIFs sent via WhatsApp are stored as `.mp4` files internally; the tool detects them via `ZMESSAGETYPE=15` and classifies them correctly
- On **Windows**, the backup is auto-detected at `%APPDATA%\Apple Computer\MobileSync\Backup\`
- On **Linux** (iTunes via Wine), the backup is auto-detected at `~/.wine/…`; use `--backup` to specify the path manually if needed

---

## ☕ Support

If this tool saved you time or helped you recover memories, consider buying me a coffee:

[![Buy Me a Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/renanssn)

---

## 📄 License

MIT License — free to use, modify and distribute.
