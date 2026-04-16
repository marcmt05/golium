from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from engine.betting.combinadas import build_conservative_combo
from engine.betting.filters import allow_model_pick, allow_value_bet
from engine.betting.kelly import fractional_kelly
from engine.betting.markets import fair_odds
from engine.betting.value import edge, expected_value
from engine.config import PipelineConfig
from engine.data_sources.espn import load_from_json
from engine.data_sources.odds import fetch_bookmaker_odds
from engine.exporter import export_public_data, export_snapshot, snapshot_id_now
from engine.markets import MARKET_LABELS
from engine.models.lambdas import compute_lambdas
from engine.models.poisson import derive_markets, goal_matrix
from engine.validation.backtest import backtest_snapshot


FINAL_STATUSES = {"STATUS_FINAL", "STATUS_FULL_TIME", "FINAL", "FULL_TIME", "FULL"}


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


def _prob_gap(market: str, probs: dict[str, float]) -> float:
    p = probs.get(market, 0.0)
    if market == "1":
        return p - max(probs.get("X", 0.0), probs.get("2", 0.0))
    if market == "X":
        return p - max(probs.get("1", 0.0), probs.get("2", 0.0))
    if market == "2":
        return p - max(probs.get("1", 0.0), probs.get("X", 0.0))
    opposite = {
        "O2.5": "U2.5",
        "U2.5": "O2.5",
        "O3.5": "U3.5",
        "U3.5": "O3.5",
        "BTTS_Y": "BTTS_N",
        "BTTS_N": "BTTS_Y",
        "AH_HOME_-0.5": "AH_AWAY_-0.5",
        "AH_AWAY_-0.5": "AH_HOME_-0.5",
    }
    return p - probs.get(opposite.get(market, ""), 0.0)


def process_league(
    league_key: str,
    league: dict[str, Any],
    cfg: PipelineConfig,
    snapshot_id: str,
    generated_at: str,
) -> tuple[dict, list[dict], list[dict]]:
    standings = league.get("standings", [])
    form_by_id = _form_map(league.get("teamForm", {}))
    lookup = _build_lookup(standings)
    lg_h, lg_a = _league_averages(standings)
    picks: list[dict] = []
    ledger: list[dict] = []

    for fix in league.get("fixtures", []):
        home = fix.get("homeTeam", {})
        away = fix.get("awayTeam", {})
        h = lookup.get(str(home.get("id", "")), {})
        a = lookup.get(str(away.get("id", "")), {})
        h_form = form_by_id.get(str(home.get("id", "")), [])
        a_form = form_by_id.get(str(away.get("id", "")), [])

        lam_h, lam_a, details = compute_lambdas(h, a, h_form, a_form, lg_h, lg_a, cfg.model)
        mat = goal_matrix(lam_h, lam_a, cfg.model.max_goals, cfg.model.dc_rho, cfg.model.use_dixon_coles)
        probs = derive_markets(mat)

        odds_map = fetch_bookmaker_odds(str(fix.get("id", "")))
        derived_markets: list[dict[str, Any]] = []

        for m_key, prob in probs.items():
            fair = fair_odds(prob)
            raw_offered = odds_map.get(m_key)
            offered = float(raw_offered) if raw_offered not in (None, "") else None
            edge_value = edge(prob, offered)
            ev_value = expected_value(prob, offered)
            prob_gap = _prob_gap(m_key, probs)
            pick_type = "value_bet" if offered is not None else "model_pick"

            candidate = {
                "snapshot_id": snapshot_id,
                "generated_at": generated_at,
                "model_version": cfg.model_version,
                "fixture_id": str(fix.get("id", "")),
                "league": league.get("league", league_key),
                "home_team": home.get("name", "?"),
                "away_team": away.get("name", "?"),
                "market": m_key,
                "selection": MARKET_LABELS.get(m_key, m_key),
                "model_prob": prob,
                "prob_gap": prob_gap,
                "fair_odds": fair,
                "offered_odds": offered,
                "offered_odds_is_real": offered is not None,
                "edge": edge_value,
                "ev": ev_value,
                "stake_fraction": fractional_kelly(prob, offered, cfg.betting.kelly_fraction, cfg.betting.kelly_cap),
                "pick_type": pick_type,
                "status": "open",
                "result": None,
                "profit_units": 0.0,
                "date": fix.get("date"),
                "incomplete_data": not bool(h) or not bool(a),
                "reason": f"λH={lam_h:.2f}, λA={lam_a:.2f}, formH={details['home_form_mult']:.3f}, formA={details['away_form_mult']:.3f}",
            }

            should_keep = allow_value_bet(candidate, cfg.betting) if offered is not None else allow_model_pick(candidate, cfg.betting)
            if should_keep:
                picks.append(candidate)
                ledger.append(dict(candidate))

            derived_markets.append(
                {
                    "key": m_key,
                    "label": MARKET_LABELS.get(m_key, m_key),
                    "prob": round(prob, 5),
                    "fair_odds": round(fair, 3),
                    "offered_odds": round(offered, 3) if offered is not None else None,
                    "offered_odds_is_real": offered is not None,
                    "pick_type": pick_type,
                }
            )

        fix["model"] = {
            "lambda_home": round(lam_h, 4),
            "lambda_away": round(lam_a, 4),
            "probs": {k: round(v * 100, 2) for k, v in probs.items()},
            "markets": derived_markets,
        }

    return league, picks, ledger


def run_pipeline(cfg: PipelineConfig) -> dict[str, Any]:
    payload = load_from_json(cfg.input_file)
    leagues = payload.get("leagues") if isinstance(payload, dict) and "leagues" in payload else {payload.get("leagueKey", "liga"): payload}
    snapshot_id = snapshot_id_now()
    generated_at = datetime.now(timezone.utc).isoformat()

    out_leagues: dict[str, Any] = {}
    all_picks: list[dict] = []
    full_ledger: list[dict] = []
    for league_key, league_data in leagues.items():
        enriched, picks, ledger = process_league(league_key, league_data, cfg, snapshot_id, generated_at)
        out_leagues[league_key] = enriched
        all_picks.extend(picks)
        full_ledger.extend(ledger)

    combo = build_conservative_combo([p for p in all_picks if p["pick_type"] == "value_bet"], max_legs=3)
    metrics = backtest_snapshot(all_picks)
    metrics["combo"] = combo

    real_odds_count = sum(1 for p in all_picks if p.get("offered_odds_is_real"))
    model_info = {
        "snapshot_id": snapshot_id,
        "model_version": cfg.model_version,
        "generated_at": generated_at,
        "sources": ["espn", "understat(fallback)", "fbref(fallback)", "odds(optional)"],
        "flags": {
            "dixon_coles": cfg.model.use_dixon_coles,
            "has_real_odds": real_odds_count > 0,
            "frontend_render_only": True,
        },
        "pick_summary": {
            "total": len(all_picks),
            "value_bets": sum(1 for p in all_picks if p["pick_type"] == "value_bet"),
            "model_picks": sum(1 for p in all_picks if p["pick_type"] == "model_pick"),
            "real_odds_count": real_odds_count,
        },
        "odds_note": "When odds are unavailable, picks are flagged as model_pick and offered_odds remains null.",
    }

    export_data = {"leagues": out_leagues}
    export_public_data(cfg.output_dir, export_data, all_picks, metrics, model_info)
    snapshot_path = export_snapshot(cfg.history_dir, snapshot_id, export_data, all_picks, metrics, model_info, full_ledger)

    return {
        "data": export_data,
        "picks": all_picks,
        "metrics": metrics,
        "model_info": model_info,
        "snapshot_path": str(snapshot_path),
    }
