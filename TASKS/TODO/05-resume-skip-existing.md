# Resume — Skip Already Extracted Files

## What
Skip files that already exist in the output folder so interrupted extractions can be safely resumed.

## Why
Extracting 59,000 files can take a long time. If interrupted, users shouldn't have to start over.

## How
- Before copying, check if `dest` already exists **and** has the same file size as `src`
- If match: skip and increment a `skipped` counter
- If size differs: re-copy (file may be corrupt or incomplete)
- Add a `skipped` line to the final report

## Notes
- Different from the collision-avoidance logic (which appends `_1`, `_2`)
- Should be the default behavior — no extra flag needed
- Print `[SKIPPED]` instead of the destination path for already-existing files
