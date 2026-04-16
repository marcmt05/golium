from __future__ import annotations

MARKETS: tuple[str, ...] = (
    "1",
    "X",
    "2",
    "O2.5",
    "U2.5",
    "O3.5",
    "U3.5",
    "BTTS_Y",
    "BTTS_N",
    "AH_HOME_-0.5",
    "AH_AWAY_-0.5",
)

MARKET_LABELS: dict[str, str] = {
    "1": "Victoria local",
    "X": "Empate",
    "2": "Victoria visitante",
    "O2.5": "Over 2.5",
    "U2.5": "Under 2.5",
    "O3.5": "Over 3.5",
    "U3.5": "Under 3.5",
    "BTTS_Y": "Ambos marcan: Sí",
    "BTTS_N": "Ambos marcan: No",
    "AH_HOME_-0.5": "AH Local -0.5",
    "AH_AWAY_-0.5": "AH Visitante -0.5",
}


def market_outcome(market: str, home_goals: int, away_goals: int) -> str:
    total = home_goals + away_goals
    if market == "1":
        return "win" if home_goals > away_goals else "loss"
    if market == "X":
        return "win" if home_goals == away_goals else "loss"
    if market == "2":
        return "win" if away_goals > home_goals else "loss"
    if market == "O2.5":
        return "win" if total > 2 else "loss"
    if market == "U2.5":
        return "win" if total < 3 else "loss"
    if market == "O3.5":
        return "win" if total > 3 else "loss"
    if market == "U3.5":
        return "win" if total < 4 else "loss"
    if market == "BTTS_Y":
        return "win" if home_goals > 0 and away_goals > 0 else "loss"
    if market == "BTTS_N":
        return "win" if home_goals == 0 or away_goals == 0 else "loss"
    if market == "AH_HOME_-0.5":
        return "win" if home_goals > away_goals else "loss"
    if market == "AH_AWAY_-0.5":
        return "win" if away_goals > home_goals else "loss"
    return "void"
