#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine.validation.backtest import backtest_snapshot


def latest_snapshot(history_dir: Path) -> Path | None:
    snapshots = sorted([p for p in history_dir.iterdir() if p.is_dir()]) if history_dir.exists() else []
    return snapshots[-1] if snapshots else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run backtest metrics over picks")
    parser.add_argument("--picks-file", default=None, help="Optional picks.json path")
    parser.add_argument("--history-dir", default="history/snapshots")
    args = parser.parse_args()

    if args.picks_file:
        picks_file = Path(args.picks_file)
    else:
        snap = latest_snapshot(Path(args.history_dir))
        if not snap:
            raise SystemExit("No snapshots found. Run pipeline first.")
        picks_file = snap / "picks.json"

    if not picks_file.exists():
        raise SystemExit(f"{picks_file} not found")

    payload = json.loads(picks_file.read_text(encoding="utf-8"))
    report = backtest_snapshot(payload.get("picks", []))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
