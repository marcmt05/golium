from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.betting.combinadas import build_conservative_combo
from engine.betting.filters import allow_pick
from engine.betting.kelly import fractional_kelly
from engine.betting.markets import fair_odds
from engine.betting.value import edge, expected_value
from engine.config import PipelineConfig
from engine.data_sources.espn import load_from_json
from engine.data_sources.odds import fetch_bookmaker_odds
from engine.exporter import export_public_data, write_json
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
    "BTTS_Y": "BTTS Sí",
    "BTTS_N": "BTTS No",
    "AH_HOME_-0.5": "AH Local -0.5",
    "AH_AWAY_-0.5": "AH Visitante -0.5",
}

ODDS_KEY_ALIASES = {
    "BTTS": "BTTS_Y",
    "AHH-0.5": "AH_HOME_-0.5",
    "AHA-0.5": "AH_AWAY_-0.5",
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


def _canonicalize_odds(raw_odds: dict[str, float]) -> dict[str, float]:
    canonical: dict[str, float] = {}
    for key, value in (raw_odds or {}).items():
        mapped = ODDS_KEY_ALIASES.get(key, key)
        canonical[mapped] = float(value)
    return canonical


def _build_pick(
    *,
    snapshot_id: str,
    generated_at: str,
    cfg: PipelineConfig,
    league_name: str,
    fixture: dict[str, Any],
    market_key: str,
    model_prob: float,
    offered_odds: float | None,
    offered_odds_is_real: bool,
    incomplete_data: bool,
    reason: str,
) -> dict[str, Any]:
    fair = fair_odds(model_prob)
    is_value_bet = offered_odds_is_real and offered_odds is not None

    pick = {
        "snapshot_id": snapshot_id,
        "generated_at": generated_at,
        "model_version": cfg.model_version,
        "fixture_id": str(fixture.get("id", "")),
        "league": league_name,
        "home_team": fixture.get("homeTeam", {}).get("name", "?"),
        "away_team": fixture.get("awayTeam", {}).get("name", "?"),
        "market": market_key,
        "market_label": MARKET_LABELS.get(market_key, market_key),
        "selection": market_key,
        "model_prob": model_prob,
        "fair_odds": fair,
        "offered_odds": offered_odds if is_value_bet else None,
        "offered_odds_is_real": offered_odds_is_real,
        "edge": None,
        "ev": None,
        "stake_fraction": 0.0,
        "pick_type": "value_bet" if is_value_bet else "model_pick",
        "status": "open",
        "result": None,
        "profit_units": 0.0,
        "incomplete_data": incomplete_data,
        "reason": reason,
    }

    if is_value_bet:
        assert offered_odds is not None
        pick["edge"] = edge(model_prob, offered_odds)
        pick["ev"] = expected_value(model_prob, offered_odds)
        pick["stake_fraction"] = fractional_kelly(
            model_prob,
            offered_odds,
            cfg.betting.kelly_fraction,
            cfg.betting.kelly_cap,
        )

    return pick


def process_league(
    league_key: str,
    league: dict[str, Any],
    cfg: PipelineConfig,
    snapshot_id: str,
    generated_at: str,
) -> tuple[dict, list[dict]]:
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

        odds_map = _canonicalize_odds(fetch_bookmaker_odds(str(fix.get("id", ""))))
        derived_markets = []
        fixture_model_candidates: list[dict[str, Any]] = []
        fixture_has_real_odds = False
        for m_key, prob in probs.items():
            fair = fair_odds(prob)
            offered_real = odds_map.get(m_key)
            pick = _build_pick(
                snapshot_id=snapshot_id,
                generated_at=generated_at,
                cfg=cfg,
                league_name=league.get("league", league_key),
                fixture=fix,
                market_key=m_key,
                model_prob=prob,
                offered_odds=offered_real,
                offered_odds_is_real=m_key in odds_map,
                incomplete_data=not bool(h) or not bool(a),
                reason=f"λH={lam_h:.2f}, λA={lam_a:.2f}, formH={details['home_form_mult']:.3f}, formA={details['away_form_mult']:.3f}",
            )

            if pick["pick_type"] == "value_bet":
                fixture_has_real_odds = True
                candidate = {
                    "market": pick["market"],
                    "prob": pick["model_prob"],
                    "edge": pick["edge"] or 0.0,
                    "offered_odds": pick["offered_odds"] or 0.0,
                    "incomplete_data": pick["incomplete_data"],
                }
                if allow_pick(candidate, cfg.betting):
                    picks.append(pick)
            else:
                if pick["market"] in cfg.betting.allowed_markets:
                    fixture_model_candidates.append(pick)

            derived_markets.append(
                {
                    "key": m_key,
                    "prob": round(prob, 5),
                    "fair_odds": round(fair, 3),
                    "offered_odds": round(offered_real, 3) if offered_real is not None else None,
                    "offered_odds_is_real": m_key in odds_map,
                }
            )

        if not fixture_has_real_odds and fixture_model_candidates:
            best_model_pick = max(fixture_model_candidates, key=lambda p: p["model_prob"])
            picks.append(best_model_pick)

        fix["model"] = {
            "lambda_home": round(lam_h, 4),
            "lambda_away": round(lam_a, 4),
            "probs": {k: round(v * 100, 2) for k, v in probs.items()},
            "markets": derived_markets,
        }

    return league, picks


def _snapshot_dir(base_dir: Path, snapshot_id: str) -> Path:
    return base_dir / "history" / "snapshots" / snapshot_id


def _build_ledger(picks: list[dict], snapshot_id: str, generated_at: str, model_version: str) -> dict[str, Any]:
    settled = [p for p in picks if p.get("status") == "settled"]
    total_stake = sum(float(p.get("stake_fraction") or 0.0) for p in settled)
    total_profit = sum(float(p.get("profit_units") or 0.0) for p in settled)
    return {
        "snapshot_id": snapshot_id,
        "generated_at": generated_at,
        "model_version": model_version,
        "total_picks": len(picks),
        "settled_picks": len(settled),
        "total_stake_units": total_stake,
        "total_profit_units": total_profit,
        "roi": (total_profit / total_stake) if total_stake > 0 else 0.0,
    }


def run_pipeline(cfg: PipelineConfig) -> dict[str, Any]:
    payload = load_from_json(cfg.input_file)
    leagues = payload.get("leagues") if isinstance(payload, dict) and "leagues" in payload else {payload.get("leagueKey", "liga"): payload}

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    snapshot_id = generated_at.replace("+00:00", "Z").replace(":", "-")

    out_leagues: dict[str, Any] = {}
    all_picks: list[dict] = []
    for league_key, league_data in leagues.items():
        enriched, picks = process_league(league_key, league_data, cfg, snapshot_id, generated_at)
        out_leagues[league_key] = enriched
        all_picks.extend(picks)

    combo = build_conservative_combo(all_picks)
    metrics = backtest_snapshot(all_picks)
    metrics["combo"] = combo

    real_odds_detected = any(p.get("offered_odds_is_real") for p in all_picks)
    model_info = {
        "snapshot_id": snapshot_id,
        "model_version": cfg.model_version,
        "generated_at": generated_at,
        "sources": ["espn", "understat(fallback)", "fbref(fallback)", "odds(optional)"] ,
        "pick_mode": "value_bets_enabled" if real_odds_detected else "model_pick_only",
        "notes": "Cuando no hay cuotas reales, los picks se publican como model_pick y no como value_bet.",
        "flags": {
            "dixon_coles": cfg.model.use_dixon_coles,
            "real_odds": real_odds_detected,
        },
        "market_taxonomy": list(MARKET_LABELS.keys()),
    }

    export_data = {"leagues": out_leagues}
    export_public_data(cfg.output_dir, export_data, all_picks, metrics, model_info)

    snap_dir = _snapshot_dir(Path("."), snapshot_id)
    write_json(snap_dir / "data.json", export_data)
    write_json(snap_dir / "picks.json", {"snapshot_id": snapshot_id, "generated_at": generated_at, "picks": all_picks})
    write_json(snap_dir / "metrics.json", metrics)
    write_json(snap_dir / "model-info.json", model_info)
    write_json(snap_dir / "ledger.json", _build_ledger(all_picks, snapshot_id, generated_at, cfg.model_version))

    return {
        "snapshot_id": snapshot_id,
        "data": export_data,
        "picks": all_picks,
        "metrics": metrics,
        "model_info": model_info,
    }
