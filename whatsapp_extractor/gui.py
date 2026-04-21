"""
Tkinter GUI for WhatsApp Media Extractor.
Zero extra dependencies beyond the standard library.

Run via:  python3 gui.py
"""

import queue
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, font, scrolledtext, ttk

from .backup import find_backup_path
from .constants import DEFAULT_TYPES, FILE_TYPES
from .extractor import extract


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
        self.minsize(700, 560)

        self._log_queue: queue.Queue = queue.Queue()
        self._running   = False

        self._build_ui()
        self._auto_detect_backup()
        self._poll_log()

    # ------------------------------------------------------------------
    # UI layout
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = {'padx': 10, 'pady': 4}

        # ── Paths ──────────────────────────────────────────────────────
        paths_frame = ttk.LabelFrame(self, text=' Paths ', padding=8)
        paths_frame.pack(fill='x', **pad)
        paths_frame.columnconfigure(1, weight=1)

        ttk.Label(paths_frame, text='Backup folder:').grid(row=0, column=0, sticky='w')
        self._backup_var = tk.StringVar()
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
        filters_frame = ttk.LabelFrame(self, text=' Filters ', padding=8)
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
        types_frame = ttk.LabelFrame(self, text=' File types ', padding=8)
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
            default = key in DEFAULT_TYPES
            var = tk.BooleanVar(value=default)
            self._type_vars[key] = var
            ttk.Checkbutton(types_frame, text=label, variable=var).grid(
                row=0, column=col, sticky='w', padx=8)

        # ── Options ────────────────────────────────────────────────────
        opts_frame = ttk.Frame(self)
        opts_frame.pack(fill='x', **pad)

        self._dryrun_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts_frame, text='Dry run (simulate — no files copied)',
                        variable=self._dryrun_var).pack(side='left')

        # ── Run button ─────────────────────────────────────────────────
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', padx=10, pady=(2, 6))

        self._run_btn = ttk.Button(btn_frame, text='▶  Run Extraction',
                                   command=self._run, style='Accent.TButton')
        self._run_btn.pack(side='left')

        self._stop_btn = ttk.Button(btn_frame, text='■  Stop',
                                    command=self._stop, state='disabled')
        self._stop_btn.pack(side='left', padx=8)

        self._status_var = tk.StringVar(value='Ready.')
        ttk.Label(btn_frame, textvariable=self._status_var, foreground='grey').pack(
            side='left', padx=8)

        # ── Log ────────────────────────────────────────────────────────
        log_frame = ttk.LabelFrame(self, text=' Log ', padding=4)
        log_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        mono = font.Font(family='Courier', size=10)
        self._log = scrolledtext.ScrolledText(
            log_frame, state='disabled', wrap='none',
            font=mono, background='#1e1e1e', foreground='#d4d4d4',
            insertbackground='white',
        )
        self._log.pack(fill='both', expand=True)

        # colour tags for the log
        self._log.tag_config('info',    foreground='#9cdcfe')
        self._log.tag_config('ok',      foreground='#4ec9b0')
        self._log.tag_config('warn',    foreground='#ce9178')
        self._log.tag_config('error',   foreground='#f44747')
        self._log.tag_config('section', foreground='#dcdcaa')

        clear_btn = ttk.Button(log_frame, text='Clear log', command=self._clear_log)
        clear_btn.pack(anchor='e', pady=(4, 0))

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

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
    # Extraction
    # ------------------------------------------------------------------

    def _parse_date(self, value: str, label: str) -> datetime | None:
        if not value.strip():
            return None
        try:
            d = datetime.strptime(value.strip(), '%Y-%m-%d')
            return d.replace(tzinfo=datetime.now().astimezone().tzinfo)
        except ValueError:
            self._log_append(f'[ERROR] Invalid date for {label}: "{value}". Use YYYY-MM-DD.\n', 'error')
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
        output_dir  = Path(output_str)

        if not (backup_path / 'Manifest.db').exists():
            self._log_append(
                f'[ERROR] No Manifest.db found in: {backup_path}\n'
                '        Make sure this is a valid iPhone backup folder.\n', 'error')
            return

        date_from = self._parse_date(self._from_var.get(), '--from')
        date_to_raw = self._parse_date(self._to_var.get(), '--to')
        date_to = date_to_raw.replace(hour=23, minute=59, second=59) if date_to_raw else None

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
            args=(backup_path, output_dir, dry_run, contact, file_types, date_from, date_to),
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
        old_stdout = sys.stdout
        old_stderr = sys.stderr
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
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self._log_queue.put(None)  # sentinel → extraction finished

    def _stop(self) -> None:
        # Threads can't be forcibly killed in Python; we just update the UI.
        # The extraction loop will finish its current file and the sentinel
        # will arrive naturally.
        self._status_var.set('Stopping after current file…')
        self._stop_btn.config(state='disabled')

    # ------------------------------------------------------------------
    # Log
    # ------------------------------------------------------------------

    def _log_append(self, text: str, tag: str = '') -> None:
        self._log.config(state='normal')
        if tag:
            self._log.insert('end', text, tag)
        else:
            self._log.insert('end', text)
        self._log.config(state='disabled')
        self._log.see('end')

    def _tag_for_line(self, line: str) -> str:
        l = line.upper()
        if '[ERROR]' in l:   return 'error'
        if '[WARNING]' in l: return 'warn'
        if '[INFO]' in l:    return 'info'
        if '===' in l or '---' in l or 'FINAL REPORT' in l: return 'section'
        if '[' in l and '/' in l: return 'ok'   # progress lines like [  123/45678]
        return ''

    def _clear_log(self) -> None:
        self._log.config(state='normal')
        self._log.delete('1.0', 'end')
        self._log.config(state='disabled')

    def _poll_log(self) -> None:
        """Drains the queue and writes lines to the log widget. Runs on main thread."""
        try:
            while True:
                item = self._log_queue.get_nowait()
                if item is None:
                    # extraction finished
                    self._running = False
                    self._run_btn.config(state='normal')
                    self._stop_btn.config(state='disabled')
                    self._status_var.set('Done.')
                else:
                    tag = self._tag_for_line(item)
                    self._log_append(item, tag)
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
