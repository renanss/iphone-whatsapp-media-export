"""
CLI entry point for list_contacts.py
"""

import argparse
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

from .backup import find_backup_path, find_chatstorage
from .constants import WHATSAPP_DOMAIN
from .utils import extract_jid


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
