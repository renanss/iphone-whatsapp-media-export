"""
Pure utility helpers — no I/O, no external dependencies.
"""

import re
import unicodedata
from datetime import datetime, timedelta

from .constants import APPLE_EPOCH, FILE_TYPES


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


def get_file_type(ext: str) -> str | None:
    """Returns the type name for a file extension, or None if unknown/junk."""
    ext = ext.lower()
    for type_name, extensions in FILE_TYPES.items():
        if ext in extensions:
            return type_name
    return None
