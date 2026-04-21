# Android Backup Support

## What
Support extraction from Android WhatsApp backups in addition to iPhone backups.

## Why
Android is the dominant mobile platform globally. Many users switching from Android to iPhone (or just wanting to archive) have WhatsApp data in Android format.

## How
- Android WhatsApp stores messages in `msgstore.db` (SQLite)
- Media files are stored in `/sdcard/WhatsApp/Media/` or in a local backup ZIP
- Schema differs from iOS `ChatStorage.sqlite` but core tables (`messages`, `chat_list`) are similar
- Add `--platform android` flag and a separate `android_extractor.py` module
- Contact names come from `wa.db` (Android contacts database)

## Key differences from iOS
| | iOS | Android |
|---|---|---|
| DB file | `ChatStorage.sqlite` | `msgstore.db` |
| Media path | Inside backup blob | Direct filesystem path |
| Contact DB | `ZWACHATSESSION` | `wa.db` |
| Backup format | iTunes/Finder backup | ZIP or Google Drive |

## Notes
- Google Drive Android backups are encrypted and much harder to access
- Local Android backups (USB transfer) are straightforward
