"""
Android WhatsApp media extraction.

Android backups keep media as regular files under the WhatsApp folder. The
database schema changes across WhatsApp versions, so this module uses runtime
introspection and common column candidates instead of hard-coded SELECT shapes.
"""

import argparse
import random
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .constants import DOCS_FOLDER, DEFAULT_TYPES, FILE_TYPES
from .extractor import build_dest_path
from .metadata import HAS_PIEXIF, set_rich_metadata
from .state import load_last_run, save_last_run
from .utils import get_file_type


CONTACT_NAME_COLUMNS = (
    'display_name',
    'wa_name',
    'given_name',
    'full_name',
    'nickname',
    'sort_name',
    'phone_number',
    'number',
)

JID_COLUMNS = (
    'key_remote_jid',
    'remote_jid',
    'jid',
    'raw_string',
    'chat_jid',
    'subject',
)

TIMESTAMP_COLUMNS = (
    'timestamp',
    'message_timestamp',
    'received_timestamp',
    'receipt_server_timestamp',
    'send_timestamp',
)

FROM_ME_COLUMNS = (
    'key_from_me',
    'from_me',
    'is_from_me',
)

MEDIA_COLUMNS = (
    'media_name',
    'media_url',
    'media_file_path',
    'file_path',
    'local_path',
    'media_path',
    'thumbnail_path',
)

MIME_COLUMNS = (
    'media_mime_type',
    'mime_type',
)


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _table_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [row[0] for row in rows]


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    try:
        rows = conn.execute(f'PRAGMA table_info({_quote_identifier(table)})').fetchall()
    except sqlite3.DatabaseError:
        return []
    return [row[1] for row in rows]


def _first_existing(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    available = set(columns)
    for candidate in candidates:
        if candidate in available:
            return candidate
    return None


def _find_existing_file(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if path.exists() and path.is_file():
            return path
    return None


def _find_database(backup_path: Path, filename: str) -> Path | None:
    candidates = [
        backup_path / filename,
        backup_path / 'Databases' / filename,
        backup_path / 'databases' / filename,
        backup_path / 'WhatsApp' / filename,
        backup_path / 'WhatsApp' / 'Databases' / filename,
        backup_path / 'WhatsApp' / 'databases' / filename,
    ]
    found = _find_existing_file(candidates)
    if found:
        return found

    matches = sorted(backup_path.rglob(filename))
    return matches[0] if matches else None


def _media_roots(backup_path: Path) -> list[Path]:
    candidates = [
        backup_path / 'Media',
        backup_path / 'WhatsApp' / 'Media',
        backup_path / 'media',
        backup_path / 'WhatsApp' / 'media',
    ]
    roots: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        if not path.exists() or not path.is_dir():
            continue
        key = str(path.resolve()).casefold()
        if key in seen:
            continue
        seen.add(key)
        roots.append(path)
    return roots


def _normalize_android_path(value: str, backup_path: Path) -> list[Path]:
    raw = value.strip().replace('\\', '/')
    if not raw:
        return []

    path = Path(raw)
    if path.is_absolute() and path.exists():
        return [path]

    prefixes = (
        '/sdcard/WhatsApp/',
        '/sdcard/Android/media/com.whatsapp/WhatsApp/',
        '/storage/emulated/0/WhatsApp/',
        '/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/',
        '/mnt/sdcard/WhatsApp/',
        '/mnt/sdcard/Android/media/com.whatsapp/WhatsApp/',
        'WhatsApp/',
    )
    relative_candidates = [raw]
    for prefix in prefixes:
        if raw.startswith(prefix):
            relative_candidates.append(raw[len(prefix):])

    paths: list[Path] = []
    for rel in dict.fromkeys(relative_candidates):
        rel_path = Path(rel)
        paths.append(backup_path / rel_path)
        paths.append(backup_path / 'WhatsApp' / rel_path)
        if rel_path.parts[:1] != ('Media',):
            paths.append(backup_path / 'Media' / rel_path)
            paths.append(backup_path / 'WhatsApp' / 'Media' / rel_path)
    return paths


def _build_media_index(roots: list[Path], active_types: set[str]) -> dict[str, list[Path]]:
    active_exts = frozenset().union(*(FILE_TYPES[t] for t in active_types if t in FILE_TYPES))
    index: dict[str, list[Path]] = {}

    for root in roots:
        for path in root.rglob('*'):
            if not path.is_file():
                continue
            name = path.name
            lower_name = name.lower()
            if '.thumb' in lower_name or '.mmsthumb' in lower_name or '.favicon' in lower_name:
                continue
            if path.suffix.lower() not in active_exts:
                continue
            index.setdefault(name, []).append(path)

    return index


def _android_ts_to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return None
    if ts <= 0:
        return None

    # WhatsApp Android timestamps are usually Unix milliseconds.
    if ts > 10_000_000_000:
        ts = ts / 1000
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()


def _display_name_from_parts(parts: Iterable[Any]) -> str:
    clean = [str(part).strip() for part in parts if part is not None and str(part).strip()]
    return ' '.join(dict.fromkeys(clean))


def _load_wa_contacts(wa_db: Path | None) -> dict[str, str]:
    if not wa_db:
        return {}

    conn = sqlite3.connect(str(wa_db))
    conn.row_factory = sqlite3.Row
    contacts: dict[str, str] = {}

    try:
        tables = _table_names(conn)
        for table in tables:
            columns = _table_columns(conn, table)
            jid_col = _first_existing(columns, JID_COLUMNS)
            if not jid_col:
                continue

            name_cols = [col for col in CONTACT_NAME_COLUMNS if col in columns]
            if not name_cols:
                continue

            selected = [_quote_identifier(jid_col), *(_quote_identifier(col) for col in name_cols)]
            rows = conn.execute(
                f'SELECT {", ".join(selected)} FROM {_quote_identifier(table)} '
                f'WHERE {_quote_identifier(jid_col)} IS NOT NULL'
            ).fetchall()
            for row in rows:
                jid = str(row[jid_col]).strip()
                if not jid:
                    continue
                name = _display_name_from_parts(row[col] for col in name_cols)
                if name:
                    contacts[jid] = name
    finally:
        conn.close()

    return contacts


def _load_chat_list_contacts(conn: sqlite3.Connection) -> dict[str, str]:
    if 'chat_list' not in _table_names(conn):
        return {}

    columns = _table_columns(conn, 'chat_list')
    jid_col = _first_existing(columns, JID_COLUMNS)
    if not jid_col:
        return {}

    name_cols = [
        col for col in (
            'subject',
            'display_name',
            'name',
            'sort_name',
            'key_remote_jid',
        )
        if col in columns and col != jid_col
    ]
    if not name_cols:
        name_cols = [jid_col]

    selected = [_quote_identifier(jid_col), *(_quote_identifier(col) for col in name_cols)]
    rows = conn.execute(
        f'SELECT {", ".join(selected)} FROM chat_list '
        f'WHERE {_quote_identifier(jid_col)} IS NOT NULL'
    ).fetchall()

    contacts: dict[str, str] = {}
    for row in rows:
        jid = str(row[jid_col]).strip()
        name = _display_name_from_parts(row[col] for col in name_cols)
        if jid and name:
            contacts[jid] = name
    return contacts


def _inspect_android_db(msg_conn: sqlite3.Connection, wa_db: Path | None) -> None:
    print('\n[INSPECT] Android msgstore.db tables:')
    for table in _table_names(msg_conn):
        if any(token in table.lower() for token in ('message', 'chat', 'media', 'jid')):
            print(f'  {table}: {_table_columns(msg_conn, table)}')

    if not wa_db:
        print('\n[INSPECT] wa.db not found.')
        return

    wa_conn = sqlite3.connect(str(wa_db))
    try:
        print('\n[INSPECT] Android wa.db contact-like tables:')
        for table in _table_names(wa_conn):
            columns = _table_columns(wa_conn, table)
            if any(col in columns for col in (*JID_COLUMNS, *CONTACT_NAME_COLUMNS)):
                print(f'  {table}: {columns}')
    finally:
        wa_conn.close()
    print()


def _message_query(conn: sqlite3.Connection) -> tuple[str, list[str]]:
    tables = _table_names(conn)
    table = 'messages' if 'messages' in tables else None
    if not table:
        raise RuntimeError('messages table not found in msgstore.db')

    columns = _table_columns(conn, table)
    selected = ['rowid', *columns]
    media_markers = [col for col in (*MEDIA_COLUMNS, *MIME_COLUMNS) if col in columns]

    where = ''
    if media_markers:
        checks = [
            f'({_quote_identifier(col)} IS NOT NULL AND {_quote_identifier(col)} != "")'
            for col in media_markers
        ]
        where = ' WHERE ' + ' OR '.join(checks)

    sql = f'SELECT {", ".join(_quote_identifier(col) for col in selected)} FROM {table}{where}'
    return sql, columns


def _resolve_media_file(
    row: sqlite3.Row,
    columns: list[str],
    backup_path: Path,
    media_index: dict[str, list[Path]],
) -> Path | None:
    path_values = [
        str(row[col]).strip()
        for col in MEDIA_COLUMNS
        if col in columns and row[col] is not None and str(row[col]).strip()
    ]

    for value in path_values:
        found = _find_existing_file(_normalize_android_path(value, backup_path))
        if found:
            return found

    filenames = [Path(value).name for value in path_values if Path(value).name]
    for filename in filenames:
        matches = media_index.get(filename)
        if matches:
            return matches[0]

    return None


def _row_jid(row: sqlite3.Row, columns: list[str]) -> str:
    for column in JID_COLUMNS:
        if column in columns and row[column] is not None and str(row[column]).strip():
            return str(row[column]).strip()
    return 'unknown'


def _row_direction(row: sqlite3.Row, columns: list[str]) -> str:
    column = _first_existing(columns, FROM_ME_COLUMNS)
    if not column:
        return 'received'
    try:
        return 'sent' if int(row[column] or 0) else 'received'
    except (TypeError, ValueError):
        return 'received'


def _row_datetime(row: sqlite3.Row, columns: list[str]) -> datetime | None:
    for column in TIMESTAMP_COLUMNS:
        if column not in columns:
            continue
        dt = _android_ts_to_datetime(row[column])
        if dt:
            return dt
    return None


def extract_android(
    backup_path: Path,
    output_dir: Path,
    dry_run: bool = False,
    filter_contact: str | None = None,
    random_sample: int | None = None,
    inspect: bool = False,
    file_types: set[str] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    update_state: bool = False,
) -> None:
    run_started_at = datetime.now().astimezone().replace(microsecond=0)
    msgstore_db = _find_database(backup_path, 'msgstore.db')
    if not msgstore_db:
        sys.exit(f'[ERROR] msgstore.db not found under: {backup_path}')

    wa_db = _find_database(backup_path, 'wa.db')
    media_roots = _media_roots(backup_path)
    if not media_roots:
        sys.exit(f'[ERROR] WhatsApp Media folder not found under: {backup_path}')

    active_types = file_types or set(FILE_TYPES.keys())

    print(f'[INFO] Android backup : {backup_path}')
    print(f'[INFO] msgstore.db    : {msgstore_db}')
    print(f'[INFO] wa.db          : {wa_db or "not found"}')
    print(f'[INFO] Media folders  : {", ".join(str(root) for root in media_roots)}')
    print(f'[INFO] Output         : {output_dir}')
    print(f'[INFO] Types selected : {", ".join(sorted(active_types))}')
    if 'doc' in active_types:
        print(f'[INFO] Documents go   : {DOCS_FOLDER}/')
    if dry_run:
        print('[INFO] DRY-RUN mode -- no files will be copied.\n')

    msg_conn = sqlite3.connect(str(msgstore_db))
    msg_conn.row_factory = sqlite3.Row

    try:
        if inspect:
            _inspect_android_db(msg_conn, wa_db)

        contact_map = _load_wa_contacts(wa_db)
        contact_map.update({k: v for k, v in _load_chat_list_contacts(msg_conn).items() if k not in contact_map})

        media_index = _build_media_index(media_roots, active_types)
        sql, columns = _message_query(msg_conn)
        rows = msg_conn.execute(sql).fetchall()

        items = []
        active_exts = frozenset().union(*(FILE_TYPES[t] for t in active_types if t in FILE_TYPES))
        for row in rows:
            src = _resolve_media_file(row, columns, backup_path, media_index)
            if not src:
                continue
            ext = src.suffix.lower()
            if ext not in active_exts:
                continue
            dt = _row_datetime(row, columns)
            if date_from and (dt is None or dt < date_from):
                continue
            if date_to and (dt is None or dt > date_to):
                continue

            jid = _row_jid(row, columns)
            contact_name = contact_map.get(jid, '')
            label = contact_name or jid
            if filter_contact:
                needle = filter_contact.lower()
                if needle not in label.lower() and needle not in jid.lower():
                    continue

            items.append((row, src, jid, contact_name, dt))

        if random_sample is not None:
            n = min(random_sample, len(items))
            items = random.sample(items, n)
            print(f'[INFO] Random sample  : {n} file(s) selected')

        print(f'[INFO] Contacts loaded: {len(contact_map)}')
        print(f'[INFO] Media indexed  : {sum(len(paths) for paths in media_index.values())}')
        print(f'[INFO] Media selected : {len(items)}')
        print()

        stats: dict[str, int] = {}
        total_bytes = 0
        copied = 0

        total = len(items)
        for idx, (row, src, jid, contact_name, dt) in enumerate(items, 1):
            ftype = get_file_type(src.suffix.lower()) or 'img'
            direction = _row_direction(row, columns)
            label = contact_name or jid
            dest = build_dest_path(output_dir, contact_name, dt, src.name, jid, ftype)

            print(f'[{idx:>6}/{total}] [{ftype:>5}] {label} -- {src.name}', end='')
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

        print('\n' + '=' * 60)
        print('FINAL REPORT')
        print('=' * 60)
        print(f'Processed   : {copied}')
        if not dry_run:
            print(f'Total size  : {total_bytes / 1_073_741_824:.2f} GB')
        print()
        print(f'{"Contact/Group":<45} {"Files":>6}')
        print('-' * 53)
        for name, count in sorted(stats.items(), key=lambda item: -item[1]):
            print(f'{name:<45} {count:>6}')
        print('=' * 60)

        if update_state and not dry_run:
            path = save_last_run(output_dir, run_started_at)
            print(f'[INFO] State updated : {path}')
    finally:
        msg_conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Extract WhatsApp media from an Android WhatsApp folder.'
    )
    parser.add_argument(
        '--platform', choices=['android'], default='android',
        help='Platform selector for scripts that auto-detect command variants.'
    )
    parser.add_argument(
        '--backup', type=Path, required=True,
        help='Path to the Android WhatsApp folder, e.g. /sdcard/WhatsApp or a local copy.'
    )
    parser.add_argument(
        '--output', type=Path, default=Path(__file__).parent.parent / 'WhatsApp_Media_Export',
        help='Output folder (default: ./WhatsApp_Media_Export)'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Simulate extraction without copying any files'
    )
    parser.add_argument(
        '--contact', type=str, default=None, metavar='NAME',
        help='Extract only files from contacts/groups whose name or JID contains NAME.'
    )
    parser.add_argument(
        '--random', type=int, default=None, metavar='N', dest='random_sample',
        help='Extract N randomly selected files after filters are applied.'
    )
    parser.add_argument(
        '--type', nargs='+', default=None, metavar='TYPE', dest='file_types',
        choices=[*FILE_TYPES.keys(), 'all'],
        help='File types to include: img gif video audio doc webp all.'
    )
    parser.add_argument(
        '--exclude-type', nargs='+', default=None, metavar='TYPE', dest='exclude_types',
        choices=list(FILE_TYPES.keys()),
        help='File types to exclude from the selection.'
    )
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument(
        '--from', type=str, default=None, metavar='YYYY-MM-DD', dest='date_from',
        help='Extract only files on or after this date.'
    )
    date_group.add_argument(
        '--since-last-run', action='store_true',
        help='Resume from the last successful extraction recorded in the output folder'
    )
    parser.add_argument(
        '--to', type=str, default=None, metavar='YYYY-MM-DD', dest='date_to',
        help='Extract only files on or before this date.'
    )
    parser.add_argument(
        '--inspect-db', action='store_true',
        help='Print Android msgstore.db and wa.db schema hints before extracting.'
    )

    args = parser.parse_args()

    if args.random_sample is not None and args.random_sample < 1:
        sys.exit('[ERROR] --random must be greater than zero.')

    def _parse_date(value: str, param: str) -> datetime:
        try:
            parsed = datetime.strptime(value, '%Y-%m-%d')
            return parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
        except ValueError:
            sys.exit(f'[ERROR] Invalid date for {param}: "{value}". Use YYYY-MM-DD format.')

    date_from = _parse_date(args.date_from, '--from') if args.date_from else None
    if args.since_last_run:
        try:
            date_from = load_last_run(args.output)
        except ValueError as exc:
            sys.exit(f'[ERROR] {exc}')

        if date_from:
            print(f'[INFO] Resuming from last run: {date_from.strftime("%Y-%m-%d")}')
        else:
            print('[INFO] No previous run state found; extracting from the beginning.')

    date_to = _parse_date(args.date_to, '--to').replace(
        hour=23, minute=59, second=59
    ) if args.date_to else None

    if date_from and date_to and date_from > date_to:
        sys.exit('[ERROR] --from date cannot be after --to date.')

    if not args.file_types:
        file_types = set(DEFAULT_TYPES)
    elif 'all' in args.file_types:
        file_types = set(FILE_TYPES.keys())
    else:
        file_types = set(args.file_types)

    if args.exclude_types:
        file_types -= set(args.exclude_types)

    if not file_types:
        sys.exit('[ERROR] No file types remaining after applying --exclude-type.')

    if not HAS_PIEXIF:
        print('[WARNING] piexif is not installed -- EXIF fields will not be written.')
        print('          Install with: pip3 install piexif')
        print('          (metadata side effects that do not need piexif will still run)\n')

    extract_android(
        backup_path=args.backup,
        output_dir=args.output,
        dry_run=args.dry_run,
        filter_contact=args.contact,
        random_sample=args.random_sample,
        inspect=args.inspect_db,
        file_types=file_types,
        date_from=date_from,
        date_to=date_to,
        update_state=args.since_last_run,
    )


if __name__ == '__main__':
    main()
