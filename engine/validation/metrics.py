from __future__ import annotations

import math
from collections import defaultdict


def brier(prob: float, outcome: int) -> float:
    return (prob - outcome) ** 2


def log_loss(prob: float, outcome: int) -> float:
    p = min(max(prob, 1e-8), 1 - 1e-8)
    return -(outcome * math.log(p) + (1 - outcome) * math.log(1 - p))


def _odds_bucket(offered_odds: float | None) -> str:
    if offered_odds is None:
        return "N/A"
    if offered_odds < 1.5:
        return "1.00-1.49"
    if offered_odds < 2.0:
        return "1.50-1.99"
    if offered_odds < 2.5:
        return "2.00-2.49"
    return "2.50+"


def _edge_bucket(edge: float | None) -> str:
    if edge is None:
        return "N/A"
    pct = edge * 100
    if pct < 2:
        return "0-1.99%"
    if pct < 4:
        return "2-3.99%"
    if pct < 6:
        return "4-5.99%"
    return "6%+"


def aggregate_picks(picks: list[dict]) -> dict:
    if not picks:
        return {
            "total_picks": 0,
            "settled_picks": 0,
            "yield": 0.0,
            "roi": 0.0,
            "hit_rate": 0.0,
            "average_edge": 0.0,
            "average_ev": 0.0,
            "average_profit": 0.0,
            "brier_score": None,
            "log_loss": None,
        }

    settled = [p for p in picks if p.get("status") == "settled"]
    graded = [p for p in settled if p.get("result") in ("win", "loss")]

    total_stake = sum(float(p.get("stake_fraction") or 0.0) for p in settled)
    total_profit = sum(float(p.get("profit_units") or 0.0) for p in settled)

    wins = sum(1 for p in graded if p.get("result") == "win")
    edges = [float(p["edge"]) for p in picks if p.get("edge") is not None]
    evs = [float(p["ev"]) for p in picks if p.get("ev") is not None]

    brier_avg = None
    log_avg = None
    if graded:
        brier_avg = sum(brier(float(p["model_prob"]), 1 if p["result"] == "win" else 0) for p in graded) / len(graded)
        log_avg = sum(log_loss(float(p["model_prob"]), 1 if p["result"] == "win" else 0) for p in graded) / len(graded)

    stake_base = total_stake if total_stake > 0 else 1.0
    return {
        "total_picks": len(picks),
        "settled_picks": len(settled),
        "yield": total_profit / stake_base,
        "roi": total_profit / stake_base,
        "hit_rate": wins / len(graded) if graded else 0.0,
        "average_edge": sum(edges) / len(edges) if edges else 0.0,
        "average_ev": sum(evs) / len(evs) if evs else 0.0,
        "average_profit": total_profit / len(settled) if settled else 0.0,
        "brier_score": brier_avg,
        "log_loss": log_avg,
    }


def grouped_metrics(picks: list[dict], key_fn) -> dict[str, dict]:
    buckets: defaultdict[str, list[dict]] = defaultdict(list)
    for pick in picks:
        buckets[key_fn(pick)].append(pick)
    return {key: aggregate_picks(rows) for key, rows in buckets.items()}


def build_metrics_report(picks: list[dict]) -> dict:
    return {
        "global": aggregate_picks(picks),
        "by_market": grouped_metrics(picks, lambda p: str(p.get("market", "?"))),
        "by_league": grouped_metrics(picks, lambda p: str(p.get("league", "?"))),
        "by_pick_type": grouped_metrics(picks, lambda p: str(p.get("pick_type", "?"))),
        "by_odds_bucket": grouped_metrics(picks, lambda p: _odds_bucket(p.get("offered_odds"))),
        "by_edge_bucket": grouped_metrics(picks, lambda p: _edge_bucket(p.get("edge"))),
    }
