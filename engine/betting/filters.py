from __future__ import annotations

from engine.config import BettingConfig


def allow_model_pick(candidate: dict, cfg: BettingConfig) -> bool:
    if candidate.get("market") not in cfg.allowed_markets:
        return False
    if candidate.get("model_prob", 0.0) < cfg.min_model_prob:
        return False
    if candidate.get("prob_gap", 0.0) < cfg.min_model_gap:
        return False
    if candidate.get("incomplete_data"):
        return False
    return True


def allow_value_bet(candidate: dict, cfg: BettingConfig) -> bool:
    odds = candidate.get("offered_odds")
    if not odds:
        return False
    if odds < cfg.min_odds or odds > cfg.max_odds:
        return False
    if candidate.get("edge") is None or candidate.get("edge") < cfg.min_value_edge:
        return False
    if candidate.get("incomplete_data"):
        return False
    return True
