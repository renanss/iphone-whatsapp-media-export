#!/usr/bin/env python3
"""
Lista contatos/grupos do WhatsApp presentes no backup do iPhone,
com contagem de fotos disponíveis para cada um.

Uso:
  python3 list_contacts.py
  python3 list_contacts.py --backup /path/para/backup
  python3 list_contacts.py --sort name       # ordena por nome (padrão: fotos)
  python3 list_contacts.py --filter familia  # filtra por substring
"""

import argparse
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

WHATSAPP_DOMAIN = "AppDomainGroup-group.net.whatsapp.WhatsApp.shared"


def find_backup_path() -> Path:
    base = Path.home() / 'Library' / 'Application Support' / 'MobileSync' / 'Backup'
    if not base.exists():
        sys.exit(f'[ERRO] Diretório de backup não encontrado: {base}')
    backups = [d for d in base.iterdir() if d.is_dir() and (d / 'Manifest.db').exists()]
    if not backups:
        sys.exit(f'[ERRO] Nenhum backup com Manifest.db encontrado em: {base}')
    backups.sort(key=lambda d: (d / 'Manifest.db').stat().st_mtime, reverse=True)
    return backups[0]


def find_chatstorage(manifest_conn: sqlite3.Connection, backup_path: Path) -> Path:
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


def extract_jid(relative_path: str) -> str | None:
    match = re.match(r'^Message/Media/([^/]+)/', relative_path)
    return match.group(1) if match else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Lista contatos/grupos do WhatsApp com contagem de fotos.'
    )
    parser.add_argument('--backup', type=Path, default=None)
    parser.add_argument(
        '--sort', choices=['name', 'photos'], default='photos',
        help='Ordenar por nome ou por quantidade de fotos (padrão: photos)'
    )
    parser.add_argument(
        '--filter', type=str, default=None, metavar='TEXTO',
        help='Filtra contatos cujo nome ou JID contenha TEXTO (case-insensitive)'
    )
    args = parser.parse_args()

    backup_path = args.backup or find_backup_path()
    manifest_db = backup_path / 'Manifest.db'
    if not manifest_db.exists():
        sys.exit(f'[ERRO] Manifest.db não encontrado em: {backup_path}')

    print(f'[INFO] Backup: {backup_path}\n')

    manifest_conn = sqlite3.connect(str(manifest_db))

    # Contagem de fotos por JID direto do Manifest.db
    rows = manifest_conn.execute(
        """
        SELECT relativePath FROM Files
        WHERE domain = ?
        AND relativePath LIKE 'Message/Media/%'
        AND relativePath NOT LIKE '%.thumb%'
        AND (
            relativePath LIKE '%.jpg'
            OR relativePath LIKE '%.jpeg'
            OR relativePath LIKE '%.png'
        )
        """,
        (WHATSAPP_DOMAIN,)
    ).fetchall()

    photo_count: dict[str, int] = {}
    for (rpath,) in rows:
        jid = extract_jid(rpath)
        if jid:
            photo_count[jid] = photo_count.get(jid, 0) + 1

    # Carrega nomes do ChatStorage
    chatstorage_src = find_chatstorage(manifest_conn, backup_path)
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
        tmp_path = tmp.name
    shutil.copy2(str(chatstorage_src), tmp_path)

    chat_conn = sqlite3.connect(tmp_path)
    contact_rows = chat_conn.execute(
        "SELECT ZCONTACTJID, ZPARTNERNAME FROM ZWACHATSESSION WHERE ZCONTACTJID IS NOT NULL"
    ).fetchall()
    contact_map: dict[str, str] = {jid: (name or '').strip() for jid, name in contact_rows}

    chat_conn.close()
    manifest_conn.close()
    os.unlink(tmp_path)

    # Monta lista final: todos os JIDs que têm fotos
    entries = []
    for jid, count in photo_count.items():
        name = contact_map.get(jid, '')
        entries.append((jid, name, count))

    # Inclui contatos do ChatStorage sem fotos (count=0) apenas se não filtrado
    if not args.filter:
        for jid, name in contact_map.items():
            if jid not in photo_count:
                entries.append((jid, name, 0))

    # Filtro
    if args.filter:
        flt = args.filter.lower()
        entries = [e for e in entries if flt in e[0].lower() or flt in e[1].lower()]

    # Ordenação
    if args.sort == 'name':
        entries.sort(key=lambda e: (e[1].lower() or e[0].lower()))
    else:
        entries.sort(key=lambda e: -e[2])

    # Exibe
    total_photos = sum(e[2] for e in entries)
    groups = [e for e in entries if '@g.us' in e[0]]
    contacts = [e for e in entries if '@g.us' not in e[0]]

    def print_section(title: str, items: list) -> None:
        if not items:
            return
        print(f'{"─" * 70}')
        print(f'  {title}')
        print(f'{"─" * 70}')
        print(f'  {"Nome":<40} {"JID":<35} {"Fotos":>6}')
        print(f'  {"─"*40} {"─"*35} {"─"*6}')
        for jid, name, count in items:
            name_display = name if name else '(sem nome)'
            print(f'  {name_display:<40} {jid:<35} {count:>6}')

    print(f'{"═" * 70}')
    print(f'  CONTATOS DO WHATSAPP — {len(entries)} encontrados / {total_photos} fotos')
    print(f'{"═" * 70}')
    print_section(f'CONTATOS INDIVIDUAIS ({len(contacts)})', contacts)
    print_section(f'GRUPOS ({len(groups)})', groups)
    print(f'{"═" * 70}')
    print(f'  Total de fotos listadas: {total_photos}')
    print(f'{"═" * 70}\n')

    print('Para extrair um contato específico:')
    print('  python3 extract_whatsapp_media.py --contact "Nome do Contato"')
    print('  python3 extract_whatsapp_media.py --dry-run --contact "Nome do Contato"')


if __name__ == '__main__':
    main()
