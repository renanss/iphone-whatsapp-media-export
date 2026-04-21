# QA — Task 10: Windows / Linux Support

**Branch:** `feature/10-11-metadata-gui`
**PR:** https://github.com/renanss/iphone-whatsapp-media-export/pull/1
**Dev completed by:** Agent 1 (Claude)

---

## What was built

- `metadata.py` now detects the platform at import time (`sys.platform`).
- **macOS**: behaviour unchanged — Spotlight xattr written via `setxattr`.
- **Windows / Linux**: a `.xmp` sidecar file is written alongside each exported file (valid XMP/RDF, readable by Lightroom, digiKam, etc.). `ctypes` and `plistlib` imports are skipped entirely so the module loads cleanly on non-macOS.
- `backup.py`: new `_mobilesync_candidates()` returns platform-correct backup paths:
  - macOS: `~/Library/Application Support/MobileSync/Backup`
  - Windows: `%APPDATA%\Apple Computer\MobileSync\Backup` + Microsoft Store iTunes path
  - Linux: `~/.wine/…`

---

## Definition of Done

- [ ] **macOS — xattr still works**: run a dry-run extraction on macOS, pick any exported JPEG, open Get Info in Finder → Title, Keywords and Content Created must be populated.
- [ ] **XMP sidecar is valid XML**: after a real extraction on any platform, run:
  ```bash
  python3 -c "import xml.etree.ElementTree as ET; ET.parse('path/to/file.jpg.xmp'); print('valid')"
  ```
- [ ] **XMP sidecar contains expected fields**: open the `.xmp` in a text editor and confirm `dc:title`, `dc:creator`, `dc:subject` (keywords), and `xmp:CreateDate` are present.
- [ ] **No import error on non-macOS**: on Windows or Linux (or WSL), running `python3 -c "from whatsapp_extractor.metadata import set_rich_metadata"` must succeed without errors.
- [ ] **`extract_whatsapp_media.py --help` has no regression**: all existing CLI flags still present and functional.
- [ ] **`--dry-run` produces no `.xmp` files**: sidecar should only be written when a file is actually copied.
