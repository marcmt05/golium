from __future__ import annotations

from .metrics import aggregate_picks, grouped_metrics, odds_bucket, edge_bucket


def backtest_snapshot(picks: list[dict]) -> dict:
    odds_grouped = {}
    edge_grouped = {}
    for p in picks:
        odds_grouped.setdefault(odds_bucket(p.get("offered_odds")), []).append(p)
        edge_grouped.setdefault(edge_bucket(p.get("edge")), []).append(p)

    return {
        "global": aggregate_picks(picks),
        "by_market": grouped_metrics(picks, "market"),
        "by_league": grouped_metrics(picks, "league"),
        "by_pick_type": grouped_metrics(picks, "pick_type"),
        "by_odds_bucket": {k: aggregate_picks(v) for k, v in odds_grouped.items()},
        "by_edge_bucket": {k: aggregate_picks(v) for k, v in edge_grouped.items()},
    }
