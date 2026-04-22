"""Dedicated ESPN soccer scraper for Golium."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Iterable

from .shared import (
    BASE_SITE_API,
    BASE_STANDINGS_API,
    LEAGUES,
    build_url,
    fetch_json,
    logger,
    normalize_team_name,
    save_json,
    utc_now_iso,
)


@dataclass(frozen=True)
class LeagueConfig:
    """Static league configuration."""

    key: str
    name: str
    slug: str


def get_league_config(league_key: str) -> LeagueConfig:
    """Return validated league configuration."""
    try:
        item = LEAGUES[league_key]
    except KeyError as exc:
        supported = ", ".join(sorted(LEAGUES))
        raise ValueError(f"Unknown league '{league_key}'. Supported: {supported}") from exc
    return LeagueConfig(**item)


def fetch_scoreboard(league: LeagueConfig, *, dates: str | None = None, limit: int | None = None) -> dict[str, Any]:
    """Fetch the ESPN scoreboard payload for a league/date."""
    params: dict[str, Any] = {}
    if dates:
        params["dates"] = dates
    if limit is not None:
        params["limit"] = limit
    url = build_url(f"{BASE_SITE_API}/{league.slug}/scoreboard", params)
    return fetch_json(url)


def fetch_standings_payload(league: LeagueConfig) -> dict[str, Any]:
    """Fetch the ESPN standings payload for a league."""
    url = f"{BASE_STANDINGS_API}/{league.slug}/standings"
    return fetch_json(url)


def parse_iso_date(value: str | dict[str, Any] | None) -> str | None:
    """Convert an ISO ESPN datetime to YYYY-MM-DD when possible."""
    if isinstance(value, dict):
        value = value.get("value") or value.get("date")

    if not value or not isinstance(value, str):
        return None

    cleaned = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned).astimezone(UTC).date().isoformat()
    except ValueError:
        return None


def _extract_stat_map(stat_items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    stat_map: dict[str, Any] = {}
    for item in stat_items or []:
        name = item.get("name") or item.get("displayName") or item.get("abbreviation")
        if not name:
            continue
        stat_map[name] = item.get("value", item.get("displayValue"))
        display_name = item.get("displayName")
        if display_name:
            stat_map[display_name] = item.get("displayValue", item.get("value"))
        abbreviation = item.get("abbreviation")
        if abbreviation:
            stat_map[abbreviation] = item.get("displayValue", item.get("value"))
    return stat_map


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_standings(league_key: str) -> list[dict[str, Any]]:
    """Return normalized standings for a league."""
    league = get_league_config(league_key)
    payload = fetch_standings_payload(league)
    children = payload.get("children") or []
    standings_rows: list[dict[str, Any]] = []

    for child in children:
        standings = child.get("standings") or {}
        entries = standings.get("entries") or []
        for entry in entries:
            team = entry.get("team") or {}
            stats = _extract_stat_map(entry.get("stats") or [])
            note = entry.get("note") or {}
            standings_rows.append(
                {
                    "rank": stats.get("rank") or stats.get("Rank") or len(standings_rows) + 1,
                    "team_id": str(team.get("id") or ""),
                    "team_name": team.get("displayName") or team.get("shortDisplayName") or team.get("name"),
                    "team_short_name": team.get("shortDisplayName") or team.get("abbreviation"),
                    "team_abbr": team.get("abbreviation"),
                    "normalized_name": normalize_team_name(team.get("displayName") or team.get("name") or ""),
                    "played": stats.get("gamesPlayed") or stats.get("P") or stats.get("GP"),
                    "wins": stats.get("wins") or stats.get("W"),
                    "draws": stats.get("ties") or stats.get("draws") or stats.get("D"),
                    "losses": stats.get("losses") or stats.get("L"),
                    "goals_for": stats.get("pointsFor") or stats.get("GF"),
                    "goals_against": stats.get("pointsAgainst") or stats.get("GA"),
                    "goal_difference": stats.get("pointDifferential") or stats.get("GD"),
                    "points": stats.get("points") or stats.get("PTS"),
                    "form": stats.get("form") or stats.get("Form") or None,
                    "status": note.get("description") or note.get("displayValue"),
                    "raw_stats": stats,
                }
            )

    standings_rows.sort(key=lambda row: _safe_int(row.get("rank"), 10**6))
    return standings_rows


def parse_event(event: dict[str, Any]) -> dict[str, Any]:
    """Parse a single ESPN event into a stable fixture/result record."""
    competition = (event.get("competitions") or [{}])[0]
    competitors = competition.get("competitors") or []
    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), {})
    status = (competition.get("status") or {}).get("type") or {}
    venue = competition.get("venue") or {}

    def _team_payload(side: dict[str, Any]) -> dict[str, Any]:
        team = side.get("team") or {}
        return {
            "id": str(team.get("id") or side.get("id") or ""),
            "name": team.get("displayName") or team.get("shortDisplayName") or team.get("name"),
            "abbr": team.get("abbreviation"),
            "normalized_name": normalize_team_name(team.get("displayName") or team.get("name") or ""),
            "score": side.get("score"),
            "form": side.get("form"),
            "record": ((side.get("records") or [{}])[0]).get("summary"),
        }

    return {
        "event_id": str(event.get("id") or competition.get("id") or ""),
        "date": event.get("date") or competition.get("date") or competition.get("startDate"),
        "date_only": parse_iso_date(event.get("date") or competition.get("date") or competition.get("startDate")),
        "name": event.get("name") or competition.get("name"),
        "short_name": event.get("shortName"),
        "status": {
            "state": status.get("state"),
            "completed": bool(status.get("completed")),
            "description": status.get("description"),
            "detail": (competition.get("status") or {}).get("type", {}).get("detail")
            or (competition.get("status") or {}).get("detail"),
        },
        "season_year": (event.get("season") or {}).get("year"),
        "home_team": _team_payload(home),
        "away_team": _team_payload(away),
        "venue": {
            "name": venue.get("fullName"),
            "city": (venue.get("address") or {}).get("city"),
            "country": (venue.get("address") or {}).get("country"),
        },
    }


def _today_compact() -> str:
    return date.today().strftime("%Y%m%d")


def _compact_date_range(*, days_back: int = 0, days_ahead: int = 0) -> list[str]:
    """Return YYYYMMDD dates around today, oldest -> newest."""
    today = date.today()
    start = today - timedelta(days=days_back)
    end = today + timedelta(days=days_ahead)

    result: list[str] = []
    cursor = start
    while cursor <= end:
        result.append(cursor.strftime("%Y%m%d"))
        cursor += timedelta(days=1)
    return result


def _collect_events_for_dates(
    league: LeagueConfig,
    compact_dates: list[str],
) -> list[dict[str, Any]]:
    """Fetch scoreboard for each date and de-duplicate events."""
    events_by_id: dict[str, dict[str, Any]] = {}

    for compact_date in compact_dates:
        try:
            payload = fetch_scoreboard(league, dates=compact_date)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed fetching ESPN scoreboard league=%s date=%s error=%s", league.key, compact_date, exc)
            continue

        for event in payload.get("events") or []:
            parsed = parse_event(event)
            event_id = parsed.get("event_id")
            if not event_id:
                continue
            events_by_id[event_id] = parsed

    return list(events_by_id.values())


def get_fixtures(
    league_key: str,
    *,
    max_upcoming_dates: int = 7,
    max_recent_dates: int = 45,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Return upcoming fixtures and recent results for a league.

    Important:
    We do NOT rely on ESPN's 'calendar' field anymore because it can be incomplete
    and sometimes causes only 1 historical match/day to be collected.
    Instead, we explicitly iterate over recent and upcoming dates.
    """
    league = get_league_config(league_key)

    compact_dates = _compact_date_range(
        days_back=max_recent_dates,
        days_ahead=max_upcoming_dates,
    )
    all_events = _collect_events_for_dates(league, compact_dates)

    today = _today_compact()
    upcoming: list[dict[str, Any]] = []
    recent: list[dict[str, Any]] = []

    for record in all_events:
        date_only = (record.get("date_only") or "").replace("-", "")
        completed = bool(((record.get("status") or {}).get("completed")))

        if completed:
            recent.append(record)
        else:
            if not date_only or date_only >= today:
                upcoming.append(record)

    upcoming.sort(key=lambda x: (x.get("date") or "", x.get("event_id") or ""))
    recent.sort(key=lambda x: (x.get("date") or "", x.get("event_id") or ""), reverse=True)
    return upcoming, recent


def _result_letter(team_score: int, opp_score: int) -> str:
    if team_score > opp_score:
        return "W"
    if team_score < opp_score:
        return "L"
    return "D"


def build_team_form(
    recent_results: list[dict[str, Any]],
    *,
    max_matches: int = 5,
) -> dict[str, dict[str, Any]]:
    """Build recent form per team from already parsed results."""
    sequences: dict[str, deque[str]] = defaultdict(lambda: deque(maxlen=max_matches))
    summary: dict[str, dict[str, Any]] = defaultdict(lambda: {"wins": 0, "draws": 0, "losses": 0})

    for match in sorted(recent_results, key=lambda item: item.get("date") or ""):
        try:
            home_score = int(match["home_team"].get("score") or 0)
            away_score = int(match["away_team"].get("score") or 0)
        except (TypeError, ValueError):
            continue

        home_key = match["home_team"]["normalized_name"]
        away_key = match["away_team"]["normalized_name"]
        home_result = _result_letter(home_score, away_score)
        away_result = _result_letter(away_score, home_score)

        sequences[home_key].append(home_result)
        sequences[away_key].append(away_result)

        if home_result == "W":
            summary[home_key]["wins"] += 1
            summary[away_key]["losses"] += 1
        elif home_result == "L":
            summary[home_key]["losses"] += 1
            summary[away_key]["wins"] += 1
        else:
            summary[home_key]["draws"] += 1
            summary[away_key]["draws"] += 1

    output: dict[str, dict[str, Any]] = {}
    for normalized_name, sequence in sequences.items():
        stats = summary[normalized_name]
        output[normalized_name] = {
            "sequence": "".join(sequence),
            "matches": len(sequence),
            **stats,
        }
    return output


def get_team_form(
    league_key: str,
    *,
    max_matches: int = 5,
    recent_dates_window: int = 45,
) -> dict[str, dict[str, Any]]:
    """Build recent form per team using ESPN recent results."""
    _, recent_results = get_fixtures(
        league_key,
        max_upcoming_dates=0,
        max_recent_dates=recent_dates_window,
    )
    return build_team_form(recent_results, max_matches=max_matches)


def build_team_index(
    standings: list[dict[str, Any]],
    upcoming: list[dict[str, Any]],
    recent: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build an internal team index from already collected league data."""
    team_index: dict[str, dict[str, Any]] = {}

    def _upsert(team: dict[str, Any], source: str) -> None:
        normalized = team.get("normalized_name")
        if not normalized:
            return
        entry = team_index.setdefault(
            normalized,
            {
                "team_id": team.get("team_id") or team.get("id"),
                "name": team.get("team_name") or team.get("name"),
                "short_name": team.get("team_short_name") or team.get("name"),
                "abbr": team.get("team_abbr") or team.get("abbr"),
                "normalized_name": normalized,
                "sources": [],
                "aliases": [],
            },
        )
        if source not in entry["sources"]:
            entry["sources"].append(source)
        for alias in [team.get("team_name"), team.get("team_short_name"), team.get("name"), team.get("abbr")]:
            if alias and alias not in entry["aliases"]:
                entry["aliases"].append(alias)
        entry["aliases"].sort()

    for row in standings:
        _upsert(row, "standings")
    for match in [*upcoming, *recent]:
        _upsert(match["home_team"], "fixtures")
        _upsert(match["away_team"], "fixtures")

    return dict(sorted(team_index.items(), key=lambda item: item[0]))


def get_team_index(league_key: str) -> dict[str, dict[str, Any]]:
    """Build an internal team index for cross-source matching."""
    standings = get_standings(league_key)
    upcoming, recent = get_fixtures(league_key)
    return build_team_index(standings, upcoming, recent)


def scrape_league(league_key: str, *, output_dir: str = "output/raw/espn") -> dict[str, Any]:
    """Scrape one league and persist its JSON output."""
    league = get_league_config(league_key)
    logger.info("Scraping ESPN league=%s slug=%s", league.key, league.slug)

    standings = get_standings(league.key)
    fixtures, recent_results = get_fixtures(league.key)
    team_form = build_team_form(recent_results)
    team_index = build_team_index(standings, fixtures, recent_results)

    for row in standings:
        normalized = row.get("normalized_name")
        if normalized and normalized in team_form and not row.get("form"):
            row["form"] = team_form[normalized]["sequence"]

    payload = {
        "league_key": league.key,
        "league_name": league.name,
        "league_slug": league.slug,
        "source": "ESPN",
        "scraped_at": utc_now_iso(),
        "standings": standings,
        "fixtures": fixtures,
        "recent_results": recent_results,
        "team_index": team_index,
        "team_form": team_form,
        "meta": {
            "fixture_count": len(fixtures),
            "recent_result_count": len(recent_results),
            "team_count": len(team_index),
        },
    }

    path = save_json(f"{output_dir}/{league.key}.json", payload)
    logger.info("Saved ESPN league=%s -> %s", league.key, path)
    return payload


def scrape_all_leagues(*, output_dir: str = "output/raw/espn") -> dict[str, Any]:
    """Scrape all configured leagues without failing the whole run."""
    results: dict[str, Any] = {}
    errors: dict[str, str] = {}

    for league_key in LEAGUES:
        try:
            results[league_key] = scrape_league(league_key, output_dir=output_dir)
        except Exception as exc:  # noqa: BLE001
            logger.exception("League scrape failed: %s", league_key)
            errors[league_key] = str(exc)

    aggregate = {
        "source": "ESPN",
        "scraped_at": utc_now_iso(),
        "leagues": results,
        "errors": errors,
        "meta": {
            "requested_leagues": list(LEAGUES.keys()),
            "successful_leagues": sorted(results.keys()),
            "failed_leagues": sorted(errors.keys()),
        },
    }

    path = save_json(f"{output_dir}/all.json", aggregate)
    logger.info("Saved ESPN aggregate -> %s", path)
    return aggregate