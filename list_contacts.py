#!/usr/bin/env python3
"""
Lists WhatsApp contacts and groups present in an iPhone backup,
with a photo count for each one.

Usage:
  python3 list_contacts.py
  python3 list_contacts.py --backup /path/to/backup
  python3 list_contacts.py --sort name       # sort by name (default: photos)
  python3 list_contacts.py --filter john     # filter by substring
"""

import argparse
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

WHATSAPP_DOMAIN = "AppDomainGroup-group.net.whatsapp.WhatsApp.shared"


def find_backup_path() -> Path:
    """
    Locates the iPhone backup directory. Checks the script's own folder first
    (in case the backup was moved locally), then falls back to the default
    MobileSync location used by Finder.
    """
    # 1. Same directory as this script
    script_dir = Path(__file__).parent
    local = [d for d in script_dir.iterdir() if d.is_dir() and (d / 'Manifest.db').exists()]
    if local:
        local.sort(key=lambda d: (d / 'Manifest.db').stat().st_mtime, reverse=True)
        return local[0]

    # 2. Default MobileSync location
    base = Path.home() / 'Library' / 'Application Support' / 'MobileSync' / 'Backup'
    if not base.exists():
        sys.exit(f'[ERROR] Backup directory not found: {base}')
    backups = [d for d in base.iterdir() if d.is_dir() and (d / 'Manifest.db').exists()]
    if not backups:
        sys.exit(f'[ERROR] No backup with Manifest.db found in: {base}')
    backups.sort(key=lambda d: (d / 'Manifest.db').stat().st_mtime, reverse=True)
    return backups[0]


def find_chatstorage(manifest_conn: sqlite3.Connection, backup_path: Path) -> Path:
    """Locates ChatStorage.sqlite inside the backup via Manifest.db."""
    row = manifest_conn.execute(
        "SELECT fileID FROM Files WHERE relativePath LIKE '%ChatStorage.sqlite' "
        "AND domain = ? LIMIT 1",
        (WHATSAPP_DOMAIN,)
    ).fetchone()
    if not row:
        sys.exit('[ERROR] ChatStorage.sqlite not found in Manifest.db.')
    file_id = row[0]
    src = backup_path / file_id[:2] / file_id
    if not src.exists():
        sys.exit(f'[ERROR] Physical ChatStorage file not found: {src}')
    return src


def extract_jid(relative_path: str) -> str | None:
    """Extracts the contact/group JID from a Manifest.db relativePath."""
    match = re.match(r'^Message/Media/([^/]+)/', relative_path)
    return match.group(1) if match else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description='List WhatsApp contacts and groups with photo counts.'
    )
    parser.add_argument(
        '--backup', type=Path, default=None,
        help='Path to the iPhone backup (auto-detected if omitted)'
    )
    parser.add_argument(
        '--sort', choices=['name', 'photos'], default='photos',
        help='Sort by name or photo count (default: photos)'
    )
    parser.add_argument(
        '--filter', type=str, default=None, metavar='TEXT',
        help='Show only contacts whose name or JID contains TEXT (case-insensitive)'
    )
    args = parser.parse_args()

    backup_path = args.backup or find_backup_path()
    manifest_db = backup_path / 'Manifest.db'
    if not manifest_db.exists():
        sys.exit(f'[ERROR] Manifest.db not found in: {backup_path}')

    print(f'[INFO] Backup: {backup_path}\n')

    manifest_conn = sqlite3.connect(str(manifest_db))

    # Count photos per JID directly from Manifest.db
    rows = manifest_conn.execute(
        """
        SELECT relativePath FROM Files
        WHERE domain = ?
        AND relativePath LIKE 'Message/Media/%'
        AND relativePath NOT LIKE '%.thumb%'
        AND (
            relativePath LIKE '%.jpg'
            OR relativePath LIKE '%.jpeg'
            OR relativePath LIKE '%.png'
        )
        """,
        (WHATSAPP_DOMAIN,)
    ).fetchall()

    photo_count: dict[str, int] = {}
    for (rpath,) in rows:
        jid = extract_jid(rpath)
        if jid:
            photo_count[jid] = photo_count.get(jid, 0) + 1

    # Load display names from ChatStorage
    chatstorage_src = find_chatstorage(manifest_conn, backup_path)
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
        tmp_path = tmp.name
    shutil.copy2(str(chatstorage_src), tmp_path)

    chat_conn = sqlite3.connect(tmp_path)
    contact_rows = chat_conn.execute(
        "SELECT ZCONTACTJID, ZPARTNERNAME FROM ZWACHATSESSION WHERE ZCONTACTJID IS NOT NULL"
    ).fetchall()
    contact_map: dict[str, str] = {jid: (name or '').strip() for jid, name in contact_rows}

    chat_conn.close()
    manifest_conn.close()
    os.unlink(tmp_path)

    # Build final list: all JIDs that have photos
    entries = []
    for jid, count in photo_count.items():
        name = contact_map.get(jid, '')
        entries.append((jid, name, count))

    # Include contacts from ChatStorage with zero photos (only when not filtering)
    if not args.filter:
        for jid, name in contact_map.items():
            if jid not in photo_count:
                entries.append((jid, name, 0))

    # Apply filter
    if args.filter:
        flt = args.filter.lower()
        entries = [e for e in entries if flt in e[0].lower() or flt in e[1].lower()]

    # Sort
    if args.sort == 'name':
        entries.sort(key=lambda e: (e[1].lower() or e[0].lower()))
    else:
        entries.sort(key=lambda e: -e[2])

    # Display
    total_photos = sum(e[2] for e in entries)
    groups   = [e for e in entries if '@g.us' in e[0]]
    contacts = [e for e in entries if '@g.us' not in e[0]]

    def print_section(title: str, items: list) -> None:
        if not items:
            return
        print(f'{"─" * 70}')
        print(f'  {title}')
        print(f'{"─" * 70}')
        print(f'  {"Name":<40} {"JID":<35} {"Photos":>6}')
        print(f'  {"─"*40} {"─"*35} {"─"*6}')
        for jid, name, count in items:
            name_display = name if name else '(no name)'
            print(f'  {name_display:<40} {jid:<35} {count:>6}')

    print(f'{"═" * 70}')
    print(f'  WHATSAPP CONTACTS — {len(entries)} found / {total_photos} photos')
    print(f'{"═" * 70}')
    print_section(f'INDIVIDUAL CONTACTS ({len(contacts)})', contacts)
    print_section(f'GROUPS ({len(groups)})', groups)
    print(f'{"═" * 70}')
    print(f'  Total photos listed: {total_photos}')
    print(f'{"═" * 70}\n')

    print('To extract a specific contact:')
    print('  python3 extract_whatsapp_media.py --contact "Contact Name"')
    print('  python3 extract_whatsapp_media.py --dry-run --contact "Contact Name"')


if __name__ == '__main__':
    main()
