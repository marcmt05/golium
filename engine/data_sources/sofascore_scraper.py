"""Direct SofaScore scraper using public JSON endpoints.

No browser automation required. This is intentionally defensive and designed
to enrich Golium without depending on fragile HTML parsing.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from curl_cffi import requests

from .shared import logger, normalize_team_name, save_json, utc_now_iso

SOFASCORE_BASE = "https://www.sofascore.com/api/v1"

SOFASCORE_TOURNAMENTS: dict[str, dict[str, Any]] = {
    "laliga": {"id": 8, "slug": "laliga", "name": "LaLiga"},
    "hypermotion": {"id": 54, "slug": "laliga-2", "name": "LaLiga 2"},
    "epl": {"id": 17, "slug": "premier-league", "name": "Premier League"},
    "bundesliga": {"id": 35, "slug": "bundesliga", "name": "Bundesliga"},
    "seriea": {"id": 23, "slug": "serie-a", "name": "Serie A"},
}

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
}


def fetch_json(url: str, *, retries: int = 3, timeout: int = 30) -> dict[str, Any]:
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(
                url,
                headers=DEFAULT_HEADERS,
                impersonate="chrome",
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            error_text = str(exc)

            if "404" in error_text:
                raise RuntimeError(f"HTTP 404 for {url}")

            logger.warning(
                "SofaScore fetch attempt %s/%s failed for %s: %s",
                attempt,
                retries,
                url,
                exc,
            )

    raise RuntimeError(f"Failed to fetch JSON from {url}: {last_error}")

def _iso_from_timestamp(value: Any) -> str | None:
    try:
        return (
            datetime.fromtimestamp(int(value), tz=UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
    except Exception:
        return None

def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def _status_payload(status: dict[str, Any] | None) -> dict[str, Any]:
    status = status or {}
    status_type = (status.get("type") or "").lower()
    completed = status_type in {"finished", "afterextra", "afterpenalties"}
    return {
        "state": status_type,
        "completed": completed,
        "description": status.get("description"),
        "code": status.get("code"),
    }


def _strip_event_statistics(statistics: dict[str, Any] | None) -> dict[str, Any] | None:
    if not statistics:
        return None

    periods = statistics.get("statistics") or []
    by_period: dict[str, dict[str, dict[str, Any]]] = {}

    for period in periods:
        period_name = period.get("period") or "ALL"
        groups = period.get("groups") or []
        flat: dict[str, dict[str, Any]] = {}

        for group in groups:
            for item in group.get("statisticsItems") or []:
                key = item.get("key") or item.get("name")
                if not key:
                    continue

                flat[str(key)] = {
                    "name": item.get("name"),
                    "group": group.get("groupName"),
                    "home": item.get("homeValue", item.get("home")),
                    "away": item.get("awayValue", item.get("away")),
                    "home_total": item.get("homeTotal"),
                    "away_total": item.get("awayTotal"),
                }

        by_period[str(period_name)] = flat

    return by_period


def _extract_lineup_summary(lineups: dict[str, Any] | None) -> dict[str, Any] | None:
    if not lineups:
        return None

    out: dict[str, Any] = {}

    for side in ("home", "away"):
        team = lineups.get(side) or {}
        players = team.get("players") or []
        starters = []
        bench = []

        for p in players:
            player = p.get("player") or {}
            statistics = p.get("statistics") or {}

            row = {
                "id": player.get("id"),
                "name": player.get("name"),
                "position": p.get("position"),
                "shirt_number": p.get("shirtNumber") or p.get("jerseyNumber"),
                "substitute": bool(p.get("substitute")),
                "captain": bool(p.get("captain")),
                "rating": statistics.get("rating"),
                "minutes_played": statistics.get("minutesPlayed"),
            }

            (bench if row["substitute"] else starters).append(row)

        out[side] = {
            "formation": team.get("formation"),
            "missing_players": team.get("missingPlayers") or [],
            "starters": starters,
            "bench": bench,
        }

    return out


def _summarize_incidents(incidents: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    if not incidents:
        return None

    summary = {
        "home_goals": 0,
        "away_goals": 0,
        "home_red_cards": 0,
        "away_red_cards": 0,
        "home_yellow_cards": 0,
        "away_yellow_cards": 0,
        "penalties": 0,
        "own_goals": 0,
        "timeline": [],
    }

    for inc in incidents:
        kind = (inc.get("incidentType") or inc.get("type") or "").lower()
        team_side = inc.get("teamSide")
        minute = inc.get("time") or inc.get("minute") or inc.get("addedTime")

        entry = {
            "type": kind,
            "team_side": team_side,
            "minute": minute,
            "player": ((inc.get("player") or {}).get("name")),
            "reason": inc.get("reason"),
        }
        summary["timeline"].append(entry)

        if "goal" in kind:
            if inc.get("isOwnGoal"):
                summary["own_goals"] += 1
            if team_side == "home":
                summary["home_goals"] += 1
            elif team_side == "away":
                summary["away_goals"] += 1
            if inc.get("isPenalty"):
                summary["penalties"] += 1

        elif "red" in kind:
            if team_side == "home":
                summary["home_red_cards"] += 1
            elif team_side == "away":
                summary["away_red_cards"] += 1

        elif "yellow" in kind:
            if team_side == "home":
                summary["home_yellow_cards"] += 1
            elif team_side == "away":
                summary["away_yellow_cards"] += 1

    return summary


def get_league_config(league_key: str) -> dict[str, Any]:
    try:
        return SOFASCORE_TOURNAMENTS[league_key]
    except KeyError as exc:
        raise ValueError(f"Unsupported SofaScore league: {league_key}") from exc


def resolve_season(league_key: str, season_year: str | None = None) -> dict[str, Any]:
    league = get_league_config(league_key)
    payload = fetch_json(f"{SOFASCORE_BASE}/unique-tournament/{league['id']}/seasons")
    seasons = payload.get("seasons") or []

    if not seasons:
        raise RuntimeError(f"No SofaScore seasons found for {league_key}")

    if season_year:
        season_year = season_year.strip()
        for season in seasons:
            if str(season.get("year") or "").strip() == season_year:
                return season

    return seasons[0]


def fetch_standings(league_key: str, season_id: int) -> dict[str, Any]:
    league = get_league_config(league_key)
    out: dict[str, Any] = {}

    for section in ("total", "home", "away"):
        payload = fetch_json(
            f"{SOFASCORE_BASE}/unique-tournament/{league['id']}/season/{season_id}/standings/{section}"
        )
        standings = payload.get("standings") or []
        out[section] = standings[0] if standings else {"rows": []}

    return out


def fetch_rounds(league_key: str, season_id: int) -> dict[str, Any]:
    league = get_league_config(league_key)
    return fetch_json(
        f"{SOFASCORE_BASE}/unique-tournament/{league['id']}/season/{season_id}/rounds"
    )


def fetch_events_by_round(league_key: str, season_id: int, round_number: int) -> list[dict[str, Any]]:
    league = get_league_config(league_key)
    payload = fetch_json(
        f"{SOFASCORE_BASE}/unique-tournament/{league['id']}/season/{season_id}/events/round/{round_number}"
    )
    return payload.get("events") or []


def fetch_event_details(event_id: int | str) -> dict[str, Any] | None:
    try:
        return fetch_json(f"{SOFASCORE_BASE}/event/{event_id}")
    except Exception as exc:
        logger.warning("SofaScore event details failed event=%s error=%s", event_id, exc)
        return None


def fetch_event_statistics(event_id: int | str) -> dict[str, Any] | None:
    try:
        return fetch_json(f"{SOFASCORE_BASE}/event/{event_id}/statistics")
    except Exception as exc:
        if "404" not in str(exc):
            logger.warning("SofaScore event statistics failed event=%s error=%s", event_id, exc)
        return None


def fetch_event_lineups(event_id: int | str) -> dict[str, Any] | None:
    try:
        return fetch_json(f"{SOFASCORE_BASE}/event/{event_id}/lineups")
    except Exception as exc:
        logger.warning("SofaScore event lineups failed event=%s error=%s", event_id, exc)
        return None


def fetch_event_incidents(event_id: int | str) -> list[dict[str, Any]] | None:
    try:
        payload = fetch_json(f"{SOFASCORE_BASE}/event/{event_id}/incidents")
        return payload.get("incidents") or []
    except Exception as exc:
        logger.warning("SofaScore event incidents failed event=%s error=%s", event_id, exc)
        return None


def _standing_row(
    total_row: dict[str, Any],
    home_row: dict[str, Any] | None,
    away_row: dict[str, Any] | None,
) -> dict[str, Any]:
    team = total_row.get("team") or {}

    return {
        "team_id": str(team.get("id") or ""),
        "team_name": team.get("name") or "",
        "team_short_name": team.get("shortName") or team.get("name") or "",
        "rank": total_row.get("position"),
        "played": total_row.get("matches"),
        "wins": total_row.get("wins"),
        "draws": total_row.get("draws"),
        "losses": total_row.get("losses"),
        "goals_for": total_row.get("scoresFor"),
        "goals_against": total_row.get("scoresAgainst"),
        "points": total_row.get("points"),
        "form": total_row.get("form"),
        "raw_stats": {
            "homeGoalsFor": (home_row or {}).get("scoresFor"),
            "homeGoalsAgainst": (home_row or {}).get("scoresAgainst"),
            "awayGoalsFor": (away_row or {}).get("scoresFor"),
            "awayGoalsAgainst": (away_row or {}).get("scoresAgainst"),
            "homeWins": (home_row or {}).get("wins"),
            "awayWins": (away_row or {}).get("wins"),
            "homeDraws": (home_row or {}).get("draws"),
            "awayDraws": (away_row or {}).get("draws"),
            "homeLosses": (home_row or {}).get("losses"),
            "awayLosses": (away_row or {}).get("losses"),
        },
    }


def build_standings_payload(standings: dict[str, Any]) -> list[dict[str, Any]]:
    total_rows = (standings.get("total") or {}).get("rows") or []
    home_rows = {
        (row.get("team") or {}).get("id"): row
        for row in ((standings.get("home") or {}).get("rows") or [])
    }
    away_rows = {
        (row.get("team") or {}).get("id"): row
        for row in ((standings.get("away") or {}).get("rows") or [])
    }

    output = []
    for row in total_rows:
        team_id = (row.get("team") or {}).get("id")
        output.append(_standing_row(row, home_rows.get(team_id), away_rows.get(team_id)))

    return output


def _parse_event(event: dict[str, Any]) -> dict[str, Any]:
    round_number = (event.get("roundInfo") or {}).get("round")

    return {
        "event_id": str(event.get("id") or ""),
        "date": _iso_from_timestamp(event.get("startTimestamp")),
        "date_only": (_iso_from_timestamp(event.get("startTimestamp")) or "").split("T")[0] or None,
        "name": event.get("slug"),
        "short_name": event.get("slug"),
        "status": _status_payload(event.get("status")),
        "season_year": ((event.get("season") or {}).get("year")),
        "round": round_number,
        "matchday": round_number,
        "winner_code": event.get("winnerCode"),
        "home_team": {
            "id": str((event.get("homeTeam") or {}).get("id") or ""),
            "name": (event.get("homeTeam") or {}).get("name") or "",
            "normalized_name": normalize_team_name((event.get("homeTeam") or {}).get("name") or ""),
            "score": (event.get("homeScore") or {}).get("current"),
            "form": (event.get("homeTeam") or {}).get("form"),
        },
        "away_team": {
            "id": str((event.get("awayTeam") or {}).get("id") or ""),
            "name": (event.get("awayTeam") or {}).get("name") or "",
            "normalized_name": normalize_team_name((event.get("awayTeam") or {}).get("name") or ""),
            "score": (event.get("awayScore") or {}).get("current"),
            "form": (event.get("awayTeam") or {}).get("form"),
        },
        "venue": {},
        "flags": {
            "has_xg": event.get("hasXg"),
            "has_event_player_statistics": event.get("hasEventPlayerStatistics"),
            "has_event_player_heatmap": event.get("hasEventPlayerHeatMap"),
        },
        "sofascore": {
            "statistics": None,
            "lineups": None,
            "incidents_summary": None,
        },
    }


def _attach_detail(
    parsed: dict[str, Any],
    detail: dict[str, Any] | None,
    stats: dict[str, Any] | None,
    lineups: dict[str, Any] | None,
    incidents: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    event = (detail or {}).get("event") or {}

    if event:
        parsed["venue"] = {
            "name": ((event.get("venue") or {}).get("name")),
            "city": (((event.get("venue") or {}).get("city") or {}).get("name")),
            "country": (((event.get("venue") or {}).get("country") or {}).get("name")),
        }
        parsed["referee"] = event.get("referee")
        parsed["manager_home"] = ((event.get("homeTeam") or {}).get("manager") or {}).get("name")
        parsed["manager_away"] = ((event.get("awayTeam") or {}).get("manager") or {}).get("name")

    parsed["sofascore"] = {
        "statistics": _strip_event_statistics(stats),
        "lineups": _extract_lineup_summary(lineups),
        "incidents_summary": _summarize_incidents(incidents),
    }
    return parsed


def build_team_metrics(recent_results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    sums: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "matches": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_for": 0,
            "goals_against": 0,
            "xg_for": 0.0,
            "xg_against": 0.0,
            "shots_for": 0.0,
            "shots_against": 0.0,
            "shots_on_target_for": 0.0,
            "shots_on_target_against": 0.0,
            "corners_for": 0.0,
            "corners_against": 0.0,
            "yellow_for": 0.0,
            "yellow_against": 0.0,
            "red_for": 0.0,
            "red_against": 0.0,
            "btts_count": 0,
            "over25_count": 0,
        }
    )

    for match in recent_results:
        try:
            hg = int(match["home_team"].get("score") or 0)
            ag = int(match["away_team"].get("score") or 0)
        except Exception:
            continue

        stats = (((match.get("sofascore") or {}).get("statistics") or {}).get("ALL") or {})

        def _num(key: str, side: str) -> float:
            item = stats.get(key) or {}
            val = item.get(side)

            try:
                return float(val)
            except Exception:
                try:
                    txt = str(item.get("home" if side == "home" else "away") or "").replace("%", "").strip()
                    return float(txt)
                except Exception:
                    return 0.0

        pairs = [
            (match["home_team"], hg, ag, "home"),
            (match["away_team"], ag, hg, "away"),
        ]

        for team, gf, ga, side in pairs:
            tid = str(team.get("id") or team.get("normalized_name") or "")
            row = sums[tid]
            row["team_name"] = team.get("name")
            row["matches"] += 1
            row["goals_for"] += gf
            row["goals_against"] += ga

            if gf > ga:
                row["wins"] += 1
            elif gf < ga:
                row["losses"] += 1
            else:
                row["draws"] += 1

            if gf > 0 and ga > 0:
                row["btts_count"] += 1
            if gf + ga > 2:
                row["over25_count"] += 1

            opp_side = "away" if side == "home" else "home"

            row["xg_for"] += _num("expectedGoals", side)
            row["xg_against"] += _num("expectedGoals", opp_side)
            row["shots_for"] += _num("totalShotsOnGoal", side)
            row["shots_against"] += _num("totalShotsOnGoal", opp_side)
            row["shots_on_target_for"] += _num("shotsOnGoal", side)
            row["shots_on_target_against"] += _num("shotsOnGoal", opp_side)
            row["corners_for"] += _num("cornerKicks", side)
            row["corners_against"] += _num("cornerKicks", opp_side)
            row["yellow_for"] += _num("yellowCards", side)
            row["yellow_against"] += _num("yellowCards", opp_side)
            row["red_for"] += _num("redCards", side)
            row["red_against"] += _num("redCards", opp_side)

    output: dict[str, dict[str, Any]] = {}

    for tid, row in sums.items():
        matches = max(int(row["matches"]), 1)
        output[tid] = {
            **row,
            "avg_goals_for": round(row["goals_for"] / matches, 3),
            "avg_goals_against": round(row["goals_against"] / matches, 3),
            "avg_xg_for": round(row["xg_for"] / matches, 3),
            "avg_xg_against": round(row["xg_against"] / matches, 3),
            "avg_shots_for": round(row["shots_for"] / matches, 3),
            "avg_shots_against": round(row["shots_against"] / matches, 3),
            "avg_shots_on_target_for": round(row["shots_on_target_for"] / matches, 3),
            "avg_shots_on_target_against": round(row["shots_on_target_against"] / matches, 3),
            "avg_corners_for": round(row["corners_for"] / matches, 3),
            "avg_corners_against": round(row["corners_against"] / matches, 3),
            "avg_yellow_for": round(row["yellow_for"] / matches, 3),
            "avg_yellow_against": round(row["yellow_against"] / matches, 3),
            "avg_red_for": round(row["red_for"] / matches, 3),
            "avg_red_against": round(row["red_against"] / matches, 3),
            "btts_rate": round(row["btts_count"] / matches, 3),
            "over25_rate": round(row["over25_count"] / matches, 3),
        }

    return output


def scrape_league(
    league_key: str,
    *,
    output_dir: str | None = None,
    recent_detail_limit: int = 24,
    upcoming_detail_limit: int = 12,
    season_year: str | None = None,
) -> dict[str, Any]:
    league = get_league_config(league_key)
    logger.info("Scraping SofaScore league=%s tournament=%s", league_key, league["id"])

    season = resolve_season(league_key, season_year)
    season_id = season["id"]

    standings_raw = fetch_standings(league_key, season_id)
    rounds_info = fetch_rounds(league_key, season_id)
    round_numbers = [
        int((r or {}).get("round"))
        for r in (rounds_info.get("rounds") or [])
        if (r or {}).get("round") is not None
    ]

    all_events = []
    for round_number in round_numbers:
        try:
            all_events.extend(fetch_events_by_round(league_key, season_id, round_number))
        except Exception as exc:
            logger.warning(
                "SofaScore round fetch failed league=%s round=%s error=%s",
                league_key,
                round_number,
                exc,
            )

    parsed_events = [_parse_event(event) for event in all_events]
    recent = [e for e in parsed_events if (e.get("status") or {}).get("completed")]

    now_iso = _now_iso()
    upcoming = [
        e
        for e in parsed_events
        if not (e.get("status") or {}).get("completed")
        and (e.get("date") or "") >= now_iso
    ]

    recent.sort(key=lambda x: (x.get("date") or "", x.get("event_id") or ""), reverse=True)
    upcoming.sort(key=lambda x: (x.get("date") or "", x.get("event_id") or ""))

    enrich_targets = recent[:recent_detail_limit] + upcoming[:upcoming_detail_limit]
    by_event = {item["event_id"]: item for item in enrich_targets}

    for event_id, parsed in by_event.items():
        detail = fetch_event_details(event_id)
        stats = fetch_event_statistics(event_id)
        lineups = fetch_event_lineups(event_id)
        incidents = fetch_event_incidents(event_id)
        _attach_detail(parsed, detail, stats, lineups, incidents)

    standings = build_standings_payload(standings_raw)
    team_metrics = build_team_metrics(recent[:recent_detail_limit])

    payload = {
        "league_key": league_key,
        "league_name": league["name"],
        "league_slug": league["slug"],
        "source": "SofaScore",
        "scraped_at": utc_now_iso(),
        "tournament_id": league["id"],
        "season_id": season_id,
        "season_year": season.get("year"),
        "current_round": ((rounds_info.get("currentRound") or {}).get("round")),
        "standings": standings,
        "fixtures": upcoming,
        "recent_results": recent,
        "team_metrics": team_metrics,
        "meta": {
            "rounds_total": len(round_numbers),
            "events_total": len(parsed_events),
            "recent_detail_limit": recent_detail_limit,
            "upcoming_detail_limit": upcoming_detail_limit,
        },
    }

    if output_dir:
        output_path = save_json(f"{output_dir}/{league_key}.json", payload)
        logger.info("Saved SofaScore league=%s -> %s", league_key, output_path)

    return payload