"""
Rich metadata writing:
  - EXIF fields (JPEG via piexif)
  - macOS extended attributes / Spotlight (xattr via ctypes)
  - Filesystem timestamps (mtime/atime)
"""

import ctypes
import ctypes.util
import json
import os
import plistlib
from datetime import datetime, timezone
from pathlib import Path

try:
    import piexif
    HAS_PIEXIF = True
except ImportError:
    HAS_PIEXIF = False

try:
    from PIL import Image  # noqa: F401  (imported for future use)
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

from .utils import local_tz_offset, phone_from_jid

# macOS native libc for setxattr
_libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)


# ---------------------------------------------------------------------------
# Low-level xattr helpers
# ---------------------------------------------------------------------------

def _macos_setxattr(filepath: Path, name: str, value: bytes) -> None:
    """Writes a macOS extended attribute via native setxattr."""
    try:
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def set_rich_metadata(
    filepath: Path,
    dt: datetime | None,
    contact_name: str,
    jid: str,
    direction: str = 'received',
    ftype: str | None = None,
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
    date_exif    = dt.strftime('%Y:%m:%d %H:%M:%S') if dt else None
    date_human   = dt.strftime('%m/%d/%Y at %H:%M') if dt else 'unknown date'
    date_iso     = dt.isoformat() if dt else None
    tz_offset    = local_tz_offset(dt) if dt else ''

    title        = f'{display_name} · {dt.strftime("%Y-%m-%d %H:%M")}' if dt else display_name
    description  = f'WhatsApp · {chat_type}: {display_name} · {date_human}'
    phone        = phone_from_jid(jid)
    keywords     = ['WhatsApp', chat_type, display_name, phone, direction]
    if ftype:
        keywords.append(ftype)
    if dt:
        keywords.append(dt.strftime('%Y'))
        keywords.append(dt.strftime('%Y-%m'))

    comment_json = json.dumps({
        'source':    'WhatsApp',
        'chat_type': chat_type.lower(),
        'file_type': ftype,
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

            ifd0 = exif_dict.setdefault('0th', {})
            exif = exif_dict.setdefault('Exif', {})

            if date_exif:
                ifd0[piexif.ImageIFD.DateTime]         = date_exif.encode()
                exif[piexif.ExifIFD.DateTimeOriginal]  = date_exif.encode()
                exif[piexif.ExifIFD.DateTimeDigitized] = date_exif.encode()

            if tz_offset:
                exif[piexif.ExifIFD.OffsetTimeOriginal]  = tz_offset.encode()
                exif[piexif.ExifIFD.OffsetTimeDigitized] = tz_offset.encode()

            ifd0[piexif.ImageIFD.ImageDescription] = description.encode('utf-8')
            ifd0[piexif.ImageIFD.Artist]           = display_name.encode('utf-8')
            ifd0[piexif.ImageIFD.Copyright]        = b'WhatsApp'
            ifd0[piexif.ImageIFD.Software]         = b'WhatsApp Media Extractor'

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
