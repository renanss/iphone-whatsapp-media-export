# GUI — Graphical Interface

## What
A simple graphical interface for non-technical users who aren't comfortable with the terminal.

## Why
The target audience (people with years of WhatsApp media) includes many non-developers. A GUI removes the barrier entirely.

## How
Two options:

### Option A — Desktop (tkinter, no extra deps)
- Contact list with checkboxes
- Date range pickers
- File type toggles
- Output folder selector
- Progress bar
- Run button

### Option B — Web UI (Flask + plain HTML)
- Run `python3 gui.py` → opens `http://localhost:5000` in the browser
- More flexible UI, easier to style
- No extra deps beyond Flask

## Notes
- Both options should call the same `extract()` function internally — no logic duplication
- Start with Option A (tkinter) since it requires zero extra dependencies
