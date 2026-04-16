from __future__ import annotations

from engine.config import BettingConfig


def allow_pick(candidate: dict, cfg: BettingConfig) -> bool:
    if candidate.get("market") not in cfg.allowed_markets:
        return False
    if candidate.get("prob", 0.0) < cfg.min_prob:
        return False
    if candidate.get("edge", 0.0) < cfg.min_edge:
        return False
    odds = candidate.get("offered_odds", 0.0)
    if odds < cfg.min_odds or odds > cfg.max_odds:
        return False
    if candidate.get("incomplete_data"):
        return False
    return True
