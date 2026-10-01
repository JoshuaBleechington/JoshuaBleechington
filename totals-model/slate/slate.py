#!/usr/bin/env python3
"""Write the day's slate for Call Sheet 2.0.

Runs on your own computer, needs nothing but Python 3, and writes one JSON
file that the sheet's **Load slate** button reads.

    python3 slate.py                    today's MLB games  -> slate-YYYY-MM-DD.json
    python3 slate.py --date 2026-09-28  another day's games
    python3 slate.py grade              yesterday's finals -> grade-YYYY-MM-DD.json
    python3 slate.py grade --date 2026-09-27
    python3 slate.py --selftest         offline checks, touches no network

Per MLB game the slate carries: the probable starters with ERA and innings,
each team's runs per game, a bullpen ERA built from the active roster's
relievers, each team's last-ten average total, the season head-to-head, and
the wind at first pitch resolved to the sheet's out / quarter-out / cross /
quarter-in / in relative to centre field, plus the temperature. When the
lineups are posted it lists them and names anyone who started the team's
last game but is not in today's order. It never carries a line or a price:
those come from the book and are typed.

Sources: MLB's public stats feed (statsapi.mlb.com) and Open-Meteo's free
forecast (api.open-meteo.com). Both are unauthenticated. Park positions and
centre-field bearings come from parks.json beside this file.

The WNBA is not covered. Its inputs (pace, ratings, rest, last five) still
come from a stats site by hand.
"""

import argparse
import datetime as dt
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

FORMAT = "callsheet2.slate"
VERSION = 1
HERE = os.path.dirname(os.path.abspath(__file__))
STATS = "https://statsapi.mlb.com/api/v1"
METEO = "https://api.open-meteo.com/v1/forecast"
UA = "callsheet2-slate/1 (personal betting sheet; python-urllib)"

# MLB's team ids never change; the nickname is what the sheet's team table
# canonicalises to, so emitting it exactly avoids any fuzzy matching.
NICK = {
    108: "Angels", 109: "Diamondbacks", 110: "Orioles", 111: "Red Sox", 112: "Cubs",
    113: "Reds", 114: "Guardians", 115: "Rockies", 116: "Tigers", 117: "Astros",
    118: "Royals", 119: "Dodgers", 120: "Nationals", 121: "Mets", 133: "Athletics",
    134: "Pirates", 135: "Padres", 136: "Mariners", 137: "Giants", 138: "Cardinals",
    139: "Rays", 140: "Rangers", 141: "Blue Jays", 142: "Twins", 143: "Phillies",
    144: "Braves", 145: "White Sox", 146: "Marlins", 147: "Yankees", 158: "Brewers",
}

COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


# ---- fetching --------------------------------------------------------------

_cache = {}


def fetch_json(url, tries=3):
    """GET a JSON document. Retries twice on a network error, caches by URL."""
    if url in _cache:
        return _cache[url]
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                data = json.loads(r.read().decode("utf-8"))
            _cache[url] = data
            return data
        except (OSError, ValueError) as e:  # URLError and HTTPError are OSErrors; so is a socket timeout
            last = e
            if i + 1 < tries:
                time.sleep(1.5 * (i + 1))
    raise RuntimeError("%s -> %s" % (url.split("?")[0], last))


def api(path, **params):
    q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return fetch_json(STATS + path + ("?" + q if q else ""))


# ---- small pure helpers (all covered by --selftest) ------------------------

def ip_decimal(ip):
    """Baseball innings '111.1' (111 and a third) -> 111.333. Blank -> None."""
    if ip is None or ip == "":
        return None
    s = str(ip)
    if "." not in s:
        return float(s)
    whole, frac = s.split(".", 1)
    thirds = {"0": 0.0, "1": 1.0 / 3, "2": 2.0 / 3}.get(frac[:1])
    if thirds is None:
        return float(s)
    return float(whole) + thirds


def fmt(v, dp):
    """Number -> the string the sheet stores. None -> '' (a blank field)."""
    if v is None:
        return ""
    if dp == 0:
        return str(int(round(v)))
    return ("%." + str(dp) + "f") % v


def compass(deg):
    return COMPASS[int((deg % 360) / 22.5 + 0.5) % 16]


def resolve_dir(wind_from_deg, cf_bearing):
    """Wind FROM a compass bearing, at a park whose centre field lies at
    cf_bearing from home plate -> the sheet's five directions. 'Out' is wind
    blowing toward centre field, 'in' toward the plate."""
    to = (wind_from_deg + 180.0) % 360.0
    d = abs((to - cf_bearing + 180.0) % 360.0 - 180.0)
    if d <= 22.5:
        return "out"
    if d <= 67.5:
        return "quarter-out"
    if d <= 112.5:
        return "cross"
    if d <= 157.5:
        return "quarter-in"
    return "in"


def vector_mean_dir(degs, weights=None):
    if not degs:
        return None
    ws = weights or [1.0] * len(degs)
    x = sum(w * math.cos(math.radians(a)) for a, w in zip(degs, ws))
    y = sum(w * math.sin(math.radians(a)) for a, w in zip(degs, ws))
    if abs(x) < 1e-9 and abs(y) < 1e-9:
        return degs[0]
    return math.degrees(math.atan2(y, x)) % 360.0


MLB_WIND = [
    ("out to cf", "out"), ("out to lf", "quarter-out"), ("out to rf", "quarter-out"),
    ("l to r", "cross"), ("r to l", "cross"),
    ("in from lf", "quarter-in"), ("in from rf", "quarter-in"), ("in from cf", "in"),
]


def parse_mlb_wind(s):
    """MLB's own wind string, e.g. '12 mph, Out To CF' -> (12, 'out').
    'Calm' or 'None' -> (0, ''). Unknown wording -> None."""
    if not s:
        return None
    low = str(s).lower().strip()
    if "calm" in low or low in ("none", "0 mph, none"):
        return (0, "")
    mph = None
    for tok in low.replace(",", " ").split():
        if tok.isdigit():
            mph = int(tok)
            break
    if mph is None:
        return None
    for key, val in MLB_WIND:
        if key in low:
            return (mph, val)
    if "varies" in low:
        return (mph, "")
    return None


def bullpen_era(people, exclude_ids=(), top=None):
    """Aggregate ER and IP over the roster's relievers: pitchers whose starts
    are fewer than half their appearances, minus today's probable starters.
    With top=N, only the N most-used relievers (by appearances, then innings)
    count: the October pen, where the mop-up arms never pitch.
    Returns (era, arms, innings) or (None, 0, 0.0) when nothing qualifies."""
    arms = []
    for p in people:
        if p.get("id") in exclude_ids:
            continue
        st = season_split(p)
        if not st:
            continue
        gp = int(st.get("gamesPlayed") or 0)
        gs = int(st.get("gamesStarted") or 0)
        innings = ip_decimal(st.get("inningsPitched")) or 0.0
        if gp == 0 or innings <= 0 or gs * 2 >= gp:
            continue
        arms.append((gp, innings, float(st.get("earnedRuns") or 0)))
    if top:
        arms.sort(key=lambda a: (-a[0], -a[1]))
        arms = arms[:top]
    ip = sum(a[1] for a in arms)
    er = sum(a[2] for a in arms)
    if ip <= 0:
        return (None, 0, 0.0)
    return (9.0 * er / ip, len(arms), ip)


def last_starts(splits, n=5):
    """A pitcher's game log -> (era, innings, starts) over his last n starts.
    Relief appearances are skipped. (None, 0.0, 0) with no starts at all."""
    starts = []
    for sp in splits or []:
        st = sp.get("stat") or {}
        if int(st.get("gamesStarted") or 0) < 1:
            continue
        starts.append((sp.get("date") or "", ip_decimal(st.get("inningsPitched")) or 0.0, float(st.get("earnedRuns") or 0)))
    starts.sort(key=lambda s: s[0])
    tail = starts[-n:]
    ip = sum(s[1] for s in tail)
    er = sum(s[2] for s in tail)
    if not tail or ip <= 0:
        return (None, 0.0, len(tail))
    return (9.0 * er / ip, ip, len(tail))


def season_split(person):
    for block in person.get("stats") or []:
        if (block.get("group") or {}).get("displayName") not in (None, "pitching"):
            continue
        for sp in block.get("splits") or []:
            if sp.get("stat"):
                return sp["stat"]
    return None


def is_final(game):
    st = game.get("status") or {}
    code = st.get("codedGameState") or ""
    det = (st.get("detailedState") or "").lower()
    return code == "F" or det.startswith("final") or det.startswith("completed") or det == "game over"


def game_total(game):
    a = (game.get("teams") or {}).get("away") or {}
    h = (game.get("teams") or {}).get("home") or {}
    if a.get("score") is None or h.get("score") is None:
        return None
    return int(a["score"]) + int(h["score"])


def last_n_avg_total(games, n=10):
    """Finished games, newest last -> average of the last n totals and n."""
    totals = [game_total(g) for g in games if is_final(g) and game_total(g) is not None]
    tail = totals[-n:]
    if not tail:
        return (None, 0)
    return (sum(tail) / float(len(tail)), len(tail))


def f5_from_linescore(linescore):
    """Runs after five for each side from a linescore, or (None, None) when
    fewer than five innings are on it."""
    innings = (linescore or {}).get("innings") or []
    if len(innings) < 5:
        return (None, None)
    a = 0
    h = 0
    for inn in innings[:5]:
        ra = (inn.get("away") or {}).get("runs")
        rh = (inn.get("home") or {}).get("runs")
        if ra is None or rh is None:
            # A fifth inning with no home half is a home team that led and
            # never batted; that is still a complete five for the total.
            if inn is innings[4] and ra is not None and rh is None:
                a += int(ra)
                continue
            return (None, None)
        a += int(ra)
        h += int(rh)
    return (a, h)


def nickname(team):
    tid = team.get("id")
    if tid in NICK:
        return NICK[tid]
    return team.get("teamName") or (team.get("name") or "").split(" ")[-1]


def load_parks():
    with open(os.path.join(HERE, "parks.json"), "r", encoding="utf-8") as f:
        return json.load(f)["parks"]


def find_park(parks, venue):
    """By venue name first; by MLB's venue id second. Returns (name, park, how)."""
    name = (venue or {}).get("name") or ""
    if name in parks:
        return (name, parks[name], "name")
    vid = (venue or {}).get("id")
    if vid is not None:
        for k, p in parks.items():
            if p.get("venue_id") == vid:
                return (k, p, "id")
    return (name, None, None)


def missing_from_lineup(today_ids, last_ids, names):
    out = []
    for pid in last_ids:
        if pid not in today_ids:
            out.append(names.get(pid, str(pid)))
    return out


# ---- the fetch side, one game at a time ------------------------------------

def schedule(date_iso, hydrate="probablePitcher,team,venue,weather,linescore"):
    d = api("/schedule", sportId=1, date=date_iso, hydrate=hydrate)
    games = []
    for day in d.get("dates") or []:
        games.extend(day.get("games") or [])
    return games


def team_games(team_id, start, end):
    d = api("/schedule", sportId=1, teamId=team_id, startDate=start, endDate=end, hydrate="linescore")
    games = []
    for day in d.get("dates") or []:
        games.extend(day.get("games") or [])
    games.sort(key=lambda g: g.get("gameDate") or "")
    return games


def h2h_games(team_id, opp_id, start, end):
    d = api("/schedule", sportId=1, teamId=team_id, opponentId=opp_id, startDate=start, endDate=end)
    games = []
    for day in d.get("dates") or []:
        games.extend(day.get("games") or [])
    return games


def pitcher_season(pid, season):
    d = api("/people/%d/stats" % pid, stats="season", group="pitching", season=season)
    for block in d.get("stats") or []:
        for sp in block.get("splits") or []:
            if sp.get("stat"):
                return sp["stat"]
    return None


def pitcher_gamelog(pid, season):
    d = api("/people/%d/stats" % pid, stats="gameLog", group="pitching", season=season)
    out = []
    for block in d.get("stats") or []:
        out.extend(block.get("splits") or [])
    return out


def team_hitting(team_id, season):
    d = api("/teams/%d/stats" % team_id, stats="season", group="hitting", season=season)
    for block in d.get("stats") or []:
        for sp in block.get("splits") or []:
            if sp.get("stat"):
                return sp["stat"]
    return None


def roster_pitchers(team_id, season):
    r = api("/teams/%d/roster" % team_id, rosterType="active", season=season)
    ids = []
    for row in r.get("roster") or []:
        pos = ((row.get("position") or {}).get("abbreviation") or "").upper()
        pid = (row.get("person") or {}).get("id")
        if pid and pos in ("P", "TWP", "RP", "SP"):
            ids.append(int(pid))
    if not ids:
        return []
    d = api("/people", personIds=",".join(str(i) for i in ids),
            hydrate="stats(group=[pitching],type=[season],season=%s)" % season)
    return d.get("people") or []


def boxscore(game_pk):
    return api("/game/%d/boxscore" % game_pk)


def lineup_of(box, side):
    t = ((box or {}).get("teams") or {}).get(side) or {}
    order = [int(x) for x in (t.get("battingOrder") or [])]
    names = {}
    for key, p in (t.get("players") or {}).items():
        person = p.get("person") or {}
        if person.get("id") is not None:
            names[int(person["id"])] = person.get("fullName") or key
    return (order, names)


def weather_at(park, first_pitch_utc):
    """Open-Meteo hourly at the park, averaged over first pitch and the two
    hours after it. Returns dict(mph, from_deg, temp, hours) or None."""
    day = first_pitch_utc.date().isoformat()
    day2 = (first_pitch_utc + dt.timedelta(days=1)).date().isoformat()
    q = urllib.parse.urlencode({
        "latitude": park["lat"], "longitude": park["lon"],
        "hourly": "temperature_2m,wind_speed_10m,wind_direction_10m",
        "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
        "timezone": "UTC", "start_date": day, "end_date": day2,
    })
    d = fetch_json(METEO + "?" + q)
    h = d.get("hourly") or {}
    times = h.get("time") or []
    want = []
    for k in range(3):
        t = (first_pitch_utc + dt.timedelta(hours=k)).replace(minute=0, second=0, microsecond=0)
        want.append(t.strftime("%Y-%m-%dT%H:%M"))
    rows = []
    for i, ts in enumerate(times):
        if ts in want:
            try:
                rows.append((ts, float(h["temperature_2m"][i]), float(h["wind_speed_10m"][i]), float(h["wind_direction_10m"][i])))
            except (KeyError, IndexError, TypeError, ValueError):
                pass
    if not rows:
        return None
    mph = sum(r[2] for r in rows) / len(rows)
    temp = sum(r[1] for r in rows) / len(rows)
    frm = vector_mean_dir([r[3] for r in rows], [max(r[2], 0.1) for r in rows])
    return {"mph": mph, "from_deg": frm, "temp": temp, "hours": rows}


def parse_utc(s):
    return dt.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")


def now_utc():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_game(g, parks, date_iso, season, log):
    """One schedule entry -> one slate game. Every fetch is guarded: a failed
    piece becomes a blank field and a note, never a lost game."""
    away_t = g["teams"]["away"]["team"]
    home_t = g["teams"]["home"]["team"]
    away = nickname(away_t)
    home = nickname(home_t)
    aid = int(away_t["id"])
    hid = int(home_t["id"])
    gpk = int(g.get("gamePk") or 0)
    status = ((g.get("status") or {}).get("detailedState")) or ""
    first = parse_utc(g.get("gameDate") or (date_iso + "T00:00:00Z"))
    venue = g.get("venue") or {}
    inputs = {k: "" for k in ("aera", "hera", "aip", "hip", "al5era", "hl5era", "al5ip", "hl5ip", "arpg", "hrpg", "abp", "hbp",
                              "al10", "hl10", "h2h", "h2hn", "pf", "mph", "dir", "temp")}
    inputs["dome"] = False
    notes = []
    starters = {"away": "", "home": ""}
    lineups = {"away": [], "home": []}
    pens = {"away": {}, "home": {}}
    playoff = (g.get("gameType") or "R") != "R"
    out = {"sport": "MLB", "gdate": date_iso, "away": away, "home": home, "gamePk": gpk, "playoff": playoff,
           "first_pitch_utc": first.strftime("%Y-%m-%dT%H:%M:%SZ"), "venue": venue.get("name") or "",
           "status": status, "starters": starters, "inputs": inputs, "pens": pens, "lineups": lineups, "notes": notes}
    log("%s @ %s  (%s, first pitch %s UTC, %s%s)" % (away, home, venue.get("name") or "venue ?", first.strftime("%H:%M"), status or "scheduled", ", postseason" if playoff else ""))
    if status.lower().startswith(("postponed", "cancelled", "canceled", "suspended")):
        notes.append("Game is %s." % status.lower())

    # starters
    pids = []
    for side, key in (("away", "aera"), ("home", "hera")):
        pp = (g["teams"][side].get("probablePitcher")) or {}
        if not pp.get("id"):
            notes.append("%s probable starter not announced yet." % ("Away" if side == "away" else "Home"))
            log("  %s starter: TBD" % side)
            continue
        pid = int(pp["id"])
        pids.append(pid)
        starters[side] = pp.get("fullName") or str(pid)
        try:
            st = pitcher_season(pid, season) or {}
            era = st.get("era")
            ip = ip_decimal(st.get("inningsPitched"))
            if era not in (None, "", "-.--"):
                inputs[key] = fmt(float(era), 2)
            if ip is not None:
                inputs["aip" if side == "away" else "hip"] = fmt(ip, 1)
            if not inputs[key]:
                notes.append("%s has no %s pitching line yet (ERA left blank)." % (starters[side], season))
            log("  %s starter: %s  ERA %s in %s IP" % (side, starters[side], inputs[key] or "?", inputs["aip" if side == "away" else "hip"] or "?"))
        except Exception as e:  # noqa: BLE001 - every piece is best-effort
            notes.append("Could not fetch %s's season line: %s" % (starters[side], e))
            log("  %s starter: %s  (stats failed: %s)" % (side, starters[side], e))
        # the last five starts: shown on the sheet, not scored, recorded for the test
        p = "a" if side == "away" else "h"
        try:
            era5, ip5, n5 = last_starts(pitcher_gamelog(pid, season), 5)
            if era5 is not None:
                inputs[p + "l5era"] = fmt(era5, 2)
                inputs[p + "l5ip"] = fmt(ip5, 1)
                log("  %s starter, last %d start%s: %s ERA in %s IP" % (side, n5, "" if n5 == 1 else "s", inputs[p + "l5era"], inputs[p + "l5ip"]))
                if n5 < 5:
                    notes.append("%s has only %d start%s this season; the last-five line is over those." % (starters[side], n5, "" if n5 == 1 else "s"))
            else:
                log("  %s starter, last 5 starts: none on the log" % side)
        except Exception as e:  # noqa: BLE001
            notes.append("Could not fetch %s's game log: %s" % (starters[side], e))

    # runs per game, bullpen, last ten, head to head
    season_start = "%s-03-01" % season
    yesterday = (dt.date.fromisoformat(date_iso) - dt.timedelta(days=1)).isoformat()
    month_ago = (dt.date.fromisoformat(date_iso) - dt.timedelta(days=45)).isoformat()
    for side, tid in (("away", aid), ("home", hid)):
        p = "a" if side == "away" else "h"
        try:
            st = team_hitting(tid, season) or {}
            gp = int(st.get("gamesPlayed") or 0)
            runs = float(st.get("runs") or 0)
            if gp > 0:
                inputs[p + "rpg"] = fmt(runs / gp, 2)
            log("  %s runs/game: %s (%s runs in %d games)" % (side, inputs[p + "rpg"] or "?", int(runs), gp))
        except Exception as e:  # noqa: BLE001
            notes.append("Could not fetch %s team hitting: %s" % (side, e))
        try:
            people = roster_pitchers(tid, season)
            era, arms, ip = bullpen_era(people, exclude_ids=set(pids))
            era5, arms5, ip5 = bullpen_era(people, exclude_ids=set(pids), top=5)
            pens[side] = {"roster": fmt(era, 2), "roster_arms": arms, "top5": fmt(era5, 2), "top5_arms": arms5}
            # The October pen is the top five by appearances; the whole roster
            # averages in arms who will not pitch a leveraged inning.
            use = era5 if (playoff and era5 is not None) else era
            if use is not None:
                inputs[p + "bp"] = fmt(use, 2)
            log("  %s bullpen ERA: %s over the roster (%d relievers, %.1f IP); top five by appearances %s (%.1f IP)%s" %
                (side, fmt(era, 2) or "?", arms, ip, fmt(era5, 2) or "?", ip5, "  -> using the top five: postseason" if playoff else ""))
            if playoff and era5 is not None:
                notes.append("%s pen is the top five relievers by appearances, %s (whole roster %s): postseason." % (away if side == "away" else home, fmt(era5, 2), fmt(era, 2)))
        except Exception as e:  # noqa: BLE001
            notes.append("Could not build %s bullpen ERA: %s" % (side, e))
        try:
            games = team_games(tid, month_ago, yesterday)
            avg, n = last_n_avg_total(games, 10)
            if avg is not None:
                inputs[p + "l10"] = fmt(avg, 1)
            if n < 10:
                notes.append("%s last-ten average is over %d game%s only." % (away if side == "away" else home, n, "" if n == 1 else "s"))
            log("  %s last-10 avg total: %s (%d games)" % (side, inputs[p + "l10"] or "?", n))
            out["_last_games_" + side] = games
        except Exception as e:  # noqa: BLE001
            notes.append("Could not fetch %s recent games: %s" % (side, e))
    try:
        hh = h2h_games(aid, hid, season_start, yesterday)
        totals = [game_total(x) for x in hh if is_final(x) and game_total(x) is not None]
        if totals:
            inputs["h2h"] = fmt(sum(totals) / float(len(totals)), 1)
            inputs["h2hn"] = str(len(totals))
        log("  head-to-head: %s over %s meeting%s" % (inputs["h2h"] or "none yet", inputs["h2hn"] or "0", "" if inputs["h2hn"] == "1" else "s"))
    except Exception as e:  # noqa: BLE001
        notes.append("Could not fetch the season series: %s" % e)

    # park and weather
    pname, park, how = find_park(parks, venue)
    if park is None:
        notes.append("Park '%s' is not in parks.json; wind and temp left blank. Add it to parks.json." % (venue.get("name") or "?"))
        log("  park: %s not in parks.json (wind skipped)" % (venue.get("name") or "?"))
    else:
        if how == "id":
            log("  park: matched %s by MLB venue id (the name '%s' is not in parks.json)" % (pname, venue.get("name")))
        roof = park.get("roof") or "open"
        if roof == "fixed":
            inputs["dome"] = True
            log("  park: %s, fixed roof -> dome" % pname)
        else:
            if roof == "retractable":
                notes.append("%s has a retractable roof: tick Roof shut on the sheet if it is closed." % pname)
            mlbw = parse_mlb_wind(((g.get("weather") or {}).get("wind")))
            mlbt = (g.get("weather") or {}).get("temp")
            try:
                w = weather_at(park, first)
            except Exception as e:  # noqa: BLE001
                w = None
                notes.append("Could not fetch the forecast: %s" % e)
            if w:
                d = resolve_dir(w["from_deg"], float(park["cf_bearing"]))
                inputs["mph"] = fmt(w["mph"], 0)
                inputs["dir"] = d
                inputs["temp"] = fmt(w["temp"], 0)
                out["weather_raw"] = {"from_deg": round(w["from_deg"]), "compass": compass(w["from_deg"]),
                                      "cf_bearing": park["cf_bearing"], "hours_utc": [r[0][11:] for r in w["hours"]]}
                log("  wind: %s mph from %s (%d deg) at a park whose CF lies at %d deg -> %s; %s F  [Open-Meteo, %s]" %
                    (inputs["mph"], compass(w["from_deg"]), round(w["from_deg"]), park["cf_bearing"], d, inputs["temp"],
                     ", ".join(r[0][11:] for r in w["hours"]) + " UTC"))
                if not park.get("verified"):
                    log("  (parks.json marks %s's centre-field bearing as unverified; check the direction once against the park diagram)" % pname)
            if mlbw:
                mph2, dir2 = mlbw
                log("  MLB's own read: %s mph, %s%s" % (mph2, dir2 or "calm/varies", (", %s F" % mlbt) if mlbt else ""))
                if not w or dir2 != inputs["dir"]:
                    # MLB's stadium read, when present, beats a forecast grid.
                    inputs["mph"] = str(mph2)
                    inputs["dir"] = dir2
                    if mlbt not in (None, ""):
                        inputs["temp"] = str(mlbt)
                    if w:
                        notes.append("Used MLB's stadium wind (%s mph %s) over the forecast (%s)." % (mph2, dir2 or "calm", d))

    # lineups: today's order, and who from the last game is missing
    try:
        box = boxscore(gpk) if gpk else None
        for side in ("away", "home"):
            order, names = lineup_of(box, side)
            lineups[side] = [names.get(i, str(i)) for i in order]
            if not order:
                notes.append("%s lineup not posted yet: run again nearer first pitch." % (away if side == "away" else home))
                log("  %s lineup: not posted yet" % side)
                continue
            log("  %s lineup: %s" % (side, ", ".join(lineups[side])))
            lastg = [x for x in (out.get("_last_games_" + side) or []) if is_final(x)]
            if lastg:
                try:
                    lb = boxscore(int(lastg[-1]["gamePk"]))
                    lside = "away" if int(lastg[-1]["teams"]["away"]["team"]["id"]) == (aid if side == "away" else hid) else "home"
                    lorder, lnames = lineup_of(lb, lside)
                    gone = missing_from_lineup(set(order), lorder, lnames)
                    if gone:
                        notes.append("%s: not in today's lineup but started last game: %s." % (away if side == "away" else home, ", ".join(gone)))
                        log("  %s: out vs last game: %s" % (side, ", ".join(gone)))
                except Exception as e:  # noqa: BLE001
                    log("  %s: could not compare with last game's lineup (%s)" % (side, e))
    except Exception as e:  # noqa: BLE001
        notes.append("Could not fetch the lineups: %s" % e)
    out.pop("_last_games_away", None)
    out.pop("_last_games_home", None)
    for n in notes:
        log("  note: " + n)
    return out


def grade_game(g, log):
    away = nickname(g["teams"]["away"]["team"])
    home = nickname(g["teams"]["home"]["team"])
    status = ((g.get("status") or {}).get("detailedState")) or ""
    if not is_final(g):
        log("%s @ %s: %s, not final; skipped" % (away, home, status or "not started"))
        return None
    fa = g["teams"]["away"].get("score")
    fh = g["teams"]["home"].get("score")
    f5a, f5h = f5_from_linescore(g.get("linescore"))
    fin = {"fa": str(int(fa)), "fh": str(int(fh))}
    notes = []
    if f5a is not None:
        fin["f5a"] = str(f5a)
        fin["f5h"] = str(f5h)
    else:
        notes.append("No five-inning linescore on the feed; type the first five by hand.")
    log("%s @ %s: final %s-%s, after five %s-%s%s" % (away, home, fin["fa"], fin["fh"], fin.get("f5a", "?"), fin.get("f5h", "?"),
                                                      "  (%s)" % status if "final" not in status.lower() else ""))
    return {"sport": "MLB", "gdate": g.get("officialDate") or "", "away": away, "home": home,
            "gamePk": int(g.get("gamePk") or 0), "finals": fin, "notes": notes}


# ---- NHL -------------------------------------------------------------------
# The league's public feed (api-web.nhle.com, api.nhle.com/stats/rest), no
# login. Per game: the two goalies with season save percentage and shots
# faced and a LIKELY starter (the slate cannot see the confirmed one; the
# sheet asks you to confirm), shots for per game, power play and kill, the
# last ten totals, the season series, rest days. The grade file carries the
# final (overtime and shootout included, as the league records it) and the
# first-period score in the sheet's period boxes.

#: Team rates (shots, special teams, last ten) go on the sheet at face value,
#: so they wait for this many games. The goalies do not: the sheet shrinks a
#: save percentage by its shots, so a goalie can go in from the first start.
MIN_TEAM_GAMES = 5
NHL_WEB = "https://api-web.nhle.com/v1"
NHL_STATS = "https://api.nhle.com/stats/rest/en"
NHL_NICK = {
    "ANA": "Ducks", "BOS": "Bruins", "BUF": "Sabres", "CGY": "Flames", "CAR": "Hurricanes",
    "CHI": "Blackhawks", "COL": "Avalanche", "CBJ": "Blue Jackets", "DAL": "Stars", "DET": "Red Wings",
    "EDM": "Oilers", "FLA": "Panthers", "LAK": "Kings", "MIN": "Wild", "MTL": "Canadiens",
    "NSH": "Predators", "NJD": "Devils", "NYI": "Islanders", "NYR": "Rangers", "OTT": "Senators",
    "PHI": "Flyers", "PIT": "Penguins", "SJS": "Sharks", "SEA": "Kraken", "STL": "Blues",
    "TBL": "Lightning", "TOR": "Maple Leafs", "UTA": "Mammoth", "VAN": "Canucks", "VGK": "Golden Knights",
    "WSH": "Capitals", "WPG": "Jets",
}


def nhl_api(path):
    return fetch_json(NHL_WEB + path)


def nhl_name(team):
    """The nickname the sheet's NHL table canonicalises to."""
    ab = (team or {}).get("abbrev") or ""
    if ab in NHL_NICK:
        return NHL_NICK[ab]
    cn = (team or {}).get("commonName") or {}
    if isinstance(cn, dict) and cn.get("default"):
        return cn["default"]
    return ab or "?"


def nhl_schedule(date_iso):
    d = nhl_api("/schedule/%s" % date_iso)
    out = []
    for day in d.get("gameWeek") or []:
        if day.get("date") == date_iso:
            out.extend(day.get("games") or [])
    return out


def nhl_final(game):
    st = str(game.get("gameState") or "").upper()
    return st in ("OFF", "FINAL")


def nhl_season_id(games, date_iso):
    for g in games:
        if g.get("season"):
            return str(g["season"])
    y = int(date_iso[:4])
    return "%d%d" % (y, y + 1) if int(date_iso[5:7]) >= 8 else "%d%d" % (y - 1, y)


def nhl_team_summary(season_id):
    """One row per team from the stats REST summary report, keyed by team id."""
    q = urllib.parse.urlencode({"cayenneExp": "seasonId=%s and gameTypeId=2" % season_id, "limit": -1})
    d = fetch_json(NHL_STATS + "/team/summary?" + q)
    return {int(r["teamId"]): r for r in (d.get("data") or []) if r.get("teamId") is not None}


def nhl_club_goalies(abbrev):
    d = nhl_api("/club-stats/%s/now" % abbrev)
    out = []
    for g in d.get("goalies") or []:
        name = " ".join(x for x in [(g.get("firstName") or {}).get("default") if isinstance(g.get("firstName"), dict) else g.get("firstName"),
                                    (g.get("lastName") or {}).get("default") if isinstance(g.get("lastName"), dict) else g.get("lastName")] if x)
        sv = g.get("savePercentage", g.get("savePctg"))
        out.append({"id": g.get("playerId"), "name": name or str(g.get("playerId")),
                    "sv": None if sv in (None, "") else float(sv),
                    "shots": int(g.get("shotsAgainst") or 0), "gp": int(g.get("gamesPlayed") or 0),
                    "gs": int(g.get("gamesStarted") or 0)})
    return out


def nhl_club_games(abbrev):
    d = nhl_api("/club-schedule-season/%s/now" % abbrev)
    games = [g for g in (d.get("games") or []) if str(g.get("gameType", 2)) in ("2", "3")]
    games.sort(key=lambda g: g.get("gameDate") or "")
    return games


def nhl_game_total(g):
    a = (g.get("awayTeam") or {}).get("score")
    h = (g.get("homeTeam") or {}).get("score")
    if a is None or h is None:
        return None
    return int(a) + int(h)


def nhl_last_n_avg(games, before_iso, n=10):
    fin = [g for g in games if nhl_final(g) and (g.get("gameDate") or "") < before_iso and nhl_game_total(g) is not None]
    tail = fin[-n:]
    if not tail:
        return (None, 0, fin)
    return (sum(nhl_game_total(g) for g in tail) / float(len(tail)), len(tail), fin)


def nhl_rest_days(fin_games, date_iso):
    if not fin_games:
        return None
    last = fin_games[-1].get("gameDate") or ""
    try:
        return (dt.date.fromisoformat(date_iso) - dt.date.fromisoformat(last)).days - 1
    except ValueError:
        return None


def nhl_last_starter(game_id, abbrev):
    """Who started the team's last game, from its boxscore."""
    box = nhl_api("/gamecenter/%s/boxscore" % game_id)
    pbg = box.get("playerByGameStats") or {}
    side = "awayTeam" if ((box.get("awayTeam") or {}).get("abbrev") == abbrev) else "homeTeam"
    for g in (pbg.get(side) or {}).get("goalies") or []:
        if g.get("starter"):
            return g.get("playerId")
    return None


def nhl_likely_starter(goalies, rest_days, last_starter_id):
    """The slate's guess at tonight's goalie: on a back to back, the one who
    did NOT start yesterday; otherwise the one with the most starts. Never
    confirmed -- the sheet says so and the user confirms."""
    if not goalies:
        return None, "no goalies on the club page"
    pool = list(goalies)
    why = "most starts this season"
    if rest_days is not None and rest_days <= 0 and last_starter_id is not None and len(pool) > 1:
        rested = [g for g in pool if g["id"] != last_starter_id]
        if rested:
            pool = rested
            why = "back to back: the goalie who did not start yesterday"
    pool.sort(key=lambda g: (-g["gs"], -g["gp"], -g["shots"]))
    if pool[0]["gs"] == 0 and pool[0]["gp"] == 0:
        why = "no starts logged yet this season; a guess"
    return pool[0], why


def p1_from_landing(landing):
    """First-period goals (away, home) from a game's landing page linescore."""
    ls = ((landing or {}).get("summary") or {}).get("linescore") or {}
    for p in ls.get("byPeriod") or []:
        num = (p.get("periodDescriptor") or {}).get("number", p.get("period"))
        if num == 1 and p.get("away") is not None and p.get("home") is not None:
            return int(p["away"]), int(p["home"])
    goals = ((landing or {}).get("summary") or {}).get("scoring") or []
    for per in goals:
        if (per.get("periodDescriptor") or {}).get("number") == 1:
            a = h = 0
            for g in per.get("goals") or []:
                if g.get("teamAbbrev") and (landing.get("awayTeam") or {}).get("abbrev") == (g.get("teamAbbrev") or {}).get("default", g.get("teamAbbrev")):
                    a += 1
                else:
                    h += 1
            return a, h
    return None, None


def build_nhl_game(g, date_iso, season_id, summary, log):
    away_t, home_t = g.get("awayTeam") or {}, g.get("homeTeam") or {}
    away, home = nhl_name(away_t), nhl_name(home_t)
    aab, hab = away_t.get("abbrev") or "", home_t.get("abbrev") or ""
    gid = g.get("id")
    start = str(g.get("startTimeUTC") or "")
    state = str(g.get("gameState") or "")
    inputs = {k: "" for k in ("agsv", "hgsv", "agsh", "hgsh", "asf", "hsf", "app", "hpp", "apk", "hpk",
                              "al10", "hl10", "h2h", "h2hn", "arest", "hrest")}
    notes, starters = [], {"away": "", "home": ""}
    out = {"sport": "NHL", "gdate": date_iso, "away": away, "home": home, "gameId": gid, "first_puck_utc": start,
           "venue": ((g.get("venue") or {}).get("default") if isinstance(g.get("venue"), dict) else g.get("venue")) or "",
           "status": state, "starters": starters, "goalies": {"away": [], "home": []}, "inputs": inputs, "notes": notes}
    log("%s @ %s  (%s, %s UTC, %s)" % (away, home, out["venue"] or "venue ?", start[11:16] if len(start) >= 16 else "?", state or "scheduled"))

    for side, t, ab in (("away", away_t, aab), ("home", home_t, hab)):
        p = "a" if side == "away" else "h"
        nick = away if side == "away" else home
        # team rates from the summary report
        row = summary.get(int(t.get("id") or -1)) if summary else None
        if row:
            try:
                gp = int(row.get("gamesPlayed") or 0)
                # A one-game season is not a sample. Shots per game, the power
                # play and the kill go on the sheet at face value, so they wait
                # for MIN_TEAM_GAMES; the goalies are shrunk by the sheet and
                # can go in from the first shot.
                if gp >= MIN_TEAM_GAMES:
                    if row.get("shotsForPerGame") is not None:
                        inputs[p + "sf"] = fmt(float(row["shotsForPerGame"]), 1)
                    if row.get("powerPlayPct") is not None:
                        inputs[p + "pp"] = fmt(float(row["powerPlayPct"]) * 100.0, 1)
                    if row.get("penaltyKillPct") is not None:
                        inputs[p + "pk"] = fmt(float(row["penaltyKillPct"]) * 100.0, 1)
                    log("  %s shots for %s/g, PP %s%%, PK %s%% (%d games)" % (side, inputs[p + "sf"] or "?", inputs[p + "pp"] or "?", inputs[p + "pk"] or "?", gp))
                else:
                    notes.append("%s has %d game%s this season: shots, power play and kill left blank until %d." % (nick, gp, "" if gp == 1 else "s", MIN_TEAM_GAMES))
                    log("  %s shots %s/g, PP %s%%, PK %s%% on %d game%s: left blank until %d" % (side, row.get("shotsForPerGame", "?"), row.get("powerPlayPct", "?"), row.get("penaltyKillPct", "?"), gp, "" if gp == 1 else "s", MIN_TEAM_GAMES))
            except (TypeError, ValueError) as e:
                notes.append("Could not read %s team rates: %s" % (nick, e))
        else:
            notes.append("%s has no row on the season summary yet (first games of the year)." % nick)
        # recent games, rest, head to head
        fin = []
        try:
            games = nhl_club_games(ab)
            avg, n, fin = nhl_last_n_avg(games, date_iso, 10)
            if avg is not None and n >= MIN_TEAM_GAMES:
                inputs[p + "l10"] = fmt(avg, 1)
            if n < MIN_TEAM_GAMES:
                notes.append("%s has %d final%s this season: the last-ten box is left blank until %d." % (nick, n, "" if n == 1 else "s", MIN_TEAM_GAMES))
            elif n < 10:
                notes.append("%s last-ten average is over %d games only." % (nick, n))
            rest = nhl_rest_days(fin, date_iso)
            if rest is not None:
                inputs[p + "rest"] = str(max(0, rest))
            log("  %s last-10 avg total: %s (%d games); rest %s day(s)" % (side, inputs[p + "l10"] or "?", n, inputs[p + "rest"] or "?"))
            if side == "away":
                opp = hab
                h2h = [x for x in fin if (x.get("awayTeam") or {}).get("abbrev") == opp or (x.get("homeTeam") or {}).get("abbrev") == opp]
                if h2h:
                    inputs["h2h"] = fmt(sum(nhl_game_total(x) for x in h2h) / float(len(h2h)), 1)
                    inputs["h2hn"] = str(len(h2h))
                log("  head-to-head: %s over %s meeting%s" % (inputs["h2h"] or "none yet", inputs["h2hn"] or "0", "" if inputs["h2hn"] == "1" else "s"))
        except Exception as e:  # noqa: BLE001
            notes.append("Could not fetch %s recent games: %s" % (nick, e))
        # goalies
        try:
            goalies = nhl_club_goalies(ab)
            out["goalies"][side] = [{"name": x["name"], "sv": x["sv"], "shots": x["shots"], "gs": x["gs"]} for x in goalies]
            last_id = None
            if fin and inputs[p + "rest"] == "0":
                try:
                    last_id = nhl_last_starter(fin[-1].get("id"), ab)
                except Exception as e:  # noqa: BLE001
                    log("  %s: could not read yesterday's starter (%s)" % (side, e))
            pick, why = nhl_likely_starter(goalies, int(inputs[p + "rest"]) if inputs[p + "rest"] != "" else None, last_id)
            if pick:
                starters[side] = pick["name"]
                if pick["sv"] is not None and pick["shots"] > 0:
                    inputs[p + "gsv"] = "%.3f" % pick["sv"]
                    inputs[p + "gsh"] = str(pick["shots"])
                else:
                    notes.append("%s's likely starter %s has no shots this season; save percentage left blank." % (nick, pick["name"]))
                notes.append("%s likely starter: %s (%s). NOT confirmed: check Daily Faceoff and tick the box." % (nick, pick["name"], why))
                others = ", ".join("%s %s/%d" % (x["name"], "%.3f" % x["sv"] if x["sv"] is not None else "?", x["shots"]) for x in goalies if x is not pick)
                log("  %s goalie: %s  SV %s on %s shots  [%s]%s" % (side, pick["name"], inputs[p + "gsv"] or "?", inputs[p + "gsh"] or "?", why, ("; others: " + others) if others else ""))
            else:
                notes.append("%s: %s." % (nick, why))
        except Exception as e:  # noqa: BLE001
            notes.append("Could not fetch %s goalies: %s" % (nick, e))
    for n in notes:
        log("  note: " + n)
    return out


def grade_nhl_game(g, log):
    away, home = nhl_name(g.get("awayTeam")), nhl_name(g.get("homeTeam"))
    if not nhl_final(g):
        log("%s @ %s: %s, not final; skipped" % (away, home, g.get("gameState") or "not started"))
        return None
    fa, fh = (g.get("awayTeam") or {}).get("score"), (g.get("homeTeam") or {}).get("score")
    fin = {"fa": str(int(fa)), "fh": str(int(fh))}
    notes = []
    try:
        p1a, p1h = p1_from_landing(nhl_api("/gamecenter/%s/landing" % g.get("id")))
        if p1a is not None:
            fin["f5a"], fin["f5h"] = str(p1a), str(p1h)
        else:
            notes.append("No first-period linescore on the feed; type the period score by hand.")
    except Exception as e:  # noqa: BLE001
        notes.append("Could not fetch the period score: %s" % e)
    how = ((g.get("gameOutcome") or {}).get("lastPeriodType") or "").upper()
    log("%s @ %s: final %s-%s%s, after one %s-%s" % (away, home, fin["fa"], fin["fh"], " (%s)" % how if how in ("OT", "SO") else "", fin.get("f5a", "?"), fin.get("f5h", "?")))
    return {"sport": "NHL", "gdate": "", "away": away, "home": home, "gameId": g.get("id"), "finals": fin, "notes": notes}


def make_nhl_slate(date_iso, out_dir, log):
    games = nhl_schedule(date_iso)
    if not games:
        log("No NHL games on the feed for %s." % date_iso)
    season_id = nhl_season_id(games, date_iso)
    summary = {}
    try:
        summary = nhl_team_summary(season_id)
    except Exception as e:  # noqa: BLE001
        log("Could not fetch the team summary report (%s); shots and special teams will be blank." % e)
    rows = []
    for g in games:
        try:
            rows.append(build_nhl_game(g, date_iso, season_id, summary, log))
        except Exception as e:  # noqa: BLE001
            log("%s @ %s: FAILED (%s); left out of the slate" % (nhl_name(g.get("awayTeam")), nhl_name(g.get("homeTeam")), e))
        log("")
    doc = {"format": FORMAT, "version": VERSION, "date": date_iso, "generated": now_utc(),
           "source": "slate.py nhl: NHL public feed", "games": rows}
    path = os.path.join(out_dir, "nhl-slate-%s.json" % date_iso)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    log("Wrote %s with %d game%s. Open Call Sheet 3.0 -> Saving -> Load slate. Confirm each goalie before betting." % (path, len(rows), "" if len(rows) == 1 else "s"))
    return path


def make_nhl_grade(date_iso, out_dir, log):
    games = nhl_schedule(date_iso)
    rows = []
    for g in games:
        try:
            r = grade_nhl_game(g, log)
            if r:
                r["gdate"] = date_iso
                rows.append(r)
        except Exception as e:  # noqa: BLE001
            log("a game failed to grade: %s" % e)
    doc = {"format": FORMAT, "version": VERSION, "date": date_iso, "generated": now_utc(),
           "source": "slate.py nhl-grade: NHL public feed", "games": rows}
    path = os.path.join(out_dir, "nhl-grade-%s.json" % date_iso)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    log("Wrote %s with %d final%s. Load it into Call Sheet 3.0 the same way; graded rows are never touched." % (path, len(rows), "" if len(rows) == 1 else "s"))
    return path


# ---- modes -----------------------------------------------------------------

def make_slate(date_iso, out_dir, log):
    parks = load_parks()
    games = schedule(date_iso)
    if not games:
        log("No MLB games on the feed for %s." % date_iso)
    season = str((games[0].get("season") if games else None) or date_iso[:4])
    rows = []
    for g in games:
        try:
            rows.append(build_game(g, parks, date_iso, season, log))
        except Exception as e:  # noqa: BLE001
            a = nickname((g.get("teams") or {}).get("away", {}).get("team", {}) or {})
            h = nickname((g.get("teams") or {}).get("home", {}).get("team", {}) or {})
            log("%s @ %s: FAILED (%s); left out of the slate" % (a, h, e))
        log("")
    doc = {"format": FORMAT, "version": VERSION, "date": date_iso, "generated": now_utc(),
           "source": "slate.py: MLB Stats API + Open-Meteo", "games": rows}
    path = os.path.join(out_dir, "slate-%s.json" % date_iso)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    log("Wrote %s with %d game%s. Open Call Sheet 2.0 -> Saving -> Load slate." % (path, len(rows), "" if len(rows) == 1 else "s"))
    return path


def make_grade(date_iso, out_dir, log):
    games = schedule(date_iso, hydrate="team,linescore")
    rows = []
    for g in games:
        try:
            r = grade_game(g, log)
            if r:
                rows.append(r)
        except Exception as e:  # noqa: BLE001
            log("a game failed to grade: %s" % e)
    dbl = {}
    for r in rows:
        k = (r["away"], r["home"])
        dbl[k] = dbl.get(k, 0) + 1
    for k, n in dbl.items():
        if n > 1:
            log("Doubleheader %s @ %s: the sheet keeps one row per matchup per date and takes the first game's finals." % k)
    doc = {"format": FORMAT, "version": VERSION, "date": date_iso, "generated": now_utc(),
           "source": "slate.py grade: MLB Stats API", "games": rows}
    path = os.path.join(out_dir, "grade-%s.json" % date_iso)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    log("Wrote %s with %d final%s. Load it into the sheet the same way; graded rows are never touched." % (path, len(rows), "" if len(rows) == 1 else "s"))
    return path


# ---- self test: the pure parts and one whole game through canned payloads --

def selftest():
    fails = []

    def check(name, cond):
        if not cond:
            fails.append(name)
        print(("  ok   " if cond else "  FAIL ") + name)

    print("innings")
    check("111.1 -> 111.33", abs(ip_decimal("111.1") - 111.3333) < 0.001)
    check("111.2 -> 111.67", abs(ip_decimal("111.2") - 111.6667) < 0.001)
    check("5.0 -> 5", ip_decimal("5.0") == 5.0)
    check("blank -> None", ip_decimal("") is None)
    check("fmt 1dp", fmt(111.3333, 1) == "111.3")
    check("fmt 0dp rounds", fmt(11.6, 0) == "12")
    check("fmt None blank", fmt(None, 2) == "")

    print("wind")
    # Wrigley: CF at 35 deg. A south-westerly (from 215) blows toward 35: out.
    check("from 215 at CF 35 -> out", resolve_dir(215, 35) == "out")
    check("from 35 at CF 35 -> in", resolve_dir(35, 35) == "in")
    check("from 125 at CF 35 -> cross", resolve_dir(125, 35) == "cross")
    check("from 170 at CF 35 -> quarter-out", resolve_dir(170, 35) == "quarter-out")
    check("from 80 at CF 35 -> quarter-in", resolve_dir(80, 35) == "quarter-in")
    check("wraps at north", resolve_dir(180, 0) == "out" and resolve_dir(350, 0) == "in")
    check("compass names", compass(0) == "N" and compass(225) == "SW" and compass(359) == "N")
    vm = vector_mean_dir([350, 10])
    check("vector mean across north", vm is not None and (vm < 5 or vm > 355))
    check("mlb wind out", parse_mlb_wind("12 mph, Out To CF") == (12, "out"))
    check("mlb wind cross", parse_mlb_wind("8 mph, L To R") == (8, "cross"))
    check("mlb wind quarter-in", parse_mlb_wind("15 mph, In From LF") == (15, "quarter-in"))
    check("mlb wind calm", parse_mlb_wind("0 mph, Calm") == (0, ""))
    check("mlb wind unknown", parse_mlb_wind("blustery") is None)

    print("bullpen")
    people = [
        {"id": 1, "stats": [{"group": {"displayName": "pitching"}, "splits": [{"stat": {"gamesPlayed": 30, "gamesStarted": 30, "inningsPitched": "180.0", "earnedRuns": 60}}]}]},
        {"id": 2, "stats": [{"group": {"displayName": "pitching"}, "splits": [{"stat": {"gamesPlayed": 60, "gamesStarted": 0, "inningsPitched": "60.0", "earnedRuns": 20}}]}]},
        {"id": 3, "stats": [{"group": {"displayName": "pitching"}, "splits": [{"stat": {"gamesPlayed": 40, "gamesStarted": 0, "inningsPitched": "30.0", "earnedRuns": 20}}]}]},
        {"id": 4, "stats": [{"group": {"displayName": "pitching"}, "splits": [{"stat": {"gamesPlayed": 20, "gamesStarted": 12, "inningsPitched": "70.0", "earnedRuns": 10}}]}]},
        {"id": 5, "stats": []},
    ]
    era, arms, ip = bullpen_era(people)
    check("starters excluded, relievers pooled", arms == 2 and abs(ip - 90.0) < 1e-9)
    check("era = 9*40/90 = 4.00", abs(era - 4.0) < 1e-9)
    era2, arms2, _ = bullpen_era(people, exclude_ids={2})
    check("excluding an arm", arms2 == 1 and abs(era2 - 6.0) < 1e-9)
    check("empty -> None", bullpen_era([]) == (None, 0, 0.0))
    seven = _canned_people(1000)["people"]
    era7, arms7, ip7 = bullpen_era(seven)
    check("seven-arm roster pen 108 ER / 260 IP = 3.74", arms7 == 7 and abs(ip7 - 260.0) < 1e-9 and abs(era7 - 9.0 * 108 / 260) < 1e-9)
    era5, arms5, ip5 = bullpen_era(seven, top=5)
    check("top five by appearances drops the two least used: 95 ER / 225 IP = 3.80", arms5 == 5 and abs(ip5 - 225.0) < 1e-9 and abs(era5 - 3.8) < 1e-9)
    era1, arms1, _ = bullpen_era(seven, top=1)
    check("top one is the most-used arm", arms1 == 1 and abs(era1 - 3.0) < 1e-9)

    print("last five starts")
    lg = _canned_gamelog(501)["stats"][0]["splits"]
    e5, i5, n5 = last_starts(lg, 5)
    check("last five starts skip relief and older starts: 9 ER / 29 IP", n5 == 5 and abs(i5 - 29.0) < 1e-9 and abs(e5 - 9.0 * 9 / 29) < 1e-9)
    e3, i3, n3 = last_starts(_canned_gamelog(601)["stats"][0]["splits"], 5)
    check("three starts only", n3 == 3 and abs(i3 - 13.3333) < 0.001 and abs(e3 - 6.75) < 0.001)
    check("no starts -> None", last_starts([{"date": "2026-09-01", "stat": {"gamesStarted": 0, "inningsPitched": "1.0", "earnedRuns": 0}}]) == (None, 0.0, 0))

    print("recent games")
    def fin(a, h, code="F"):
        return {"status": {"codedGameState": code, "detailedState": "Final" if code == "F" else "Scheduled"},
                "teams": {"away": {"score": a}, "home": {"score": h}}}
    gs = [fin(1, 2), fin(3, 4), fin(5, 5), fin(0, 0, "S")]
    avg, n = last_n_avg_total(gs, 10)
    check("unfinished game skipped", n == 3 and abs(avg - 20.0 / 3) < 1e-9)
    avg2, n2 = last_n_avg_total([fin(i, i) for i in range(12)], 10)
    check("last ten of twelve", n2 == 10 and abs(avg2 - 13.0) < 1e-9)
    check("nothing final", last_n_avg_total([fin(0, 0, "S")]) == (None, 0))

    print("linescore")
    ls = {"innings": [{"away": {"runs": 1}, "home": {"runs": 0}}, {"away": {"runs": 0}, "home": {"runs": 2}},
                      {"away": {"runs": 0}, "home": {"runs": 0}}, {"away": {"runs": 3}, "home": {"runs": 0}},
                      {"away": {"runs": 0}, "home": {"runs": 1}}, {"away": {"runs": 4}, "home": {"runs": 4}}]}
    check("f5 sums first five only", f5_from_linescore(ls) == (4, 3))
    check("short game -> None", f5_from_linescore({"innings": ls["innings"][:4]}) == (None, None))
    ls5 = {"innings": ls["innings"][:4] + [{"away": {"runs": 2}, "home": {}}]}
    check("home did not bat in the fifth", f5_from_linescore(ls5) == (6, 2))

    print("teams and parks")
    check("nickname by id", nickname({"id": 109, "name": "Arizona Diamondbacks"}) == "Diamondbacks")
    check("nickname fallback", nickname({"id": 9999, "name": "Springfield Isotopes"}) == "Isotopes")
    parks = load_parks()
    check("thirty clubs in parks.json", len(set(p["team"] for p in parks.values())) == 30)
    check("every park has lat, lon, bearing, roof", all(all(k in p for k in ("lat", "lon", "cf_bearing", "roof")) for p in parks.values()))
    check("roof values", all(p["roof"] in ("open", "retractable", "fixed") for p in parks.values()))
    check("find by name", find_park(parks, {"name": "Wrigley Field", "id": 17})[2] == "name")
    check("find by id when renamed", find_park(parks, {"name": "Some New Name", "id": 17})[0] == "Wrigley Field")
    check("unknown park", find_park(parks, {"name": "Estadio X", "id": 999999})[1] is None)
    check("lineup diff", missing_from_lineup({1, 2}, [1, 2, 3], {3: "Third Man"}) == ["Third Man"])

    print("one game through canned payloads")
    global fetch_json
    real = fetch_json
    canned = _canned()

    def fake(url, tries=3):
        for key, payload in canned:
            if key in url:
                return payload
        raise RuntimeError("no canned payload for " + url)
    fetch_json = fake
    lines = []
    try:
        row = build_game(canned_schedule()["dates"][0]["games"][0], parks, "2026-09-28", "2026", lines.append)
    finally:
        fetch_json = real
    i = row["inputs"]
    check("teams", row["away"] == "Diamondbacks" and row["home"] == "Padres" and row["sport"] == "MLB")
    check("starters named", row["starters"] == {"away": "Away Ace", "home": "Home Ace"})
    check("era and ip", i["aera"] == "3.31" and i["aip"] == "111.3" and i["hera"] == "4.01")
    check("last five on the slate", i["al5era"] == "2.79" and i["al5ip"] == "29.0" and i["hl5era"] == "6.75" and i["hl5ip"] == "13.3")
    check("short log noted", any("Home Ace has only 3 starts" in n for n in row["notes"]))
    check("runs per game", i["arpg"] == "4.48" and i["hrpg"] == "4.20")
    check("regular season: bullpen over the whole roster", i["abp"] == "3.74" and i["hbp"] == "3.74" and row["playoff"] is False)
    check("both pens on the record", row["pens"]["away"]["top5"] == "3.80" and row["pens"]["away"]["roster"] == "3.74")
    check("last ten", i["al10"] == "9.0" and i["hl10"] == "9.0")
    check("head to head", i["h2h"] == "9.0" and i["h2hn"] == "2")
    check("wind resolved", i["mph"] == "9" and i["dir"] == "out" and i["temp"] == "72" and i["dome"] is False)
    check("lines never in a slate", not any(k in i for k in ("total", "over", "under", "aml", "hml", "rl")))
    check("lineup listed", row["lineups"]["away"][:2] == ["Away Ace", "Leadoff Man"])
    check("missing starter noted", any("not in today's lineup" in n and "Benched Guy" in n for n in row["notes"]))
    check("home lineup not posted noted", any("Padres lineup not posted" in n for n in row["notes"]))
    doc = {"format": FORMAT, "version": VERSION, "date": "2026-09-28", "games": [row]}
    check("document round-trips as JSON", json.loads(json.dumps(doc))["games"][0]["inputs"]["dir"] == "out")

    # the same game as a postseason game: the pen becomes the top five
    fetch_json = fake
    try:
        pg = canned_schedule()["dates"][0]["games"][0]
        pg["gameType"] = "F"
        prow = build_game(pg, parks, "2026-09-28", "2026", lines.append)
    finally:
        fetch_json = real
    check("postseason: the pen is the top five by appearances", prow["playoff"] is True and prow["inputs"]["abp"] == "3.80" and prow["inputs"]["hbp"] == "3.80")
    check("postseason pen noted with the roster number", any("top five relievers by appearances, 3.80 (whole roster 3.74)" in n for n in prow["notes"]))

    gr = grade_game(canned_final(), lines.append)
    check("grade finals", gr["finals"] == {"fa": "4", "fh": "9", "f5a": "0", "f5h": "3"})
    check("grade skips live game", grade_game(canned_schedule()["dates"][0]["games"][0], lines.append) is None)

    print("nhl")
    check("nickname by abbrev", nhl_name({"abbrev": "TOR"}) == "Maple Leafs" and nhl_name({"abbrev": "UTA"}) == "Mammoth")
    check("nickname fallback", nhl_name({"abbrev": "XXX", "commonName": {"default": "Isotopes"}}) == "Isotopes")
    check("season id from the date", nhl_season_id([], "2026-10-07") == "20262027" and nhl_season_id([], "2027-03-01") == "20262027")
    gl = [{"id": 1, "name": "Starter", "sv": 0.915, "shots": 1500, "gp": 50, "gs": 50},
          {"id": 2, "name": "Backup", "sv": 0.900, "shots": 400, "gp": 15, "gs": 14}]
    check("likely starter: most starts", nhl_likely_starter(gl, 2, None)[0]["name"] == "Starter")
    check("likely starter: back to back goes to the rested goalie", nhl_likely_starter(gl, 0, 1)[0]["name"] == "Backup")
    check("likely starter: back to back, starter rested yesterday", nhl_likely_starter(gl, 0, 2)[0]["name"] == "Starter")
    check("no goalies", nhl_likely_starter([], 1, None)[0] is None)
    def ng(date, a, h, state="OFF", aab="TOR", hab="MTL", gid=1):
        return {"id": gid, "gameDate": date, "gameState": state, "awayTeam": {"abbrev": aab, "score": a}, "homeTeam": {"abbrev": hab, "score": h}}
    gs = [ng("2026-10-%02d" % d, 2, 3) for d in range(1, 13)] + [ng("2026-10-14", 1, 1, "FUT")]
    avg, n, fin = nhl_last_n_avg(gs, "2026-10-13", 10)
    check("last ten: finals before the date only", n == 10 and abs(avg - 5.0) < 1e-9 and len(fin) == 12)
    check("rest days from the last final", nhl_rest_days(fin, "2026-10-13") == 0 and nhl_rest_days(fin, "2026-10-15") == 2)
    land = {"summary": {"linescore": {"byPeriod": [{"periodDescriptor": {"number": 1}, "away": 1, "home": 0}, {"periodDescriptor": {"number": 2}, "away": 0, "home": 2}]}}}
    check("first period from the linescore", p1_from_landing(land) == (1, 0))
    check("no linescore -> None", p1_from_landing({}) == (None, None))
    # one hockey game through canned payloads
    nhl_canned = _canned_nhl()
    def fake_nhl(url, tries=3):
        for key, payload in nhl_canned:
            if key in url:
                return payload
        raise RuntimeError("no canned payload for " + url)
    fetch_json = fake_nhl
    try:
        lines2 = []
        row = build_nhl_game(nhl_schedule("2026-10-07")[0], "2026-10-07", "20262027", nhl_team_summary("20262027"), lines2.append)
        gr2 = grade_nhl_game(nhl_schedule("2026-10-06")[0], lines2.append)
    finally:
        fetch_json = real
    i = row["inputs"]
    check("nhl teams", row["away"] == "Rangers" and row["home"] == "Bruins" and row["sport"] == "NHL")
    check("nhl team rates", i["asf"] == "31.2" and i["hsf"] == "33.4" and i["app"] == "22.1" and i["hpk"] == "78.1")
    # the Rangers are on a back to back and Igor started yesterday, so the slate names the backup
    check("nhl goalies: likely starters with sv and shots", row["starters"] == {"away": "Jonathan Q", "home": "Jeremy S"} and i["agsv"] == "0.902" and i["agsh"] == "500" and i["hgsv"] == "0.921" and i["hgsh"] == "1900")
    check("nhl rest and last ten", i["arest"] == "0" and i["hrest"] == "2" and i["al10"] == "5.9" and i["hl10"] == "6.4")
    check("nhl head to head", i["h2h"] == "5.5" and i["h2hn"] == "2")
    check("nhl: the back-to-back side gets the rested goalie", any("did not start yesterday" in n for n in row["notes"]))
    check("nhl: never confirmed", all("NOT confirmed" in n for n in row["notes"] if "likely starter" in n))
    check("nhl grade: final with the period score", gr2["finals"] == {"fa": "2", "fh": "3", "f5a": "1", "f5h": "0"})

    print()
    if fails:
        print("%d check%s failed: %s" % (len(fails), "" if len(fails) == 1 else "s", ", ".join(fails)))
        return 1
    print("all checks passed")
    return 0


def canned_schedule():
    return {"dates": [{"date": "2026-09-28", "games": [{
        "gamePk": 777001, "gameDate": "2026-09-28T23:40:00Z", "season": "2026", "officialDate": "2026-09-28",
        "status": {"codedGameState": "S", "detailedState": "Scheduled"},
        "venue": {"id": 2680, "name": "Petco Park"},
        "teams": {"away": {"team": {"id": 109, "name": "Arizona Diamondbacks"}, "probablePitcher": {"id": 501, "fullName": "Away Ace"}},
                  "home": {"team": {"id": 135, "name": "San Diego Padres"}, "probablePitcher": {"id": 601, "fullName": "Home Ace"}}},
    }]}]}


def canned_final():
    return {"gamePk": 777000, "gameDate": "2026-09-27T23:40:00Z", "officialDate": "2026-09-27",
            "status": {"codedGameState": "F", "detailedState": "Final"},
            "teams": {"away": {"team": {"id": 109}, "score": 4}, "home": {"team": {"id": 135}, "score": 9}},
            "linescore": {"innings": [{"away": {"runs": 0}, "home": {"runs": 1}}, {"away": {"runs": 0}, "home": {"runs": 0}},
                                      {"away": {"runs": 0}, "home": {"runs": 2}}, {"away": {"runs": 0}, "home": {"runs": 0}},
                                      {"away": {"runs": 0}, "home": {"runs": 0}}, {"away": {"runs": 4}, "home": {"runs": 6}}]}}


def _canned_people(base):
    """A rotation arm plus seven relievers with distinct usage, so the top-five
    pen (by appearances) is a different number from the whole-roster pen."""
    def arm(k, gp, gs, ip, er):
        return {"id": base + k, "stats": [{"group": {"displayName": "pitching"}, "splits": [{"stat": {"gamesPlayed": gp, "gamesStarted": gs, "inningsPitched": ip, "earnedRuns": er}}]}]}
    return {"people": [
        arm(1, 30, 30, "180.0", 60),   # a starter: never in the pen
        arm(2, 60, 0, "60.0", 20),     # 3.00, most used
        arm(3, 40, 0, "30.0", 20),     # 6.00
        arm(4, 55, 0, "50.0", 10),
        arm(5, 50, 0, "45.0", 15),
        arm(6, 45, 0, "40.0", 30),
        arm(7, 20, 0, "25.0", 5),      # rarely used: out of the top five
        arm(8, 10, 0, "10.0", 8),      # rarely used: out of the top five
    ]}


def _canned_gamelog(pid):
    def game(date, gs, ip, er):
        return {"date": date, "stat": {"gamesStarted": gs, "inningsPitched": ip, "earnedRuns": er}}
    if pid == 501:
        splits = [game("2026-08-01", 1, "3.0", 5),    # sixth-last start: dropped
                  game("2026-08-07", 1, "6.0", 1), game("2026-08-13", 1, "5.0", 2), game("2026-08-19", 1, "7.0", 0),
                  game("2026-08-22", 0, "1.0", 3),    # relief appearance: skipped
                  game("2026-08-25", 1, "5.0", 4), game("2026-08-31", 1, "6.0", 2)]
    else:
        splits = [game("2026-09-05", 1, "4.0", 3), game("2026-09-12", 1, "5.0", 3), game("2026-09-19", 1, "4.1", 4)]
    return {"stats": [{"group": {"displayName": "pitching"}, "splits": splits}]}


def _canned():
    def pitcher(era, ip):
        return {"stats": [{"splits": [{"stat": {"era": era, "inningsPitched": ip}}]}]}

    def hitting(runs, gp):
        return {"stats": [{"splits": [{"stat": {"runs": runs, "gamesPlayed": gp}}]}]}

    people = _canned_people

    def roster(base):
        return {"roster": [{"person": {"id": base + k}, "position": {"abbreviation": "P"}} for k in range(1, 9)]}

    def recent(tid):
        gs = []
        for k in range(12):
            gs.append({"gamePk": 700000 + tid * 100 + k, "gameDate": "2026-09-%02dT23:00:00Z" % (10 + k),
                       "status": {"codedGameState": "F", "detailedState": "Final"},
                       "teams": {"away": {"team": {"id": tid}, "score": 4}, "home": {"team": {"id": 999}, "score": 5}}})
        return {"dates": [{"games": gs}]}

    h2h = {"dates": [{"games": [
        {"status": {"codedGameState": "F"}, "teams": {"away": {"score": 3}, "home": {"score": 5}}},
        {"status": {"codedGameState": "F"}, "teams": {"away": {"score": 6}, "home": {"score": 4}}},
        {"status": {"codedGameState": "S"}, "teams": {"away": {}, "home": {}}},
    ]}]}
    # Petco's CF bearing is 0 in parks.json; a wind FROM 180 (south) blows out.
    hours = ["2026-09-28T%02d:00" % h for h in range(24)] + ["2026-09-29T%02d:00" % h for h in range(24)]
    meteo = {"hourly": {"time": hours, "temperature_2m": [72.0] * 48, "wind_speed_10m": [9.0] * 48, "wind_direction_10m": [180.0] * 48}}
    box_today = {"teams": {
        "away": {"battingOrder": [501, 502, 503], "players": {"ID501": {"person": {"id": 501, "fullName": "Away Ace"}},
                                                             "ID502": {"person": {"id": 502, "fullName": "Leadoff Man"}},
                                                             "ID503": {"person": {"id": 503, "fullName": "Cleanup Man"}}}},
        "home": {"battingOrder": [], "players": {}}}}
    box_last = {"teams": {
        "away": {"battingOrder": [502, 503, 504], "players": {"ID502": {"person": {"id": 502, "fullName": "Leadoff Man"}},
                                                             "ID503": {"person": {"id": 503, "fullName": "Cleanup Man"}},
                                                             "ID504": {"person": {"id": 504, "fullName": "Benched Guy"}}}},
        "home": {"battingOrder": [], "players": {}}}}
    return [
        ("/people/501/stats?stats=gameLog", _canned_gamelog(501)),
        ("/people/601/stats?stats=gameLog", _canned_gamelog(601)),
        ("/people/501/stats", pitcher("3.31", "111.1")),
        ("/people/601/stats", pitcher("4.01", "134.2")),
        ("/teams/109/stats", hitting(699, 156)),
        ("/teams/135/stats", hitting(655, 156)),
        ("/teams/109/roster", roster(1000)),
        ("/teams/135/roster", roster(2000)),
        ("personIds=1001", people(1000)),
        ("personIds=2001", people(2000)),
        ("opponentId=135", h2h),
        ("teamId=109", recent(109)),
        ("teamId=135", recent(135)),
        ("open-meteo", meteo),
        ("/game/777001/boxscore", box_today),
        ("/boxscore", box_last),
    ]


def _canned_nhl():
    def game(gid, date, aab, hab, a=None, h=None, state="FUT"):
        return {"id": gid, "season": 20262027, "gameType": 2, "gameDate": date, "startTimeUTC": date + "T23:00:00Z",
                "gameState": state, "venue": {"default": "TD Garden"},
                "awayTeam": {"id": 3 if aab == "NYR" else 6, "abbrev": aab, "score": a},
                "homeTeam": {"id": 6 if hab == "BOS" else 3, "abbrev": hab, "score": h}}
    sched7 = {"gameWeek": [{"date": "2026-10-07", "games": [game(2026020010, "2026-10-07", "NYR", "BOS")]}]}
    sched6 = {"gameWeek": [{"date": "2026-10-06", "games": [game(2026020005, "2026-10-06", "NYR", "BOS", 2, 3, "OFF")]}]}
    summary = {"data": [
        {"teamId": 3, "teamFullName": "New York Rangers", "gamesPlayed": 10, "shotsForPerGame": 31.2, "powerPlayPct": 0.221, "penaltyKillPct": 0.802},
        {"teamId": 6, "teamFullName": "Boston Bruins", "gamesPlayed": 10, "shotsForPerGame": 33.4, "powerPlayPct": 0.248, "penaltyKillPct": 0.781}]}
    def club(abbrev, goalies):
        return {"goalies": [{"playerId": pid, "firstName": {"default": fn}, "lastName": {"default": ln}, "savePercentage": sv,
                             "shotsAgainst": sh, "gamesPlayed": gp, "gamesStarted": gs} for pid, fn, ln, sv, sh, gp, gs in goalies]}
    nyr = club("NYR", [(1, "Igor", "S", 0.912, 1400, 48, 47), (2, "Jonathan", "Q", 0.902, 500, 18, 17)])
    bos = club("BOS", [(3, "Jeremy", "S", 0.921, 1900, 60, 60), (4, "Joonas", "K", 0.898, 300, 12, 11)])
    def season(abbrev, opp, last_dates, totals, h2h_dates):
        gs = []
        for k, d in enumerate(last_dates):
            o = opp if d in h2h_dates else "XXX"
            gs.append({"id": 900 + k, "gameType": 2, "gameDate": d, "gameState": "OFF",
                       "awayTeam": {"abbrev": abbrev, "score": totals[k] - 2}, "homeTeam": {"abbrev": o, "score": 2}})
        return {"games": gs}
    nyr_dates = ["2026-09-%02d" % d for d in range(20, 30)] + ["2026-10-06"]
    bos_dates = ["2026-09-%02d" % d for d in range(20, 30)] + ["2026-10-04"]
    # eleven finals; the last ten average 5.9, and the two meetings with Boston (28 Sept, 6 Oct) average 5.5
    nyr_season = season("NYR", "BOS", nyr_dates, [7, 6, 6, 6, 6, 6, 6, 6, 5, 6, 6], ["2026-09-28", "2026-10-06"])
    bos_season = season("BOS", "NYR", bos_dates, [6, 6, 7, 7, 6, 6, 7, 6, 6, 7, 6], [])
    box = {"awayTeam": {"abbrev": "NYR"}, "homeTeam": {"abbrev": "XXX"},
           "playerByGameStats": {"awayTeam": {"goalies": [{"playerId": 1, "starter": True}, {"playerId": 2, "starter": False}]}, "homeTeam": {"goalies": []}}}
    landing = {"summary": {"linescore": {"byPeriod": [{"periodDescriptor": {"number": 1}, "away": 1, "home": 0},
                                                      {"periodDescriptor": {"number": 2}, "away": 1, "home": 2}, {"periodDescriptor": {"number": 3}, "away": 0, "home": 1}]}}}
    return [
        ("/schedule/2026-10-07", sched7), ("/schedule/2026-10-06", sched6),
        ("team/summary", summary),
        ("/club-stats/NYR/", nyr), ("/club-stats/BOS/", bos),
        ("/club-schedule-season/NYR/", nyr_season), ("/club-schedule-season/BOS/", bos_season),
        ("/boxscore", box), ("/landing", landing),
    ]


# ---- main ------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description="Write the day's slate (or yesterday's finals) for Call Sheet 2.0.")
    ap.add_argument("mode", nargs="?", choices=["slate", "grade", "nhl", "nhl-grade"], default="slate",
                    help="slate (default): today's MLB inputs. grade: MLB finals. nhl: today's NHL inputs. nhl-grade: NHL finals.")
    ap.add_argument("--date", help="YYYY-MM-DD. Default: today for slate, yesterday for grade.")
    ap.add_argument("--out", default=".", help="folder to write into (default: where you run it)")
    ap.add_argument("--selftest", action="store_true", help="run the offline checks and exit")
    ap.add_argument("--quiet", action="store_true", help="print only the final line")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if sys.version_info < (3, 7):
        print("This needs Python 3.7 or newer; you have %s." % sys.version.split()[0])
        return 2
    today = dt.date.today()
    if a.date:
        try:
            date_iso = dt.date.fromisoformat(a.date).isoformat()
        except ValueError:
            print("--date must look like 2026-09-28")
            return 2
    else:
        date_iso = (today if a.mode in ("slate", "nhl") else today - dt.timedelta(days=1)).isoformat()
    lines = []

    def log(s):
        if not a.quiet:
            print(s)
        lines.append(s)
    try:
        if a.mode == "grade":
            path = make_grade(date_iso, a.out, log)
        elif a.mode == "nhl":
            path = make_nhl_slate(date_iso, a.out, log)
        elif a.mode == "nhl-grade":
            path = make_nhl_grade(date_iso, a.out, log)
        else:
            path = make_slate(date_iso, a.out, log)
    except Exception as e:  # noqa: BLE001
        print("Stopped: %s" % e)
        print("If this says a name could not be resolved, the computer is offline or the site is blocked.")
        return 1
    if a.quiet:
        print(lines[-1] if lines else path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
