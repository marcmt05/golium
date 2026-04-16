from __future__ import annotations

from .normalization import clamp


def weighted_form_multiplier(form: list[str], decay: float = 0.72, cap: float = 0.12) -> float:
    """Deterministic weighted form over last results (newest first)."""
    if not form:
        return 1.0
    points = {"W": 3.0, "D": 1.0, "L": 0.0}
    ws = []
    vals = []
    for i, r in enumerate(reversed(form[-6:])):
        w = decay**i
        ws.append(w)
        vals.append(points.get(r, 0.0) * w)
    max_score = sum(3.0 * w for w in ws)
    norm = (sum(vals) / max_score) if max_score else 0.5
    centered = (norm - 0.5) * 2.0
    return 1.0 + clamp(centered * cap, -cap, cap)
