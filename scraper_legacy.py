#!/usr/bin/env python3
"""
Golium — Scraper v5
Quiniela: partidos OFICIALES desde quiniela15.com (jornada real de SELAE)
Análisis: ESPN Hidden API para LaLiga, Premier, etc.

Uso:
  python scraper.py quiniela        <- Partidos REALES de la quiniela SELAE
  python scraper.py laliga
  python scraper.py premier
  python scraper.py bundesliga
  python scraper.py seriea
  python scraper.py ligue1
  python scraper.py all
"""

import urllib.request, urllib.error, json, sys, time, os, re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

# ─────────────────────────────────────────
LEAGUES = {
    "laliga":     {"slug": "esp.1",          "name": "LaLiga"},
    "premier":    {"slug": "eng.1",          "name": "Premier League"},
    "bundesliga": {"slug": "ger.1",          "name": "Bundesliga"},
    "seriea":     {"slug": "ita.1",          "name": "Serie A"},
    "ligue1":     {"slug": "fra.1",          "name": "Ligue 1"},
    "champions":  {"slug": "uefa.champions", "name": "Champions League"},
    "europaleague": {"slug": "uefa.europa",    "name": "Europa League"},
    "hypermotion":{"slug": "esp.2",          "name": "LaLiga Hypermotion"},
}

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
Q15_URL   = "https://www.quiniela15.com/pronostico-quiniela"

ESPN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
    "Accept":     "application/json",
    "Referer":    "https://www.espn.com/soccer/",
}
Q15_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
    "Accept":     "text/html,application/xhtml+xml",
    "Accept-Language": "es-ES,es;q=0.9",
}

# ─────────────────────────────────────────
def fetch_json(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=ESPN_HEADERS)
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if attempt < retries - 1: time.sleep(2)
        except Exception as e:
            print(f"    Error: {e}")
            if attempt < retries - 1: time.sleep(2)
    return None

def fetch_html(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=Q15_HEADERS)
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode("utf-8")
        except Exception as e:
            print(f"    Error fetching {url}: {e}")
            if attempt < retries - 1: time.sleep(2)
    return None

def norm(s):
    s = (s or "").lower()
    s = re.sub(r'\b(fc|af|sc|ac|cd|rc|ud|ca|cf|afc|fk|sk|bv|sv|ssc|as|ss|1\.|c\.d\.|r\.c\.d\.)\b', '', s)
    s = re.sub(r'[^a-z0-9]', '', s)
    return s.strip()


def _num(v, default=0.0):
    try:
        if v in (None, "", "-"):
            return default
        return float(v)
    except Exception:
        return default

def _safe_name(x):
    return (x or "").strip()

def _extract_stat_num(stat):
    if isinstance(stat, (int, float)):
        return float(stat)
    if isinstance(stat, str):
        return _num(stat, 0.0)
    if not isinstance(stat, dict):
        return 0.0
    for key in ("value", "displayValue", "displayValueShort", "stat"):
        if key in stat:
            raw = stat.get(key)
            if isinstance(raw, str):
                m = re.search(r"-?\d+(?:\.\d+)?", raw.replace(",", "."))
                if m:
                    return float(m.group(0))
            elif isinstance(raw, (int, float)):
                return float(raw)
    return 0.0

def _extract_cards_from_stats(stats):
    yellow = 0.0
    red = 0.0
    if not isinstance(stats, list):
        return 0.0
    for st in stats:
        if not isinstance(st, dict):
            continue
        keys = " ".join(str(st.get(k, "")) for k in ("name", "displayName", "shortDisplayName", "abbreviation")).lower()
        val = _extract_stat_num(st)
        if "yellow" in keys or "amar" in keys:
            yellow = max(yellow, val)
        elif "red" in keys or "roja" in keys:
            red = max(red, val)
        elif ("card" in keys or "tarjet" in keys) and val > 0:
            # Si solo hay "cards" total, úsalo como fallback
            yellow = max(yellow, val)
    return max(0.0, yellow + red)

def _extract_ref_name(data):
    candidates = []
    for path in [
        (((data or {}).get("gameInfo") or {}).get("officials") or []),
        (((data or {}).get("officials")) or []),
        ((((data or {}).get("header") or {}).get("competitions") or [{}])[0].get("officials") or []),
        ((((data or {}).get("boxscore") or {}).get("officials")) or []),
    ]:
        candidates.extend(path if isinstance(path, list) else [])
    for off in candidates:
        if not isinstance(off, dict):
            continue
        role = " ".join(str(off.get(k, "")) for k in ("position", "type", "displayName", "shortDisplayName")).lower()
        if any(x in role for x in ("referee", "árbitro", "arbitro", "principal")) or not role:
            for k in ("displayName", "fullName", "name", "shortName"):
                name = _safe_name(off.get(k))
                if name:
                    return name
            athlete = off.get("athlete") or {}
            for k in ("displayName", "fullName", "name", "shortName"):
                name = _safe_name(athlete.get(k))
                if name:
                    return name
    return ""

def get_event_card_summary(slug, event_id):
    urls = [
        f"{ESPN_BASE}/{slug}/summary?event={event_id}",
        f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/summary?event={event_id}",
    ]
    data = None
    for url in urls:
        data = fetch_json(url)
        if data:
            break
        time.sleep(0.15)
    if not data:
        return None

    team_cards = {}
    # 1) boxscore.teams suele tener statistics por equipo
    for team_block in (((data.get("boxscore") or {}).get("teams")) or []):
        team = team_block.get("team") or {}
        tid = str(team.get("id") or "")
        stats = team_block.get("statistics") or []
        cards = _extract_cards_from_stats(stats)
        if tid:
            team_cards[tid] = cards

    # 2) fallback: competitions[0].competitors[].statistics
    if len(team_cards) < 2:
        comp = ((data.get("header") or {}).get("competitions") or [{}])[0]
        for side in (comp.get("competitors") or []):
            team = side.get("team") or {}
            tid = str(team.get("id") or "")
            stats = side.get("statistics") or []
            cards = _extract_cards_from_stats(stats)
            if tid and cards > 0:
                team_cards[tid] = cards

    ref_name = _extract_ref_name(data)
    total = sum(team_cards.values()) if team_cards else 0.0
    return {
        "eventId": str(event_id),
        "refName": ref_name,
        "teamCards": team_cards,
        "totalCards": total,
    }

def _weighted_recent_avg(values):
    if not values:
        return 0.0
    vals = values[-5:]
    weights = [0.55, 0.7, 0.85, 1.0, 1.15][-len(vals):]
    num = sum(v * w for v, w in zip(vals, weights))
    den = sum(weights) or 1.0
    return num / den

def build_card_model(slug, teams_to_fetch, form_map):
    event_ids = []
    seen_events = set()
    for t in teams_to_fetch:
        tid = str(t.get("fetchId") or t.get("id") or t.get("rawId") or "")
        for row in form_map.get(tid, [])[-8:]:
            eid = str(row.get("eventId") or "")
            if eid and eid not in seen_events:
                seen_events.add(eid)
                event_ids.append(eid)

    if not event_ids:
        return {"leagueAvgTotal": 3.8, "teams": {}, "referees": {}, "fixtures": {}}

    print(f"  [4] Tarjetas y árbitros ({len(event_ids)} partidos históricos)...")
    event_cache = {}
    referee_totals = {}
    league_totals = []

    for i, eid in enumerate(event_ids, start=1):
        sys.stdout.write(f"\r    Resumen tarjetas {i}/{len(event_ids)}...  ")
        sys.stdout.flush()
        info = get_event_card_summary(slug, eid)
        if not info:
            continue
        event_cache[eid] = info
        if info.get("totalCards", 0) > 0:
            league_totals.append(info["totalCards"])
        ref = info.get("refName", "")
        if ref and info.get("totalCards", 0) > 0:
            referee_totals.setdefault(ref, []).append(info["totalCards"])
        time.sleep(0.12)
    sys.stdout.write("\r" + " " * 60 + "\r")

    league_avg_total = round(sum(league_totals) / max(len(league_totals), 1), 3) if league_totals else 3.8

    teams_out = {}
    for t in teams_to_fetch:
        tid = str(t.get("fetchId") or t.get("id") or t.get("rawId") or "")
        name = t.get("name", "")
        rows = form_map.get(tid, [])[-8:]
        vals_for, vals_against = [], []
        for row in rows:
            eid = str(row.get("eventId") or "")
            opp = str(row.get("oppId") or "")
            ev = event_cache.get(eid)
            if not ev:
                continue
            my_cards = ev["teamCards"].get(tid)
            opp_cards = ev["teamCards"].get(opp)
            if my_cards is None:
                continue
            vals_for.append(float(my_cards))
            vals_against.append(float(opp_cards if opp_cards is not None else max(ev.get("totalCards", 0) - my_cards, 0)))

        n = len(vals_for)
        avg_for = round(sum(vals_for) / n, 3) if n else round(league_avg_total / 2, 3)
        avg_against = round(sum(vals_against) / max(len(vals_against), 1), 3) if vals_against else round(league_avg_total / 2, 3)
        recent_for = round(_weighted_recent_avg(vals_for), 3) if vals_for else avg_for
        recent_against = round(_weighted_recent_avg(vals_against), 3) if vals_against else avg_against
        form_trend = 0.0
        if n >= 4:
            half = max(2, n // 2)
            old = vals_for[:-half] or vals_for[:half]
            new = vals_for[-half:]
            old_avg = sum(old) / max(len(old), 1)
            new_avg = sum(new) / max(len(new), 1)
            form_trend = round(max(-0.18, min(0.18, (new_avg - old_avg) / max(league_avg_total / 2, 0.8) * 0.18)), 4)

        payload = {
            "teamId": tid,
            "teamName": name,
            "n": n,
            "avgFor": avg_for,
            "avgAgainst": avg_against,
            "recentFor": recent_for,
            "recentAgainst": recent_against,
            "formTrend": form_trend,
        }
        for key in {tid, str(t.get("id") or ""), str(t.get("rawId") or ""), name, norm(name)}:
            if key and key != "None":
                teams_out[key] = payload

    referees_out = {
        name: {"avgTotal": round(sum(vals) / len(vals), 3), "n": len(vals)}
        for name, vals in referee_totals.items() if vals
    }

    fixtures_out = {}
    for eid, ev in event_cache.items():
        ref_name = ev.get("refName", "")
        ref_avg = referees_out.get(ref_name, {}).get("avgTotal", league_avg_total)
        fixtures_out[eid] = {
            "refName": ref_name,
            "refAvgTotal": round(ref_avg, 3),
            "totalCards": round(ev.get("totalCards", 0.0), 3),
        }

    print(f"    Tarjetas OK · teams={len({v['teamId'] for v in teams_out.values() if isinstance(v, dict) and v.get('teamId')})} refs={len(referees_out)}")
    return {
        "leagueAvgTotal": league_avg_total,
        "teams": teams_out,
        "referees": referees_out,
        "fixtures": fixtures_out,
    }

# ═══════════════════════════════════════════════════════
#  QUINIELA SCRAPER — lee quiniela15.com
# ═══════════════════════════════════════════════════════
def scrape_quiniela_official():
    """
    Extrae los 15 partidos oficiales de la quiniela actual desde quiniela15.com
    Estrategia: parse >Análisis X - Y< desde HTML crudo (siempre limpio)
    """
    print("  Descargando partidos oficiales de quiniela15.com...")
    html = fetch_html(Q15_URL)
    if not html:
        print("  ERROR: No se pudo acceder a quiniela15.com")
        return [], "?"

    # Jornada
    j_m = re.search(r'Jornada\s+(\d+)', html)
    jornada = j_m.group(1) if j_m else "?"
    print(f"  Jornada oficial: {jornada}")

    bote_m = re.search(r'Bote[:\s]+([0-9.,]+\s*€)', html)
    bote   = bote_m.group(1).strip() if bote_m else None
    if bote: print(f"  Bote: {bote}")

    # ── STEP 1: Nombres limpios desde anchor text ">Análisis X - Y<" ──
    # Estos siempre son nombres correctos, nunca tienen basura HTML
    name_pairs = re.findall(
        r'>Análisis\s+([^<>\-][^<>]*?)\s+-\s+([^<>]+?)<',
        html, re.IGNORECASE
    )
    # Limpiar espacios extra
    name_pairs = [(h.strip(), a.strip()) for h, a in name_pairs
                  if len(h.strip()) >= 2 and len(a.strip()) >= 2]
    print(f"  Nombres limpios encontrados: {len(name_pairs)}")

    # ── STEP 2: Contexto por partido (texto limpio) ───────────────────
    clean = re.sub(r'<[^>]+>', ' ', html)
    clean = re.sub(r'&nbsp;', ' ', clean)
    clean = re.sub(r'&[^;]{1,6};', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean)

    # Localizar sección tabla
    t0 = clean.find('Tabla de pronósticos')
    if t0 == -1: t0 = clean.find('Cierre:')
    if t0 > -1: clean = clean[t0:]

    # Encontrar posiciones de cada análisis en el texto limpio
    # para extraer contexto (forma, posición, probs) de cada partido
    anchors = [m.start() for m in re.finditer(r'Análisis\s+', clean, re.IGNORECASE)]

    # ── STEP 3: Extraer probs de LAE/Q15 del texto completo ──────────
    # El HTML tiene un bloque por partido con Q15/LAE/APU probs
    # Buscamos todos los bloques "Q15: N% N% N%"
    all_q15 = re.findall(r'Q15[:\s]+?(\d+)%\s+(\d+)%\s+(\d+)%', clean)
    all_lae = re.findall(r'LAE[:\s]+?(\d+)%\s+(\d+)%\s+(\d+)%', clean)

    # ── STEP 4: Extraer posiciones y forma ───────────────────────────
    # Patrón: "Clasificación: #N"
    all_pos  = re.findall(r'Clasificaci[oó]n[:\s]*#(\d+)', clean, re.IGNORECASE)
    # Forma: secuencias de V E D
    all_form = re.findall(r'(?:[VED]\s+){2,5}[VED]', clean)
    # Historial entre equipos: números antes del signo recomendado
    all_hist = re.findall(r'(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+[1X]', clean)
    # Fechas
    all_dates = re.findall(
        r'(?:lunes|martes|miércoles|jueves|viernes|sábado|domingo)\s+(\d+)\s+(\w+)\s+(\d+):(\d+)',
        clean, re.IGNORECASE
    )

    def parse_form(letters_str):
        letters = re.findall(r'[VED]', letters_str)
        return [{'r': 'W' if x=='V' else ('D' if x=='E' else 'L')} for x in letters[-6:]]

    matches = []
    n = min(len(name_pairs), 15)
    if n == 0:
        print("  WARN: No se encontraron parejas de nombres. Usando fallback...")
        return _parse_q15_fallback(html), jornada

    for i in range(n):
        home, away = name_pairs[i]

        # Posición local y visita (pares consecutivos: local idx 2i, visita idx 2i+1)
        h_pos = int(all_pos[i*2])     if len(all_pos)   > i*2     else 0
        a_pos = int(all_pos[i*2+1])   if len(all_pos)   > i*2+1   else 0

        # Forma: pares consecutivos
        h_form = parse_form(all_form[i*2])   if len(all_form) > i*2   else []
        a_form = parse_form(all_form[i*2+1]) if len(all_form) > i*2+1 else []

        # Probs
        q15_p = {"h": int(all_q15[i][0]), "d": int(all_q15[i][1]), "a": int(all_q15[i][2])} if len(all_q15) > i else None
        lae_p = {"h": int(all_lae[i][0]), "d": int(all_lae[i][1]), "a": int(all_lae[i][2])} if len(all_lae) > i else None

        # Historial
        hist = None
        if len(all_hist) > i:
            hist = {"total": int(all_hist[i][0]), "h": int(all_hist[i][1]),
                    "d": int(all_hist[i][2]),     "a": int(all_hist[i][3])}

        # Fecha
        date_str = ""
        if len(all_dates) > i:
            d = all_dates[i]
            date_str = f"{d[0]} {d[1]} {d[2]}:{d[3]}"

        matches.append({
            "num":       i + 1,
            "homeTeam":  {"id": None, "name": home, "rawId": None},
            "awayTeam":  {"id": None, "name": away, "rawId": None},
            "date":      date_str,
            "matchday":  jornada,
            "status":    "STATUS_SCHEDULED",
            "homeScore": None,
            "awayScore": None,
            "hPos":      h_pos,
            "aPos":      a_pos,
            "hForm":     h_form,
            "aForm":     a_form,
            "q15Probs":  q15_p,
            "laeProbs":  lae_p,
            "historial": hist,
        })
        print(f"    {i+1:2d}. {home:20s} vs {away:20s}  pos:{h_pos}/{a_pos}  form:{len(h_form)}/{len(a_form)}  lae:{lae_p}")

    print(f"  {len(matches)} partidos extraídos")
    return matches, jornada


def _parse_q15_fallback(html):
    """Fallback parser using different approach."""
    matches = []
    # Look for the "análisis" links which contain team names
    links = re.findall(r'Análisis\s+([^-]+?)\s+-\s+([^"<\n]+)', html)
    dates = re.findall(r'(lunes|martes|miércoles|jueves|viernes|sábado|domingo)\s+(\d+)\s+(\w+)\s+(\d+):(\d+)', html, re.IGNORECASE)

    for i, (home, away) in enumerate(links[:15]):
        date_str = f"{dates[i][1]} {dates[i][2]} {dates[i][3]}:{dates[i][4]}" if i < len(dates) else ""
        matches.append({
            "num":       i + 1,
            "homeTeam":  {"id": None, "name": home.strip(), "rawId": None},
            "awayTeam":  {"id": None, "name": away.strip(), "rawId": None},
            "date":      date_str,
            "matchday":  "?",
            "status":    "STATUS_SCHEDULED",
            "homeScore": None,
            "awayScore": None,
            "hPos":0,"aPos":0,"hForm":[],"aForm":[],
            "q15Probs":None,"laeProbs":None,"historial":None,
        })
    return matches

# ═══════════════════════════════════════════════════════
#  ESPN STATS ENRICHMENT
#  Para cada equipo de la quiniela, busca sus stats en ESPN
# ═══════════════════════════════════════════════════════

# Mapa de ligas para buscar equipos
ESPN_SLUGS_PRIORITY = ["esp.1", "esp.2", "eng.1", "ger.1", "ita.1", "fra.1",
                        "uefa.champions", "uefa.europa", "eng.2", "por.1", "ned.1"]

def build_espn_team_index():
    """
    Construye un índice global name→standing scrapeando las principales ligas.
    Solo se hace una vez.
    """
    print("  [2] Construyendo índice de equipos ESPN (LaLiga + Hypermotion + Champions + Europa League)...")
    # Para la quiniela española, solo necesitamos esp.1 y esp.2
    # Si hay partidos de otras ligas, añadiremos más
    all_standings = {}

    for slug in ["esp.1", "esp.2", "eng.1", "ger.1", "ita.1", "fra.1", "uefa.champions", "uefa.europa"]:
        data = fetch_json(f"https://site.api.espn.com/apis/v2/sports/soccer/{slug}/standings")
        if not data:
            data = fetch_json(f"{ESPN_BASE}/{slug}/standings")
        if not data:
            continue

        rows = _extract_standing_entries(data)
        for r in rows:
            tid   = str(r.get("teamId",""))
            tname = r.get("teamName","")
            n     = norm(tname)
            if tid: all_standings[tid] = r
            if n:   all_standings[n]   = r
            if tname: all_standings[tname] = r
        time.sleep(0.3)

    print(f"  {len(all_standings)} entradas en índice ESPN")
    return all_standings

def _extract_standing_entries(raw):
    rows = []
    entries = (raw.get("standings") or {}).get("entries", [])
    if not entries:
        for child in (raw.get("children") or []):
            entries.extend((child.get("standings") or {}).get("entries", []))

    for row in entries:
        team  = row.get("team") or {}
        stats = {s.get("name",""): s.get("value",0) for s in (row.get("stats") or [])}
        tid   = str(team.get("id",""))
        tname = team.get("displayName") or team.get("name") or ""
        pos   = int(stats.get("rank") or stats.get("position") or 0)
        rows.append({
            "teamId":   tid,
            "teamName": tname,
            "position": pos,
            "played":   int(stats.get("gamesPlayed") or stats.get("played") or 0),
            "wins":     int(stats.get("wins") or 0),
            "draws":    int(stats.get("ties") or stats.get("draws") or 0),
            "losses":   int(stats.get("losses") or 0),
            "gf":       int(stats.get("pointsFor") or stats.get("goalsFor") or 0),
            "ga":       int(stats.get("pointsAgainst") or stats.get("goalsAgainst") or 0),
            "points":   int(stats.get("points") or 0),
            # Home/Away split (ESPN provides these in some standing formats)
            "gfHome":   int(stats.get("homeGoalsFor")   or stats.get("pointsForHome")     or 0),
            "gaHome":   int(stats.get("homeGoalsAgainst") or stats.get("pointsAgainstHome") or 0),
            "gfAway":   int(stats.get("awayGoalsFor")   or stats.get("pointsForAway")     or 0),
            "gaAway":   int(stats.get("awayGoalsAgainst") or stats.get("pointsAgainstAway") or 0),
            "wHome":    int(stats.get("homeWins")  or 0),
            "wAway":    int(stats.get("awayWins")  or 0),
        })

    if rows and all(r["position"] == 0 for r in rows):
        for i, r in enumerate(rows):
            r["position"] = i + 1
    return rows

def find_in_index(name, idx):
    sid = str(name or "")
    if sid in idx: return idx[sid]
    n = norm(name)
    if n and n in idx: return idx[n]
    # Fuzzy
    best, bestLen = None, 3
    for k, v in idx.items():
        if not isinstance(k, str) or k.isdigit() or len(k) < 4: continue
        if len(n) >= 4 and (k.lower().replace(' ','') in n or n in k.lower().replace(' ','')):
            l = min(len(k), len(n))
            if l > bestLen:
                best = v
                bestLen = l
    return best

def enrich_with_espn_form(matches, team_idx):
    """
    Para cada equipo en los partidos, busca su forma reciente si no la tenemos ya.
    Solo fetchea forma si no viene de quiniela15 (hForm vacío).
    """
    form_map = {}
    teams_to_fetch = []
    seen = set()

    for m in matches:
        for side, form_key in [(m["homeTeam"], "hForm"), (m["awayTeam"], "aForm")]:
            existing_form = m.get(form_key, [])
            if existing_form:
                # Ya tenemos forma de quiniela15, usar esa
                tid = side.get("id") or side.get("name","")
                form_map[str(tid)] = [{"r":x["r"],"gf":0,"ga":0} if isinstance(x,dict) else {"r":x,"gf":0,"ga":0} for x in existing_form]
                continue
            # Buscar en índice ESPN para obtener el teamId
            stand = find_in_index(side["name"], team_idx)
            if stand:
                side["id"] = stand["teamId"]
                espn_id = stand["teamId"]
                if espn_id and espn_id not in seen:
                    seen.add(espn_id)
                    teams_to_fetch.append({"id": espn_id, "name": side["name"]})

    if teams_to_fetch:
        print(f"  [3] Obteniendo forma ESPN para {len(teams_to_fetch)} equipos sin forma...")
        for i, t in enumerate(teams_to_fetch[:20]):
            tid = t["id"]
            # Try laliga slug first, then search through slugs
            data = None
            for slug in ["esp.1", "esp.2", "eng.1", "ger.1", "ita.1", "fra.1", "uefa.champions", "uefa.europa"]:
                data = fetch_json(f"{ESPN_BASE}/{slug}/teams/{tid}/schedule")
                if data and data.get("events"):
                    break
                time.sleep(0.2)

            if not data:
                form_map[str(tid)] = []
                continue

            results = []
            for ev in (data.get("events") or []):
                comp  = (ev.get("competitions") or [{}])[0]
                stype = ev.get("status",{}).get("type",{}).get("name","")
                if stype not in ("STATUS_FINAL","STATUS_FULL_TIME"):
                    continue
                comps = comp.get("competitors") or []
                if len(comps) < 2: continue
                me    = next((c for c in comps if str((c.get("team")or{}).get("id",""))==str(tid)), None)
                other = next((c for c in comps if str((c.get("team")or{}).get("id",""))!=str(tid)), None)
                if not me: me = comps[0]; other = comps[1]
                try:
                    gf = int(me.get("score",0) or 0)
                    ga = int(other.get("score",0) or 0)
                except: continue
                r = "W" if gf>ga else ("L" if gf<ga else "D")
                is_home = me.get("homeAway","") == "home"
                results.append({"r":r,"gf":gf,"ga":ga,"home":is_home})

            form_map[str(tid)] = results[-8:]
            time.sleep(0.35)

    return form_map

# ═══════════════════════════════════════════════════════
#  MAIN QUINIELA SCRAPE
# ═══════════════════════════════════════════════════════
def scrape_quiniela():
    print(f"\n{'='*55}")
    print(f"  🎯 QUINIELA OFICIAL — quiniela15.com")
    print(f"{'='*55}")

    # 1. Partidos oficiales
    matches, jornada = scrape_quiniela_official()
    if not matches:
        print("ERROR: No se obtuvieron partidos de quiniela15.com")
        return None

    # 2. Índice ESPN para enriquecer stats
    team_idx = build_espn_team_index()

    # 3. Enriquecer cada partido con datos ESPN
    print("  Enriqueciendo con stats ESPN...")
    standings_out = []
    seen_ids = set()

    for m in matches:
        for side_key, pos_key in [("homeTeam","hPos"),("awayTeam","aPos")]:
            side = m[side_key]
            stand = find_in_index(side["name"], team_idx)
            if stand:
                side["id"] = stand["teamId"]
                side["rawId"] = stand["teamId"]
                # Add to standings if not already there
                if stand["teamId"] not in seen_ids:
                    seen_ids.add(stand["teamId"])
                    standings_out.append(stand)

    # 4. Forma de equipos
    form_map = enrich_with_espn_form(matches, team_idx)

    # Merge quiniela15 form into form_map
    for m in matches:
        for side_key, form_key in [("homeTeam","hForm"),("awayTeam","aForm")]:
            side = m[side_key]
            existing = m.get(form_key, [])
            if existing:
                tid = str(side.get("id") or side.get("name",""))
                form_map[tid] = [{"r":x["r"],"gf":0,"ga":0} if isinstance(x,dict) else {"r":x,"gf":0,"ga":0} for x in existing]

    # 5. Convert matches to fixture format
    fixtures = []
    for m in matches:
        fixtures.append({
            "id":        str(m["num"]),
            "date":      m["date"],
            "status":    m["status"],
            "matchday":  jornada,
            "homeTeam":  m["homeTeam"],
            "awayTeam":  m["awayTeam"],
            "homeScore": m["homeScore"],
            "awayScore": m["awayScore"],
            "q15Probs":  m.get("q15Probs"),
            "laeProbs":  m.get("laeProbs"),
            "historial": m.get("historial"),
            "hPos":      m.get("hPos",0),
            "aPos":      m.get("aPos",0),
        })

    # League averages: LaLiga ~2.6 goals/game average 2024-25
    la1_stands = [r for r in standings_out if r.get("position",99) <= 20]
    la2_stands = [r for r in standings_out if r.get("position",99) > 20]

    return {
        "league":      f"Quiniela Oficial — Jornada {jornada}",
        "leagueKey":   "quiniela",
        "jornada":     jornada,
        "source":      "quiniela15.com (SELAE oficial)",
        "scrapedAt":   datetime.now(timezone.utc).isoformat(),
        "fixtures":    fixtures,
        "standings":   standings_out,
        "teamForm":    form_map,
        "quiniela":    True,
        "quinielaOfficial": True,
    }

# ═══════════════════════════════════════════════════════
#  NORMAL ESPN SCRAPE (unchanged from v3)
# ═══════════════════════════════════════════════════════
def get_standings_espn(slug):
    urls = [
        f"https://site.api.espn.com/apis/v2/sports/soccer/{slug}/standings",
        f"https://cdn.espn.com/core/soccer/standings?league={slug}&xhr=1",
        f"{ESPN_BASE}/{slug}/standings",
    ]
    for url in urls:
        raw = fetch_json(url)
        if raw:
            rows = _extract_standing_entries(raw)
            if rows:
                rows.sort(key=lambda x: x["position"] or 99)
                return rows
        time.sleep(0.3)
    return []

def _resolve_id(raw_id, name, lookup):
    if raw_id and raw_id in lookup: return raw_id
    n = norm(name)
    if n and n in lookup: return lookup[n]["teamId"]
    for k, v in lookup.items():
        if not isinstance(k,str) or k.isdigit() or len(k)<4: continue
        if k in n or n in k: return v["teamId"]
    return None

def get_fixtures_espn(slug, stand_lookup, days=28):
    fixtures = []
    today = datetime.now(timezone.utc)
    for offset in range(days):
        ds = (today + timedelta(days=offset)).strftime("%Y%m%d")
        data = fetch_json(f"{ESPN_BASE}/{slug}/scoreboard?dates={ds}")
        if not data: continue
        for ev in (data.get("events") or []):
            comp  = (ev.get("competitions") or [{}])[0]
            comps = comp.get("competitors") or []
            if len(comps) < 2: continue
            home = next((c for c in comps if c.get("homeAway")=="home"), comps[0])
            away = next((c for c in comps if c.get("homeAway")=="away"), comps[1])
            status = ev.get("status",{}).get("type",{}).get("name","STATUS_SCHEDULED")
            if status in ("STATUS_FINAL","STATUS_FULL_TIME"): continue
            ht = home.get("team") or {}
            at = away.get("team") or {}
            hname = ht.get("displayName") or ht.get("name") or ""
            aname = at.get("displayName") or at.get("name") or ""
            hid_raw = str(ht.get("id",""))
            aid_raw = str(at.get("id",""))
            hid = _resolve_id(hid_raw, hname, stand_lookup) or hid_raw
            aid = _resolve_id(aid_raw, aname, stand_lookup) or aid_raw
            s = lambda c: int(c.get("score")) if c.get("score") is not None else None
            fixtures.append({
                "id": str(ev.get("id","")),
                "date": ev.get("date",""),
                "status": status,
                "matchday": str(ev.get("week",{}).get("number") or "?"),
                "homeTeam": {"id":hid,"rawId":hid_raw,"name":hname,"short":ht.get("abbreviation","")},
                "awayTeam": {"id":aid,"rawId":aid_raw,"name":aname,"short":at.get("abbreviation","")},
                "homeScore": s(home), "awayScore": s(away),
            })
            if len(fixtures) >= 12: break
        if len(fixtures) >= 12: break
        time.sleep(0.25)
    return fixtures

# Slugs de competiciones "copa" que pueden contaminar el scoreboard de liga
# ESPN a veces devuelve varios torneos al buscar por fecha y slug de primera div.
_COPA_SLUGS = {
    "esp.1":  {"esp.copa", "esp.super_cup", "esp.copa_rey"},
    "eng.1":  {"eng.fa_cup", "eng.league_cup", "eng.community_shield"},
    "ger.1":  {"ger.dfb_pokal", "ger.super_cup"},
    "ita.1":  {"ita.coppa_italia", "ita.super_cup"},
    "fra.1":  {"fra.coupe_de_france", "fra.coupe_de_la_ligue"},
}

def _event_belongs_to_slug(ev, slug):
    """
    Filtra si un evento del scoreboard pertenece REALMENTE al slug pedido.
    ESPN a veces devuelve Copa del Rey etc. al pedir esp.1.
    Comprobamos el slug/uid del evento para descartarlos.
    """
    blocked = _COPA_SLUGS.get(slug, set())
    if not blocked:
        return True  # sin lista negra → aceptar todo

    # Intentar leer el slug de la competición del evento
    # ESPN lo guarda en distintos sitios según la versión de la API
    comp = (ev.get("competitions") or [{}])[0]

    # Opción 1: season.slug
    s_slug = ev.get("season", {}).get("slug", "").lower()
    if any(b in s_slug for b in blocked):
        return False

    # Opción 2: uid del evento contiene el leagueId
    # e.g. "s:600~l:140~e:..." → l:140 = LaLiga
    uid = ev.get("uid", "").lower()
    if uid:
        # Extraer id de liga del uid
        import re as _re
        m = _re.search(r"l:(\d+)", uid)
        if m:
            lid = m.group(1)
            # LaLiga=140, Premier=23, Bundesliga=10, SerieA=15, Ligue1=9, Esp2=70
            VALID_IDS = {
                "esp.1": {"140"}, "eng.1": {"23"}, "ger.1": {"10"},
                "ita.1": {"15"},  "fra.1": {"9"},  "esp.2": {"70"},
                "uefa.champions": {"19"},
            }
            valid = VALID_IDS.get(slug, set())
            if valid and lid not in valid:
                return False  # pertenece a otra competición

    # Opción 3: notes con el nombre del torneo
    notes = comp.get("notes", [])
    for note in notes:
        headline = (note.get("headline") or "").lower()
        if any(b.replace(".", " ") in headline for b in blocked):
            return False

    return True

def get_form_espn(slug, teams):
    """
    Obtiene la forma reciente de cada equipo usando el scoreboard por fechas.

    Fixes vs versión anterior:
    - Filtra eventos por competición (rechaza Copa del Rey, FA Cup, etc.)
    - Ventana ampliada a 90 días para cubrir parones internacionales
    - Fallback a /teams/{id}/schedule si el scoreboard da < 4 partidos
    """
    from datetime import datetime, timedelta, timezone as tz
    import re as _re

    form_map = {}
    seen = set()
    deduped = [t for t in teams if (k:=str(t.get("fetchId") or t.get("id") or t.get("rawId"))) not in seen and not seen.add(k)]
    total = len(deduped)

    # ── Paso 1: índice de partidos reales de la liga ─────────────
    print(f"    Construyendo índice de forma ({slug}, últimos 90 días)...")
    league_results = {}  # teamId -> [{r,gf,ga,home,date}]
    today = datetime.now(tz.utc)

    for offset in range(0, 91):  # 0 = hoy, 90 = hace 3 meses
        day = today - timedelta(days=offset)
        ds  = day.strftime("%Y%m%d")
        data = fetch_json(f"{ESPN_BASE}/{slug}/scoreboard?dates={ds}")
        if not data:
            continue

        for ev in (data.get("events") or []):
            # ── Filtro de competición ──────────────────────────
            if not _event_belongs_to_slug(ev, slug):
                continue

            comp  = (ev.get("competitions") or [{}])[0]
            stype = ev.get("status",{}).get("type",{}).get("name","")
            if stype not in ("STATUS_FINAL","STATUS_FULL_TIME"):
                continue
            comps = comp.get("competitors") or []
            if len(comps) < 2:
                continue

            try:
                home_comp = next((c for c in comps if c.get("homeAway")=="home"), comps[0])
                away_comp = next((c for c in comps if c.get("homeAway")=="away"), comps[1])
                hid  = str((home_comp.get("team")or{}).get("id",""))
                aid  = str((away_comp.get("team")or{}).get("id",""))
                hgf  = int(home_comp.get("score",0) or 0)
                agf  = int(away_comp.get("score",0) or 0)
                # Usar fecha ISO completa para ordenar correctamente
                raw_date = ev.get("date","")  # "2026-03-20T21:00Z"
                date_str = raw_date[:10] if raw_date else ""
                if not date_str:
                    continue
            except (ValueError, TypeError):
                continue

            hr = "W" if hgf>agf else ("L" if hgf<agf else "D")
            ar = "L" if hgf>agf else ("W" if hgf<agf else "D")

            event_id = str(ev.get("id",""))
            if hid:
                league_results.setdefault(hid, []).append(
                    {"r":hr,"gf":hgf,"ga":agf,"home":True,"date":date_str,"ts":raw_date,"eventId":event_id,"oppId":aid})
            if aid:
                league_results.setdefault(aid, []).append(
                    {"r":ar,"gf":agf,"ga":hgf,"home":False,"date":date_str,"ts":raw_date,"eventId":event_id,"oppId":hid})

        time.sleep(0.12)

    # Ordenar por timestamp completo (no solo fecha) → evita orden incorrecto
    # en jornadas con varios partidos el mismo día
    for tid in league_results:
        league_results[tid].sort(key=lambda x: x.get("ts",""))
        # Eliminar duplicados (mismo día, mismo rival podría aparecer dos veces)
        seen_ts = set()
        deduped_r = []
        for r in league_results[tid]:
            k = r["ts"][:16]  # precisión de minuto
            if k not in seen_ts:
                seen_ts.add(k)
                deduped_r.append(r)
        league_results[tid] = deduped_r

    n_teams   = len(league_results)
    avg_games = sum(len(v) for v in league_results.values()) // max(n_teams, 1)
    print(f"    Índice: {n_teams} equipos, ~{avg_games} partidos/equipo de liga")

    # ── Paso 2: asignar forma a cada equipo ──────────────────────
    for i, t in enumerate(deduped):
        fid = str(t.get("fetchId") or t.get("id") or t.get("rawId",""))
        sys.stdout.write(f"\r    Asignando forma {i+1}/{total}...  ")
        sys.stdout.flush()

        matches = league_results.get(fid, [])

        # Buscar por IDs alternativos si no encontramos por fid
        if not matches:
            for alt in [str(t.get("rawId","")), str(t.get("standId",""))]:
                if alt and alt not in ("None","") and alt != fid:
                    matches = league_results.get(alt, [])
                    if matches:
                        break

        # Si tenemos menos de 4 partidos de liga, hacer fallback
        # al endpoint /schedule que tiene más histórico
        if len(matches) < 4:
            fb = _form_fallback(slug, fid, t.get("name",""))
            if len(fb) > len(matches):
                matches = fb
                print(f"\n      Fallback para {t.get('name',fid)}: {len(matches)} partidos")

        form_data = matches[-8:]  # los 8 más recientes (suficiente para momentum)

        for key in {fid, str(t.get("id","")), str(t.get("rawId","")), str(t.get("standId",""))}:
            if key and key != "None":
                form_map[key] = form_data

    sys.stdout.write("\r" + ' '*50 + "\r")
    matched = sum(1 for v in form_map.values() if v)
    print(f"    Forma: {matched}/{total} equipos con datos")
    return form_map

def _form_fallback(slug, team_id, team_name=""):
    """
    Fallback: obtiene la forma desde /teams/{id}/schedule.
    Filtra por estado final, ordena por fecha, solo devuelve partidos del slug.
    Usado cuando el scoreboard da pocos resultados (parón internacional largo, etc.)
    """
    data = fetch_json(f"{ESPN_BASE}/{slug}/teams/{team_id}/schedule")
    if not data:
        return []

    results = []
    for ev in (data.get("events") or []):
        comp  = (ev.get("competitions") or [{}])[0]
        stype = ev.get("status",{}).get("type",{}).get("name","")
        if stype not in ("STATUS_FINAL","STATUS_FULL_TIME"):
            continue
        comps = comp.get("competitors") or []
        if len(comps) < 2:
            continue
        if not _event_belongs_to_slug(ev, slug):
            continue
        me    = next((c for c in comps if str((c.get("team")or{}).get("id",""))==str(team_id)), None)
        other = next((c for c in comps if str((c.get("team")or{}).get("id",""))!=str(team_id)), None)
        if not me:
            me, other = comps[0], comps[1]
        try:
            gf = int(me.get("score",0) or 0)
            ga = int(other.get("score",0) or 0)
        except:
            continue
        r  = "W" if gf>ga else ("L" if gf<ga else "D")
        ts = ev.get("date","")
        ih = me.get("homeAway","") == "home"
        opp_id = str((other.get("team") or {}).get("id",""))
        results.append({"r":r,"gf":gf,"ga":ga,"home":ih,"date":ts[:10],"ts":ts,"eventId":str(ev.get("id","")),"oppId":opp_id})

    results.sort(key=lambda x: x.get("ts",""))
    return results[-8:]

def scrape_normal(key):
    lg = LEAGUES[key]
    slug = lg["slug"]
    print(f"\n{'='*55}")
    print(f"  {lg['name']}  ({slug})")
    print(f"{'='*55}")
    test = fetch_json(f"{ESPN_BASE}/{slug}/scoreboard")
    if not test:
        print("  ERROR: Sin conexión a internet.")
        return None

    print("  [1] Clasificación...")
    st_rows = get_standings_espn(slug)
    print(f"    {len(st_rows)} equipos")

    stand_lookup = {}
    for r in st_rows:
        if r["teamId"]: stand_lookup[r["teamId"]] = r
        if norm(r["teamName"]): stand_lookup[norm(r["teamName"])] = r
        if r["teamName"]: stand_lookup[r["teamName"]] = r

    print(f"  [2] Fixtures...")
    fixtures = get_fixtures_espn(slug, stand_lookup)
    print(f"    {len(fixtures)} partidos")

    seen_ids = set()
    teams_to_fetch = []
    for f in fixtures:
        for side in [f["homeTeam"], f["awayTeam"]]:
            raw_id = side.get("rawId") or side.get("id")
            stand_row = stand_lookup.get(side.get("id")) or stand_lookup.get(norm(side["name"]))
            confirmed_id = (stand_row or {}).get("teamId") or raw_id
            uid = str(confirmed_id)
            if uid and uid not in seen_ids:
                seen_ids.add(uid)
                teams_to_fetch.append({"fetchId":confirmed_id,"id":confirmed_id,"rawId":raw_id,"name":side["name"]})

    print(f"  [3] Forma ({len(teams_to_fetch)} equipos)...")
    form_map = get_form_espn(slug, teams_to_fetch)
    print(f"    OK")

    card_model = build_card_model(slug, teams_to_fetch, form_map)

    fixture_refs = {}
    for f in fixtures:
        info = card_model.get("fixtures", {}).get(str(f.get("id","")), {})
        fixture_refs[str(f.get("id",""))] = info
    card_model["fixtures"] = fixture_refs

    return {
        "league":     lg["name"],
        "leagueKey":  key,
        "leagueSlug": slug,
        "source":     "ESPN Hidden API v5",
        "scrapedAt":  datetime.now(timezone.utc).isoformat(),
        "fixtures":   fixtures,
        "standings":  st_rows,
        "teamForm":   form_map,
        "cardModel":  card_model,
    }

# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════
def main():
    args = sys.argv[1:]
    if not args:
        print("Uso: python scraper.py [liga|all|quiniela]")
        print("Ligas:", ", ".join(LEAGUES))
        print("  quiniela -> Partidos REALES de SELAE desde quiniela15.com")
        sys.exit(0)

    target = args[0].lower()
    if target not in LEAGUES and target not in ("all","quiniela"):
        print(f"Opción inválida. Usa: {', '.join(LEAGUES)}, all, quiniela")
        sys.exit(1)

    if target == "quiniela":
        output = scrape_quiniela()
    elif target == "all":
        results = {}
        for k in LEAGUES:
            d = scrape_normal(k)
            if d: results[k] = d
        output = {"leagues": results} if len(results) > 1 else (list(results.values())[0] if results else None)
    else:
        output = scrape_normal(target)

    if not output:
        print("No se obtuvo ningún dato.")
        sys.exit(1)

    base_dir = os.path.dirname(os.path.abspath(__file__))

    if target == "quiniela":
        out_path = os.path.join(base_dir, "quiniela.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"""
  ✅ quiniela.json guardado: {out_path}
  Jornada:   {output.get('jornada','?')}
  Partidos:  {len(output.get('fixtures',[]))} (partidos REALES de SELAE)
  Equipos:   {len(output.get('standings',[]))}
  Fuente:    {output.get('source','')}

  python server.py
  http://localhost:8000/app.html  →  tab 🎯 Quiniela
""")
    else:
        out_path = os.path.join(base_dir, "data.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        snapshot_msg = ""
        if save_snapshot:
            try:
                snapshot_id = save_snapshot(output, source_file="data.json")
                snapshot_msg = f"\n  Snapshot: id={snapshot_id} guardado en golium.db"
            except Exception as exc:
                snapshot_msg = f"\n  Snapshot: error guardando en SQLite ({exc})"

        print(f"""
  ✅ data.json guardado: {out_path}
  Liga:      {output.get('league','?')}
  Partidos:  {len(output.get('fixtures',[]))}
  Equipos:   {len(output.get('standings',[]))}{snapshot_msg}

  python server.py
  http://localhost:8000/app.html
""")

if __name__ == "__main__":
    main()
