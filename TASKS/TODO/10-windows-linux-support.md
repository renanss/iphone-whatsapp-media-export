# Windows / Linux Support

## What
Make the tool fully functional on Windows and Linux by replacing the macOS-only `setxattr` calls with a cross-platform alternative.

## Why
A large portion of potential users are on Windows. The core extraction logic already works cross-platform — only the metadata writing is macOS-specific.

## How
- Detect the OS at runtime (`sys.platform`)
- **macOS**: keep current `setxattr` approach
- **Windows/Linux**: write an XMP sidecar file (`.xmp`) alongside each exported file containing the same metadata (title, keywords, date, contact)
- XMP sidecars are read by Lightroom, digiKam, and most DAM tools
- EXIF writing via `piexif` already works cross-platform

## Notes
- Windows backup path: `%APPDATA%\Apple Computer\MobileSync\Backup\`
- Linux (iTunes via Wine): path varies
- Test with Python 3.10+ on Windows 10/11
