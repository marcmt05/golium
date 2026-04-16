from __future__ import annotations

import math


def brier(prob: float, outcome: int) -> float:
    return (prob - outcome) ** 2


def log_loss(prob: float, outcome: int) -> float:
    p = min(max(prob, 1e-8), 1 - 1e-8)
    return -(outcome * math.log(p) + (1 - outcome) * math.log(1 - p))


def aggregate_picks(picks: list[dict]) -> dict:
    if not picks:
        return {"count": 0, "yield": 0.0, "roi": 0.0, "hit_rate": 0.0, "ev_expected": 0.0, "ev_realized": 0.0}

    total_stake = sum(p.get("stake", 0.0) for p in picks) or 1.0
    total_profit = sum(p.get("profit", 0.0) for p in picks)
    wins = sum(1 for p in picks if p.get("result") == 1)
    ev_expected = sum(p.get("ev", 0.0) * p.get("stake", 0.0) for p in picks)

    graded = [p for p in picks if p.get("result") in (0, 1)]
    brier_avg = sum(brier(p["prob"], p["result"]) for p in graded) / max(len(graded), 1)
    log_avg = sum(log_loss(p["prob"], p["result"]) for p in graded) / max(len(graded), 1)

    return {
        "count": len(picks),
        "yield": total_profit / total_stake,
        "roi": total_profit / total_stake,
        "hit_rate": wins / max(len(picks), 1),
        "ev_expected": ev_expected,
        "ev_realized": total_profit,
        "brier_score": brier_avg,
        "log_loss": log_avg,
    }
