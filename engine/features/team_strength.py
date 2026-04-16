from __future__ import annotations

from .normalization import clamp


def split_rates(team_row: dict, fallback_gf: float, fallback_ga: float) -> dict[str, float]:
    played = max(int(team_row.get("played") or 0), 1)
    home_n = max(played // 2, 1)
    away_n = max(played - home_n, 1)
    return {
        "att_home": (team_row.get("gfHome") or team_row.get("gf") or fallback_gf) / home_n,
        "def_home": (team_row.get("gaHome") or team_row.get("ga") or fallback_ga) / home_n,
        "att_away": (team_row.get("gfAway") or team_row.get("gf") or fallback_gf) / away_n,
        "def_away": (team_row.get("gaAway") or team_row.get("ga") or fallback_ga) / away_n,
    }


def shrink_strength(raw: float, baseline: float, weight: float) -> float:
    return clamp(raw * (1 - weight) + baseline * weight, baseline * 0.35, baseline * 2.4)
