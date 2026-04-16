from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from engine.betting.combinadas import build_conservative_combo
from engine.betting.filters import allow_pick
from engine.betting.kelly import fractional_kelly
from engine.betting.markets import fair_odds
from engine.betting.value import edge, expected_value
from engine.config import PipelineConfig
from engine.data_sources.espn import load_from_json
from engine.data_sources.odds import fetch_bookmaker_odds
from engine.exporter import export_public_data
from engine.models.lambdas import compute_lambdas
from engine.models.poisson import derive_markets, goal_matrix
from engine.validation.backtest import backtest_snapshot


MARKET_LABELS = {
    "1": "Victoria local",
    "X": "Empate",
    "2": "Victoria visitante",
    "O2.5": "Over 2.5",
    "U2.5": "Under 2.5",
    "O3.5": "Over 3.5",
    "U3.5": "Under 3.5",
    "BTTS": "Ambos marcan",
    "AHH-0.5": "AH Local -0.5",
    "AHA-0.5": "AH Visitante -0.5",
}


def _league_averages(rows: list[dict[str, Any]]) -> tuple[float, float]:
    if not rows:
        return 1.4, 1.1
    games = (sum(float(r.get("played", 0)) for r in rows) / 2) or 1.0
    goals = (sum(float(r.get("gf", 0)) for r in rows) / 2) or games * 2.5
    avg = goals / games
    return max(0.8, min(2.2, avg * 1.1)), max(0.6, min(1.8, avg * 0.9))


def _form_map(team_form: dict[str, list[Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for team_id, rows in (team_form or {}).items():
        parsed: list[str] = []
        for row in rows or []:
            parsed.append(row.get("r", "D") if isinstance(row, dict) else str(row))
        out[str(team_id)] = parsed
    return out


def _build_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        out[str(r.get("teamId", ""))] = r
        out[str(r.get("teamName", ""))] = r
    return out


def process_league(league_key: str, league: dict[str, Any], cfg: PipelineConfig) -> tuple[dict, list[dict]]:
    standings = league.get("standings", [])
    form_by_id = _form_map(league.get("teamForm", {}))
    lookup = _build_lookup(standings)
    lg_h, lg_a = _league_averages(standings)
    picks: list[dict] = []

    for fix in league.get("fixtures", []):
        h = lookup.get(str(fix.get("homeTeam", {}).get("id", "")), {})
        a = lookup.get(str(fix.get("awayTeam", {}).get("id", "")), {})
        h_form = form_by_id.get(str(fix.get("homeTeam", {}).get("id", "")), [])
        a_form = form_by_id.get(str(fix.get("awayTeam", {}).get("id", "")), [])

        lam_h, lam_a, details = compute_lambdas(h, a, h_form, a_form, lg_h, lg_a, cfg.model)
        mat = goal_matrix(lam_h, lam_a, cfg.model.max_goals, cfg.model.dc_rho, cfg.model.use_dixon_coles)
        probs = derive_markets(mat)

        odds_map = fetch_bookmaker_odds(str(fix.get("id", "")))
        derived_markets = []
        for m_key, prob in probs.items():
            fair = fair_odds(prob)
            offered = float(odds_map.get(m_key, fair * (1 + cfg.betting.bookmaker_margin)))
            pick = {
                "date": fix.get("date"),
                "league": league.get("league", league_key),
                "fixture": f"{fix.get('homeTeam', {}).get('name', '?')} vs {fix.get('awayTeam', {}).get('name', '?')}",
                "fixture_id": str(fix.get("id", "")),
                "market": m_key,
                "market_label": MARKET_LABELS.get(m_key, m_key),
                "prob": prob,
                "fair_odds": fair,
                "offered_odds": offered,
                "closing_odds": None,
                "edge": edge(prob, offered),
                "ev": expected_value(prob, offered),
                "stake": fractional_kelly(prob, offered, cfg.betting.kelly_fraction, cfg.betting.kelly_cap),
                "result": None,
                "profit": 0.0,
                "model_version": cfg.model_version,
                "incomplete_data": not bool(h) or not bool(a),
                "reason": f"λH={lam_h:.2f}, λA={lam_a:.2f}, formH={details['home_form_mult']:.3f}, formA={details['away_form_mult']:.3f}",
                "is_real_odds": m_key in odds_map,
            }
            derived_markets.append({
                "key": m_key,
                "prob": round(prob, 5),
                "fair_odds": round(fair, 3),
                "offered_odds": round(offered, 3),
            })
            if allow_pick(pick, cfg.betting):
                picks.append(pick)

        fix["model"] = {
            "lambda_home": round(lam_h, 4),
            "lambda_away": round(lam_a, 4),
            "probs": {k: round(v * 100, 2) for k, v in probs.items()},
            "markets": derived_markets,
        }

    return league, picks


def run_pipeline(cfg: PipelineConfig) -> dict[str, Any]:
    payload = load_from_json(cfg.input_file)
    leagues = payload.get("leagues") if isinstance(payload, dict) and "leagues" in payload else {payload.get("leagueKey", "liga"): payload}

    out_leagues: dict[str, Any] = {}
    all_picks: list[dict] = []
    for league_key, league_data in leagues.items():
        enriched, picks = process_league(league_key, league_data, cfg)
        out_leagues[league_key] = enriched
        all_picks.extend(picks)

    combo = build_conservative_combo(all_picks)
    metrics = backtest_snapshot(all_picks)
    metrics["combo"] = combo

    model_info = {
        "model_version": cfg.model_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": ["espn", "understat(fallback)", "fbref(fallback)", "odds(fallback)"],
        "flags": {
            "dixon_coles": cfg.model.use_dixon_coles,
            "real_odds": any(p.get("is_real_odds") for p in all_picks),
        },
    }

    export_data = {"leagues": out_leagues}
    export_public_data(cfg.output_dir, export_data, all_picks, metrics, model_info)
    return {"data": export_data, "picks": all_picks, "metrics": metrics, "model_info": model_info}
