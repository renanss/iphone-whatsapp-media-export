"""
Backup discovery — locates the iPhone backup directory and key files within it.
"""

import os
import sqlite3
import sys
from pathlib import Path

from .constants import WHATSAPP_DOMAIN


def _mobilesync_candidates() -> list[Path]:
    """
    Returns candidate MobileSync/Backup base directories for the current platform.
    Ordered by likelihood so the first hit wins.
    """
    candidates: list[Path] = []

    if sys.platform == 'darwin':
        # macOS: ~/Library/Application Support/MobileSync/Backup
        candidates.append(
            Path.home() / 'Library' / 'Application Support' / 'MobileSync' / 'Backup'
        )

    elif sys.platform == 'win32':
        # Windows: %APPDATA%\Apple Computer\MobileSync\Backup
        appdata = os.environ.get('APPDATA', '')
        if appdata:
            candidates.append(Path(appdata) / 'Apple Computer' / 'MobileSync' / 'Backup')
        # Newer iTunes from Microsoft Store uses a different path
        local_appdata = os.environ.get('LOCALAPPDATA', '')
        if local_appdata:
            candidates.append(
                Path(local_appdata) / 'Apple' / 'MobileSync' / 'Backup'
            )

    else:
        # Linux (iTunes via Wine or libimobiledevice)
        candidates.append(Path.home() / '.wine' / 'drive_c' / 'users' /
                          os.environ.get('USER', 'user') /
                          'Application Data' / 'Apple Computer' / 'MobileSync' / 'Backup')
        candidates.append(Path.home() / 'iTunes' / 'Backup')

    return candidates


def find_backup_path() -> Path:
    """
    Locates the iPhone backup directory.
    Search order:
      1. Project root directory (backup moved locally for convenience)
      2. Platform-appropriate MobileSync/Backup location
    """
    # 1. Project root (two levels up from this file)
    project_dir = Path(__file__).parent.parent
    local = [d for d in project_dir.iterdir() if d.is_dir() and (d / 'Manifest.db').exists()]
    if local:
        local.sort(key=lambda d: (d / 'Manifest.db').stat().st_mtime, reverse=True)
        return local[0]

    # 2. Platform-specific MobileSync location
    for base in _mobilesync_candidates():
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
