"""
Backup discovery — locates the iPhone backup directory and key files within it.
"""

import sqlite3
import sys
from pathlib import Path

from .constants import WHATSAPP_DOMAIN


def find_backup_path() -> Path:
    """
    Locates the iPhone backup directory. Checks the package's parent folder first
    (in case the backup was moved locally), then falls back to the default
    MobileSync location used by Finder.
    """
    # 1. Same directory as the project root (two levels up from this file)
    project_dir = Path(__file__).parent.parent
    local = [d for d in project_dir.iterdir() if d.is_dir() and (d / 'Manifest.db').exists()]
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
