"""
CLI entry point for extract_whatsapp_media.py
"""

import argparse
import getpass
import re
import sys
from datetime import datetime
from pathlib import Path

from .backup import find_backup_path
from .constants import FILE_TYPES, DEFAULT_TYPES
from .extractor import extract
from .metadata import HAS_PIEXIF
from .state import load_last_run


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Extract WhatsApp photos from a local iPhone backup.'
    )
    parser.add_argument(
        '--backup', type=Path, default=None,
        help='Path to the iPhone backup (auto-detected if omitted)'
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
        '--stats-only', action='store_true',
        help='Print aggregate backup statistics without copying or listing every file'
    )
    parser.add_argument(
        '--report', type=Path, default=None,
        metavar='PATH',
        help='Write a structured extraction or stats report to .json or .csv'
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
        '--type', nargs='+', default=None,
        metavar='TYPE',
        dest='file_types',
        choices=[*FILE_TYPES.keys(), 'all'],
        help=(
            'File types to include: img gif video audio doc all. '
            'Default: img video audio doc (gif and webp are opt-in). '
            'Docs are saved to a separate _Documents/ folder automatically. '
            'Use "all" to include gif and webp as well. '
            'Example: --type img video doc'
        )
    )
    parser.add_argument(
        '--exclude-type', nargs='+', default=None,
        metavar='TYPE',
        dest='exclude_types',
        choices=list(FILE_TYPES.keys()),
        help=(
            'File types to exclude. '
            'Example: --exclude-type gif audio'
        )
    )
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument(
        '--from', type=str, default=None,
        metavar='YYYY-MM-DD',
        dest='date_from',
        help='Extract only files on or after this date. Example: --from 2023-01-01'
    )
    date_group.add_argument(
        '--since-last-run', action='store_true',
        help='Resume from the last successful extraction recorded in the output folder'
    )
    parser.add_argument(
        '--to', type=str, default=None,
        metavar='YYYY-MM-DD',
        dest='date_to',
        help='Extract only files on or before this date. Example: --to 2023-12-31'
    )
    parser.add_argument(
        '--min-size', type=str, default=None,
        metavar='SIZE',
        help='Extract only files at least this size. Examples: 500kb, 10mb'
    )
    parser.add_argument(
        '--max-size', type=str, default=None,
        metavar='SIZE',
        help='Extract only files at most this size. Examples: 200kb, 2mb'
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--no-group', action='store_true',
        help='Exclude group chats and extract personal chats only'
    )
    group.add_argument(
        '--only-group', '--group', action='store_true',
        dest='only_group',
        help='Extract group chats only'
    )
    parser.add_argument(
        '--inspect-db', action='store_true',
        help='Print the ChatStorage.sqlite schema and exit (useful for debugging)'
    )
    parser.add_argument(
        '--password', type=str, default=None,
        metavar='PASSPHRASE',
        help=(
            'Passphrase for encrypted iPhone backups. '
            'Use "-" to be prompted interactively (password is never logged). '
            'Requires: pip3 install iphone-backup-decrypt'
        )
    )

    args = parser.parse_args()

    if args.random_sample is not None and args.random_sample < 1:
        sys.exit('[ERROR] --random must be greater than zero.')

    def _parse_date(value: str, param: str) -> datetime:
        try:
            d = datetime.strptime(value, '%Y-%m-%d')
            return d.replace(tzinfo=datetime.now().astimezone().tzinfo)
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

    date_to   = _parse_date(args.date_to,   '--to'  ).replace(
        hour=23, minute=59, second=59
    ) if args.date_to else None

    if date_from and date_to and date_from > date_to:
        sys.exit('[ERROR] --from date cannot be after --to date.')

    def _parse_size(value: str, param: str) -> int:
        match = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*([kmgt]?b?)?\s*', value, re.IGNORECASE)
        if not match:
            sys.exit(f'[ERROR] Invalid size for {param}: "{value}". Use values like 500kb or 10mb.')
        number = float(match.group(1))
        unit = (match.group(2) or 'kb').lower()
        multipliers = {
            'b': 1,
            '': 1,
            'k': 1024,
            'kb': 1024,
            'm': 1024 ** 2,
            'mb': 1024 ** 2,
            'g': 1024 ** 3,
            'gb': 1024 ** 3,
            't': 1024 ** 4,
            'tb': 1024 ** 4,
        }
        if unit not in multipliers:
            sys.exit(f'[ERROR] Invalid size unit for {param}: "{unit}". Use b, kb, mb, gb, or tb.')
        return int(number * multipliers[unit])

    min_size = _parse_size(args.min_size, '--min-size') if args.min_size else None
    max_size = _parse_size(args.max_size, '--max-size') if args.max_size else None

    if min_size is not None and max_size is not None and min_size > max_size:
        sys.exit('[ERROR] --min-size cannot be greater than --max-size.')

    group_filter = 'all'
    if args.no_group:
        group_filter = 'exclude'
    elif args.only_group:
        group_filter = 'only'

    if not args.file_types:
        file_types = set(DEFAULT_TYPES)
    elif 'all' in args.file_types:
        file_types = set(FILE_TYPES.keys())
    else:
        file_types = set(args.file_types)

    # Apply --exclude-type on top
    if args.exclude_types:
        file_types -= set(args.exclude_types)

    if not file_types:
        sys.exit('[ERROR] No file types remaining after applying --exclude-type.')

    backup_path = args.backup or find_backup_path()

    # Resolve password: "-" means prompt interactively
    password = args.password
    if password == '-':
        password = getpass.getpass('Backup passphrase: ')
        if not password:
            sys.exit('[ERROR] Empty passphrase.')

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
        file_types=file_types,
        date_from=date_from,
        date_to=date_to,
        min_size=min_size,
        max_size=max_size,
        group_filter=group_filter,
        stats_only=args.stats_only,
        report_path=args.report,
        password=password,
        update_state=args.since_last_run,
    )


if __name__ == '__main__':
    main()
