# 📱 iPhone WhatsApp Media Export

Extract, organize, and archive your WhatsApp media from a local iPhone backup — with rich metadata, proper timestamps, and iCloud-ready structure.

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support%20this%20project-yellow?style=flat&logo=buy-me-a-coffee)](https://buymeacoffee.com/renanssn)

---

## ✨ Features

- Extracts **all media** from a local iPhone backup (no decryption needed)
- Supports **photos, videos, audio, documents, GIFs and stickers (webp)**
- Organizes files by **contact/group → year-month**
- Renames files with **contact name + phone number + original timestamp**
- Writes rich **EXIF metadata** (DateTimeOriginal, OffsetTimeOriginal, Artist, Description, UserComment)
- **macOS**: sets Spotlight attributes (Title, Keywords, Authors, ContentCreationDate) via `xattr`
- **Windows / Linux**: writes an **XMP sidecar** (`.xmp`) alongside each file — readable by Lightroom, digiKam and most DAM tools
- Corrects **filesystem timestamps** to the original message date
- Marks media as **sent** or **received**
- **Documents are isolated** in a `_Documents/` folder so iCloud Photos imports stay clean
- Supports **dry-run**, **date range**, **random sampling**, **contact filter**, **type filter** and more
- **Graphical interface** (`gui.py`) for non-terminal users — zero extra dependencies

---

## 🔧 Requirements

- **macOS, Windows or Linux**
- iPhone local backup via Finder / iTunes — **unencrypted**
- Python 3.10+
- Optional but recommended: [`piexif`](https://pypi.org/project/piexif/) for EXIF writing

```bash
pip3 install piexif --break-system-packages
```

> **macOS + tkinter**: if `python3 gui.py` fails with a tkinter error, install the binding:
> ```bash
> brew install python-tk@3.14   # match your Python version
> ```

---

## 🚀 Quick Start

### 1. Create a local iPhone backup

Open **Finder → your iPhone → Back Up Now**.
Make sure encryption is **disabled**.

### 2. Clone the repository

```bash
git clone https://github.com/renanss/iphone-whatsapp-media-export.git
cd iphone-whatsapp-media-export
```

### 3. List your contacts

```bash
python3 list_contacts.py
```

This shows all contacts and groups with their media counts, so you can choose who to export.

### 4. Run the extractor

**Option A — Graphical interface (recommended for most users):**

```bash
python3 gui.py
```

The GUI auto-detects your backup, lets you browse contacts, apply filters, and watch the live log — no terminal knowledge needed.

**Option B — Command line:**

```bash
python3 extract_whatsapp_media.py
```

Output is saved to `./WhatsApp_Media_Export/` by default.

---

## 📁 Output Structure

```
WhatsApp_Media_Export/
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

### extract_whatsapp_media.py

```
python3 extract_whatsapp_media.py [options]
```

### General

| Option | Description |
|---|---|
| `--backup PATH` | Path to the iPhone backup folder. Auto-detected if omitted (checks local folder first, then `~/Library/Application Support/MobileSync/Backup/`) |
| `--output PATH` | Output folder. Default: `./WhatsApp_Media_Export` |
| `--dry-run` | Simulate the extraction without copying any files. Shows exactly what would be exported |
| `--inspect-db` | Print the `ChatStorage.sqlite` schema and exit. Useful for debugging or unsupported WhatsApp versions |

### Filtering

| Option | Description |
|---|---|
| `--contact NAME` | Extract only files from contacts/groups whose name contains `NAME` (case-insensitive, partial match). Example: `--contact "John"` |
| `--from YYYY-MM-DD` | Extract only files sent on or after this date. Example: `--from 2023-01-01` |
| `--to YYYY-MM-DD` | Extract only files sent on or before this date (inclusive of full day). Example: `--to 2023-12-31` |
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

## 💡 Examples

```bash
# Full extraction (default: img, video, audio, doc)
python3 extract_whatsapp_media.py

# Dry run — preview without copying anything
python3 extract_whatsapp_media.py --dry-run

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

# Extract a specific month from one contact
python3 extract_whatsapp_media.py --contact "John" --from 2024-06-01 --to 2024-06-30

# Random sample of 10 files for testing
python3 extract_whatsapp_media.py --random 10 --dry-run

# Only documents
python3 extract_whatsapp_media.py --type doc

# Custom output folder
python3 extract_whatsapp_media.py --output ~/Desktop/MyWhatsAppExport
```

---

### list_contacts.py

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

iPhone backups store all files as SHA1-hashed blobs in a flat directory structure. This tool:

1. Reads `Manifest.db` to map SHA1 hashes → original file paths
2. Reads `ChatStorage.sqlite` (WhatsApp's internal database) to get contact names, message timestamps and direction (sent/received)
3. Copies the physical files using the SHA1 hash as the source filename
4. Renames and organizes them by contact and date
5. Writes rich metadata so iCloud Photos, Finder, and Spotlight can properly index everything
6. Routes documents to a separate `_Documents/` folder to keep media imports clean

---

## 📲 After Export — Import to iCloud Photos

1. Open the **Photos** app on Mac
2. **File → Import** → select the `WhatsApp_Media_Export` folder
3. Photos will be organized by the original date in your timeline

> **Tip:** skip the `_Documents/` subfolder when importing to Photos — it contains PDFs and other non-media files.

To free up space on your iPhone after verifying the export:
**WhatsApp → Settings → Storage → Manage** → clear media per conversation.

---

## ⚠️ Notes

- This tool only reads from your backup — it never modifies your iPhone or WhatsApp data
- Works with **unencrypted** backups only
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
