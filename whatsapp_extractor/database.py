"""
Database helpers — reads Manifest.db and ChatStorage.sqlite.
"""

import sqlite3
from pathlib import Path

from .constants import WHATSAPP_DOMAIN, FILE_TYPES


# ---------------------------------------------------------------------------
# Schema introspection (debugging)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Contact map
# ---------------------------------------------------------------------------

def load_contact_map(chat_conn: sqlite3.Connection) -> dict[str, str]:
    """Returns {jid: display_name} from ZWACHATSESSION."""
    rows = chat_conn.execute(
        "SELECT ZCONTACTJID, ZPARTNERNAME FROM ZWACHATSESSION "
        "WHERE ZCONTACTJID IS NOT NULL"
    ).fetchall()
    return {jid: (name or '').strip() for jid, name in rows}


# ---------------------------------------------------------------------------
# Message info
# ---------------------------------------------------------------------------

def load_message_info(chat_conn: sqlite3.Connection) -> dict[str, tuple[float, str, int]]:
    """
    Returns {filename: (apple_timestamp, direction, message_type)} where:
      - direction    : 'sent' or 'received'
      - message_type : ZMESSAGETYPE value (1=image, 3=video, 15=gif, 7=doc, etc.)

    Strategy 1: JOIN ZWAMEDIAITEM -> ZWAMESSAGE (accurate date + direction + type).
    Strategy 2: ZMEDIAURLDATE directly from ZWAMEDIAITEM as a fallback.
    """
    info_map: dict[str, tuple[float, str, int]] = {}

    # Strategy 1: JOIN for date, direction and message type
    try:
        rows = chat_conn.execute("""
            SELECT mi.ZMEDIALOCALPATH, m.ZMESSAGEDATE, m.ZISFROMME, m.ZMESSAGETYPE
            FROM ZWAMEDIAITEM mi
            JOIN ZWAMESSAGE m ON mi.ZMESSAGE = m.Z_PK
            WHERE mi.ZMEDIALOCALPATH IS NOT NULL
              AND m.ZMESSAGEDATE IS NOT NULL
        """).fetchall()
        for path, ts, fromme, msgtype in rows:
            fname = Path(path).name
            if fname:
                info_map[fname] = (ts, 'sent' if fromme else 'received', msgtype or 0)
    except sqlite3.OperationalError:
        pass

    # Strategy 2: direct ZMEDIAURLDATE (no JOIN, no direction/type info)
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
                info_map[fname] = (ts, 'received', 0)
    except sqlite3.OperationalError:
        pass

    return info_map


# ---------------------------------------------------------------------------
# Media file listing
# ---------------------------------------------------------------------------

def query_media_files(
    manifest_conn: sqlite3.Connection,
    single_file: str | None = None,
    file_types: set[str] | None = None,
) -> list[tuple[str, str]]:
    """
    Returns a list of (fileID, relativePath) for WhatsApp media in the backup.

    file_types: set of type names to include (e.g. {'img', 'gif', 'video'}).
                Defaults to all known types if None.
    """
    active_types = file_types or set(FILE_TYPES.keys())
    active_exts  = frozenset().union(*(FILE_TYPES[t] for t in active_types if t in FILE_TYPES))

    sql = """
        SELECT fileID, relativePath FROM Files
        WHERE domain = ?
        AND relativePath LIKE 'Message/Media/%'
        AND relativePath NOT LIKE '%.thumb%'
        AND relativePath NOT LIKE '%.mmsthumb%'
        AND relativePath NOT LIKE '%.favicon%'
    """
    params: list = [WHATSAPP_DOMAIN]

    if single_file:
        sql += " AND fileID LIKE ?"
        params.append(f'{single_file}%')

    rows = manifest_conn.execute(sql, params).fetchall()
    return [
        (fid, rpath) for fid, rpath in rows
        if Path(rpath).suffix.lower() in active_exts
    ]
