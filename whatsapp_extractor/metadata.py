"""
Rich metadata writing:
  - EXIF fields (JPEG via piexif)                          — all platforms
  - macOS extended attributes / Spotlight (xattr/ctypes)   — macOS only
  - XMP sidecar file (.xmp)                                — Windows / Linux
  - Filesystem timestamps (mtime/atime)                    — all platforms
"""

import json
import os
import sys
import xml.etree.ElementTree as ET
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

# ---------------------------------------------------------------------------
# macOS-only: load libc for setxattr (skipped on Windows / Linux)
# ---------------------------------------------------------------------------

_IS_MACOS = sys.platform == 'darwin'

if _IS_MACOS:
    import ctypes
    import ctypes.util
    import plistlib
    _libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
else:
    _libc = None


# ---------------------------------------------------------------------------
# macOS xattr helpers
# ---------------------------------------------------------------------------

def _macos_setxattr(filepath: Path, name: str, value: bytes) -> None:
    """Writes a macOS extended attribute via native setxattr."""
    if not _libc:
        return
    try:
        _libc.setxattr(
            str(filepath).encode('utf-8'),
            name.encode('utf-8'),
            value,
            len(value),
            0,   # position
            0,   # options
        )
    except Exception:
        pass


def _set_xattr_str(filepath: Path, key: str, value: str) -> None:
    _macos_setxattr(filepath, key, plistlib.dumps(value, fmt=plistlib.FMT_BINARY))


def _set_xattr_list(filepath: Path, key: str, value: list) -> None:
    _macos_setxattr(filepath, key, plistlib.dumps(value, fmt=plistlib.FMT_BINARY))


def _set_xattr_date(filepath: Path, key: str, dt: datetime) -> None:
    """plistlib requires a naive UTC datetime."""
    naive = dt.astimezone(timezone.utc).replace(tzinfo=None)
    _macos_setxattr(filepath, key, plistlib.dumps(naive, fmt=plistlib.FMT_BINARY))


def _write_macos_xattrs(
    filepath: Path,
    title: str,
    description: str,
    comment_json: str,
    display_name: str,
    keywords: list[str],
    dt: datetime | None,
) -> None:
    """Writes all Spotlight/Finder extended attributes (macOS only)."""
    _set_xattr_str (filepath, 'com.apple.metadata:kMDItemTitle',       title)
    _set_xattr_str (filepath, 'com.apple.metadata:kMDItemDescription', description)
    _set_xattr_str (filepath, 'com.apple.metadata:kMDItemComment',     comment_json)
    _set_xattr_list(filepath, 'com.apple.metadata:kMDItemAuthors',     [display_name])
    _set_xattr_list(filepath, 'com.apple.metadata:kMDItemKeywords',    keywords)
    if dt:
        _set_xattr_date(filepath, 'com.apple.metadata:kMDItemContentCreationDate', dt)


# ---------------------------------------------------------------------------
# Windows / Linux: XMP sidecar
# ---------------------------------------------------------------------------

_XNS = {
    'x':   'adobe:ns:meta/',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'dc':  'http://purl.org/dc/elements/1.1/',
    'xmp': 'http://ns.adobe.com/xap/1.0/',
}

for _prefix, _uri in _XNS.items():
    ET.register_namespace(_prefix, _uri)


def _xmp_text(parent: ET.Element, ns: str, tag: str, text: str) -> None:
    el = ET.SubElement(parent, f'{{{_XNS[ns]}}}{tag}')
    el.text = text


def _xmp_alt(parent: ET.Element, ns: str, tag: str, text: str) -> None:
    """<ns:tag><rdf:Alt><rdf:li xml:lang="x-default">text</rdf:li></rdf:Alt></ns:tag>"""
    el  = ET.SubElement(parent, f'{{{_XNS[ns]}}}{tag}')
    alt = ET.SubElement(el,  f'{{{_XNS["rdf"]}}}Alt')
    li  = ET.SubElement(alt, f'{{{_XNS["rdf"]}}}li')
    li.set('{http://www.w3.org/XML/1998/namespace}lang', 'x-default')
    li.text = text


def _xmp_bag(parent: ET.Element, ns: str, tag: str, items: list[str]) -> None:
    """<ns:tag><rdf:Bag><rdf:li>…</rdf:li></rdf:Bag></ns:tag>"""
    el  = ET.SubElement(parent, f'{{{_XNS[ns]}}}{tag}')
    bag = ET.SubElement(el,  f'{{{_XNS["rdf"]}}}Bag')
    for item in items:
        li = ET.SubElement(bag, f'{{{_XNS["rdf"]}}}li')
        li.text = item


def _xmp_seq(parent: ET.Element, ns: str, tag: str, items: list[str]) -> None:
    """<ns:tag><rdf:Seq><rdf:li>…</rdf:li></rdf:Seq></ns:tag>"""
    el  = ET.SubElement(parent, f'{{{_XNS[ns]}}}{tag}')
    seq = ET.SubElement(el,  f'{{{_XNS["rdf"]}}}Seq')
    for item in items:
        li = ET.SubElement(seq, f'{{{_XNS["rdf"]}}}li')
        li.text = item


def _write_xmp_sidecar(
    filepath: Path,
    title: str,
    description: str,
    comment_json: str,
    display_name: str,
    keywords: list[str],
    dt: datetime | None,
) -> None:
    """
    Writes a <filename>.xmp sidecar alongside filepath.
    Readable by Lightroom, digiKam, and most DAM tools on Windows / Linux.
    """
    sidecar_path = filepath.with_suffix(filepath.suffix + '.xmp')

    xmpmeta = ET.Element(f'{{{_XNS["x"]}}}xmpmeta')
    xmpmeta.set(f'{{{_XNS["x"]}}}xmptk', 'WhatsApp Media Extractor')

    rdf  = ET.SubElement(xmpmeta, f'{{{_XNS["rdf"]}}}RDF')
    desc = ET.SubElement(rdf, f'{{{_XNS["rdf"]}}}Description')
    desc.set(f'{{{_XNS["rdf"]}}}about', '')

    # Dublin Core
    _xmp_alt(desc, 'dc', 'title',       title)
    _xmp_alt(desc, 'dc', 'description', description)
    _xmp_seq(desc, 'dc', 'creator',     [display_name])
    _xmp_bag(desc, 'dc', 'subject',     keywords)

    # XMP basic
    if dt:
        iso = dt.strftime('%Y-%m-%dT%H:%M:%S')
        _xmp_text(desc, 'xmp', 'CreateDate',   iso)
        _xmp_text(desc, 'xmp', 'MetadataDate', iso)
    _xmp_text(desc, 'xmp', 'CreatorTool', 'WhatsApp Media Extractor')
    _xmp_text(desc, 'xmp', 'UserComment', comment_json)

    tree = ET.ElementTree(xmpmeta)
    ET.indent(tree, space='  ')  # Python 3.9+

    try:
        with open(sidecar_path, 'wb') as f:
            f.write(b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>\n')
            tree.write(f, encoding='utf-8', xml_declaration=False)
            f.write(b'\n<?xpacket end="w"?>\n')
    except Exception:
        pass  # metadata is non-critical


# ---------------------------------------------------------------------------
# Public API  (signature unchanged)
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
      - EXIF: dates, description, artist, software, JSON comment (JPEG only, all platforms)
      - macOS Spotlight xattr: title, description, authors, keywords, creation date
      - XMP sidecar (.xmp): same fields for Windows / Linux DAM tools
      - Filesystem: mtime/atime set to the original message date (all platforms)
    """
    is_group     = '@g.us' in jid
    chat_type    = 'Group' if is_group else 'Contact'
    display_name = contact_name or jid
    ext          = filepath.suffix.lower()

    date_exif  = dt.strftime('%Y:%m:%d %H:%M:%S') if dt else None
    date_human = dt.strftime('%m/%d/%Y at %H:%M') if dt else 'unknown date'
    date_iso   = dt.isoformat() if dt else None
    tz_offset  = local_tz_offset(dt) if dt else ''

    title       = f'{display_name} · {dt.strftime("%Y-%m-%d %H:%M")}' if dt else display_name
    description = f'WhatsApp · {chat_type}: {display_name} · {date_human}'
    phone       = phone_from_jid(jid)
    keywords    = ['WhatsApp', chat_type, display_name, phone, direction]
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
    # 1. EXIF — JPEG only, all platforms
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
    # 2. Platform-specific rich metadata
    # ------------------------------------------------------------------
    if _IS_MACOS:
        _write_macos_xattrs(
            filepath, title, description, comment_json, display_name, keywords, dt
        )
    else:
        _write_xmp_sidecar(
            filepath, title, description, comment_json, display_name, keywords, dt
        )

    # ------------------------------------------------------------------
    # 3. Filesystem timestamps — all platforms
    # ------------------------------------------------------------------
    if dt:
        ts = dt.timestamp()
        os.utime(str(filepath), (ts, ts))
