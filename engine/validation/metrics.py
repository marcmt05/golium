from __future__ import annotations

import math
from collections import defaultdict


def brier(prob: float, outcome: int) -> float:
    return (prob - outcome) ** 2


def log_loss(prob: float, outcome: int) -> float:
    p = min(max(prob, 1e-8), 1 - 1e-8)
    return -(outcome * math.log(p) + (1 - outcome) * math.log(1 - p))


def odds_bucket(odds: float | None) -> str:
    if odds is None:
        return "no_odds"
    if odds < 1.5:
        return "1.00-1.49"
    if odds < 2.0:
        return "1.50-1.99"
    if odds < 2.5:
        return "2.00-2.49"
    return "2.50+"


def edge_bucket(edge_value: float | None) -> str:
    if edge_value is None:
        return "no_edge"
    pct = edge_value * 100
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

    settled = [p for p in picks if p.get("status") == "settled" and p.get("result") in ("win", "loss")]
    stake_total = sum(p.get("stake_fraction", 0.0) for p in settled) or 1.0
    profit_total = sum(p.get("profit_units", 0.0) for p in settled)
    wins = sum(1 for p in settled if p.get("result") == "win")
    edges = [p.get("edge") for p in picks if p.get("edge") is not None]
    evs = [p.get("ev") for p in picks if p.get("ev") is not None]

    scored = [p for p in settled if p.get("model_prob") is not None]
    brier_avg = None
    log_avg = None
    if scored:
        y = [1 if p["result"] == "win" else 0 for p in scored]
        probs = [float(p["model_prob"]) for p in scored]
        brier_avg = sum(brier(p, o) for p, o in zip(probs, y)) / len(scored)
        log_avg = sum(log_loss(p, o) for p, o in zip(probs, y)) / len(scored)

    return {
        "total_picks": len(picks),
        "settled_picks": len(settled),
        "yield": (profit_total / stake_total) if settled else 0.0,
        "roi": (profit_total / stake_total) if settled else 0.0,
        "hit_rate": (wins / len(settled)) if settled else 0.0,
        "average_edge": (sum(edges) / len(edges)) if edges else 0.0,
        "average_ev": (sum(evs) / len(evs)) if evs else 0.0,
        "average_profit": (profit_total / len(settled)) if settled else 0.0,
        "brier_score": brier_avg,
        "log_loss": log_avg,
    }


def grouped_metrics(picks: list[dict], field: str) -> dict[str, dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for p in picks:
        buckets[str(p.get(field, "unknown"))].append(p)
    return {k: aggregate_picks(v) for k, v in buckets.items()}
