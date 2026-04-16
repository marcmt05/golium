#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine.markets import market_outcome
from engine.validation.backtest import backtest_snapshot

FINAL_STATUS_MARKERS = ("FINAL", "FULL")


def load_results(data_file: Path) -> dict[str, tuple[int, int, str]]:
    payload = json.loads(data_file.read_text(encoding="utf-8"))
    leagues = payload.get("leagues", {}) if isinstance(payload, dict) else {}
    out: dict[str, tuple[int, int, str]] = {}
    for league in leagues.values():
        for fix in league.get("fixtures", []):
            fid = str(fix.get("id", ""))
            status = str(fix.get("status", ""))
            if not fid or not any(marker in status for marker in FINAL_STATUS_MARKERS):
                continue
            out[fid] = (int(fix.get("homeScore", 0)), int(fix.get("awayScore", 0)), status)
    return out


def settle_ledger(ledger: list[dict], results: dict[str, tuple[int, int, str]]) -> list[dict]:
    updated = []
    for row in ledger:
        if row.get("status") == "settled":
            updated.append(row)
            continue
        fixture_id = str(row.get("fixture_id", ""))
        if fixture_id not in results:
            updated.append(row)
            continue

        hg, ag, _ = results[fixture_id]
        outcome = market_outcome(str(row.get("market", "")), hg, ag)
        row["status"] = "settled"
        row["result"] = outcome
        stake = float(row.get("stake_fraction", 0.0))
        odds = row.get("offered_odds")
        if outcome == "win":
            if odds and odds > 1:
                row["profit_units"] = stake * (float(odds) - 1)
            else:
                row["profit_units"] = 0.0
        elif outcome == "loss":
            row["profit_units"] = -stake
        else:
            row["profit_units"] = 0.0
        updated.append(row)
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Settle historical Golium picks")
    parser.add_argument("--history-dir", default="history/snapshots")
    parser.add_argument("--results", default="public-data/data.json")
    args = parser.parse_args()

    history_dir = Path(args.history_dir)
    results = load_results(Path(args.results))
    if not history_dir.exists():
        raise SystemExit("history directory not found")

    for snapshot in sorted(p for p in history_dir.iterdir() if p.is_dir()):
        ledger_file = snapshot / "ledger.json"
        if not ledger_file.exists():
            continue
        ledger = json.loads(ledger_file.read_text(encoding="utf-8"))
        settled = settle_ledger(ledger, results)
        ledger_file.write_text(json.dumps(settled, ensure_ascii=False, indent=2), encoding="utf-8")

        picks_file = snapshot / "picks.json"
        if picks_file.exists():
            picks_payload = json.loads(picks_file.read_text(encoding="utf-8"))
            picks_payload["picks"] = settled
            picks_file.write_text(json.dumps(picks_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        metrics_file = snapshot / "metrics.json"
        metrics = backtest_snapshot(settled)
        metrics_file.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Settlement complete using {len(results)} final fixtures.")


if __name__ == "__main__":
    main()
