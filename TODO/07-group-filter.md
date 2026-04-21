# `--group` / `--no-group` — Include or Exclude Group Chats

## What
Add flags to explicitly include or exclude group chats from the extraction.

## Why
Some users only want personal conversations; others only want group media. Currently both are extracted together.

## How
- Group JIDs end with `@g.us`; individual JIDs end with `@s.whatsapp.net`
- `--no-group` filters out any file whose JID ends with `@g.us`
- `--only-group` (or `--group`) filters to group chats only
- Can be combined with `--contact` to target a specific group by name

## Example
```bash
# Personal chats only
python3 extract_whatsapp_media.py --no-group

# Group chats only
python3 extract_whatsapp_media.py --only-group

# Specific group
python3 extract_whatsapp_media.py --only-group --contact "Family"
```
