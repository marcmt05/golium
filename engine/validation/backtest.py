from __future__ import annotations

from .metrics import aggregate_picks


def backtest_snapshot(picks: list[dict]) -> dict:
    """Simple backtest scaffold based on current pick ledger."""
    by_market: dict[str, list[dict]] = {}
    by_league: dict[str, list[dict]] = {}
    for p in picks:
        by_market.setdefault(p.get("market", "?"), []).append(p)
        by_league.setdefault(p.get("league", "?"), []).append(p)

    return {
        "global": aggregate_picks(picks),
        "by_market": {k: aggregate_picks(v) for k, v in by_market.items()},
        "by_league": {k: aggregate_picks(v) for k, v in by_league.items()},
    }
