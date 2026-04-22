# QA — Encrypted backup support

**Branch:** `feature/encrypted-backup`
**PR:** https://github.com/renanss/iphone-whatsapp-media-export/pull/4
**Dev completed by:** Agent 1 (Claude)

---

## What was built
- Added `--password PASSPHRASE` flag to `extract_whatsapp_media.py`. Passing
  `--password -` prompts for the passphrase interactively via `getpass`
  (never echoed, never logged).
- Auto-detects encryption from `Manifest.plist` (`IsEncrypted = True`). If a
  backup is encrypted and no password is given, the tool exits with a clear
  error. If `--password` is passed but the backup isn't encrypted, a warning
  is printed and the flag is ignored.
- New helpers in `whatsapp_extractor/backup.py`:
  `is_backup_encrypted()` and `open_encrypted_backup()` (lazy-imports
  `iphone-backup-decrypt` so the dep is only needed when used).
- `extractor.extract()` now accepts `password: str | None`. When set, it
  decrypts `Manifest.db` to a temp file, decrypts `ChatStorage.sqlite`
  through the library, and decrypts each media file directly to its
  destination (no plaintext intermediate). Temp manifest is deleted on exit.
- All existing filters (`--contact`, `--from/--to`, `--type`, `--random`)
  and the metadata-writing step work unchanged on encrypted backups.

---

## Definition of Done
- [ ] `pip3 install iphone-backup-decrypt --break-system-packages` succeeds
- [ ] `python3 extract_whatsapp_media.py --help` shows the new `--password` flag
- [ ] On an **unencrypted** backup, running without `--password` behaves
      exactly as before (dry-run of 3 random files succeeds)
- [ ] On an **unencrypted** backup, running with `--password foo` prints the
      warning and continues normally
- [ ] On an **encrypted** backup, running without `--password` exits with
      `[ERROR] This backup is encrypted. Pass --password ...`
- [ ] On an **encrypted** backup, `--password <wrong>` exits with
      `[ERROR] Could not decrypt backup (wrong password?): ...`
- [ ] On an **encrypted** backup, `--password <correct> --dry-run --random 5`
      completes and lists destination paths
- [ ] On an **encrypted** backup, a real extraction of a few files produces
      valid, openable media (try `--random 3` without `--dry-run`)
- [ ] `--password -` triggers an interactive prompt (no echo)
- [ ] Grep the code for `password` — it must never be passed to `print`,
      written to disk, or included in log messages
