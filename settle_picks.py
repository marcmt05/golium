#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine.validation.backtest import backtest_snapshot


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict | list) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fixture_index(data_payload: dict) -> dict[str, dict]:
    leagues = data_payload.get("leagues", {})
    out: dict[str, dict] = {}
    for league in leagues.values():
        for fixture in league.get("fixtures", []):
            out[str(fixture.get("id", ""))] = fixture
    return out


def is_final_status(status: str) -> bool:
    st = (status or "").upper()
    return any(token in st for token in ("FINAL", "FULL", "STATUS_FINAL", "FT"))


def settle_market(market: str, home: int, away: int) -> str:
    total = home + away
    if market == "1":
        return "win" if home > away else "loss"
    if market == "X":
        return "win" if home == away else "loss"
    if market == "2":
        return "win" if away > home else "loss"
    if market == "O2.5":
        return "win" if total > 2.5 else "loss"
    if market == "U2.5":
        return "win" if total < 2.5 else "loss"
    if market == "O3.5":
        return "win" if total > 3.5 else "loss"
    if market == "U3.5":
        return "win" if total < 3.5 else "loss"
    if market == "BTTS_Y":
        return "win" if home > 0 and away > 0 else "loss"
    if market == "BTTS_N":
        return "win" if (home == 0 or away == 0) else "loss"
    if market == "AH_HOME_-0.5":
        return "win" if home > away else "loss"
    if market == "AH_AWAY_-0.5":
        return "win" if away > home else "loss"
    return "void"


def profit_units(result: str, stake: float, offered_odds: float | None) -> float:
    if result in ("push", "void"):
        return 0.0
    if result == "loss":
        return -stake
    if result == "win":
        if offered_odds is None:
            return 0.0
        return stake * (offered_odds - 1.0)
    return 0.0


def settle_snapshot(snapshot_dir: Path) -> dict[str, int]:
    data_file = snapshot_dir / "data.json"
    picks_file = snapshot_dir / "picks.json"
    ledger_file = snapshot_dir / "ledger.json"
    metrics_file = snapshot_dir / "metrics.json"

    if not data_file.exists() or not picks_file.exists():
        return {"open": 0, "settled": 0, "void": 0}

    data_payload = load_json(data_file)
    picks_payload = load_json(picks_file)
    picks = picks_payload.get("picks", [])
    fixtures = fixture_index(data_payload)

    counts = {"open": 0, "settled": 0, "void": 0}
    for pick in picks:
        if pick.get("status") == "settled":
            counts["settled"] += 1
            continue

        fixture = fixtures.get(str(pick.get("fixture_id", "")))
        if not fixture:
            counts["open"] += 1
            continue

        home = fixture.get("homeScore")
        away = fixture.get("awayScore")
        if home is None or away is None or not is_final_status(str(fixture.get("status", ""))):
            counts["open"] += 1
            continue

        result = settle_market(str(pick.get("market", "")), int(home), int(away))
        pick["status"] = "settled"
        pick["result"] = result
        stake = float(pick.get("stake_fraction") or 0.0)
        pick["profit_units"] = round(profit_units(result, stake, pick.get("offered_odds")), 6)

        if result == "void":
            counts["void"] += 1
        else:
            counts["settled"] += 1

    picks_payload["picks"] = picks
    write_json(picks_file, picks_payload)

    total_stake = sum(float(p.get("stake_fraction") or 0.0) for p in picks if p.get("status") == "settled")
    total_profit = sum(float(p.get("profit_units") or 0.0) for p in picks if p.get("status") == "settled")

    ledger_payload = {
        "snapshot_id": picks_payload.get("snapshot_id"),
        "generated_at": picks_payload.get("generated_at"),
        "total_picks": len(picks),
        "settled_picks": sum(1 for p in picks if p.get("status") == "settled"),
        "open_picks": sum(1 for p in picks if p.get("status") == "open"),
        "total_stake_units": total_stake,
        "total_profit_units": total_profit,
        "roi": (total_profit / total_stake) if total_stake > 0 else 0.0,
    }
    write_json(ledger_file, ledger_payload)
    write_json(metrics_file, backtest_snapshot(picks))

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Settle historical picks across snapshot folders.")
    parser.add_argument("--history-dir", default="history/snapshots", help="Snapshots directory")
    parser.add_argument("--sync-public", action="store_true", help="If set, copy latest settled picks/metrics into public-data")
    args = parser.parse_args()

    base = Path(args.history_dir)
    if not base.exists():
        raise SystemExit(f"History directory not found: {base}")

    totals = {"open": 0, "settled": 0, "void": 0}
    snapshots = sorted([p for p in base.iterdir() if p.is_dir()])
    for snapshot in snapshots:
        c = settle_snapshot(snapshot)
        for k in totals:
            totals[k] += c[k]

    if args.sync_public and snapshots:
        latest = snapshots[-1]
        for filename in ("picks.json", "metrics.json", "ledger.json", "model-info.json", "data.json"):
            src = latest / filename
            if src.exists():
                dst = Path("public-data") / filename
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    print(
        f"Settlement done: snapshots={len(snapshots)} settled={totals['settled']} open={totals['open']} void={totals['void']}"
    )


if __name__ == "__main__":
    main()
