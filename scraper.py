#!/usr/bin/env python3
"""
Golium — integrated combined scraper

Uses ESPN as the base data source for standings, fixtures and recent form,
and enriches teams with xG/xGA from Understat and FBref when available.

Outputs the same top-level shape expected by the current frontend:
- single league: one league payload
- all: {"leagues": {...}}

Legacy quiniela support is kept in scraper_legacy.py.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any

try:
    from storage import save_snapshot
except Exception:
    save_snapshot = None

LEAGUES = {
    "laliga": {"slug": "esp.1", "name": "LaLiga"},
    "premier": {"slug": "eng.1", "name": "Premier League"},
    "bundesliga": {"slug": "ger.1", "name": "Bundesliga"},
    "seriea": {"slug": "ita.1", "name": "Serie A"},
    "ligue1": {"slug": "fra.1", "name": "Ligue 1"},
    "champions": {"slug": "uefa.champions", "name": "Champions League"},
    "europaleague": {"slug": "uefa.europa", "name": "Europa League"},
    "hypermotion": {"slug": "esp.2", "name": "LaLiga Hypermotion"},
}

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
UNDERSTAT_BASE = "https://understat.com"
FBREF_BASE = "https://fbref.com"

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.8",
}

ESPN_SLUGS_PRIORITY = [
    "esp.1", "esp.2", "eng.1", "ger.1", "ita.1", "fra.1",
    "uefa.champions", "uefa.europa", "eng.2", "por.1", "ned.1"
]

SLUG_TO_FBREF_COMP = {
    "esp.1": "12",
    "eng.1": "9",
    "ger.1": "20",
    "ita.1": "11",
    "fra.1": "13",
}


def fetch_json(url: str, headers: dict[str, str] | None = None, retries: int = 3) -> Any:
    hdrs = COMMON_HEADERS.copy()
    if headers:
        hdrs.update(headers)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError:
            if attempt < retries - 1:
                time.sleep(1.5)
        except Exception:
            if attempt < retries - 1:
                time.sleep(1.5)
    return None


def fetch_text(url: str, headers: dict[str, str] | None = None, retries: int = 3) -> str | None:
    hdrs = COMMON_HEADERS.copy()
    if headers:
        hdrs.update(headers)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", errors="ignore")
        except Exception:
            if attempt < retries - 1:
                time.sleep(1.5)
    return None


def norm(s: str | None) -> str:
    s = (s or "").lower()
    s = re.sub(r'\b(fc|af|sc|ac|cd|rc|ud|ca|cf|afc|fk|sk|bv|sv|ssc|as|ss|1\.|c\.d\.|r\.c\.d\.)\b', '', s)
    s = re.sub(r'[^a-z0-9]', '', s)
    return s.strip()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "-"):
            return default
        return float(value)
    except Exception:
        return default


def season_start_year() -> int:
    today = datetime.now(tz=timezone.utc)
    return today.year - (1 if today.month < 7 else 0)


# ---------------------------------------------------------------------------
# Understat / FBref enrichment

def fetch_understat_team_xg(team_name: str, season: int) -> dict[str, float] | None:
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', team_name.strip()).strip('-')
    url = f"{UNDERSTAT_BASE}/team/{slug}/{season}"
    html = fetch_text(url)
    if not html:
        return None
    m = re.search(r"data\s*=\s*JSON.parse\('([^']+)", html)
    if not m:
        return None
    try:
        decoded = json.loads(m.group(1).encode().decode('unicode_escape'))
    except Exception:
        return None

    total_for = 0.0
    total_against = 0.0
    match_count = 0
    for match in decoded:
        if match.get('isResult'):
            total_for += safe_float(match.get('xG'))
            total_against += safe_float(match.get('xGA'))
            match_count += 1
    if match_count == 0:
        return None
    return {
        "xg_for": round(total_for / match_count, 3),
        "xg_against": round(total_against / match_count, 3),
    }


def fetch_fbref_team_xg(team_name: str, season: int, comp_slug: str | None = None) -> dict[str, float] | None:
    if not comp_slug:
        return None
    season_range = f"{season}-{str(season + 1)[2:]}"
    url = f"{FBREF_BASE}/en/comps/{comp_slug}/{season_range}/stats"
    html = fetch_text(url)
    if not html:
        return None

    clean = html.replace("<!--", "").replace("-->", "")
    table_m = re.search(r'<table[^>]*id="stats_squads_(?:shooting|standard)_for"[^>]*>(.*?)</table>', clean, re.DOTALL | re.IGNORECASE)
    if not table_m:
        return None

    table_html = table_m.group(1)
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL | re.IGNORECASE)
    for row in rows:
        team_cell = re.search(r'<th[^>]*>(.*?)</th>', row, re.DOTALL | re.IGNORECASE)
        if not team_cell:
            continue
        team_text = re.sub('<[^>]+>', '', team_cell.group(1)).strip()
        if norm(team_text) != norm(team_name):
            continue
        # FBref often puts values in data-stat attributes; take a permissive route.
        xg_m = re.search(r'data-stat="xg"[^>]*>([^<]+)<', row, re.IGNORECASE)
        xga_m = re.search(r'data-stat="xga"[^>]*>([^<]+)<', row, re.IGNORECASE)
        if not xg_m or not xga_m:
            cols = re.findall(r'<td[^>]*>([^<]*)</td>', row)
            if len(cols) < 2:
                return None
            return None
        return {
            "xg_for": round(safe_float(xg_m.group(1)), 3),
            "xg_against": round(safe_float(xga_m.group(1)), 3),
        }
    return None


# ---------------------------------------------------------------------------
# ESPN helpers

def _extract_standing_entries(raw: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    entries = (raw.get("standings") or {}).get("entries", [])
    if not entries:
        for child in (raw.get("children") or []):
            entries.extend((child.get("standings") or {}).get("entries", []))

    for entry in entries:
        team = entry.get("team", {})
        stats = {s.get("name", ""): s.get("value", 0) for s in (entry.get("stats") or [])}
        rows.append({
            "teamId": str(team.get("id", "")),
            "teamName": team.get("displayName") or team.get("name") or "",
            "position": int(stats.get("rank") or stats.get("position") or 0),
            "played": int(stats.get("gamesPlayed") or stats.get("played") or 0),
            "wins": int(stats.get("wins") or 0),
            "draws": int(stats.get("ties") or stats.get("draws") or 0),
            "losses": int(stats.get("losses") or 0),
            "gf": int(stats.get("pointsFor") or stats.get("goalsFor") or 0),
            "ga": int(stats.get("pointsAgainst") or stats.get("goalsAgainst") or 0),
            "points": int(stats.get("points") or 0),
            "gfHome": int(stats.get("homeGoalsFor") or stats.get("pointsForHome") or 0),
            "gaHome": int(stats.get("homeGoalsAgainst") or stats.get("pointsAgainstHome") or 0),
            "gfAway": int(stats.get("awayGoalsFor") or stats.get("pointsForAway") or 0),
            "gaAway": int(stats.get("awayGoalsAgainst") or stats.get("pointsAgainstAway") or 0),
            "wHome": int(stats.get("homeWins") or 0),
            "wAway": int(stats.get("awayWins") or 0),
        })

    if rows and all(r["position"] == 0 for r in rows):
        for i, row in enumerate(rows, start=1):
            row["position"] = i
    return rows

def parse_standings(league_key: str) -> list[dict[str, Any]]:
    league = LEAGUES[league_key]
    slug = league["slug"]
    urls = [
        f"https://site.api.espn.com/apis/v2/sports/soccer/{slug}/standings",
        f"{ESPN_BASE}/{slug}/standings",
    ]
    data = None
    for url in urls:
        data = fetch_json(url)
        if data:
            break
    if not data:
        return []

    entries = (data.get("standings") or {}).get("entries", [])
    rows: list[dict[str, Any]] = []
    for entry in entries:
        team = entry.get("team", {})
        stats = {s.get("name", ""): s.get("value", 0) for s in (entry.get("stats") or [])}
        rows.append({
            "teamId": str(team.get("id", "")),
            "teamName": team.get("displayName") or team.get("name") or "",
            "position": int(stats.get("rank") or stats.get("position") or 0),
            "played": int(stats.get("gamesPlayed") or 0),
            "wins": int(stats.get("wins") or 0),
            "draws": int(stats.get("ties") or stats.get("draws") or 0),
            "losses": int(stats.get("losses") or 0),
            "gf": int(stats.get("pointsFor") or stats.get("goalsFor") or 0),
            "ga": int(stats.get("pointsAgainst") or stats.get("goalsAgainst") or 0),
            "points": int(stats.get("points") or 0),
            "gfHome": int(stats.get("goalsForHome") or 0),
            "gaHome": int(stats.get("goalsAgainstHome") or 0),
            "gfAway": int(stats.get("goalsForAway") or 0),
            "gaAway": int(stats.get("goalsAgainstAway") or 0),
            "wHome": int(stats.get("winsHome") or 0),
            "wAway": int(stats.get("winsAway") or 0),
        })
    return rows


def parse_scoreboard(league_key: str, standings_lookup: dict[str, dict[str, Any]] | None = None, days: int = 28, max_fixtures: int = 12) -> list[dict[str, Any]]:
    league = LEAGUES[league_key]
    slug = league["slug"]
    standings_lookup = standings_lookup or {}
    fixtures: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    today = datetime.now(timezone.utc)

    for offset in range(days):
        ds = (today + timedelta(days=offset)).strftime("%Y%m%d")
        data = fetch_json(f"{ESPN_BASE}/{slug}/scoreboard?dates={ds}")
        if not data:
            continue
        for ev in data.get("events") or []:
            comp = (ev.get("competitions") or [{}])[0]
            competitors = comp.get("competitors") or []
            if len(competitors) < 2:
                continue
            status = ((ev.get("status") or {}).get("type") or {}).get("name") or "STATUS_SCHEDULED"
            if status in ("STATUS_FINAL", "STATUS_FULL_TIME"):
                continue
            home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
            away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
            ev_id = str(ev.get("id") or "")
            if not ev_id or ev_id in seen_ids:
                continue
            seen_ids.add(ev_id)

            def _team_rec(c: dict[str, Any]) -> dict[str, Any]:
                team = c.get("team") or {}
                name = team.get("displayName") or team.get("name") or ""
                raw_id = str(team.get("id") or "")
                lookup = standings_lookup.get(raw_id) or standings_lookup.get(norm(name)) or standings_lookup.get(name) or {}
                return {
                    "id": str(lookup.get("teamId") or raw_id),
                    "rawId": raw_id,
                    "name": name,
                    "short": team.get("abbreviation") or team.get("shortDisplayName") or name[:3].upper(),
                }

            fixtures.append({
                "id": ev_id,
                "date": ev.get("date") or "",
                "status": status,
                "matchday": str(ev.get("week", {}).get("number") or comp.get("date") or "?"),
                "homeTeam": _team_rec(home),
                "awayTeam": _team_rec(away),
                "homeScore": int(safe_float(home.get("score"), 0)),
                "awayScore": int(safe_float(away.get("score"), 0)),
            })
            if len(fixtures) >= max_fixtures:
                return fixtures
        time.sleep(0.1)
    return fixtures


def build_espn_team_index() -> dict[str, dict[str, Any]]:
    idx: dict[str, dict[str, Any]] = {}
    for slug in ESPN_SLUGS_PRIORITY:
        urls = [
            f"https://site.api.espn.com/apis/v2/sports/soccer/{slug}/standings",
            f"https://cdn.espn.com/core/soccer/standings?league={slug}&xhr=1",
            f"{ESPN_BASE}/{slug}/standings",
        ]
        data = None
        for url in urls:
            data = fetch_json(url)
            if data:
                break
        if not data:
            continue
        rows = _extract_standing_entries(data)
        for row in rows:
            rec = {
                "teamId": str(row.get("teamId") or ""),
                "teamName": row.get("teamName") or "",
                "position": int(row.get("position") or 0),
                "leagueSlug": slug,
            }
            if rec["teamId"]:
                idx[rec["teamId"]] = rec
            if rec["teamName"]:
                idx[rec["teamName"]] = rec
            n = norm(rec["teamName"])
            if n:
                idx[n] = rec
        time.sleep(0.1)
    return idx


def fetch_espn_team_form(team_id: str, slug_priority: list[str] | None = None) -> list[dict[str, Any]]:
    for slug in (slug_priority or ESPN_SLUGS_PRIORITY):
        data = fetch_json(f"{ESPN_BASE}/{slug}/teams/{team_id}/schedule")
        if not data or not data.get("events"):
            continue
        form = []
        for ev in data.get("events") or []:
            status = ((ev.get("status") or {}).get("type") or {}).get("name", "")
            if status != "STATUS_FINAL":
                continue
            comp = (ev.get("competitions") or [{}])[0]
            my = opp = None
            for c in comp.get("competitors") or []:
                if str((c.get("team") or {}).get("id")) == str(team_id):
                    my = c
                else:
                    opp = c
            if not my or not opp:
                continue
            my_score = safe_float(my.get("score"))
            opp_score = safe_float(opp.get("score"))
            res = 'D'
            if my_score > opp_score:
                res = 'W'
            elif my_score < opp_score:
                res = 'L'
            form.append({
                "r": res,
                "gf": my_score,
                "ga": opp_score,
                "oppId": str((opp.get("team") or {}).get("id") or ""),
                "eventId": str(ev.get("id") or ""),
            })
        return form
    return []


def enrich_fixtures_with_xg(fixtures: list[dict[str, Any]], team_idx: dict[str, dict[str, Any]], season: int | None = None) -> None:
    season = season or season_start_year()
    cache: dict[tuple[str, str | None], dict[str, float] | None] = {}
    for fix in fixtures:
        for side_key, prefix in (("homeTeam", "home"), ("awayTeam", "away")):
            side = fix.get(side_key) or {}
            name = side.get("name") or ""
            if not name:
                fix[f"{prefix}XG"] = None
                fix[f"{prefix}XGA"] = None
                continue
            idx_rec = team_idx.get(str(side.get("id"))) or team_idx.get(norm(name)) or team_idx.get(name)
            comp_slug = SLUG_TO_FBREF_COMP.get((idx_rec or {}).get("leagueSlug", ""))
            cache_key = (name, comp_slug)
            if cache_key not in cache:
                xg_data = fetch_understat_team_xg(name, season)
                if not xg_data:
                    xg_data = fetch_fbref_team_xg(name, season, comp_slug)
                cache[cache_key] = xg_data
            xg_data = cache.get(cache_key)
            fix[f"{prefix}XG"] = xg_data.get("xg_for") if xg_data else None
            fix[f"{prefix}XGA"] = xg_data.get("xg_against") if xg_data else None


def build_team_form(standings: list[dict[str, Any]], team_idx: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in standings:
        team_id = str(row.get("teamId") or "")
        if not team_id:
            continue
        rec = team_idx.get(team_id) or team_idx.get(norm(row.get("teamName"))) or team_idx.get(row.get("teamName"))
        slug_priority = [rec.get("leagueSlug")] if rec and rec.get("leagueSlug") else None
        form = fetch_espn_team_form(team_id, slug_priority=slug_priority)
        out[team_id] = form[-6:]
        time.sleep(0.05)
    return out


def build_output_for_league(league_key: str) -> dict[str, Any] | None:
    league = LEAGUES.get(league_key)
    if not league:
        return None

    print(f"\n{'='*55}\n  {league['name']}  ({league['slug']})\n{'='*55}")
    print("  [1] Standings...")
    standings = parse_standings(league_key)
    print(f"    {len(standings)} equipos")

    print("  [2] Fixtures...")
    standings_lookup = {}
    for row in standings:
        tid = str(row.get("teamId") or "")
        name = row.get("teamName") or ""
        if tid:
            standings_lookup[tid] = row
        if name:
            standings_lookup[name] = row
        n = norm(name)
        if n:
            standings_lookup[n] = row
    fixtures = parse_scoreboard(league_key, standings_lookup=standings_lookup)
    print(f"    {len(fixtures)} partidos")

    print("  [3] Form...")
    idx = build_espn_team_index()
    team_form = build_team_form(standings, idx)
    with_form = sum(1 for v in team_form.values() if v)
    print(f"    Forma OK: {with_form}/{len(team_form)}")

    print("  [4] xG enrichment (Understat/FBref fallback)...")
    enrich_fixtures_with_xg(fixtures, idx)

    return {
        "league": league["name"],
        "leagueKey": league_key,
        "leagueSlug": league["slug"],
        "source": "ESPN + Understat + FBref",
        "scrapedAt": datetime.now(timezone.utc).isoformat(),
        "fixtures": fixtures,
        "standings": standings,
        "teamForm": team_form,
        "cardModel": {"leagueAvgTotal": 3.8, "teams": {}, "referees": {}, "fixtures": {}},
    }


def save_output(output: dict[str, Any], filename: str) -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(base_dir, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    return out_path


def maybe_save_snapshot(output: dict[str, Any], source_file: str) -> str:
    if not save_snapshot:
        return ""
    try:
        snapshot_id = save_snapshot(output, source_file=source_file)
        return f"\n  Snapshot: id={snapshot_id} guardado en golium.db"
    except Exception as exc:
        return f"\n  Snapshot: error guardando en SQLite ({exc})"


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("Uso: python scraper.py [liga|all]")
        print("Ligas:", ", ".join(LEAGUES))
        print("Legacy quiniela: python scraper_legacy.py quiniela")
        sys.exit(0)

    target = args[0].lower()

    if target == "quiniela":
        try:
            import scraper_legacy
            output = scraper_legacy.scrape_quiniela()
            if not output:
                print("No se pudo generar la quiniela.")
                sys.exit(1)
            out_path = save_output(output, "quiniela.json")
            snapshot_msg = maybe_save_snapshot(output, "quiniela.json")
            print(
                f"\n  ✅ quiniela.json guardado: {out_path}{snapshot_msg}\n"
                f"  Jornada: {output.get('matchday', '?')}\n"
                f"  Partidos: {len(output.get('fixtures', []))}\n"
            )
            return
        except Exception as exc:
            print(f"Error ejecutando quiniela legacy: {exc}")
            sys.exit(1)

    if target not in LEAGUES and target != "all":
        print(f"Opción inválida. Usa: {', '.join(LEAGUES)}, all")
        sys.exit(1)

    if target == "all":
        results: dict[str, Any] = {}
        for k in LEAGUES:
            data = build_output_for_league(k)
            if data:
                results[k] = data
        output = {"leagues": results}
        out_path = save_output(output, "data.json")
        snapshot_msg = maybe_save_snapshot(output, "data.json")
        print(f"\n  ✅ data.json guardado: {out_path}{snapshot_msg}\n  Ligas: {len(results)}\n")
        return

    output = build_output_for_league(target)
    if not output:
        print("No se obtuvo ningún dato.")
        sys.exit(1)

    out_path = save_output(output, "data.json")
    snapshot_msg = maybe_save_snapshot(output, "data.json")
    print(
        f"\n  ✅ data.json guardado: {out_path}\n"
        f"  Liga:      {output.get('league', '?')}\n"
        f"  Partidos:  {len(output.get('fixtures', []))}\n"
        f"  Equipos:   {len(output.get('standings', []))}{snapshot_msg}\n\n"
        "  python server.py\n"
        "  http://localhost:8000/app.html\n"
    )


if __name__ == "__main__":
    main()
