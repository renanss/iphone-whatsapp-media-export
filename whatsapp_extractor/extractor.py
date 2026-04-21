"""
Core extraction logic — builds destination paths and drives the extraction loop.
"""

import os
import random
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from .backup import find_backup_path, find_chatstorage
from .constants import DOCS_FOLDER, FILE_TYPES, GIF_MESSAGE_TYPES
from .database import inspect_db, load_contact_map, load_message_info, query_media_files
from .metadata import set_rich_metadata
from .utils import apple_ts_to_datetime, extract_jid, get_file_type, phone_from_jid, safe_filename_part, safe_folder_name


def build_dest_path(
    output_dir: Path,
    contact_name: str,
    dt: datetime | None,
    original_filename: str,
    jid: str,
    ftype: str | None = None,
) -> Path:
    """
    Builds the destination path for a media file.

    Documents go to _Documents/<contact>/<month>/ so they are physically
    separated from photos/videos and won't pollute iCloud Photos imports.
    All other types go directly to <contact>/<month>/.
    """
    contact_folder = safe_folder_name(contact_name) if contact_name else f'_Unknown/{safe_folder_name(jid)}'
    name_part      = safe_filename_part(contact_name or jid)
    phone_part     = phone_from_jid(jid)
    ext            = Path(original_filename).suffix.lower()

    if dt:
        month_folder = dt.strftime('%Y-%m')
        filename     = f'{name_part}_{phone_part}_{dt.strftime("%Y-%m-%d_%H-%M-%S")}{ext}'
    else:
        month_folder = '_no_date'
        filename     = f'{name_part}_{phone_part}_{original_filename}'

    # Documents are isolated so iCloud Photos imports stay clean
    if ftype == 'doc':
        dest = output_dir / DOCS_FOLDER / contact_folder / month_folder / filename
    else:
        dest = output_dir / contact_folder / month_folder / filename

    # Avoid filename collisions
    if dest.exists():
        stem    = dest.stem
        suffix  = dest.suffix
        counter = 1
        while dest.exists():
            dest = dest.with_name(f'{stem}_{counter}{suffix}')
            counter += 1

    return dest


def extract(
    backup_path: Path,
    output_dir: Path,
    dry_run: bool = False,
    filter_contact: str | None = None,
    single_file: str | None = None,
    random_sample: int | None = None,
    inspect: bool = False,
    file_types: set[str] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> None:
    manifest_db = backup_path / 'Manifest.db'
    if not manifest_db.exists():
        sys.exit(f'[ERROR] Manifest.db not found in: {backup_path}')

    print(f'[INFO] Backup : {backup_path}')
    print(f'[INFO] Output : {output_dir}')
    if dry_run:
        print('[INFO] DRY-RUN mode — no files will be copied.\n')

    manifest_conn = sqlite3.connect(str(manifest_db))

    # Copy ChatStorage to a temp file to avoid locking the backup
    chatstorage_src = find_chatstorage(manifest_conn, backup_path)
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
        tmp_path = tmp.name
    shutil.copy2(str(chatstorage_src), tmp_path)

    chat_conn = sqlite3.connect(tmp_path)

    contact_map = load_contact_map(chat_conn)

    if inspect:
        inspect_db(chat_conn)

    info_map = load_message_info(chat_conn)

    print(f'[INFO] Contacts/groups loaded : {len(contact_map)}')
    print(f'[INFO] Media entries mapped   : {len(info_map)}')

    active_types = file_types or set(FILE_TYPES.keys())
    all_files = query_media_files(manifest_conn, single_file, active_types)
    print(f'[INFO] Types selected         : {", ".join(sorted(active_types))}')
    print(f'[INFO] Media files found      : {len(all_files)}')

    # Filter by date range (uses info_map for pre-filtering before the main loop)
    if date_from or date_to:
        def _in_range(rpath: str) -> bool:
            ts_val = info_map.get(Path(rpath).name)
            if not ts_val:
                return False  # no date → exclude when a range is set
            dt = apple_ts_to_datetime(ts_val[0])
            if date_from and dt < date_from:
                return False
            if date_to and dt > date_to:
                return False
            return True

        all_files = [(fid, rpath) for fid, rpath in all_files if _in_range(rpath)]
        label_from = date_from.strftime('%Y-%m-%d') if date_from else '—'
        label_to   = date_to.strftime('%Y-%m-%d')   if date_to   else '—'
        print(f'[INFO] Date range filter      : {label_from} → {label_to}')
        print(f'[INFO] Files after date filter: {len(all_files)}')

    # Filter by contact name
    if filter_contact:
        filter_lower = filter_contact.lower()
        matching_jids = {
            jid for jid, name in contact_map.items()
            if filter_lower in name.lower()
        }
        if not matching_jids:
            print(f'[WARNING] No contact found matching "{filter_contact}".')
            print(f'          Available contacts: {sorted(contact_map.values())[:20]}')
        all_files = [
            (fid, rpath) for fid, rpath in all_files
            if extract_jid(rpath) in matching_jids
        ]
        print(f'[INFO] Files after contact filter : {len(all_files)}')

    if random_sample is not None:
        n = min(random_sample, len(all_files))
        all_files = random.sample(all_files, n)
        print(f'[INFO] Random sample: {n} file(s) selected')

    print()

    # Counters for the final report
    stats: dict[str, int] = {}
    total_bytes = 0
    not_found = 0
    copied = 0

    total = len(all_files)
    for idx, (file_id, relative_path) in enumerate(all_files, 1):
        jid = extract_jid(relative_path) or 'unknown'
        contact_name = contact_map.get(jid, '')

        original_filename = Path(relative_path).name
        ext               = Path(original_filename).suffix.lower()
        info              = info_map.get(original_filename)
        ts, direction, msgtype = info if info else (None, 'received', 0)
        dt                = apple_ts_to_datetime(ts) if ts is not None else None

        # Determine file type — GIFs saved as .mp4 by WhatsApp use ZMESSAGETYPE=15
        if msgtype in GIF_MESSAGE_TYPES and ext == '.mp4':
            ftype = 'gif'
        else:
            ftype = get_file_type(ext) or 'img'

        label = contact_name or jid
        print(f'[{idx:>6}/{total}] [{ftype:>5}] {label} — {original_filename}', end='')

        # Locate the physical file in the backup
        src = backup_path / file_id[:2] / file_id
        if not src.exists():
            print(' [NOT FOUND]')
            not_found += 1
            continue

        dest = build_dest_path(output_dir, contact_name, dt, original_filename, jid, ftype)

        if dry_run:
            print(f'\n         -> {dest}  (dry-run)')
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dest))
            set_rich_metadata(dest, dt, contact_name, jid, direction, ftype)
            total_bytes += dest.stat().st_size
            print(f'\n         -> {dest}')

        copied += 1
        stats[label] = stats.get(label, 0) + 1

    # Cleanup
    chat_conn.close()
    manifest_conn.close()
    os.unlink(tmp_path)

    # Final report
    print('\n' + '=' * 60)
    print('FINAL REPORT')
    print('=' * 60)
    print(f'Processed   : {copied}')
    print(f'Not found   : {not_found}')
    if not dry_run:
        print(f'Total size  : {total_bytes / 1_073_741_824:.2f} GB')
    print()
    print(f'{"Contact/Group":<45} {"Files":>6}')
    print('-' * 53)
    for name, count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f'{name:<45} {count:>6}')
    print('=' * 60)
