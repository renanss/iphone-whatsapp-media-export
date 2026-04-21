# `--since-last-run` — Incremental Extraction

## What
Add a `--since-last-run` flag that reads the date of the last successful extraction from a `.state` file and automatically sets `--from` to that date.

## Why
Users who run the extractor periodically (e.g. monthly) shouldn't have to re-extract everything from scratch each time.

## How
- Save a `.whatsapp_export_state.json` file in the output folder after each successful run containing `{"last_run": "2025-12-13T17:39:44"}`
- `--since-last-run` reads that file and injects it as `date_from`
- Update the state file at the end of each run

## Notes
- Should be skipped in `--dry-run` mode (don't update state)
- Print a clear message: `[INFO] Resuming from last run: 2025-12-13`
