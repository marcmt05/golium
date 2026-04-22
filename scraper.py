#!/usr/bin/env python3
"""Golium scraper bridge.

Uses the dedicated ESPN scraper internally, but preserves the JSON schema
expected by the legacy Golium frontend (data.json / quiniela.json).
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any

from engine.data_sources.espn_scraper import scrape_league as scrape_league_espn
from engine.data_sources.hybrid_scraper import scrape_league as scrape_league_hybrid
from engine.data_sources.sofascore_scraper import scrape_league as scrape_league_sofascore
from engine.data_sources.shared import LEAGUES, setup_logging

Q15_URL = "https://www.quiniela15.com/pronostico-quiniela"
Q15_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "es-ES,es;q=0.9",
}


def norm(s: str | None) -> str:
    s = (s or "").lower()
    s = re.sub(r"\b(fc|af|sc|ac|cd|rc|ud|ca|cf|afc|fk|sk|bv|sv|ssc|as|ss|1\.|c\.d\.|r\.c\.d\.)\b", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s.strip()


def fetch_html(url: str, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=Q15_HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8")
        except Exception as exc:  # noqa: BLE001
            print(f"    Error fetching {url}: {exc}")
            if attempt < retries - 1:
                time.sleep(2)
    return None


def _parse_form_letters(letters_str: str) -> list[dict[str, Any]]:
    letters = re.findall(r"[VED]", letters_str)
    return [{"r": "W" if x == "V" else ("D" if x == "E" else "L"), "gf": 0, "ga": 0} for x in letters[-6:]]


def _parse_q15_fallback(html: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    links = re.findall(r"Análisis\s+([^-]+?)\s+-\s+([^\"<\n]+)", html)
    dates = re.findall(
        r"(lunes|martes|miércoles|jueves|viernes|sábado|domingo)\s+(\d+)\s+(\w+)\s+(\d+):(\d+)",
        html,
        re.IGNORECASE,
    )
    for i, (home, away) in enumerate(links[:15]):
        date_str = f"{dates[i][1]} {dates[i][2]} {dates[i][3]}:{dates[i][4]}" if i < len(dates) else ""
        matches.append(
            {
                "num": i + 1,
                "homeTeam": {"id": None, "name": home.strip(), "rawId": None},
                "awayTeam": {"id": None, "name": away.strip(), "rawId": None},
                "date": date_str,
                "matchday": item.get("matchday") or item.get("round") or "?",
                "status": "STATUS_SCHEDULED",
                "homeScore": None,
                "awayScore": None,
                "hPos": 0,
                "aPos": 0,
                "hForm": [],
                "aForm": [],
                "q15Probs": None,
                "laeProbs": None,
                "historial": None,
            }
        )
    return matches


def scrape_quiniela_official() -> tuple[list[dict[str, Any]], str]:
    print("  Descargando partidos oficiales de quiniela15.com...")
    html = fetch_html(Q15_URL)
    if not html:
        print("  ERROR: No se pudo acceder a quiniela15.com")
        return [], "?"

    j_m = re.search(r"Jornada\s+(\d+)", html)
    jornada = j_m.group(1) if j_m else "?"
    print(f"  Jornada oficial: {jornada}")

    name_pairs = re.findall(r">Análisis\s+([^<>\-][^<>]*?)\s+-\s+([^<>]+?)<", html, re.IGNORECASE)
    name_pairs = [(h.strip(), a.strip()) for h, a in name_pairs if len(h.strip()) >= 2 and len(a.strip()) >= 2]

    clean = re.sub(r"<[^>]+>", " ", html)
    clean = re.sub(r"&nbsp;", " ", clean)
    clean = re.sub(r"&[^;]{1,6};", " ", clean)
    clean = re.sub(r"\s+", " ", clean)

    t0 = clean.find("Tabla de pronósticos")
    if t0 == -1:
        t0 = clean.find("Cierre:")
    if t0 > -1:
        clean = clean[t0:]

    all_q15 = re.findall(r"Q15[:\s]+?(\d+)%\s+(\d+)%\s+(\d+)%", clean)
    all_lae = re.findall(r"LAE[:\s]+?(\d+)%\s+(\d+)%\s+(\d+)%", clean)
    all_pos = re.findall(r"Clasificaci[oó]n[:\s]*#(\d+)", clean, re.IGNORECASE)
    all_form = re.findall(r"(?:[VED]\s+){2,5}[VED]", clean)
    all_hist = re.findall(r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+[1X]", clean)
    all_dates = re.findall(
        r"(?:lunes|martes|miércoles|jueves|viernes|sábado|domingo)\s+(\d+)\s+(\w+)\s+(\d+):(\d+)",
        clean,
        re.IGNORECASE,
    )

    matches: list[dict[str, Any]] = []
    n = min(len(name_pairs), 15)
    if n == 0:
        return _parse_q15_fallback(html), jornada

    for i in range(n):
        home, away = name_pairs[i]
        h_pos = int(all_pos[i * 2]) if len(all_pos) > i * 2 else 0
        a_pos = int(all_pos[i * 2 + 1]) if len(all_pos) > i * 2 + 1 else 0
        h_form = _parse_form_letters(all_form[i * 2]) if len(all_form) > i * 2 else []
        a_form = _parse_form_letters(all_form[i * 2 + 1]) if len(all_form) > i * 2 + 1 else []
        q15_p = {"h": int(all_q15[i][0]), "d": int(all_q15[i][1]), "a": int(all_q15[i][2])} if len(all_q15) > i else None
        lae_p = {"h": int(all_lae[i][0]), "d": int(all_lae[i][1]), "a": int(all_lae[i][2])} if len(all_lae) > i else None
        hist = None
        if len(all_hist) > i:
            hist = {
                "total": int(all_hist[i][0]),
                "h": int(all_hist[i][1]),
                "d": int(all_hist[i][2]),
                "a": int(all_hist[i][3]),
            }
        date_str = f"{all_dates[i][0]} {all_dates[i][1]} {all_dates[i][2]}:{all_dates[i][3]}" if len(all_dates) > i else ""
        matches.append(
            {
                "num": i + 1,
                "homeTeam": {"id": None, "name": home, "rawId": None},
                "awayTeam": {"id": None, "name": away, "rawId": None},
                "date": date_str,
                "matchday": jornada,
                "status": "STATUS_SCHEDULED",
                "homeScore": None,
                "awayScore": None,
                "hPos": h_pos,
                "aPos": a_pos,
                "hForm": h_form,
                "aForm": a_form,
                "q15Probs": q15_p,
                "laeProbs": lae_p,
                "historial": hist,
            }
        )
    return matches, jornada


def _convert_status(status: dict[str, Any] | None) -> str:
    if not status:
        return "STATUS_SCHEDULED"
    if status.get("completed"):
        return "STATUS_FINAL"
    state = (status.get("state") or "").lower()
    return "STATUS_FINAL" if state == "post" else "STATUS_SCHEDULED"


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, "", "-"):
            return default
        return int(float(value))
    except Exception:  # noqa: BLE001
        return default


def _standing_home_away_splits(raw_stats: dict[str, Any]) -> dict[str, int]:
    return {
        "gfHome": _to_int(raw_stats.get("homeGoalsFor") or raw_stats.get("pointsForHome") or 0),
        "gaHome": _to_int(raw_stats.get("homeGoalsAgainst") or raw_stats.get("pointsAgainstHome") or 0),
        "gfAway": _to_int(raw_stats.get("awayGoalsFor") or raw_stats.get("pointsForAway") or 0),
        "gaAway": _to_int(raw_stats.get("awayGoalsAgainst") or raw_stats.get("pointsAgainstAway") or 0),
        "wHome": _to_int(raw_stats.get("homeWins") or 0),
        "wAway": _to_int(raw_stats.get("awayWins") or 0),
    }


def convert_standings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        raw_stats = row.get("raw_stats") or {}
        out.append(
            {
                "teamId": str(row.get("team_id") or ""),
                "teamName": row.get("team_name") or row.get("team_short_name") or "",
                "position": _to_int(row.get("rank")),
                "played": _to_int(row.get("played")),
                "wins": _to_int(row.get("wins")),
                "draws": _to_int(row.get("draws")),
                "losses": _to_int(row.get("losses")),
                "gf": _to_int(row.get("goals_for")),
                "ga": _to_int(row.get("goals_against")),
                "points": _to_int(row.get("points")),
                **_standing_home_away_splits(raw_stats),
            }
        )
    return out


def convert_fixtures(rows: list[dict[str, Any]], *, matchday: str = "?") -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        status = row.get("status") or {}
        completed = bool(status.get("completed"))
        out.append(
            {
                "id": str(row.get("event_id") or ""),
                "date": row.get("date") or "",
                "matchday": row.get("matchday") or row.get("round") or matchday,
                "status": _convert_status(status),
                "homeScore": _to_int((row.get("home_team") or {}).get("score"), 0) if completed else None,
                "awayScore": _to_int((row.get("away_team") or {}).get("score"), 0) if completed else None,
                "homeTeam": {
                    "id": str((row.get("home_team") or {}).get("id") or ""),
                    "rawId": str((row.get("home_team") or {}).get("id") or ""),
                    "name": (row.get("home_team") or {}).get("name") or "",
                },
                "awayTeam": {
                    "id": str((row.get("away_team") or {}).get("id") or ""),
                    "rawId": str((row.get("away_team") or {}).get("id") or ""),
                    "name": (row.get("away_team") or {}).get("name") or "",
                },
                "venue": row.get("venue") or {},
                "round": row.get("round"),
                "winnerCode": row.get("winner_code"),
                "referee": row.get("referee"),
                "managerHome": row.get("manager_home"),
                "managerAway": row.get("manager_away"),
                "sofascore": row.get("sofascore"),
            }
        )
    return out


def convert_team_form(recent_results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    ordered = sorted(recent_results, key=lambda item: item.get("date") or "")

    for match in ordered:
        home = match.get("home_team") or {}
        away = match.get("away_team") or {}

        try:
            hg = int(home.get("score") or 0)
            ag = int(away.get("score") or 0)
        except Exception:  # noqa: BLE001
            continue

        pairs = [
            (home, away, hg, ag, True),
            (away, home, ag, hg, False),
        ]

        for side, opp, gf, ga, is_home in pairs:
            result = "W" if gf > ga else ("L" if gf < ga else "D")
            row = {
                "eventId": str(match.get("event_id") or ""),
                "oppId": str(opp.get("id") or ""),
                "oppName": opp.get("name") or "",
                "r": result,
                "gf": gf,
                "ga": ga,
                "date": match.get("date") or "",
                "home": is_home,
            }
            keys = {
                str(side.get("id") or ""),
                norm(side.get("name") or ""),
                side.get("name") or "",
            }
            for key in keys:
                if not key:
                    continue
                buckets.setdefault(str(key), []).append(row)

    for key, items in list(buckets.items()):
        buckets[key] = items[-8:]

    return buckets




def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "-", "—"):
            return default
        if isinstance(value, str):
            value = value.replace("%", "").replace(",", ".").strip()
        return float(value)
    except Exception:  # noqa: BLE001
        return default


def _get_stat_item(match: dict[str, Any], key: str) -> dict[str, Any]:
    sofascore = match.get("sofascore") or {}
    stats = (sofascore.get("statistics") or {}).get("ALL") or {}
    return stats.get(key) or {}


def _get_stat(match: dict[str, Any], key: str, side: str, default: float = 0.0) -> float:
    item = _get_stat_item(match, key)
    return _safe_float(item.get(side), default)


def _goals_completed(match: dict[str, Any]) -> tuple[int, int]:
    return _to_int((match.get("home_team") or {}).get("score"), 0), _to_int((match.get("away_team") or {}).get("score"), 0)


def _is_completed_internal(match: dict[str, Any]) -> bool:
    return bool((match.get("status") or {}).get("completed"))


def _weighted(values: list[float]) -> float:
    if not values:
        return 0.0
    weights = [i + 1 for i in range(len(values))]
    total_w = sum(weights)
    return sum(v * w for v, w in zip(values, weights)) / total_w


def _trend_label(value: float) -> str:
    if value >= 0.22:
        return "up"
    if value <= -0.22:
        return "down"
    return "steady"


def _team_profile_tags(profile: dict[str, Any], league_baselines: dict[str, float]) -> list[str]:
    tags: list[str] = []
    if profile.get("attack_index", 0) >= 1.12:
        tags.append("ofensivo")
    if profile.get("defense_index", 0) >= 1.08:
        tags.append("defensivo")
    if profile.get("home_strength", 0) >= 0.18:
        tags.append("fuerte en casa")
    if profile.get("away_weakness", 0) >= 0.12:
        tags.append("débil fuera")
    if profile.get("momentum", {}).get("score", 0) >= 0.22:
        tags.append("en forma")
    elif profile.get("momentum", {}).get("score", 0) <= -0.22:
        tags.append("mala dinámica")
    if profile.get("cards", {}).get("avg_for", 0) >= league_baselines.get("cards_for", 2.2) * 1.08:
        tags.append("tarjetero")
    if profile.get("corners", {}).get("avg_for", 0) >= league_baselines.get("corners_for", 4.7) * 1.1:
        tags.append("equipo de corners")
    if profile.get("btts_rate", 0) >= 0.62:
        tags.append("partido abierto")
    if profile.get("under35_rate", 0) >= 0.68:
        tags.append("tendencia under")
    return tags[:4]


def build_betting_models(standings: list[dict[str, Any]], recent_results: list[dict[str, Any]], fixtures: list[dict[str, Any]], team_form: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    completed = [m for m in recent_results if _is_completed_internal(m)]
    completed.sort(key=lambda x: x.get("date") or "")

    league_cards: list[float] = []
    league_corners: list[float] = []
    team_rows: dict[str, dict[str, Any]] = {}
    refs: dict[str, dict[str, Any]] = {}

    def ensure_team(team: dict[str, Any], standing: dict[str, Any] | None = None) -> dict[str, Any]:
        tid = str(team.get("id") or "")
        name = team.get("name") or (standing or {}).get("teamName") or tid
        row = team_rows.setdefault(tid or norm(name), {
            "teamId": tid or norm(name),
            "teamName": name,
            "matches": 0,
            "home_matches": 0,
            "away_matches": 0,
            "goals_for": 0.0,
            "goals_against": 0.0,
            "gf_home": 0.0,
            "ga_home": 0.0,
            "gf_away": 0.0,
            "ga_away": 0.0,
            "xg_for_vals": [],
            "xg_against_vals": [],
            "shots_for_vals": [],
            "shots_against_vals": [],
            "shots_on_target_for_vals": [],
            "shots_on_target_against_vals": [],
            "corners_for_vals": [],
            "corners_against_vals": [],
            "cards_for_vals": [],
            "cards_against_vals": [],
            "points_seq": [],
            "recent_cards_for": [],
            "recent_corners_for": [],
            "btts_count": 0,
            "over25_count": 0,
            "under35_count": 0,
        })
        if standing:
            for k in ["position","points","played","wins","draws","losses","gfHome","gaHome","gfAway","gaAway","gf","ga"]:
                row[k] = standing.get(k)
        return row

    stand_by_id = {str(r.get("teamId") or ""): r for r in standings}

    for match in completed:
        home = match.get("home_team") or {}
        away = match.get("away_team") or {}
        hg, ag = _goals_completed(match)
        hxg = _get_stat(match, "expectedGoals", "home", float(hg))
        axg = _get_stat(match, "expectedGoals", "away", float(ag))
        hshots = _get_stat(match, "totalShotsOnGoal", "home", 0.0)
        ashots = _get_stat(match, "totalShotsOnGoal", "away", 0.0)
        hsot = _get_stat(match, "shotsOnGoal", "home", 0.0)
        asot = _get_stat(match, "shotsOnGoal", "away", 0.0)
        hcorn = _get_stat(match, "cornerKicks", "home", 0.0)
        acorn = _get_stat(match, "cornerKicks", "away", 0.0)
        hyel = _get_stat(match, "yellowCards", "home", 0.0)
        ayel = _get_stat(match, "yellowCards", "away", 0.0)
        hred = _get_stat(match, "redCards", "home", 0.0)
        ared = _get_stat(match, "redCards", "away", 0.0)
        hcards = hyel + hred
        acards = ayel + ared

        league_cards.append(hcards + acards)
        league_corners.append(hcorn + acorn)

        ref = match.get("referee")
        ref_name = ref.get("name") if isinstance(ref, dict) else (str(ref) if ref else "")
        if ref_name:
            rr = refs.setdefault(ref_name, {"games": 0, "yellowCards": 0.0, "redCards": 0.0})
            rr["games"] += 1
            rr["yellowCards"] += hyel + ayel
            rr["redCards"] += hred + ared

        pairs = [
            (home, hg, ag, hxg, axg, hshots, ashots, hsot, asot, hcorn, acorn, hcards, acards, True),
            (away, ag, hg, axg, hxg, ashots, hshots, asot, hsot, acorn, hcorn, acards, hcards, False),
        ]
        for side, gf, ga, xgf, xga, shots_f, shots_a, sot_f, sot_a, cor_f, cor_a, cards_f, cards_a, is_home in pairs:
            row = ensure_team(side, stand_by_id.get(str(side.get("id") or "")))
            row["matches"] += 1
            row["goals_for"] += gf
            row["goals_against"] += ga
            row["xg_for_vals"].append(xgf)
            row["xg_against_vals"].append(xga)
            row["shots_for_vals"].append(shots_f)
            row["shots_against_vals"].append(shots_a)
            row["shots_on_target_for_vals"].append(sot_f)
            row["shots_on_target_against_vals"].append(sot_a)
            row["corners_for_vals"].append(cor_f)
            row["corners_against_vals"].append(cor_a)
            row["cards_for_vals"].append(cards_f)
            row["cards_against_vals"].append(cards_a)
            row["recent_cards_for"].append(cards_f)
            row["recent_corners_for"].append(cor_f)
            row["btts_count"] += 1 if gf > 0 and ga > 0 else 0
            row["over25_count"] += 1 if gf + ga > 2 else 0
            row["under35_count"] += 1 if gf + ga <= 3 else 0
            row["points_seq"].append(3 if gf > ga else (1 if gf == ga else 0))
            if is_home:
                row["home_matches"] += 1
                row["gf_home"] += gf
                row["ga_home"] += ga
            else:
                row["away_matches"] += 1
                row["gf_away"] += gf
                row["ga_away"] += ga

    league_avg_cards = sum(league_cards) / len(league_cards) if league_cards else 3.8
    league_avg_corners = sum(league_corners) / len(league_corners) if league_corners else 9.2
    league_avg_cards_team = league_avg_cards / 2
    league_avg_corners_team = league_avg_corners / 2

    for rr in refs.values():
        rr["avgTotal"] = round((rr["yellowCards"] + rr["redCards"]) / max(rr["games"], 1), 3)

    for team_id, standing in {str(r.get("teamId") or ""): r for r in standings}.items():
        ensure_team({"id": team_id, "name": standing.get("teamName")}, standing)

    team_profiles: dict[str, Any] = {}
    card_teams: dict[str, Any] = {}
    corner_teams: dict[str, Any] = {}
    momentum_teams: dict[str, Any] = {}
    fixture_models: dict[str, Any] = {}

    for tid, row in team_rows.items():
        matches = max(int(row.get("matches") or row.get("played") or 0), 1)
        letters = [x.get("r") if isinstance(x, dict) else x for x in (team_form.get(str(tid)) or team_form.get(norm(row.get("teamName") or "")) or [])][-6:]
        pts_seq = row["points_seq"][-6:] if row["points_seq"] else [3 if x == "W" else 1 if x == "D" else 0 for x in letters]
        half = max(1, len(pts_seq) // 2)
        old_pts = sum(pts_seq[:half])
        new_pts = sum(pts_seq[-half:])
        momentum_score = ((new_pts - old_pts) / max(half * 3, 1)) if pts_seq else 0.0
        momentum_mult = max(0.92, min(1.08, 1 + momentum_score * 0.12))
        avg_xgf = sum(row["xg_for_vals"]) / max(len(row["xg_for_vals"]), 1) if row["xg_for_vals"] else (row["goals_for"] / matches)
        avg_xga = sum(row["xg_against_vals"]) / max(len(row["xg_against_vals"]), 1) if row["xg_against_vals"] else (row["goals_against"] / matches)
        attack_index = avg_xgf / 1.15 if avg_xgf else 1.0
        defense_index = max(0.7, min(1.3, 1.25 - (avg_xga / 1.1 if avg_xga else 1.0) * 0.25))
        home_strength = ((row.get("gf_home") or 0) / max(row.get("home_matches") or 1, 1) - (row.get("ga_home") or 0) / max(row.get("home_matches") or 1, 1))
        away_weakness = ((row.get("ga_away") or 0) / max(row.get("away_matches") or 1, 1) - (row.get("gf_away") or 0) / max(row.get("away_matches") or 1, 1))
        profile = {
            "teamId": tid,
            "teamName": row.get("teamName"),
            "position": row.get("position"),
            "points": row.get("points"),
            "played": row.get("played") or matches,
            "goals": {
                "avg_for": round((row.get("goals_for") or 0) / matches, 3),
                "avg_against": round((row.get("goals_against") or 0) / matches, 3),
                "avg_home_for": round((row.get("gf_home") or 0) / max(row.get("home_matches") or 1, 1), 3),
                "avg_home_against": round((row.get("ga_home") or 0) / max(row.get("home_matches") or 1, 1), 3),
                "avg_away_for": round((row.get("gf_away") or 0) / max(row.get("away_matches") or 1, 1), 3),
                "avg_away_against": round((row.get("ga_away") or 0) / max(row.get("away_matches") or 1, 1), 3),
            },
            "xg": {"avg_for": round(avg_xgf, 3), "avg_against": round(avg_xga, 3)},
            "shots": {
                "avg_for": round(sum(row["shots_for_vals"]) / max(len(row["shots_for_vals"]), 1), 3),
                "avg_against": round(sum(row["shots_against_vals"]) / max(len(row["shots_against_vals"]), 1), 3),
                "sot_for": round(sum(row["shots_on_target_for_vals"]) / max(len(row["shots_on_target_for_vals"]), 1), 3),
                "sot_against": round(sum(row["shots_on_target_against_vals"]) / max(len(row["shots_on_target_against_vals"]), 1), 3),
            },
            "corners": {
                "avg_for": round(sum(row["corners_for_vals"]) / max(len(row["corners_for_vals"]), 1), 3),
                "avg_against": round(sum(row["corners_against_vals"]) / max(len(row["corners_against_vals"]), 1), 3),
                "recent_for": round(_weighted(row["recent_corners_for"][-5:]), 3),
            },
            "cards": {
                "avg_for": round(sum(row["cards_for_vals"]) / max(len(row["cards_for_vals"]), 1), 3),
                "avg_against": round(sum(row["cards_against_vals"]) / max(len(row["cards_against_vals"]), 1), 3),
                "recent_for": round(_weighted(row["recent_cards_for"][-5:]), 3),
            },
            "btts_rate": round((row.get("btts_count") or 0) / matches, 3),
            "over25_rate": round((row.get("over25_count") or 0) / matches, 3),
            "under35_rate": round((row.get("under35_count") or 0) / matches, 3),
            "momentum": {"score": round(momentum_score, 3), "label": _trend_label(momentum_score), "mult": round(momentum_mult, 3), "form": letters},
            "attack_index": round(attack_index, 3),
            "defense_index": round(defense_index, 3),
            "home_strength": round(home_strength, 3),
            "away_weakness": round(away_weakness, 3),
        }
        profile["tags"] = _team_profile_tags(profile, {"cards_for": league_avg_cards_team, "corners_for": league_avg_corners_team})
        team_profiles[str(tid)] = profile
        if row.get("teamName"):
            team_profiles[norm(row["teamName"])] = profile
        card_team = {"avgFor": profile["cards"]["avg_for"], "avgAgainst": profile["cards"]["avg_against"], "recentFor": profile["cards"]["recent_for"], "recentAgainst": profile["cards"]["avg_against"], "formTrend": profile["momentum"]["score"]}
        corner_team = {"avgFor": profile["corners"]["avg_for"], "avgAgainst": profile["corners"]["avg_against"], "recentFor": profile["corners"]["recent_for"], "recentAgainst": profile["corners"]["avg_against"], "formTrend": profile["momentum"]["score"]}
        card_teams[str(tid)] = card_team
        corner_teams[str(tid)] = corner_team
        if row.get("teamName"):
            card_teams[norm(row["teamName"])] = card_team
            corner_teams[norm(row["teamName"])] = corner_team
            momentum_teams[norm(row["teamName"])] = profile["momentum"]
        momentum_teams[str(tid)] = profile["momentum"]

    def profile_for(team: dict[str, Any]) -> dict[str, Any] | None:
        tid = str(team.get("id") or "")
        return team_profiles.get(tid) or team_profiles.get(norm(team.get("name") or ""))

    for fix in fixtures:
        home = fix.get("home_team") or {}
        away = fix.get("away_team") or {}
        hp = profile_for(home)
        ap = profile_for(away)
        if not hp or not ap:
            continue
        h_cards = hp["cards"]["avg_for"] * 0.6 + hp["cards"]["recent_for"] * 0.4 + ap["cards"]["avg_against"] * 0.25
        a_cards = ap["cards"]["avg_for"] * 0.6 + ap["cards"]["recent_for"] * 0.4 + hp["cards"]["avg_against"] * 0.25
        p_home_card = max(0.05, min(0.96, 1 - math.exp(-max(0.05, h_cards))))
        p_away_card = max(0.05, min(0.96, 1 - math.exp(-max(0.05, a_cards))))
        both_cards = max(0.03, min(0.95, p_home_card * p_away_card))
        h_corners = hp["corners"]["avg_for"] * 0.6 + hp["corners"]["recent_for"] * 0.4 + ap["corners"]["avg_against"] * 0.2
        a_corners = ap["corners"]["avg_for"] * 0.6 + ap["corners"]["recent_for"] * 0.4 + hp["corners"]["avg_against"] * 0.2
        total_corners = max(3.0, min(18.0, h_corners + a_corners))
        over85 = max(0.05, min(0.98, 1 / (1 + math.exp(-(total_corners - 8.5) / 1.25))))
        over95 = max(0.03, min(0.97, 1 / (1 + math.exp(-(total_corners - 9.5) / 1.35))))
        tags = list(dict.fromkeys((hp.get("tags") or []) + (ap.get("tags") or [])))[:6]
        fixture_models[str(fix.get("event_id") or "")] = {
            "homeCards": round(h_cards, 3),
            "awayCards": round(a_cards, 3),
            "bothTeamsCardProb": round(both_cards, 3),
            "homeCardProb": round(p_home_card, 3),
            "awayCardProb": round(p_away_card, 3),
            "homeCorners": round(h_corners, 3),
            "awayCorners": round(a_corners, 3),
            "totalCorners": round(total_corners, 3),
            "over85CornersProb": round(over85, 3),
            "over95CornersProb": round(over95, 3),
            "under95CornersProb": round(1 - over95, 3),
            "momentumDelta": round(hp["momentum"]["score"] - ap["momentum"]["score"], 3),
            "tags": tags,
        }

    return {
        "cardModel": {"leagueAvgTotal": round(league_avg_cards, 3), "teams": card_teams, "referees": refs, "fixtures": fixture_models},
        "cornerModel": {"leagueAvgTotal": round(league_avg_corners, 3), "teams": corner_teams, "fixtures": fixture_models},
        "momentumModel": {"teams": momentum_teams, "fixtures": {k: {"momentumDelta": v.get("momentumDelta"), "tags": v.get("tags")} for k, v in fixture_models.items()}},
        "teamProfiles": team_profiles,
        "autoTags": {k: v.get("tags", []) for k, v in fixture_models.items()},
    }

def convert_league_payload(new_payload: dict[str, Any], league_key: str) -> dict[str, Any]:
    standings = convert_standings(new_payload.get("standings") or [])
    fixtures = convert_fixtures(new_payload.get("fixtures") or [])
    recent_results = convert_fixtures(new_payload.get("recent_results") or [])
    team_form = convert_team_form(new_payload.get("recent_results") or [])
    models = build_betting_models(standings, new_payload.get("recent_results") or [], new_payload.get("fixtures") or [], team_form)

    return {
        "league": new_payload.get("league_name") or LEAGUES[league_key]["name"],
        "leagueKey": league_key,
        "leagueSlug": new_payload.get("league_slug") or LEAGUES[league_key]["slug"],
        "source": new_payload.get("source") or "ESPN",
        "scrapedAt": new_payload.get("scraped_at") or datetime.now(timezone.utc).isoformat(),
        "fixtures": fixtures,
        "standings": standings,
        "teamForm": team_form,
        "cardModel": models["cardModel"],
        "cornerModel": models["cornerModel"],
        "momentumModel": models["momentumModel"],
        "teamProfiles": models["teamProfiles"],
        "autoTags": models["autoTags"],
        "recentResults": recent_results,
        "meta": new_payload.get("meta") or {},
        "teamMetrics": new_payload.get("team_metrics") or {},
    }


def scrape_normal(league_key: str, mode: str = "hybrid") -> dict[str, Any] | None:
    print(f"\n{'=' * 55}")
    print(f"  {LEAGUES[league_key]['name']}  ({LEAGUES[league_key]['slug']})")
    print(f"{'=' * 55}")

    try:
        raw_base = os.path.join(os.path.dirname(__file__), "output", "raw")
        if mode == "espn":
            payload = scrape_league_espn(
                league_key,
                output_dir=os.path.join(raw_base, "espn"),
            )
        elif mode == "sofascore":
            payload = scrape_league_sofascore(
                league_key,
                output_dir=os.path.join(raw_base, "sofascore"),
            )
        else:
            payload = scrape_league_hybrid(
                league_key,
                output_dir=os.path.join(raw_base, "hybrid"),
                espn_output_dir=os.path.join(raw_base, "espn"),
                sofascore_output_dir=os.path.join(raw_base, "sofascore"),
            )
        converted = convert_league_payload(payload, league_key)
        print(f"  Equipos: {len(converted['standings'])}")
        print(f"  Fixtures: {len(converted['fixtures'])}")
        print(f"  Históricos: {len(converted['recentResults'])}")
        print(f"  FormKeys: {len(converted['teamForm'])}")
        return converted
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR scraping {league_key}: {exc}")
        return None


def scrape_quiniela() -> dict[str, Any] | None:
    print(f"\n{'=' * 55}")
    print("  🎯 QUINIELA OFICIAL — quiniela15.com")
    print(f"{'=' * 55}")

    matches, jornada = scrape_quiniela_official()
    if not matches:
        return None

    standings_out: list[dict[str, Any]] = []
    team_form: dict[str, list[dict[str, Any]]] = {}
    seen: set[str] = set()

    for league_key in LEAGUES:
        league_data = scrape_normal(league_key)
        if not league_data:
            continue

        idx: dict[str, dict[str, Any]] = {}
        for row in league_data.get("standings", []):
            team_id = str(row.get("teamId") or "")
            team_name = row.get("teamName") or ""
            idx[team_id] = row
            idx[norm(team_name)] = row
            idx[team_name] = row

        for match in matches:
            for side_key, form_key, pos_key in [
                ("homeTeam", "hForm", "hPos"),
                ("awayTeam", "aForm", "aPos"),
            ]:
                side = match[side_key]
                lookup = idx.get(norm(side.get("name") or "")) or idx.get(side.get("name") or "")
                if not lookup:
                    continue

                side["id"] = lookup.get("teamId")
                side["rawId"] = lookup.get("teamId")

                if not match.get(pos_key):
                    match[pos_key] = lookup.get("position", 0)

                tid = str(lookup.get("teamId") or "")
                if tid and tid not in seen:
                    seen.add(tid)
                    standings_out.append(lookup)

                if not match.get(form_key):
                    form_rows = (
                        league_data.get("teamForm", {}).get(tid)
                        or league_data.get("teamForm", {}).get(norm(side.get("name") or ""))
                        or []
                    )
                    match[form_key] = form_rows[-6:]

                if tid and tid in league_data.get("teamForm", {}):
                    team_form[tid] = league_data["teamForm"][tid]

                nkey = norm(side.get("name") or "")
                if nkey and nkey in league_data.get("teamForm", {}):
                    team_form[nkey] = league_data["teamForm"][nkey]

    for match in matches:
        for side_key, form_key in [("homeTeam", "hForm"), ("awayTeam", "aForm")]:
            side = match[side_key]
            tid = str(side.get("id") or "")
            nkey = norm(side.get("name") or "")
            if match.get(form_key):
                if tid:
                    team_form.setdefault(tid, match[form_key])
                if nkey:
                    team_form.setdefault(nkey, match[form_key])

    return {
        "league": "Quiniela oficial",
        "leagueKey": "quiniela",
        "source": "quiniela15 + ESPN",
        "scrapedAt": datetime.now(timezone.utc).isoformat(),
        "jornada": jornada,
        "fixtures": matches,
        "standings": standings_out,
        "teamForm": team_form,
        "cardModel": {"leagueAvgTotal": 3.8, "teams": {}, "referees": {}, "fixtures": {}},
    }


def main() -> int:
    setup_logging()
    args = sys.argv[1:]

    if not args:
        print("Uso: python scraper.py [liga|all|quiniela] [hybrid|espn|sofascore]")
        print("Ligas:", ", ".join(sorted(LEAGUES)))
        return 0

    target = args[0].lower()
    mode = args[1].lower() if len(args) > 1 else "hybrid"
    if mode not in {"hybrid", "espn", "sofascore"}:
        print("Modo inválido. Usa: hybrid, espn, sofascore")
        return 1
    if target not in LEAGUES and target not in {"all", "quiniela"}:
        print(f"Opción inválida. Usa: {', '.join(sorted(LEAGUES))}, all, quiniela")
        return 1

    if target == "quiniela":
        output = scrape_quiniela()
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quiniela.json")

    elif target == "all":
        results: dict[str, Any] = {}
        errors: dict[str, str] = {}

        for key in LEAGUES:
            data = scrape_normal(key, mode)
            if data:
                results[key] = data
            else:
                errors[key] = "scrape failed"

        output = {
            "leagues": results,
            "errors": errors,
            "scrapedAt": datetime.now(timezone.utc).isoformat(),
        } if results else None

        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

    else:
        output = scrape_normal(target, mode)
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

    if not output:
        print("No se obtuvo ningún dato.")
        return 1

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)

    print(f"\n✅ Guardado: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())