# CSV / JSON Report Export

## What
Save the final extraction report as a structured file (CSV or JSON) for further analysis.

## Why
Power users may want to analyse their data: who sends the most media, which months are busiest, storage breakdown by contact, etc.

## How
- Add `--report PATH` argument (e.g. `--report report.json` or `--report report.csv`)
- Include per-file data: contact, jid, type, date, size, direction, destination path
- Also include a summary section: totals per contact, per type, per month

## Example output (JSON)
```json
{
  "summary": {
    "total_files": 59361,
    "total_size_gb": 12.4,
    "by_type": { "img": 42000, "video": 8000, "audio": 7000, "doc": 2361 },
    "by_contact": { "John Smith": 1823, "Family Group": 4201 }
  },
  "files": [
    { "contact": "John Smith", "date": "2023-03-15T14:30:22", "type": "img", "size": 194645, "direction": "received" }
  ]
}
```
