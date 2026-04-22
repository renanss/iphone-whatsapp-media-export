# QA — `--group` / `--no-group`: Include or Exclude Group Chats

**Branch:** `feature/size-group-filters`
**PR:** https://github.com/renanss/iphone-whatsapp-media-export/pull/TBD
**Dev completed by:** Agent 2

---

## What was built

- Added mutually exclusive `--no-group` and `--only-group` CLI flags.
- Added `--group` as an alias for `--only-group`.
- Added pre-loop filtering based on WhatsApp JID suffixes: `@g.us` for groups and `@s.whatsapp.net` for personal chats.
- Documented group filtering in the README with examples.

---

## Definition of Done

- [ ] `python3 extract_whatsapp_media.py --help` shows `--no-group`, `--only-group`, and `--group`.

  Tester note: `--no-group` and `--only-group` should be mutually exclusive.

- [ ] Run `python3 extract_whatsapp_media.py --backup /path/to/backup --output /tmp/wa-group-test --dry-run --no-group`.

  Tester note: output should include `Group filter : personal chats only`, and exported paths should not include group chats.

- [ ] Run `python3 extract_whatsapp_media.py --backup /path/to/backup --output /tmp/wa-group-test --dry-run --only-group`.

  Tester note: output should include `Group filter : groups only`, and exported paths should contain group chats only.

- [ ] Run `python3 extract_whatsapp_media.py --backup /path/to/backup --output /tmp/wa-group-test --dry-run --only-group --contact "Family"`.

  Tester note: group filtering should combine with contact-name filtering so only matching groups remain.

- [ ] Run `python3 extract_whatsapp_media.py --backup /path/to/backup --dry-run --no-group --only-group`.

  Tester note: argparse should reject the mutually exclusive flags before extraction starts.
