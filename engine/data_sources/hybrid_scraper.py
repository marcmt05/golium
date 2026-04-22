"""Hybrid ESPN + SofaScore scraper for Golium."""
from __future__ import annotations

from typing import Any

from .espn_scraper import scrape_league as scrape_espn
from .shared import logger, normalize_team_name, save_json, utc_now_iso
from .sofascore_scraper import scrape_league as scrape_sofascore


def _event_key(row: dict[str, Any]) -> tuple[str, str, str]:
    home = normalize_team_name(((row.get("home_team") or {}).get("name")) or ((row.get("homeTeam") or {}).get("name")) or "")
    away = normalize_team_name(((row.get("away_team") or {}).get("name")) or ((row.get("awayTeam") or {}).get("name")) or "")
    date = str(row.get("date_only") or (str(row.get("date") or "")[:10]))
    return home, away, date


def _standing_key(row: dict[str, Any]) -> str:
    return normalize_team_name(row.get("team_name") or row.get("teamName") or "")


def _merge_standings(espn_rows: list[dict[str, Any]], sofa_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sofa_index = {_standing_key(row): row for row in sofa_rows}
    merged = []
    used = set()
    for row in espn_rows:
        key = _standing_key(row)
        sofa = sofa_index.get(key)
        used.add(key)
        if sofa:
            new_row = dict(row)
            new_row["raw_stats"] = sofa.get("raw_stats") or row.get("raw_stats") or {}
            new_row["form"] = sofa.get("form") or row.get("form")
            new_row["sofascore_rank"] = sofa.get("rank")
            new_row["sofascore_points"] = sofa.get("points")
            merged.append(new_row)
        else:
            merged.append(row)
    for row in sofa_rows:
        key = _standing_key(row)
        if key in used:
            continue
        merged.append(row)
    return merged


def _merge_events(espn_rows: list[dict[str, Any]], sofa_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sofa_index = {_event_key(row): row for row in sofa_rows}
    merged = []
    for row in espn_rows:
        key = _event_key(row)
        sofa = sofa_index.get(key)
        new_row = dict(row)
        if sofa:
            new_row["sofascore"] = sofa.get("sofascore")
            new_row["sofascore_event_id"] = sofa.get("event_id")
            new_row["round"] = sofa.get("round")
            new_row["winner_code"] = sofa.get("winner_code")
            if not new_row.get("venue"):
                new_row["venue"] = sofa.get("venue") or {}
            if sofa.get("referee"):
                new_row["referee"] = sofa.get("referee")
            if sofa.get("manager_home"):
                new_row["manager_home"] = sofa.get("manager_home")
            if sofa.get("manager_away"):
                new_row["manager_away"] = sofa.get("manager_away")
        merged.append(new_row)
    return merged


def scrape_league(
    league_key: str,
    *,
    output_dir: str | None = None,
    espn_output_dir: str | None = None,
    sofascore_output_dir: str | None = None,
) -> dict[str, Any]:
    espn = scrape_espn(league_key, output_dir=espn_output_dir)
    sofa = scrape_sofascore(league_key, output_dir=sofascore_output_dir)

    merged = {
        "league_key": league_key,
        "league_name": espn.get("league_name") or sofa.get("league_name"),
        "league_slug": espn.get("league_slug") or sofa.get("league_slug"),
        "source": "ESPN+SofaScore",
        "scraped_at": utc_now_iso(),
        "standings": _merge_standings(espn.get("standings") or [], sofa.get("standings") or []),
        "fixtures": _merge_events(espn.get("fixtures") or [], sofa.get("fixtures") or []),
        "recent_results": _merge_events(espn.get("recent_results") or [], sofa.get("recent_results") or []),
        "team_metrics": sofa.get("team_metrics") or {},
        "meta": {
            "espn": espn.get("meta") or {},
            "sofascore": {
                "season_id": sofa.get("season_id"),
                "season_year": sofa.get("season_year"),
                "tournament_id": sofa.get("tournament_id"),
                "current_round": sofa.get("current_round"),
                **(sofa.get("meta") or {}),
            },
        },
    }
    if output_dir:
        output_path = save_json(f"{output_dir}/{league_key}.json", merged)
        logger.info("Saved hybrid league=%s -> %s", league_key, output_path)
    return merged
