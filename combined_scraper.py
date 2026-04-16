#!/usr/bin/env python3
"""
Golium — Combined scraper for ESPN, Understat and FBref

This module expands upon the original scraper.py by adding support for
scraping advanced metrics from Understat and FBref.  The aim is to
augment the baseline ESPN data with expected goals (xG) and other
useful statistics when available.  Where neither Understat nor FBref
provides data for a given league or team the scraper will gracefully
fall back to ESPN‐only metrics.

Usage examples::

    python combined_scraper.py laliga
    python combined_scraper.py premier
    python combined_scraper.py all

The command line interface mirrors that of the original script.  See
the README for details.
"""

import urllib.request
import urllib.error
import json
import sys
import time
import os
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

# ---------------------------------------------------------------------------
# Constants and configuration

# ESPN league map.  We reuse this from the original scraper but keep it
# here for clarity.  Slugs correspond to ESPN's API endpoints.
LEAGUES = {
    "laliga":     {"slug": "esp.1",          "name": "LaLiga"},
    "premier":    {"slug": "eng.1",          "name": "Premier League"},
    "bundesliga": {"slug": "ger.1",          "name": "Bundesliga"},
    "seriea":     {"slug": "ita.1",          "name": "Serie A"},
    "ligue1":     {"slug": "fra.1",          "name": "Ligue 1"},
    "champions":  {"slug": "uefa.champions", "name": "Champions League"},
    "europaleague": {"slug": "uefa.europa",    "name": "Europa League"},
    "hypermotion": {"slug": "esp.2",          "name": "LaLiga Hypermotion"},
}

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

# Understat and FBref base URLs.  These sites do not provide a
# documented API, so scraping them relies on parsing HTML/JS data.
UNDERSTAT_BASE = "https://understat.com"
FBREF_BASE    = "https://fbref.com"

# HTTP headers for polite scraping.  Pretend to be a browser to
# minimise the risk of being blocked.  Adjust the User‑Agent if
# required.
COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
    "Accept":     "*/*",
    "Accept-Language": "en-US,en;q=0.8",
}

# ---------------------------------------------------------------------------
# Helper functions

def fetch_json(url, headers=None, retries=3):
    """Fetch JSON from a URL, retrying on failure.

    The optional ``headers`` argument allows callers to override the
    default headers.  Returns a Python object on success or ``None`` on
    failure.
    """
    hdrs = COMMON_HEADERS.copy()
    if headers:
        hdrs.update(headers)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError:
            if attempt < retries - 1:
                time.sleep(2)
        except Exception:
            if attempt < retries - 1:
                time.sleep(2)
    return None


def fetch_text(url, headers=None, retries=3):
    """Fetch raw text from a URL, retrying on failure.

    Use this helper for HTML or JavaScript pages.  Returns a string on
    success or ``None`` on failure.
    """
    hdrs = COMMON_HEADERS.copy()
    if headers:
        hdrs.update(headers)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode("utf-8")
        except Exception:
            if attempt < retries - 1:
                time.sleep(2)
    return None


def norm(s):
    """Normalise a team name for matching purposes.

    Strips common prefixes/suffixes and non‑alphanumeric characters
    before lowering case.  This mirrors the function in the original
    scraper and helps unify team names across disparate data sources.
    """
    s = (s or "").lower()
    s = re.sub(r'\b(fc|af|sc|ac|cd|rc|ud|ca|cf|afc|fk|sk|bv|sv|ssc|as|ss|1\.|c\.d\.|r\.c\.d\.)\b', '', s)
    s = re.sub(r'[^a-z0-9]', '', s)
    return s.strip()


def safe_float(value, default=0.0):
    """Convert a value to float if possible, returning ``default`` on failure."""
    try:
        if value in (None, "", "-"):
            return default
        return float(value)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Understat scraping

def fetch_understat_team_xg(team_name: str, season: int):
    """
    Fetch expected goals (xG) statistics for a given team and season from
    Understat.

    Understat embeds its data inside inline JavaScript on each team
    page.  The relevant information is typically stored in a JSON
    assigned to a ``data`` variable.  This function extracts that
    JSON, decodes it and aggregates xG for and against across all
    league matches.

    :param team_name: Human readable team name, e.g. "FC Barcelona".
    :param season: Four digit season start year (e.g. 2023 for the
        2023–24 season).
    :returns: A dict ``{"xg_for": float, "xg_against": float}`` or
        ``None`` if data cannot be found.  Values represent total xG
        across the season divided by the number of matches.

    The function uses the normalised team name to build a slug for the
    URL (spaces replaced with hyphens).  Some teams have special
    slugs; consider maintaining a mapping if you encounter mismatches.
    """
    # Build the team slug.  Understat uses hyphen‑separated names.
    # Example: "FC Barcelona" -> "Barcelona" or sometimes "Barcelona-2023".
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', team_name.strip()).strip('-')
    url = f"{UNDERSTAT_BASE}/team/{slug}/{season}"
    html = fetch_text(url)
    if not html:
        return None
    # Look for the JS assignment that contains JSON data.  It usually
    # appears like: "data = JSON.parse('...');".  We capture the
    # contents within the single quotes.
    m = re.search(r"data\s*=\s*JSON.parse\('([^']+)" , html)
    if not m:
        return None
    js_str = m.group(1)
    # The JSON string is encoded with escaped characters (e.g. \"), so
    # unescape it and parse.  Surround in try/catch to avoid
    # exceptions on malformed JSON.
    try:
        decoded = json.loads(js_str.encode().decode('unicode_escape'))
    except Exception:
        return None
    # The decoded structure is a list of match dictionaries.  Each item
    # contains 'xg' and 'xga' fields (expected goals for and against).
    total_for = 0.0
    total_against = 0.0
    match_count = 0
    for match in decoded:
        # Some competitions (cups) might be included; skip non‑league.
        if match.get('isResult'):
            # ``h_a" indicates home/away.  Understat stores xG in
            # different fields depending on whether the team was home or
            # away.  The keys 'xG' and 'xGA' are common across
            # examples.
            xg = safe_float(match.get('xG'))
            xga = safe_float(match.get('xGA'))
            total_for += xg
            total_against += xga
            match_count += 1
    if match_count == 0:
        return None
    return {
        "xg_for": round(total_for / match_count, 3),
        "xg_against": round(total_against / match_count, 3),
    }


# ---------------------------------------------------------------------------
# FBref scraping

def fetch_fbref_team_xg(team_name: str, season: int, comp_slug: str = None):
    """
    Fetch expected goals data for a team and season from FBref.

    FBref organises statistics by competition.  When ``comp_slug`` is
    provided (e.g. 'Big5' or '12' for LaLiga) the scraper will look for
    team shooting tables on the league page.  Otherwise it will
    attempt to infer the team page by name and season.

    This implementation provides a basic fallback: it searches for a
    shooting stats table on the league page, finds the row matching
    ``team_name`` and extracts "xG" and "xGA" columns if present.

    :param team_name: Team name as it appears on FBref.
    :param season: Four digit season start year (e.g. 2023).
    :param comp_slug: Optional FBref competition identifier.  If None,
        the function will attempt to detect the appropriate page.
    :returns: ``{"xg_for": float, "xg_against": float}`` or
        ``None`` if extraction fails.
    """
    # If comp_slug is not supplied, attempt to guess from the league
    # mapping.  Many European domestic leagues have stable IDs:
    # 9=Premier League, 12=LaLiga, 11=Serie A, 20=Bundesliga, 13=Ligue 1.
    if not comp_slug:
        # Derive from team_name heuristically; mapping can be expanded.
        lower = team_name.lower()
        if any(x in lower for x in ('real madrid', 'barcelona', 'sevilla')):
            comp_slug = '12'
        elif any(x in lower for x in ('manchester', 'liverpool', 'arsenal')):
            comp_slug = '9'
        elif any(x in lower for x in ('juventus', 'napoli', 'milan')):
            comp_slug = '11'
        elif any(x in lower for x in ('bayern', 'dortmund', 'leverkusen')):
            comp_slug = '20'
        elif any(x in lower for x in ('psg', 'monaco', 'lyon')):
            comp_slug = '13'
        else:
            return None
    # Build the league stats page URL.  FBref uses a pattern like
    # ``https://fbref.com/en/comps/{comp_slug}/{season}-{season+1}/stats`` for
    # team summary stats.  Note that FBref uses season range in the URL.
    season_range = f"{season}-{str(season + 1)[2:]}"
    url = f"{FBREF_BASE}/en/comps/{comp_slug}/{season_range}/stats"
    html = fetch_text(url)
    if not html:
        return None
    # FBref hides tables behind comments.  Remove comments so that
    # regular expressions can find the table.
    clean = re.sub(r'<!--', '', html)
    clean = re.sub(r'-->', '', clean)
    # Identify the shooting table.  The id attribute often looks like
    # "stats_squads_shooting_for" or similar.  Use a broad pattern to
    # capture all rows of the table.
    table_m = re.search(r'<table[^>]*id="stats_squads_(?:shooting|standard)_for"[^>]*>(.*?)</table>', clean, re.DOTALL | re.IGNORECASE)
    if not table_m:
        return None
    table_html = table_m.group(1)
    # Extract header row to identify xG column indices.
    headers = re.findall(r'<th[^>]*>([^<]+)</th>', table_html)
    xg_idx = None
    xga_idx = None
    for i, h in enumerate(headers):
        name = h.strip().lower()
        if name in ('xg', 'expected goals'):
            xg_idx = i
        elif name in ('xga', 'expected goals against', 'xg allowed'):
            xga_idx = i
    if xg_idx is None or xga_idx is None:
        return None
    # Find all rows in the table body and look for the team.
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL | re.IGNORECASE)
    for row in rows:
        cols = re.findall(r'<td[^>]*>([^<]*)</td>', row)
        # Some rows may have th tags for the team name.
        if not cols:
            continue
        # Look for team name separately.
        team_cell = re.search(r'<th[^>]*>(.*?)</th>', row)
        if team_cell:
            team_text = re.sub('<[^>]+>', '', team_cell.group(1)).strip().lower()
            if norm(team_text) == norm(team_name):
                # Extract xG and xGA values.
                try:
                    xg_val = safe_float(cols[xg_idx])
                    xga_val = safe_float(cols[xga_idx])
                    return {
                        "xg_for": round(xg_val, 3),
                        "xg_against": round(xga_val, 3),
                    }
                except Exception:
                    break
    return None


# ---------------------------------------------------------------------------
# ESPN enrichment functions (extracted from original scraper)

ESPN_SLUGS_PRIORITY = [
    "esp.1", "esp.2", "eng.1", "ger.1", "ita.1", "fra.1",
    "uefa.champions", "uefa.europa", "eng.2", "por.1", "ned.1"
]


def build_espn_team_index():
    """Construct a name→standing index from ESPN standings for key leagues."""
    print("  [2] Building ESPN team index (LaLiga, Hypermotion, Champions, etc.)…")
    idx = {}
    for slug in ESPN_SLUGS_PRIORITY:
        url = f"https://site.api.espn.com/apis/v2/sports/soccer/{slug}/standings"
        data = fetch_json(url)
        if not data:
            url2 = f"{ESPN_BASE}/{slug}/standings"
            data = fetch_json(url2)
        if not data:
            continue
        for entry in (data.get("standings") or {}).get("entries", []):
            team  = entry.get("team", {})
            stats = {s.get("name", ""): s.get("value", 0) for s in (entry.get("stats") or [])}
            tid   = str(team.get("id", ""))
            name  = team.get("displayName") or team.get("name") or ""
            rec = {
                "teamId": tid,
                "teamName": name,
                "position": int(stats.get("rank") or stats.get("position") or 0),
            }
            if tid:
                idx[tid] = rec
            n = norm(name)
            if n:
                idx[n] = rec
            idx[name] = rec
        time.sleep(0.2)
    print(f"  {len(idx)} entries in ESPN index")
    return idx


def fetch_espn_team_form(team_id: str, slug_priority=None):
    """Fetch recent form (results, goals for/against) for a team from ESPN."""
    if not slug_priority:
        slug_priority = ESPN_SLUGS_PRIORITY[:]
    data = None
    for slug in slug_priority:
        url = f"{ESPN_BASE}/{slug}/teams/{team_id}/schedule"
        data = fetch_json(url)
        if data and data.get("events"):
            break
        time.sleep(0.2)
    if not data:
        return []
    form = []
    for ev in (data.get("events") or []):
        status = ev.get("status", {}).get("type", {}).get("name", "")
        if status != "STATUS_FINAL":
            continue
        comp  = (ev.get("competitions") or [{}])[0]
        competitors = comp.get("competitors") or []
        my, opp = None, None
        for c in competitors:
            if str(c.get("team", {}).get("id")) == str(team_id):
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
        form.append({"r": res, "gf": my_score, "ga": opp_score, "oppId": opp.get("team", {}).get("id")})
    return form


# ---------------------------------------------------------------------------
# Combined enrichment

def enrich_with_xg(matches, team_idx, season=None):
    """
    Enrich a list of match dicts with xG data from Understat and FBref.

    This function iterates over each match in ``matches`` and attempts
    to compute average expected goals for and against for the home and
    away teams.  It first checks Understat; if that fails it falls
    back to FBref.  Results are stored under the keys ``homeXG``,
    ``awayXG``, ``homeXGA`` and ``awayXGA`` in the match dict.

    The ``season`` argument defaults to the current season (year of
    today's date).  Understat and FBref operate on season start years.
    """
    if season is None:
        today = datetime.now(tz=timezone.utc)
        # Assume European seasons start around August; if the month is
        # before July, subtract one year.
        season = today.year - (1 if today.month < 7 else 0)
    for m in matches:
        for side, prefix in [(m.get("homeTeam"), 'home'), (m.get("awayTeam"), 'away')]:
            if not side:
                continue
            name = side.get("name") or ""
            # Understat lookup
            xg_data = fetch_understat_team_xg(name, season)
            if not xg_data:
                # FBref fallback.  Derive competition slug from the ESPN team index
                rec = team_idx.get(norm(name)) or team_idx.get(name)
                comp_slug = None
                if rec:
                    # Use the league slug to guess FBref comp id.  This map can be
                    # refined with more leagues.
                    # Example mapping: esp.1 -> 12, eng.1 -> 9, ger.1 -> 20,
                    # ita.1 -> 11, fra.1 -> 13.
                    slug_to_comp = {
                        "esp.1": "12",
                        "eng.1": "9",
                        "ger.1": "20",
                        "ita.1": "11",
                        "fra.1": "13",
                    }
                    for slug, comp_id in slug_to_comp.items():
                        if slug in rec.get("teamName", "").lower() or slug in rec.get("teamId", ""):
                            comp_slug = comp_id
                            break
                xg_data = fetch_fbref_team_xg(name, season, comp_slug)
            if xg_data:
                m[f"{prefix}XG"]  = xg_data.get("xg_for")
                m[f"{prefix}XGA"] = xg_data.get("xg_against")
            else:
                m[f"{prefix}XG"]  = None
                m[f"{prefix}XGA"] = None
    return matches


# ---------------------------------------------------------------------------
# Example main routine (simplified)

def scrape_league(league_key: str):
    """
    Scrape fixtures, form and xG for a given league.

    This simplified example fetches the upcoming fixtures for
    ``league_key`` using ESPN, enriches the matches with recent form
    and xG statistics, and prints a summary.  It illustrates how the
    helper functions can be combined; it is not intended to replace
    the full functionality of the original scraper.
    """
    league = LEAGUES.get(league_key)
    if not league:
        print(f"Unknown league: {league_key}")
        return []
    slug = league['slug']
    # Fetch scoreboard (next fixtures) from ESPN
    score_url = f"{ESPN_BASE}/{slug}/scoreboard"
    data = fetch_json(score_url)
    if not data:
        print(f"Failed to fetch scoreboard for {league['name']}")
        return []
    events = data.get("events") or []
    matches = []
    for ev in events:
        comp  = (ev.get("competitions") or [{}])[0]
        home, away = None, None
        for c in (comp.get("competitors") or []):
            if c.get("homeAway") == "home":
                home = {"id": c.get("team", {}).get("id"), "name": c.get("team", {}).get("displayName")}
            else:
                away = {"id": c.get("team", {}).get("id"), "name": c.get("team", {}).get("displayName")}
        matches.append({"homeTeam": home, "awayTeam": away, "homeForm": [], "awayForm": []})
    # Build index and fetch form
    idx = build_espn_team_index()
    for m in matches:
        for side_key, form_key in [("homeTeam", "homeForm"), ("awayTeam", "awayForm")]:
            team = m.get(side_key)
            if not team:
                continue
            rec = idx.get(norm(team.get("name"))) or idx.get(team.get("name"))
            if rec:
                form = fetch_espn_team_form(rec["teamId"])
                m[form_key] = form[-6:]
            else:
                m[form_key] = []
    # Enrich with xG
    matches = enrich_with_xg(matches, idx)
    return matches


if __name__ == "__main__":
    # Very simple CLI: scrape a single league and dump JSON
    if len(sys.argv) < 2:
        print("Usage: python combined_scraper.py <league>")
        print(f"Available leagues: {', '.join(LEAGUES.keys())}")
        sys.exit(1)
    arg = sys.argv[1].lower()
    if arg == 'all':
        out = {}
        for k in LEAGUES:
            out[k] = scrape_league(k)
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        matches = scrape_league(arg)
        print(json.dumps(matches, indent=2, ensure_ascii=False))