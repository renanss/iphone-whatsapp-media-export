# Encrypted Backup Support

## What
Support iPhone backups created with encryption enabled, by decrypting them before extraction.

## Why
Many users have encrypted backups (recommended by Apple). Currently the tool only works with unencrypted ones.

## How
- Use the [`iphone-backup-decrypt`](https://github.com/jsharkey13/iphone_backup_decrypt) library
- Add `--password` argument to pass the backup password
- Decrypt `Manifest.db` and individual files on-the-fly into a temp directory
- Proceed with the normal extraction flow

## Dependencies
```bash
pip3 install iphone-backup-decrypt --break-system-packages
```

## Notes
- Decryption is CPU-intensive; warn the user it may be slow
- Never store the password in logs or state files
- Test with both iTunes-style and Finder-style encrypted backups
