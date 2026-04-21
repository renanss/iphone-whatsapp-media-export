# Progress Bar — Replace Per-File Output

## What
Replace the per-file print lines with a `tqdm` progress bar for cleaner output during large extractions.

## Why
Printing 59,000 lines to the terminal is slow and unreadable. A progress bar with ETA is much friendlier.

## How
- Add `tqdm` as an optional dependency
- Wrap the main loop: `for idx, (file_id, relative_path) in tqdm(enumerate(all_files), total=total)`
- Show: `[=====>    ] 15234/59361 • João Silva • 2.3 GB • ETA 4m32s`
- Fall back to current line-by-line output if `tqdm` is not installed
- Keep verbose mode available via `--verbose` for debugging

## Dependencies
```bash
pip3 install tqdm --break-system-packages
```
