from __future__ import annotations


def fractional_kelly(prob: float, odds: float | None, fraction: float = 0.25, cap: float = 0.03) -> float:
    if not odds or odds <= 1:
        return 0.0
    b = odds - 1.0
    full = ((b * prob) - (1 - prob)) / b
    return max(0.0, min(full * fraction, cap))
