# `--min-size` / `--max-size` — Filter by File Size

## What
Add `--min-size` and `--max-size` arguments to filter files by size in KB.

## Why
Useful for skipping tiny thumbnails or preview images that passed through the type filter, or for targeting only high-resolution files.

## How
- `ZFILESIZE` is already available in `ZWAMEDIAITEM`
- Add it to `load_message_info()` so it's available without touching the physical file
- Filter in the pre-processing step alongside contact and date filters
- Accept human-readable values: `--min-size 100kb`, `--max-size 10mb`

## Example
```bash
# Only files larger than 500 KB (skip tiny previews)
python3 extract_whatsapp_media.py --min-size 500kb

# Only small files
python3 extract_whatsapp_media.py --max-size 200kb
```
