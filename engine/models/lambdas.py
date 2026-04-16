from __future__ import annotations

from engine.config import ModelConfig
from engine.features.form import weighted_form_multiplier
from engine.features.momentum import momentum_multiplier
from engine.features.team_strength import split_rates, shrink_strength


def compute_lambdas(
    home_row: dict,
    away_row: dict,
    home_form: list[str],
    away_form: list[str],
    league_avg_home: float,
    league_avg_away: float,
    cfg: ModelConfig,
) -> tuple[float, float, dict]:
    h = split_rates(home_row, league_avg_home, league_avg_away)
    a = split_rates(away_row, league_avg_away, league_avg_home)

    base_h_att = shrink_strength(h["att_home"], league_avg_home, cfg.shrinkage_weight)
    base_h_def = shrink_strength(h["def_home"], league_avg_away, cfg.shrinkage_weight)
    base_a_att = shrink_strength(a["att_away"], league_avg_away, cfg.shrinkage_weight)
    base_a_def = shrink_strength(a["def_away"], league_avg_home, cfg.shrinkage_weight)

    h_form_mult = weighted_form_multiplier(home_form, cfg.form_decay, cfg.form_cap)
    a_form_mult = weighted_form_multiplier(away_form, cfg.form_decay, cfg.form_cap)

    h_mom_att, h_mom_def = momentum_multiplier(base_h_att, base_h_def, h["att_home"], h["def_home"], cfg.momentum_cap)
    a_mom_att, a_mom_def = momentum_multiplier(base_a_att, base_a_def, a["att_away"], a["def_away"], cfg.momentum_cap)

    lambda_home = league_avg_home * (base_h_att / league_avg_home) * (base_a_def / league_avg_home)
    lambda_away = league_avg_away * (base_a_att / league_avg_away) * (base_h_def / league_avg_away)

    lambda_home *= cfg.home_advantage * h_form_mult * h_mom_att * a_mom_def
    lambda_away *= a_form_mult * a_mom_att * h_mom_def

    lambda_home = min(max(lambda_home, 0.15), 4.8)
    lambda_away = min(max(lambda_away, 0.15), 4.8)

    details = {
        "home_form_mult": h_form_mult,
        "away_form_mult": a_form_mult,
        "home_momentum_att": h_mom_att,
        "away_momentum_att": a_mom_att,
    }
    return lambda_home, lambda_away, details
