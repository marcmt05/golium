from __future__ import annotations

import math
from .dixon_coles import tau


def poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def goal_matrix(lam: float, mu: float, max_goals: int, rho: float = 0.0, use_dc: bool = False) -> list[list[float]]:
    matrix: list[list[float]] = []
    for i in range(max_goals + 1):
        row = []
        for j in range(max_goals + 1):
            p = poisson_pmf(i, lam) * poisson_pmf(j, mu)
            if use_dc and i <= 1 and j <= 1:
                p *= tau(i, j, lam, mu, rho)
            row.append(max(p, 0.0))
        matrix.append(row)

    total = sum(sum(r) for r in matrix) or 1.0
    return [[v / total for v in r] for r in matrix]


def derive_markets(matrix: list[list[float]]) -> dict[str, float]:
    out = {
        "1": 0.0, "X": 0.0, "2": 0.0,
        "O2.5": 0.0, "U2.5": 0.0,
        "O3.5": 0.0, "U3.5": 0.0,
        "BTTS": 0.0,
        "AHH-0.5": 0.0, "AHA-0.5": 0.0,
    }
    for i, row in enumerate(matrix):
        for j, p in enumerate(row):
            if i > j:
                out["1"] += p
                out["AHH-0.5"] += p
            elif i == j:
                out["X"] += p
            else:
                out["2"] += p
                out["AHA-0.5"] += p
            if i + j > 2:
                out["O2.5"] += p
            else:
                out["U2.5"] += p
            if i + j > 3:
                out["O3.5"] += p
            else:
                out["U3.5"] += p
            if i > 0 and j > 0:
                out["BTTS"] += p
    return out
