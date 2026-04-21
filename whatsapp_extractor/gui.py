"""
Tkinter GUI for WhatsApp Media Extractor.
Zero extra dependencies beyond the standard library.

Run via:  python3 gui.py
"""

import os
import queue
import shutil
import sqlite3
import sys
import tempfile
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, font, scrolledtext, ttk

from .backup import find_backup_path, find_chatstorage
from .constants import DEFAULT_TYPES, FILE_TYPES, WHATSAPP_DOMAIN
from .database import load_contact_map
from .extractor import extract
from .utils import extract_jid


# ---------------------------------------------------------------------------
# stdout redirect → tkinter Text widget via a Queue
# ---------------------------------------------------------------------------

class _QueueStream:
    """Wraps a Queue so that print() calls land in the GUI log."""

    def __init__(self, q: queue.Queue) -> None:
        self._q = q

    def write(self, text: str) -> None:
        if text:
            self._q.put(text)

    def flush(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class App(tk.Tk):

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()
        self.title('WhatsApp Media Extractor')
        self.resizable(True, True)
        self.minsize(900, 580)

        self._log_queue: queue.Queue        = queue.Queue()
        self._running                        = False
        self._contacts_data: list[tuple]    = []   # (display_name, jid, count)
        self._contacts_filtered: list[tuple] = []  # currently shown subset

        self._build_ui()
        self._auto_detect_backup()
        self._poll_log()

    # ------------------------------------------------------------------
    # UI layout
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Root split: left controls | right contact list
        self._left  = ttk.Frame(self)
        self._right = ttk.LabelFrame(self, text=' Contacts ', padding=8)

        self._right.pack(side='right', fill='y', padx=(0, 10), pady=6)
        self._left.pack(side='left', fill='both', expand=True)

        self._build_left(self._left)
        self._build_contacts(self._right)

    # ------------------------------------------------------------------
    # Left panel — all extraction controls
    # ------------------------------------------------------------------

    def _build_left(self, parent: ttk.Frame) -> None:
        pad = {'padx': 10, 'pady': 4}

        # ── Paths ──────────────────────────────────────────────────────
        paths_frame = ttk.LabelFrame(parent, text=' Paths ', padding=8)
        paths_frame.pack(fill='x', **pad)
        paths_frame.columnconfigure(1, weight=1)

        ttk.Label(paths_frame, text='Backup folder:').grid(row=0, column=0, sticky='w')
        self._backup_var = tk.StringVar()
        self._backup_var.trace_add('write', lambda *_: self._on_backup_changed())
        ttk.Entry(paths_frame, textvariable=self._backup_var).grid(
            row=0, column=1, sticky='ew', padx=6)
        ttk.Button(paths_frame, text='Browse…', command=self._browse_backup).grid(
            row=0, column=2)

        ttk.Label(paths_frame, text='Output folder:').grid(row=1, column=0, sticky='w', pady=(6, 0))
        self._output_var = tk.StringVar(value=str(Path.home() / 'WhatsApp_Media_Export'))
        ttk.Entry(paths_frame, textvariable=self._output_var).grid(
            row=1, column=1, sticky='ew', padx=6, pady=(6, 0))
        ttk.Button(paths_frame, text='Browse…', command=self._browse_output).grid(
            row=1, column=2, pady=(6, 0))

        # ── Filters ────────────────────────────────────────────────────
        filters_frame = ttk.LabelFrame(parent, text=' Filters ', padding=8)
        filters_frame.pack(fill='x', **pad)
        filters_frame.columnconfigure(1, weight=1)
        filters_frame.columnconfigure(3, weight=1)

        ttk.Label(filters_frame, text='Contact name:').grid(row=0, column=0, sticky='w')
        self._contact_var = tk.StringVar()
        ttk.Entry(filters_frame, textvariable=self._contact_var).grid(
            row=0, column=1, sticky='ew', padx=6)

        ttk.Label(filters_frame, text='Date from:').grid(row=0, column=2, sticky='w', padx=(12, 0))
        self._from_var = tk.StringVar()
        ttk.Entry(filters_frame, textvariable=self._from_var, width=12).grid(
            row=0, column=3, sticky='w', padx=6)
        ttk.Label(filters_frame, text='YYYY-MM-DD', foreground='grey').grid(
            row=0, column=4, sticky='w')

        ttk.Label(filters_frame, text='Date to:').grid(
            row=1, column=2, sticky='w', padx=(12, 0), pady=(6, 0))
        self._to_var = tk.StringVar()
        ttk.Entry(filters_frame, textvariable=self._to_var, width=12).grid(
            row=1, column=3, sticky='w', padx=6, pady=(6, 0))
        ttk.Label(filters_frame, text='YYYY-MM-DD', foreground='grey').grid(
            row=1, column=4, sticky='w', pady=(6, 0))

        # ── File types ─────────────────────────────────────────────────
        types_frame = ttk.LabelFrame(parent, text=' File types ', padding=8)
        types_frame.pack(fill='x', **pad)

        self._type_vars: dict[str, tk.BooleanVar] = {}
        labels = {
            'img':   'Images (jpg, png, heic…)',
            'video': 'Video (mp4, mov…)',
            'audio': 'Audio (opus, mp3…)',
            'doc':   'Documents (pdf, docx…)',
            'gif':   'GIF (opt-in)',
            'webp':  'WebP / stickers (opt-in)',
        }
        for col, (key, label) in enumerate(labels.items()):
            var = tk.BooleanVar(value=key in DEFAULT_TYPES)
            self._type_vars[key] = var
            ttk.Checkbutton(types_frame, text=label, variable=var).grid(
                row=0, column=col, sticky='w', padx=8)

        # ── Options ────────────────────────────────────────────────────
        opts_frame = ttk.Frame(parent)
        opts_frame.pack(fill='x', **pad)

        self._dryrun_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts_frame, text='Dry run (simulate — no files copied)',
                        variable=self._dryrun_var).pack(side='left')

        # ── Run / Stop ─────────────────────────────────────────────────
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x', padx=10, pady=(2, 6))

        self._run_btn = ttk.Button(btn_frame, text='▶  Run Extraction',
                                   command=self._run)
        self._run_btn.pack(side='left')

        self._stop_btn = ttk.Button(btn_frame, text='■  Stop',
                                    command=self._stop, state='disabled')
        self._stop_btn.pack(side='left', padx=8)

        self._status_var = tk.StringVar(value='Ready.')
        ttk.Label(btn_frame, textvariable=self._status_var,
                  foreground='grey').pack(side='left', padx=8)

        # ── Log ────────────────────────────────────────────────────────
        log_frame = ttk.LabelFrame(parent, text=' Log ', padding=4)
        log_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        mono = font.Font(family='Courier', size=10)
        self._log = scrolledtext.ScrolledText(
            log_frame, state='disabled', wrap='none',
            font=mono, background='#1e1e1e', foreground='#d4d4d4',
            insertbackground='white',
        )
        self._log.pack(fill='both', expand=True)
        self._log.tag_config('info',    foreground='#9cdcfe')
        self._log.tag_config('ok',      foreground='#4ec9b0')
        self._log.tag_config('warn',    foreground='#ce9178')
        self._log.tag_config('error',   foreground='#f44747')
        self._log.tag_config('section', foreground='#dcdcaa')

        ttk.Button(log_frame, text='Clear log',
                   command=self._clear_log).pack(anchor='e', pady=(4, 0))

    # ------------------------------------------------------------------
    # Right panel — contact list
    # ------------------------------------------------------------------

    def _build_contacts(self, parent: ttk.LabelFrame) -> None:
        # Load button
        self._load_contacts_btn = ttk.Button(
            parent, text='⟳  Load contacts', command=self._load_contacts)
        self._load_contacts_btn.pack(fill='x')

        # Search box
        ttk.Label(parent, text='Search:', foreground='grey').pack(
            anchor='w', pady=(8, 0))
        self._contacts_search_var = tk.StringVar()
        self._contacts_search_var.trace_add('write', lambda *_: self._filter_contacts_list())
        ttk.Entry(parent, textvariable=self._contacts_search_var).pack(fill='x')

        # Listbox + scrollbar
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill='both', expand=True, pady=(6, 0))

        sb = ttk.Scrollbar(list_frame, orient='vertical')
        sb.pack(side='right', fill='y')

        self._contacts_lb = tk.Listbox(
            list_frame,
            yscrollcommand=sb.set,
            selectmode='single',
            width=28,
            activestyle='dotbox',
            background='#2d2d2d',
            foreground='#d4d4d4',
            selectbackground='#094771',
            selectforeground='#ffffff',
            font=('Helvetica', 11),
        )
        self._contacts_lb.pack(side='left', fill='both', expand=True)
        sb.config(command=self._contacts_lb.yview)
        self._contacts_lb.bind('<<ListboxSelect>>', self._on_contact_select)

        # Status label
        self._contacts_status_var = tk.StringVar(value='Not loaded')
        ttk.Label(parent, textvariable=self._contacts_status_var,
                  foreground='grey').pack(anchor='w', pady=(4, 0))

        # Clear selection button
        ttk.Button(parent, text='✕  Clear selection',
                   command=self._clear_contact_selection).pack(fill='x', pady=(4, 0))

    # ------------------------------------------------------------------
    # Backup path helpers
    # ------------------------------------------------------------------

    def _on_backup_changed(self) -> None:
        """Reset contact list whenever the backup path changes."""
        self._contacts_data     = []
        self._contacts_filtered = []
        self._contacts_lb.delete(0, 'end')
        self._contacts_status_var.set('Not loaded')

    def _auto_detect_backup(self) -> None:
        try:
            path = find_backup_path()
            self._backup_var.set(str(path))
            self._log_append(f'[INFO] Backup auto-detected: {path}\n', 'info')
        except SystemExit:
            self._log_append('[WARNING] No backup auto-detected. Select one manually.\n', 'warn')

    def _browse_backup(self) -> None:
        path = filedialog.askdirectory(title='Select iPhone backup folder')
        if path:
            self._backup_var.set(path)

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title='Select output folder')
        if path:
            self._output_var.set(path)

    # ------------------------------------------------------------------
    # Contact list — load + filter + select
    # ------------------------------------------------------------------

    def _load_contacts(self) -> None:
        backup_str = self._backup_var.get().strip()
        if not backup_str:
            self._log_append('[ERROR] Set the backup folder first.\n', 'error')
            return
        backup_path = Path(backup_str)
        if not (backup_path / 'Manifest.db').exists():
            self._log_append('[ERROR] No Manifest.db found in the backup folder.\n', 'error')
            return

        self._load_contacts_btn.config(state='disabled')
        self._contacts_status_var.set('Loading…')
        self._contacts_lb.delete(0, 'end')

        threading.Thread(
            target=self._fetch_contacts,
            args=(backup_path,),
            daemon=True,
        ).start()

    def _fetch_contacts(self, backup_path: Path) -> None:
        """Background thread: reads contact map + media counts from the backup."""
        try:
            manifest_conn    = sqlite3.connect(str(backup_path / 'Manifest.db'))
            chatstorage_src  = find_chatstorage(manifest_conn, backup_path)

            with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
                tmp_path = tmp.name
            shutil.copy2(str(chatstorage_src), tmp_path)
            chat_conn   = sqlite3.connect(tmp_path)
            contact_map = load_contact_map(chat_conn)
            chat_conn.close()
            os.unlink(tmp_path)

            # Count all media files per JID from Manifest.db
            rows = manifest_conn.execute(
                "SELECT relativePath FROM Files "
                "WHERE domain = ? AND relativePath LIKE 'Message/Media/%' "
                "AND relativePath NOT LIKE '%.thumb%' "
                "AND relativePath NOT LIKE '%.mmsthumb%'",
                (WHATSAPP_DOMAIN,),
            ).fetchall()
            manifest_conn.close()

            counts: dict[str, int] = {}
            for (rpath,) in rows:
                jid = extract_jid(rpath)
                if jid:
                    counts[jid] = counts.get(jid, 0) + 1

            # Build sorted list: contacts with media first, then by count desc
            entries: list[tuple[str, str, int]] = []
            for jid, name in contact_map.items():
                entries.append((name or jid, jid, counts.get(jid, 0)))
            entries.sort(key=lambda e: (-e[2], e[0].lower()))

            self._contacts_data = entries
            self.after(0, lambda: self._populate_contacts_list(entries))

        except Exception as exc:
            self.after(0, lambda: self._log_append(
                f'[ERROR] Failed to load contacts: {exc}\n', 'error'))
            self.after(0, lambda: self._load_contacts_btn.config(state='normal'))
            self.after(0, lambda: self._contacts_status_var.set('Error loading contacts'))

    def _populate_contacts_list(self, entries: list[tuple]) -> None:
        self._contacts_filtered = entries
        self._contacts_lb.delete(0, 'end')
        for name, jid, count in entries:
            tag  = ' 👥' if '@g.us' in jid else ''
            line = f'{name}{tag}  ({count})' if count else f'{name}{tag}'
            self._contacts_lb.insert('end', line)
        self._contacts_status_var.set(f'{len(entries)} contacts')
        self._load_contacts_btn.config(state='normal')

    def _filter_contacts_list(self) -> None:
        """Re-renders the listbox based on the search field."""
        query = self._contacts_search_var.get().lower()
        filtered = [
            e for e in self._contacts_data
            if query in e[0].lower() or query in e[1].lower()
        ] if query else self._contacts_data

        self._contacts_filtered = filtered
        self._contacts_lb.delete(0, 'end')
        for name, jid, count in filtered:
            tag  = ' 👥' if '@g.us' in jid else ''
            line = f'{name}{tag}  ({count})' if count else f'{name}{tag}'
            self._contacts_lb.insert('end', line)

        count_label = f'{len(filtered)} of {len(self._contacts_data)}' if query else f'{len(filtered)} contacts'
        self._contacts_status_var.set(count_label)

    def _on_contact_select(self, _event: tk.Event) -> None:
        selection = self._contacts_lb.curselection()
        if not selection:
            return
        idx = selection[0]
        name = self._contacts_filtered[idx][0]
        self._contact_var.set(name)

    def _clear_contact_selection(self) -> None:
        self._contacts_lb.selection_clear(0, 'end')
        self._contact_var.set('')

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def _parse_date(self, value: str, label: str) -> datetime | None:
        if not value.strip():
            return None
        try:
            d = datetime.strptime(value.strip(), '%Y-%m-%d')
            return d.replace(tzinfo=datetime.now().astimezone().tzinfo)
        except ValueError:
            self._log_append(
                f'[ERROR] Invalid date for {label}: "{value}". Use YYYY-MM-DD.\n', 'error')
            return None

    def _run(self) -> None:
        if self._running:
            return

        backup_str = self._backup_var.get().strip()
        output_str = self._output_var.get().strip()

        if not backup_str:
            self._log_append('[ERROR] Backup folder is required.\n', 'error')
            return
        if not output_str:
            self._log_append('[ERROR] Output folder is required.\n', 'error')
            return

        backup_path = Path(backup_str)
        if not (backup_path / 'Manifest.db').exists():
            self._log_append(
                f'[ERROR] No Manifest.db found in: {backup_path}\n'
                '        Make sure this is a valid iPhone backup folder.\n', 'error')
            return

        date_from   = self._parse_date(self._from_var.get(), '--from')
        date_to_raw = self._parse_date(self._to_var.get(), '--to')
        date_to     = date_to_raw.replace(hour=23, minute=59, second=59) if date_to_raw else None

        file_types = {k for k, v in self._type_vars.items() if v.get()}
        if not file_types:
            self._log_append('[ERROR] Select at least one file type.\n', 'error')
            return

        contact = self._contact_var.get().strip() or None
        dry_run = self._dryrun_var.get()

        self._running = True
        self._run_btn.config(state='disabled')
        self._stop_btn.config(state='normal')
        self._status_var.set('Running…')

        self._thread = threading.Thread(
            target=self._run_extract,
            args=(Path(backup_str), Path(output_str),
                  dry_run, contact, file_types, date_from, date_to),
            daemon=True,
        )
        self._thread.start()

    def _run_extract(
        self,
        backup_path: Path,
        output_dir: Path,
        dry_run: bool,
        contact: str | None,
        file_types: set[str],
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> None:
        old_out, old_err = sys.stdout, sys.stderr
        stream = _QueueStream(self._log_queue)
        sys.stdout = stream  # type: ignore[assignment]
        sys.stderr = stream  # type: ignore[assignment]
        try:
            extract(
                backup_path=backup_path,
                output_dir=output_dir,
                dry_run=dry_run,
                filter_contact=contact,
                file_types=file_types,
                date_from=date_from,
                date_to=date_to,
            )
        except SystemExit as e:
            self._log_queue.put(f'[ERROR] {e}\n')
        except Exception as e:
            self._log_queue.put(f'[ERROR] Unexpected error: {e}\n')
        finally:
            sys.stdout, sys.stderr = old_out, old_err
            self._log_queue.put(None)  # sentinel → done

    def _stop(self) -> None:
        self._status_var.set('Stopping after current file…')
        self._stop_btn.config(state='disabled')

    # ------------------------------------------------------------------
    # Log
    # ------------------------------------------------------------------

    def _log_append(self, text: str, tag: str = '') -> None:
        self._log.config(state='normal')
        self._log.insert('end', text, tag if tag else '')
        self._log.config(state='disabled')
        self._log.see('end')

    def _tag_for_line(self, line: str) -> str:
        u = line.upper()
        if '[ERROR]'   in u: return 'error'
        if '[WARNING]' in u: return 'warn'
        if '[INFO]'    in u: return 'info'
        if '===' in u or '---' in u or 'FINAL REPORT' in u: return 'section'
        if '[' in u and '/' in u: return 'ok'
        return ''

    def _clear_log(self) -> None:
        self._log.config(state='normal')
        self._log.delete('1.0', 'end')
        self._log.config(state='disabled')

    def _poll_log(self) -> None:
        try:
            while True:
                item = self._log_queue.get_nowait()
                if item is None:
                    self._running = False
                    self._run_btn.config(state='normal')
                    self._stop_btn.config(state='disabled')
                    self._status_var.set('Done.')
                else:
                    self._log_append(item, self._tag_for_line(item))
        except queue.Empty:
            pass
        self.after(100, self._poll_log)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = App()
    app.mainloop()


if __name__ == '__main__':
    main()
