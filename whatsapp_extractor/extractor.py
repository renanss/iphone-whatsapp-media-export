"""
Core extraction logic — builds destination paths and drives the extraction loop.
"""

import csv
import json
import os
import random
import shutil
import sqlite3
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from .backup import find_backup_path, find_chatstorage, is_backup_encrypted, open_encrypted_backup
from .constants import DOCS_FOLDER, FILE_TYPES, GIF_MESSAGE_TYPES, WHATSAPP_DOMAIN
from .database import inspect_db, load_contact_map, load_message_info, query_media_files
from .metadata import set_rich_metadata
from .state import save_last_run
from .utils import apple_ts_to_datetime, extract_jid, get_file_type, phone_from_jid, safe_filename_part, safe_folder_name


def _format_size(num_bytes: int | None) -> str:
    if num_bytes is None:
        return '—'
    value = float(num_bytes)
    for unit in ('bytes', 'KB', 'MB', 'GB'):
        if value < 1024 or unit == 'GB':
            if unit == 'bytes':
                return f'{int(value)} bytes'
            return f'{value:.1f} {unit}'
        value /= 1024


def _empty_summary() -> dict[str, Any]:
    return {
        'total_files': 0,
        'total_size_bytes': 0,
        'total_size_gb': 0.0,
        'by_type': {},
        'by_contact': {},
        'by_month': {},
        'date_range': {'earliest': None, 'latest': None},
    }


def _build_report_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return _empty_summary()

    by_type = Counter(record['type'] for record in records)
    by_contact = Counter(record['contact'] for record in records)
    by_month = Counter(record['month'] for record in records if record['month'])
    dates = sorted(record['date'] for record in records if record['date'])
    total_size = sum(record['size'] or 0 for record in records)

    return {
        'total_files': len(records),
        'total_size_bytes': total_size,
        'total_size_gb': round(total_size / 1_073_741_824, 4),
        'by_type': dict(sorted(by_type.items())),
        'by_contact': dict(sorted(by_contact.items(), key=lambda item: (-item[1], item[0]))),
        'by_month': dict(sorted(by_month.items())),
        'date_range': {
            'earliest': dates[0] if dates else None,
            'latest': dates[-1] if dates else None,
        },
    }


def _print_stats_report(records: list[dict[str, Any]]) -> None:
    summary = _build_report_summary(records)

    print('\n' + '=' * 60)
    print('BACKUP STATS')
    print('=' * 60)
    print(f'Total files : {summary["total_files"]}')
    print(f'Total size  : {_format_size(summary["total_size_bytes"])}')
    print(f'Date range  : {summary["date_range"]["earliest"] or "—"} → {summary["date_range"]["latest"] or "—"}')

    print('\nFiles by type')
    print('-' * 53)
    for ftype, count in summary['by_type'].items():
        print(f'{ftype:<45} {count:>6}')

    print('\nTop contacts/groups')
    print('-' * 53)
    for contact, count in list(summary['by_contact'].items())[:20]:
        print(f'{contact:<45} {count:>6}')

    print('\nFiles by month')
    print('-' * 53)
    for month, count in summary['by_month'].items():
        print(f'{month:<45} {count:>6}')
    print('=' * 60)


def _write_report(report_path: Path, records: list[dict[str, Any]]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = report_path.suffix.lower()

    if suffix == '.json':
        payload = {
            'summary': _build_report_summary(records),
            'files': records,
        }
        report_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )
    elif suffix == '.csv':
        fieldnames = [
            'status',
            'contact',
            'jid',
            'type',
            'date',
            'month',
            'size',
            'direction',
            'source',
            'destination',
            'file_id',
        ]
        with report_path.open('w', encoding='utf-8', newline='') as f:
            summary = _build_report_summary(records)
            writer = csv.writer(f)
            writer.writerow(['section', 'key', 'value'])
            writer.writerow(['summary', 'total_files', summary['total_files']])
            writer.writerow(['summary', 'total_size_bytes', summary['total_size_bytes']])
            writer.writerow(['summary', 'total_size_gb', summary['total_size_gb']])
            writer.writerow(['summary', 'date_earliest', summary['date_range']['earliest'] or ''])
            writer.writerow(['summary', 'date_latest', summary['date_range']['latest'] or ''])
            for key, value in summary['by_type'].items():
                writer.writerow(['by_type', key, value])
            for key, value in summary['by_contact'].items():
                writer.writerow(['by_contact', key, value])
            for key, value in summary['by_month'].items():
                writer.writerow(['by_month', key, value])
            writer.writerow([])
            writer.writerow(['files', *fieldnames])
            for record in records:
                writer.writerow(['file', *(record.get(field) for field in fieldnames)])
    else:
        sys.exit('[ERROR] --report path must end with .json or .csv.')

    print(f'[INFO] Report written         : {report_path}')


def _validate_report_path(report_path: Path | None) -> None:
    if report_path and report_path.suffix.lower() not in ('.json', '.csv'):
        sys.exit('[ERROR] --report path must end with .json or .csv.')


try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    tqdm = None
    HAS_TQDM = False


def build_dest_path(
    output_dir: Path,
    contact_name: str,
    dt: datetime | None,
    original_filename: str,
    jid: str,
    ftype: str | None = None,
    avoid_collisions: bool = True,
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
    if avoid_collisions and dest.exists():
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
    filter_jids: set[str] | None = None,
    single_file: str | None = None,
    random_sample: int | None = None,
    inspect: bool = False,
    file_types: set[str] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    min_size: int | None = None,
    max_size: int | None = None,
    group_filter: str = 'all',
    stats_only: bool = False,
    report_path: Path | None = None,
    password: str | None = None,
    verbose: bool = False,
    update_state: bool = False,
) -> None:
    _validate_report_path(report_path)
    run_started_at = datetime.now().astimezone().replace(microsecond=0)

    manifest_db = backup_path / 'Manifest.db'
    if not manifest_db.exists():
        sys.exit(f'[ERROR] Manifest.db not found in: {backup_path}')

    print(f'[INFO] Backup : {backup_path}')
    print(f'[INFO] Output : {output_dir}')
    if dry_run:
        print('[INFO] DRY-RUN mode — no files will be copied.\n')
    if stats_only:
        print('[INFO] STATS-ONLY mode — no files will be copied.\n')

    # Encrypted backup: auto-detect and require a password
    encrypted = is_backup_encrypted(backup_path)
    enc_backup = None
    tmp_manifest_path: str | None = None

    if encrypted and not password:
        sys.exit(
            '[ERROR] This backup is encrypted. Pass --password <your iTunes passphrase>.'
        )
    if password and not encrypted:
        print('[WARNING] --password given but backup does not appear encrypted; ignoring.\n')
        password = None

    if password:
        print('[INFO] Encrypted backup — decrypting (this may be slow on large backups).')
        enc_backup = open_encrypted_backup(backup_path, password)
        # Decrypt Manifest.db to a temp file so the rest of the code can
        # continue to read it with plain sqlite3.
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp_manifest_path = tmp.name
        enc_backup.save_manifest_file(tmp_manifest_path)
        manifest_conn = sqlite3.connect(tmp_manifest_path)
    else:
        manifest_conn = sqlite3.connect(str(manifest_db))

    # Copy ChatStorage to a temp file to avoid locking the backup
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
        tmp_path = tmp.name

    if enc_backup is not None:
        # Decrypt ChatStorage.sqlite directly into the tmp path
        enc_backup.extract_file(
            relative_path='ChatStorage.sqlite',
            domain_like=WHATSAPP_DOMAIN,
            output_filename=tmp_path,
        )
    else:
        chatstorage_src = find_chatstorage(manifest_conn, backup_path)
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

    if min_size is not None or max_size is not None:
        def _size_in_range(rpath: str) -> bool:
            info = info_map.get(Path(rpath).name)
            size = info[3] if info else None
            if size is None:
                return False
            if min_size is not None and size < min_size:
                return False
            if max_size is not None and size > max_size:
                return False
            return True

        all_files = [(fid, rpath) for fid, rpath in all_files if _size_in_range(rpath)]
        label_min = _format_size(min_size)
        label_max = _format_size(max_size)
        print(f'[INFO] Size range filter      : {label_min} → {label_max}')
        print(f'[INFO] Files after size filter: {len(all_files)}')

    if group_filter not in ('all', 'exclude', 'only'):
        sys.exit(f'[ERROR] Invalid group_filter: {group_filter}')

    if group_filter != 'all':
        want_groups = group_filter == 'only'
        all_files = [
            (fid, rpath) for fid, rpath in all_files
            if ((extract_jid(rpath) or '').endswith('@g.us')) == want_groups
        ]
        label = 'groups only' if want_groups else 'personal chats only'
        print(f'[INFO] Group filter           : {label}')
        print(f'[INFO] Files after group filter: {len(all_files)}')

    # Filter by contact — filter_jids (exact JIDs, from GUI) takes priority
    # over filter_contact (substring name match, from CLI).
    if filter_jids is not None:
        all_files = [
            (fid, rpath) for fid, rpath in all_files
            if extract_jid(rpath) in filter_jids
        ]
        names = [contact_map.get(j, j) for j in filter_jids]
        print(f'[INFO] Contact filter ({len(filter_jids)}): {", ".join(sorted(names))}')
        print(f'[INFO] Files after contact filter : {len(all_files)}')
    elif filter_contact:
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

    def _media_record(
        file_id: str,
        relative_path: str,
        status: str = 'selected',
        destination: Path | None = None,
    ) -> dict[str, Any]:
        jid = extract_jid(relative_path) or 'unknown'
        contact_name = contact_map.get(jid, '')
        original_filename = Path(relative_path).name
        ext = Path(original_filename).suffix.lower()
        info = info_map.get(original_filename)
        ts, direction, msgtype, size = info if info else (None, 'received', 0, None)
        dt = apple_ts_to_datetime(ts) if ts is not None else None

        if msgtype in GIF_MESSAGE_TYPES and ext == '.mp4':
            ftype = 'gif'
        else:
            ftype = get_file_type(ext) or 'img'

        return {
            'status': status,
            'contact': contact_name or jid,
            'jid': jid,
            'type': ftype,
            'date': dt.isoformat() if dt else None,
            'month': dt.strftime('%Y-%m') if dt else None,
            'size': size,
            'direction': direction,
            'source': relative_path,
            'destination': str(destination) if destination else None,
            'file_id': file_id,
        }

    if stats_only:
        records = [_media_record(file_id, relative_path) for file_id, relative_path in all_files]
        _print_stats_report(records)
        if report_path:
            _write_report(report_path, records)

        chat_conn.close()
        manifest_conn.close()
        os.unlink(tmp_path)
        if tmp_manifest_path and os.path.exists(tmp_manifest_path):
            os.unlink(tmp_manifest_path)
        return

    # Counters for the final report
    stats: dict[str, int] = {}
    report_records: list[dict[str, Any]] = []
    total_bytes = 0
    not_found = 0
    copied = 0
    skipped = 0
    duplicates_skipped = 0
    seen_file_ids: set[str] = set()

    progress = None
    if HAS_TQDM and not verbose and not dry_run:
        progress = tqdm(
            total=len(all_files),
            unit='file',
            dynamic_ncols=True,
            desc='Extracting',
        )

    def _log(message: str) -> None:
        if progress is not None:
            progress.write(message)
        else:
            print(message)

    total = len(all_files)
    try:
        for idx, (file_id, relative_path) in enumerate(all_files, 1):
            jid = extract_jid(relative_path) or 'unknown'
            contact_name = contact_map.get(jid, '')

            original_filename = Path(relative_path).name
            ext               = Path(original_filename).suffix.lower()
            info              = info_map.get(original_filename)
            ts, direction, msgtype, _size = info if info else (None, 'received', 0, None)
            dt                = apple_ts_to_datetime(ts) if ts is not None else None

            # Determine file type — GIFs saved as .mp4 by WhatsApp use ZMESSAGETYPE=15
            if msgtype in GIF_MESSAGE_TYPES and ext == '.mp4':
                ftype = 'gif'
            else:
                ftype = get_file_type(ext) or 'img'

            label = contact_name or jid
            line = f'[{idx:>6}/{total}] [{ftype:>5}] {label} — {original_filename}'
            if progress is None:
                print(line, end='')
            else:
                progress.set_postfix_str(
                    f'{label[:30]} • {total_bytes / 1_073_741_824:.2f} GB',
                    refresh=False,
                )

            # Locate the physical file in the backup
            src = backup_path / file_id[:2] / file_id
            if not src.exists():
                report_records.append(_media_record(file_id, relative_path, 'not_found'))
                if progress is None:
                    print(' [NOT FOUND]')
                else:
                    _log(f'{line} [NOT FOUND]')
                    progress.update(1)
                not_found += 1
                continue

            if file_id in seen_file_ids:
                report_records.append(_media_record(file_id, relative_path, 'duplicate'))
                if progress is None:
                    print(' [DUPLICATE]')
                else:
                    _log(f'{line} [DUPLICATE]')
                    progress.update(1)
                duplicates_skipped += 1
                continue

            dest = build_dest_path(
                output_dir,
                contact_name,
                dt,
                original_filename,
                jid,
                ftype,
                avoid_collisions=False,
            )

            if dry_run:
                report_records.append(_media_record(file_id, relative_path, 'dry_run', dest))
                if progress is None:
                    print(f'\n         -> {dest}  (dry-run)')
            elif enc_backup is None and dest.exists() and dest.stat().st_size == src.stat().st_size:
                skipped += 1
                seen_file_ids.add(file_id)
                report_records.append(_media_record(file_id, relative_path, 'skipped', dest))
                if progress is None:
                    print(' [SKIPPED]')
                else:
                    _log(f'{line} [SKIPPED]')
                    progress.update(1)
                continue
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                if enc_backup is not None:
                    # Decrypt directly to the destination path
                    enc_backup.extract_file(
                        relative_path=relative_path,
                        domain_like=WHATSAPP_DOMAIN,
                        output_filename=str(dest),
                    )
                else:
                    shutil.copy2(str(src), str(dest))
                set_rich_metadata(dest, dt, contact_name, jid, direction, ftype)
                total_bytes += dest.stat().st_size
                record = _media_record(file_id, relative_path, 'copied', dest)
                record['size'] = dest.stat().st_size
                report_records.append(record)
                if progress is None:
                    print(f'\n         -> {dest}')

            seen_file_ids.add(file_id)
            copied += 1
            stats[label] = stats.get(label, 0) + 1
            if progress is not None:
                progress.update(1)
    finally:
        if progress is not None:
            progress.close()

    # Cleanup
    chat_conn.close()
    manifest_conn.close()
    os.unlink(tmp_path)
    if tmp_manifest_path and os.path.exists(tmp_manifest_path):
        os.unlink(tmp_manifest_path)

    # Final report
    print('\n' + '=' * 60)
    print('FINAL REPORT')
    print('=' * 60)
    print(f'Processed   : {copied}')
    print(f'Skipped     : {skipped}')
    print(f'Duplicates skipped: {duplicates_skipped}')
    print(f'Not found   : {not_found}')
    if not dry_run:
        print(f'Total size  : {total_bytes / 1_073_741_824:.2f} GB')
    print()
    print(f'{"Contact/Group":<45} {"Files":>6}')
    print('-' * 53)
    for name, count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f'{name:<45} {count:>6}')
    print('=' * 60)

    if report_path:
        _write_report(report_path, report_records)

    if update_state and not dry_run and not stats_only:
        path = save_last_run(output_dir, run_started_at)
        print(f'[INFO] State updated          : {path}')
