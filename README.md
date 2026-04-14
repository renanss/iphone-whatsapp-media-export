# 📱 iPhone WhatsApp Media Export

Extract, organize, and archive your WhatsApp photos from an iPhone local backup — with rich metadata, proper timestamps, and iCloud-ready structure.

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support%20this%20project-yellow?style=flat&logo=buy-me-a-coffee)](https://buymeacoffee.com/renanssn)

---

## ✨ Features

- Extracts **all photos** from a local iPhone backup (no decryption needed)
- Organizes files by **contact/group → year-month**
- Renames files with **contact name + phone number + original timestamp**
- Writes rich **EXIF metadata** (DateTimeOriginal, Artist, Description, UserComment)
- Sets **macOS Spotlight attributes** (Title, Keywords, Authors, ContentCreationDate)
- Corrects **filesystem timestamps** to the original message date
- Marks photos as **"enviada" (sent) or "recebida" (received)**
- Supports **dry-run**, **random sampling**, **single contact** and **single file** modes

---

## 🔧 Requirements

- macOS (uses native `setxattr` for Spotlight metadata)
- iPhone local backup via Finder — **unencrypted**
- Python 3.10+
- Optional but recommended: [`piexif`](https://pypi.org/project/piexif/) for EXIF writing

```bash
pip3 install piexif
```

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

This shows all contacts and groups with their photo counts, so you can choose who to export.

### 4. Run the extractor

```bash
# Full extraction (all contacts)
python3 extract_whatsapp_media.py

# Dry run — see what would happen without copying anything
python3 extract_whatsapp_media.py --dry-run

# Extract a specific contact
python3 extract_whatsapp_media.py --contact "John"

# Extract a random sample (great for testing)
python3 extract_whatsapp_media.py --random 10

# Combine filters
python3 extract_whatsapp_media.py --random 5 --contact "John" --dry-run
```

Output is saved to `./WhatsApp_Media_Export/` by default.

---

## 📁 Output Structure

```
WhatsApp_Media_Export/
├── John_Smith/
│   ├── 2023-03/
│   │   ├── John_Smith_15519999999_2023-03-15_14-30-22.jpg
│   │   └── John_Smith_15519999999_2023-03-16_09-12-45.jpg
│   └── 2024-01/
│       └── John_Smith_15519999999_2024-01-08_18-45-00.jpg
├── Family_Group/
│   └── 2023-06/
│       └── ...
└── _Desconhecido/
    └── ...
```

---

## 🏷️ Metadata Written

Each exported photo gets:

| Field | Example |
|---|---|
| Filename | `John_Smith_15519999999_2025-12-13_17-39-44.jpg` |
| EXIF DateTimeOriginal | `2025:12:13 17:39:44` (local time) |
| EXIF OffsetTimeOriginal | `-03:00` |
| EXIF Artist | `John Smith` |
| EXIF ImageDescription | `WhatsApp · Contact: John Smith · 13/12/2025 at 17:39` |
| Spotlight Title | `John Smith · 2025-12-13 17:39` |
| Spotlight Keywords | `WhatsApp, Contact, John Smith, 15519999999, recebida, 2025, 2025-12` |
| Spotlight Authors | `John Smith` |
| ContentCreationDate | Original message date |
| Filesystem mtime | Original message date |

---

## ⚙️ All Options

```
python3 extract_whatsapp_media.py [options]

  --backup PATH       Path to iPhone backup (auto-detected if omitted)
  --output PATH       Output folder (default: ./WhatsApp_Media_Export)
  --contact NAME      Filter by contact name (case-insensitive, partial match)
  --file FILE_ID      Extract a single file by its SHA1 fileID
  --random N          Extract N random files (combinable with --contact)
  --dry-run           Simulate without copying any files
  --inspect-db        Print ChatStorage.sqlite schema (useful for debugging)
```

```
python3 list_contacts.py [options]

  --backup PATH       Path to iPhone backup (auto-detected if omitted)
  --sort name|photos  Sort by name or photo count (default: photos)
  --filter TEXT       Filter contacts by name or JID
```

---

## 🗂️ How It Works

iPhone backups store all files as SHA1-hashed blobs in a flat directory structure. This tool:

1. Reads `Manifest.db` to map SHA1 hashes → original file paths
2. Reads `ChatStorage.sqlite` (WhatsApp's internal database) to get contact names and message timestamps
3. Copies the physical files using the SHA1 hash as the source filename
4. Renames and organizes them by contact and date
5. Writes rich metadata so iCloud Photos, Finder, and Spotlight can properly index everything

---

## 📲 After Export — Import to iCloud Photos

1. Open the **Photos** app on Mac
2. **File → Import** → select the `WhatsApp_Media_Export` folder
3. Photos will be organized by the original date in your timeline

To free up space on your iPhone after verifying the export:
**WhatsApp → Settings → Storage → Manage** → clear media per conversation

---

## ⚠️ Notes

- This tool only reads from your backup — it never modifies your iPhone or WhatsApp data
- Works with **unencrypted** backups only
- Tested on macOS with Python 3.13 and WhatsApp backups from 2017–2025
- The Apple timestamp epoch starts at `2001-01-01 00:00:00 UTC` (not Unix epoch)

---

## ☕ Support

If this tool saved you time or helped you recover memories, consider buying me a coffee:

[![Buy Me a Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/renanssn)

---

## 📄 License

MIT License — free to use, modify and distribute.
