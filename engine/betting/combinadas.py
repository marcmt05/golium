from __future__ import annotations


def build_conservative_combo(picks: list[dict], max_legs: int = 3) -> dict:
    chosen: list[dict] = []
    used_matches: set[str] = set()
    for pick in sorted(picks, key=lambda x: x.get("edge", 0.0) or 0.0, reverse=True):
        fid = str(pick.get("fixture_id"))
        if fid in used_matches:
            continue
        if len(chosen) >= max_legs:
            break
        if not pick.get("offered_odds"):
            continue
        chosen.append(pick)
        used_matches.add(fid)

    if len(chosen) < 2:
        return {"legs": [], "combined_odds": 0.0, "combined_prob": 0.0}

    odds = 1.0
    prob = 1.0
    for leg in chosen:
        odds *= float(leg["offered_odds"])
        prob *= float(leg["model_prob"])
    return {"legs": chosen, "combined_odds": round(odds, 3), "combined_prob": round(prob, 4)}
