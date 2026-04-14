#!/usr/bin/env python3
"""
WhatsApp Media Extractor
Extrai fotos do backup local do iPhone, organizadas por contato/grupo e data.

Uso:
  python3 extract_whatsapp_media.py [opções]

Exemplos:
  python3 extract_whatsapp_media.py                          # extração completa
  python3 extract_whatsapp_media.py --dry-run                # simula sem copiar nada
  python3 extract_whatsapp_media.py --contact "João Silva"   # apenas um contato
  python3 extract_whatsapp_media.py --file abc123def456      # apenas um fileID
  python3 extract_whatsapp_media.py --random 10              # 10 arquivos aleatórios
  python3 extract_whatsapp_media.py --random 5 --contact "João"  # 5 aleatórios de um contato
"""

import argparse
import ctypes
import ctypes.util
import json
import os
import plistlib
import random
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone, timedelta
import unicodedata
from pathlib import Path

try:
    import piexif
    HAS_PIEXIF = True
except ImportError:
    HAS_PIEXIF = False

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

# macOS libc para setxattr nativo
_libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)

# Apple epoch: 2001-01-01 00:00:00 UTC
APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)
WHATSAPP_DOMAIN = "AppDomainGroup-group.net.whatsapp.WhatsApp.shared"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def apple_ts_to_datetime(ts: float) -> datetime:
    """Converte timestamp Apple (UTC) para datetime no fuso local da máquina."""
    utc = APPLE_EPOCH + timedelta(seconds=ts)
    return utc.astimezone()  # converte para timezone local


def local_tz_offset(dt: datetime) -> str:
    """Retorna o offset do fuso local no formato ±HH:MM (ex: -03:00)."""
    offset = dt.utcoffset()
    if offset is None:
        return ''
    total = int(offset.total_seconds())
    sign = '+' if total >= 0 else '-'
    h, m = divmod(abs(total) // 60, 60)
    return f'{sign}{h:02d}:{m:02d}'


def safe_folder_name(name: str) -> str:
    """Remove caracteres inválidos e emojis para nomes de pasta."""
    # Remove emojis e caracteres não-ASCII problemáticos
    name = ''.join(
        c for c in name
        if unicodedata.category(c) not in ('So', 'Cs')  # So=símbolo, Cs=surrogate
        and ord(c) < 0x10000
    )
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    return name.strip().strip('.') or '_Sem_Nome'


def safe_filename_part(name: str, max_len: int = 40) -> str:
    """Versão do nome para usar dentro do filename (underscores, sem emojis)."""
    name = safe_folder_name(name)
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    return name[:max_len]


def extract_jid(relative_path: str) -> str | None:
    """
    Extrai o JID do contato/grupo a partir do relativePath.
    Ex: Message/Media/5511999910208@s.whatsapp.net/a/3/uuid.jpg  → 5511999910208@s.whatsapp.net
        Message/Media/5511964049807-1595615948@g.us/2/3/uuid.jpg → 5511964049807-1595615948@g.us
    """
    match = re.match(r'^Message/Media/([^/]+)/', relative_path)
    if match:
        return match.group(1)
    return None


def phone_from_jid(jid: str) -> str:
    """
    Extrai o número de telefone do JID.
    5511999910208@s.whatsapp.net        → 5511999910208
    5511964049807-1595615948@g.us       → 5511964049807 (criador do grupo)
    """
    number = jid.split('@')[0]
    number = number.split('-')[0]  # grupos: pega só o número do criador
    return number


def _macos_setxattr(filepath: Path, name: str, value: bytes) -> None:
    """Escreve um extended attribute no macOS via setxattr nativo."""
    try:
        # setxattr(path, name, value, size, position, options)
        ret = _libc.setxattr(
            str(filepath).encode('utf-8'),
            name.encode('utf-8'),
            value,
            len(value),
            0,   # position
            0,   # options
        )
        if ret != 0:
            pass  # silencia; xattr não é crítico
    except Exception:
        pass


def _set_xattr_str(filepath: Path, key: str, value: str) -> None:
    """Escreve xattr macOS com valor string (bplist)."""
    _macos_setxattr(filepath, key, plistlib.dumps(value, fmt=plistlib.FMT_BINARY))


def _set_xattr_list(filepath: Path, key: str, value: list) -> None:
    """Escreve xattr macOS com valor lista (bplist)."""
    _macos_setxattr(filepath, key, plistlib.dumps(value, fmt=plistlib.FMT_BINARY))


def _set_xattr_date(filepath: Path, key: str, dt: datetime) -> None:
    """Escreve xattr macOS com valor datetime (bplist). plistlib exige naive UTC."""
    naive = dt.astimezone(timezone.utc).replace(tzinfo=None)
    _macos_setxattr(filepath, key, plistlib.dumps(naive, fmt=plistlib.FMT_BINARY))


def set_rich_metadata(
    filepath: Path,
    dt: datetime | None,
    contact_name: str,
    jid: str,
    direcao: str = 'recebida',
) -> None:
    """
    Define metadados ricos no arquivo:
      - EXIF: datas, descrição, autor, software, comentário JSON  (JPEG/PNG)
      - macOS Spotlight (xattr): título, descrição, autores, palavras-chave, data de criação
      - Filesystem: mtime/atime ajustados para a data original da mensagem
    """
    is_group     = '@g.us' in jid
    chat_type    = 'Grupo' if is_group else 'Contato'
    display_name = contact_name or jid
    ext          = filepath.suffix.lower()

    # dt já está em horário local (convertido em apple_ts_to_datetime)
    date_exif    = dt.strftime('%Y:%m:%d %H:%M:%S') if dt else None  # EXIF = local time
    date_human   = dt.strftime('%d/%m/%Y às %H:%M') if dt else 'data desconhecida'
    date_iso     = dt.isoformat() if dt else None
    tz_offset    = local_tz_offset(dt) if dt else ''                  # ex: -03:00

    title        = f'{display_name} · {dt.strftime("%Y-%m-%d %H:%M")}' if dt else display_name
    description  = f'WhatsApp · {chat_type}: {display_name} · {date_human}'
    phone        = phone_from_jid(jid)
    keywords     = ['WhatsApp', chat_type, display_name, phone, direcao]
    if dt:
        keywords.append(dt.strftime('%Y'))
        keywords.append(dt.strftime('%Y-%m'))

    comment_json = json.dumps({
        'source':   'WhatsApp',
        'type':     chat_type.lower(),
        'contact':  display_name,
        'phone':    phone,
        'jid':      jid,
        'date':     date_iso,
        'direcao':  direcao,
    }, ensure_ascii=False)

    # ------------------------------------------------------------------
    # 1. EXIF — apenas JPEG (piexif não suporta PNG)
    # ------------------------------------------------------------------
    if HAS_PIEXIF and ext in ('.jpg', '.jpeg'):
        try:
            try:
                exif_dict = piexif.load(str(filepath))
            except Exception:
                exif_dict = {'0th': {}, 'Exif': {}, 'GPS': {}, '1st': {}}

            ifd0  = exif_dict.setdefault('0th', {})
            exif  = exif_dict.setdefault('Exif', {})

            # Datas em horário local (padrão EXIF)
            if date_exif:
                ifd0[piexif.ImageIFD.DateTime]          = date_exif.encode()
                exif[piexif.ExifIFD.DateTimeOriginal]   = date_exif.encode()
                exif[piexif.ExifIFD.DateTimeDigitized]  = date_exif.encode()
            # Offset de fuso horário (EXIF 2.31+)
            if tz_offset:
                exif[piexif.ExifIFD.OffsetTimeOriginal]  = tz_offset.encode()
                exif[piexif.ExifIFD.OffsetTimeDigitized] = tz_offset.encode()

            # Descrição / título
            ifd0[piexif.ImageIFD.ImageDescription] = description.encode('utf-8')
            ifd0[piexif.ImageIFD.Artist]           = display_name.encode('utf-8')
            ifd0[piexif.ImageIFD.Copyright]        = 'WhatsApp'.encode()
            ifd0[piexif.ImageIFD.Software]         = 'WhatsApp Media Extractor'.encode()

            # UserComment: prefixo ASCII obrigatório pelo padrão EXIF
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
    # 3. Timestamps do filesystem (mtime/atime → data original)
    # ------------------------------------------------------------------
    if dt:
        ts = dt.timestamp()
        os.utime(str(filepath), (ts, ts))


# ---------------------------------------------------------------------------
# Localização do backup
# ---------------------------------------------------------------------------

def find_backup_path() -> Path:
    """
    Detecta o backup do iPhone. Procura primeiro na pasta do projeto
    (backup movido localmente), depois no local padrão do Finder.
    """
    # 1. Pasta do próprio script (backup movido para o projeto)
    script_dir = Path(__file__).parent
    local = [d for d in script_dir.iterdir() if d.is_dir() and (d / 'Manifest.db').exists()]
    if local:
        local.sort(key=lambda d: (d / 'Manifest.db').stat().st_mtime, reverse=True)
        return local[0]

    # 2. Local padrão do MobileSync
    base = Path.home() / 'Library' / 'Application Support' / 'MobileSync' / 'Backup'
    if base.exists():
        backups = [d for d in base.iterdir() if d.is_dir() and (d / 'Manifest.db').exists()]
        if backups:
            backups.sort(key=lambda d: (d / 'Manifest.db').stat().st_mtime, reverse=True)
            return backups[0]

    sys.exit('[ERRO] Nenhum backup encontrado. Use --backup para especificar o caminho.')


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------

def find_chatstorage(manifest_conn: sqlite3.Connection, backup_path: Path) -> Path:
    """Localiza o ChatStorage.sqlite dentro do backup via Manifest.db."""
    row = manifest_conn.execute(
        "SELECT fileID FROM Files WHERE relativePath LIKE '%ChatStorage.sqlite' "
        "AND domain = ? LIMIT 1",
        (WHATSAPP_DOMAIN,)
    ).fetchone()

    if not row:
        sys.exit('[ERRO] ChatStorage.sqlite não encontrado no Manifest.db.')

    file_id = row[0]
    src = backup_path / file_id[:2] / file_id
    if not src.exists():
        sys.exit(f'[ERRO] Arquivo físico do ChatStorage não encontrado: {src}')

    return src


def load_contact_map(chat_conn: sqlite3.Connection) -> dict[str, str]:
    """Retorna {jid: nome_legível} a partir do ZWACHATSESSION."""
    rows = chat_conn.execute(
        "SELECT ZCONTACTJID, ZPARTNERNAME FROM ZWACHATSESSION "
        "WHERE ZCONTACTJID IS NOT NULL"
    ).fetchall()
    return {jid: (name or '').strip() for jid, name in rows}


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """Retorna lista de colunas de uma tabela."""
    try:
        return [r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()]
    except Exception:
        return []


def _tables(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]


def inspect_db(chat_conn: sqlite3.Connection) -> None:
    """Imprime o esquema relevante do ChatStorage.sqlite para diagnóstico."""
    tables = _tables(chat_conn)
    interesting = [t for t in tables if 'WA' in t.upper() or 'CHAT' in t.upper() or 'MESSAGE' in t.upper()]
    print('\n[INSPECT] Tabelas encontradas no ChatStorage.sqlite:')
    for t in interesting:
        cols = _table_columns(chat_conn, t)
        print(f'  {t}: {cols}')

    # Mostra 2 linhas de ZWAMESSAGE para ver como ZMEDIALOCALPATH está preenchido
    for table in ['ZWAMESSAGE', 'ZWAMEDIAITEM']:
        if table not in tables:
            continue
        cols = _table_columns(chat_conn, table)
        date_cols = [c for c in cols if any(k in c.upper() for k in ('DATE', 'TIME', 'STAMP'))]
        path_cols = [c for c in cols if any(k in c.upper() for k in ('PATH', 'URL', 'LOCAL', 'FILE'))]
        print(f'\n[INSPECT] {table} — colunas de data: {date_cols} | de path: {path_cols}')
        if date_cols and path_cols:
            sample = chat_conn.execute(
                f'SELECT {path_cols[0]}, {date_cols[0]} FROM {table} '
                f'WHERE {path_cols[0]} IS NOT NULL AND {date_cols[0]} IS NOT NULL LIMIT 3'
            ).fetchall()
            for row in sample:
                print(f'  path={row[0]}  ts={row[1]}')
    print()


def load_message_info(chat_conn: sqlite3.Connection) -> dict[str, tuple[float, str]]:
    """
    Retorna {filename: (apple_timestamp, direcao)} onde direcao é 'enviada' ou 'recebida'.
    """
    info_map: dict[str, tuple[float, str]] = {}

    # Estratégia 1: JOIN ZWAMEDIAITEM → ZWAMESSAGE
    try:
        rows = chat_conn.execute("""
            SELECT mi.ZMEDIALOCALPATH, m.ZMESSAGEDATE, m.ZISFROMME
            FROM ZWAMEDIAITEM mi
            JOIN ZWAMESSAGE m ON mi.ZMESSAGE = m.Z_PK
            WHERE mi.ZMEDIALOCALPATH IS NOT NULL
              AND m.ZMESSAGEDATE IS NOT NULL
        """).fetchall()
        for path, ts, fromme in rows:
            fname = Path(path).name
            if fname:
                info_map[fname] = (ts, 'enviada' if fromme else 'recebida')
    except sqlite3.OperationalError:
        pass

    # Estratégia 2: ZMEDIAURLDATE direto (fallback, sem ZISFROMME)
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
                info_map[fname] = (ts, 'recebida')
    except sqlite3.OperationalError:
        pass

    return info_map


def query_media_files(
    manifest_conn: sqlite3.Connection,
    single_file: str | None = None
) -> list[tuple[str, str]]:
    """
    Retorna lista de (fileID, relativePath) para imagens do WhatsApp.
    Se single_file for fornecido, filtra apenas esse fileID.
    """
    base_sql = """
        SELECT fileID, relativePath FROM Files
        WHERE domain = ?
        AND relativePath LIKE 'Message/Media/%'
        AND relativePath NOT LIKE '%.thumb%'
        AND (
            relativePath LIKE '%.jpg'
            OR relativePath LIKE '%.jpeg'
            OR relativePath LIKE '%.png'
        )
    """
    params: list = [WHATSAPP_DOMAIN]

    if single_file:
        base_sql += " AND fileID LIKE ?"
        params.append(f'{single_file}%')

    return manifest_conn.execute(base_sql, params).fetchall()


# ---------------------------------------------------------------------------
# Extração
# ---------------------------------------------------------------------------

def build_dest_path(
    output_dir: Path,
    contact_name: str,
    dt: datetime | None,
    original_filename: str,
    jid: str,
) -> Path:
    """Monta o caminho de destino do arquivo."""
    if contact_name:
        folder = safe_folder_name(contact_name)
    else:
        folder = f'_Desconhecido/{safe_folder_name(jid)}'

    name_part  = safe_filename_part(contact_name or jid)
    phone_part = phone_from_jid(jid)
    ext        = Path(original_filename).suffix.lower()

    if dt:
        month_folder = dt.strftime('%Y-%m')
        # Ex: Lucila_Calaca_5511999910208_2025-12-13_17-39-44.jpg
        filename = f'{name_part}_{phone_part}_{dt.strftime("%Y-%m-%d_%H-%M-%S")}{ext}'
    else:
        month_folder = '_sem_data'
        filename = f'{name_part}_{phone_part}_{original_filename}'

    dest = output_dir / folder / month_folder / filename

    # Evita colisão de nomes
    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
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
    single_file: str | None = None,
    random_sample: int | None = None,
    inspect: bool = False,
) -> None:
    manifest_db = backup_path / 'Manifest.db'
    if not manifest_db.exists():
        sys.exit(f'[ERRO] Manifest.db não encontrado em: {backup_path}')

    print(f'[INFO] Backup: {backup_path}')
    print(f'[INFO] Destino: {output_dir}')
    if dry_run:
        print('[INFO] Modo DRY-RUN — nenhum arquivo será copiado.\n')

    manifest_conn = sqlite3.connect(str(manifest_db))

    # Copia ChatStorage para tmp (evita lock no backup)
    chatstorage_src = find_chatstorage(manifest_conn, backup_path)
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
        tmp_path = tmp.name
    shutil.copy2(str(chatstorage_src), tmp_path)

    chat_conn = sqlite3.connect(tmp_path)

    contact_map = load_contact_map(chat_conn)

    if inspect:
        inspect_db(chat_conn)

    info_map = load_message_info(chat_conn)

    print(f'[INFO] Contatos/grupos carregados : {len(contact_map)}')
    print(f'[INFO] Mídias mapeadas            : {len(info_map)}')

    all_files = query_media_files(manifest_conn, single_file)
    print(f'[INFO] Arquivos de mídia encontrados: {len(all_files)}')

    # Filtra por contato se solicitado
    if filter_contact:
        filter_lower = filter_contact.lower()
        # Descobre quais JIDs correspondem ao nome
        matching_jids = {
            jid for jid, name in contact_map.items()
            if filter_lower in name.lower()
        }
        if not matching_jids:
            print(f'[AVISO] Nenhum contato encontrado com nome contendo "{filter_contact}".')
            print(f'        Contatos disponíveis: {sorted(contact_map.values())[:20]}')
        all_files = [
            (fid, rpath) for fid, rpath in all_files
            if extract_jid(rpath) in matching_jids
        ]
        print(f'[INFO] Arquivos após filtro de contato: {len(all_files)}')

    if random_sample is not None:
        n = min(random_sample, len(all_files))
        all_files = random.sample(all_files, n)
        print(f'[INFO] Amostra aleatória: {n} arquivo(s) selecionado(s)')

    print()

    # Contadores para o relatório
    stats: dict[str, int] = {}  # {nome_contato: count}
    total_bytes = 0
    not_found = 0
    copied = 0

    total = len(all_files)
    for idx, (file_id, relative_path) in enumerate(all_files, 1):
        jid = extract_jid(relative_path) or 'desconhecido'
        contact_name = contact_map.get(jid, '')

        original_filename = Path(relative_path).name
        info = info_map.get(original_filename)
        ts, direcao = info if info else (None, 'recebida')
        dt = apple_ts_to_datetime(ts) if ts is not None else None

        label = contact_name or jid
        print(f'[{idx:>6}/{total}] {label} — {original_filename}', end='')

        # Arquivo físico no backup
        src = backup_path / file_id[:2] / file_id
        if not src.exists():
            print(' [NÃO ENCONTRADO]')
            not_found += 1
            continue

        dest = build_dest_path(output_dir, contact_name, dt, original_filename, jid)

        if dry_run:
            print(f'\n         → {dest}  (dry-run)')
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dest))
            set_rich_metadata(dest, dt, contact_name, jid, direcao)
            total_bytes += dest.stat().st_size
            print(f'\n         → {dest}')

        copied += 1
        stats[label] = stats.get(label, 0) + 1

    # Limpeza
    chat_conn.close()
    manifest_conn.close()
    os.unlink(tmp_path)

    # Relatório final
    print('\n' + '=' * 60)
    print('RELATÓRIO FINAL')
    print('=' * 60)
    print(f'Total processado : {copied}')
    print(f'Não encontrados  : {not_found}')
    if not dry_run:
        print(f'Espaço total     : {total_bytes / 1_073_741_824:.2f} GB')
    print()
    print(f'{"Contato/Grupo":<45} {"Fotos":>6}')
    print('-' * 53)
    for name, count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f'{name:<45} {count:>6}')
    print('=' * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Extrai fotos do WhatsApp de um backup local do iPhone.'
    )
    parser.add_argument(
        '--backup', type=Path, default=None,
        help='Path do backup (detecta o mais recente automaticamente se omitido)'
    )
    parser.add_argument(
        '--output', type=Path, default=Path(__file__).parent / 'WhatsApp_Media_Export',
        help='Pasta de destino (padrão: ./WhatsApp_Media_Export na pasta do script)'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Simula a extração sem copiar nenhum arquivo'
    )
    parser.add_argument(
        '--contact', type=str, default=None,
        metavar='NOME',
        help='Extrai apenas arquivos do contato/grupo cujo nome contenha NOME (case-insensitive)'
    )
    parser.add_argument(
        '--file', type=str, default=None,
        metavar='FILE_ID',
        help='Extrai apenas o arquivo com esse fileID (pode ser prefixo do SHA1)'
    )
    parser.add_argument(
        '--random', type=int, default=None,
        metavar='N',
        dest='random_sample',
        help='Extrai N arquivos escolhidos aleatoriamente (combinável com --contact)'
    )
    parser.add_argument(
        '--inspect-db', action='store_true',
        help='Imprime o esquema do ChatStorage.sqlite e sai (útil para diagnóstico)'
    )

    args = parser.parse_args()

    if args.random_sample is not None and args.random_sample < 1:
        sys.exit('[ERRO] --random deve ser um número maior que zero.')

    backup_path = args.backup or find_backup_path()

    if not HAS_PIEXIF:
        print('[AVISO] piexif não instalado — campos EXIF internos não serão gravados.')
        print('        Instale com: pip3 install piexif')
        print('        (macOS Spotlight/xattr e timestamps continuam funcionando)\n')

    extract(
        backup_path=backup_path,
        output_dir=args.output,
        dry_run=args.dry_run,
        filter_contact=args.contact,
        single_file=args.file,
        random_sample=args.random_sample,
        inspect=args.inspect_db,
    )


if __name__ == '__main__':
    main()
