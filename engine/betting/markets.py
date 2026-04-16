from __future__ import annotations


def fair_odds(prob: float) -> float:
    return (1.0 / prob) if prob > 0 else 999.0


def implied_prob(odds: float) -> float:
    return (1.0 / odds) if odds > 1 else 0.0
