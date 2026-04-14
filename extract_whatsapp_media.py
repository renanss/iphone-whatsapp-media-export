#!/usr/bin/env python3
"""
WhatsApp Media Extractor
Extracts photos from a local iPhone backup, organized by contact/group and date.

Usage:
  python3 extract_whatsapp_media.py [options]

Examples:
  python3 extract_whatsapp_media.py                           # full extraction
  python3 extract_whatsapp_media.py --dry-run                 # simulate without copying
  python3 extract_whatsapp_media.py --contact "John"          # single contact
  python3 extract_whatsapp_media.py --file abc123def456       # single file by fileID
  python3 extract_whatsapp_media.py --random 10               # 10 random files
  python3 extract_whatsapp_media.py --random 5 --contact "John"  # 5 random from one contact
"""

import argparse
import ctypes
import ctypes.util
import json
import os
import plistlib
import random
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone, timedelta
import unicodedata
from pathlib import Path

try:
    import piexif
    HAS_PIEXIF = True
except ImportError:
    HAS_PIEXIF = False

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

# macOS native libc for setxattr
_libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)

# Apple Core Data epoch starts at 2001-01-01 00:00:00 UTC (not Unix epoch)
APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)
WHATSAPP_DOMAIN = "AppDomainGroup-group.net.whatsapp.WhatsApp.shared"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def apple_ts_to_datetime(ts: float) -> datetime:
    """Converts an Apple timestamp (UTC) to a datetime in the local machine timezone."""
    utc = APPLE_EPOCH + timedelta(seconds=ts)
    return utc.astimezone()


def local_tz_offset(dt: datetime) -> str:
    """Returns the local timezone offset as ±HH:MM (e.g. -03:00)."""
    offset = dt.utcoffset()
    if offset is None:
        return ''
    total = int(offset.total_seconds())
    sign = '+' if total >= 0 else '-'
    h, m = divmod(abs(total) // 60, 60)
    return f'{sign}{h:02d}:{m:02d}'


def safe_folder_name(name: str) -> str:
    """Strips emojis and characters that are invalid in folder names."""
    # Remove emoji and non-BMP characters
    name = ''.join(
        c for c in name
        if unicodedata.category(c) not in ('So', 'Cs')  # So=symbol, Cs=surrogate
        and ord(c) < 0x10000
    )
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    return name.strip().strip('.') or '_Unknown'


def safe_filename_part(name: str, max_len: int = 40) -> str:
    """Returns a filesystem-safe version of a name for use inside filenames."""
    name = safe_folder_name(name)
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    return name[:max_len]


def extract_jid(relative_path: str) -> str | None:
    """
    Extracts the contact/group JID from a relativePath.
    e.g. Message/Media/15519999910208@s.whatsapp.net/a/3/uuid.jpg -> 15519999910208@s.whatsapp.net
         Message/Media/15519649807-1595615948@g.us/2/3/uuid.jpg   -> 15519649807-1595615948@g.us
    """
    match = re.match(r'^Message/Media/([^/]+)/', relative_path)
    if match:
        return match.group(1)
    return None


def phone_from_jid(jid: str) -> str:
    """
    Extracts the phone number from a JID.
    15519999910208@s.whatsapp.net  -> 15519999910208
    15519649807-1595615948@g.us    -> 15519649807  (group creator's number)
    """
    number = jid.split('@')[0]
    number = number.split('-')[0]  # for groups, keep only the creator's number
    return number


def _macos_setxattr(filepath: Path, name: str, value: bytes) -> None:
    """Writes a macOS extended attribute via native setxattr."""
    try:
        # setxattr(path, name, value, size, position, options)
        ret = _libc.setxattr(
            str(filepath).encode('utf-8'),
            name.encode('utf-8'),
            value,
            len(value),
            0,   # position
            0,   # options
        )
        if ret != 0:
            pass  # xattr is non-critical; silently ignore errors
    except Exception:
        pass


def _set_xattr_str(filepath: Path, key: str, value: str) -> None:
    """Writes a macOS xattr with a string value (binary plist)."""
    _macos_setxattr(filepath, key, plistlib.dumps(value, fmt=plistlib.FMT_BINARY))


def _set_xattr_list(filepath: Path, key: str, value: list) -> None:
    """Writes a macOS xattr with a list value (binary plist)."""
    _macos_setxattr(filepath, key, plistlib.dumps(value, fmt=plistlib.FMT_BINARY))


def _set_xattr_date(filepath: Path, key: str, dt: datetime) -> None:
    """Writes a macOS xattr with a datetime value (binary plist). plistlib requires naive UTC."""
    naive = dt.astimezone(timezone.utc).replace(tzinfo=None)
    _macos_setxattr(filepath, key, plistlib.dumps(naive, fmt=plistlib.FMT_BINARY))


def set_rich_metadata(
    filepath: Path,
    dt: datetime | None,
    contact_name: str,
    jid: str,
    direction: str = 'received',
) -> None:
    """
    Writes rich metadata to the file:
      - EXIF: dates, description, artist, software, JSON comment (JPEG only)
      - macOS Spotlight (xattr): title, description, authors, keywords, creation date
      - Filesystem: mtime/atime set to the original message date
    """
    is_group     = '@g.us' in jid
    chat_type    = 'Group' if is_group else 'Contact'
    display_name = contact_name or jid
    ext          = filepath.suffix.lower()

    # dt is already in local time (converted in apple_ts_to_datetime)
    date_exif    = dt.strftime('%Y:%m:%d %H:%M:%S') if dt else None  # EXIF standard = local time
    date_human   = dt.strftime('%m/%d/%Y at %H:%M') if dt else 'unknown date'
    date_iso     = dt.isoformat() if dt else None
    tz_offset    = local_tz_offset(dt) if dt else ''                  # e.g. -03:00

    title        = f'{display_name} · {dt.strftime("%Y-%m-%d %H:%M")}' if dt else display_name
    description  = f'WhatsApp · {chat_type}: {display_name} · {date_human}'
    phone        = phone_from_jid(jid)
    keywords     = ['WhatsApp', chat_type, display_name, phone, direction]
    if dt:
        keywords.append(dt.strftime('%Y'))
        keywords.append(dt.strftime('%Y-%m'))

    comment_json = json.dumps({
        'source':    'WhatsApp',
        'type':      chat_type.lower(),
        'contact':   display_name,
        'phone':     phone,
        'jid':       jid,
        'date':      date_iso,
        'direction': direction,
    }, ensure_ascii=False)

    # ------------------------------------------------------------------
    # 1. EXIF — JPEG only (piexif does not support PNG)
    # ------------------------------------------------------------------
    if HAS_PIEXIF and ext in ('.jpg', '.jpeg'):
        try:
            try:
                exif_dict = piexif.load(str(filepath))
            except Exception:
                exif_dict = {'0th': {}, 'Exif': {}, 'GPS': {}, '1st': {}}

            ifd0  = exif_dict.setdefault('0th', {})
            exif  = exif_dict.setdefault('Exif', {})

            # Dates in local time (EXIF standard)
            if date_exif:
                ifd0[piexif.ImageIFD.DateTime]          = date_exif.encode()
                exif[piexif.ExifIFD.DateTimeOriginal]   = date_exif.encode()
                exif[piexif.ExifIFD.DateTimeDigitized]  = date_exif.encode()

            # Timezone offset (EXIF 2.31+)
            if tz_offset:
                exif[piexif.ExifIFD.OffsetTimeOriginal]  = tz_offset.encode()
                exif[piexif.ExifIFD.OffsetTimeDigitized] = tz_offset.encode()

            # Description / authorship
            ifd0[piexif.ImageIFD.ImageDescription] = description.encode('utf-8')
            ifd0[piexif.ImageIFD.Artist]           = display_name.encode('utf-8')
            ifd0[piexif.ImageIFD.Copyright]        = 'WhatsApp'.encode()
            ifd0[piexif.ImageIFD.Software]         = 'WhatsApp Media Extractor'.encode()

            # UserComment: ASCII prefix required by EXIF spec
            encoded_comment = b'ASCII\x00\x00\x00' + comment_json.encode('utf-8')
            exif[piexif.ExifIFD.UserComment] = encoded_comment

            piexif.insert(piexif.dump(exif_dict), str(filepath))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 2. macOS extended attributes (Spotlight / Finder)
    # ------------------------------------------------------------------
    _set_xattr_str (filepath, 'com.apple.metadata:kMDItemTitle',       title)
    _set_xattr_str (filepath, 'com.apple.metadata:kMDItemDescription', description)
    _set_xattr_str (filepath, 'com.apple.metadata:kMDItemComment',     comment_json)
    _set_xattr_list(filepath, 'com.apple.metadata:kMDItemAuthors',     [display_name])
    _set_xattr_list(filepath, 'com.apple.metadata:kMDItemKeywords',    keywords)

    if dt:
        _set_xattr_date(filepath, 'com.apple.metadata:kMDItemContentCreationDate', dt)

    # ------------------------------------------------------------------
    # 3. Filesystem timestamps (mtime/atime → original message date)
    # ------------------------------------------------------------------
    if dt:
        ts = dt.timestamp()
        os.utime(str(filepath), (ts, ts))


# ---------------------------------------------------------------------------
# Backup discovery
# ---------------------------------------------------------------------------

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
    if base.exists():
        backups = [d for d in base.iterdir() if d.is_dir() and (d / 'Manifest.db').exists()]
        if backups:
            backups.sort(key=lambda d: (d / 'Manifest.db').stat().st_mtime, reverse=True)
            return backups[0]

    sys.exit('[ERROR] No backup found. Use --backup to specify the path.')


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

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


def load_contact_map(chat_conn: sqlite3.Connection) -> dict[str, str]:
    """Returns {jid: display_name} from ZWACHATSESSION."""
    rows = chat_conn.execute(
        "SELECT ZCONTACTJID, ZPARTNERNAME FROM ZWACHATSESSION "
        "WHERE ZCONTACTJID IS NOT NULL"
    ).fetchall()
    return {jid: (name or '').strip() for jid, name in rows}


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """Returns the list of column names for a given table."""
    try:
        return [r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()]
    except Exception:
        return []


def _tables(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]


def inspect_db(chat_conn: sqlite3.Connection) -> None:
    """Prints the relevant ChatStorage.sqlite schema for debugging purposes."""
    tables = _tables(chat_conn)
    interesting = [t for t in tables if 'WA' in t.upper() or 'CHAT' in t.upper() or 'MESSAGE' in t.upper()]
    print('\n[INSPECT] Tables found in ChatStorage.sqlite:')
    for t in interesting:
        cols = _table_columns(chat_conn, t)
        print(f'  {t}: {cols}')

    for table in ['ZWAMESSAGE', 'ZWAMEDIAITEM']:
        if table not in tables:
            continue
        cols = _table_columns(chat_conn, table)
        date_cols = [c for c in cols if any(k in c.upper() for k in ('DATE', 'TIME', 'STAMP'))]
        path_cols = [c for c in cols if any(k in c.upper() for k in ('PATH', 'URL', 'LOCAL', 'FILE'))]
        print(f'\n[INSPECT] {table} — date columns: {date_cols} | path columns: {path_cols}')
        if date_cols and path_cols:
            sample = chat_conn.execute(
                f'SELECT {path_cols[0]}, {date_cols[0]} FROM {table} '
                f'WHERE {path_cols[0]} IS NOT NULL AND {date_cols[0]} IS NOT NULL LIMIT 3'
            ).fetchall()
            for row in sample:
                print(f'  path={row[0]}  ts={row[1]}')
    print()


def load_message_info(chat_conn: sqlite3.Connection) -> dict[str, tuple[float, str]]:
    """
    Returns {filename: (apple_timestamp, direction)} where direction is
    'sent' (you sent it) or 'received' (sent by the contact).

    Strategy 1: JOIN ZWAMEDIAITEM -> ZWAMESSAGE for accurate send date + direction.
    Strategy 2: ZMEDIAURLDATE directly from ZWAMEDIAITEM as a fallback.
    """
    info_map: dict[str, tuple[float, str]] = {}

    # Strategy 1: JOIN for send date and direction
    try:
        rows = chat_conn.execute("""
            SELECT mi.ZMEDIALOCALPATH, m.ZMESSAGEDATE, m.ZISFROMME
            FROM ZWAMEDIAITEM mi
            JOIN ZWAMESSAGE m ON mi.ZMESSAGE = m.Z_PK
            WHERE mi.ZMEDIALOCALPATH IS NOT NULL
              AND m.ZMESSAGEDATE IS NOT NULL
        """).fetchall()
        for path, ts, fromme in rows:
            fname = Path(path).name
            if fname:
                info_map[fname] = (ts, 'sent' if fromme else 'received')
    except sqlite3.OperationalError:
        pass

    # Strategy 2: direct ZMEDIAURLDATE (no JOIN, no direction info)
    try:
        rows = chat_conn.execute("""
            SELECT ZMEDIALOCALPATH, ZMEDIAURLDATE
            FROM ZWAMEDIAITEM
            WHERE ZMEDIALOCALPATH IS NOT NULL
              AND ZMEDIAURLDATE IS NOT NULL
        """).fetchall()
        for path, ts in rows:
            fname = Path(path).name
            if fname and fname not in info_map:
                info_map[fname] = (ts, 'received')
    except sqlite3.OperationalError:
        pass

    return info_map


def query_media_files(
    manifest_conn: sqlite3.Connection,
    single_file: str | None = None
) -> list[tuple[str, str]]:
    """
    Returns a list of (fileID, relativePath) for all WhatsApp images in the backup.
    If single_file is given, restricts to that fileID (prefix match).
    """
    base_sql = """
        SELECT fileID, relativePath FROM Files
        WHERE domain = ?
        AND relativePath LIKE 'Message/Media/%'
        AND relativePath NOT LIKE '%.thumb%'
        AND (
            relativePath LIKE '%.jpg'
            OR relativePath LIKE '%.jpeg'
            OR relativePath LIKE '%.png'
        )
    """
    params: list = [WHATSAPP_DOMAIN]

    if single_file:
        base_sql += " AND fileID LIKE ?"
        params.append(f'{single_file}%')

    return manifest_conn.execute(base_sql, params).fetchall()


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def build_dest_path(
    output_dir: Path,
    contact_name: str,
    dt: datetime | None,
    original_filename: str,
    jid: str,
) -> Path:
    """Builds the destination path for a media file."""
    if contact_name:
        folder = safe_folder_name(contact_name)
    else:
        folder = f'_Unknown/{safe_folder_name(jid)}'

    name_part  = safe_filename_part(contact_name or jid)
    phone_part = phone_from_jid(jid)
    ext        = Path(original_filename).suffix.lower()

    if dt:
        month_folder = dt.strftime('%Y-%m')
        # e.g. John_Smith_15519999910208_2025-12-13_17-39-44.jpg
        filename = f'{name_part}_{phone_part}_{dt.strftime("%Y-%m-%d_%H-%M-%S")}{ext}'
    else:
        month_folder = '_no_date'
        filename = f'{name_part}_{phone_part}_{original_filename}'

    dest = output_dir / folder / month_folder / filename

    # Avoid filename collisions
    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
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

    all_files = query_media_files(manifest_conn, single_file)
    print(f'[INFO] Media files found      : {len(all_files)}')

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
        info = info_map.get(original_filename)
        ts, direction = info if info else (None, 'received')
        dt = apple_ts_to_datetime(ts) if ts is not None else None

        label = contact_name or jid
        print(f'[{idx:>6}/{total}] {label} — {original_filename}', end='')

        # Locate the physical file in the backup
        src = backup_path / file_id[:2] / file_id
        if not src.exists():
            print(' [NOT FOUND]')
            not_found += 1
            continue

        dest = build_dest_path(output_dir, contact_name, dt, original_filename, jid)

        if dry_run:
            print(f'\n         -> {dest}  (dry-run)')
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dest))
            set_rich_metadata(dest, dt, contact_name, jid, direction)
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
    print(f'{"Contact/Group":<45} {"Photos":>6}')
    print('-' * 53)
    for name, count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f'{name:<45} {count:>6}')
    print('=' * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Extract WhatsApp photos from a local iPhone backup.'
    )
    parser.add_argument(
        '--backup', type=Path, default=None,
        help='Path to the iPhone backup (auto-detected if omitted)'
    )
    parser.add_argument(
        '--output', type=Path, default=Path(__file__).parent / 'WhatsApp_Media_Export',
        help='Output folder (default: ./WhatsApp_Media_Export)'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Simulate extraction without copying any files'
    )
    parser.add_argument(
        '--contact', type=str, default=None,
        metavar='NAME',
        help='Extract only files from contacts whose name contains NAME (case-insensitive)'
    )
    parser.add_argument(
        '--file', type=str, default=None,
        metavar='FILE_ID',
        help='Extract a single file by its SHA1 fileID (prefix match supported)'
    )
    parser.add_argument(
        '--random', type=int, default=None,
        metavar='N',
        dest='random_sample',
        help='Extract N randomly selected files (combinable with --contact)'
    )
    parser.add_argument(
        '--inspect-db', action='store_true',
        help='Print the ChatStorage.sqlite schema and exit (useful for debugging)'
    )

    args = parser.parse_args()

    if args.random_sample is not None and args.random_sample < 1:
        sys.exit('[ERROR] --random must be greater than zero.')

    backup_path = args.backup or find_backup_path()

    if not HAS_PIEXIF:
        print('[WARNING] piexif is not installed — EXIF fields will not be written.')
        print('          Install with: pip3 install piexif')
        print('          (macOS Spotlight/xattr and timestamps will still work)\n')

    extract(
        backup_path=backup_path,
        output_dir=args.output,
        dry_run=args.dry_run,
        filter_contact=args.contact,
        single_file=args.file,
        random_sample=args.random_sample,
        inspect=args.inspect_db,
    )


if __name__ == '__main__':
    main()
