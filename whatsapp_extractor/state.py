"""
Incremental extraction state helpers.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any


STATE_FILENAME = '.whatsapp_export_state.json'


def state_path(output_dir: Path) -> Path:
    return output_dir / STATE_FILENAME


def load_last_run(output_dir: Path) -> datetime | None:
    path = state_path(output_dir)
    if not path.exists():
        return None

    try:
        payload: dict[str, Any] = json.loads(path.read_text(encoding='utf-8'))
        raw_value = payload.get('last_run')
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise ValueError('missing "last_run" string')
        dt = datetime.fromisoformat(raw_value)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f'Invalid state file at {path}: {exc}') from exc

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return dt


def save_last_run(output_dir: Path, dt: datetime | None = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    value = (dt or datetime.now().astimezone()).replace(microsecond=0).isoformat()
    path = state_path(output_dir)
    tmp_path = path.with_suffix(path.suffix + '.tmp')
    tmp_path.write_text(
        json.dumps({'last_run': value}, indent=2) + '\n',
        encoding='utf-8',
    )
    tmp_path.replace(path)
    return path
