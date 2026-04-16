#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from engine.validation.backtest import backtest_snapshot


def main() -> None:
    picks_file = Path("public-data/picks.json")
    if not picks_file.exists():
        raise SystemExit("public-data/picks.json not found. Run pipeline first.")
    payload = json.loads(picks_file.read_text(encoding="utf-8"))
    report = backtest_snapshot(payload.get("picks", []))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
