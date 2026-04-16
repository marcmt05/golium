from __future__ import annotations


def edge(model_prob: float, offered_odds: float | None) -> float | None:
    if not offered_odds or offered_odds <= 1:
        return None
    return model_prob - (1.0 / offered_odds)


def expected_value(model_prob: float, offered_odds: float | None) -> float | None:
    if not offered_odds or offered_odds <= 1:
        return None
    return model_prob * (offered_odds - 1.0) - (1.0 - model_prob)
