# Duplicate Detection

## What
Skip files that were already exported in a previous run, even if they appear under a different contact or folder.

## Why
The same media file can sometimes be forwarded across multiple chats, creating duplicate entries in `Manifest.db` with the same SHA1. Exporting them wastes space.

## How
- The `fileID` in `Manifest.db` is already a SHA1 hash of the file content
- Maintain a `seen_file_ids` set during extraction
- If a `fileID` has already been copied, skip it and log `[DUPLICATE]`
- Optionally: create a symlink instead of a second copy

## Notes
- This is different from the resume feature (#05) — duplicates are files that exist in multiple chats, not files from a previous run
- Add a `Duplicates skipped` line to the final report
