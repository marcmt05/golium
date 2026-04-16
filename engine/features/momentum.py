from __future__ import annotations

from .normalization import clamp


def momentum_multiplier(
    season_att: float,
    season_def: float,
    recent_att: float,
    recent_def: float,
    cap: float = 0.08,
) -> tuple[float, float]:
    """Momentum as delta between season baseline and recent performance."""
    att_delta = (recent_att / max(season_att, 0.05)) - 1.0
    def_delta = 1.0 - (recent_def / max(season_def, 0.05))
    return (1.0 + clamp(att_delta, -cap, cap), 1.0 + clamp(def_delta, -cap, cap))
