#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from storage import save_snapshot

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data.json"

if __name__ == "__main__":
    if not DATA_PATH.exists():
        raise SystemExit("No existe data.json")
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    snapshot_id = save_snapshot(payload, source_file=DATA_PATH.name)
    print(f"Snapshot guardado con id={snapshot_id} en golium.db")
