"""
Shared constants used across all modules.
"""

from datetime import datetime, timezone

# Apple Core Data epoch starts at 2001-01-01 00:00:00 UTC (not Unix epoch)
APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)

WHATSAPP_DOMAIN = "AppDomainGroup-group.net.whatsapp.WhatsApp.shared"

# Documents go to a dedicated folder so they don't pollute iCloud Photos imports
DOCS_FOLDER = '_Documents'

# ZMESSAGETYPE values that indicate GIF (WhatsApp stores GIFs as .mp4)
GIF_MESSAGE_TYPES: frozenset[int] = frozenset({15})

# ---------------------------------------------------------------------------
# File type definitions
# ---------------------------------------------------------------------------

FILE_TYPES: dict[str, frozenset[str]] = {
    'img': frozenset({
        '.jpg', '.jpeg', '.png', '.heic', '.tiff', '.bmp',
    }),
    'webp': frozenset({
        '.webp',  # mostly WhatsApp stickers
    }),
    'gif': frozenset({
        '.gif',
    }),
    'video': frozenset({
        '.mp4', '.mov', '.avi', '.mkv', '.3gp', '.m4v', '.wmv',
    }),
    'audio': frozenset({
        '.opus', '.mp3', '.m4a', '.aac', '.ogg', '.wav', '.amr', '.flac',
    }),
    'doc': frozenset({
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.xlsm', '.xltx', '.xltm',
        '.ppt', '.pptx', '.txt', '.csv', '.zip', '.rar', '.bz2', '.7z',
        '.html', '.json', '.xml', '.yml', '.yaml',
        '.odt', '.ods', '.odp', '.pages', '.numbers', '.key',
        '.epub', '.msg', '.psd', '.aep', '.sql',
    }),
}

# All known extensions across every type
ALL_KNOWN_EXTENSIONS: frozenset[str] = frozenset().union(*FILE_TYPES.values())

# Default types: img, video, audio, doc — gif and webp are opt-in
DEFAULT_TYPES: set[str] = {'img', 'video', 'audio', 'doc'}
