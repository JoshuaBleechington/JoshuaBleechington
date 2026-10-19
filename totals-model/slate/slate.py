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
import csv
import datetime as dt
import gzip
import html
import io
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

FORMAT = "callsheet2.slate"
VERSION = 1
EN_MIN_GAMES = 10     # empty-net habits wait for ten finals a club (totals/nhl.py EN_MIN_GAMES)
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
_last_headers = {}   # the headers of the last document fetched (The Odds API counts credits in them)


def fetch_json(url, tries=3, headers=None, timeout=25, cache=True):
    """GET a JSON document. Retries twice on a network error, caches by URL.
    `headers` replaces the default pair (the NBA stats site wants a browser's
    and answers gzipped); `cache=False` for the thousand box scores of a
    ledger pull, which would otherwise sit in memory for the whole run."""
    if url in _cache:
        return _cache[url]
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers or {"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
                    raw = gzip.decompress(raw)
                data = json.loads(raw.decode("utf-8"))
                _last_headers.clear()
                _last_headers.update({k.lower(): v for k, v in r.headers.items()})
            if cache:
                _cache[url] = data
            return data
        except (OSError, ValueError) as e:  # URLError and HTTPError are OSErrors; so is a socket timeout
            last = e
            if i + 1 < tries:
                time.sleep(1.5 * (i + 1))
    raise RuntimeError("%s -> %s" % (url.split("?")[0], last))


def fetch_text(url, tries=3):
    """GET a text document (a CSV). Same retries and cache as fetch_json."""
    if url in _cache:
        return _cache[url]
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/csv,text/plain,*/*"})
            with urllib.request.urlopen(req, timeout=40) as r:
                data = r.read().decode("utf-8", "replace")
            _cache[url] = data
            return data
        except (OSError, ValueError) as e:
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
        # the park factor: Statcast's figure, kept in parks.json (read once a season)
        if park.get("pf") is not None:
            inputs["pf"] = str(park["pf"])
            log("  park factor: %s (Statcast, from parks.json)" % inputs["pf"])
        else:
            notes.append("%s has no park factor in parks.json: type it from Statcast." % pname)
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
                # The bearing check: when the stadium's own read and the forecast
                # both exist, they verify the centre-field bearing on file without
                # a park diagram. "Out" from a wind blowing toward X degrees says
                # the bearing is near X; the file's bearing either agrees or not.
                if w and dir2 and mph2 >= 5:
                    toward = (w["from_deg"] + 180.0) % 360.0
                    agree = (dir2 == d)
                    out["bearing_check"] = {"mlb": dir2, "forecast": d, "wind_toward_deg": round(toward), "cf_bearing": park["cf_bearing"], "agree": agree}
                    log("  bearing check: the stadium says %s, the forecast wind blows toward %d deg and the %d deg bearing on file calls that %s -> %s"
                        % (dir2, round(toward), park["cf_bearing"], d, "agree" if agree else "DISAGREE: check %s's bearing" % pname))
                    if not agree:
                        notes.append("Bearing check: MLB's stadium read says %s where the forecast at the %d-degree bearing says %s. The file's bearing for %s may be wrong; the stadium read was used." % (dir2, park["cf_bearing"], d, pname))
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


def nhl_prev_season(season_id):
    y = int(str(season_id)[:4])
    return "%d%d" % (y - 1, y)


def nhl_roster_goalie_ids(abbrev):
    d = nhl_api("/roster/%s/current" % abbrev)
    return set(int(g["id"]) for g in (d.get("goalies") or []) if g.get("id") is not None)


#: How much of last season a goalie carries into this one: half his shots.
#: The sheet shrinks a save percentage toward the league by the shots behind
#: it (stable near 1,340), so without this a goalie's first start of the year
#: -- .739 on 23 shots, 1 Oct 2026 -- went on the sheet as his line, and his
#: prior was the league's, not his own. A year-old season is evidence about
#: the man; it just is not as good as this year's will be.
GOALIE_PRIOR_SHARE = 0.5
#: A backup in net (Call Sheet 3.0's Backup box): the named starter has
#: under this share of his club's starts this season, once the club has
#: BACKUP_MIN_STARTS to share. Same figures as totals/nhl.py, measured 7
#: Oct 2026: one backup in a game, the total landed 0.18 under the close.
BACKUP_SHARE = 0.30
BACKUP_MIN_STARTS = 10


def nhl_is_backup(pick, goalies):
    """True when the likely starter is his club's backup: under BACKUP_SHARE
    of the club's starts this season, ten starts in. Last season's lines (a
    club that has not played) never qualify: the flag is about this season."""
    if not pick or pick.get("season"):
        return False
    starts = sum(int(g.get("gs") or 0) for g in goalies if not g.get("season"))
    if starts < BACKUP_MIN_STARTS:
        return False
    return int(pick.get("gs") or 0) < BACKUP_SHARE * starts


# ---- the goalie lineups: RotoWire and CBS (19 Oct 2026) ---------------------
# The slate's likely starter is a guess from the club's starts. RotoWire's
# lineup page names tonight's goalie for each club and marks him CONFIRMED
# (green) or EXPECTED (yellow); CBS's goalie depth chart lists each club's
# starter, backup and reserves with its news blurbs. On 17 Oct 2026 the user
# ticked Confirmed on 21 goalies and 6 of them did not play, so the slate now
# reads both: a goalie RotoWire names replaces the guess (his line follows), a
# confirmed start ticks the sheet's Confirmed box, an expected one is said to
# be expected, and the Backup box follows CBS's depth chart until the club has
# the ten starts the starts rule needs. RotoWire shows today and tomorrow only
# (?date=tomorrow; a date in the query is ignored), so any other day gets no
# lineups and says so. Either page may fail alone; the slate still writes.
ROTOWIRE_NHL = "https://www.rotowire.com/hockey/nhl-lineups.php"
CBS_NHL_GOALIES = "https://www.cbssports.com/fantasy/hockey/depth-chart/G/"
CBS_NHL_CODES = {"CLB": "CBJ", "MON": "MTL", "NJ": "NJD", "TB": "TBL", "WAS": "WSH", "LA": "LAK", "LV": "VGK", "SJ": "SJS"}


def _name_key(name):
    """'A. Vasilevskiy' / 'Andrei Vasilevskiy' -> ('a', 'vasilevskiy'): the first
    initial (blank when the name is one word) and the surname, accents and
    punctuation dropped, so the three sites' spellings meet."""
    s = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode("ascii").lower()
    parts = [p for p in re.split(r"[^a-z]+", s) if p]
    if not parts:
        return ("", "")
    return (parts[0][0] if len(parts) > 1 else "", parts[-1])


def nhl_goalie_match(name, goalies):
    """The club-page goalie a lineup name refers to: the same surname, and the
    same first initial when two goalies share one. None when nobody matches."""
    ini, sur = _name_key(name)
    if not sur:
        return None
    found = [g for g in goalies if _name_key(g.get("name"))[1] == sur]
    if len(found) > 1 and ini:
        found = [g for g in found if _name_key(g.get("name"))[0] == ini]
    return found[0] if len(found) == 1 else None


def nhl_backup_source(pick, goalies, cb):
    """Why the Backup box is ticked: 'starts' by the starts rule (nhl_is_backup),
    'cbs' when the club has under BACKUP_MIN_STARTS and CBS's depth chart lists
    the named goalie as the backup, else None. The starts rule is the measured
    one; CBS only speaks in the weeks before it can."""
    if nhl_is_backup(pick, goalies):
        return "starts"
    if not pick or pick.get("season") or not cb:
        return None
    starts = sum(int(g.get("gs") or 0) for g in goalies if not g.get("season"))
    if starts >= BACKUP_MIN_STARTS:
        return None
    sur = _name_key(cb.get("backup"))[1]
    return "cbs" if sur and sur == _name_key(pick.get("name"))[1] else None


def _rw_date_iso(line):
    """'October 19, 2026' -> '2026-10-19', or None."""
    try:
        return dt.datetime.strptime(str(line or "").strip(), "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def parse_rotowire_goalies(text):
    """RotoWire's NHL lineups page -> (the page's date line, {nickname: {name,
    status, opp, home}}). Each game is a `lineup is-nhl` box: two `lineup__mteam`
    names, and two `lineup__list`s whose `lineup__player-highlight` is the
    goalie, with a status row under his name whose class says confirmed or
    expected (the word beside the dot is kept when the class is something new)."""
    m = re.search(r"Starting NHL lineups for ([A-Za-z]+ \d{1,2}, \d{4})", text)
    page_date = m.group(1) if m else ""
    out = {}
    for box in text.split('<div class="lineup is-nhl">')[1:]:
        names = {}
        for side, nm in re.findall(r'lineup__mteam is-(visit|home)[^"]*">\s*([^<]+?)\s*<', box):
            names[side] = re.sub(r"\s+", " ", nm).strip()
        if len(names) != 2:
            continue
        for side in ("visit", "home"):
            lst = re.search(r'<ul class="lineup__list is-%s">(.*?)</ul>' % side, box, re.S)
            li = re.search(r'<li class="lineup__player-highlight">(.*?)</li>', lst.group(1), re.S) if lst else None
            nm = re.search(r'highlight-name">\s*<a[^>]*>([^<]+)</a>', li.group(1)) if li else None
            if not nm:
                continue
            st = re.search(r'align-center is-([a-z]+)"', li.group(1))
            word = re.search(r"</div>\s*([A-Za-z][A-Za-z ]*?)\s*</div>\s*$", li.group(1).strip())
            status = st.group(1) if st else (word.group(1).strip().lower() if word else "")
            out[names[side]] = {"name": re.sub(r"\s+", " ", nm.group(1)).strip(), "status": status,
                                "opp": names["home" if side == "visit" else "visit"], "home": side == "home"}
    return page_date, out


def parse_cbs_goalies(text):
    """CBS's goalie depth chart -> {tricode: {starter, backup, reserves, news}}:
    one table row a club (CBS's own codes mapped to the league's), the long
    name of each goalie in the Starter, Backup and Reserves cells, and the
    tooltip beside a name (an injury, or the day's blurb) under `news` by name."""
    out = {}
    cell_names = re.compile(r'CellPlayerName--long">\s*<span[^>]*>\s*<a [^>]*>([^<]+)</a>')
    tips = re.compile(r'CellPlayerName--long">\s*<span[^>]*>\s*<a [^>]*>([^<]+)</a>\s*<span class="CellPlayerName-icon[^"]*">.*?Tablebase-tooltipInner">\s*(.*?)\s*</div>', re.S)
    for row in re.findall(r'<tr class="TableBase-bodyTr">(.*?)</tr>', text, re.S):
        cells = re.findall(r'<td class="TableBase-bodyTd[^"]*">(.*?)</td>', row, re.S)
        if len(cells) < 3:
            continue
        m = re.search(r"/nhl/teams/([A-Z]+)/", cells[0])
        if not m:
            continue
        ab = CBS_NHL_CODES.get(m.group(1), m.group(1))
        news = {}
        for c in cells[1:]:
            for nm, tip in tips.findall(c):
                news[nm.strip()] = re.sub(r"\s+", " ", html.unescape(tip)).strip()
        out[ab] = {"starter": (cell_names.findall(cells[1]) or [""])[0].strip(),
                   "backup": (cell_names.findall(cells[2]) or [""])[0].strip(),
                   "reserves": [x.strip() for x in cell_names.findall(cells[3])] if len(cells) > 3 else [],
                   "news": news}
    return out


def nhl_lineups(date_iso, log):
    """Tonight's goalies from RotoWire (today's page, or tomorrow's) and the
    depth chart from CBS: {"rw": {nickname: ...}, "rw_date": the page's date
    line, "cbs": {tricode: ...}}, with whatever came back. A page that fails,
    or a RotoWire page for another day, leaves its part empty and is logged."""
    out = {"rw": {}, "rw_date": "", "cbs": {}}
    today = dt.date.today()
    try:
        want = dt.date.fromisoformat(date_iso)
    except ValueError:
        want = None
    url = None
    if want == today:
        url = ROTOWIRE_NHL
    elif want == today + dt.timedelta(days=1):
        url = ROTOWIRE_NHL + "?date=tomorrow"
    else:
        log("RotoWire lineups: the page shows today and tomorrow only, and %s is neither; the goalies are the slate's guess." % date_iso)
    if url:
        try:
            page_date, rw = parse_rotowire_goalies(fetch_text(url))
            shown = _rw_date_iso(page_date)
            if shown and shown != date_iso:
                log("RotoWire lineups: the page is for %s, not %s; not used." % (page_date, date_iso))
            elif not rw:
                log("RotoWire lineups: no goalies on the page yet (%s)." % (page_date or "no date on it"))
            else:
                out["rw"], out["rw_date"] = rw, page_date
                log("RotoWire lineups for %s: %d goalies named, %d confirmed." % (page_date or date_iso, len(rw), sum(1 for v in rw.values() if v["status"] == "confirmed")))
        except Exception as e:  # noqa: BLE001
            log("RotoWire lineups: not read (%s); the goalies are the slate's guess." % e)
    try:
        out["cbs"] = parse_cbs_goalies(fetch_text(CBS_NHL_GOALIES))
        log("CBS goalie depth chart: %d clubs." % len(out["cbs"]))
    except Exception as e:  # noqa: BLE001
        log("CBS goalie depth chart: not read (%s)." % e)
    return out


def nhl_goalie_prior(player_id, prev_season):
    """Last regular season's line for one goalie, from his player page,
    summed across clubs if he moved: (save %, shots) or None."""
    d = nhl_api("/player/%s/landing" % player_id)
    shots = saves = 0.0
    for row in d.get("seasonTotals") or []:
        if str(row.get("season")) != str(prev_season) or str(row.get("gameTypeId", 2)) != "2":
            continue
        if row.get("leagueAbbrev") not in (None, "NHL"):
            continue
        sa = row.get("shotsAgainst")
        if sa in (None, "") or int(sa) <= 0:
            continue
        sa = int(sa)
        ga = row.get("goalsAgainst")
        if ga not in (None, ""):
            sv = sa - int(ga)
        elif row.get("savePctg") not in (None, ""):
            sv = float(row["savePctg"]) * sa
        else:
            continue
        shots += sa
        saves += sv
    if shots <= 0:
        return None
    return (saves / shots, int(shots))


def nhl_blend_prior(g, prior, prev):
    """This season's line plus half of last season's, as one line. The entry
    keeps both halves so the printout can show them."""
    psv, pshots = prior
    w = int(round(pshots * GOALIE_PRIOR_SHARE))
    now_sv, now_shots = g.get("sv"), int(g.get("shots") or 0)
    g["this"] = {"sv": now_sv, "shots": now_shots}
    g["prior"] = {"sv": psv, "shots": pshots, "season": prev}
    tot = now_shots + w
    if tot <= 0:
        return g
    g["sv"] = ((now_sv or 0.0) * now_shots + psv * w) / float(tot)
    g["shots"] = tot
    return g


def nhl_club_goalies(abbrev, season_id=None):
    """This season's goalies from the club page, each blended with half of
    his last season (nhl_blend_prior). When nobody has a shot yet (a team
    that has not played), LAST season's page for the goalies still on the
    roster, with the shots halved -- the same half, by another route. Each
    entry says which."""
    out = _club_goalies(nhl_api("/club-stats/%s/now" % abbrev))
    if not season_id:
        return out
    prev = nhl_prev_season(season_id)
    if any(g["shots"] > 0 for g in out):
        for g in out:
            if g.get("id") is None:
                continue
            try:
                prior = nhl_goalie_prior(g["id"], prev)
            except Exception:  # noqa: BLE001
                prior = None
            if prior:
                nhl_blend_prior(g, prior, prev)
        return out
    try:
        roster = nhl_roster_goalie_ids(abbrev)
    except Exception:  # noqa: BLE001
        roster = set()
    last = _club_goalies(nhl_api("/club-stats/%s/%s/2" % (abbrev, prev)))
    kept = []
    for g in last:
        if roster and g["id"] not in roster:
            continue
        g = dict(g)
        g["shots"] = g["shots"] // 2
        g["season"] = prev
        kept.append(g)
    return kept or out


def _club_goalies(d):
    out = []
    for g in d.get("goalies") or []:
        name = " ".join(x for x in [(g.get("firstName") or {}).get("default") if isinstance(g.get("firstName"), dict) else g.get("firstName"),
                                    (g.get("lastName") or {}).get("default") if isinstance(g.get("lastName"), dict) else g.get("lastName")] if x)
        sv = g.get("savePercentage", g.get("savePctg"))
        out.append({"id": g.get("playerId"), "name": name or str(g.get("playerId")),
                    "sv": None if sv in (None, "") else float(sv),
                    "shots": int(g.get("shotsAgainst") or 0), "gp": int(g.get("gamesPlayed") or 0),
                    "gs": int(g.get("gamesStarted") or 0), "season": None})
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


def nhl_season_rates(fin_games, abbrev):
    """The club's goals for and against per game over its finals this season,
    and how many finals: (gf, ga, n). The sheet scores them FADED (13 Oct
    2026): the market over-moves with a club's scoring rates, two seasons
    running, so the lean goes on the line with the opposite sign."""
    gf = ga = n = 0
    for g in fin_games:
        a, h = g.get("awayTeam") or {}, g.get("homeTeam") or {}
        if a.get("score") is None or h.get("score") is None:
            continue
        us, them = (h, a) if h.get("abbrev") == abbrev else (a, h)
        gf += int(us["score"])
        ga += int(them["score"])
        n += 1
    return (gf / float(n), ga / float(n), n) if n else (None, None, 0)


def nhl_league_gpg(ledger_games, date_iso, min_games=20):
    """The league's goals a game this season to date, from the ledger: the
    number a club's scoring rates are read against. None under min_games."""
    tots = [g["fa"] + g["fh"] for g in (ledger_games or [])
            if g.get("fa") is not None and g.get("fh") is not None and (g.get("date") or "") < date_iso]
    return sum(tots) / float(len(tots)) if len(tots) >= min_games else None


def nhl_ledger_tables(ledger_games, date_iso):
    """Every club's season to date from the league ledger, before a date:
    {abbrev: {gf, ga, n, l10, enc, ens}} with goals for and against per game,
    the last-ten average total and empty-netters conceded and scored per
    game. The context card ranks a club against the other 31 from this one
    table (14 Oct 2026)."""
    per = {}
    for g in sorted(ledger_games or [], key=lambda g: (g.get("date") or "", g.get("id") or 0)):
        if g.get("fa") is None or g.get("fh") is None or (g.get("date") or "") >= date_iso:
            continue
        tot = g["fa"] + g["fh"]
        for ab, us, them, enc, ens in ((g.get("home"), g["fh"], g["fa"], g.get("ena"), g.get("enh")),
                                        (g.get("away"), g["fa"], g["fh"], g.get("enh"), g.get("ena"))):
            if not ab:
                continue
            d = per.setdefault(ab, {"gf": 0, "ga": 0, "n": 0, "tots": [], "enc": 0, "ens": 0, "en_n": 0})
            d["gf"] += us
            d["ga"] += them
            d["n"] += 1
            d["tots"].append(tot)
            if enc is not None and ens is not None:
                d["enc"] += enc
                d["ens"] += ens
                d["en_n"] += 1
    out = {}
    for ab, d in per.items():
        n = d["n"]
        out[ab] = {"gf": d["gf"] / float(n), "ga": d["ga"] / float(n), "n": n,
                   "l10": sum(d["tots"][-10:]) / float(len(d["tots"][-10:])),
                   "enc": (d["enc"] / float(d["en_n"])) if d["en_n"] else None,
                   "ens": (d["ens"] / float(d["en_n"])) if d["en_n"] else None, "en_n": d["en_n"]}
    return out


def nhl_goalie_summary(season_id):
    """Every goalie's season line from the stats REST goalie report, keyed by
    player id: {name, team, sv, shots, gs}. One call for the league; the
    context card ranks the named starter among the goalies with CTX_GOALIE_SHOTS."""
    q = urllib.parse.urlencode({"cayenneExp": "seasonId=%s and gameTypeId=2" % season_id, "limit": -1})
    d = fetch_json(NHL_STATS + "/goalie/summary?" + q)
    out = {}
    for r in d.get("data") or []:
        pid = r.get("playerId")
        if pid is None or r.get("savePct") in (None, "") or not r.get("shotsAgainst"):
            continue
        try:
            out[int(pid)] = {"name": r.get("goalieFullName") or r.get("lastName") or str(pid), "team": r.get("teamAbbrevs") or "",
                             "sv": float(r["savePct"]), "shots": int(r["shotsAgainst"]), "gs": int(r.get("gamesStarted") or 0)}
        except (TypeError, ValueError):
            continue
    return out


# ---- the context card (14 Oct 2026, at the user's word: "little bits of info like
# Bruins have the 4th worst defense in the league") -------------------------
# Each line is a club's rank against the other 31 on a number the slate
# already holds, with a TAG that says what the sheet did with the fact:
# scored (at its weight), faded (the market over-moves with it), shown (it
# measured null or the wrong way against the close) or a label. The tag is
# the point: "4th worst defence" is what the public bets and the book
# shades to, and the card says so next to it. Lines appear when a club sits
# in the top or bottom CTX_NOTABLE of the league; the named goalie always.
CTX_NOTABLE = 8
CTX_MIN_CLUBS = 16
CTX_GOALIE_SHOTS = 100
CTX_TAGS = {
    "rates": ("faded", "scored, faded: the market over-moves with scoring reputations, so the lean goes on the line at −0.25 a goal, tagged"),
    "goalie": ("scored", "scored: the goalie line at weight 1.6, shrunk by his shots"),
    "goalie_backup": ("scored", "the backup rule: a tagged −0.15 on the line, −0.25 if his line reads cold; the line itself is not scored"),
    "form": ("scored", "scored: the last ten at weight 0.6"),
    "en": ("scored", "scored, tagged: both clubs' net empty-netters at +0.40 a goal"),
    "xg": ("shown", "shown, not scored: expected goals measured null against the close"),
    "special": ("shown", "shown, not scored: special teams measured the wrong way against the close"),
    "shots": ("shown", "shown, not scored: shot rates measured the wrong way against the close"),
    "rest": ("label", "a label: the goalie line carries a back to back"),
}


def ordinal(k):
    k = int(k)
    suf = "th" if 10 <= k % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(k % 10, "th")
    return "%d%s" % (k, suf)


def ctx_rank(value, values, high_first=True):
    """(rank, n) of a value among values, 1 = the highest (or lowest)."""
    vals = [v for v in values if v is not None]
    if value is None or not vals:
        return None, 0
    ahead = sum(1 for v in vals if ((v > value) if high_first else (v < value)))
    return ahead + 1, len(vals)


def ctx_phrase(rank, n, hi_word, lo_word):
    """'4th most' from the top, '4th fewest' from the bottom."""
    if rank <= n / 2.0:
        return "%s %s" % (ordinal(rank), hi_word)
    return "%s %s" % (ordinal(n - rank + 1), lo_word)


def ctx_notable(rank, n):
    return n >= CTX_MIN_CLUBS and (rank <= CTX_NOTABLE or rank > n - CTX_NOTABLE)


def ctx_line(kind, side, text):
    s, tag = CTX_TAGS[kind]
    return {"side": side, "k": kind, "s": s, "t": text, "tag": tag}


def nhl_context(sides, summary, xg, tables, gsum):
    """The context lines for one game. `sides` is a list of two dicts with
    nick, ab, side, row (the team summary row), pick (the goalie, with id),
    backup (bool) and rest; `summary` every club's summary row, `xg` the
    MoneyPuck table, `tables` nhl_ledger_tables, `gsum` nhl_goalie_summary."""
    out = []
    rows = list((summary or {}).values())
    xrates = (xg[0] if xg else None) or {}
    xall = [r for r in xrates.values() if r.get("gp", 0) >= MIN_TEAM_GAMES]
    tall = [t for t in (tables or {}).values() if t["n"] >= MIN_TEAM_GAMES]
    goalies = [g for g in (gsum or {}).values() if g["shots"] >= CTX_GOALIE_SHOTS]
    for s in sides:
        nick, side = s["nick"], s["side"]
        t = (tables or {}).get(s["ab"])
        if t and t["n"] >= MIN_TEAM_GAMES:
            r, n = ctx_rank(t["gf"], [x["gf"] for x in tall])
            if r and ctx_notable(r, n):
                out.append(ctx_line("rates", side, "%s score %.2f a game, %s in the league (%d games)." % (nick, t["gf"], ctx_phrase(r, n, "most", "fewest"), t["n"])))
            r, n = ctx_rank(t["ga"], [x["ga"] for x in tall])
            if r and ctx_notable(r, n):
                out.append(ctx_line("rates", side, "%s allow %.2f a game, %s in the league (%d games)." % (nick, t["ga"], ctx_phrase(r, n, "most", "fewest"), t["n"])))
            r, n = ctx_rank(t["l10"], [x["l10"] for x in tall])
            if r and ctx_notable(r, n):
                out.append(ctx_line("form", side, "%s games have averaged %.1f goals over the last ten, %s in the league." % (nick, t["l10"], ctx_phrase(r, n, "highest", "lowest"))))
            if t["enc"] is not None and t["en_n"] >= EN_MIN_GAMES:
                eall = [x for x in tall if x["enc"] is not None and x["en_n"] >= EN_MIN_GAMES]
                r, n = ctx_rank(t["enc"], [x["enc"] for x in eall])
                if r and ctx_notable(r, n) and r <= n / 2.0:
                    out.append(ctx_line("en", side, "%s concede %.2f empty-netters a game, %s in the league: they trail late." % (nick, t["enc"], ctx_phrase(r, n, "most", "fewest"))))
                r, n = ctx_rank(t["ens"], [x["ens"] for x in eall])
                if r and ctx_notable(r, n) and r <= n / 2.0:
                    out.append(ctx_line("en", side, "%s score %.2f empty-netters a game, %s in the league: they lead late." % (nick, t["ens"], ctx_phrase(r, n, "most", "fewest"))))
        row = s.get("row")
        if row and int(row.get("gamesPlayed") or 0) >= MIN_TEAM_GAMES:
            full = [x for x in rows if int(x.get("gamesPlayed") or 0) >= MIN_TEAM_GAMES]
            for key, kind, verb, hi, lo, scale in (("shotsForPerGame", "shots", "take %.1f shots a game", "most", "fewest", 1.0),
                                                   ("powerPlayPct", "special", "power play at %.1f%%", "best", "worst", 100.0),
                                                   ("penaltyKillPct", "special", "kill at %.1f%%", "best", "worst", 100.0)):
                try:
                    v = float(row[key]) if row.get(key) is not None else None
                    vals = [float(x[key]) for x in full if x.get(key) is not None]
                except (TypeError, ValueError):
                    continue
                r, n = ctx_rank(v, vals)
                if r and ctx_notable(r, n):
                    out.append(ctx_line(kind, side, ("%s " + verb + ", %s in the league.") % (nick, v * scale, ctx_phrase(r, n, hi, lo))))
        xr = xrates.get(s["ab"])
        if xr and xr.get("gp", 0) >= MIN_TEAM_GAMES:
            r, n = ctx_rank(xr["xgf"], [x["xgf"] for x in xall])
            if r and ctx_notable(r, n):
                out.append(ctx_line("xg", side, "%s create %.2f expected goals a game, %s in the league." % (nick, xr["xgf"], ctx_phrase(r, n, "most", "fewest"))))
            r, n = ctx_rank(xr["xga"], [x["xga"] for x in xall])
            if r and ctx_notable(r, n):
                out.append(ctx_line("xg", side, "%s give up %.2f expected goals a game, %s in the league." % (nick, xr["xga"], ctx_phrase(r, n, "most", "fewest"))))
        pick = s.get("pick")
        g = (gsum or {}).get((pick or {}).get("id")) if pick else None
        if g and g["shots"] >= CTX_GOALIE_SHOTS and goalies:
            r, n = ctx_rank(g["sv"], [x["sv"] for x in goalies])
            out.append(ctx_line("goalie_backup" if s.get("backup") else "goalie", side,
                                "%s .%03d on %d shots, %s of %d goalies with %d+ shots." % (g["name"], round(g["sv"] * 1000), g["shots"], ordinal(r), n, CTX_GOALIE_SHOTS)))
        if s.get("rest") == "0":
            out.append(ctx_line("rest", side, "%s on a back to back." % nick))
    return out


def nhl_en_rates(ledger_games, abbrev, date_iso):
    """The club's empty-net goals conceded and scored per game to date, from
    the league ledger, and the games behind them: (conceded, scored, n). The
    sheet reads both clubs' net (conceded minus scored) as a tagged lean on
    the total (13 Oct 2026): a club that trails late pulls the goalie."""
    conceded = scored = n = 0
    for g in ledger_games or []:
        if g.get("ena") is None or g.get("enh") is None or (g.get("date") or "") >= date_iso:
            continue
        if g.get("home") == abbrev:
            conceded += g["ena"]
            scored += g["enh"]
        elif g.get("away") == abbrev:
            conceded += g["enh"]
            scored += g["ena"]
        else:
            continue
        n += 1
    return (conceded / float(n), scored / float(n), n) if n else (None, None, 0)


def nhl_last_starter(game_id, abbrev):
    """Who started the team's last game, from its boxscore."""
    box = nhl_api("/gamecenter/%s/boxscore" % game_id)
    pbg = box.get("playerByGameStats") or {}
    side = "awayTeam" if ((box.get("awayTeam") or {}).get("abbrev") == abbrev) else "homeTeam"
    for g in (pbg.get(side) or {}).get("goalies") or []:
        if g.get("starter"):
            return g.get("playerId")
    return None


_BOX_CACHE = {}


def nhl_boxscore(game_id):
    """One box score per game per run; the two clubs in it share the call."""
    if game_id not in _BOX_CACHE:
        _BOX_CACHE[game_id] = nhl_api("/gamecenter/%s/boxscore" % game_id)
    return _BOX_CACHE[game_id]


_LANDING_CACHE = {}


def nhl_landing(game_id):
    if game_id not in _LANDING_CACHE:
        _LANDING_CACHE[game_id] = nhl_api("/gamecenter/%s/landing" % game_id)
    return _LANDING_CACHE[game_id]


def nhl_recent_form(fin_games, abbrev, n=5):
    """The club's last n finals, oldest first: score, shots for and against,
    who started in net, how the game ended. Shown on the sheet, not scored:
    three games of scores is noise dressed as a trend, and this exists to
    catch what the season line hides (a goalie who has stopped starting, a
    team suddenly giving up 40 shots a night). Added 5 Oct 2026."""
    out = []
    for g in fin_games[-n:]:
        is_home = (g.get("homeTeam") or {}).get("abbrev") == abbrev
        us, them = ("homeTeam", "awayTeam") if is_home else ("awayTeam", "homeTeam")
        try:
            box = nhl_boxscore(g.get("id")) or {}
        except Exception:  # noqa: BLE001
            box = {}
        goalie = ""
        for x in ((box.get("playerByGameStats") or {}).get(us) or {}).get("goalies") or []:
            if x.get("starter"):
                nm = x.get("name")
                goalie = (nm.get("default") if isinstance(nm, dict) else nm) or ""
        end = str((g.get("gameOutcome") or {}).get("lastPeriodType") or "REG")
        # the first period, from the landing page's linescore: the first-five
        # of hockey, asked for on 5 Oct ("just like the MLB setup")
        p1f = p1a = None
        try:
            pa, ph = p1_from_landing(nhl_landing(g.get("id")) or {})
            if pa is not None and ph is not None:
                p1f, p1a = (ph, pa) if is_home else (pa, ph)
        except Exception:  # noqa: BLE001
            pass
        out.append({"date": g.get("gameDate"), "opp": nhl_name(g.get(them) or {}), "home": is_home,
                    "gf": (g.get(us) or {}).get("score"), "ga": (g.get(them) or {}).get("score"),
                    "sf": (box.get(us) or {}).get("sog"), "sa": (box.get(them) or {}).get("sog"),
                    "p1f": p1f, "p1a": p1a, "goalie": goalie, "end": end})
    return out


def nhl_form_line(form):
    bits = []
    for g in form:
        res = "W" if (g["gf"] is not None and g["ga"] is not None and g["gf"] > g["ga"]) else ("OTL" if g["end"] != "REG" else "L")
        b = "%s %s%s %s-%s" % (res, "v " if g["home"] else "@ ", g["opp"], g["gf"], g["ga"])
        if g["sf"] is not None:
            b += " (%s-%s)" % (g["sf"], g["sa"])
        if g.get("p1f") is not None:
            b += " P1 %s-%s" % (g["p1f"], g["p1a"])
        if g["goalie"]:
            b += " " + g["goalie"]
        bits.append(b)
    return ", ".join(bits) or "none yet"


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


def build_nhl_game(g, date_iso, season_id, summary, log, ledger=None, xg=None, goalie_summary=None, tables=None, lineups=None):
    away_t, home_t = g.get("awayTeam") or {}, g.get("homeTeam") or {}
    away, home = nhl_name(away_t), nhl_name(home_t)
    aab, hab = away_t.get("abbrev") or "", home_t.get("abbrev") or ""
    gid = g.get("id")
    start = str(g.get("startTimeUTC") or "")
    state = str(g.get("gameState") or "")
    inputs = {k: "" for k in ("agsv", "hgsv", "agsh", "hgsh", "asf", "hsf", "app", "hpp", "apk", "hpk",
                              "al10", "hl10", "h2h", "h2hn", "arest", "hrest", "nhlform", "nhlctx", "ap1l10", "hp1l10",
                              "axgf", "axga", "hxgf", "hxga", "xglg", "ngoalies", "agname", "hgname",
                              "agf", "aga", "hgf", "hga", "lgg", "angp", "hngp", "aenc", "aens", "henc", "hens")}
    inputs["agbk"] = inputs["hgbk"] = False   # the sheet's Backup in net boxes; True when the named starter is one
    inputs["agconf"] = inputs["hgconf"] = False   # the sheet's Confirmed boxes; True when RotoWire marks the start confirmed
    lineups = lineups or {}
    notes, starters, form = [], {"away": "", "home": ""}, {"away": [], "home": []}
    ctx_sides = []   # what the context card needs from each side (nhl_context)
    out = {"sport": "NHL", "gdate": date_iso, "away": away, "home": home, "gameId": gid, "first_puck_utc": start,
           "venue": ((g.get("venue") or {}).get("default") if isinstance(g.get("venue"), dict) else g.get("venue")) or "",
           "status": state, "starters": starters, "goalies": {"away": [], "home": []}, "inputs": inputs, "notes": notes}
    log("%s @ %s  (%s, %s UTC, %s)" % (away, home, out["venue"] or "venue ?", start[11:16] if len(start) >= 16 else "?", state or "scheduled"))

    for side, t, ab in (("away", away_t, aab), ("home", home_t, hab)):
        p = "a" if side == "away" else "h"
        nick = away if side == "away" else home
        # team rates from the summary report
        row = summary.get(int(t.get("id") or -1)) if summary else None
        cs = {"nick": nick, "ab": ab, "side": side, "row": row, "pick": None, "backup": False, "rest": None}
        ctx_sides.append(cs)
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
        # expected goals, from MoneyPuck, once the club has MIN_TEAM_GAMES
        if xg:
            xr = xg[0].get(ab)
            if xr and xr["gp"] >= MIN_TEAM_GAMES:
                inputs[p + "xgf"], inputs[p + "xga"] = fmt(xr["xgf"], 2), fmt(xr["xga"], 2)
                if xg[1] is not None:
                    inputs["xglg"] = fmt(xg[1], 2)
                log("  %s expected goals %s for / %s against per game (%d games)" % (side, inputs[p + "xgf"], inputs[p + "xga"], xr["gp"]))
            elif xr:
                notes.append("%s has %d game%s in the MoneyPuck table: expected goals left blank until %d." % (nick, xr["gp"], "" if xr["gp"] == 1 else "s", MIN_TEAM_GAMES))
            else:
                notes.append("%s is not in the MoneyPuck table under %s." % (nick, ab))
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
                cs["rest"] = inputs[p + "rest"]
            log("  %s last-10 avg total: %s (%d games); rest %s day(s)" % (side, inputs[p + "l10"] or "?", n, inputs[p + "rest"] or "?"))
            # season scoring rates, faded on the sheet (13 Oct 2026): goals for and
            # against per game over the club's finals, with the games behind them
            gfp, gap_, ng = nhl_season_rates(fin, ab)
            inputs[p + "ngp"] = str(ng)
            if gfp is not None and ng >= MIN_TEAM_GAMES:
                inputs[p + "gf"], inputs[p + "ga"] = fmt(gfp, 2), fmt(gap_, 2)
                log("  %s scoring rates: %s for, %s against per game (%d games)" % (side, inputs[p + "gf"], inputs[p + "ga"], ng))
            else:
                notes.append("%s has %d final%s this season: the scoring rates are left blank until %d." % (nick, ng, "" if ng == 1 else "s", MIN_TEAM_GAMES))
            # the league box stays blank: the sheet's fixed 6.17 measured stronger than the season's running mean
            form[side] = nhl_recent_form(fin, ab, 5)
            log("  %s last five: %s" % (side, nhl_form_line(form[side])))
            # the first-period last ten, from the league ledger
            if ledger is not None:
                avg1, k1 = team_p1_last10(ledger, ab, date_iso)
                if avg1 is not None and k1 >= MIN_TEAM_GAMES:
                    inputs[p + "p1l10"] = fmt(avg1, 2)
                    log("  %s first-period last ten: %s over %d game%s" % (side, inputs[p + "p1l10"], k1, "" if k1 == 1 else "s"))
                else:
                    notes.append("%s has %d final%s in the league ledger: the first-period last ten is left blank until %d." % (nick, k1, "" if k1 == 1 else "s", MIN_TEAM_GAMES))
                # empty-net habits, tagged on the sheet (13 Oct 2026): conceded and scored per game, ten games in
                enc, ens, ken = nhl_en_rates(ledger, ab, date_iso)
                if enc is not None and ken >= EN_MIN_GAMES:
                    inputs[p + "enc"], inputs[p + "ens"] = fmt(enc, 2), fmt(ens, 2)
                    log("  %s empty-netters: %s conceded, %s scored per game (%d games)" % (side, inputs[p + "enc"], inputs[p + "ens"], ken))
                else:
                    notes.append("%s has %d final%s in the league ledger: the empty-net habits are left blank until %d." % (nick, ken, "" if ken == 1 else "s", EN_MIN_GAMES))
            elif side == "away":
                notes.append("No league ledger in this folder: run the NHL ledger first and the first-period last ten fills.")
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
            goalies = nhl_club_goalies(ab, season_id)
            out["goalies"][side] = [{"name": x["name"], "sv": x["sv"], "shots": x["shots"], "gs": x["gs"], "season": x.get("season"),
                                     "this": x.get("this"), "prior": x.get("prior")} for x in goalies]
            # the sheet's goalie picker (11 Oct 2026): every goalie on the club with
            # the line the sheet would score, so the right starter is a click, not
            # a retype. 42 of the first 150 goalie boxes on the card carried the
            # other goalie's line. Compact keys: n name, sv, sh shots, gs starts,
            # cs the club's starts this season (the backup rule's denominator),
            # ls true when the line is last season's (a club that has not played).
            club_starts = sum(int(x.get("gs") or 0) for x in goalies if not x.get("season"))
            picker = [{"n": x["name"], "sv": (round(x["sv"], 3) if x["sv"] is not None else None), "sh": int(x["shots"] or 0),
                       "gs": int(x.get("gs") or 0), "cs": club_starts, "ls": bool(x.get("season"))} for x in goalies]
            ngo = json.loads(inputs["ngoalies"]) if inputs.get("ngoalies") else {}
            ngo[side] = picker
            inputs["ngoalies"] = json.dumps(ngo, separators=(",", ":"))
            if goalies and goalies[0].get("season"):
                notes.append("%s has not played yet: the goalie lines are LAST season's (%s), shots halved." % (nick, goalies[0]["season"]))
            elif any(x.get("prior") for x in goalies):
                notes.append("%s goalie lines blend this season with half of last season's shots, so an early-season number is the man's own prior, not the league's." % nick)
            last_id = None
            if fin and inputs[p + "rest"] == "0":
                try:
                    last_id = nhl_last_starter(fin[-1].get("id"), ab)
                except Exception as e:  # noqa: BLE001
                    log("  %s: could not read yesterday's starter (%s)" % (side, e))
            pick, why = nhl_likely_starter(goalies, int(inputs[p + "rest"]) if inputs[p + "rest"] != "" else None, last_id)
            # the lineups (19 Oct 2026): the goalie RotoWire names replaces the guess,
            # with his status; CBS's depth chart speaks on the backup and carries the news
            rw = (lineups.get("rw") or {}).get(nick)
            rw_status = ""
            if rw:
                named = nhl_goalie_match(rw["name"], goalies)
                if named is not None:
                    pick, why, rw_status = named, "RotoWire: %s" % rw["status"], rw["status"]
                else:
                    notes.append("RotoWire names %s in net for the %s (%s), who is not on the club's goalie page; the slate's guess stands. Pick him by hand if he is a call-up." % (rw["name"], nick, rw["status"] or "no status"))
            cb = (lineups.get("cbs") or {}).get(ab)
            if pick:
                cs["pick"] = pick
                starters[side] = pick["name"]
                inputs[p + "gname"] = pick["name"]   # whose line is on the card; the grade run checks it against who played
                if pick["sv"] is not None and pick["shots"] > 0:
                    inputs[p + "gsv"] = "%.3f" % pick["sv"]
                    inputs[p + "gsh"] = str(pick["shots"])
                else:
                    notes.append("%s's likely starter %s has no shots this season; save percentage left blank." % (nick, pick["name"]))
                if rw_status == "confirmed":
                    inputs[p + "gconf"] = True
                    notes.append("%s starter: %s, CONFIRMED on RotoWire. The Confirmed box is ticked." % (nick, pick["name"]))
                elif rw_status:
                    notes.append("%s likely starter: %s, %s on RotoWire, not yet confirmed: tick the box when it turns green." % (nick, pick["name"], rw_status.upper()))
                else:
                    notes.append("%s likely starter: %s (%s). NOT confirmed: check RotoWire or CBS and tick the box." % (nick, pick["name"], why))
                club_starts = sum(int(x.get("gs") or 0) for x in goalies if not x.get("season"))
                bsrc = nhl_backup_source(pick, goalies, cb)
                if bsrc:
                    inputs[p + "gbk"] = True
                    cs["backup"] = True
                    if bsrc == "cbs":
                        notes.append("%s: %s is the BACKUP on CBS's depth chart (the club has %d start%s, under the %d the starts rule needs). The Backup box is ticked." % (nick, pick["name"], club_starts, "" if club_starts == 1 else "s", BACKUP_MIN_STARTS))
                        log("  %s: %s is the backup on CBS's depth chart (%d club starts) -> Backup in net ticked" % (side, pick["name"], club_starts))
                    else:
                        notes.append("%s: %s is the BACKUP (%d of the club's %d starts). The Backup box is ticked%s" % (nick, pick["name"], int(pick.get("gs") or 0), club_starts, "." if rw_status else "; untick it if RotoWire or CBS names the starter."))
                        log("  %s: %s is the backup (%d of %d starts) -> Backup in net ticked" % (side, pick["name"], int(pick.get("gs") or 0), club_starts))
                elif cb and _name_key(cb.get("backup"))[1] and _name_key(cb.get("backup"))[1] == _name_key(pick["name"])[1]:
                    notes.append("CBS's depth chart lists %s as the %s backup; by starts he is not (%d of the club's %d), so the Backup box is left alone." % (pick["name"], nick, int(pick.get("gs") or 0), club_starts))
                if cb:
                    blurb = next((v for k, v in (cb.get("news") or {}).items() if _name_key(k)[1] == _name_key(pick["name"])[1]), None)
                    if blurb:
                        notes.append("CBS on %s: %s" % (pick["name"], blurb))
                    for nm in cb.get("reserves") or []:
                        tip = (cb.get("news") or {}).get(nm)
                        if tip and nhl_goalie_match(nm, goalies) is not None:
                            notes.append("%s: %s is on CBS's reserve list (%s)." % (nick, nm, tip))
                others = ", ".join("%s %s/%d" % (x["name"], "%.3f" % x["sv"] if x["sv"] is not None else "?", x["shots"]) for x in goalies if x is not pick)
                halves = ""
                if pick.get("prior"):
                    t, pr = pick["this"], pick["prior"]
                    halves = " (this season %s on %d; last season %.3f on %d, at half)" % ("%.3f" % t["sv"] if t["sv"] is not None else "?", t["shots"], pr["sv"], pr["shots"])
                log("  %s goalie: %s  SV %s on %s shots%s  [%s]%s" % (side, pick["name"], inputs[p + "gsv"] or "?", inputs[p + "gsh"] or "?", halves, why, ("; others: " + others) if others else ""))
            else:
                notes.append("%s: %s." % (nick, why))
        except Exception as e:  # noqa: BLE001
            notes.append("Could not fetch %s goalies: %s" % (nick, e))
    # the form panel: both sides' last five, as one JSON input so the sheet
    # carries it through the form, the draft and the row like any other box
    if form["away"] or form["home"]:
        inputs["nhlform"] = json.dumps(form, separators=(",", ":"))
    out["form"] = form
    # the context card: each club's rank in the league on the numbers above, with the
    # tag that says what the sheet did with each (nhl_context); one JSON input
    try:
        ctx = nhl_context(ctx_sides, summary, xg, tables, goalie_summary)
    except Exception as e:  # noqa: BLE001
        ctx = []
        notes.append("Could not build the context lines: %s" % e)
    if ctx:
        inputs["nhlctx"] = json.dumps(ctx, separators=(",", ":"))
        for c in ctx:
            log("  context: %s  [%s]" % (c["t"], c["s"]))
    out["context"] = ctx
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
    # who actually started in net, from the box score: the sheet compares it
    # with the goalie whose line was on the card and keeps the record of
    # rows where they differed (11 Oct 2026: 42 of the first 150 boxes did)
    starters = {}
    try:
        det = nhl_detail({}, nhl_boxscore(g.get("id")), {})
        if det.get("ga_name"):
            starters["away"] = det["ga_name"]
        if det.get("gh_name"):
            starters["home"] = det["gh_name"]
    except Exception as e:  # noqa: BLE001
        notes.append("Could not read the starters from the box score: %s" % e)
    log("%s @ %s: final %s-%s%s, after one %s-%s%s" % (away, home, fin["fa"], fin["fh"], " (%s)" % how if how in ("OT", "SO") else "", fin.get("f5a", "?"), fin.get("f5h", "?"),
                                                      ("; in net %s / %s" % (starters.get("away", "?"), starters.get("home", "?"))) if starters else ""))
    out = {"sport": "NHL", "gdate": "", "away": away, "home": home, "gameId": g.get("id"), "finals": fin, "notes": notes}
    if starters:
        out["starters"] = starters
    return out


# ---- the league ledger -------------------------------------------------------
# Every regular-season final in the league, with period scores, shots,
# empty-net goals and how the game ended, in one growing file per season.
# The sheet learns from the user's eight rows a night; the league plays
# thirty-two teams a night. From the ledger the hockey book's a-priori
# constants are MEASURED (nhl_measure) and each club's first-period last ten
# is filled on the slate (team_p1_last10). Added 5 Oct 2026.
LEDGER_FORMAT = "callsheet3.nhl-ledger"
# the engine's figures as of 7 Oct 2026, measured on the 2024-25 and 2025-26 ledgers
A_PRIORI = {"goals_per_game": 6.17, "ot_rate": 0.23, "empty_net_rate": 0.357, "p1_share": 0.314,
            "p1_per_game": 0.314 * (6.17 - 0.39 - 0.23), "shots_per_team": 28.1, "save_pct": 0.898}


def ledger_path(out_dir, season_id):
    return os.path.join(out_dir, "nhl-ledger-%s.json" % season_id)


def season_start_iso(season_id):
    return "%s-09-20" % str(season_id)[:4]


def load_ledger(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    if d.get("format") != LEDGER_FORMAT or not isinstance(d.get("games"), list):
        return None
    return d


def periods_from_landing(landing):
    """Per-period scores {1: (away, home), 2: ..., 3: ..., "OT": ...}, shots
    (away, home), empty-net goals (away, home) and how it ended."""
    summ = (landing or {}).get("summary") or {}
    ls = summ.get("linescore") or {}
    per = {}
    for pdesc in ls.get("byPeriod") or []:
        d = pdesc.get("periodDescriptor") or {}
        num, typ = d.get("number", pdesc.get("period")), str(d.get("periodType") or "")
        if pdesc.get("away") is None or pdesc.get("home") is None:
            continue
        key = "SO" if typ == "SO" else ("OT" if (typ == "OT" or (num is not None and num > 3)) else num)
        a, h = int(pdesc["away"]), int(pdesc["home"])
        if key in per and key in ("OT",):
            per[key] = (per[key][0] + a, per[key][1] + h)
        else:
            per[key] = (a, h)
    away_ab = ((landing or {}).get("awayTeam") or {}).get("abbrev")
    scoring = summ.get("scoring") or []
    # A finished season's page has no linescore (checked against a saved
    # 2024-25 page, 7 Oct 2026): the periods come from the goal list instead,
    # one entry per period with each goal's team. A period with no goals is
    # still listed, so three regulation periods always resolve.
    if 1 not in per and scoring:
        for sc in scoring:
            d = sc.get("periodDescriptor") or {}
            num, typ = d.get("number"), str(d.get("periodType") or "")
            key = "SO" if typ == "SO" else ("OT" if (typ == "OT" or (num is not None and num > 3)) else num)
            if key is None:
                continue
            a = h = 0
            for g in sc.get("goals") or []:
                ab = g.get("teamAbbrev")
                ab = ab.get("default") if isinstance(ab, dict) else ab
                if ab == away_ab:
                    a += 1
                else:
                    h += 1
            if key == "OT" and key in per:
                per[key] = (per[key][0] + a, per[key][1] + h)
            else:
                per[key] = (a, h)
        for k in (1, 2, 3):
            per.setdefault(k, (0, 0))
    sa = sh = None
    sbp = summ.get("shotsByPeriod") or []
    if sbp:
        sa = sum(int(x.get("away") or 0) for x in sbp)
        sh = sum(int(x.get("home") or 0) for x in sbp)
    else:
        # the finished-season page keeps the game's shots on the two teams
        ta, th = (landing or {}).get("awayTeam") or {}, (landing or {}).get("homeTeam") or {}
        if ta.get("sog") is not None and th.get("sog") is not None:
            sa, sh = int(ta["sog"]), int(th["sog"])
    ena = enh = 0
    for sc in scoring:
        for g in sc.get("goals") or []:
            if str(g.get("goalModifier") or "").lower().startswith("empty"):
                ab = g.get("teamAbbrev")
                ab = ab.get("default") if isinstance(ab, dict) else ab
                if ab == away_ab:
                    ena += 1
                else:
                    enh += 1
    end = str(((landing or {}).get("gameOutcome") or {}).get("lastPeriodType") or "")
    if not end:
        # the page's own last period descriptor: REG, OT or SO
        pt = str(((landing or {}).get("periodDescriptor") or {}).get("periodType") or "")
        end = pt if pt in ("REG", "OT", "SO") else ("SO" if "SO" in per else ("OT" if "OT" in per else "REG"))
    return per, (sa, sh), (ena, enh), end


def ledger_entry(g, landing, day_date=None):
    per, shots, en, end = periods_from_landing(landing)
    at, ht = g.get("awayTeam") or {}, g.get("homeTeam") or {}
    fa, fh = at.get("score"), ht.get("score")
    if (fa is None or fh is None) and landing:
        fa = ((landing.get("awayTeam") or {}).get("score"))
        fh = ((landing.get("homeTeam") or {}).get("score"))
    # the schedule page keeps the date on the day, not the game (checked
    # against a saved page, 6 Oct 2026); startTimeUTC is the last resort
    date = g.get("gameDate") or day_date or str(g.get("startTimeUTC") or "")[:10] or None
    e = {"id": g.get("id"), "date": date, "away": at.get("abbrev"), "home": ht.get("abbrev"),
         "fa": None if fa is None else int(fa), "fh": None if fh is None else int(fh), "end": end,
         "sa": shots[0], "sh": shots[1], "ena": en[0], "enh": en[1]}
    for k, name in ((1, "p1"), (2, "p2"), (3, "p3"), ("OT", "ot")):
        if k in per:
            e[name + "a"], e[name + "h"] = per[k]
    return e


def nhl_ledger_scan(start_iso, end_iso, have_ids, log):
    """Every regular-season final from start to end, one schedule week per
    call and one landing page per new game."""
    out = []
    d = dt.date.fromisoformat(start_iso)
    end = dt.date.fromisoformat(end_iso)
    while d <= end:
        try:
            sched = nhl_api("/schedule/%s" % d.isoformat())
        except Exception as e:  # noqa: BLE001
            log("  week of %s: could not fetch the schedule (%s)" % (d.isoformat(), e))
            d += dt.timedelta(days=7)
            continue
        week_new = 0
        for day in sched.get("gameWeek") or []:
            if (day.get("date") or "") > end_iso:
                continue
            for g in day.get("games") or []:
                if str(g.get("gameType", 2)) != "2" or not nhl_final(g) or g.get("id") in have_ids:
                    continue
                try:
                    landing = nhl_landing(g.get("id"))
                except Exception as e:  # noqa: BLE001
                    log("  game %s: no landing page (%s); scores only" % (g.get("id"), e))
                    landing = {}
                out.append(ledger_entry(g, landing, day.get("date")))
                have_ids.add(g.get("id"))
                week_new += 1
        if week_new:
            log("  week of %s: %d final%s added (%d so far)" % (d.isoformat(), week_new, "" if week_new == 1 else "s", len(out)))
        d += dt.timedelta(days=7)
    return out


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return (sum(xs) / float(len(xs))) if xs else None


def _sd(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    m = sum(xs) / float(len(xs))
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


def nhl_measure(games):
    """The hockey book's constants, measured on the ledger. Each figure is
    the thing the engine assumes, computed the way the engine means it."""
    fin = [g for g in games if g.get("fa") is not None and g.get("fh") is not None]
    n = len(fin)
    m = {"games": n}
    if not n:
        return m
    totals = [g["fa"] + g["fh"] for g in fin]
    m["goals_per_game"] = _mean(totals)
    m["total_sd"] = _sd(totals)
    m["ot_rate"] = sum(1 for g in fin if g.get("end") in ("OT", "SO")) / float(n)
    m["so_rate"] = sum(1 for g in fin if g.get("end") == "SO") / float(n)
    en = [g for g in fin if g.get("ena") is not None]
    if en:
        m["empty_net_rate"] = sum(1 for g in en if (g["ena"] or 0) + (g["enh"] or 0) > 0) / float(len(en))
        m["empty_net_goals_per_game"] = _mean([(g["ena"] or 0) + (g["enh"] or 0) for g in en])
    withp = [g for g in fin if g.get("p1a") is not None and g.get("p3a") is not None]
    if withp:
        p1 = [g["p1a"] + g["p1h"] for g in withp]
        reg = [g["p1a"] + g["p1h"] + g["p2a"] + g["p2h"] + g["p3a"] + g["p3h"] for g in withp]
        regnoen = [r - ((g.get("ena") or 0) + (g.get("enh") or 0)) for r, g in zip(reg, withp)]
        m["p1_per_game"] = _mean(p1)
        m["p1_share"] = (sum(p1) / float(sum(regnoen))) if sum(regnoen) > 0 else None
        m["p1_dist"] = {"0": sum(1 for x in p1 if x == 0) / float(len(p1)), "1": sum(1 for x in p1 if x == 1) / float(len(p1)),
                        "2+": sum(1 for x in p1 if x >= 2) / float(len(p1))}
        lam = m["p1_per_game"]
        m["p1_poisson_2plus"] = 1.0 - math.exp(-lam) * (1.0 + lam)
        m["regulation_goals_per_game"] = _mean(reg)
        m["p2_per_game"] = _mean([g["p2a"] + g["p2h"] for g in withp])
        m["p3_per_game"] = _mean([g["p3a"] + g["p3h"] for g in withp])
    shots = [g for g in fin if g.get("sa") is not None and g.get("sh") is not None and (g["sa"] + g["sh"]) > 0]
    if shots:
        m["shots_per_team"] = _mean([g["sa"] for g in shots] + [g["sh"] for g in shots])
        goals_on_goalie = sum(g["fa"] + g["fh"] - ((g.get("ena") or 0) + (g.get("enh") or 0)) - (1 if g.get("end") == "SO" else 0) for g in shots)
        tot_shots = sum(g["sa"] + g["sh"] for g in shots)
        m["save_pct"] = 1.0 - goals_on_goalie / float(tot_shots) if tot_shots else None
    return m


def ledger_report(m, log):
    n = m.get("games", 0)
    log("League ledger: %d regular-season final%s." % (n, "" if n == 1 else "s"))
    if not n:
        return
    rows = [("goals per game", "goals_per_game", "%.2f"), ("overtime or shootout", "ot_rate", "%.3f"),
            ("game with an empty-net goal", "empty_net_rate", "%.3f"), ("first-period share of regulation goals", "p1_share", "%.3f"),
            ("first-period goals per game", "p1_per_game", "%.2f"), ("shots per team per game", "shots_per_team", "%.1f"),
            ("league save percentage", "save_pct", "%.3f")]
    log("  %-40s %10s %10s" % ("", "engine", "measured"))
    for label, key, f in rows:
        if m.get(key) is None:
            continue
        log("  %-40s %10s %10s" % (label, f % A_PRIORI[key], f % m[key]))
    if m.get("total_sd") is not None:
        log("  %-40s %10s %10s" % ("spread of the total (raw, not residual)", "~2.55+", "%.2f" % m["total_sd"]))
    if m.get("p1_dist"):
        d = m["p1_dist"]
        log("  first period 0 / 1 / 2+ goals: %.1f%% / %.1f%% / %.1f%%  (Poisson at the measured mean says 2+ in %.1f%%)"
            % (d["0"] * 100, d["1"] * 100, d["2+"] * 100, m["p1_poisson_2plus"] * 100))
    if n < 100:
        log("  Under 100 games: read these as noise until the sample is there; the engine's constants change by hand, with a note.")


def team_p1_last10(games, abbrev, before_iso, n=10):
    """A club's last n first-period totals (for plus against) before a date,
    from the ledger: (average, count)."""
    mine = [g for g in games if (g.get("away") == abbrev or g.get("home") == abbrev) and (g.get("date") or "") < before_iso
            and g.get("p1a") is not None and g.get("p1h") is not None]
    mine.sort(key=lambda g: g.get("date") or "")
    tail = mine[-n:]
    if not tail:
        return None, 0
    return sum(g["p1a"] + g["p1h"] for g in tail) / float(len(tail)), len(tail)


def _frac(sv):
    """'28/31' -> (28, 31); anything else -> (None, None)."""
    try:
        a, b = str(sv).split("/")
        return int(a), int(b)
    except (ValueError, AttributeError):
        return None, None


def nhl_detail(entry, box, landing):
    """The second pass over a ledger game, for the backtest of the inputs the
    first pass could not test: who started in net and his line that night
    (from the box score), power-play goals and penalties by side (from the
    game page). Fills the entry in place and returns it."""
    pbg = (box or {}).get("playerByGameStats") or {}
    for side, key in (("awayTeam", "a"), ("homeTeam", "h")):
        starter = None
        for g in (pbg.get(side) or {}).get("goalies") or []:
            if g.get("starter"):
                starter = g
                break
        if starter is None:
            # no starter flag: the goalie with the most time on ice
            gs = [g for g in (pbg.get(side) or {}).get("goalies") or [] if g.get("toi")]
            if gs:
                starter = max(gs, key=lambda g: int(str(g.get("toi", "0:0")).split(":")[0]))
        if starter is not None:
            saves, shots = _frac(starter.get("saveShotsAgainst"))
            nm = starter.get("name")
            entry["g" + key + "_id"] = starter.get("playerId")
            entry["g" + key + "_name"] = (nm.get("default") if isinstance(nm, dict) else nm) or ""
            entry["g" + key + "_sa"] = shots
            entry["g" + key + "_sv"] = saves
            entry["g" + key + "_ga"] = int(starter.get("goalsAgainst") or 0) if starter.get("goalsAgainst") not in (None, "") else (shots - saves if shots is not None else None)
    summ = (landing or {}).get("summary") or {}
    away_ab = ((landing or {}).get("awayTeam") or {}).get("abbrev") or entry.get("away")
    ppa = pph = 0
    for sc in summ.get("scoring") or []:
        for g in sc.get("goals") or []:
            if str(g.get("strength") or "").lower() == "pp":
                ab = g.get("teamAbbrev")
                ab = ab.get("default") if isinstance(ab, dict) else ab
                if ab == away_ab:
                    ppa += 1
                else:
                    pph += 1
    pena = penh = 0
    for per in summ.get("penalties") or []:
        for pn in per.get("penalties") or []:
            if str(pn.get("type") or "").upper() not in ("MIN", "MAJ"):
                continue
            ab = pn.get("teamAbbrev")
            ab = ab.get("default") if isinstance(ab, dict) else ab
            if ab == away_ab:
                pena += 1
            else:
                penh += 1
    entry["ppga"], entry["ppgh"] = ppa, pph       # power-play goals FOR each side
    entry["pena"], entry["penh"] = pena, penh     # minors and majors committed by each side
    entry["detail"] = True
    return entry


def nhl_right_rail(game_id):
    """The game page's side panel: officials, head coaches, scratches."""
    return nhl_api("/gamecenter/%s/right-rail" % game_id)


def _names(xs):
    out = []
    for x in xs or []:
        # the side panel writes an official as {"fullName": {"default": "Garrett Rank"}, "sweaterNumber": 7}
        nm = (x.get("fullName", x.get("default")) if isinstance(x, dict) else x)
        if isinstance(nm, dict):
            nm = nm.get("default")
        if nm:
            out.append(str(nm))
    return out


def nhl_refs(entry, rail, landing=None):
    """The third pass over a ledger game: the two referees and the two
    linesmen, and how many skaters each side scratched, from the game
    page's side panel (falling back to the game page itself). Fills the
    entry in place; `rail` is set either way so the game is not refetched."""
    gi = ((rail or {}).get("gameInfo") or {}) or (((landing or {}).get("summary") or {}).get("gameInfo") or {})
    refs = _names(gi.get("referees"))
    lines = _names(gi.get("linesmen"))
    if refs:
        entry["refs"] = refs
    if lines:
        entry["linesmen"] = lines
    for side, key in (("awayTeam", "a"), ("homeTeam", "h")):
        sc = (gi.get(side) or {}).get("scratches")
        if isinstance(sc, list):
            entry["scr" + key] = len(sc)
    entry["rail"] = True
    return entry


def nhl_ledger_refs(led, path, log):
    """Fetch the side panel for every ledger game without it, for the
    referees and scratches. One call a game; a season is about 20 minutes.
    Written every 100 games so a stopped run keeps what it fetched."""
    # a game fetched without its referees (the first run of 7 Oct 2026 read
    # the names at the wrong depth) is fetched again; one with them is kept
    todo = [g for g in led["games"] if not g.get("refs") and g.get("id") is not None]
    log("Officials pass: %d game%s to fetch (one call each)..." % (len(todo), "" if len(todo) == 1 else "s"))
    done = found = 0
    for g in todo:
        try:
            rail = nhl_right_rail(g["id"])
        except Exception as e:  # noqa: BLE001
            log("  game %s: no side panel (%s)" % (g["id"], e))
            rail = {}
        nhl_refs(g, rail)
        done += 1
        if g.get("refs"):
            found += 1
        if done == 1 and not g.get("refs"):
            log("  the first game came back without referees; the panel's keys were: %s" % ", ".join(sorted((rail or {}).keys())) or "none")
        if done % 100 == 0 or done == len(todo):
            led["generated"] = now_utc()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(led, f, indent=1)
            log("  %d of %d fetched, %d with referees; written" % (done, len(todo), found))
    return done


def nhl_ledger_detail(led, path, log):
    """Fetch the box score and game page for every ledger game without its
    detail, writing the file every 100 games so a stopped run keeps what it
    fetched. Two calls a game; a season is about 40 minutes."""
    todo = [g for g in led["games"] if not g.get("detail") and g.get("id") is not None]
    log("Detail pass: %d game%s to fetch (box score and game page each)..." % (len(todo), "" if len(todo) == 1 else "s"))
    done = 0
    for g in todo:
        try:
            box = nhl_boxscore(g["id"])
        except Exception as e:  # noqa: BLE001
            log("  game %s: no box score (%s)" % (g["id"], e))
            box = {}
        try:
            landing = nhl_landing(g["id"])
        except Exception as e:  # noqa: BLE001
            log("  game %s: no game page (%s)" % (g["id"], e))
            landing = {}
        nhl_detail(g, box, landing)
        done += 1
        if done % 100 == 0 or done == len(todo):
            led["generated"] = now_utc()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(led, f, indent=1)
            log("  %d of %d detailed; written" % (done, len(todo)))
        # the two caches would hold a whole season's pages; keep them small
        if len(_BOX_CACHE) > 50:
            _BOX_CACHE.clear()
        if len(_LANDING_CACHE) > 50:
            _LANDING_CACHE.clear()
    return done


def make_nhl_ledger(date_iso, out_dir, log, season=None, detail=False, refs=False):
    """This season's ledger up to date_iso, or -- with a season id such as
    20252026 -- a PAST season in full, for the backtest. A past season's
    file is complete once written and never rescanned."""
    past = season is not None and str(season) != nhl_season_id([], date_iso)
    season = str(season) if season else nhl_season_id([], date_iso)
    if past:
        date_iso = "%s-05-05" % str(season)[4:]   # the regular season is long over by May
    path = ledger_path(out_dir, season)
    led = load_ledger(path) or {"format": LEDGER_FORMAT, "version": 1, "season": season, "games": [], "through": None}
    # a game that came through without its periods (the first two season
    # pulls, before the finished-season page was read right) is fetched again
    have = set(g.get("id") for g in led["games"] if g.get("p1a") is not None)
    redo = len(led["games"]) - len(have)
    if redo:
        log("%d game%s in the ledger lack period scores and will be fetched again." % (redo, "" if redo == 1 else "s"))
    if led.get("through") and not redo:
        start = (dt.date.fromisoformat(led["through"]) - dt.timedelta(days=7)).isoformat()
    else:
        start = season_start_iso(season)
    log("Scanning the league from %s to %s (%d game%s already in the ledger); a line prints per week with games..." % (start, date_iso, len(have), "" if len(have) == 1 else "s"))
    new = nhl_ledger_scan(start, date_iso, have, log)
    byid = {g.get("id"): g for g in led["games"]}
    for e in new:
        byid[e.get("id")] = e
    led["games"] = sorted(byid.values(), key=lambda g: ((g.get("date") or ""), g.get("id") or 0))
    led["through"] = date_iso
    led["generated"] = now_utc()
    led["measure"] = nhl_measure(led["games"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(led, f, indent=1)
    log("Added %d final%s. Wrote %s." % (len(new), "" if len(new) == 1 else "s", path))
    ledger_report(led["measure"], log)
    if detail:
        n = nhl_ledger_detail(led, path, log)
        log("Detail pass done: %d game%s fetched; %d of %d in the ledger carry starters and special teams." % (n, "" if n == 1 else "s", sum(1 for g in led["games"] if g.get("detail")), len(led["games"])))
    if refs:
        n = nhl_ledger_refs(led, path, log)
        log("Officials pass done: %d game%s fetched; %d of %d in the ledger name their referees." % (n, "" if n == 1 else "s", sum(1 for g in led["games"] if g.get("refs")), len(led["games"])))
    return path


# ---- the NBA ledger ----------------------------------------------------------
# Every regular-season final of a season from the league's public feeds, with
# quarter scores, the two teams' box lines (for pace), and every player who
# dressed with his minutes, plus who sat and why. The basketball book is
# built the hockey way (15 Oct 2026, at the user's word on 8 Oct: "I want
# everything you mentioned"): the ledger first, the backtest against the
# KillerSports closes second, the engine third with only what the backtest
# supports. The feeds cannot be reached from the build container, so the
# shapes below are the feed's documented ones, checked offline (--selftest)
# and proven on the user's own machine on the first run.
#
#   python slate.py nba-ledger --season 2024-25     (a past season in full)
#   python slate.py nba-ledger                      (this season, up to today)
#
# Games are listed from stats.nba.com's league game log (one call a season,
# two rows a game) or, for the current season when that fails, the CDN's
# schedule file. Each game's detail comes from the CDN's live-data box score
# (one call a game); when a game's box score is not on the CDN the stats site's
# traditional box score and summary are read instead (two calls). The file is
# written every NBA_LEDGER_FLUSH games so a run can be stopped and resumed.
NBA_LEDGER_FORMAT = "callsheet3.nba-ledger"
NBA_LEDGER_FLUSH = 100
NBA_CDN = "https://cdn.nba.com/static/json"
NBA_STATS = "https://stats.nba.com/stats"
NBA_STATS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip",
    "Referer": "https://www.nba.com/", "Origin": "https://www.nba.com", "Host": "stats.nba.com", "Connection": "keep-alive",
    "x-nba-stats-origin": "stats", "x-nba-stats-token": "true",
}
NBA_STATS_TIMEOUT = 60   # the stats site answers a season's log slowly or not at all; one try, then the CDN
NBA_CDN_TIMEOUT = 20
NBA_PACE_FT = 0.44   # free-throw possessions: the standard estimate, FGA - OREB + TOV + 0.44 FTA
# Regular-season game ids are sequential: 002 + the season's two digits + 00001
# upward, 1,230 a season (30 clubs, 82 games). When the stats site will not
# answer, the ledger walks the ids on the CDN directly and stops after
# NBA_ID_GAP misses past NBA_ID_FLOOR; a postponed game leaves a hole, a
# rescheduled one takes a later id.
NBA_ID_FLOOR = 1230
NBA_ID_GAP = 15
NBA_ID_LIMIT = 1320
# A player's line in a ledger game, as a list (the file is 2 MB a season and
# keys would double it). The first six are the 15 Oct 2026 entry (id, name,
# starter, minutes, points, plus-minus); the rest were added 19 Oct 2026 for
# the player props: rebounds, assists, threes made, field-goal and free-throw
# attempts, turnovers, steals, blocks, field goals and free throws made, the
# position ESPN lists. An older entry is six long; nba_player_dict reads
# either and the ledger run refills the short ones from the summaries.
NBA_PLAYER_KEYS = ("id", "n", "st", "min", "pts", "pm", "reb", "ast", "tpm", "fga", "fta", "tov", "stl", "blk", "fgm", "ftm", "pos")


def nba_player_line(pid, name, starter, mins, pts, pm, reb=0, ast=0, tpm=0, fga=0, fta=0, tov=0, stl=0, blk=0, fgm=0, ftm=0, pos=""):
    return [pid, name, int(starter or 0), round(float(mins or 0), 1), int(pts or 0), int(pm or 0),
            int(reb or 0), int(ast or 0), int(tpm or 0), int(fga or 0), int(fta or 0), int(tov or 0), int(stl or 0), int(blk or 0), int(fgm or 0), int(ftm or 0), str(pos or "")]


def nba_player_dict(entry):
    """A ledger player entry as a dict; a six-long entry (before 19 Oct 2026)
    reads with `full` False and the box stats None."""
    d = dict(zip(NBA_PLAYER_KEYS, entry))
    d["full"] = len(entry) >= 16
    for k in NBA_PLAYER_KEYS[6:]:
        d.setdefault(k, None)
    d["id"] = str(d.get("id") or "")
    return d


def nba_season_id(date_iso):
    """'2024-25' for any date in that season: October to June."""
    d = dt.date.fromisoformat(date_iso)
    y = d.year if d.month >= 8 else d.year - 1
    return "%d-%02d" % (y, (y + 1) % 100)


def nba_norm_season(season):
    """'2024-25', '2024', '202425' or '20242025' -> '2024-25'."""
    s = str(season).strip()
    if re.fullmatch(r"\d{4}-\d{2}", s):
        return s
    if re.fullmatch(r"\d{4}", s):
        return "%s-%02d" % (s, (int(s) + 1) % 100)
    if re.fullmatch(r"\d{8}", s) or re.fullmatch(r"\d{6}", s):
        return "%s-%s" % (s[:4], s[-2:])
    raise ValueError("a season looks like 2024-25")


def nba_ledger_path(out_dir, season):
    return os.path.join(out_dir, "nba-ledger-%s.json" % season.replace("-", ""))


def nba_stats_json(path, params, tries=1):
    url = NBA_STATS + path + "?" + urllib.parse.urlencode(params)
    return fetch_json(url, tries=tries, headers=NBA_STATS_HEADERS, timeout=NBA_STATS_TIMEOUT)


def nba_box_url(gid):
    return NBA_CDN + "/liveData/boxscore/boxscore_%s.json" % gid


def nba_box_date(game):
    """The game's US date from the CDN box score: gameEt carries the Eastern
    clock; failing that, the UTC time less five hours."""
    et = str(game.get("gameEt") or "")
    if re.match(r"\d{4}-\d{2}-\d{2}", et):
        return et[:10]
    utc = str(game.get("gameTimeUTC") or "")
    m = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})", utc)
    if m:
        d = dt.datetime(int(m.group(1)[:4]), int(m.group(1)[5:7]), int(m.group(1)[8:10]), int(m.group(2)), int(m.group(3))) - dt.timedelta(hours=5)
        return d.date().isoformat()
    return None


# ESPN's open site API: no headers, no key, every season back to the 2000s,
# the regular season marked on each event. The league's own CDN keeps box
# scores for the running season only (the 2024-25 walk found none, 15 Oct
# 2026) and the stats site will not answer a script, so a PAST season is
# read here: the scoreboard a week at a time for the games, the summary
# page per game for quarters, the box lines, every player's minutes and
# who sat, the crew.
ESPN_NBA = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
ESPN_TRICODE = {"GS": "GSW", "NY": "NYK", "NO": "NOP", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS", "PHX": "PHX", "BKN": "BKN"}


def espn_tricode(ab):
    ab = str(ab or "").upper()
    return ESPN_TRICODE.get(ab, ab)


def nba_us_date(iso):
    """A US date from an ESPN or NBA UTC stamp: five hours back, so a late
    West Coast tip stays on its own night (the date KillerSports uses)."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})", str(iso or ""))
    if not m:
        return None
    d = dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))) - dt.timedelta(hours=5)
    return d.date().isoformat()


def nba_games_from_espn(season, through_iso=None, log=None, since_iso=None):
    """Every regular-season final of a season from ESPN's scoreboard, a day
    a call: {id, date, away, home, an, hn, fa, fh} with ESPN's event id, NBA
    tricodes and the nicknames KillerSports uses. `since_iso` starts the walk
    there (the daily run picks up from the ledger's last date)."""
    y = int(season[:4])
    start, end = dt.date(y, 10, 1), dt.date(y + 1, 6, 30)
    if through_iso:
        end = min(end, dt.date.fromisoformat(through_iso))
    if since_iso:
        try:
            start = max(start, dt.date.fromisoformat(since_iso))
        except ValueError:
            pass
    out, d, failed = {}, start, []
    # one day a call: ESPN answers 400 to a date range (seen 15 Oct 2026)
    while d <= end:
        e = d
        try:
            doc = fetch_json(ESPN_NBA + "/scoreboard?dates=%s&limit=100" % d.strftime("%Y%m%d"), cache=False)
        except Exception as ex:  # noqa: BLE001
            failed.append(d.isoformat())
            if log and len(failed) <= 3:
                log("  %s: no scoreboard (%s)" % (d.isoformat(), ex))
            d = e + dt.timedelta(days=1)
            continue
        for ev in doc.get("events") or []:
            if int(((ev.get("season") or {}).get("type") or 0)) != 2:
                continue   # preseason, play-in, playoffs
            comp = ((ev.get("competitions") or [{}])[0]) or {}
            st = ((comp.get("status") or {}).get("type") or {})
            if not st.get("completed"):
                continue
            g = {"id": str(ev.get("id")), "date": nba_us_date(comp.get("date") or ev.get("date")), "t": comp.get("date") or ev.get("date"),
                 "away": None, "home": None, "an": None, "hn": None, "fa": None, "fh": None}
            for c in comp.get("competitors") or []:
                t = c.get("team") or {}
                side = "home" if c.get("homeAway") == "home" else "away"
                g[side] = espn_tricode(t.get("abbreviation"))
                g[("hn" if side == "home" else "an")] = t.get("name") or t.get("shortDisplayName")
                try:
                    g["fh" if side == "home" else "fa"] = int(c.get("score")) if c.get("score") not in (None, "") else None
                except (TypeError, ValueError):
                    pass
            if g["away"] and g["home"]:
                out[g["id"]] = g
        d = e + dt.timedelta(days=1)
    if failed and log:
        log("  %d day%s with no scoreboard answer (first %s, last %s)." % (len(failed), "" if len(failed) == 1 else "s", failed[0], failed[-1]))
    return sorted(out.values(), key=lambda g: (g["date"] or "", g["id"]))


def _espn_stat(stats, *names):
    for s in stats or []:
        if s.get("name") in names:
            v = str(s.get("displayValue") or s.get("value") or "")
            return v
    return ""


def _espn_attempts(v):
    """'40-88' -> 88; '12' -> 12."""
    try:
        return int(float(v.split("-")[-1])) if v else 0
    except ValueError:
        return 0


def nba_entry_from_espn(g, summ):
    """A ledger entry from ESPN's game summary: quarters from the header's
    line scores, the box lines from the team statistics, every player from
    the box with his minutes, points and plus-minus, the DNPs and the
    injury list as who sat, the officials."""
    box = (summ or {}).get("boxscore") or {}
    hdr = ((((summ or {}).get("header") or {}).get("competitions") or [{}])[0]) or {}
    sides = {"away": {}, "home": {}}
    for c in hdr.get("competitors") or []:
        side = "home" if c.get("homeAway") == "home" else "away"
        ls = []
        for q in c.get("linescores") or []:
            try:
                ls.append(int(float(q.get("displayValue") if q.get("displayValue") not in (None, "") else q.get("value") or 0)))
            except (TypeError, ValueError):
                ls.append(0)
        sides[side]["q"], sides[side]["ot"] = ls[:4], ls[4:]
        sides[side]["ab"] = espn_tricode((c.get("team") or {}).get("abbreviation"))
        try:
            sides[side]["score"] = int(c.get("score")) if c.get("score") not in (None, "") else None
        except (TypeError, ValueError):
            sides[side]["score"] = None
    for t in box.get("teams") or []:
        side = "home" if t.get("homeAway") == "home" else "away"
        st = t.get("statistics") or []
        sides[side]["line"] = {"fga": _espn_attempts(_espn_stat(st, "fieldGoalsMade-fieldGoalsAttempted", "fieldGoalsAttempted")),
                               "fta": _espn_attempts(_espn_stat(st, "freeThrowsMade-freeThrowsAttempted", "freeThrowsAttempted")),
                               "oreb": _espn_attempts(_espn_stat(st, "offensiveRebounds")), "tov": _espn_attempts(_espn_stat(st, "turnovers", "totalTurnovers")),
                               "min": 240.0}
        sides[side]["ab"] = sides[side].get("ab") or espn_tricode((t.get("team") or {}).get("abbreviation"))
    for p in box.get("players") or []:
        ab = espn_tricode((p.get("team") or {}).get("abbreviation"))
        side = "home" if ab == sides["home"].get("ab") else "away"
        played, out = sides[side].setdefault("pa", []), sides[side].setdefault("oa", [])
        for grp in p.get("statistics") or []:
            names = [str(x) for x in (grp.get("names") or grp.get("labels") or [])]
            ix = {k: (names.index(k) if k in names else None) for k in ("MIN", "+/-", "PTS", "REB", "AST", "3PT", "FG", "FT", "TO", "STL", "BLK")}
            iM = ix["MIN"]
            for a in grp.get("athletes") or []:
                ath = a.get("athlete") or {}
                pid, name = ath.get("id"), ath.get("displayName") or ath.get("shortName") or str(ath.get("id"))
                stats = a.get("stats") or []
                mins = nba_minutes(stats[iM]) if iM is not None and iM < len(stats) else 0.0
                if a.get("didNotPlay") or mins <= 0:
                    out.append([pid, name, str(a.get("reason") or "DNP")])
                    continue
                def _i(k):
                    try:
                        return int(float(str(stats[k]).replace("+", ""))) if k is not None and k < len(stats) else 0
                    except ValueError:
                        return 0
                def _made_att(k):
                    """'9-18' -> (9, 18)."""
                    v = str(stats[k]) if k is not None and k < len(stats) else ""
                    try:
                        made, att = v.split("-", 1)
                        return int(float(made)), int(float(att))
                    except ValueError:
                        return 0, 0
                fgm, fga = _made_att(ix["FG"])
                ftm, fta = _made_att(ix["FT"])
                tpm, _tpa = _made_att(ix["3PT"])
                pos = str(((ath.get("position") or {}).get("abbreviation") if isinstance(ath.get("position"), dict) else ath.get("position")) or "")
                played.append(nba_player_line(pid, name, 1 if a.get("starter") else 0, mins, _i(ix["PTS"]), _i(ix["+/-"]),
                                              _i(ix["REB"]), _i(ix["AST"]), tpm, fga, fta, _i(ix["TO"]), _i(ix["STL"]), _i(ix["BLK"]), fgm, ftm, pos))
    # the injury list on the page: who was out before the game, with the status
    for team in (summ or {}).get("injuries") or []:
        ab = espn_tricode((team.get("team") or {}).get("abbreviation"))
        side = "home" if ab == sides["home"].get("ab") else "away"
        out = sides[side].setdefault("oa", [])
        seen = {x[0] for x in out}
        for inj in team.get("injuries") or []:
            ath = inj.get("athlete") or {}
            if ath.get("id") in seen:
                continue
            det = inj.get("details") or {}
            out.append([ath.get("id"), ath.get("displayName") or str(ath.get("id")), "%s - %s" % (inj.get("status") or "Out", det.get("type") or det.get("detail") or "injury")])
    offs = [o.get("displayName") or o.get("fullName") for o in (((summ or {}).get("gameInfo") or {}).get("officials") or []) if isinstance(o, dict)]
    a, h = sides["away"], sides["home"]
    e = {"id": g["id"], "date": g.get("date"), "away": a.get("ab") or g.get("away"), "home": h.get("ab") or g.get("home"), "an": g.get("an"), "hn": g.get("hn"),
         "fa": a.get("score") if a.get("score") is not None else g.get("fa"), "fh": h.get("score") if h.get("score") is not None else g.get("fh"),
         "qa": a.get("q") or [], "qh": h.get("q") or [], "ota": a.get("ot") or [], "oth": h.get("ot") or [],
         "sa": a.get("line"), "sh": h.get("line"), "pa": a.get("pa") or [], "ph": h.get("pa") or [], "oa": a.get("oa") or [], "oh": h.get("oa") or [],
         "t": g.get("t"), "off": [o for o in offs if o], "detail": bool(a.get("line") and h.get("line"))}
    e["end"] = "OT" if (e["ota"] or e["oth"]) else "REG"
    e["pace"] = nba_pace(a.get("line"), h.get("line")) if e["detail"] else None
    return e


def nba_scan_ids(season, have, log, on_entry):
    """Walk a season's regular-season game ids on the CDN, building an entry
    from each box score found (no stats site at all). Calls on_entry(entry)
    for each; skips ids in `have`. Returns (fetched, misses)."""
    yy = season[2:4]
    fetched = misses = 0
    streak = 0
    for k in range(1, NBA_ID_LIMIT + 1):
        gid = "002%s%05d" % (yy, k)
        if gid in have:
            streak = 0
            continue
        try:
            box = fetch_json(nba_box_url(gid), tries=1, timeout=NBA_CDN_TIMEOUT, cache=False)
            game = box.get("game") or {}
            if not game.get("homeTeam"):
                raise ValueError("no game in the document")
        except Exception:  # noqa: BLE001
            misses += 1
            streak += 1
            if k > NBA_ID_FLOOR and streak >= NBA_ID_GAP:
                break
            continue
        streak = 0
        if int(game.get("gameStatus") or 0) != 3:
            continue   # not final yet (this season)
        g = {"id": gid, "date": nba_box_date(game), "away": None, "home": None, "fa": None, "fh": None}
        on_entry(nba_entry_from_cdn(g, box))
        fetched += 1
    return fetched, misses


def nba_result_set(doc, name=None):
    """stats.nba.com documents carry tables as headers + rowSet; this returns
    a list of dicts for the named (or first) table."""
    sets = (doc or {}).get("resultSets") or ([doc["resultSet"]] if (doc or {}).get("resultSet") else [])
    for rs in sets:
        if name is None or rs.get("name") == name:
            heads = rs.get("headers") or []
            return [dict(zip(heads, row)) for row in rs.get("rowSet") or []]
    return []


def nba_minutes(s):
    """'PT34M12.00S', '34:12', '34' or '' -> minutes as a float."""
    if s in (None, ""):
        return 0.0
    s = str(s)
    m = re.fullmatch(r"PT(?:(\d+)M)?(?:([\d.]+)S)?", s)
    if m:
        return float(m.group(1) or 0) + float(m.group(2) or 0) / 60.0
    if ":" in s:
        a, b = s.split(":", 1)
        try:
            return float(a) + float(b) / 60.0
        except ValueError:
            return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def nba_games_from_log(season):
    """Every regular-season game of a season from the league game log, one
    entry per game: {id, date, away, home, fa, fh}. Two rows a game in the
    log (one per team); the MATCHUP column says who was home."""
    rows = nba_result_set(nba_stats_json("/leaguegamelog", {"Counter": 0, "DateFrom": "", "DateTo": "", "Direction": "ASC", "LeagueID": "00",
                                                             "PlayerOrTeam": "T", "Season": season, "SeasonType": "Regular Season", "Sorter": "DATE"}),
                          "LeagueGameLog")
    games = {}
    for r in rows:
        gid = str(r.get("GAME_ID") or "")
        if not gid.startswith("002"):
            continue
        g = games.setdefault(gid, {"id": gid, "date": str(r.get("GAME_DATE") or "")[:10], "away": None, "home": None, "fa": None, "fh": None})
        ab, pts, m = r.get("TEAM_ABBREVIATION"), r.get("PTS"), str(r.get("MATCHUP") or "")
        if " @ " in m:
            g["away"], g["fa"] = ab, (int(pts) if pts is not None else None)
        else:
            g["home"], g["fh"] = ab, (int(pts) if pts is not None else None)
    return [g for g in games.values() if g["away"] and g["home"]]


def nba_games_from_schedule(season_iso_through):
    """This season's finals from the CDN schedule file (the current season
    only): {id, date, away, home, fa, fh} for games marked final up to a date."""
    doc = fetch_json(NBA_CDN + "/staticData/scheduleLeagueV2.json")
    out = []
    for day in ((doc.get("leagueSchedule") or {}).get("gameDates") or []):
        for g in day.get("games") or []:
            gid = str(g.get("gameId") or "")
            if not gid.startswith("002") or int(g.get("gameStatus") or 0) != 3:
                continue
            date = str(g.get("gameDateEst") or day.get("gameDate") or "")[:10]
            if "/" in date:   # the schedule writes 10/22/2024 00:00:00 on the day; the game carries ISO
                mth, dy, yr = date.split("/")[:3]
                date = "%s-%s-%s" % (yr[:4], mth.zfill(2), dy.zfill(2))
            if date > season_iso_through:
                continue
            at, ht = g.get("awayTeam") or {}, g.get("homeTeam") or {}
            out.append({"id": gid, "date": date, "away": at.get("teamTricode"), "home": ht.get("teamTricode"),
                        "fa": int(at["score"]) if at.get("score") is not None else None, "fh": int(ht["score"]) if ht.get("score") is not None else None})
    return out


def _nba_team_from_cdn(t):
    """One side of the CDN box score: quarters, the team line, the players."""
    reg, ot = [], []
    for p in t.get("periods") or []:
        (ot if str(p.get("periodType") or "").upper().startswith("OT") or int(p.get("period") or 0) > 4 else reg).append(int(p.get("score") or 0))
    st = t.get("statistics") or {}
    line = {"fga": int(st.get("fieldGoalsAttempted") or 0), "fta": int(st.get("freeThrowsAttempted") or 0),
            "oreb": int(st.get("reboundsOffensive") or 0), "tov": int(st.get("turnovers") or st.get("turnoversTotal") or 0),
            "min": nba_minutes(st.get("minutes")) or 240.0}
    played, out = [], []
    for p in t.get("players") or []:
        s = p.get("statistics") or {}
        mins = nba_minutes(s.get("minutes"))
        name = p.get("name") or ("%s %s" % (p.get("firstName") or "", p.get("familyName") or "")).strip()
        status = str(p.get("status") or "").upper()
        if status == "INACTIVE" or (status != "ACTIVE" and mins == 0 and p.get("notPlayingReason")):
            out.append([p.get("personId"), name, str(p.get("notPlayingReason") or p.get("notPlayingDescription") or "inactive")])
        elif mins > 0:
            played.append(nba_player_line(p.get("personId"), name, 1 if str(p.get("starter") or "0") == "1" else 0, mins,
                                          s.get("points"), s.get("plusMinusPoints"), s.get("reboundsTotal"), s.get("assists"), s.get("threePointersMade"),
                                          s.get("fieldGoalsAttempted"), s.get("freeThrowsAttempted"), s.get("turnovers"), s.get("steals"), s.get("blocks"),
                                          s.get("fieldGoalsMade"), s.get("freeThrowsMade"), p.get("position")))
        else:
            out.append([p.get("personId"), name, str(p.get("notPlayingReason") or "DNP")])
    return reg, ot, line, played, out


def nba_entry_from_cdn(g, box):
    """A ledger entry from the CDN live-data box score."""
    game = (box or {}).get("game") or {}
    at, ht = game.get("awayTeam") or {}, game.get("homeTeam") or {}
    qa, ota, la, pa, oa = _nba_team_from_cdn(at)
    qh, oth, lh, ph, oh = _nba_team_from_cdn(ht)
    e = {"id": g["id"], "date": g["date"], "away": at.get("teamTricode") or g.get("away"), "home": ht.get("teamTricode") or g.get("home"),
         "fa": int(at["score"]) if at.get("score") is not None else g.get("fa"), "fh": int(ht["score"]) if ht.get("score") is not None else g.get("fh"),
         "qa": qa, "qh": qh, "ota": ota, "oth": oth, "end": "OT" if ota or oth else "REG",
         "sa": la, "sh": lh, "pa": pa, "ph": ph, "oa": oa, "oh": oh, "detail": True,
         # tip-off (UTC) for the rest, travel and time-zone tests; the crew for the referee test
         "t": game.get("gameTimeUTC") or None,
         "off": [o.get("name") or ("%s %s" % (o.get("firstName") or "", o.get("familyName") or "")).strip() for o in (game.get("officials") or []) if isinstance(o, dict)]}
    e["pace"] = nba_pace(la, lh)
    return e


def nba_pace(la, lh):
    """Possessions per 48 minutes, the average of the two teams' estimates."""
    if not la or not lh:
        return None
    pa = la["fga"] - la["oreb"] + la["tov"] + NBA_PACE_FT * la["fta"]
    ph = lh["fga"] - lh["oreb"] + lh["tov"] + NBA_PACE_FT * lh["fta"]
    mins = ((la.get("min") or 240.0) + (lh.get("min") or 240.0)) / 2.0 / 5.0   # team minutes are five men's
    if mins <= 0:
        return None
    return round((pa + ph) / 2.0 * 48.0 / mins, 1)


def nba_entry_from_stats(g, trad, summary):
    """A ledger entry from the stats site's traditional box score (players,
    team lines) and summary (the line score by quarter)."""
    bs = (trad or {}).get("boxScoreTraditional") or {}
    sides = {}
    for key in ("awayTeam", "homeTeam"):
        t = bs.get(key) or {}
        st = t.get("statistics") or {}
        line = {"fga": int(st.get("fieldGoalsAttempted") or 0), "fta": int(st.get("freeThrowsAttempted") or 0),
                "oreb": int(st.get("reboundsOffensive") or 0), "tov": int(st.get("turnovers") or 0), "min": nba_minutes(st.get("minutes")) or 240.0}
        played, out = [], []
        for p in t.get("players") or []:
            s = p.get("statistics") or {}
            mins = nba_minutes(s.get("minutes"))
            name = p.get("name") or ("%s %s" % (p.get("firstName") or "", p.get("familyName") or "")).strip()
            if mins > 0:
                played.append(nba_player_line(p.get("personId"), name, 1 if (p.get("position") or "") else 0, mins, s.get("points"), s.get("plusMinusPoints"),
                                              s.get("reboundsTotal"), s.get("assists"), s.get("threePointersMade"), s.get("fieldGoalsAttempted"), s.get("freeThrowsAttempted"),
                                              s.get("turnovers"), s.get("steals"), s.get("blocks"), s.get("fieldGoalsMade"), s.get("freeThrowsMade"), p.get("position")))
            else:
                out.append([p.get("personId"), name, str(p.get("comment") or "DNP")])
        sides[key] = (t.get("teamTricode"), line, played, out)
    qa = qh = ota = oth = None
    for r in nba_result_set(summary, "LineScore"):
        q = [int(r.get("PTS_QTR%d" % k) or 0) for k in (1, 2, 3, 4)]
        o = [int(r.get("PTS_OT%d" % k) or 0) for k in range(1, 11) if r.get("PTS_OT%d" % k)]
        if r.get("TEAM_ABBREVIATION") == sides["awayTeam"][0]:
            qa, ota = q, o
        elif r.get("TEAM_ABBREVIATION") == sides["homeTeam"][0]:
            qh, oth = q, o
    a, h = sides["awayTeam"], sides["homeTeam"]
    offs = [("%s %s" % (r.get("FIRST_NAME") or "", r.get("LAST_NAME") or "")).strip() for r in nba_result_set(summary, "Officials")]
    e = {"id": g["id"], "date": g["date"], "away": a[0] or g.get("away"), "home": h[0] or g.get("home"), "fa": g.get("fa"), "fh": g.get("fh"),
         "qa": qa or [], "qh": qh or [], "ota": ota or [], "oth": oth or [], "end": "OT" if (ota or oth) else "REG",
         "sa": a[1], "sh": h[1], "pa": a[2], "ph": h[2], "oa": a[3], "oh": h[3], "detail": True, "t": None, "off": [o for o in offs if o]}
    e["pace"] = nba_pace(a[1], h[1])
    return e


def nba_game_entry(g, log):
    """The CDN box score first; the stats site's two documents when the CDN
    has none; scores only when neither can be read."""
    try:
        box = fetch_json(nba_box_url(g["id"]), timeout=NBA_CDN_TIMEOUT, cache=False)
        if (box.get("game") or {}).get("homeTeam"):
            return nba_entry_from_cdn(g, box)
    except Exception as e:  # noqa: BLE001
        log("  game %s: no CDN box score (%s); trying the stats site" % (g["id"], e))
    try:
        trad = nba_stats_json("/boxscoretraditionalv3", {"GameID": g["id"], "LeagueID": "00", "endPeriod": 0, "endRange": 0, "rangeType": 0, "startPeriod": 0, "startRange": 0})
        summ = nba_stats_json("/boxscoresummaryv2", {"GameID": g["id"]})
        return nba_entry_from_stats(g, trad, summ)
    except Exception as e:  # noqa: BLE001
        log("  game %s: no box score anywhere (%s); scores only" % (g["id"], e))
    return {"id": g["id"], "date": g["date"], "away": g.get("away"), "home": g.get("home"), "fa": g.get("fa"), "fh": g.get("fh"), "detail": False}


def nba_measure(games):
    """The basketball book's constants as the ledger measures them: points a
    game, the spread of the total and the margin, home court, overtime, the
    first half's share, pace. The engine's a-priori figures are set against
    these once two seasons are in."""
    fin = [g for g in games if g.get("fa") is not None and g.get("fh") is not None]
    n = len(fin)
    m = {"games": n}
    if not n:
        return m
    tots = [g["fa"] + g["fh"] for g in fin]
    margins = [g["fh"] - g["fa"] for g in fin]
    m["points_per_game"] = _mean(tots)
    m["total_sd"] = _sd(tots)
    m["home_margin"] = _mean(margins)
    m["margin_sd"] = _sd(margins)
    m["home_win_pct"] = sum(1 for x in margins if x > 0) / float(n)
    m["ot_rate"] = sum(1 for g in fin if g.get("end") == "OT") / float(n)
    withq = [g for g in fin if len(g.get("qa") or []) == 4 and len(g.get("qh") or []) == 4]
    if withq:
        reg = [sum(g["qa"]) + sum(g["qh"]) for g in withq]
        half = [g["qa"][0] + g["qa"][1] + g["qh"][0] + g["qh"][1] for g in withq]
        m["first_half_share"] = sum(half) / float(sum(reg)) if sum(reg) else None
        m["first_half_points"] = _mean(half)
        m["first_half_sd"] = _sd(half)
        m["quarter_shares"] = [sum(g["qa"][k] + g["qh"][k] for g in withq) / float(sum(reg)) for k in range(4)]
    paced = [g["pace"] for g in fin if g.get("pace")]
    if paced:
        m["pace"] = _mean(paced)
        m["pace_sd"] = _sd(paced)
    return m


def nba_ledger_report(m, log):
    n = m.get("games", 0)
    log("NBA ledger: %d regular-season final%s." % (n, "" if n == 1 else "s"))
    if not n:
        return
    for label, key, f in (("points per game, both teams", "points_per_game", "%.1f"), ("spread of the total (raw)", "total_sd", "%.1f"),
                          ("home margin", "home_margin", "%+.2f"), ("spread of the margin (raw)", "margin_sd", "%.1f"),
                          ("home wins", "home_win_pct", "%.3f"), ("overtime", "ot_rate", "%.3f"),
                          ("first-half share of regulation points", "first_half_share", "%.3f"), ("first-half points", "first_half_points", "%.1f"),
                          ("pace, possessions per 48", "pace", "%.1f")):
        if m.get(key) is not None:
            log("  %-42s %8s" % (label, f % m[key]))
    if m.get("quarter_shares"):
        log("  quarters' share of regulation points: " + " / ".join("%.3f" % x for x in m["quarter_shares"]))
    if n < 200:
        log("  Under 200 games: read these as noise until the sample is there.")


def make_nba_ledger(date_iso, out_dir, log, season=None):
    """A season's NBA ledger: this season up to date_iso, or a past season
    in full with --season. Resumable: written every NBA_LEDGER_FLUSH games."""
    current = nba_season_id(date_iso)
    season = nba_norm_season(season) if season else current
    past = season != current
    path = nba_ledger_path(out_dir, season)
    led = None
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            led = json.load(f)
        if led.get("format") != NBA_LEDGER_FORMAT:
            led = None
    led = led or {"format": NBA_LEDGER_FORMAT, "version": 1, "season": season, "games": [], "through": None}
    have = {g.get("id") for g in led["games"] if g.get("detail")}
    log("NBA %s: %d game%s already in the ledger with detail." % (season, len(have), "" if len(have) == 1 else "s"))
    byid = {g.get("id"): g for g in led["games"]}

    def flush():
        led["games"] = sorted(byid.values(), key=lambda g: ((g.get("date") or ""), g.get("id") or ""))
        led["through"] = date_iso if not past else "%d-06-30" % (int(season[:4]) + 1)
        led["generated"] = now_utc()
        led["measure"] = nba_measure(led["games"])
        with open(path, "w", encoding="utf-8") as f:
            json.dump(led, f, separators=(",", ":"))
    done = [0]

    def took(e):
        byid[e["id"]] = e
        done[0] += 1
        if done[0] % NBA_LEDGER_FLUSH == 0:
            flush()
            log("  %d fetched (%s); written." % (done[0], e.get("date")))
    # the games and their detail: ESPN's open API first for every season, the
    # scoreboard a day a call and the summary page per game (the user's machine
    # and the build container both read it; the league's CDN answered 403 on
    # his first run of the season, 15 Oct 2026, and its stats site will not
    # answer a script). The daily run walks the scoreboard from two days
    # before the ledger's last game. THIS season falls back to the CDN
    # schedule and box scores when ESPN lists nothing; a PAST season to the
    # stats site's game log and then the id walk.
    games, source = None, ""
    since = None
    if not past and led["games"]:
        last = max((g.get("date") or "") for g in led["games"])
        if last:
            since = (dt.date.fromisoformat(last) - dt.timedelta(days=2)).isoformat()
    try:
        games = nba_games_from_espn(season, None if past else date_iso, log, since_iso=since)
        source = "espn"
        log("ESPN scoreboard: %d regular-season finals listed%s." % (len(games), (" from %s" % since) if since else ""))
    except Exception as e:  # noqa: BLE001
        log("Could not read ESPN's scoreboard (%s)." % e)
        games = None
    if not past and games is None:   # ESPN did not answer at all; an empty answer is the truth before opening night
        try:
            games = nba_games_from_schedule(date_iso)
            source = "cdn"
            log("CDN schedule: %d finals listed up to %s." % (len(games), date_iso))
        except Exception as e:  # noqa: BLE001
            log("Could not read the CDN schedule either (%s)." % e)
    if (games is None or not games) and past:
        try:
            games = nba_games_from_log(season)
            source = "stats"
            log("League game log: %d regular-season games listed." % len(games))
        except Exception as e:  # noqa: BLE001
            games = None
            log("The stats site did not answer for the game log (%s): walking the season's game ids on the CDN instead." % e)
    if games is None and past:
        log("Walking ids 002%s00001 upward; a line prints every %d, and the file is written every %d so a run can be stopped and resumed." % (season[2:4], NBA_LEDGER_FLUSH, NBA_LEDGER_FLUSH))
        fetched, misses = nba_scan_ids(season, have, log, took)
        log("Walked the ids: %d box score%s read, %d id%s with none." % (fetched, "" if fetched == 1 else "s", misses, "" if misses == 1 else "s"))
    elif games is None:
        log("No games listed for %s yet." % season)
    else:
        todo = [g for g in sorted(games, key=lambda g: (g["date"] or "", g["id"])) if g["id"] not in have and (past or (g["date"] or "") <= date_iso)]
        log("%d game%s to fetch; a line prints every %d, and the file is written every %d so a run can be stopped and resumed." % (len(todo), "" if len(todo) == 1 else "s", NBA_LEDGER_FLUSH, NBA_LEDGER_FLUSH))
        for g in todo:
            if source == "espn":
                try:
                    took(nba_entry_from_espn(g, fetch_json(ESPN_NBA + "/summary?event=%s" % g["id"], timeout=NBA_CDN_TIMEOUT, cache=False)))
                except Exception as e:  # noqa: BLE001
                    log("  game %s (%s, %s @ %s): no summary (%s); scores only" % (g["id"], g.get("date"), g.get("away"), g.get("home"), e))
                    took({"id": g["id"], "date": g.get("date"), "away": g.get("away"), "home": g.get("home"), "an": g.get("an"), "hn": g.get("hn"),
                          "fa": g.get("fa"), "fh": g.get("fh"), "t": g.get("t"), "detail": False})
            else:
                took(nba_game_entry(g, log))
    # the box lines (19 Oct 2026): a game whose player entries predate them is
    # read again from its ESPN summary, so an older ledger fills in place;
    # written every NBA_LEDGER_FLUSH like the rest, so this too can be resumed
    short = [g for g in byid.values() if g.get("detail") and any(len(p) < 16 for p in (g.get("pa") or []) + (g.get("ph") or []))]
    if short and source == "espn":
        log("%d game%s in the ledger carry the old six-item player lines: reading their summaries again for the box stats (rebounds, assists, threes, the rest)." % (len(short), "" if len(short) == 1 else "s"))
        filled = 0
        for g in sorted(short, key=lambda g: (g.get("date") or "", g.get("id") or "")):
            try:
                e = nba_entry_from_espn(g, fetch_json(ESPN_NBA + "/summary?event=%s" % g["id"], timeout=NBA_CDN_TIMEOUT, cache=False))
            except Exception as e:  # noqa: BLE001
                log("  game %s (%s): no summary (%s); its lines stay short" % (g["id"], g.get("date"), e))
                continue
            took(e)
            filled += 1
        log("Filled the box lines on %d game%s." % (filled, "" if filled == 1 else "s"))
    elif short:
        log("%d game%s carry the old six-item player lines and this ledger did not come from ESPN; they stay as they are." % (len(short), "" if len(short) == 1 else "s"))
    flush()
    log("Added %d game%s. Wrote %s." % (done[0], "" if done[0] == 1 else "s", path))
    nba_ledger_report(led["measure"], log)
    return path


# ---- the NBA slate ------------------------------------------------------------
# Today's games with the boxes the basketball book scores or shows (totals/nba.py):
# each club's ratings, pace and games to date from the running ledger, the
# league's own figures beside them, rest, the who-is-out list from the injury
# report with each player's own line (this season after NBA_PLAYER_MIN_GAMES
# games, LAST season's before that, by player id, so a traded man carries his
# own numbers to his new club), and the context lines with the tag that says
# what the sheet did with each fact. Built 15 Oct 2026, five days before the
# season. The lines and prices come from the odds run, never from here.
NBA_MIN_TEAM_GAMES = 5
NBA_PLAYER_MIN_GAMES = 3
NBA_REGULAR_MPG = 20.0
NBA_CTX_NOTABLE = 6
NBA_CTX_MIN_CLUBS = 16
NBA_FADE_UNTIL = 50
NBA_WATCHED = {"DEN": "Nuggets", "UTA": "Jazz"}
NBA_SEASON_DATES = {"deadline": "2027-02-04", "last_two_weeks": "2027-03-29", "end": "2027-04-11"}   # a priori for 2026-27 (totals/nba.py SEASON_DATES)
NBA_NICK = {"ATL": "Hawks", "BOS": "Celtics", "BKN": "Nets", "CHA": "Hornets", "CHI": "Bulls", "CLE": "Cavaliers", "DAL": "Mavericks", "DEN": "Nuggets",
            "DET": "Pistons", "GSW": "Warriors", "HOU": "Rockets", "IND": "Pacers", "LAC": "Clippers", "LAL": "Lakers", "MEM": "Grizzlies", "MIA": "Heat",
            "MIL": "Bucks", "MIN": "Timberwolves", "NOP": "Pelicans", "NYK": "Knicks", "OKC": "Thunder", "ORL": "Magic", "PHI": "76ers", "PHX": "Suns",
            "POR": "Trail Blazers", "SAC": "Kings", "SAS": "Spurs", "TOR": "Raptors", "UTA": "Jazz", "WAS": "Wizards"}
NBA_TRICODE = {v: k for k, v in NBA_NICK.items()}
NBA_CTX_TAGS = {
    "ratings_faded": ("faded", "faded: the market over-moves with early-season ratings, so the projection's lean goes on the line at −0.25 a point until fifty games, tagged"),
    "ratings_shown": ("shown", "shown, not scored: past fifty games a side the market has the ratings priced"),
    "pace": ("shown", "shown, not scored: pace alone measured null against the close; it feeds the projection"),
    "points": ("shown", "shown, not scored: season points per game measured null against the close"),
    "form": ("shown", "shown, not scored: the last ten ran the wrong way against the close both seasons"),
    "ft": ("shown", "shown, not scored: the crews predict the free throws and the total does not follow"),
    "record": ("shown", "shown, not scored: the spread is priced against the box score"),
    "stage": ("scored", "scored, tagged: the stage of the season goes on the line (+1.0 after the deadline, +2.0 in the last two weeks)"),
    "watched": ("label", "watched, not scored: a club the close has run under two seasons running, home and away"),
    "rest": ("label", "a label: rest measured inside the number against two seasons of closes"),
    "out": ("shown", "shown, not scored: announced absences are in the close; the card measures the late ones"),
    "move": ("shown", "shown, not scored: the current line is the anchor and the move is already inside it"),
}


def espn_json(path):
    return fetch_json(ESPN_NBA + path, timeout=NBA_CDN_TIMEOUT, cache=False)


def nba_nick_tricode(name):
    """'Boston Celtics' / 'Celtics' / 'Portland Trail Blazers' -> the tricode, or None."""
    s = str(name or "").strip()
    if not s:
        return None
    for nick, tri in NBA_TRICODE.items():
        if s == nick or s.endswith(" " + nick):
            return tri
    return None


def _ls_value(x):
    v = x.get("value") if x.get("value") is not None else x.get("displayValue")
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def nba_day_games(date_iso):
    """ESPN's scoreboard for a day: every game, scheduled or final, with its id,
    tricodes, nicknames, scores, the half-time score, the tip-off and the state."""
    doc = espn_json("/scoreboard?dates=%s&limit=100" % date_iso.replace("-", ""))
    out = []
    for ev in doc.get("events") or []:
        comp = ((ev.get("competitions") or [{}])[0]) or {}
        st = ((comp.get("status") or {}).get("type") or {})
        g = {"id": str(ev.get("id")), "date": nba_us_date(comp.get("date") or ev.get("date")) or date_iso, "t": comp.get("date") or ev.get("date"),
             "type": int(((ev.get("season") or {}).get("type") or 0)), "final": bool(st.get("completed")), "state": str(st.get("description") or st.get("name") or ""),
             "away": None, "home": None, "an": None, "hn": None, "fa": None, "fh": None, "ha": None, "hh": None,
             "venue": ((comp.get("venue") or {}).get("fullName")) or "", "odds": nba_espn_odds(comp)}
        for c in comp.get("competitors") or []:
            t = c.get("team") or {}
            side = "home" if c.get("homeAway") == "home" else "away"
            g[side] = espn_tricode(t.get("abbreviation"))
            g["hn" if side == "home" else "an"] = t.get("name") or t.get("shortDisplayName") or NBA_NICK.get(g[side])
            try:
                g["fh" if side == "home" else "fa"] = int(c.get("score")) if c.get("score") not in (None, "") else None
            except (TypeError, ValueError):
                pass
            ls = [_ls_value(x) for x in (c.get("linescores") or [])]
            if len(ls) >= 2 and ls[0] is not None and ls[1] is not None:
                g["hh" if side == "home" else "ha"] = ls[0] + ls[1]
        if g["away"] and g["home"]:
            out.append(g)
    return out


def nba_team_tables(ledger_games, date_iso):
    """Every club's season to date from the ledger, before a date: ratings per
    100, pace, points for and against, the last ten, free-throw rate, home and
    road records, the last game's date; and the league's rating and pace."""
    per, lg = {}, {"pts": 0, "poss": 0.0, "mins": 0.0, "tots": []}
    for g in sorted(ledger_games or [], key=lambda g: (g.get("date") or "", g.get("id") or "")):
        if not g.get("detail") or not g.get("sa") or not g.get("sh") or g.get("fa") is None or (g.get("date") or "") >= date_iso:
            continue
        pa = g["sa"]["fga"] - g["sa"]["oreb"] + g["sa"]["tov"] + NBA_PACE_FT * g["sa"]["fta"]
        ph = g["sh"]["fga"] - g["sh"]["oreb"] + g["sh"]["tov"] + NBA_PACE_FT * g["sh"]["fta"]
        tot = g["fa"] + g["fh"]
        for ab, pts, opts, p, op, line, home in ((g["away"], g["fa"], g["fh"], pa, ph, g["sa"], False), (g["home"], g["fh"], g["fa"], ph, pa, g["sh"], True)):
            d = per.setdefault(ab, {"pts": 0, "opts": 0, "poss": 0.0, "oposs": 0.0, "mins": 0.0, "n": 0, "tots": [], "fta": 0, "fga": 0, "hw": 0, "hl": 0, "rw": 0, "rl": 0, "last": None})
            d["pts"] += pts; d["opts"] += opts; d["poss"] += p; d["oposs"] += op; d["mins"] += line.get("min") or 240.0; d["n"] += 1
            d["tots"].append(tot); d["fta"] += line.get("fta") or 0; d["fga"] += line.get("fga") or 0; d["last"] = g["date"]
            won = pts > opts
            if home:
                d["hw" if won else "hl"] += 1
            else:
                d["rw" if won else "rl"] += 1
            lg["pts"] += pts; lg["poss"] += p; lg["mins"] += line.get("min") or 240.0
        lg["tots"].append(tot)
    out = {}
    for ab, d in per.items():
        out[ab] = {"ortg": 100.0 * d["pts"] / d["poss"], "drtg": 100.0 * d["opts"] / d["oposs"], "pace": d["poss"] * 48.0 / (d["mins"] / 5.0),
                   "n": d["n"], "ppg": d["pts"] / float(d["n"]), "oppg": d["opts"] / float(d["n"]), "l10": sum(d["tots"][-10:]) / float(len(d["tots"][-10:])),
                   "ftr": (d["fta"] / float(d["fga"])) if d["fga"] else None, "hw": d["hw"], "hl": d["hl"], "rw": d["rw"], "rl": d["rl"], "last": d["last"]}
    league = None
    if lg["poss"] > 0 and len(lg["tots"]) >= 20:
        league = {"ortg": 100.0 * lg["pts"] / lg["poss"], "pace": lg["poss"] * 48.0 / (lg["mins"] / 5.0), "n": len(lg["tots"]), "ppg": sum(lg["tots"]) / float(len(lg["tots"]))}
    return out, league


def nba_player_tables(ledger_games):
    """Every player's season line from the ledger, by id: games, minutes, points
    and plus-minus a game, starts, the club he last dressed for."""
    per = {}
    for g in sorted(ledger_games or [], key=lambda g: (g.get("date") or "", g.get("id") or "")):
        for key, ab in (("pa", g.get("away")), ("ph", g.get("home"))):
            for p in g.get(key) or []:
                d = per.setdefault(str(p[0]), {"n": p[1], "team": ab, "g": 0, "mins": 0.0, "pts": 0, "pm": 0, "starts": 0})
                d["n"], d["team"] = p[1], ab
                d["g"] += 1; d["mins"] += float(p[3] or 0); d["pts"] += int(p[4] or 0); d["pm"] += int(p[5] or 0); d["starts"] += int(p[2] or 0)
    return {pid: {"n": d["n"], "team": d["team"], "g": d["g"], "mpg": d["mins"] / d["g"], "ppg": d["pts"] / float(d["g"]), "pm": d["pm"] / float(d["g"]), "starts": d["starts"]}
            for pid, d in per.items() if d["g"]}


def espn_athlete_id(ath):
    """The player's ESPN id: the injury page's athlete carries none as a field
    (the user's page of 15 Oct 2026), only in his player-card link and his
    headshot; the box scores key him by the same number."""
    pid = str((ath or {}).get("id") or "")
    if pid:
        return pid
    for l in (ath or {}).get("links") or []:
        m = re.search(r"/id/(\d+)", str(l.get("href") or ""))
        if m:
            return m.group(1)
    m = re.search(r"/(\d+)\.png", str(((ath or {}).get("headshot") or {}).get("href") or ""))
    return m.group(1) if m else ""


def nba_injuries():
    """ESPN's injury page: {tricode: [{id, n, st, note, pos, c, ret}]} for every
    club listed. The club is the athlete's own on his entry, else the page's
    heading; the id is read off his links when the page gives none."""
    doc = espn_json("/injuries")
    out = {}
    for team in doc.get("injuries") or []:
        t = team.get("team") or {}
        ab_team = espn_tricode(t.get("abbreviation") or team.get("abbreviation") or "") or nba_nick_tricode(t.get("displayName") or team.get("displayName") or team.get("name"))
        for inj in team.get("injuries") or []:
            ath = inj.get("athlete") or {}
            det = inj.get("details") or {}
            ab = espn_tricode(((ath.get("team") or {}).get("abbreviation")) or "") or ab_team
            if not ab:
                continue
            fs = det.get("fantasyStatus") if isinstance(det.get("fantasyStatus"), dict) else {}
            name = ath.get("displayName") or ath.get("shortName") or "?"
            e = {"id": espn_athlete_id(ath) or name, "n": name, "st": str(inj.get("status") or fs.get("description") or ""),
                 "note": str(det.get("type") or det.get("detail") or "")[:60], "pos": str(((ath.get("position") or {}).get("abbreviation")) or "")}
            if inj.get("shortComment"):
                e["c"] = str(inj["shortComment"])[:200]
            if det.get("returnDate"):
                e["ret"] = str(det["returnDate"])[:10]
            out.setdefault(ab, []).append(e)
    return out


def _odds_num(s):
    """'o221.5' / 'u221.5' / '-1.5' / '+105' / 'EVEN' -> a number, or None."""
    t = str(s if s is not None else "").strip().lower().lstrip("ou")
    if t in ("even", "ev", "pk", "pick"):
        return 0.0 if t in ("pk", "pick") else 100.0
    try:
        return float(t.replace("+", ""))
    except ValueError:
        return None


def nba_espn_odds(comp):
    """DraftKings' numbers on ESPN's scoreboard, when the event carries them:
    the total with its prices, the home spread with its prices, the two
    moneylines, and the OPENING total and spread. Shown on the row and the
    opener filled; the carded lines still come from the odds run."""
    for o in comp.get("odds") or []:
        tot, ps, ml = o.get("total") or {}, o.get("pointSpread") or {}, o.get("moneyline") or {}
        c = lambda d, k: ((d.get(k) or {}).get("close") or {})   # noqa: E731
        op_ = lambda d, k: ((d.get(k) or {}).get("open") or {})  # noqa: E731
        d = {"book": (o.get("provider") or {}).get("name") or "the book", "total": _odds_num(o.get("overUnder")) if o.get("overUnder") is not None else _odds_num(c(tot, "over").get("line")),
             "op": _odds_num(c(tot, "over").get("odds")), "up": _odds_num(c(tot, "under").get("odds")),
             "sp": _odds_num(o.get("spread")) if o.get("spread") is not None else _odds_num(c(ps, "home").get("line")),
             "sph": _odds_num(c(ps, "home").get("odds")), "spa": _odds_num(c(ps, "away").get("odds")),
             "hml": _odds_num(c(ml, "home").get("odds")), "aml": _odds_num(c(ml, "away").get("odds")),
             "o_total": _odds_num(op_(tot, "over").get("line")), "o_sp": _odds_num(op_(ps, "home").get("line"))}
        if d["total"] is not None or d["sp"] is not None:
            return d
    return None


def nba_out_list(ab, injuries, players, prior_players):
    """The who-is-out list for one club: each listed player with his status and his
    own line, this season's after NBA_PLAYER_MIN_GAMES games, last season's before."""
    out = []
    for inj in injuries.get(ab, []):
        p, q = players.get(inj["id"]), prior_players.get(inj["id"])
        src = None
        if p and p["g"] >= NBA_PLAYER_MIN_GAMES:
            src, where = p, "this season"
        elif q:
            src, where = q, "last season"
        elif p:
            src, where = p, "this season"
        e = {"id": inj["id"], "n": inj["n"], "st": inj["st"], "note": inj["note"]}
        for k in ("c", "ret", "pos"):
            if inj.get(k):
                e[k] = inj[k]
        if src:
            e.update({"mpg": round(src["mpg"], 1), "ppg": round(src["ppg"], 1), "pm": round(src["pm"], 1), "src": where, "g": src["g"]})
            if where == "last season" and src.get("team") and src["team"] != ab:
                e["note"] = (e["note"] + "; " if e["note"] else "") + "with %s last season" % NBA_NICK.get(src["team"], src["team"])
        out.append(e)
    out.sort(key=lambda e: (-(e.get("mpg") or 0), e["n"]))
    return out


def nba_rest_days(table_entry, date_iso):
    if not table_entry or not table_entry.get("last"):
        return None
    try:
        return (dt.date.fromisoformat(date_iso) - dt.date.fromisoformat(table_entry["last"])).days - 1
    except ValueError:
        return None


def nba_stage(date_iso):
    s = NBA_SEASON_DATES
    if date_iso > s["end"]:
        return None
    if date_iso >= s["last_two_weeks"]:
        return "the last two weeks of the season: +2.0 on the line"
    if date_iso > s["deadline"]:
        return "after the trade deadline: +1.0 on the line"
    return None


def nba_context(sides, tables, date_iso):
    """The context lines for one game (the hockey card's shape, nhl_context)."""
    out = []
    allt = [t for t in (tables or {}).values() if t["n"] >= NBA_MIN_TEAM_GAMES]
    st = nba_stage(date_iso)
    if st:
        out.append(ctx_line_nba("stage", "game", st[0].upper() + st[1:] + "."))
    for s in sides:
        nick, side, ab = s["nick"], s["side"], s["ab"]
        t = (tables or {}).get(ab)
        if ab in NBA_WATCHED:
            out.append(ctx_line_nba("watched", side, "%s games ran over the close both seasons, home and away (Nuggets +5.1 / +4.3, Jazz +3.0 / +5.7)." % nick))
        if t and t["n"] >= NBA_MIN_TEAM_GAMES and len(allt) >= NBA_CTX_MIN_CLUBS:
            rk = "ratings_faded" if t["n"] < NBA_FADE_UNTIL else "ratings_shown"
            r, n = ctx_rank(t["ortg"], [x["ortg"] for x in allt])
            if nba_notable(r, n):
                out.append(ctx_line_nba(rk, side, "%s score %.1f per 100 possessions, %s in the league (%d games)." % (nick, t["ortg"], ctx_phrase(r, n, "best", "worst"), t["n"])))
            r, n = ctx_rank(t["drtg"], [x["drtg"] for x in allt], high_first=False)
            if nba_notable(r, n):
                out.append(ctx_line_nba(rk, side, "%s allow %.1f per 100 possessions, %s in the league (%d games)." % (nick, t["drtg"], ctx_phrase(r, n, "best", "worst"), t["n"])))
            r, n = ctx_rank(t["pace"], [x["pace"] for x in allt])
            if nba_notable(r, n):
                out.append(ctx_line_nba("pace", side, "%s play at %.1f possessions a game, %s in the league." % (nick, t["pace"], ctx_phrase(r, n, "fastest", "slowest"))))
            r, n = ctx_rank(t["ppg"], [x["ppg"] for x in allt])
            if nba_notable(r, n):
                out.append(ctx_line_nba("points", side, "%s score %.1f a game, %s in the league." % (nick, t["ppg"], ctx_phrase(r, n, "most", "fewest"))))
            r, n = ctx_rank(t["oppg"], [x["oppg"] for x in allt])
            if nba_notable(r, n):
                out.append(ctx_line_nba("points", side, "%s allow %.1f a game, %s in the league." % (nick, t["oppg"], ctx_phrase(r, n, "most", "fewest"))))
            r, n = ctx_rank(t["l10"], [x["l10"] for x in allt])
            if nba_notable(r, n):
                out.append(ctx_line_nba("form", side, "%s games have averaged %.1f points over the last ten, %s in the league." % (nick, t["l10"], ctx_phrase(r, n, "highest", "lowest"))))
            if t.get("ftr") is not None:
                fr = [x["ftr"] for x in allt if x.get("ftr") is not None]
                r, n = ctx_rank(t["ftr"], fr)
                if nba_notable(r, n):
                    out.append(ctx_line_nba("ft", side, "%s take %.2f free throws per field-goal attempt, %s in the league." % (nick, t["ftr"], ctx_phrase(r, n, "most", "fewest"))))
            hw, hl, rw, rl = t["hw"], t["hl"], t["rw"], t["rl"]
            if side == "home" and hw + hl >= 5 and (hw / float(hw + hl) >= 0.75 or hw / float(hw + hl) <= 0.25):
                out.append(ctx_line_nba("record", side, "%s are %d-%d at home." % (nick, hw, hl)))
            if side == "away" and rw + rl >= 5 and (rw / float(rw + rl) >= 0.65 or rw / float(rw + rl) <= 0.25):
                out.append(ctx_line_nba("record", side, "%s are %d-%d on the road." % (nick, rw, rl)))
        if s.get("rest") == 0:
            out.append(ctx_line_nba("rest", side, "%s on a back to back." % nick))
        mins = sum(e.get("mpg") or 0 for e in (s.get("out") or []) if str(e.get("st", "")).lower().startswith("out") and (e.get("mpg") or 0) >= NBA_REGULAR_MPG)
        names = [e["n"] for e in (s.get("out") or []) if str(e.get("st", "")).lower().startswith("out") and (e.get("mpg") or 0) >= NBA_REGULAR_MPG]
        if names:
            out.append(ctx_line_nba("out", side, "%s without %s: %.0f minutes a game of regulars." % (nick, ", ".join(names[:4]) + (" and more" if len(names) > 4 else ""), mins)))
    return out


def nba_notable(rank, n):
    return rank is not None and n >= NBA_CTX_MIN_CLUBS and (rank <= NBA_CTX_NOTABLE or rank > n - NBA_CTX_NOTABLE)


def ctx_line_nba(kind, side, text):
    s, tag = NBA_CTX_TAGS[kind]
    return {"side": side, "k": kind, "s": s, "t": text, "tag": tag}


NBA_INPUT_IDS = ("naort", "nhort", "nadrt", "nhdrt", "napace", "nhpace", "nagp", "nhgp", "nlrtg", "nlpace", "narest", "nhrest", "nbaout", "nbactx", "opened", "ncrew", "nbarefs")

# ---- the crew: the day's assignments and each referee's line from the ledger ----
# The league posts the crews about 9 am Eastern on official.nba.com; the page
# reads a JSON feed by date (read against the user's download of 15 Oct 2026
# and live the same day: nba.Table.rows, one row a game, the tricodes in
# home_team_abbr / away_team_abbr and the game code, the officials as
# official1..3 with a usually-null fourth; the G League and the WNBA ride
# beside it). Shown on the Context card, never scored: against two seasons
# of closes crews predict the night's free throws (slope 0.60, t 7.3) and the
# total does not follow them (t -1.0), NBA.md. When the feed is not up the
# Crew box on the sheet takes the names by hand and the card composes the
# same line.
NBA_OFFICIALS_URL = "https://official.nba.com/wp-json/api/v1/get-game-officials?date=%s"
NBA_OFFICIALS_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                         "Referer": "https://official.nba.com/referee-assignments/", "Accept": "application/json, text/plain, */*"}


# Each referee's games against the closing total over the backtest's two seasons,
# 2024-25 and 2025-26: the ledgers joined to KillerSports' closes, generated 15 Oct
# 2026 by tools_nba_ref_table.py (86 officials over 2442 joined games with a crew; [games, over, under, push] against the closing total). SHOWN on the
# Context card beside each official's free throws and points; not scored: the
# crew's own over/under residual to date measured +0.17 (t 1.0) against the
# close. With 86 officials a few sit two sigma from even by chance alone, so a
# tilt here is a watch until this season's record (from the odds log, beside
# it) says the same thing out of sample.
NBA_REF_OU = {
    "Aaron Smith": [38, 20, 18, 0], "Agon Abazi": [4, 1, 3, 0], "Andy Nagy": [126, 76, 50, 0],
    "Ashley Moyer-Gleich": [50, 26, 24, 0], "Ben Taylor": [80, 43, 36, 1], "Bill Kennedy": [77, 39, 38, 0],
    "Biniam Maru": [40, 21, 19, 0], "Brandon Adair": [80, 32, 48, 0], "Brandon Schwab": [103, 51, 51, 1],
    "Brent Barnaky": [122, 60, 62, 0], "Brent Haskill": [13, 6, 6, 1], "Brett Nansel": [69, 35, 33, 1],
    "Brian Forte": [117, 48, 69, 0], "CJ Washington": [103, 63, 39, 1], "Che Flores": [78, 46, 31, 1],
    "Chelisa Painter": [3, 0, 3, 0], "Courtney Kirkland": [120, 63, 57, 0], "Curtis Blair": [116, 47, 68, 1],
    "Danielle Scott": [92, 49, 43, 0], "Dannica Baroody": [38, 17, 21, 0], "David Guthrie": [48, 18, 29, 1],
    "Dedric Taylor": [75, 33, 42, 0], "Derek Richardson": [40, 19, 21, 0], "Derrick Collins": [81, 39, 42, 0],
    "Ed Malloy": [100, 44, 56, 0], "Eric Dalen": [107, 49, 58, 0], "Eric Lewis": [14, 10, 4, 0],
    "Evan Scott": [100, 51, 49, 0], "Gediminas Petraitis": [130, 61, 68, 1], "Gina Catanzariti": [3, 2, 1, 0],
    "Intae Hwang": [57, 27, 30, 0], "J.B. DeRosa": [101, 53, 47, 1], "J.D. Ralls": [37, 21, 15, 1],
    "J.T. Orr": [99, 44, 54, 1], "JD Ralls": [43, 15, 28, 0], "Jacyn Goble": [133, 68, 65, 0],
    "James Capers": [89, 56, 33, 0], "James Williams": [127, 60, 66, 1], "Jason Goldenberg": [116, 66, 50, 0],
    "Jenna Reneau": [44, 18, 26, 0], "Jenna Schroeder": [102, 45, 55, 2], "John Butler": [121, 57, 64, 0],
    "John Conley": [79, 44, 35, 0], "John Goble": [116, 63, 53, 0], "Jonathan Sterling": [92, 48, 44, 0],
    "Josh Tiven": [128, 67, 61, 0], "Justin Van Duyne": [129, 60, 68, 1], "Karl Lane": [113, 62, 49, 2],
    "Kevin Cutler": [123, 55, 67, 1], "Kevin Scott": [119, 56, 63, 0], "Klajdi Mulla": [3, 2, 1, 0],
    "Leon Wood": [40, 22, 18, 0], "Marat Kogut": [118, 61, 57, 0], "Marc Davis": [122, 71, 51, 0],
    "Marcy Williams": [2, 1, 1, 0], "Mark Lindsay": [125, 64, 61, 0], "Matt Boland": [36, 19, 17, 0],
    "Matt Kallio": [82, 47, 35, 0], "Matt Myers": [101, 56, 45, 0], "Michael Smith": [77, 39, 38, 0],
    "Mitchell Ervin": [127, 67, 59, 1], "Mousa Dagher": [113, 57, 55, 1], "Natalie Sago": [127, 57, 68, 2],
    "Nate Cearley": [8, 4, 4, 0], "Nate Green": [113, 58, 54, 1], "Nick Buchert": [127, 68, 59, 0],
    "Pat Fraher": [127, 71, 56, 0], "Pat O'Connell": [48, 20, 28, 0], "Phenizee Ransom": [119, 63, 54, 2],
    "Ray Acosta": [132, 66, 65, 1], "Robert Hussey": [93, 48, 45, 0], "Rodney Mott": [91, 43, 48, 0],
    "Scott Foster": [109, 66, 41, 2], "Scott Twardoski": [106, 54, 52, 0], "Sean Corbin": [120, 58, 62, 0],
    "Sean Wright": [105, 57, 48, 0], "Sha'Rae Mitchell": [76, 41, 35, 0], "Simone Jelks": [87, 50, 37, 0],
    "Suyash Mehta": [92, 49, 43, 0], "Tom Washington": [41, 15, 25, 1], "Tony Brothers": [112, 56, 54, 2],
    "Tre Maddox": [99, 62, 37, 0], "Tyler Ford": [124, 68, 56, 0], "Tyler Mirkovich": [4, 1, 3, 0],
    "Tyler Ricks": [67, 33, 33, 1], "Zach Zarba": [118, 58, 60, 0],
}


def _official_rows(doc):
    """Every dict in the feed that names a first official, wherever it sits."""
    out = []
    def walk(x):
        if isinstance(x, dict):
            if any(k in x for k in ("official1", "OFFICIAL1", "crew_chief", "referee1")):
                out.append(x)
            else:
                for v in x.values():
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(doc)
    return out


def nba_officials(date_iso):
    """{(away tricode, home tricode): [names]} for a date from the league's feed."""
    doc = fetch_json(NBA_OFFICIALS_URL % date_iso, headers=NBA_OFFICIALS_HEADERS, timeout=NBA_CDN_TIMEOUT, cache=False)
    if isinstance(doc, dict) and isinstance(doc.get("nba"), (dict, list)):
        doc = doc["nba"]   # the feed carries the G League and the WNBA beside the NBA
    out = {}
    for r in _official_rows(doc):
        low = {str(k).lower(): v for k, v in r.items()}
        names = []
        for k in ("official1", "official2", "official3", "crew_chief", "referee1", "referee2", "referee3", "umpire1", "umpire2"):
            v = low.get(k)
            if v and str(v).strip() and str(v).strip() not in names:
                names.append(str(v).strip())
        # the feed (the user's download of 15 Oct 2026): home_team_abbr / away_team_abbr are the league's tricodes, home_team / away_team the cities
        away = str(low.get("away_team_abbr") or low.get("away_team_abbreviation") or "").strip().upper()
        home = str(low.get("home_team_abbr") or low.get("home_team_abbreviation") or "").strip().upper()
        code = str(low.get("game_code") or "")
        if (len(away) != 3 or len(home) != 3) and "/" in code and len(code.split("/")[-1]) == 6:
            away, home = code.split("/")[-1][:3].upper(), code.split("/")[-1][3:].upper()
        if len(away) == 3 and len(home) == 3 and names:
            out[(espn_tricode(away), espn_tricode(home))] = names
    return out


def nba_season_ref_ou(this_season, odds_log):
    """{name: [over, under]} for this season: each ledger game with a crew graded
    against the close the odds run last saw (odds-log.json, by date and nicknames)."""
    out = {}
    if not this_season or not odds_log:
        return out
    try:
        with open(odds_log, encoding="utf-8") as f:
            logd = json.load(f)
    except (OSError, ValueError):
        return out
    for g in this_season:
        if not g.get("off") or g.get("fa") is None or g.get("fh") is None:
            continue
        an, hn = g.get("an") or NBA_NICK.get(g.get("away"), g.get("away")), g.get("hn") or NBA_NICK.get(g.get("home"), g.get("home"))
        last = (logd.get(odds_log_key("NBA", g.get("date") or "", an, hn)) or {}).get("last") or {}
        try:
            close = float(last.get("line"))
        except (TypeError, ValueError):
            continue
        tot = g["fa"] + g["fh"]
        if abs(tot - close) < 1e-9:
            continue
        for name in g["off"]:
            d = out.setdefault(str(name), [0, 0])
            d[0 if tot > close else 1] += 1
    return out


def nba_referee_tables(ledger_games, this_season=None, odds_log=None):
    """Each official's games, free throws and points a game over the ledgers, the
    league's over the same games, and his record against the close: the past two
    seasons' from NBA_REF_OU, this season's from the odds log.
    {"lg": [g, fta, pts], "r": {name: [g, fta, pts, over2, under2, over1, under1]}}."""
    per, lg = {}, [0, 0, 0]
    for g in ledger_games or []:
        if not g.get("off") or not g.get("sa") or not g.get("sh") or g.get("fa") is None or g.get("fh") is None:
            continue
        fta, pts = (g["sa"].get("fta") or 0) + (g["sh"].get("fta") or 0), g["fa"] + g["fh"]
        lg[0] += 1; lg[1] += fta; lg[2] += pts
        for name in g["off"]:
            d = per.setdefault(str(name), [0, 0, 0])
            d[0] += 1; d[1] += fta; d[2] += pts
    if not lg[0]:
        return None
    now = nba_season_ref_ou(this_season, odds_log)
    out = {}
    for n, d in per.items():
        past, cur = NBA_REF_OU.get(n) or [0, 0, 0, 0], now.get(n) or [0, 0]
        out[n] = [d[0], round(d[1] / float(d[0]), 1), round(d[2] / float(d[0]), 1), past[1], past[2], cur[0], cur[1]]
    return {"lg": [lg[0], round(lg[1] / float(lg[0]), 1), round(lg[2] / float(lg[0]), 1)], "r": out}


def nba_crew_summary(names, refs):
    """One printable line for the log: each named official's line, the league's beside."""
    if not refs:
        return ", ".join(names)
    bits = []
    for n in names:
        d = refs["r"].get(n)
        if not d:
            bits.append("%s no games in the ledger" % n)
            continue
        ou = (", over the close %d-%d the last two seasons" % (d[3], d[4])) if len(d) > 4 and (d[3] or d[4]) else ""
        ou += (", %d-%d this season" % (d[5], d[6])) if len(d) > 6 and (d[5] or d[6]) else ""
        bits.append("%s %.1f FTA / %.1f pts over %d%s" % (n, d[1], d[2], d[0], ou))
    return "; ".join(bits) + " (league %.1f / %.1f)" % (refs["lg"][1], refs["lg"][2])


def nba_odds_note(o, away, home):
    """One line on the row for the scoreboard's book: the numbers at the run and
    where they opened."""
    def price(p):
        return "%+.0f" % p if p is not None else "?"
    bits = []
    if o.get("total") is not None:
        bits.append("total %s (%s/%s)%s" % (fmt(o["total"], 1), price(o.get("op")), price(o.get("up")), (", opened %s" % fmt(o["o_total"], 1)) if o.get("o_total") is not None and abs(o["o_total"] - o["total"]) > 1e-9 else ""))
    if o.get("sp") is not None:
        fav = home if o["sp"] <= 0 else away
        ln = o["sp"] if o["sp"] <= 0 else -o["sp"]
        bits.append("%s %s (%s/%s)%s" % (fav, ("%+g" % ln) if ln else "pick", price(o.get("sph")), price(o.get("spa")),
                                        (", opened %+g" % (o["o_sp"] if o["sp"] <= 0 else -o["o_sp"])) if o.get("o_sp") is not None and abs(o["o_sp"] - o["sp"]) > 1e-9 else ""))
    if o.get("hml") is not None and o.get("aml") is not None:
        bits.append("moneyline %s %s / %s %s" % (home, price(o["hml"]), away, price(o["aml"])))
    return "%s on ESPN's scoreboard at the slate run: %s. Shown for the opener and as a check on the carded book; the lines come from the odds run." % (o.get("book") or "The book", "; ".join(bits))


def build_nba_game(g, date_iso, tables, league, players, prior_players, injuries, log, have_ledger=True, officials=None, refs=None):
    away, home = g.get("an") or NBA_NICK.get(g["away"], g["away"]), g.get("hn") or NBA_NICK.get(g["home"], g["home"])
    inputs = {k: "" for k in NBA_INPUT_IDS}
    notes = []
    out = {"sport": "NBA", "gdate": date_iso, "away": away, "home": home, "gameId": g["id"], "first_tip_utc": g.get("t") or "", "venue": g.get("venue") or "",
           "status": g.get("state") or "", "inputs": inputs, "notes": notes}
    log("%s @ %s  (%s, %s UTC, %s)" % (away, home, out["venue"] or "venue ?", str(g.get("t") or "")[11:16] or "?", g.get("state") or "scheduled"))
    if g.get("type") == 1:
        notes.append("PRESEASON: the lines are thin and the rotations are not the season's; the record keeps it apart if you log it.")
    sides = []
    for side, ab, nick in (("away", g["away"], away), ("home", g["home"], home)):
        p = "a" if side == "away" else "h"
        t = (tables or {}).get(ab)
        cs = {"side": side, "ab": ab, "nick": nick, "rest": None, "out": []}
        if t and t["n"] >= NBA_MIN_TEAM_GAMES:
            inputs["n%sort" % p], inputs["n%sdrt" % p], inputs["n%space" % p] = fmt(t["ortg"], 1), fmt(t["drtg"], 1), fmt(t["pace"], 1)
            log("  %s ratings to date: %s / %s per 100, pace %s (%d games)" % (side, inputs["n%sort" % p], inputs["n%sdrt" % p], inputs["n%space" % p], t["n"]))
        elif t:
            notes.append("%s has %d game%s this season: the ratings are left blank until %d (the sheet's fade waits for ten)." % (nick, t["n"], "" if t["n"] == 1 else "s", NBA_MIN_TEAM_GAMES))
        elif have_ledger:
            notes.append("%s has no game in the ledger yet." % nick)
        inputs["n%sgp" % p] = str(t["n"]) if t else "0"
        rest = nba_rest_days(t, date_iso)
        if rest is not None:
            inputs["n%srest" % p] = str(max(0, rest))
            cs["rest"] = max(0, rest)
        cs["out"] = nba_out_list(ab, injuries, players, prior_players)
        for e in cs["out"]:
            if e.get("ret") and e["ret"] < date_iso:
                e["past"] = True   # the page's return date is before this game: the listing is likely stale
        if cs["out"]:
            regs = [e for e in cs["out"] if str(e.get("st", "")).lower().startswith("out") and (e.get("mpg") or 0) >= NBA_REGULAR_MPG]
            log("  %s injury report: %d listed%s" % (side, len(cs["out"]), ("; OUT regulars: " + ", ".join("%s %.0f min" % (e["n"], e["mpg"]) for e in regs)) if regs else ""))
        sides.append(cs)
    if league:
        inputs["nlrtg"], inputs["nlpace"] = fmt(league["ortg"], 1), fmt(league["pace"], 1)
    inputs["nbaout"] = json.dumps({"away": sides[0]["out"], "home": sides[1]["out"]}, separators=(",", ":"))
    for s in sides:
        if s["ab"] in NBA_WATCHED:
            notes.append("%s: a club the close has run under both seasons, home and away. Watched on the sheet, not scored." % s["nick"])
    try:
        ctx = nba_context(sides, tables, date_iso)
    except Exception as e:  # noqa: BLE001
        ctx = []
        notes.append("Could not build the context lines: %s" % e)
    o = g.get("odds")
    if o:
        notes.append(nba_odds_note(o, away, home))
        if o.get("o_total") is not None:
            inputs["opened"] = fmt(o["o_total"], 1)
        moves = []
        if o.get("o_total") is not None and o.get("total") is not None and abs(o["total"] - o["o_total"]) >= 1.0:
            moves.append("the total opened %s and sits %s, %s %g" % (fmt(o["o_total"], 1), fmt(o["total"], 1), "down" if o["total"] < o["o_total"] else "up", abs(o["total"] - o["o_total"])))
        if o.get("o_sp") is not None and o.get("sp") is not None and abs(o["sp"] - o["o_sp"]) >= 1.0:
            moves.append("%s opened %+g and sit %+g" % (home, o["o_sp"], o["sp"]))
        if moves:
            ctx.append(ctx_line_nba("move", "game", "%s: %s." % (o.get("book") or "The book", "; ".join(moves))))
    if ctx:
        inputs["nbactx"] = json.dumps(ctx, separators=(",", ":"))
        for c in ctx:
            log("  context: %s  [%s]" % (c["t"], c["s"]))
    if not injuries:
        notes.append("The injury report could not be read; the who-is-out list is empty. Check the league's report before betting.")
    if refs:
        inputs["nbarefs"] = json.dumps(refs, separators=(",", ":"))
    crew = (officials or {}).get((g["away"], g["home"]))
    if crew:
        inputs["ncrew"] = ", ".join(crew)
        log("  crew: " + nba_crew_summary(crew, refs))
    elif officials is not None:
        notes.append("No crew on the league's feed for this game yet (posted about 9 am Eastern): type the names in the Crew box when they are up.")
    for n in notes:
        log("  note: " + n)
    return out


def nba_prev_season(season):
    y = int(season[:4])
    return "%d-%02d" % (y - 1, y % 100)


def load_nba_ledger(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    return d if d.get("format") == NBA_LEDGER_FORMAT and isinstance(d.get("games"), list) else None


def make_nba_slate(date_iso, out_dir, log):
    games = [g for g in nba_day_games(date_iso) if not g["final"]]
    if not games:
        log("No NBA games on the feed for %s." % date_iso)
    season = nba_season_id(date_iso)
    led = load_nba_ledger(nba_ledger_path(out_dir, season))
    prior = load_nba_ledger(nba_ledger_path(out_dir, nba_prev_season(season)))
    tables, league = nba_team_tables(led["games"] if led else [], date_iso)
    players = nba_player_tables(led["games"] if led else [])
    prior_players = nba_player_tables(prior["games"] if prior else [])
    if led:
        log("Ledger %s: %d games through %s; %d clubs with %d+ games." % (season, len(led["games"]), led.get("through"), sum(1 for t in tables.values() if t["n"] >= NBA_MIN_TEAM_GAMES), NBA_MIN_TEAM_GAMES))
    else:
        log("No ledger for %s in %s: run 'python slate.py nba-ledger' (Run NBA ledger.bat) and the ratings fill." % (season, out_dir))
    if prior:
        log("Last season's ledger: %d players' lines as the prior for the who-is-out list." % len(prior_players))
    else:
        log("No ledger for %s in the folder: a player with under %d games this season has no line on the who-is-out list." % (nba_prev_season(season), NBA_PLAYER_MIN_GAMES))
    if league:
        log("League to date: %.1f per 100 possessions, pace %.1f, %.1f points a game (%d games)." % (league["ortg"], league["pace"], league["ppg"], league["n"]))
    injuries = {}
    try:
        injuries = nba_injuries()
        log("Injury report: %d clubs, %d players listed." % (len(injuries), sum(len(v) for v in injuries.values())))
    except Exception as e:  # noqa: BLE001
        log("Could not read the injury report (%s)." % e)
    prior2 = load_nba_ledger(nba_ledger_path(out_dir, nba_prev_season(nba_prev_season(season))))   # two seasons back, for the referees' lines only
    refs = nba_referee_tables((led["games"] if led else []) + (prior["games"] if prior else []) + (prior2["games"] if prior2 else []), led["games"] if led else [], odds_log_path(out_dir))
    if refs:
        log("Referees: %d officials' lines over %d ledger games%s (league %.1f free throws and %.1f points a game)." % (
            len(refs["r"]), refs["lg"][0], " across three seasons" if prior2 and prior else (" across two seasons" if prior else ""), refs["lg"][1], refs["lg"][2]))
    officials = None
    try:
        officials = nba_officials(date_iso)
        log("Crews: %d game%s on the league's assignments feed." % (len(officials), "" if len(officials) == 1 else "s"))
    except Exception as e:  # noqa: BLE001
        log("Could not read the league's referee assignments (%s): type the crews in the Crew box from official.nba.com/referee-assignments." % e)
    rows = []
    for g in games:
        try:
            rows.append(build_nba_game(g, date_iso, tables, league, players, prior_players, injuries, log, have_ledger=bool(led and led.get("games")), officials=officials, refs=refs))
        except Exception as e:  # noqa: BLE001
            log("%s @ %s: FAILED (%s); left out of the slate" % (g.get("an"), g.get("hn"), e))
        log("")
    doc = {"format": FORMAT, "version": VERSION, "date": date_iso, "generated": now_utc(), "source": "slate.py nba: ESPN's site API and the ledger", "games": rows}
    path = os.path.join(out_dir, "nba-slate-%s.json" % date_iso)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    log("Wrote %s with %d game%s. Open The Super Model -> Saving -> Load slate; then run the odds for the lines." % (path, len(rows), "" if len(rows) == 1 else "s"))
    return path


def make_nba_grade(date_iso, out_dir, log):
    games = nba_day_games(date_iso)
    rows = []
    for g in games:
        away, home = g.get("an") or NBA_NICK.get(g["away"], g["away"]), g.get("hn") or NBA_NICK.get(g["home"], g["home"])
        if not g["final"] or g["fa"] is None or g["fh"] is None:
            log("%s @ %s: %s, not final; skipped" % (away, home, g.get("state") or "not started"))
            continue
        fin = {"fa": str(g["fa"]), "fh": str(g["fh"])}
        notes = []
        ha, hh = g.get("ha"), g.get("hh")
        # the summary page: the half-time score when the scoreboard has none, and
        # every player's box line for the Props tab (19 Oct 2026), by ESPN id
        box = None
        try:
            summ = espn_json("/summary?event=%s" % g["id"])
            e = nba_entry_from_espn({"id": g["id"], "date": date_iso}, summ)
            if (ha is None or hh is None) and len(e.get("qa") or []) >= 2 and len(e.get("qh") or []) >= 2:
                ha, hh = e["qa"][0] + e["qa"][1], e["qh"][0] + e["qh"][1]
            box = nba_props_box(e)
        except Exception as ex:  # noqa: BLE001
            notes.append("Could not read the summary page (%s): no half-time score from it, and no box lines for the props." % ex)
        if ha is not None and hh is not None:
            fin["f5a"], fin["f5h"] = str(ha), str(hh)
        else:
            notes.append("No half-time score on the feed; type it by hand.")
        row = {"sport": "NBA", "gdate": date_iso, "away": away, "home": home, "gameId": g["id"], "finals": fin, "notes": notes}
        if box:
            row["box"] = box
        c = odds_close_for(odds_log_path(out_dir), "NBA", date_iso, away, home)
        if c:
            row["close"] = c
        log("%s @ %s: final %s-%s, at the half %s-%s%s" % (away, home, fin["fa"], fin["fh"], fin.get("f5a", "?"), fin.get("f5h", "?"), (" · close %s" % c["ctot"]) if c else ""))
        rows.append(row)
    doc = {"format": FORMAT, "version": VERSION, "date": date_iso, "generated": now_utc(), "source": "slate.py nba-grade: ESPN's site API", "games": rows}
    path = os.path.join(out_dir, "nba-grade-%s.json" % date_iso)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    log("Wrote %s with %d final%s. Load it into The Super Model the same way; it grades the card and the Props tab together." % (path, len(rows), "" if len(rows) == 1 else "s"))
    return path


# ---- NBA player props (19 Oct 2026) ------------------------------------------
# The user: "set up another tab for player props... find the ideal scenario
# for player props". One file a day for The Super Model's Props tab: every
# player prop The Odds API lists on the day's games (points, rebounds,
# assists, threes, points + rebounds + assists), each with the book's line and
# prices, and beside it the slate's own projection from the ledgers' box lines:
#   rate x minutes      his per-minute rate this season, last season's as a
#                       prior at half its minutes (PROPS_PRIOR_CAP of them at
#                       most), times the minutes of his last PROPS_LAST_N games
#   regulars out        pooled over 2025-26 (26,628 player lines): every 30
#                       minutes a game of teammates missing who play 24+ adds
#                       1.42 minutes (t 36), 0.56 points per 36 (t 11) and
#                       0.09 assists per 36 (t 6); rebounds and threes moved
#                       nothing (t 0.6, 1.8), so they get no rate lift. SCORED
#   pace                the matchup's pace against the league's, in full
#   defence v position  the LEDGER's own table: what each defence allowed per
#                       minute to guards, forwards and centres against the
#                       league, this season shrunk toward last season's. A
#                       defence's lean over the first half of 2025-26 carried
#                       into its second half at 0.77 (points, t 8), 0.74
#                       (rebounds), 0.73 (assists) and 0.41 (threes), and
#                       those are the weights. HashtagBasketball's table is
#                       read beside it and SHOWN as a rank, never scored
#   home / road         SHOWN, not scored: a player's own split over the first
#                       half of 2025-26 predicted the second half's at r 0.08
# A projection built this way is unbiased (points +0.10 over 14,370 player-
# games; rebounds, assists and threes within 0.05) and misses by k x sqrt
# (projection) one sigma, k measured per market (PROPS_SD_K), a normal that
# held 69% within one sigma on every market. That normal gives the chance of
# the over; it is blended with the book's own chance at PROPS_ANCHOR to
# PROPS_MODEL_W, as the rest of the sheet anchors on the market, and the
# Props record tile says whether any of it earns its keep. Props cannot be
# backtested against lines (ten credits a market a game on the history
# endpoint), so the tile is the test. All measured 19 Oct 2026 on the 2025-26
# ledger with the box lines (tools_backtest_nba_props.py).
PROPS_FORMAT = "callsheet3.props"
PROPS_MARKETS = (("pts", "player_points", "points"), ("reb", "player_rebounds", "rebounds"), ("ast", "player_assists", "assists"),
                 ("tpm", "player_threes", "threes"), ("pra", "player_points_rebounds_assists", "points + rebounds + assists"))
PROPS_SD_K = {"pts": 1.85, "reb": 1.2, "ast": 1.15, "tpm": 1.1, "pra": 1.9}      # one sigma = k x sqrt(projection), measured per market
PROPS_OUT_MIN_PER30 = 1.42                                                    # minutes added per 30 mpg of regulars out (t 36)
PROPS_OUT_RATE_PER30 = {"pts": 0.56, "reb": 0.0, "ast": 0.09, "tpm": 0.0, "pra": 0.66}   # per 36, per 30 mpg out (points t 11, assists t 6; the rest null)
PROPS_PRIOR_CAP = 1000.0
PROPS_PRIOR_SHARE = 0.5
PROPS_LAST_N = 5
PROPS_MIN_MINUTES = 60.0
PROPS_REGULAR_MPG = 24.0
PROPS_PLAYER_MIN_GAMES = 3
PROPS_ANCHOR = 4.0
PROPS_MODEL_W = 2.0
PROPS_DVP_WEIGHT = {"pts": 0.75, "reb": 0.75, "ast": 0.75, "tpm": 0.4, "pra": 0.75}   # how much of a defence's lean to carry (measured, first half to second)
PROPS_DVP_SHRINK = 20                                                         # games of this season before its table outweighs last season's
PROPS_BET_EDGE = 0.03
PROPS_BET_CHANCE = 0.55
PROPS_OUT_STATUSES = ("out", "doubtful")
HASHTAG_DVP = "https://hashtagbasketball.com/nba-defense-vs-position"
HASHTAG_CODES = {"GS": "GSW", "NY": "NYK", "NO": "NOP", "SA": "SAS", "WSH": "WAS", "PHO": "PHX", "UTAH": "UTA"}
# ESPN's box scores and rosters list a man as G, F or C (26,628 lines of 2025-26: G 12,970, F 9,644, C 3,982, a
# handful finer), so the ledger's defence table is by those three; the website's five fold into them
POS3 = {"G": "G", "PG": "G", "SG": "G", "F": "F", "SF": "F", "PF": "F", "C": "C", "G-F": "F", "F-G": "G", "F-C": "F", "C-F": "C", "GF": "F", "FC": "F"}
POS_WORD = {"G": "guards", "F": "forwards", "C": "centres"}
HTB_POS = {"G": ("PG", "SG"), "F": ("SF", "PF"), "C": ("C",)}


def _phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def props_implied(price):
    """An American price as the chance it needs."""
    p = float(price)
    return 100.0 / (p + 100.0) if p > 0 else -p / (-p + 100.0)


def props_devig(over, under):
    """The book's own chance of the over, the margin taken out."""
    a, b = props_implied(over), props_implied(under)
    return a / (a + b) if a + b > 0 else 0.5


def props_over(mu, sd, line):
    """(chance of the over, chance of a push) for a normal projection against a
    line: a .5 line cannot push; a whole line pushes on the number itself."""
    if sd <= 0:
        return (1.0 if mu > line else 0.0), 0.0
    if abs(line - round(line)) < 1e-9:
        hi, lo = _phi((line + 0.5 - mu) / sd), _phi((line - 0.5 - mu) / sd)
        return 1.0 - hi, hi - lo
    return 1.0 - _phi((line - mu) / sd), 0.0


def props_blend(pb, pm):
    """The book's chance and the model's, blended on the logit scale at the
    anchor's weight against the model's: the market stays the spine."""
    def lg(p):
        p = min(max(p, 1e-4), 1 - 1e-4)
        return math.log(p / (1 - p))
    z = (PROPS_ANCHOR * lg(pb) + PROPS_MODEL_W * lg(pm)) / (PROPS_ANCHOR + PROPS_MODEL_W)
    return 1.0 / (1.0 + math.exp(-z))


def props_name_key(name):
    """'Luka Dončić' / 'Jaren Jackson Jr.' / 'P.J. Washington' -> a key the three
    sites' spellings share: ascii, lower, no punctuation, no suffix."""
    s = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[.'`’]", "", s)
    parts = [p for p in re.split(r"[^a-z0-9]+", s) if p and p not in ("jr", "sr", "ii", "iii", "iv", "v")]
    return " ".join(parts)


def props_stat(g, mk):
    """The market's number from one game log, or None when the log predates the box lines."""
    if mk == "pts":
        return g.get("pts")
    if not g.get("full"):
        return None
    if mk == "pra":
        return (g.get("pts") or 0) + (g.get("reb") or 0) + (g.get("ast") or 0)
    return g.get(mk)


def nba_player_logs(ledger_games):
    """Every player's game log from a ledger, by ESPN id: {pid: {n, team, pos,
    g: [{d, opp, home, min, st, pts, reb, ast, tpm, full}, ...]}}, oldest first;
    team and position are the last the ledger saw him with."""
    per = {}
    for g in sorted(ledger_games or [], key=lambda g: (g.get("date") or "", g.get("id") or "")):
        for key, ab, opp, home in (("pa", g.get("away"), g.get("home"), False), ("ph", g.get("home"), g.get("away"), True)):
            for p in g.get(key) or []:
                d = nba_player_dict(p)
                e = per.setdefault(d["id"], {"n": d["n"], "team": ab, "pos": "", "g": []})
                e["n"], e["team"] = d["n"], ab
                if d.get("pos"):
                    e["pos"] = d["pos"]
                e["g"].append({"d": g.get("date"), "opp": opp, "home": home, "min": float(d["min"] or 0), "st": int(d["st"] or 0),
                               "pts": d["pts"], "reb": d["reb"], "ast": d["ast"], "tpm": d["tpm"], "full": d["full"]})
    return per


def props_rate(logs_this, logs_last, mk):
    """The player's per-minute rate on a market: this season's total over its
    minutes, with last season's rate as a prior weighted at half of last
    season's minutes (PROPS_PRIOR_CAP of them at most). None under
    PROPS_MIN_MINUTES of evidence."""
    def sums(logs):
        s = m = 0.0
        n = 0
        for g in logs or []:
            v = props_stat(g, mk)
            if v is None or g["min"] <= 0:
                continue
            s += v
            m += g["min"]
            n += 1
        return s, m, n
    s1, m1, n1 = sums(logs_this)
    s2, m2, n2 = sums(logs_last)
    prior = (s2 / m2) if m2 > 0 else None
    w = min(m2, PROPS_PRIOR_CAP) * PROPS_PRIOR_SHARE if prior is not None else 0.0
    denom = m1 + w
    if denom < PROPS_MIN_MINUTES:
        return None
    return {"rate": (s1 + (prior * w if prior is not None else 0.0)) / denom, "this": (s1 / m1) if m1 > 0 else None, "m_this": m1, "n_this": n1,
            "prior": prior, "m_last": m2, "n_last": n2, "w": w}


def props_minutes(logs_this, logs_last):
    """Minutes to project: the mean of the last PROPS_LAST_N games played this
    season, with the season mean and the starts among them beside it. Before
    he has played this season, LAST season's mean over every game he played
    (not its last five: April's minutes are rest and garbage time; Cade
    Cunningham's last five of 2025-26 averaged 23.6)."""
    this = [g for g in (logs_this or []) if g["min"] > 0]
    if this:
        recent = this[-PROPS_LAST_N:]
        return {"proj": sum(g["min"] for g in recent) / len(recent), "n": len(recent), "season": sum(g["min"] for g in this) / len(this),
                "starts": sum(1 for g in recent if g["st"]), "last_season": False}
    last = [g for g in (logs_last or []) if g["min"] > 0]
    if not last:
        return None
    return {"proj": sum(g["min"] for g in last) / len(last), "n": len(last), "season": None, "starts": sum(1 for g in last if g["st"]), "last_season": True}


def props_split(logs_this, logs_last, mk):
    """Per-36 at home and on the road, this season with last season behind it: shown, never scored."""
    out = {}
    for side in (True, False):
        s = m = 0.0
        for g in (logs_this or []) + (logs_last or []):
            v = props_stat(g, mk)
            if v is None or g["min"] <= 0 or g["home"] != side:
                continue
            s += v
            m += g["min"]
        out["home" if side else "road"] = (s / m * 36.0, m) if m > 0 else None
    return out


def parse_hashtag_dvp(text):
    """HashtagBasketball's defence-v-position page -> {(pos, tricode): {"pts":
    (allowed a game, rank), "reb": ..., "ast": ..., "tpm": ...}} from the one
    table that lists every position; the rank runs 1 (fewest allowed) to 150."""
    best = []
    for tb in re.findall(r"<table[^>]*>(.*?)</table>", text, re.S):
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S)
        if len(rows) > len(best):
            best = rows
    out, cols = {}, None
    for r in best:
        cells = [html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c))).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
        if not cells:
            continue
        if cells[0].lower().startswith("sort") or cells[0].lower() == "position":
            cols = [c.replace("Sort:", "").strip().upper() for c in cells]
            continue
        if cols is None or len(cells) != len(cols) or "TEAM" not in cols:
            continue
        team = cells[cols.index("TEAM")].split()
        if not team:
            continue
        code = team[0].upper()
        ab = espn_tricode(HASHTAG_CODES.get(code, code))
        e = {}
        for key, col in (("pts", "PTS"), ("reb", "REB"), ("ast", "AST"), ("tpm", "3PM")):
            if col not in cols:
                continue
            parts = cells[cols.index(col)].split()
            try:
                e[key] = (float(parts[0]), int(parts[1]) if len(parts) > 1 else None)
            except (ValueError, IndexError):
                continue
        if e:
            out[(cells[0].upper(), ab)] = e
    return out


def props_dvp_means(dvp):
    """The league's mean allowed per position per stat, from the table itself."""
    acc = {}
    for (pos, _ab), e in dvp.items():
        for k, (v, _r) in e.items():
            a = acc.setdefault((pos, k), [0.0, 0])
            a[0] += v
            a[1] += 1
    return {k: a[0] / a[1] for k, a in acc.items() if a[1]}


def nba_dvp_table(ledger_games, date_iso=None):
    """The ledger's own defence-v-position table: {(defence, pos3, mk): (factor,
    games)}, what each defence allowed per minute to guards, forwards and
    centres against the league's per-minute to that position, over its games
    before date_iso (every game when None). A factor of 1.08 is eight percent
    more than the league allowed."""
    acc, lg, gcount = {}, {}, {}
    for g in ledger_games or []:
        if not g.get("detail") or (date_iso and (g.get("date") or "") >= date_iso):
            continue
        for key, opp in (("pa", g.get("home")), ("ph", g.get("away"))):
            if not opp:
                continue
            gcount[opp] = gcount.get(opp, 0) + 1
            for p in g.get(key) or []:
                d = nba_player_dict(p)
                ps = POS3.get(str(d.get("pos") or "").upper())
                if not ps or not d["full"] or (d["min"] or 0) <= 0:
                    continue
                for mk in ("pts", "reb", "ast", "tpm"):
                    v = d.get(mk) or 0
                    a = acc.setdefault((opp, ps, mk), [0.0, 0.0])
                    a[0] += v
                    a[1] += d["min"]
                    l = lg.setdefault((ps, mk), [0.0, 0.0])
                    l[0] += v
                    l[1] += d["min"]
    out = {}
    for (opp, ps, mk), (s, m) in acc.items():
        l = lg[(ps, mk)]
        if m > 0 and l[1] > 0 and l[0] > 0:
            out[(opp, ps, mk)] = ((s / m) / (l[0] / l[1]), gcount.get(opp, 0))
    return out


def props_dvp_blend(this, last):
    """This season's factor shrunk toward last season's by the games behind it:
    {f, f_this, n_this, f_last, n_last} or None. `this` and `last` are (factor,
    games) or None."""
    if not this and not last:
        return None
    if this and last:
        n = this[1]
        f = (n * this[0] + PROPS_DVP_SHRINK * last[0]) / float(n + PROPS_DVP_SHRINK)
    else:
        f = (this or last)[0]
    return {"f": f, "f_this": this[0] if this else None, "n_this": this[1] if this else 0, "f_last": last[0] if last else None, "n_last": last[1] if last else 0}


def htb_line(dvp, opp_nick, opp, pos3, mk):
    """HashtagBasketball's rank for a defence against the website's positions that fold into pos3, shown beside the ledger's table."""
    parts = []
    label = dict((m, lab) for m, _a, lab in PROPS_MARKETS).get(mk, mk)
    for ps in HTB_POS.get(pos3, ()):
        e = (dvp or {}).get((ps, opp))
        if e and mk in e:
            v, rank = e[mk]
            parts.append("%.1f %s a game to %ss%s" % (v, label, ps, (" (%s of 150, 1 the fewest)" % ordinal(rank)) if rank else ""))
    return ("HashtagBasketball: %s allow %s; shown, not scored" % (opp_nick, ", ".join(parts))) if parts else None


def fetch_odds_events(sport, key):
    """The sport's upcoming events (a free call): id, commence_time, the two clubs' full names."""
    q = urllib.parse.urlencode({"apiKey": key, "dateFormat": "iso"})
    return fetch_json("%s/sports/%s/events?%s" % (ODDS_API, ODDS_SPORTS[sport], q))


def odds_event_props(doc, books):
    """Every player prop in one event document: [{name, mk, line, op, up, book,
    books: {book: [line, over, under]}}], the carded line the first book in
    `books` that posts both prices on one number (a book's first number is
    its main line; the alternates follow it in the list and are left)."""
    keymap = {api: mk for mk, api, _ in PROPS_MARKETS}
    by = {}
    for bm in (doc or {}).get("bookmakers") or []:
        bk = bm.get("key")
        for m in bm.get("markets") or []:
            mk = keymap.get(m.get("key"))
            if not mk:
                continue
            for o in m.get("outcomes") or []:
                name = str(o.get("description") or "").strip()
                side = str(o.get("name") or "").strip().lower()
                if side not in ("over", "under") or not name or o.get("point") is None:
                    continue
                slot = by.setdefault((name, mk), {}).setdefault(bk, [None, None, None])
                try:
                    pt = float(o["point"])
                except (TypeError, ValueError):
                    continue
                if slot[0] is None:
                    slot[0] = pt
                if abs(pt - slot[0]) > 1e-9:
                    continue
                try:
                    slot[1 if side == "over" else 2] = int(float(o.get("price")))
                except (TypeError, ValueError):
                    continue
    out = []
    for (name, mk), bks in by.items():
        posted = [(bk, v) for bk, v in bks.items() if v[0] is not None and v[1] is not None and v[2] is not None]
        if not posted:
            continue
        carded = None
        for bk in books:
            for b, v in posted:
                if b == bk:
                    carded = (b, v)
                    break
            if carded:
                break
        if carded is None:
            carded = posted[0]
        out.append({"name": name, "mk": mk, "line": carded[1][0], "op": carded[1][1], "up": carded[1][2], "book": carded[0],
                    "books": {b: v for b, v in posted}})
    out.sort(key=lambda x: (x["name"], x["mk"]))
    return out


def props_match_player(name, clubs, logs_this, logs_last, rosters=None):
    """The ESPN id a prop's name refers to, looked for on the two clubs first:
    the day's rosters when the game page lists them, then the ledgers' players
    whose last club is one of the two, then anyone with the name. Returns
    (pid, team, how) or (None, None, why)."""
    key = props_name_key(name)
    if not key:
        return None, None, "no name"
    for ab in clubs:
        for pid, nm in ((rosters or {}).get(ab) or {}).items():
            if props_name_key(nm) == key:
                return str(pid), ab, "roster"
    for logs in (logs_this, logs_last):
        for pid, e in (logs or {}).items():
            if e.get("team") in clubs and props_name_key(e.get("n")) == key:
                return pid, e["team"], "ledger"
    sur = key.split()[-1]
    ini = key[0]
    for logs in (logs_this, logs_last):
        hits = [(pid, e) for pid, e in (logs or {}).items() if e.get("team") in clubs and props_name_key(e.get("n")).split()[-1:] == [sur] and props_name_key(e.get("n"))[:1] == ini]
        if len(hits) == 1:
            return hits[0][0], hits[0][1]["team"], "surname"
    for logs in (logs_this, logs_last):
        hits = [(pid, e) for pid, e in (logs or {}).items() if props_name_key(e.get("n")) == key]
        if len(hits) == 1:
            return hits[0][0], None, "name only, club unknown"
    return None, None, "not in the ledgers"


def props_out_minutes(ab, injuries, logs_this, logs_last):
    """The minutes a game of the club's listed-out players (Out or Doubtful on
    ESPN), each at his own mpg this season after PROPS_PLAYER_MIN_GAMES games,
    else last season's: (total mpg of those at PROPS_REGULAR_MPG or more,
    [(name, mpg, status)], [(name, status)] of the questionable)."""
    regular, listed, maybe = 0.0, [], []
    for inj in (injuries or {}).get(ab) or []:
        st = str(inj.get("st") or "")
        pid = str(inj.get("id") or "")
        e1, e2 = (logs_this or {}).get(pid), (logs_last or {}).get(pid)
        mpg = None
        if e1 and len(e1["g"]) >= PROPS_PLAYER_MIN_GAMES:
            mpg = sum(g["min"] for g in e1["g"]) / len(e1["g"])
        elif e2 and e2["g"]:
            mpg = sum(g["min"] for g in e2["g"]) / len(e2["g"])
        elif e1 and e1["g"]:
            mpg = sum(g["min"] for g in e1["g"]) / len(e1["g"])
        if st.lower() in PROPS_OUT_STATUSES:
            listed.append((inj.get("n"), mpg, st))
            if mpg is not None and mpg >= PROPS_REGULAR_MPG:
                regular += mpg
        elif st:
            maybe.append((inj.get("n"), st))
    return regular, listed, maybe


def props_project(prop, logs_this, logs_last, ctx):
    """One prop's projection: {proj, sd, pm, pb, p, push, side, chance, price,
    need, edge, band, why[]} or None with the reason. ctx carries out_mpg and
    out_names for his club, pace and league_pace, dvp as (allowed, rank, league
    mean) for his position against tonight's defence, home, and his own status."""
    mk, line = prop["mk"], float(prop["line"])
    label = dict((m, lab) for m, _a, lab in PROPS_MARKETS)[mk]
    why = []
    if ctx.get("self_out"):
        return None, ["listed %s on ESPN: no projection, the book will void or pull the line" % ctx["self_out"]]
    r = props_rate(logs_this, logs_last, mk)
    m = props_minutes(logs_this, logs_last)
    if not r or not m:
        return None, ["no history to project from (under %d minutes with the stat in the ledgers)" % int(PROPS_MIN_MINUTES)]
    rate36 = r["rate"] * 36.0
    if r["this"] is not None and r["prior"] is not None:
        why.append("%.1f %s per 36 this season (%d games, %d minutes), blended with last season's %.1f (%d of %d minutes, at half): %.1f per 36" % (
            r["this"] * 36, label, r["n_this"], int(r["m_this"]), r["prior"] * 36, int(round(r["w"] / PROPS_PRIOR_SHARE)), int(r["m_last"]), rate36))
    elif r["this"] is not None:
        why.append("%.1f %s per 36 this season (%d games, %d minutes); no last season to blend" % (rate36, label, r["n_this"], int(r["m_this"])))
    else:
        why.append("%.1f %s per 36 LAST season (%d games, %d minutes): nothing this season yet" % (rate36, label, r["n_last"], int(r["m_last"])))
    mins = m["proj"]
    if m["last_season"]:
        why.append("%.1f minutes projected: last season's mean over %d game%s (nothing this season yet), %d of them starts" % (mins, m["n"], "" if m["n"] == 1 else "s", m["starts"]))
    else:
        why.append("%.1f minutes projected: his last %d game%s%s, %d of them starts" % (
            mins, m["n"], "" if m["n"] == 1 else "s", (" (season %.1f)" % m["season"]) if m["season"] else "", m["starts"]))
    out_mpg = float(ctx.get("out_mpg") or 0.0)
    rate = r["rate"]
    if out_mpg > 0:
        dmin = PROPS_OUT_MIN_PER30 * out_mpg / 30.0
        drate = PROPS_OUT_RATE_PER30[mk] / 36.0 * out_mpg / 30.0
        mins += dmin
        rate += drate
        why.append("%s out (%.0f minutes a game between them): +%.1f minutes and +%.2f %s per 36, the pooled rule, scored" % (
            ", ".join(n for n, _mpg, _st in (ctx.get("out_names") or [])[:4]) or "regulars", out_mpg, dmin, drate * 36, label))
    for nm, st in (ctx.get("maybe") or [])[:3]:
        why.append("%s is %s: not counted as out" % (nm, st))
    f_pace = 1.0
    if ctx.get("pace") and ctx.get("league_pace"):
        f_pace = float(ctx["pace"]) / float(ctx["league_pace"])
        why.append("pace %.1f against the league's %.1f: x%.3f" % (ctx["pace"], ctx["league_pace"], f_pace))
    f_dvp = 1.0
    dv = ctx.get("dvp")
    if dv and dv.get("f"):
        wgt = PROPS_DVP_WEIGHT[mk]
        f_dvp = 1.0 + wgt * (dv["f"] - 1.0)
        detail = []
        if dv.get("f_this") is not None:
            detail.append("this season %.2f over %d game%s" % (dv["f_this"], dv["n_this"], "" if dv["n_this"] == 1 else "s"))
        if dv.get("f_last") is not None:
            detail.append("last season %.2f" % dv["f_last"])
        why.append("%s allow %.2fx the league's %s per minute to %s (%s): x%.3f at %.2f weight, measured" % (
            ctx.get("opp_nick") or "they", dv["f"], "points" if mk == "pra" else label, POS_WORD.get(ctx.get("pos"), "that position"), ", ".join(detail), f_dvp, wgt))
    if ctx.get("htb"):
        why.append(ctx["htb"])
    sp = props_split(logs_this, logs_last, mk)
    if sp.get("home") and sp.get("road"):
        why.append("home %.1f / road %.1f per 36 over %d minutes: shown, not scored (a player's own split did not persist from one half of 2025-26 to the other, r 0.08)%s" % (
            sp["home"][0], sp["road"][0], int(sp["home"][1] + sp["road"][1]), "; tonight at home" if ctx.get("home") else "; tonight on the road"))
    mu = rate * mins * f_pace * f_dvp
    sd = PROPS_SD_K[mk] * math.sqrt(max(mu, 1.0))
    pm, push = props_over(mu, sd, line)
    pm_c = pm / (1.0 - push) if push < 1.0 else 0.5
    pb = props_devig(prop["op"], prop["up"])
    p = props_blend(pb, pm_c)
    side = "OVER" if p >= 0.5 else "UNDER"
    chance = p if side == "OVER" else 1.0 - p
    price = prop["op"] if side == "OVER" else prop["up"]
    need = props_implied(price)
    edge = chance - need
    band = "BET" if (edge >= PROPS_BET_EDGE and chance >= PROPS_BET_CHANCE) else ("LEAN" if edge > 0 else "no edge")
    why.append("projected %.1f against %s %.1f, one sigma %.1f: the over %.1f%% by the projection, %.1f%% by the book's prices; blended %.1f%% at %.0f to %.0f" % (
        mu, label, line, sd, pm * 100, pb * 100, p * 100, PROPS_ANCHOR, PROPS_MODEL_W))
    return {"proj": round(mu, 2), "sd": round(sd, 2), "pm": round(pm, 4), "pb": round(pb, 4), "p": round(p, 4), "push": round(push, 4),
            "side": side, "chance": round(chance, 4), "price": price, "need": round(need, 4), "edge": round(edge, 4), "band": band,
            "mins": round(mins, 1), "rate36": round(rate * 36.0, 2), "why": why}, why


def nba_props_box(entry):
    """A graded game's box for the Props tab, by ESPN id: [name, minutes, points, rebounds, assists, threes]."""
    box = {}
    for key in ("pa", "ph"):
        for p in entry.get(key) or []:
            d = nba_player_dict(p)
            if d["id"]:
                box[d["id"]] = [d["n"], d["min"], d["pts"], d["reb"], d["ast"], d["tpm"]]
    return box


ESPN_TEAM_CODE = {v: k for k, v in ESPN_TRICODE.items()}   # the league's tricode -> ESPN's own (GSW -> GS)


def espn_team_roster(ab):
    """A club's roster from ESPN's team page, {espn id: (name, position)}:
    the authority on who is on which club today, since the game page lists
    nobody before tip-off (seen 19 Oct 2026) and the ledger's last club is a
    summer trade behind."""
    doc = espn_json("/teams/%s/roster" % ESPN_TEAM_CODE.get(ab, ab))
    out = {}
    for a in (doc or {}).get("athletes") or []:
        if a.get("id"):
            out[str(a["id"])] = (a.get("displayName") or a.get("fullName") or str(a["id"]), str(((a.get("position") or {}).get("abbreviation")) or ""))
    return out


def make_nba_props(date_iso, out_dir, log):
    """The day's player props with the slate's projection beside each, for The
    Super Model's Props tab: nba-props-DATE.json. The lines come from The Odds
    API (a credit a market a game), the history from the ledgers, who is out
    from ESPN, the defence table from HashtagBasketball."""
    key = odds_key(out_dir)
    season = nba_season_id(date_iso)
    led = load_nba_ledger(nba_ledger_path(out_dir, season))
    prior = load_nba_ledger(nba_ledger_path(out_dir, nba_prev_season(season)))
    logs_this = nba_player_logs(led["games"] if led else [])
    logs_last = nba_player_logs(prior["games"] if prior else [])
    full_this = sum(1 for e in logs_this.values() for g in e["g"] if g["full"])
    full_last = sum(1 for e in logs_last.values() for g in e["g"] if g["full"])
    log("Ledgers: %s %d games (%d player lines with the box stats), %s %d games (%d with)." % (
        season, len(led["games"]) if led else 0, full_this, nba_prev_season(season), len(prior["games"]) if prior else 0, full_last))
    if prior and not full_last:
        log("  Last season's ledger has no box stats yet: run the NBA ledger for %s once (Run NBA ledger.bat) and rebounds, assists and threes get a history." % nba_prev_season(season))
    tables, league = nba_team_tables(led["games"] if led else [], date_iso)
    ptables, pleague = nba_team_tables(prior["games"] if prior else [], "9999-12-31")
    league_pace = (league or {}).get("pace") or (pleague or {}).get("pace")

    def club_pace(ab):
        t = tables.get(ab)
        if t and t["n"] >= NBA_MIN_TEAM_GAMES:
            return t["pace"]
        t = ptables.get(ab)
        return t["pace"] if t else None
    injuries = {}
    try:
        injuries = nba_injuries()
        log("Injury report: %d clubs, %d players listed." % (len(injuries), sum(len(v) for v in injuries.values())))
    except Exception as e:  # noqa: BLE001
        log("Could not read the injury report (%s): nobody counted as out." % e)
    dvp_this = nba_dvp_table(led["games"] if led else [], date_iso)
    dvp_last = nba_dvp_table(prior["games"] if prior else [])
    log("Defence v position from the ledgers: %d defence-position-market factors this season, %d last season (guards, forwards, centres)." % (len(dvp_this), len(dvp_last)))
    htb = {}
    try:
        htb = parse_hashtag_dvp(fetch_text(HASHTAG_DVP))
        log("HashtagBasketball's table: %d position-club rows, shown beside the ledger's factor." % len(htb))
    except Exception as e:  # noqa: BLE001
        log("Could not read HashtagBasketball's table (%s): the ledger's factor stands alone." % e)
    day = {}
    try:
        for g in nba_day_games(date_iso):
            day[(g["away"], g["home"])] = g
        log("ESPN scoreboard: %d game%s on %s." % (len(day), "" if len(day) == 1 else "s", date_iso))
    except Exception as e:  # noqa: BLE001
        log("Could not read ESPN's scoreboard (%s): no rosters, spreads or totals beside the props." % e)
    events = [ev for ev in fetch_odds_events("NBA", key) if us_game_date(ev.get("commence_time") or "") == date_iso]
    log("The Odds API lists %d event%s on %s." % (len(events), "" if len(events) == 1 else "s", date_iso))
    if not events:
        log("Nothing to project for %s. The run is for today unless told otherwise: python slate.py nba-props --date 2026-10-21 (or add --date to the bat file's click)." % date_iso)
    markets = ",".join(api for _mk, api, _lab in PROPS_MARKETS)
    games, credits_used, roster_cache = [], 0, {}
    for ev in events:
        aab, hab = nba_nick_tricode(ev.get("away_team")), nba_nick_tricode(ev.get("home_team"))
        away, home = NBA_NICK.get(aab, ev.get("away_team")), NBA_NICK.get(hab, ev.get("home_team"))
        if not aab or not hab:
            log("%s @ %s: could not place the clubs; skipped" % (ev.get("away_team"), ev.get("home_team")))
            continue
        try:
            doc = fetch_odds_event("NBA", ev["id"], key, ODDS_BOOKS, markets=markets)
        except Exception as e:  # noqa: BLE001
            log("%s @ %s: no props from the API (%s)" % (away, home, e))
            continue
        used, left = odds_credits()
        credits_used += used or 0
        props = odds_event_props(doc, ODDS_BOOKS)
        g = day.get((aab, hab)) or {}
        rosters, roster_pos = {}, {}
        for ab in (aab, hab):
            try:
                if ab not in roster_cache:
                    roster_cache[ab] = espn_team_roster(ab)
                rosters[ab] = {pid: nm for pid, (nm, _pos) in roster_cache[ab].items()}
                roster_pos.update({pid: pos for pid, (_nm, pos) in roster_cache[ab].items()})
            except Exception as e:  # noqa: BLE001
                log("  %s: no roster from ESPN's team page (%s); the ledgers place its players" % (NBA_NICK.get(ab, ab), e))
        pace_a, pace_h = club_pace(aab), club_pace(hab)
        pace = (pace_a + pace_h) / 2.0 if pace_a and pace_h else (pace_a or pace_h)
        out = {}
        for ab in (aab, hab):
            out[ab] = props_out_minutes(ab, injuries, logs_this, logs_last)
        odds = g.get("odds") or {}
        row = {"gid": g.get("id"), "away": away, "home": home, "aab": aab, "hab": hab, "tip": g.get("t") or ev.get("commence_time"),
               "spread": odds.get("sp"), "total": odds.get("total"), "pace": round(pace, 1) if pace else None, "league_pace": round(league_pace, 1) if league_pace else None,
               "out": {ab: [[n, round(mpg, 1) if mpg is not None else None, st] for n, mpg, st in out[ab][1]] for ab in (aab, hab)},
               "props": [], "unmatched": []}
        log("%s @ %s: %d props%s%s" % (away, home, len(props), (" · pace %.1f" % pace) if pace else "",
                                       "".join(" · %s out: %s" % (NBA_NICK.get(ab, ab), ", ".join("%s (%s)" % (n, ("%.0f mpg" % mpg) if mpg is not None else "no line") for n, mpg, _s in out[ab][1])) for ab in (aab, hab) if out[ab][1])))
        for pr in props:
            pid, team, how = props_match_player(pr["name"], (aab, hab), logs_this, logs_last, rosters)
            if not pid or not team:
                row["unmatched"].append([pr["name"], pr["mk"], pr["line"], how])
                continue
            opp = hab if team == aab else aab
            e1, e2 = logs_this.get(pid) or {}, logs_last.get(pid) or {}
            pos = POS3.get(str(e1.get("pos") or e2.get("pos") or roster_pos.get(pid) or "").upper(), "")
            self_out = ""
            for n, mpg, st in out[team][1]:
                if props_name_key(n) == props_name_key(pr["name"]):
                    self_out = st
            dmk = "pts" if pr["mk"] == "pra" else pr["mk"]
            dv = props_dvp_blend(dvp_this.get((opp, pos, dmk)), dvp_last.get((opp, pos, dmk))) if pos else None
            ctx = {"out_mpg": out[team][0], "out_names": [(n, mpg, st) for n, mpg, st in out[team][1] if mpg is not None and mpg >= PROPS_REGULAR_MPG],
                   "maybe": out[team][2], "pace": pace, "league_pace": league_pace, "home": team == hab, "pos": pos, "opp_nick": NBA_NICK.get(opp, opp),
                   "dvp": dv, "htb": htb_line(htb, NBA_NICK.get(opp, opp), opp, pos, dmk) if pos else None, "self_out": self_out}
            proj, why = props_project(pr, e1.get("g"), e2.get("g"), ctx)
            recent = [[g_["d"], g_["opp"], 1 if g_["home"] else 0, g_["min"], props_stat(g_, pr["mk"])] for g_ in (e1.get("g") or e2.get("g") or [])[-10:]]
            item = {"pid": pid, "name": e1.get("n") or e2.get("n") or pr["name"], "team": team, "opp": opp, "home": team == hab, "pos": pos,
                    "mk": pr["mk"], "line": pr["line"], "op": pr["op"], "up": pr["up"], "book": pr["book"], "books": pr["books"], "log": recent, "why": why}
            if proj:
                item.update(proj)
            row["props"].append(item)
        row["props"].sort(key=lambda x: (-(x.get("edge") if x.get("edge") is not None else -9), x["name"], x["mk"]))
        projected = sum(1 for x in row["props"] if x.get("p") is not None)
        log("  %d placed and projected, %d placed without a projection, %d not placed%s" % (
            projected, len(row["props"]) - projected, len(row["unmatched"]), (" (credits: %s used, %s left)" % (used, left)) if used is not None else ""))
        for x in row["props"][:3]:
            if x.get("p") is not None:
                log("    %s %s %s %s at %+d: %.1f%% (needs %.1f%%) %s · proj %.1f" % (x["name"], x["side"], x["line"], dict((m, lab) for m, _a, lab in PROPS_MARKETS)[x["mk"]], x["price"], x["chance"] * 100, x["need"] * 100, x["band"], x["proj"]))
        games.append(row)
    doc = {"format": PROPS_FORMAT, "version": 1, "date": date_iso, "generated": now_utc(), "source": "slate.py nba-props: The Odds API, the ledgers, ESPN, HashtagBasketball",
           "credits": credits_used, "games": games,
           "method": {"anchor": PROPS_ANCHOR, "model": PROPS_MODEL_W, "sd_k": PROPS_SD_K, "out_min_per30": PROPS_OUT_MIN_PER30, "out_rate_per30": PROPS_OUT_RATE_PER30, "dvp_weight": PROPS_DVP_WEIGHT, "dvp_shrink": PROPS_DVP_SHRINK}}
    path = os.path.join(out_dir, "nba-props-%s.json" % date_iso)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    n = sum(len(g["props"]) for g in games)
    log("Wrote %s: %d props on %d game%s, %d credits. Open The Super Model -> NBA PROPS -> Load props." % (path, n, len(games), "" if len(games) == 1 else "s", credits_used))
    return path


# ---- expected goals, from MoneyPuck's team file ------------------------------
# https://moneypuck.com/data.htm -- "Team" season summary, one row per club per
# situation. The 'all' row's xGoalsFor and xGoalsAgainst over games_played are
# the two figures the sheet scores (totals/nhl.py, "Expected goals"), against
# the league mean of the SAME table, which the slate writes beside them. Read
# against the user's download of 6 Oct 2026. A teams.csv saved in the folder
# is the fallback when the site cannot be reached.
MONEYPUCK_TEAMS = "https://moneypuck.com/moneypuck/playerData/seasonSummary/%s/regular/teams.csv"


def parse_moneypuck_teams(text):
    """{club: {gp, xgf, xga, sf, gf}} per game, and the league mean xG per
    team-game, from the 'all' rows."""
    rows = list(csv.DictReader(io.StringIO(text)))
    rates, gp_t, xgf_t, xga_t = {}, 0.0, 0.0, 0.0
    for r in rows:
        if (r.get("situation") or "").strip() != "all":
            continue
        try:
            gp = float(r.get("games_played") or 0)
            xgf, xga = float(r["xGoalsFor"]), float(r["xGoalsAgainst"])
        except (TypeError, ValueError, KeyError):
            continue
        if gp <= 0:
            continue
        name = (r.get("name") or r.get("team") or "").strip().upper()
        rates[name] = {"gp": int(gp), "xgf": xgf / gp, "xga": xga / gp,
                       "sf": (float(r.get("shotsOnGoalFor") or 0) / gp), "gf": (float(r.get("goalsFor") or 0) / gp)}
        gp_t += gp
        xgf_t += xgf
        xga_t += xga
    lg = ((xgf_t + xga_t) / (2.0 * gp_t)) if gp_t > 0 else None
    return rates, lg


def moneypuck_teams(season_id, out_dir, log):
    """(rates, league xG per team-game, where it came from) or (None, None, why)."""
    year = str(season_id)[:4]
    text, src = None, ""
    try:
        text = fetch_text(MONEYPUCK_TEAMS % year)
        src = "moneypuck.com"
    except Exception as e:  # noqa: BLE001
        local = os.path.join(out_dir, "teams.csv")
        if os.path.exists(local):
            with open(local, "r", encoding="utf-8") as f:
                text = f.read()
            src = "teams.csv in the folder (the site could not be reached: %s)" % e
        else:
            return None, None, "could not fetch MoneyPuck (%s) and there is no teams.csv in the folder" % e
    try:
        rates, lg = parse_moneypuck_teams(text)
    except Exception as e:  # noqa: BLE001
        return None, None, "could not read the MoneyPuck team file (%s)" % e
    if not rates:
        return None, None, "the MoneyPuck team file had no 'all' rows for %s" % year
    return rates, lg, src


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
    led = load_ledger(ledger_path(out_dir, season_id))
    ledger = led["games"] if led else None
    xg_rates, xg_lg, xg_src = moneypuck_teams(season_id, out_dir, log)
    if xg_rates:
        log("Expected goals: %d clubs from %s; league %.2f xG per team-game." % (len(xg_rates), xg_src, xg_lg))
    else:
        log("Expected goals: %s. The xG boxes stay blank." % xg_src)
    if led:
        log("League ledger: %d finals through %s." % (len(ledger), led.get("through")))
    else:
        log("No league ledger in %s: run 'python slate.py nhl-ledger' (Run NHL ledger.bat) and the first-period form fills." % out_dir)
    tables = nhl_ledger_tables(ledger, date_iso) if ledger else {}
    gsum = {}
    try:
        gsum = nhl_goalie_summary(season_id)
        log("Goalie report: %d goalies, %d with %d+ shots (the context card ranks the named starter among them)." % (len(gsum), sum(1 for x in gsum.values() if x["shots"] >= CTX_GOALIE_SHOTS), CTX_GOALIE_SHOTS))
    except Exception as e:  # noqa: BLE001
        log("Could not fetch the goalie report (%s); the context card has no goalie line." % e)
    lineups = nhl_lineups(date_iso, log) if games else {}
    rows = []
    for g in games:
        try:
            rows.append(build_nhl_game(g, date_iso, season_id, summary, log, ledger, (xg_rates, xg_lg) if xg_rates else None, gsum, tables, lineups))
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
                c = odds_close_for(odds_log_path(out_dir), "NHL", date_iso, r["away"], r["home"])
                if c:
                    r["close"] = c     # the last number the odds run saw before the game
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


# ---- the odds feed: The Odds API --------------------------------------------
# https://the-odds-api.com -- a paid key, read from odds_key.txt beside this
# script (one line) or the ODDS_API_KEY environment variable. One call a
# sport for the main markets (total, moneyline, spread) across the books the
# user shops, one call a game for the period market (first five, first
# period, first half). Fills the LINE boxes the sheet never filled before
# (12 Oct 2026, at the user's request): the main total and its prices, the
# moneyline, the run or puck line, the period total and its prices; the
# OPENER as the first number this script saw for the game (odds-log.json);
# every book's price on each side for the sheet's best-price chip; and, on
# the grade run, the CLOSE as the last number it saw before the game.
#
# The rest of the subscription, wired 13 Oct 2026 ("make sure we aren't
# leaving anything on the table"): PINNACLE, the sharp book, read beside the
# carded line and never carded itself (the sheet shows the gap; it scores
# nothing until the log has measured it); ALTERNATE TOTALS, every number the
# books post with its price, so the sheet can price the under at 6.5 and the
# over at 5.5 with the Line box left alone; TEAM TOTALS, each side's own
# number, shown as the book's split; the CREDITS the run cost and what is
# left, read from the response headers; and the HISTORY mode, snapshots of
# past seasons' lines for the backtest's openers (10 credits a market a
# snapshot, paid plans only, so it asks before it pulls and keeps a floor).
ODDS_API = "https://api.the-odds-api.com/v4"
ODDS_SPORTS = {"MLB": "baseball_mlb", "NHL": "icehockey_nhl", "NBA": "basketball_nba"}
ODDS_PERIOD = {"MLB": "totals_1st_5_innings", "NHL": "totals_p1", "NBA": "totals_h1"}
ODDS_PERIOD_KEYS = {"MLB": ("f5line", "f5op", "f5up"), "NHL": ("p1line", "p1op", "p1up"), "NBA": ("h1line", "h1op", "h1up")}
ODDS_SPREAD_KEYS = {"MLB": ("rl", "rlh", "rla"), "NHL": ("pl", "plh", "pla"), "NBA": ("sp", "sph", "spa")}
ODDS_EXTRA = ["alternate_totals", "team_totals"]     # per-game markets fetched beside the period total
ODDS_BOOKS = ["fanatics", "betmgm", "draftkings", "fanduel", "caesars", "espnbet", "betrivers", "bovada", "pinnacle"]
ODDS_SHARP = "pinnacle"                               # read beside the carded line, never carded
ODDS_LOG = "odds-log.json"
ODDS_HISTORY_FORMAT = "callsheet.odds-history"
ODDS_HISTORY_TIMES = ("16:00", "23:30")              # UTC: noon Eastern (the opener) and 7:30 pm Eastern (the close for the main slate)
ODDS_HISTORY_TIMES_NBA = ("22:30",)                  # UTC: one snapshot at 6:30 pm Eastern (5:30 in winter), before the 7 pm tips; the moneylines for the upset test (16 Oct 2026)
ODDS_HISTORY_MARKETS = {"NBA": "h2h"}                # the NBA pull wants the moneyline alone: KillerSports already gave the spreads and totals at the close
ODDS_HISTORY_KEEP = 3000                             # credits a history pull leaves untouched for the nightly runs
ODDS_HISTORY_COST = 10                               # credits a market a snapshot, by the API's price list
ODDS_TWO_WORD = {"Blue Jackets", "Red Wings", "Maple Leafs", "Golden Knights", "Red Sox", "White Sox", "Blue Jays", "Trail Blazers"}


def odds_key(out_dir="."):
    k = os.environ.get("ODDS_API_KEY", "").strip()
    if k:
        return k
    for folder in (out_dir, HERE):
        p = os.path.join(folder, "odds_key.txt")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                k = f.read().strip()
            if k:
                return k
    raise RuntimeError("no Odds API key: put it in odds_key.txt beside slate.py (one line) or set ODDS_API_KEY")


def odds_nick(full):
    """'Florida Panthers' -> 'Panthers'; two-word nicknames kept whole; Utah's club -> Mammoth."""
    s = str(full or "").strip()
    if s.startswith("Utah") and "Jazz" not in s:   # the hockey club; the Jazz are the Jazz
        return "Mammoth"
    words = s.split()
    if len(words) >= 2 and " ".join(words[-2:]) in ODDS_TWO_WORD:
        return " ".join(words[-2:])
    return words[-1] if words else s


def us_game_date(iso_utc):
    """The US game date of a UTC start time: Eastern time, daylight saving by the US rule."""
    t = dt.datetime.strptime(str(iso_utc)[:19], "%Y-%m-%dT%H:%M:%S")
    y = t.year
    mar = dt.date(y, 3, 8)
    mar += dt.timedelta(days=(6 - mar.weekday()) % 7)        # the second Sunday of March
    nov = dt.date(y, 11, 1)
    nov += dt.timedelta(days=(6 - nov.weekday()) % 7)        # the first Sunday of November
    summer = dt.datetime.combine(mar, dt.time(7)) <= t < dt.datetime.combine(nov, dt.time(6))   # 2am local, in UTC
    return (t - dt.timedelta(hours=4 if summer else 5)).date().isoformat()


def fetch_odds(sport, key, books):
    q = urllib.parse.urlencode({"apiKey": key, "markets": "h2h,spreads,totals", "oddsFormat": "american",
                                "dateFormat": "iso", "bookmakers": ",".join(books)})
    return fetch_json("%s/sports/%s/odds/?%s" % (ODDS_API, ODDS_SPORTS[sport], q))


def fetch_odds_event(sport, event_id, key, books, markets=None):
    """One game's extra markets: the period total, the alternate totals and the
    team totals (a credit a market the books actually price)."""
    mk = ",".join([ODDS_PERIOD[sport]] + ODDS_EXTRA) if markets is None else markets
    q = urllib.parse.urlencode({"apiKey": key, "markets": mk, "oddsFormat": "american",
                                "dateFormat": "iso", "bookmakers": ",".join(books)})
    return fetch_json("%s/sports/%s/events/%s/odds?%s" % (ODDS_API, ODDS_SPORTS[sport], event_id, q))


def fetch_odds_history(sport, key, books, at_iso, markets="totals"):
    """The books' lines as they stood at a past moment: the closest snapshot at
    or before at_iso (five-minute steps). Paid plans only; ten credits a market."""
    q = urllib.parse.urlencode({"apiKey": key, "markets": markets, "oddsFormat": "american",
                                "dateFormat": "iso", "bookmakers": ",".join(books), "date": at_iso})
    return fetch_json("%s/historical/sports/%s/odds?%s" % (ODDS_API, ODDS_SPORTS[sport], q))


def odds_credits():
    """(credits the last call cost, credits left this month), from the response headers."""
    def num(k):
        try:
            return int(float(_last_headers.get(k, "")))
        except (TypeError, ValueError):
            return None
    return num("x-requests-last"), num("x-requests-remaining")


def odds_rows(ev, market):
    """Every outcome of a list-style market (alternate totals, team totals) across
    the books: [(book, name, description, price, point), ...]."""
    out = []
    for bk in (ev or {}).get("bookmakers") or []:
        for m in bk.get("markets") or []:
            if m.get("key") != market:
                continue
            for o in m.get("outcomes") or []:
                try:
                    out.append((bk.get("key"), str(o.get("name")), str(o.get("description") or ""),
                                int(round(float(o.get("price")))), float(o["point"]) if o.get("point") is not None else None))
                except (TypeError, ValueError, KeyError):
                    continue
    return out


def _imp(price):
    price = float(price)
    return 100.0 / (price + 100.0) if price > 0 else -price / (-price + 100.0)


def odds_main_line(rows, books):
    """The MAIN number of a market from every book's postings (odds_rows): the
    point most books post both sides of, ties to the most evenly priced, and
    that point's prices at the first of `books` that posts it. A guard against
    a book listing an alternate as its line: on 13 Oct 2026 BetMGM's
    first-period total came through as 2.5 at +240/-325 while five books had
    1.5, the carded book had no period line, and the sheet's first period was
    the alternate on all sixteen games. Returns (point, over, under, book)."""
    by = {}
    for b, name, _desc, price, point in rows:
        if point is None or name not in ("Over", "Under"):
            continue
        by.setdefault(point, {}).setdefault(b, {})[name] = price
    cands = []
    for point, bb in by.items():
        full = {b: v for b, v in bb.items() if "Over" in v and "Under" in v}
        if full:
            even = min(abs(_imp(v["Over"]) - _imp(v["Under"])) for v in full.values())
            cands.append((-len(full), even, point, full))
    if not cands:
        return None
    cands.sort(key=lambda c: (c[0], c[1], c[2]))
    _n, _even, point, full = cands[0]
    for b in books:
        if b in full:
            return (point, full[b]["Over"], full[b]["Under"], b)
    b = sorted(full)[0]
    return (point, full[b]["Over"], full[b]["Under"], b)


def odds_markets(ev):
    """{book: {market key: {outcome name: (price, point)}}} for one event document."""
    out = {}
    for bk in (ev or {}).get("bookmakers") or []:
        mk = {}
        for m in bk.get("markets") or []:
            oc = {}
            for o in m.get("outcomes") or []:
                try:
                    oc[str(o.get("name"))] = (int(round(float(o.get("price")))),
                                              float(o["point"]) if o.get("point") is not None else None)
                except (TypeError, ValueError):
                    continue
            mk[m.get("key")] = oc
        out[bk.get("key")] = mk
    return out


def odds_game(ev, sport, books, extra=None):
    """One event -> the sheet's line boxes from the first of the user's books that
    prices it (the sharp book never carded), the sharp book's numbers beside it,
    and every book's price on each side (the shop) as JSON: the main total, the
    moneyline, the spread, the period total, the alternate totals, the team totals."""
    full_home, full_away = ev.get("home_team"), ev.get("away_team")
    g = {"sport": sport, "gdate": us_game_date(ev.get("commence_time") or "1970-01-01T00:00:00Z"),
         "away": odds_nick(full_away), "home": odds_nick(full_home), "eventId": ev.get("id"),
         "first_utc": ev.get("commence_time"), "book": "", "inputs": {}, "notes": []}
    seen = odds_markets(ev)
    retail = [b for b in books if b != ODDS_SHARP] or list(books)
    book = (next((b for b in retail if b in seen and "totals" in seen[b]), None) or next((b for b in retail if b in seen), None)
            or next((b for b in books if b in seen), None))
    if not book:
        g["notes"].append("No book in the list has priced this game yet.")
        return g
    g["book"] = book
    i, mk = g["inputs"], seen[book]
    t = mk.get("totals") or {}
    if "Over" in t and "Under" in t and t["Over"][1] is not None:
        i["line"] = fmt(t["Over"][1], 1)
        i["op"], i["up"] = str(t["Over"][0]), str(t["Under"][0])
    h2h = mk.get("h2h") or {}
    if full_home in h2h and full_away in h2h:
        i["hml"], i["aml"] = str(h2h[full_home][0]), str(h2h[full_away][0])
    sp = mk.get("spreads") or {}
    if full_home in sp and full_away in sp and sp[full_home][1] is not None:
        k0, k1, k2 = ODDS_SPREAD_KEYS[sport]
        i[k0], i[k1], i[k2] = fmt(sp[full_home][1], 1), str(sp[full_home][0]), str(sp[full_away][0])
    # the sharp book, beside the carded line: shown on the sheet, scored nowhere
    sh = seen.get(ODDS_SHARP) if ODDS_SHARP != book else None
    if sh:
        st, s2 = sh.get("totals") or {}, sh.get("h2h") or {}
        sharp = {"book": ODDS_SHARP}
        if "Over" in st and "Under" in st and st["Over"][1] is not None:
            sharp.update({"line": st["Over"][1], "op": st["Over"][0], "up": st["Under"][0]})
        if full_home in s2 and full_away in s2:
            sharp.update({"hml": s2[full_home][0], "aml": s2[full_away][0]})
        if len(sharp) > 1:
            i["sharp"] = json.dumps(sharp, separators=(",", ":"))
            if sharp.get("line") is not None and i.get("line") and abs(sharp["line"] - float(i["line"])) > 1e-9:
                g["notes"].append("Pinnacle has the total at %s (%s/%s) against the carded %s: the sharp line sits %s. Shown, not scored." % (
                    fmt(sharp["line"], 1), sharp["op"], sharp["up"], i["line"], "higher" if sharp["line"] > float(i["line"]) else "lower"))
    # the period total: the number most books post, at the carded book when it posts it,
    # else the first retail book that does (13 Oct 2026: never one book's alternate again)
    pkey = ODDS_PERIOD[sport]
    prow = odds_rows(extra, pkey)
    pm = odds_main_line(prow, [book] + retail)
    if pm:
        k0, k1, k2 = ODDS_PERIOD_KEYS[sport]
        i[k0], i[k1], i[k2] = fmt(pm[0], 1), str(pm[1]), str(pm[2])
        if pm[3] != book:
            g["notes"].append("The period line is %s's, the number most books post (%s at %s/%s); the carded book posts no period line." % (pm[3], fmt(pm[0], 1), pm[1], pm[2]))
    shop = {}
    for b, mks in seen.items():
        tt = mks.get("totals") or {}
        for side in ("Over", "Under"):
            if side in tt and tt[side][1] is not None:
                shop.setdefault("total", {}).setdefault(side.upper(), []).append([b, tt[side][0], tt[side][1]])
        hh = mks.get("h2h") or {}
        for side, nm in (("HOME", full_home), ("AWAY", full_away)):
            if nm in hh:
                shop.setdefault("ml", {}).setdefault(side, []).append([b, hh[nm][0], None])
        ss = mks.get("spreads") or {}
        for side, nm in (("HOME", full_home), ("AWAY", full_away)):
            if nm in ss and ss[nm][1] is not None:
                shop.setdefault("spread", {}).setdefault(side, []).append([b, ss[nm][0], ss[nm][1]])
    for b, name, _desc, price, point in prow:    # every book's period postings, every number, for the shop
        if name in ("Over", "Under") and point is not None:
            shop.setdefault("period", {}).setdefault(name.upper(), []).append([b, price, point])
    # every number the books post on the total, with its price, and each side's own total
    for b, name, _desc, price, point in odds_rows(extra, "alternate_totals"):
        if name in ("Over", "Under") and point is not None:
            shop.setdefault("alt", {}).setdefault(name.upper(), []).append([b, price, point])
    for b, name, desc, price, point in odds_rows(extra, "team_totals"):
        side = "HOME" if desc == full_home else "AWAY" if desc == full_away else None
        if side and name in ("Over", "Under") and point is not None:
            shop.setdefault("team", {}).setdefault(side, {}).setdefault(name.upper(), []).append([b, price, point])
    if shop:
        shop["book"] = book     # the carded book, so the sheet's split reads the same book
        i["odds"] = json.dumps(shop, separators=(",", ":"))
    return g


def odds_log_path(out_dir):
    return os.path.join(out_dir, ODDS_LOG)


def odds_log_key(sport, date_iso, away, home):
    return "%s|%s|%s @ %s" % (sport, date_iso, away, home)


def odds_log_update(path, g, now):
    """The first numbers this script saw for a game are kept as the OPENER; the
    latest are kept as the CLOSE candidate. Returns the game's entry."""
    try:
        with open(path, encoding="utf-8") as f:
            log = json.load(f)
    except (OSError, ValueError):
        log = {}
    k = odds_log_key(g["sport"], g["gdate"], g["away"], g["home"])
    snap = {k2: g["inputs"].get(k2) for k2 in ("line", "op", "up", "hml", "aml", "p1line", "f5line", "h1line") if g["inputs"].get(k2)}
    snap["at"], snap["book"] = now, g["book"]
    if g["inputs"].get("sharp"):
        try:
            sh = json.loads(g["inputs"]["sharp"])
            if sh.get("line") is not None:
                snap["sharp"] = {"line": fmt(sh["line"], 1), "op": str(sh.get("op")), "up": str(sh.get("up"))}   # the sharp book's close rides in the log for the measure
        except (ValueError, TypeError):
            pass
    e = log.get(k) or {}
    if snap.get("line"):
        if not e.get("first"):
            e["first"] = snap
        e["last"] = snap
    log[k] = e
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=1)
    return e


def odds_close_for(path, sport, date_iso, away, home):
    """The close the grade run attaches: the last total (and period total) this script saw."""
    try:
        with open(path, encoding="utf-8") as f:
            log = json.load(f)
    except (OSError, ValueError):
        return None
    last = (log.get(odds_log_key(sport, date_iso, away, home)) or {}).get("last") or {}
    if not last.get("line"):
        return None
    c = {"ctot": last["line"]}
    per = last.get("p1line") or last.get("f5line") or last.get("h1line")
    if per:
        c["cf5"] = per
    return c


def odds_books_list(books):
    return [b.strip().lower() for b in (books or ",".join(ODDS_BOOKS)).split(",") if b.strip()]


def make_odds(date_iso, out_dir, log, books=None, sports=("MLB", "NHL", "NBA")):
    key = odds_key(out_dir)
    books = odds_books_list(books)
    rows, now, spent, left = [], now_utc(), 0, None
    for sport in sports:
        try:
            evs = fetch_odds(sport, key, books)
        except Exception as e:  # noqa: BLE001
            log("%s: the odds feed failed (%s)" % (sport, e))
            continue
        used, left = odds_credits()
        spent += used or 0
        todays = [ev for ev in evs if us_game_date(ev.get("commence_time") or "1970-01-01T00:00:00Z") == date_iso]
        log("%s: %d game%s on the feed for %s (%d listed in all)" % (sport, len(todays), "" if len(todays) == 1 else "s", date_iso, len(evs)))
        for ev in todays:
            extra = None
            try:
                extra = fetch_odds_event(sport, ev.get("id"), key, books)
                used, left = odds_credits()
                spent += used or 0
            except Exception as e:  # noqa: BLE001
                log("  %s @ %s: no period, alternate or team totals on the feed (%s)" % (odds_nick(ev.get("away_team")), odds_nick(ev.get("home_team")), e))
            g = odds_game(ev, sport, books, extra)
            e = odds_log_update(odds_log_path(out_dir), g, now)
            opener = (e.get("first") or {}).get("line")
            if opener and not g["inputs"].get("opened"):
                g["inputs"]["opened"] = opener
            i = g["inputs"]
            k0, k1, k2 = ODDS_PERIOD_KEYS[sport]
            s0, s1, s2 = ODDS_SPREAD_KEYS[sport]
            shop = json.loads(i["odds"]) if i.get("odds") else {}
            nalt = len(set(x[2] for x in (shop.get("alt") or {}).get("OVER", [])))
            sharp = json.loads(i["sharp"]) if i.get("sharp") else {}
            log("  %s @ %s  [%s]  total %s (%s/%s) opened %s · ML %s/%s · %s %s (%s/%s) · period %s (%s/%s) · sharp %s · %d alternate number%s%s" % (
                g["away"], g["home"], g["book"] or "no book", i.get("line", "-"), i.get("op", "-"), i.get("up", "-"), i.get("opened", "-"),
                i.get("aml", "-"), i.get("hml", "-"), s0, i.get(s0, "-"), i.get(s1, "-"), i.get(s2, "-"), i.get(k0, "-"), i.get(k1, "-"), i.get(k2, "-"),
                ("%s (%s/%s)" % (fmt(sharp["line"], 1), sharp.get("op"), sharp.get("up"))) if sharp.get("line") is not None else "-",
                nalt, "" if nalt == 1 else "s", " · team totals" if shop.get("team") else ""))
            rows.append(g)
    doc = {"format": FORMAT, "version": VERSION, "date": date_iso, "generated": now,
           "source": "slate.py odds: The Odds API (%s)" % ", ".join(books), "games": rows}
    path = os.path.join(out_dir, "odds-%s.json" % date_iso)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    log("Credits: this run used %s; %s left this month." % (spent, left if left is not None else "unknown"))
    log("Wrote %s with %d game%s. Load it into the sheet with the slate: blank line boxes fill, anything typed stays, and the best price on each side shows on the rail." % (path, len(rows), "" if len(rows) == 1 else "s"))
    return path


# ---- the history mode: past seasons' lines for the backtest ------------------
# One call a snapshot returns every game then on the board, so a season of
# ~185 game dates at two snapshots is ~370 calls: 3,700 credits for the total
# alone. The backtest (tools_backtest_nhl_odds.py) takes the first snapshot
# before a game's start as its OPENER and the last as its CLOSE, for the
# retail book and the sharp one, and measures the move and the gap against
# the finals in the season ledger.

def odds_history_path(out_dir, sport, season):
    return os.path.join(out_dir, "odds-history-%s-%s.json" % (sport, season))


def odds_history_at(date_iso, hhmm):
    """'2025-10-08' + '16:00' -> that day's 16:00Z; '+02:30' -> 02:30Z the NEXT day (a late start)."""
    d = dt.date.fromisoformat(date_iso)
    if hhmm.startswith("+"):
        d += dt.timedelta(days=1)
        hhmm = hhmm[1:]
    return "%sT%s:00Z" % (d.isoformat(), hhmm)


def odds_history_dates(sport, season, out_dir, start=None, end=None):
    """The game dates to pull: a date range when given; else the season ledger's
    own dates (NHL, no off days wasted); else the season's calendar."""
    if not (start and end):
        led = None
        if sport == "NHL":
            led = load_ledger(ledger_path(out_dir, str(season)))
        elif sport == "NBA":
            led = load_nba_ledger(nba_ledger_path(out_dir, nba_norm_season(str(season))))   # the game days only: no off day, no All-Star weekend
        dates = sorted(set(g.get("date") for g in ((led or {}).get("games") or []) if g.get("date")))
        if dates:
            return dates
        y0 = int(str(season)[:4])
        y1 = int(str(season)[4:8]) if len(str(season)) >= 8 else y0 + 1
        start, end = {"NHL": ("%d-10-01" % y0, "%d-04-20" % y1), "MLB": ("%d-03-25" % y0, "%d-10-01" % y0)}.get(sport, ("%d-10-20" % y0, "%d-04-15" % y1))
    a, b = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    return [(a + dt.timedelta(days=n)).isoformat() for n in range((b - a).days + 1)]


def odds_history_add(doc, sport, snap_doc, label):
    """Fold one historical snapshot into the history file: per game, per book,
    [total, over price, under price(, home ML, away ML)] under the snapshot's stamp."""
    ts = snap_doc.get("timestamp") or label
    got = 0
    for ev in snap_doc.get("data") or []:
        full_home, full_away = ev.get("home_team"), ev.get("away_team")
        start = ev.get("commence_time") or "1970-01-01T00:00:00Z"
        k = odds_log_key(sport, us_game_date(start), odds_nick(full_away), odds_nick(full_home))
        g = doc["games"].setdefault(k, {"sport": sport, "gdate": us_game_date(start), "away": odds_nick(full_away), "home": odds_nick(full_home), "start": start, "snaps": {}})
        snap = {}
        for b, mks in odds_markets(ev).items():
            tt = mks.get("totals") or {}
            row = [tt["Over"][1], tt["Over"][0], tt["Under"][0]] if ("Over" in tt and "Under" in tt and tt["Over"][1] is not None) else None
            hh = mks.get("h2h") or {}
            if full_home in hh and full_away in hh:
                row = (row or [None, None, None]) + [hh[full_home][0], hh[full_away][0]]
            if row:
                snap[b] = row
        if snap:
            g["snaps"][ts] = snap
            got += 1
    doc["pulled"][label] = {"at": ts, "games": got}
    return got, ts


def make_odds_history(out_dir, log, books=None, sports=("NHL",), season=None, start=None, end=None, times=None, markets=None, yes=False, keep=ODDS_HISTORY_KEEP):
    if not season and not (start and end):
        raise RuntimeError("odds-history needs --season (e.g. 20252026, or 2024-25 for the NBA) or --from and --to")
    key = odds_key(out_dir)
    books = odds_books_list(books)
    season_arg = str(season) if season else "%s-%s" % (start, end)
    paths = []
    for sport in sports:
        # the defaults by sport: hockey two snapshots a day on the totals (the openers test), the NBA one snapshot on the moneyline (the upset test)
        sp_times = [t.strip() for t in (times or ",".join(ODDS_HISTORY_TIMES_NBA if sport == "NBA" else ODDS_HISTORY_TIMES)).split(",") if t.strip()]
        sp_markets = markets or ODDS_HISTORY_MARKETS.get(sport, "totals")
        nmk = len([m for m in sp_markets.split(",") if m.strip()])
        season = nba_norm_season(season_arg) if (sport == "NBA" and season) else season_arg
        times, markets = sp_times, sp_markets   # the file records what was pulled
        dates = odds_history_dates(sport, season, out_dir, start, end)
        path = odds_history_path(out_dir, sport, season)
        try:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, ValueError):
            doc = {"format": ODDS_HISTORY_FORMAT, "version": 1, "sport": sport, "season": season, "books": books, "markets": markets, "times": times, "pulled": {}, "games": {}}
        todo = [(d, t) for d in dates for t in times if ("%s %s" % (d, t)) not in doc["pulled"]]
        done = len(doc["pulled"])
        log("%s %s: %d game date%s, %d snapshot%s to pull (%d pulled before), about %d credits at %d a market a snapshot." % (
            sport, season, len(dates), "" if len(dates) == 1 else "s", len(todo), "" if len(todo) == 1 else "s", done, len(todo) * ODDS_HISTORY_COST * nmk, ODDS_HISTORY_COST))
        if not todo:
            paths.append(path)
            continue
        if not yes:
            try:
                ans = input("Pull them? Type y to go on: ")
            except EOFError:
                ans = ""
            if ans.strip().lower() not in ("y", "yes"):
                log("Stopped before pulling anything.")
                continue
        for n, (d, t) in enumerate(todo, 1):
            label, at = "%s %s" % (d, t), odds_history_at(d, t)
            try:
                snap_doc = fetch_odds_history(sport, key, books, at, markets)
            except Exception as e:  # noqa: BLE001
                log("  %s: the history call failed (%s). Stopped; what is pulled is kept, run again to go on." % (label, e))
                break
            used, left = odds_credits()
            got, ts = odds_history_add(doc, sport, snap_doc, label)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=1)
            log("  %d/%d  %s -> snapshot %s: %d game%s priced · %s credits · %s left" % (n, len(todo), label, ts, got, "" if got == 1 else "s", used if used is not None else "?", left if left is not None else "?"))
            if left is not None and left < keep:
                log("Stopped with %s credits left, to keep %d for the nightly runs. The month resets on the 1st; run again then and it carries on where it stopped." % (left, keep))
                break
        log("Wrote %s: %d game%s, %d snapshot%s. %s" % (
            path, len(doc["games"]), "" if len(doc["games"]) == 1 else "s", len(doc["pulled"]), "" if len(doc["pulled"]) == 1 else "s",
            "Send it to Claude with the season ledger: the upset test reads the dog's price from it." if sport == "NBA" else "Run tools_backtest_nhl_odds.py on it beside the season ledger."))
        paths.append(path)
        times, markets = None if not times else ",".join(times), None   # the next sport takes its own defaults unless the user gave them
    return paths[-1] if paths else out_dir


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
                c = odds_close_for(odds_log_path(out_dir), "MLB", date_iso, r["away"], r["home"])
                if c:
                    r["close"] = c     # the last number the odds run saw before the game
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
    check("park factor from parks.json (Petco 97)", i["pf"] == "97")
    check("every park factor on file is a Statcast number", all(80 <= p.get("pf", 100) <= 120 for p in parks.values()) and sum(1 for p in parks.values() if "pf" in p) >= 30)
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
    per, shots, en, end = periods_from_landing(_canned_nhl_landing())
    check("ledger: periods, shots, empty net and the end from a landing page",
          per == {1: (1, 0), 2: (1, 2), 3: (0, 1)} and shots == (29, 28) and en == (0, 1) and end == "REG")
    synthetic = [
        {"fa": 2, "fh": 3, "end": "REG", "sa": 29, "sh": 28, "ena": 0, "enh": 1, "p1a": 1, "p1h": 0, "p2a": 1, "p2h": 2, "p3a": 0, "p3h": 1, "away": "NYR", "home": "BOS", "date": "2026-10-06"},
        {"fa": 4, "fh": 3, "end": "OT", "sa": 30, "sh": 32, "ena": 0, "enh": 0, "p1a": 2, "p1h": 1, "p2a": 1, "p2h": 1, "p3a": 0, "p3h": 1, "ota": 1, "oth": 0, "away": "NYR", "home": "XXX", "date": "2026-10-04"},
        {"fa": 1, "fh": 2, "end": "SO", "sa": 25, "sh": 35, "ena": 0, "enh": 0, "p1a": 0, "p1h": 0, "p2a": 1, "p2h": 1, "p3a": 0, "p3h": 0, "away": "XXX", "home": "BOS", "date": "2026-10-02"},
        {"fa": 5, "fh": 1, "end": "REG", "sa": 31, "sh": 30, "ena": 1, "enh": 0, "p1a": 2, "p1h": 0, "p2a": 1, "p2h": 1, "p3a": 2, "p3h": 0, "away": "BOS", "home": "NYR", "date": "2026-09-30"},
    ]
    m = nhl_measure(synthetic)
    # totals 5, 7, 3, 6 -> 5.25; OT or SO 2 of 4; an empty-net goal in 2 of 4; P1 goals 1+3+0+2 = 6 over
    # regulation non-EN goals (5-1)+(6)+(2)+(6-1) = 17 -> .353; P1 per game 1.5; shots 240 over 8 team-games = 30.0;
    # goals on goalies: 21 finals - 2 EN - 1 SO = 18 on 240 shots -> .925
    check("ledger: the measures", m["games"] == 4 and abs(m["goals_per_game"] - 5.25) < 1e-9 and abs(m["ot_rate"] - 0.5) < 1e-9 and abs(m["so_rate"] - 0.25) < 1e-9
          and abs(m["empty_net_rate"] - 0.5) < 1e-9 and abs(m["p1_share"] - 6 / 17.0) < 1e-9 and abs(m["p1_per_game"] - 1.5) < 1e-9
          and abs(m["shots_per_team"] - 30.0) < 1e-9 and abs(m["save_pct"] - 0.925) < 1e-9 and abs(m["p1_dist"]["2+"] - 0.5) < 1e-9)
    avg1, k1 = team_p1_last10(synthetic, "NYR", "2026-10-07")
    check("ledger: a club's first-period last ten, before the date", k1 == 3 and abs(avg1 - (1 + 3 + 2) / 3.0) < 1e-9)
    check("ledger: nothing before the season", team_p1_last10(synthetic, "NYR", "2026-09-01") == (None, 0))
    det = nhl_detail({"away": "NYR", "home": "BOS"}, dict(x for x in _canned_nhl())["/boxscore"], _canned_nhl_landing())
    check("ledger detail: starters by flag or by ice time, their lines, power-play goals and penalties",
          det["ga_id"] == 1 and det["ga_sa"] == 28 and det["ga_sv"] == 26 and det["ga_ga"] == 2 and det["gh_id"] == 9 and det["gh_name"] == "J. S" and det["gh_sa"] == 31
          and det["ppga"] == 1 and det["ppgh"] == 0 and det["pena"] == 1 and det["penh"] == 1 and det["detail"] is True)
    rail = {"gameInfo": {"referees": [{"default": "Wes McCauley"}, {"default": "Kelly Sutherland"}], "linesmen": [{"default": "A. Lines"}, {"default": "B. Lines"}],
                         "awayTeam": {"headCoach": {"default": "Coach A"}, "scratches": [{"id": 1}, {"id": 2}]}, "homeTeam": {"headCoach": {"default": "Coach B"}, "scratches": []}}}
    rf = nhl_refs({"id": 1}, rail)
    check("ledger officials: referees, linesmen and scratch counts from the side panel",
          rf["refs"] == ["Wes McCauley", "Kelly Sutherland"] and rf["linesmen"] == ["A. Lines", "B. Lines"] and rf["scra"] == 2 and rf["scrh"] == 0 and rf["rail"] is True)
    # the feed's real shape, from the user's saved side panel of game 2024020500
    real_rail = {"gameInfo": {"referees": [{"fullName": {"default": "Garrett Rank"}, "sweaterNumber": 7}, {"fullName": {"default": "Francois St-Laurent"}, "sweaterNumber": 8}],
                              "linesmen": [{"fullName": {"default": "Julien Fournier"}, "sweaterNumber": 56}], "awayTeam": {"scratches": [{"id": 1}, {"id": 2}, {"id": 3}]}, "homeTeam": {"scratches": [{"id": 4}]}}}
    rr = nhl_refs({"id": 2024020500}, real_rail)
    check("ledger officials: the feed's fullName shape", rr["refs"] == ["Garrett Rank", "Francois St-Laurent"] and rr["linesmen"] == ["Julien Fournier"] and rr["scra"] == 3 and rr["scrh"] == 1)
    rf2 = nhl_refs({"id": 2}, {}, {"summary": {"gameInfo": {"referees": [{"default": "Chris Rooney"}]}}})
    check("ledger officials: falls back to the game page, and an empty panel still marks the game fetched", rf2.get("refs") == ["Chris Rooney"] and nhl_refs({"id": 3}, {}).get("rail") is True and "refs" not in nhl_refs({"id": 3}, {}))
    past = {"id": 2024020001, "gameDate": "2024-10-04", "periodDescriptor": {"number": 4, "periodType": "OT"},
            "awayTeam": {"abbrev": "NJD", "score": 4, "sog": 23}, "homeTeam": {"abbrev": "BUF", "score": 3, "sog": 31},
            "summary": {"scoring": [
                {"periodDescriptor": {"number": 1, "periodType": "REG"}, "goals": [{"teamAbbrev": {"default": "NJD"}, "goalModifier": "none"}, {"teamAbbrev": {"default": "NJD"}, "goalModifier": "none"}]},
                {"periodDescriptor": {"number": 2, "periodType": "REG"}, "goals": []},
                {"periodDescriptor": {"number": 3, "periodType": "REG"}, "goals": [{"teamAbbrev": {"default": "BUF"}, "goalModifier": "none"}, {"teamAbbrev": {"default": "BUF"}, "goalModifier": "none"}, {"teamAbbrev": {"default": "BUF"}, "goalModifier": "none"}]},
                {"periodDescriptor": {"number": 4, "periodType": "OT"}, "goals": [{"teamAbbrev": {"default": "NJD"}, "goalModifier": "none"}]}]}}
    pper, pshots, pen, pend = periods_from_landing(past)
    check("ledger: a finished season's page (goal list, no linescore) gives periods, shots and the end",
          pper == {1: (2, 0), 2: (0, 0), 3: (0, 3), "OT": (1, 0)} and pshots == (23, 31) and pen == (0, 0) and pend == "OT")
    land0 = _canned_nhl_landing()
    e0 = ledger_entry({"id": 7, "awayTeam": {"abbrev": "NYR", "score": 2}, "homeTeam": {"abbrev": "BOS", "score": 3}}, land0, "2026-10-06")
    check("ledger: a schedule game without its own date takes the day's", e0["date"] == "2026-10-06" and e0["fa"] == 2)
    mp_csv = ("team,season,name,team,position,situation,games_played,xGoalsFor,xGoalsAgainst,shotsOnGoalFor,goalsFor\n"
              "BOS,2026,BOS,BOS,Team Level,all,4,11.72,11.64,99.0,9.0\n"
              "BOS,2026,BOS,BOS,Team Level,5on5,4,8.0,8.0,70.0,6.0\n"
              "NYR,2026,NYR,NYR,Team Level,all,6,15.0,21.0,180.0,18.0\n"
              "SJS,2026,SJS,SJS,Team Level,all,0,0,0,0,0\n")
    rates, lg = parse_moneypuck_teams(mp_csv)
    check("moneypuck: the 'all' rows per game, and the table's league mean",
          set(rates) == {"BOS", "NYR"} and abs(rates["BOS"]["xgf"] - 2.93) < 1e-9 and abs(rates["NYR"]["xga"] - 3.5) < 1e-9
          and abs(lg - (11.72 + 11.64 + 15.0 + 21.0) / 20.0) < 1e-9)
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
        gsum = nhl_goalie_summary("20262027")
        row = build_nhl_game(nhl_schedule("2026-10-07")[0], "2026-10-07", "20262027", nhl_team_summary("20262027"), lines2.append, goalie_summary=gsum)
        gr2 = grade_nhl_game(nhl_schedule("2026-10-06")[0], lines2.append)
    finally:
        fetch_json = real
    i = row["inputs"]
    # the context card (14 Oct 2026): the named goalies ranked among the goalies with 100+ shots
    # (Thin Line's 40 shots do not count), the back-to-back label, and the tag on each line
    check("goalie report: every goalie's line by id", gsum[3]["sv"] == 0.921 and gsum[3]["shots"] == 1900 and gsum[2]["name"] == "Jonathan Q")
    ctx = json.loads(i["nhlctx"])
    check("context: the named starters are ranked among the goalies with 100+ shots",
          any(c["t"] == "Jeremy S .921 on 1900 shots, 1st of 4 goalies with 100+ shots." and c["side"] == "home" and c["s"] == "scored" and c["k"] == "goalie" for c in ctx)
          and any(c["t"] == "Jonathan Q .902 on 500 shots, 3rd of 4 goalies with 100+ shots." and c["k"] == "goalie_backup" and "backup rule" in c["tag"] for c in ctx))
    check("context: the back to back is a label", any(c["t"] == "Rangers on a back to back." and c["s"] == "label" for c in ctx))
    check("context: two clubs on the summary is no league to rank in", not any(c["k"] in ("shots", "special") for c in ctx))
    check("context: the printout reads it", any("context: Rangers on a back to back." in l for l in lines2))
    # the ranks, on a synthetic league of twenty clubs: the Bruins allow the most, the Rangers the fewest
    tabs = {"C%02d" % k: {"gf": 2.5 + 0.05 * k, "ga": 2.5 + 0.05 * k, "n": 8, "l10": 5.0 + 0.1 * k, "enc": 0.3, "ens": 0.3, "en_n": 12} for k in range(18)}
    tabs["BOS"] = {"gf": 2.95, "ga": 4.1, "n": 8, "l10": 7.4, "enc": 0.75, "ens": 0.2, "en_n": 12}   # 2.95 scored is 9th of 20: the middle
    tabs["NYR"] = {"gf": 2.1, "ga": 2.2, "n": 8, "l10": 5.1, "enc": 0.3, "ens": 0.3, "en_n": 12}
    sides = [{"nick": "Rangers", "ab": "NYR", "side": "away", "row": None, "pick": None, "backup": False, "rest": "1"},
             {"nick": "Bruins", "ab": "BOS", "side": "home", "row": None, "pick": None, "backup": False, "rest": "1"}]
    cx = nhl_context(sides, {}, None, tabs, {})
    texts = [c["t"] for c in cx]
    check("context: ranks from the ledger table, most and fewest, with the faded tag on scoring rates",
          "Bruins allow 4.10 a game, 1st most in the league (8 games)." in texts and "Rangers allow 2.20 a game, 1st fewest in the league (8 games)." in texts
          and "Rangers score 2.10 a game, 1st fewest in the league (8 games)." in texts
          and all(c["s"] == "faded" and "over-moves" in c["tag"] for c in cx if c["k"] == "rates"))
    check("context: the last ten and the empty-net habit, scored", "Bruins games have averaged 7.4 goals over the last ten, 1st highest in the league." in texts
          and "Bruins concede 0.75 empty-netters a game, 1st most in the league: they trail late." in texts and all(c["s"] == "scored" for c in cx if c["k"] in ("form", "en")))
    check("context: a club in the middle of the league says nothing", not any("Bruins score" in t for t in texts))
    check("context: ordinals and phrases", ordinal(1) == "1st" and ordinal(2) == "2nd" and ordinal(3) == "3rd" and ordinal(4) == "4th" and ordinal(11) == "11th" and ordinal(12) == "12th" and ordinal(13) == "13th" and ordinal(22) == "22nd"
          and ctx_phrase(4, 32, "most", "fewest") == "4th most" and ctx_phrase(29, 32, "most", "fewest") == "4th fewest" and ctx_rank(3.0, [1.0, 2.0, 3.0, 4.0]) == (2, 4) and ctx_rank(3.0, [1.0, 2.0, 3.0, 4.0], False) == (3, 4))
    check("context: fewer than sixteen clubs ranks nothing; the top and bottom eight of 32 are notable",
          not ctx_notable(1, 10) and ctx_notable(1, 16) and ctx_notable(8, 32) and not ctx_notable(9, 32) and not ctx_notable(24, 32) and ctx_notable(25, 32))
    led_t = nhl_ledger_tables([{"date": "2026-10-01", "home": "BOS", "away": "NYR", "fa": 2, "fh": 5, "ena": 0, "enh": 1, "id": 1},
                               {"date": "2026-10-03", "home": "NYR", "away": "BOS", "fa": 1, "fh": 3, "ena": 0, "enh": 0, "id": 2},
                               {"date": "2026-10-09", "home": "NYR", "away": "BOS", "fa": 9, "fh": 9, "ena": 0, "enh": 0, "id": 3}], "2026-10-07")
    check("context: the ledger table, per club before the date", led_t["BOS"]["gf"] == 3.0 and led_t["BOS"]["ga"] == 2.5 and led_t["BOS"]["n"] == 2 and led_t["NYR"]["l10"] == 5.5
          and led_t["BOS"]["ens"] == 0.5 and led_t["NYR"]["enc"] == 0.5 and led_t["NYR"]["en_n"] == 2)
    check("nhl teams", row["away"] == "Rangers" and row["home"] == "Bruins" and row["sport"] == "NHL")
    check("nhl team rates", i["asf"] == "31.2" and i["hsf"] == "33.4" and i["app"] == "22.1" and i["hpk"] == "78.1")
    # the Rangers are on a back to back and Igor started yesterday, so the slate names the backup
    # Jonathan Q: .902 on 500 this season plus half of .910 on 1,000 last season = .906 on 1,000.
    # Jeremy S: .921 on 1,900 plus half of .915 on 2,000 (two clubs, summed) = .919 on 2,900.
    check("nhl goalies: likely starters, this season blended with half of last",
          row["starters"] == {"away": "Jonathan Q", "home": "Jeremy S"} and i["agsv"] == "0.906" and i["agsh"] == "1000" and i["hgsv"] == "0.919" and i["hgsh"] == "2900")
    check("nhl goalies: the printout shows both halves", any("this season 0.902 on 500; last season 0.910 on 1000, at half" in l for l in lines2))
    pk = json.loads(i["ngoalies"])
    check("nhl goalies: the picker lists every goalie on each club with his line, starts and the club's starts",
          [x["n"] for x in pk["away"]] == ["Igor S", "Jonathan Q"] and pk["away"][1]["sv"] == 0.906 and pk["away"][1]["sh"] == 1000 and pk["away"][1]["gs"] == 17 and pk["away"][0]["cs"] == 64 and pk["home"][0]["n"] == "Jeremy S" and pk["home"][0]["ls"] is False)
    check("nhl goalies: the named starter's name rides on the row", i["agname"] == "Jonathan Q" and i["hgname"] == "Jeremy S")
    check("nhl grade: who started in net, from the box score", gr2.get("starters") == {"away": "I. S", "home": "J. S"})
    check("nhl goalies: a goalie with no last season keeps his own line", any(x["name"] == "Igor S" and x["shots"] == 1400 and x.get("prior") is None for x in row["goalies"]["away"]))
    check("nhl goalies: the blend is noted", any("blend this season with half of last season" in n for n in row["notes"]))
    fa = row["form"]["away"]
    check("nhl form: the last five finals, oldest first, with shots and the starter",
          len(fa) == 5 and fa[-1]["date"] == "2026-10-06" and fa[0]["date"] == "2026-09-26" and fa[-1]["sf"] == 31 and fa[-1]["sa"] == 28 and fa[-1]["goalie"] == "I. S" and fa[-1]["opp"] == "Bruins")
    check("nhl form: rides in the inputs as JSON", json.loads(i["nhlform"])["home"][-1]["date"] == "2026-10-04")
    check("nhl form: the first period rides along (NYR away, 1-0 after one)", fa[-1]["p1f"] == 1 and fa[-1]["p1a"] == 0)
    check("nhl form: the printout reads it", any("last five:" in l and "I. S" in l for l in lines2))
    check("nhl rest and last ten", i["arest"] == "0" and i["hrest"] == "2" and i["al10"] == "5.9" and i["hl10"] == "6.4")
    # the Rangers scored total-2 in every fake final (44 over 11), the Bruins 48 over 11; both allowed 2 a game
    check("nhl scoring rates: goals for and against per game over the season's finals, with the games behind them",
          i["agf"] == "4.00" and i["aga"] == "2.00" and i["hgf"] == "4.36" and i["hga"] == "2.00" and i["angp"] == "11" and i["hngp"] == "11" and i["lgg"] == "")
    check("nhl scoring rates: the league's goals a game from the ledger, twenty finals in",
          nhl_league_gpg([{"fa": 2, "fh": 3, "date": "2026-10-01"}] * 25, "2026-10-07") == 5.0 and nhl_league_gpg([{"fa": 2, "fh": 3, "date": "2026-10-01"}] * 5, "2026-10-07") is None)
    # empty-net habits from the ledger: the Rangers, away in every game, conceded the home side's empty-netter each night
    en_led = [{"home": "BOS", "away": "NYR", "ena": 0, "enh": 1, "date": "2026-10-01"}] * 12 + [{"home": "BOS", "away": "NYR", "ena": 1, "enh": 0, "date": "2026-10-09"}]
    check("nhl empty-net habits: conceded and scored per game to date, games after the date left out",
          nhl_en_rates(en_led, "NYR", "2026-10-07") == (1.0, 0.0, 12) and nhl_en_rates(en_led, "BOS", "2026-10-07") == (0.0, 1.0, 12) and nhl_en_rates(en_led, "SJS", "2026-10-07") == (None, None, 0))
    check("nhl head to head", i["h2h"] == "5.5" and i["h2hn"] == "2")
    check("nhl: the back-to-back side gets the rested goalie", any("did not start yesterday" in n for n in row["notes"]))
    # Jonathan Q has 17 of the Rangers' 64 starts (27%): the backup. Jeremy S has 60 of 71: not.
    check("nhl backup: the away starter is flagged, the home one is not", i["agbk"] is True and i["hgbk"] is False)
    check("nhl backup: noted with the share", any("Jonathan Q is the BACKUP (17 of the club's 64 starts)" in n for n in row["notes"]))
    check("nhl backup: last season's lines never qualify", not nhl_is_backup({"gs": 2, "season": "20252026"}, [{"gs": 2, "season": "20252026"}, {"gs": 60, "season": "20252026"}]))
    check("nhl backup: under ten club starts, no flag", not nhl_is_backup({"gs": 1}, [{"gs": 1}, {"gs": 7}]))
    check("nhl: never confirmed", all("NOT confirmed" in n for n in row["notes"] if "likely starter" in n))
    # the goalie lineups (19 Oct 2026): RotoWire names the goalie and his status, CBS the depth chart and the news
    rw_date, rw = parse_rotowire_goalies(_canned_rotowire())
    check("rotowire: the page's date, each club's goalie with his status and opponent, the tools box skipped",
          rw_date == "October 7, 2026" and rw["Rangers"] == {"name": "I. S", "status": "confirmed", "opp": "Bruins", "home": False}
          and rw["Bruins"]["name"] == "Jeremy S" and rw["Bruins"]["status"] == "expected" and rw["Bruins"]["home"] is True and len(rw) == 2)
    check("rotowire: the date line to ISO", _rw_date_iso("October 7, 2026") == "2026-10-07" and _rw_date_iso("") is None)
    cbs = parse_cbs_goalies(_canned_cbs())
    check("cbs: starter, backup, reserves and the tooltip by name, CBS's codes mapped to the league's",
          cbs["NYR"]["starter"] == "Igor S" and cbs["NYR"]["backup"] == "Jonathan Q" and cbs["NYR"]["reserves"] == [] and cbs["CBJ"]["starter"] == "Jet G"
          and cbs["NYR"]["news"]["Igor S"] == "Rangers' Igor S: First goalie off Wednesday" and cbs["BOS"]["reserves"] == ["Joonas K"]
          and cbs["BOS"]["news"]["Joonas K"] == "Lower Body: IR. Expected to be out until at least Oct 20" and set(cbs) == {"NYR", "BOS", "CBJ"})
    check("goalie names: an initial and a surname meet the club page's full name, accents and hyphens aside",
          nhl_goalie_match("A. Vasilevskiy", [{"name": "Andrei Vasilevskiy"}, {"name": "Dennis Hildeby"}])["name"] == "Andrei Vasilevskiy"
          and nhl_goalie_match("Ukko-Pekka Luukkonen", [{"name": "Ukko-Pekka Luukkonen"}])["name"] == "Ukko-Pekka Luukkonen"
          and nhl_goalie_match("J. Smith", [{"name": "Alex Smith"}, {"name": "Jo Smith"}])["name"] == "Jo Smith"
          and nhl_goalie_match("Nobody", [{"name": "Igor S"}]) is None and _name_key("Jesper Wallstedt") == ("j", "wallstedt") and _name_key("Montembeault") == ("", "montembeault"))
    check("backup source: the starts rule first, CBS's depth chart under ten club starts, nothing otherwise",
          nhl_backup_source({"name": "Jonathan Q", "gs": 17}, [{"name": "Igor S", "gs": 47}, {"name": "Jonathan Q", "gs": 17}], None) == "starts"
          and nhl_backup_source({"name": "Jonathan Q", "gs": 1}, [{"name": "Igor S", "gs": 5}, {"name": "Jonathan Q", "gs": 1}], {"backup": "Jonathan Q"}) == "cbs"
          and nhl_backup_source({"name": "Igor S", "gs": 5}, [{"name": "Igor S", "gs": 5}, {"name": "Jonathan Q", "gs": 1}], {"backup": "Jonathan Q"}) is None
          and nhl_backup_source({"name": "Jonathan Q", "gs": 1}, [{"name": "Igor S", "gs": 5}, {"name": "Jonathan Q", "gs": 1}], None) is None
          and nhl_backup_source({"name": "Jonathan Q", "gs": 3}, [{"name": "Igor S", "gs": 20}, {"name": "Jonathan Q", "gs": 3}], {"backup": "Igor S"}) == "starts")
    fetch_json = fake_nhl
    try:
        lines3 = []
        row3 = build_nhl_game(nhl_schedule("2026-10-07")[0], "2026-10-07", "20262027", nhl_team_summary("20262027"), lines3.append, goalie_summary=gsum, lineups={"rw": rw, "cbs": cbs})
    finally:
        fetch_json = real
    i3 = row3["inputs"]
    check("lineups: RotoWire's confirmed goalie replaces the slate's back-to-back guess, his line follows and the Confirmed box is ticked",
          i3["agname"] == "Igor S" and i3["agsv"] == "0.912" and i3["agsh"] == "1400" and i3["agconf"] is True and i3["agbk"] is False and row3["starters"]["away"] == "Igor S"
          and any("Rangers starter: Igor S, CONFIRMED on RotoWire. The Confirmed box is ticked." in n for n in row3["notes"]))
    check("lineups: an expected start is said to be expected and its box stays unticked",
          i3["hgname"] == "Jeremy S" and i3["hgconf"] is False and any("Bruins likely starter: Jeremy S, EXPECTED on RotoWire, not yet confirmed" in n for n in row3["notes"]))
    check("lineups: CBS's blurb on the named goalie and the injured reserve ride in the notes",
          any(n == "CBS on Igor S: Rangers' Igor S: First goalie off Wednesday" for n in row3["notes"])
          and any("Bruins: Joonas K is on CBS's reserve list (Lower Body: IR. Expected to be out until at least Oct 20)." in n for n in row3["notes"]))
    check("lineups: the printout names the source", any("[RotoWire: confirmed]" in l for l in lines3) and any("[RotoWire: expected]" in l for l in lines3))
    fetch_json = fake_nhl
    try:
        row4 = build_nhl_game(nhl_schedule("2026-10-07")[0], "2026-10-07", "20262027", nhl_team_summary("20262027"), lambda s: None, goalie_summary=gsum,
                              lineups={"rw": {"Rangers": {"name": "Call Up", "status": "confirmed", "opp": "Bruins", "home": False}}, "cbs": {}})
    finally:
        fetch_json = real
    check("lineups: a goalie RotoWire names who is not on the club page leaves the guess and says so",
          row4["inputs"]["agname"] == "Jonathan Q" and row4["inputs"]["agconf"] is False
          and any("RotoWire names Call Up in net for the Rangers (confirmed), who is not on the club's goalie page" in n for n in row4["notes"]))
    check("lineups: the boxes start False on every row, so the sheet reads a boolean either way", i["agconf"] is False and i["hgconf"] is False)
    # the player props (19 Oct 2026): the lines in The Odds API's shape, the defence table, the logs, the projection
    ev_doc = {"id": "e1", "bookmakers": [
        {"key": "draftkings", "markets": [{"key": "player_points", "outcomes": [{"name": "Over", "description": "Luka Dončić", "price": -115, "point": 31.5}, {"name": "Under", "description": "Luka Dončić", "price": -105, "point": 31.5}]}]},
        {"key": "fanatics", "markets": [
            {"key": "player_points", "outcomes": [{"name": "Over", "description": "Luka Dončić", "price": -110, "point": 30.5}, {"name": "Under", "description": "Luka Dončić", "price": -110, "point": 30.5},
                                                  {"name": "Over", "description": "Luka Dončić", "price": 150, "point": 35.5}, {"name": "Under", "description": "Luka Dončić", "price": -190, "point": 35.5},
                                                  {"name": "Over", "description": "Bench Guy", "price": -110, "point": 8.5}]},
            {"key": "player_rebounds", "outcomes": []},
            {"key": "player_first_basket", "outcomes": [{"name": "Luka Dončić", "price": 600}]}]},
        {"key": "fanduel", "markets": [{"key": "player_rebounds", "outcomes": [{"name": "Over", "description": "Luka Dončić", "price": -120, "point": 8.5}, {"name": "Under", "description": "Luka Dončić", "price": 100, "point": 8.5}]}]}]}
    pp = odds_event_props(ev_doc, ODDS_BOOKS)
    check("props: the carded book's main line first, the alternates left, a one-sided line left, the other markets ignored",
          [(x["name"], x["mk"], x["line"], x["op"], x["up"], x["book"]) for x in pp] == [("Luka Dončić", "pts", 30.5, -110, -110, "fanatics"), ("Luka Dončić", "reb", 8.5, -120, 100, "fanduel")]
          and pp[0]["books"]["draftkings"] == [31.5, -115, -105] and "fanatics" not in pp[1]["books"])
    dvp_html = ('<table id="GridView2"><tr><th>Sort: Position</th><th>Sort: Team</th><th>Sort: PTS</th><th>Sort: REB</th></tr><tr><td>PG</td><td>OKC &nbsp;&nbsp; 3</td><td>21.6 &nbsp;&nbsp; 28</td><td>6.3 &nbsp;&nbsp; 27</td></tr></table>'
                '<table id="GridView1"><tr><th>Sort: Position</th><th>Sort: Team</th><th>Sort: PTS</th><th>Sort: FG%</th><th>Sort: 3PM</th><th>Sort: REB</th><th>Sort: AST</th></tr>'
                '<tr><td>PG</td><td><a>NY</a> &nbsp;&nbsp; 6</td><td>21.9 &nbsp;&nbsp; 34</td><td>42.8 &nbsp;&nbsp; 7</td><td>3.0 &nbsp;&nbsp; 104</td><td>5.6 &nbsp;&nbsp; 4</td><td>8.4 &nbsp;&nbsp; 135</td></tr>'
                '<tr><td>PG</td><td>GS &nbsp;&nbsp; 150</td><td>26.1 &nbsp;&nbsp; 149</td><td>47.0 &nbsp;&nbsp; 83</td><td>3.9 &nbsp;&nbsp; 150</td><td>6.5 &nbsp;&nbsp; 35</td><td>8.6 &nbsp;&nbsp; 139</td></tr>'
                '<tr><td>C</td><td>GS &nbsp;&nbsp; 10</td><td>24.0 &nbsp;&nbsp; 50</td><td>50.0 &nbsp;&nbsp; 90</td><td>0.5 &nbsp;&nbsp; 10</td><td>12.0 &nbsp;&nbsp; 100</td><td>3.0 &nbsp;&nbsp; 20</td></tr></table>')
    dv = parse_hashtag_dvp(dvp_html)
    means = props_dvp_means(dv)
    check("props: the defence table from the one table with every position, the site's codes mapped to the league's, value and rank, the league mean per position",
          dv[("PG", "NYK")]["pts"] == (21.9, 34) and dv[("PG", "GSW")]["tpm"] == (3.9, 150) and dv[("C", "GSW")]["reb"] == (12.0, 100) and ("PG", "OKC") not in dv
          and abs(means[("PG", "pts")] - 24.0) < 1e-9 and means[("C", "ast")] == 3.0)

    def pline(pid, name, st, mins, pts, reb, ast, tpm, pos="PG"):
        return nba_player_line(pid, name, st, mins, pts, 0, reb, ast, tpm, 20, 8, 3, 1, 0, 10, 7, pos)
    this_games = [{"id": "g%d" % k, "date": "2026-10-%02d" % (10 + k), "away": "DAL", "home": "LAL", "detail": True,
                   "pa": [pline("11", "Luka Doncic", 1, m_, p_, r_, a_, t_), pline("22", "Kyrie Irving", 1, 30.0, 20, 4, 5, 2)], "ph": [pline("44", "LeBron James", 1, 35.0, 25, 7, 8, 2, "SF")]}
                  for k, (m_, p_, r_, a_, t_) in enumerate([(36.0, 30, 8, 9, 4), (34.0, 28, 7, 8, 3), (38.0, 35, 9, 10, 5)])]
    last_games = [{"id": "h%d" % k, "date": "2026-01-%02d" % (10 + k), "away": "LAL", "home": "DAL", "detail": True, "ph": [pline("11", "Luka Doncic", 1, 35.0, 30, 8, 8, 4)], "pa": [pline("44", "LeBron James", 1, 35.0, 25, 7, 8, 2, "SF")]} for k in range(2)]
    lt, ll = nba_player_logs(this_games), nba_player_logs(last_games)
    check("props: the game logs by id, oldest first, with the club, the position and the stats",
          lt["11"]["team"] == "DAL" and lt["11"]["pos"] == "PG" and len(lt["11"]["g"]) == 3 and lt["11"]["g"][-1]["pts"] == 35 and lt["11"]["g"][0]["home"] is False and ll["11"]["g"][0]["home"] is True and lt["44"]["pos"] == "SF")
    pr_ = props_rate(lt["11"]["g"], ll["11"]["g"], "pts")
    check("props: the rate blends this season with last season's at half its minutes", abs(pr_["rate"] * 36 - 30.965) < 0.01 and pr_["m_this"] == 108 and pr_["w"] == 35 and abs(pr_["prior"] * 36 - 30.857) < 0.01
          and props_rate([], [], "pts") is None and props_rate(lt["11"]["g"], ll["11"]["g"], "pra")["n_this"] == 3)
    pm_ = props_minutes(lt["11"]["g"], ll["11"]["g"])
    check("props: the minutes are the last five games' mean this season, else last season's whole-season mean",
          pm_["proj"] == 36.0 and pm_["n"] == 3 and pm_["starts"] == 3 and pm_["last_season"] is False and pm_["season"] == 36.0
          and props_minutes([], ll["11"]["g"]) == {"proj": 35.0, "n": 2, "season": None, "starts": 2, "last_season": True} and props_minutes([], []) is None)
    check("props: the chance of the over from a normal, a whole line pushing on the number", abs(props_over(34.134, 10.5165, 30.5)[0] - 0.6352) < 0.001 and props_over(34.134, 10.5165, 30.5)[1] == 0
          and abs(sum(props_over(30.0, 5.0, 30)) - (1 - _phi(-0.1))) < 1e-9 and props_over(20.0, 0.0, 19.5) == (1.0, 0.0))
    check("props: the blend leans on the market", abs(props_blend(0.5, 0.6352) - 0.5461) < 0.001 and props_blend(0.5, 0.5) == 0.5 and abs(props_devig(-110, -110) - 0.5) < 1e-9 and abs(props_implied(150) - 0.4) < 1e-9)
    inj_ = {"DAL": [{"id": "22", "n": "Kyrie Irving", "st": "Out", "note": "knee"}, {"id": "33", "n": "Some Body", "st": "Questionable", "note": "ankle"}]}
    out_mpg, listed, maybe = props_out_minutes("DAL", inj_, lt, ll)
    check("props: the regulars out, at their own minutes, the questionable listed apart", out_mpg == 30.0 and listed == [("Kyrie Irving", 30.0, "Out")] and maybe == [("Some Body", "Questionable")])
    prop_ = {"name": "Luka Dončić", "mk": "pts", "line": 30.5, "op": -110, "up": -110, "book": "fanatics", "books": {}}
    tbl = nba_dvp_table(this_games)
    check("props: the ledger's defence table, per defence, position and market, with the games behind it; one defence of guards is the league itself",
          tbl[("LAL", "G", "pts")] == (1.0, 3) and tbl[("DAL", "F", "reb")] == (1.0, 3) and ("DAL", "G", "pts") not in tbl and nba_dvp_table(this_games, "2026-10-11")[("LAL", "G", "ast")][1] == 1)
    check("props: this season's factor shrinks toward last season's by the games behind it",
          abs(props_dvp_blend((1.10, 10), (1.00, 82))["f"] - 1.0333333) < 1e-6 and props_dvp_blend((1.10, 10), None)["f"] == 1.10 and props_dvp_blend(None, (0.95, 82)) == {"f": 0.95, "f_this": None, "n_this": 0, "f_last": 0.95, "n_last": 82}
          and props_dvp_blend(None, None) is None)
    check("props: the website's rank shown beside the ledger's factor, the five positions folded into three",
          htb_line(dv, "Knicks", "NYK", "G", "pts") == "HashtagBasketball: Knicks allow 21.9 points a game to PGs (34th of 150, 1 the fewest); shown, not scored"
          and htb_line(dv, "Warriors", "GSW", "C", "reb") == "HashtagBasketball: Warriors allow 12.0 rebounds a game to Cs (100th of 150, 1 the fewest); shown, not scored" and htb_line(dv, "Knicks", "NYK", "F", "pts") is None)
    ctx_ = {"out_mpg": 30.0, "out_names": [("Kyrie Irving", 30.0, "Out")], "maybe": [("Some Body", "Questionable")], "pace": 100.0, "league_pace": 98.0, "home": False, "pos": "G", "opp_nick": "Lakers",
            "dvp": {"f": 25.0 / 24.0, "f_this": 25.0 / 24.0, "n_this": 10, "f_last": None, "n_last": 0}, "htb": "HashtagBasketball: Lakers allow 25.0 points a game to PGs (120th of 150, 1 the fewest); shown, not scored", "self_out": ""}
    proj_, why_ = props_project(prop_, lt["11"]["g"], ll["11"]["g"], ctx_)
    check("props: the projection is rate x minutes, the regulars out, pace and the defence, against the line",
          abs(proj_["proj"] - 34.48) < 0.05 and abs(proj_["sd"] - 10.86) < 0.02 and proj_["side"] == "OVER" and abs(proj_["p"] - 0.549) < 0.002 and proj_["band"] == "LEAN"
          and abs(proj_["edge"] - 0.025) < 0.002 and proj_["price"] == -110 and abs(proj_["mins"] - 37.4) < 0.05)
    check("props: the why says each step",
          any(w.startswith("31.0 points per 36 this season (3 games, 108 minutes), blended with last season's 30.9 (70 of 70 minutes, at half): 31.0 per 36") for w in why_)
          and any(w.startswith("36.0 minutes projected: his last 3 games (season 36.0), 3 of them starts") for w in why_)
          and any(w == "Kyrie Irving out (30 minutes a game between them): +1.4 minutes and +0.56 points per 36, the pooled rule, scored" for w in why_)
          and any(w == "Some Body is Questionable: not counted as out" for w in why_) and any(w == "pace 100.0 against the league's 98.0: x1.020" for w in why_)
          and any(w == "Lakers allow 1.04x the league's points per minute to guards (this season 1.04 over 10 games): x1.031 at 0.75 weight, measured" for w in why_)
          and any(w == ctx_["htb"] for w in why_)
          and any(w.startswith("home 30.9 / road 31.0 per 36 over 178 minutes: shown, not scored") and w.endswith("; tonight on the road") for w in why_)
          and any(w.startswith("projected 34.5 against points 30.5, one sigma 10.9: the over 64.3% by the projection, 50.0% by the book's prices; blended 54.9% at 4 to 2") for w in why_))
    check("props: a listed-out player gets no projection, and no history is said", props_project(prop_, lt["11"]["g"], ll["11"]["g"], dict(ctx_, self_out="Out"))[0] is None
          and props_project(prop_, [], [], ctx_)[1] == ["no history to project from (under 60 minutes with the stat in the ledgers)"])
    check("props: a prop's name finds the player on one of the two clubs, by roster, by ledger, by surname, else says so",
          props_match_player("Luka Dončić", ("DAL", "LAL"), lt, ll) == ("11", "DAL", "ledger") and props_match_player("L. Doncic", ("DAL", "LAL"), lt, ll) == ("11", "DAL", "surname")
          and props_match_player("Luka Doncic", ("BOS", "MIA"), {}, {}, {"MIA": {"77": "Luka Doncic"}}) == ("77", "MIA", "roster") and props_match_player("Nobody Here", ("DAL", "LAL"), lt, ll) == (None, None, "not in the ledgers")
          and props_match_player("Luka Doncic", ("BOS", "MIA"), lt, ll) == ("11", None, "name only, club unknown") and props_name_key("Jaren Jackson Jr.") == "jaren jackson" and props_name_key("P.J. Washington") == "pj washington")
    check("props: the box for the grade file, by id", nba_props_box(this_games[0]) == {"11": ["Luka Doncic", 36.0, 30, 8, 9, 4], "22": ["Kyrie Irving", 30.0, 20, 4, 5, 2], "44": ["LeBron James", 35.0, 25, 7, 8, 2]})
    check("the date: every slate, the ledgers, the odds and the props run for today; the grades for yesterday",
          all(default_date(m, dt.date(2026, 10, 19)) == "2026-10-19" for m in ("slate", "nhl", "nhl-ledger", "nba", "nba-ledger", "nba-props", "odds"))
          and all(default_date(m, dt.date(2026, 10, 19)) == "2026-10-18" for m in ("grade", "nhl-grade", "nba-grade")))
    check("nhl grade: final with the period score", gr2["finals"] == {"fa": "2", "fh": "3", "f5a": "1", "f5h": "0"})
    check("previous season id", nhl_prev_season("20262027") == "20252026")
    # the odds feed, offline: one event document in The Odds API's shape
    ev = {"id": "abc", "commence_time": "2026-10-13T00:10:00Z", "home_team": "Milwaukee Brewers", "away_team": "Los Angeles Dodgers",
          "bookmakers": [{"key": "fanatics", "markets": [
                              {"key": "totals", "outcomes": [{"name": "Over", "price": 100, "point": 7.0}, {"name": "Under", "price": -120, "point": 7.0}]},
                              {"key": "h2h", "outcomes": [{"name": "Milwaukee Brewers", "price": 110}, {"name": "Los Angeles Dodgers", "price": -130}]},
                              {"key": "spreads", "outcomes": [{"name": "Milwaukee Brewers", "price": -165, "point": 1.5}, {"name": "Los Angeles Dodgers", "price": 135, "point": -1.5}]}]},
                         {"key": "draftkings", "markets": [
                              {"key": "totals", "outcomes": [{"name": "Over", "price": -105, "point": 7.0}, {"name": "Under", "price": -115, "point": 7.0}]}]}]}
    per = {"id": "abc", "bookmakers": [{"key": "fanatics", "markets": [{"key": "totals_1st_5_innings", "outcomes": [{"name": "Over", "price": -110, "point": 3.5}, {"name": "Under", "price": -120, "point": 3.5}]}]}]}
    og = odds_game(ev, "MLB", ["fanatics", "betmgm", "draftkings"], per)
    oi = og["inputs"]
    check("odds: the game date is the US date of a UTC start", og["gdate"] == "2026-10-12" and us_game_date("2026-12-01T01:00:00Z") == "2026-11-30" and us_game_date("2026-10-12T23:30:00Z") == "2026-10-12")
    check("odds: nicknames the sheet uses", og["away"] == "Dodgers" and og["home"] == "Brewers" and odds_nick("Columbus Blue Jackets") == "Blue Jackets" and odds_nick("Utah Mammoth") == "Mammoth" and odds_nick("Boston Red Sox") == "Red Sox" and odds_nick("Portland Trail Blazers") == "Trail Blazers")
    check("odds: the carded book's total, prices, moneyline and run line", og["book"] == "fanatics" and oi["line"] == "7.0" and oi["op"] == "100" and oi["up"] == "-120" and oi["hml"] == "110" and oi["aml"] == "-130" and oi["rl"] == "1.5" and oi["rlh"] == "-165" and oi["rla"] == "135")
    check("odds: the period market", oi["f5line"] == "3.5" and oi["f5op"] == "-110" and oi["f5up"] == "-120")
    shop = json.loads(oi["odds"])
    check("odds: every book's price on each side for the shop", [x[0] for x in shop["total"]["UNDER"]] == ["fanatics", "draftkings"] and shop["total"]["UNDER"][1][1] == -115 and shop["period"]["OVER"][0][1] == -110 and shop["ml"]["HOME"][0][1] == 110)
    import tempfile
    tmp = os.path.join(tempfile.mkdtemp(), "odds-log.json")
    e1 = odds_log_update(tmp, og, "2026-10-12T15:00:00Z")
    og2 = json.loads(json.dumps(og)); og2["inputs"]["line"] = "6.5"; og2["inputs"]["up"] = "105"
    e2 = odds_log_update(tmp, og2, "2026-10-12T22:00:00Z")
    check("odds log: the first number seen is the opener, the latest the close candidate", e1["first"]["line"] == "7.0" and e2["first"]["line"] == "7.0" and e2["last"]["line"] == "6.5" and e2["last"]["at"] == "2026-10-12T22:00:00Z")
    check("odds log: the grade run reads the close", odds_close_for(tmp, "MLB", "2026-10-12", "Dodgers", "Brewers") == {"ctot": "6.5", "cf5": "3.5"} and odds_close_for(tmp, "NHL", "2026-10-12", "Dodgers", "Brewers") is None)
    check("odds: a game no book has priced carries a note and no line", odds_game({"id": "x", "commence_time": "2026-10-13T00:00:00Z", "home_team": "A B", "away_team": "C D", "bookmakers": []}, "NHL", ["fanatics"])["notes"] == ["No book in the list has priced this game yet."])
    # the rest of the subscription (13 Oct 2026): the sharp book, the alternates, the team totals, the credits, the history
    ev2 = json.loads(json.dumps(ev))
    ev2["bookmakers"].insert(0, {"key": "pinnacle", "markets": [
        {"key": "totals", "outcomes": [{"name": "Over", "price": -108, "point": 7.5}, {"name": "Under", "price": -112, "point": 7.5}]},
        {"key": "h2h", "outcomes": [{"name": "Milwaukee Brewers", "price": 115}, {"name": "Los Angeles Dodgers", "price": -125}]}]})
    extra = {"id": "abc", "bookmakers": [{"key": "fanatics", "markets": [
        {"key": "totals_1st_5_innings", "outcomes": [{"name": "Over", "price": -110, "point": 3.5}, {"name": "Under", "price": -120, "point": 3.5}]},
        {"key": "alternate_totals", "outcomes": [{"name": "Over", "price": -150, "point": 6.5}, {"name": "Under", "price": 125, "point": 6.5},
                                                 {"name": "Over", "price": 130, "point": 7.5}, {"name": "Under", "price": -155, "point": 7.5}]},
        {"key": "team_totals", "outcomes": [{"name": "Over", "description": "Milwaukee Brewers", "price": -115, "point": 3.5}, {"name": "Under", "description": "Milwaukee Brewers", "price": -105, "point": 3.5},
                                            {"name": "Over", "description": "Los Angeles Dodgers", "price": -120, "point": 4.5}]}]}]}
    og3 = odds_game(ev2, "MLB", ["pinnacle", "fanatics", "draftkings"], extra)
    sh3, shop3 = json.loads(og3["inputs"]["sharp"]), json.loads(og3["inputs"]["odds"])
    check("odds: the sharp book is read beside the carded line, never carded", og3["book"] == "fanatics" and shop3["book"] == "fanatics" and sh3["book"] == "pinnacle" and sh3["line"] == 7.5 and sh3["op"] == -108 and sh3["hml"] == 115)
    check("odds: a sharp line off the carded one is noted, shown not scored", any(n.startswith("Pinnacle has the total at 7.5 (-108/-112) against the carded 7.0: the sharp line sits higher.") for n in og3["notes"]))
    check("odds: the alternate totals ride in the shop with their prices", [x[2] for x in shop3["alt"]["UNDER"]] == [6.5, 7.5] and shop3["alt"]["OVER"][1][1] == 130)
    check("odds: the team totals ride as each side's own number", shop3["team"]["HOME"]["OVER"][0] == ["fanatics", -115, 3.5] and shop3["team"]["AWAY"]["OVER"][0][2] == 4.5 and "UNDER" not in shop3["team"]["AWAY"])
    check("odds: the period total still fills beside them", og3["inputs"]["f5line"] == "3.5")
    check("odds: the main period line is the number most books post, not one book's alternate, at the first book in the list that posts it",
          odds_main_line([("betmgm", "Over", "", 240, 2.5), ("betmgm", "Under", "", -325, 2.5), ("draftkings", "Over", "", -130, 1.5), ("draftkings", "Under", "", 100, 1.5),
                          ("pinnacle", "Over", "", -122, 1.5), ("pinnacle", "Under", "", 104, 1.5)], ["fanatics", "betmgm", "draftkings"]) == (1.5, -130, 100, "draftkings")
          and odds_main_line([("betmgm", "Over", "", 240, 2.5)], ["betmgm"]) is None and odds_main_line([], ["fanatics"]) is None)
    e3 = odds_log_update(tmp, og3, "2026-10-12T23:00:00Z")
    check("odds log: the sharp book's number rides in the log", e3["last"]["sharp"] == {"line": "7.5", "op": "-108", "up": "-112"} and e3["first"]["line"] == "7.0")
    _last_headers.clear()
    _last_headers.update({"x-requests-last": "3", "x-requests-remaining": "19987"})
    check("odds: the credits come off the headers", odds_credits() == (3, 19987))
    check("odds history: the snapshot stamps", odds_history_at("2025-10-08", "16:00") == "2025-10-08T16:00:00Z" and odds_history_at("2025-10-08", "+02:30") == "2025-10-09T02:30:00Z")
    hist = {"pulled": {}, "games": {}}
    got, ts = odds_history_add(hist, "NHL", {"timestamp": "2025-10-08T15:55:00Z", "data": [{"commence_time": "2025-10-08T23:00:00Z", "home_team": "Boston Bruins", "away_team": "New York Rangers", "bookmakers": [
        {"key": "fanatics", "markets": [{"key": "totals", "outcomes": [{"name": "Over", "price": -110, "point": 6.0}, {"name": "Under", "price": -110, "point": 6.0}]}]},
        {"key": "pinnacle", "markets": [{"key": "totals", "outcomes": [{"name": "Over", "price": -105, "point": 6.5}, {"name": "Under", "price": -115, "point": 6.5}]},
                                        {"key": "h2h", "outcomes": [{"name": "Boston Bruins", "price": -130}, {"name": "New York Rangers", "price": 110}]}]}]}]}, "2025-10-08 16:00")
    hg = hist["games"]["NHL|2025-10-08|Rangers @ Bruins"]
    check("odds history: a snapshot folds in per game, per book", got == 1 and ts == "2025-10-08T15:55:00Z" and hg["snaps"][ts]["fanatics"] == [6.0, -110, -110]
          and hg["snaps"][ts]["pinnacle"] == [6.5, -105, -115, -130, 110] and hist["pulled"]["2025-10-08 16:00"]["games"] == 1)
    hist_nba = {"pulled": {}, "games": {}}
    got_n, ts_n = odds_history_add(hist_nba, "NBA", {"timestamp": "2024-10-22T22:30:00Z", "data": [{"commence_time": "2024-10-22T23:30:00Z", "home_team": "Boston Celtics", "away_team": "New York Knicks", "bookmakers": [
        {"key": "fanatics", "markets": [{"key": "h2h", "outcomes": [{"name": "Boston Celtics", "price": -320}, {"name": "New York Knicks", "price": 255}]}]},
        {"key": "pinnacle", "markets": [{"key": "h2h", "outcomes": [{"name": "Boston Celtics", "price": -300}, {"name": "New York Knicks", "price": 265}]}]}]}]}, "2024-10-22 22:30")
    hgn = hist_nba["games"].get("NBA|2024-10-22|Knicks @ Celtics") or {"snaps": {}}
    check("odds history (NBA): a moneyline-only snapshot folds in with the totals blank and the two prices, keyed like the ledger", got_n == 1 and hgn["snaps"].get(ts_n, {}).get("fanatics") == [None, None, None, -320, 255]
          and hgn["snaps"][ts_n]["pinnacle"] == [None, None, None, -300, 265] and hgn["away"] == "Knicks" and hgn["home"] == "Celtics")
    tmp_h = tempfile.mkdtemp()
    with open(nba_ledger_path(tmp_h, "2026-27"), "w", encoding="utf-8") as f:
        json.dump({"format": NBA_LEDGER_FORMAT, "season": "2026-27", "games": [{"id": str(k), "date": "2026-10-%02d" % d} for k, d in enumerate([13, 13, 14, 15, 16, 17, 18, 19, 20])]}, f)
    nba_hist_dates = odds_history_dates("NBA", "2026-27", tmp_h)
    check("odds history (NBA): the dates come from the NBA ledger's game days (the season spelt either way), the calendar without one",
          nba_hist_dates[0] == "2026-10-13" and nba_hist_dates[-1] == "2026-10-20" and len(nba_hist_dates) == 8 and odds_history_dates("NBA", "202627", tmp_h) == nba_hist_dates
          and odds_history_dates("NBA", "2024-25", tempfile.mkdtemp())[0] == "2024-10-20" and odds_history_dates("NBA", "2024-25", tempfile.mkdtemp())[-1] == "2025-04-15"
          and odds_history_path(tempfile.mkdtemp(), "NBA", "2024-25").endswith("odds-history-NBA-2024-25.json"))
    check("odds history: the dates come from the calendar without a ledger, or from the range", odds_history_dates("NHL", "20252026", tempfile.mkdtemp())[0] == "2025-10-01"
          and odds_history_dates("NHL", "x", ".", "2025-10-08", "2025-10-10") == ["2025-10-08", "2025-10-09", "2025-10-10"])
    # the NBA ledger (15 Oct 2026), offline: the feed's shapes, canned
    check("nba: the season from a date", nba_season_id("2026-10-15") == "2026-27" and nba_season_id("2027-04-10") == "2026-27" and nba_season_id("2027-07-01") == "2026-27" and nba_season_id("2027-08-15") == "2027-28")
    check("nba: season spellings", nba_norm_season("2024-25") == "2024-25" and nba_norm_season("2024") == "2024-25" and nba_norm_season("20242025") == "2024-25" and nba_norm_season("202425") == "2024-25")
    check("nba: minutes in the feed's shapes", abs(nba_minutes("PT34M12.00S") - 34.2) < 1e-9 and abs(nba_minutes("34:30") - 34.5) < 1e-9 and nba_minutes("") == 0.0 and nba_minutes(None) == 0.0 and nba_minutes("PT00M00.00S") == 0.0 and abs(nba_minutes("PT240M") - 240.0) < 1e-9)
    # (90 - 10 + 12 + 0.44 x 25 = 103.0) and (86 - 8 + 14 + 0.44 x 20 = 100.8): 101.9 a side over 48 minutes
    check("nba: pace from the two box lines", nba_pace({"fga": 90, "fta": 25, "oreb": 10, "tov": 12, "min": 240.0}, {"fga": 86, "fta": 20, "oreb": 8, "tov": 14, "min": 240.0}) == 101.9
          and nba_pace({"fga": 90, "fta": 25, "oreb": 10, "tov": 12, "min": 265.0}, {"fga": 86, "fta": 20, "oreb": 8, "tov": 14, "min": 265.0}) == round(101.9 * 48 / 53.0, 1))
    nba_canned = _canned_nba()
    def fake_nba(url, tries=3, headers=None, timeout=25, cache=True):
        for key, payload in nba_canned:
            if key in url:
                return payload
        raise RuntimeError("no canned payload for " + url)
    check("nba: the US date from the box score's Eastern clock, or UTC less five hours",
          nba_box_date({"gameEt": "2024-10-22T19:30:00Z"}) == "2024-10-22" and nba_box_date({"gameTimeUTC": "2024-10-23T02:30:00Z"}) == "2024-10-22" and nba_box_date({}) is None)
    fetch_json = fake_nba
    try:
        gl = nba_games_from_log("2024-25")
        lines3 = []
        e1 = nba_game_entry(gl[0], lines3.append)       # the CDN box score
        e2 = nba_game_entry(gl[1], lines3.append)       # not on the CDN: the stats site's two documents
        sch = nba_games_from_schedule("2026-10-25")
    finally:
        fetch_json = real
    check("nba log: one entry a game from two rows, home and away by the matchup", len(gl) == 2 and gl[0] == {"id": "0022400001", "date": "2024-10-22", "away": "NYK", "home": "BOS", "fa": 109, "fh": 132}
          and gl[1]["home"] == "LAL" and gl[1]["away"] == "MIN" and gl[1]["fa"] == 103)
    check("nba box (CDN): quarters, overtime, the end, the team lines and pace",
          e1["qa"] == [28, 25, 30, 26] and e1["qh"] == [35, 31, 33, 33] and e1["ota"] == [] and e1["end"] == "REG" and e1["sa"]["fga"] == 90 and e1["sh"]["tov"] == 14 and e1["pace"] == 101.9 and e1["detail"] is True)
    check("nba box (CDN): every man who played with his minutes, starters flagged; the inactive and the DNPs listed with the reason",
          e1["pa"][0][:6] == [201, "Jalen B", 1, 34.2, 25, -12] and e1["pa"][1][2] == 0 and len(e1["pa"]) == 2 and e1["oa"] == [[203, "Hurt Guy", "Injury/Illness - Left Knee"], [204, "Benched Guy", "DNP - Coach's Decision"]]
          and e1["ph"][0][1] == "Jayson T" and e1["oh"] == [])
    check("nba box: the player line carries the box stats (19 Oct 2026) and reads as a dict either length",
          len(e1["pa"][0]) == 17 and nba_player_dict(e1["pa"][0])["full"] is True and nba_player_dict(e1["pa"][0])["reb"] == 0
          and nba_player_dict([201, "Jalen B", 1, 34.2, 25, -12]) == {"id": "201", "n": "Jalen B", "st": 1, "min": 34.2, "pts": 25, "pm": -12, "reb": None, "ast": None, "tpm": None, "fga": None, "fta": None, "tov": None, "stl": None, "blk": None, "fgm": None, "ftm": None, "pos": None, "full": False}
          and nba_player_line("9", "X", True, 31.26, "20", None, reb="7", pos="PG") == ["9", "X", 1, 31.3, 20, 0, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, "PG"])
    check("nba box (stats site): quarters from the summary's line score, starters by position, the DNP comment",
          e2["qa"] == [20, 30, 25, 28] and e2["qh"] == [30, 28, 20, 25] and e2["ota"] == [5] and e2["oth"] == [10] and e2["end"] == "OT" and e2["pa"][0][:6] == [301, "Anthony E", 1, 38.5, 30, 4] and len(e2["pa"][0]) == 17
          and e2["oa"] == [[302, "Sat Out", "DNP - Injury/Illness"]] and e2["pace"] is not None and e2["detail"] is True and any("trying the stats site" in l for l in lines3))
    check("nba schedule (CDN): this season's finals only, dates normalised", sch == [{"id": "0022600003", "date": "2026-10-22", "away": "GSW", "home": "LAL", "fa": 110, "fh": 115}])
    check("nba box: tip-off and the crew ride along for the rest, travel and referee tests",
          e1["t"] == "2024-10-22T23:30:00Z" and e1["off"] == ["Scott Foster", "Tony Brothers"] and e2["off"] == ["Marc Davis"] and e2["t"] is None)
    m3 = nba_measure([e1, e2])
    check("nba measure: points, home margin, overtime, the first half's share, pace", m3["games"] == 2 and m3["points_per_game"] == (241 + 211) / 2.0 and m3["home_margin"] == (23 + 5) / 2.0 and m3["ot_rate"] == 0.5
          and abs(m3["first_half_share"] - (28 + 25 + 35 + 31 + 20 + 30 + 30 + 28) / float(241 + 206)) < 1e-9 and m3["pace"] is not None)
    tmp3 = tempfile.mkdtemp()
    # the stats site's game log as the source (ESPN's scoreboard not answering): the CDN box for one game, the stats documents for the other
    canned_no_espn = [x for x in nba_canned if not x[0].startswith("scoreboard?")]
    def fake_nba_noespn(url, tries=3, headers=None, timeout=25, cache=True):
        for key, payload in canned_no_espn:
            if key in url:
                return payload
        raise RuntimeError("no canned payload for " + url)
    fetch_json = fake_nba_noespn
    try:
        lines4 = []
        p3 = make_nba_ledger("2026-10-15", tmp3, lines4.append, "2024-25")
        with open(p3, "r", encoding="utf-8") as f:
            led3 = json.load(f)
        p4 = make_nba_ledger("2026-10-15", tmp3, lines4.append, "2024-25")   # again: nothing to fetch
    finally:
        fetch_json = real
    check("nba ledger (stats log): a past season's file, with detail, the measure and the through date; a second run fetches nothing",
          led3["format"] == NBA_LEDGER_FORMAT and led3["season"] == "2024-25" and len(led3["games"]) == 2 and led3["through"] == "2025-06-30" and led3["measure"]["games"] == 2
          and os.path.basename(p3) == "nba-ledger-202425.json" and p4 == p3 and any("0 games to fetch" in l for l in lines4) and any("League game log: 2" in l for l in lines4))
    # neither ESPN nor the stats site: the ids are walked on the CDN; only the first game has a box there
    canned_no_log = [x for x in nba_canned if x[0] not in ("leaguegamelog", "scoreboard?dates=20241022&")]
    def fake_nba_nolog(url, tries=3, headers=None, timeout=25, cache=True):
        for key, payload in canned_no_log:
            if key in url:
                return payload
        raise RuntimeError("no canned payload for " + url)
    fetch_json = fake_nba_nolog
    try:
        tmp4 = tempfile.mkdtemp()
        lines5 = []
        p5 = make_nba_ledger("2026-10-15", tmp4, lines5.append, "2024-25")
        with open(p5, "r", encoding="utf-8") as f:
            led5 = json.load(f)
    finally:
        fetch_json = real
    check("nba ledger: with neither ESPN nor the stats site the ids are walked on the CDN, the date read from the box, and the walk stops after the gap",
          any("walking the season's game ids" in l for l in lines5) and len(led5["games"]) == 1 and led5["games"][0]["id"] == "0022400001" and led5["games"][0]["date"] == "2024-10-22"
          and led5["games"][0]["away"] == "NYK" and led5["games"][0]["fa"] == 109 and any("1 box score read" in l for l in lines5))
    # ESPN, the way a past season is read now (15 Oct 2026, after the CDN walk found no 2024-25 box scores)
    check("nba espn: tricodes and the US date", espn_tricode("GS") == "GSW" and espn_tricode("ny") == "NYK" and espn_tricode("BOS") == "BOS" and nba_us_date("2024-10-23T02:30Z") == "2024-10-22" and nba_us_date("2024-10-22T23:30Z") == "2024-10-22")
    fetch_json = fake_nba
    try:
        eg = nba_games_from_espn("2024-25", "2024-10-28")
        es = nba_entry_from_espn(eg[0], fetch_json(ESPN_NBA + "/summary?event=401704001"))
        tmp5 = tempfile.mkdtemp()
        lines6 = []
        p6 = make_nba_ledger("2026-10-15", tmp5, lines6.append, "2024-25")
        with open(p6, "r", encoding="utf-8") as f:
            led6 = json.load(f)
    finally:
        fetch_json = real
    check("nba espn: the scoreboard lists regular-season finals only, with nicknames", len(eg) == 1 and eg[0]["id"] == "401704001" and eg[0]["date"] == "2024-10-22" and eg[0]["away"] == "NYK" and eg[0]["home"] == "BOS"
          and eg[0]["an"] == "Knicks" and eg[0]["hn"] == "Celtics" and eg[0]["fa"] == 109 and eg[0]["fh"] == 132)
    check("nba espn: quarters from the line scores, the box lines and pace", es["qa"] == [28, 25, 30, 26] and es["qh"] == [35, 31, 33, 33] and es["ota"] == [] and es["end"] == "REG"
          and es["sa"] == {"fga": 90, "fta": 25, "oreb": 10, "tov": 12, "min": 240.0} and es["sh"]["tov"] == 14 and es["pace"] == 101.9 and es["detail"] is True)
    check("nba espn: every man who played with his minutes, starters flagged; the DNPs and the injury list as who sat; the crew",
          es["pa"] == [["3934672", "Jalen Brunson", 1, 34.0, 25, -12, 3, 8, 2, 18, 5, 2, 1, 0, 9, 5, "PG"], ["1", "Bench Guy", 0, 12.0, 4, -3, 2, 0, 0, 4, 0, 0, 0, 0, 2, 0, ""]]
          and es["oa"] == [["2", "Benched Guy", "COACH'S DECISION"], ["3", "Hurt Guy", "Out - Knee"]]
          and es["ph"] == [["4065648", "Jayson Tatum", 1, 36.0, 37, 20, 4, 10, 8, 18, 1, 1, 1, 0, 14, 1, ""]] and es["oh"] == [] and es["off"] == ["Scott Foster", "Tony Brothers"] and es["t"] == "2024-10-22T23:30Z")
    check("nba ledger: a past season reads from ESPN first", any("ESPN scoreboard: 1 regular-season finals listed" in l for l in lines6) and len(led6["games"]) == 1 and led6["games"][0]["id"] == "401704001"
          and led6["games"][0]["hn"] == "Celtics" and led6["games"][0]["detail"] is True and led6["measure"]["games"] == 1)
    # the NBA slate and the morning grade (15 Oct 2026), offline: the scoreboard, the injury page and two small ledgers
    check("nba slate: nicknames to tricodes and the stage of the season", nba_nick_tricode("Portland Trail Blazers") == "POR" and nba_nick_tricode("Jazz") == "UTA" and nba_nick_tricode("Nowhere Club") is None
          and nba_stage("2026-12-10") is None and nba_stage("2027-03-01") == "after the trade deadline: +1.0 on the line" and nba_stage("2027-04-06").startswith("the last two weeks") and nba_stage("2027-05-01") is None
          and nba_prev_season("2026-27") == "2025-26")
    slate_canned, led_now, led_prior = _canned_nba_slate()
    def fake_nba_slate(url, tries=3, headers=None, timeout=25, cache=True):
        for key, payload in slate_canned:
            if key in url:
                return payload
        raise RuntimeError("no canned payload for " + url)
    tmp7 = tempfile.mkdtemp()
    for season, games in (("2026-27", led_now), ("2025-26", led_prior)):
        with open(nba_ledger_path(tmp7, season), "w", encoding="utf-8") as f:
            json.dump({"format": NBA_LEDGER_FORMAT, "season": season, "through": games[-1]["date"], "games": games}, f)
    with open(odds_log_path(tmp7), "w", encoding="utf-8") as f:
        json.dump({odds_log_key("NBA", "2026-10-22", "Celtics", "Knicks"): {"first": {"line": "223.0"}, "last": {"line": "221.5", "op": "-110", "up": "-110", "h1line": "110.5", "at": "2026-10-21T23:00:00Z", "book": "fanatics"}},
                   # closes for two of the synthetic finals: Celtics @ Knicks 115-114 (over 225.5, Zarba's crew), Lakers @ Warriors 113-112 (under 230, Foster's crew)
                   odds_log_key("NBA", "2026-10-13", "Celtics", "Knicks"): {"last": {"line": "225.5"}}, odds_log_key("NBA", "2026-10-13", "Lakers", "Warriors"): {"last": {"line": "230"}}}, f)
    fetch_json = fake_nba_slate
    try:
        day = nba_day_games("2026-10-21")
        tabs7, lg7 = nba_team_tables(led_now, "2026-10-21")
        lines7 = []
        p7 = make_nba_slate("2026-10-21", tmp7, lines7.append)
        with open(p7, "r", encoding="utf-8") as f:
            sl7 = json.load(f)
        lines8 = []
        p8 = make_nba_grade("2026-10-22", tmp7, lines8.append)
        with open(p8, "r", encoding="utf-8") as f:
            gr8 = json.load(f)
        lines9 = []
        bare = build_nba_game(day[1], "2026-10-21", {}, None, {}, {}, {}, lines9.append, have_ledger=False)
    finally:
        fetch_json = real
    check("nba slate: the scoreboard for a day, finals and scheduled games alike, on the US date with the half-time score",
          len(day) == 4 and day[0]["final"] is True and day[0]["ha"] == 51 and day[0]["hh"] == 49 and day[0]["fa"] == 101 and day[0]["date"] == "2026-10-21"
          and day[1]["final"] is False and day[1]["state"] == "Scheduled" and day[1]["away"] == "BOS" and day[1]["home"] == "NYK" and day[1]["hn"] == "Knicks" and day[1]["venue"] == "Madison Square Garden"
          and day[3]["home"] == "UTA" and day[3]["type"] == 1)
    check("nba slate: the team tables from the ledger (Boston 120.0 per 100 on six games, the slowest; San Antonio the fastest), the league at twenty games",
          tabs7["BOS"]["n"] == 6 and round(tabs7["BOS"]["ortg"], 1) == 120.0 and tabs7["BOS"]["last"] == "2026-10-20" and tabs7["BOS"]["pace"] < tabs7["SAS"]["pace"] and tabs7["POR"]["n"] == 2
          and tabs7["SAS"]["n"] == 7 and tabs7["SAS"]["hw"] == 2 and lg7 is not None and lg7["n"] == 43 and 100 < lg7["ortg"] < 112 and lg7["ppg"] < 220)
    rows7 = {"%s @ %s" % (g["away"], g["home"]): g for g in sl7["games"]}
    bn = rows7.get("Celtics @ Knicks") or {"inputs": {}, "notes": []}
    check("nba slate: three rows (the final left out), each with the sport, the date, the id and the tip-off",
          len(sl7["games"]) == 3 and set(rows7) == {"Celtics @ Knicks", "Trail Blazers @ Lakers", "Nuggets @ Jazz"} and all(g["sport"] == "NBA" and g["gdate"] == "2026-10-21" for g in sl7["games"])
          and bn["gameId"] == "4019000101" and bn["first_tip_utc"] == "2026-10-22T00:00Z" and os.path.basename(p7) == "nba-slate-2026-10-21.json")
    check("nba slate: the ratings, pace, games and the league fill at five games; both sides on a back to back read rest 0",
          bn["inputs"]["naort"] == "120.0" and bn["inputs"]["nagp"] == "6" and bn["inputs"]["nhgp"] == "6" and bn["inputs"]["narest"] == "0" and bn["inputs"]["nhrest"] == "0"
          and bn["inputs"]["napace"] == "95.8" and bn["inputs"]["nlrtg"] != "" and bn["inputs"]["nlpace"] != "" and float(bn["inputs"]["nhdrt"]) > 100)
    out7 = json.loads(bn["inputs"]["nbaout"]) if bn["inputs"].get("nbaout") else {"away": [], "home": []}
    moved = [e for e in out7["away"] if e["id"] == "7777"]
    star = [e for e in out7["away"] if e["id"] == "9000"]
    rookie = [e for e in out7["away"] if e["id"] == "8888"]
    check("nba slate: the who-is-out list keys each man by his id, so a traded player carries LAST season's line with his old club named, a regular this season's, a rookie none",
          len(out7["away"]) == 3 and len(moved) == 1 and moved[0]["st"] == "Out" and moved[0]["mpg"] == 30.0 and moved[0]["src"] == "last season" and moved[0]["note"] == "Hamstring; with Lakers last season"
          and star[0]["st"] == "Questionable" and star[0]["mpg"] == 34.0 and star[0]["src"] == "this season" and star[0]["g"] == 6 and "mpg" not in rookie[0]
          and out7["away"][0]["id"] == "9000" and len(out7["home"]) == 2 and out7["home"][0]["n"] == "Knicks Star" and out7["home"][0]["st"] == "Day-To-Day")
    check("nba slate: the id is read off the player-card link or the headshot when the page gives none, the name stands in when there is neither, and the page's comment and return date ride along",
          moved[0]["c"] == "Man (hamstring) is out for Wednesday's game against the Knicks." and moved[0]["ret"] == "2026-10-28" and "past" not in moved[0] and "c" not in star[0]
          and rookie[0]["ret"] == "2026-10-19" and rookie[0]["past"] is True
          and [e["id"] for e in out7["home"]] == ["9001", "No Id Man"] and any("Injury report: 2 clubs, 5 players listed" in l for l in lines7)
          and espn_athlete_id({"links": [{"href": "https://www.espn.com/nba/player/_/id/4585618/keshon-gilbert"}]}) == "4585618" and espn_athlete_id({}) == "")
    check("nba slate: the scoreboard's book rides as a note with the opener, fills the Opened box, and a move of a point or more is a context line",
          bn["inputs"]["opened"] == "224.5" and any(n == "Draft Kings on ESPN's scoreboard at the slate run: total 221.5 (-115/-105), opened 224.5; Knicks -1.5 (-108/-112), opened -2.5; moneyline Knicks -115 / Celtics -105. Shown for the opener and as a check on the carded book; the lines come from the odds run." for n in bn["notes"])
          and any(c["k"] == "move" and c["s"] == "shown" and c["t"] == "Draft Kings: the total opened 224.5 and sits 221.5, down 3; Knicks opened -2.5 and sit -1.5." for c in (json.loads(bn["inputs"]["nbactx"]) if bn["inputs"].get("nbactx") else []))
          and _odds_num("o221.5") == 221.5 and _odds_num("u221.5") == 221.5 and _odds_num("+105") == 105.0 and _odds_num("-1.5") == -1.5 and _odds_num("EVEN") == 100.0 and _odds_num(None) is None and _odds_num("x") is None)
    ctx7 = json.loads(bn["inputs"]["nbactx"]) if bn["inputs"].get("nbactx") else []
    kinds7 = [(c["k"], c["side"], c["s"]) for c in ctx7]
    check("nba slate: the context lines carry the tag (Boston's offence faded, pace shown, the back to back a label, the regular out shown)",
          ("ratings_faded", "away", "faded") in kinds7 and ("pace", "away", "shown") in kinds7 and ("rest", "away", "label") in kinds7 and ("rest", "home", "label") in kinds7 and ("out", "away", "shown") in kinds7
          and any(c["t"] == "Celtics score 120.0 per 100 possessions, 1st best in the league (6 games)." for c in ctx7)
          and any(c["t"] == "Celtics without Moved Man: 30 minutes a game of regulars." for c in ctx7) and any(c["t"] == "Celtics on a back to back." for c in ctx7)
          and all("faded" in c["tag"] for c in ctx7 if c["k"] == "ratings_faded"))
    pl = rows7.get("Trail Blazers @ Lakers") or {"inputs": {}, "notes": []}
    dj = rows7.get("Nuggets @ Jazz") or {"inputs": {}, "notes": []}
    check("nba slate: a club with two games keeps its ratings blank with a note; its games and rest still fill, the other side's ratings too; no book on the event, no opener and no note",
          pl["inputs"]["naort"] == "" and pl["inputs"]["nagp"] == "2" and pl["inputs"]["narest"] == "1" and pl["inputs"]["nhort"] != "" and pl["inputs"]["nhgp"] == "5"
          and any(n.startswith("Trail Blazers has 2 games this season: the ratings are left blank until 5") for n in pl["notes"])
          and pl["inputs"]["opened"] == "" and not any("scoreboard" in n for n in pl["notes"]))
    check("nba slate: a preseason game is flagged, and the two watched clubs are named on the row and in the context",
          any(n.startswith("PRESEASON") for n in dj["notes"]) and any(n.startswith("Nuggets: a club the close has run under") for n in dj["notes"]) and any(n.startswith("Jazz: a club") for n in dj["notes"])
          and sum(1 for c in (json.loads(dj["inputs"]["nbactx"]) if dj["inputs"].get("nbactx") else []) if c["k"] == "watched") == 2)
    refs7 = json.loads(bn["inputs"]["nbarefs"]) if bn["inputs"].get("nbarefs") else None
    foster_games = [g for g in led_now if g.get("off") and "Scott Foster" in g["off"]]
    check("nba slate: the referee table from the ledgers rides in the row (each official's games, free throws and points a game, the league's beside), and the crew fills from the league's feed by tricode or game code",
          refs7 is not None and refs7["lg"][0] == 40 and refs7["lg"][1] == 40.0 and set(refs7["r"]) == {"Scott Foster", "Tony Brothers", "Marc Davis", "Zach Zarba", "Eric Dalen", "Jason Goldenberg"}
          and refs7["r"]["Scott Foster"][0] == len(foster_games) and refs7["r"]["Scott Foster"][2] == round(sum(g["fa"] + g["fh"] for g in foster_games) / float(len(foster_games)), 1)
          and refs7["r"]["Scott Foster"][3:] == [66, 41, 0, 1] and refs7["r"]["Zach Zarba"][3:] == [58, 60, 1, 0] and refs7["r"]["Tony Brothers"][5:] == [0, 1]
          and any("Scott Foster 40.0 FTA / " in l and "over the close 66-41 the last two seasons, 0-1 this season" in l for l in lines7)
          and nba_season_ref_ou(led_now, "/nonexistent/odds-log.json") == {} and NBA_REF_OU["Scott Foster"] == [109, 66, 41, 2]
          and bn["inputs"]["ncrew"] == "Scott Foster, Tony Brothers, Marc Davis" and pl["inputs"]["ncrew"] == "Zach Zarba, Eric Dalen, Jason Goldenberg" and dj["inputs"]["ncrew"] == ""
          and any(n.startswith("No crew on the league's feed for this game yet") for n in dj["notes"]) and not any("No crew" in n for n in bn["notes"])
          and any("Crews: 2 games on the league's assignments feed" in l for l in lines7) and any(l.startswith("  crew: Scott Foster 40.0 FTA / ") for l in lines7)
          and bare["inputs"]["ncrew"] == "" and not any("No crew" in n for n in bare["notes"]))
    check("nba slate: the printout names the ledger, the injury report and each game", any("Ledger 2026-27: 43 games" in l for l in lines7) and any("Injury report: 2 clubs, 5 players listed" in l for l in lines7)
          and any(l.startswith("Celtics @ Knicks  (Madison Square Garden") for l in lines7) and any("Wrote" in l and "3 games" in l for l in lines7))
    check("nba slate: without a ledger or the injury page the row says so and the boxes stay blank", bare["inputs"]["naort"] == "" and bare["inputs"]["nagp"] == "0" and bare["inputs"]["nbaout"] == '{"away":[],"home":[]}'
          and any("injury report could not be read" in n for n in bare["notes"]) and not any("no game in the ledger" in n for n in bare["notes"]))
    g8 = {"%s @ %s" % (g["away"], g["home"]): g for g in gr8["games"]}
    check("nba grade: the finals with the half-time score from the line scores, or from the summary when the scoreboard has none; the close attached; a game not played skipped",
          len(gr8["games"]) == 2 and g8["Celtics @ Knicks"]["finals"] == {"fa": "110", "fh": "105", "f5a": "55", "f5h": "55"} and g8["Celtics @ Knicks"]["close"] == {"ctot": "221.5", "cf5": "110.5"}
          and g8["Warriors @ Lakers"]["finals"] == {"fa": "120", "fh": "118", "f5a": "58", "f5h": "58"} and "close" not in g8["Warriors @ Lakers"] and g8["Warriors @ Lakers"]["sport"] == "NBA"
          and any("Mavericks @ Suns: Scheduled, not final; skipped" in l for l in lines8) and os.path.basename(p8) == "nba-grade-2026-10-22.json")
    fetch_json = fake_nhl
    try:
        sjs = nhl_club_goalies("SJS", "20262027")
    finally:
        fetch_json = real
    check("a team with no games falls back to last season's goalies still on the roster, shots halved",
          len(sjs) == 1 and sjs[0]["name"] == "Yaroslav A" and sjs[0]["shots"] == 800 and sjs[0]["season"] == "20252026")
    fetch_json = fake_nhl
    try:
        _LANDING_CACHE.clear()
        scanned = nhl_ledger_scan("2026-10-06", "2026-10-06", set(), lines2.append)
    finally:
        fetch_json = real
    check("ledger: a week's scan takes the finals, with periods, shots and the empty-net goal",
          len(scanned) == 1 and scanned[0]["id"] == 2026020005 and scanned[0]["fa"] == 2 and scanned[0]["fh"] == 3
          and scanned[0]["p1a"] == 1 and scanned[0]["p3h"] == 1 and scanned[0]["sa"] == 29 and scanned[0]["enh"] == 1 and scanned[0]["end"] == "REG")
    # the slate fills the first-period last ten from a ledger with enough games
    fetch_json = fake_nhl
    try:
        led_games = [dict(synthetic[0], date="2026-09-%02d" % d, p1a=1, p1h=1) for d in range(21, 28)]
        row3 = build_nhl_game(nhl_schedule("2026-10-07")[0], "2026-10-07", "20262027", nhl_team_summary("20262027"), lines2.append, led_games)
    finally:
        fetch_json = real
    check("ledger: the slate fills each side's first-period last ten (2.00 on seven games)", row3["inputs"]["ap1l10"] == "2.00" and row3["inputs"]["hp1l10"] == "2.00")
    check("nhl empty-net habits: the slate leaves them blank under ten finals", row3["inputs"]["aenc"] == "" and any("empty-net habits are left blank until 10" in n for n in row3["notes"]))
    fetch_json = fake_nhl
    try:
        row4 = build_nhl_game(nhl_schedule("2026-10-07")[0], "2026-10-07", "20262027", nhl_team_summary("20262027"), lines2.append, None, (rates, lg))
    finally:
        fetch_json = real
    i4 = row4["inputs"]
    check("moneypuck: the slate fills the xG boxes for a club with five games and leaves a four-game club blank, with the league mean beside them",
          i4["axgf"] == "2.50" and i4["axga"] == "3.50" and i4["hxgf"] == "" and i4["hxga"] == "" and i4["xglg"] == "2.97"
          and any("expected goals left blank until 5" in n for n in row4["notes"]))
    check("ledger: without a ledger the slate says so", any("No league ledger" in n for n in row["notes"]))

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


def _canned_nba():
    """Two games of 2024-25 in the feeds' shapes: the league game log (two rows
    a game), a CDN box score for the first, the stats site's traditional box
    score and summary for the second, and this season's CDN schedule."""
    heads = ["SEASON_ID", "TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME", "GAME_ID", "GAME_DATE", "MATCHUP", "WL", "MIN", "PTS", "PLUS_MINUS"]
    log = {"resultSets": [{"name": "LeagueGameLog", "headers": heads, "rowSet": [
        ["22024", 1610612752, "NYK", "New York Knicks", "0022400001", "2024-10-22", "NYK @ BOS", "L", 240, 109, -23],
        ["22024", 1610612738, "BOS", "Boston Celtics", "0022400001", "2024-10-22", "BOS vs. NYK", "W", 240, 132, 23],
        ["22024", 1610612750, "MIN", "Minnesota Timberwolves", "0022400002", "2024-10-22", "MIN @ LAL", "L", 265, 103, -5],
        ["22024", 1610612747, "LAL", "Los Angeles Lakers", "0022400002", "2024-10-22", "LAL vs. MIN", "W", 265, 108, 5],
        ["22024", 1610612747, "LAL", "Los Angeles Lakers", "0012400002", "2024-10-10", "LAL vs. PHX", "W", 240, 100, 1]]}]}   # preseason: ignored

    def player(pid, name, starter, mins, pts, pm, status="ACTIVE", reason=None):
        p = {"personId": pid, "name": name, "starter": "1" if starter else "0", "status": status,
             "statistics": {"minutes": mins, "points": pts, "plusMinusPoints": pm}}
        if reason:
            p["notPlayingReason"] = reason
        return p
    box1 = {"game": {"gameId": "0022400001", "gameStatus": 3, "gameTimeUTC": "2024-10-22T23:30:00Z", "gameEt": "2024-10-22T19:30:00Z",
                     "officials": [{"personId": 1, "name": "Scott Foster", "assignment": "OFFICIAL1"}, {"personId": 2, "name": "Tony Brothers", "assignment": "OFFICIAL2"}],
                     "awayTeam": {"teamTricode": "NYK", "score": 109, "periods": [{"period": k, "periodType": "REGULAR", "score": s} for k, s in enumerate([28, 25, 30, 26], 1)],
                                  "statistics": {"fieldGoalsAttempted": 90, "freeThrowsAttempted": 25, "reboundsOffensive": 10, "turnovers": 12, "minutes": "PT240M00.00S"},
                                  "players": [player(201, "Jalen B", True, "PT34M12.00S", 25, -12), player(202, "Bench Guy", False, "PT12M00.00S", 4, -3),
                                              player(203, "Hurt Guy", False, "PT00M00.00S", 0, 0, "INACTIVE", "Injury/Illness - Left Knee"),
                                              player(204, "Benched Guy", False, "", 0, 0, "ACTIVE", "DNP - Coach's Decision")]},
                     "homeTeam": {"teamTricode": "BOS", "score": 132, "periods": [{"period": k, "periodType": "REGULAR", "score": s} for k, s in enumerate([35, 31, 33, 33], 1)],
                                  "statistics": {"fieldGoalsAttempted": 86, "freeThrowsAttempted": 20, "reboundsOffensive": 8, "turnovers": 14, "minutes": "PT240M00.00S"},
                                  "players": [player(101, "Jayson T", True, "PT36M30.00S", 37, 20)]}}}
    trad2 = {"boxScoreTraditional": {"gameId": "0022400002",
                                     "awayTeam": {"teamTricode": "MIN", "statistics": {"fieldGoalsAttempted": 95, "freeThrowsAttempted": 22, "reboundsOffensive": 11, "turnovers": 13, "minutes": "265:00"},
                                                  "players": [{"personId": 301, "firstName": "Anthony", "familyName": "E", "position": "G", "comment": "", "statistics": {"minutes": "38:30", "points": 30, "plusMinusPoints": 4}},
                                                              {"personId": 302, "firstName": "Sat", "familyName": "Out", "position": "", "comment": "DNP - Injury/Illness", "statistics": {"minutes": "", "points": 0, "plusMinusPoints": 0}}]},
                                     "homeTeam": {"teamTricode": "LAL", "statistics": {"fieldGoalsAttempted": 92, "freeThrowsAttempted": 30, "reboundsOffensive": 9, "turnovers": 10, "minutes": "265:00"},
                                                  "players": [{"personId": 401, "firstName": "LeBron", "familyName": "J", "position": "F", "comment": "", "statistics": {"minutes": "40:00", "points": 28, "plusMinusPoints": 6}}]}}}
    lh = ["GAME_ID", "TEAM_ID", "TEAM_ABBREVIATION", "PTS_QTR1", "PTS_QTR2", "PTS_QTR3", "PTS_QTR4", "PTS_OT1", "PTS_OT2", "PTS"]
    summ2 = {"resultSets": [{"name": "GameSummary", "headers": ["GAME_ID"], "rowSet": [["0022400002"]]},
                            {"name": "LineScore", "headers": lh, "rowSet": [["0022400002", 1610612750, "MIN", 20, 30, 25, 28, 5, 0, 108], ["0022400002", 1610612747, "LAL", 30, 28, 20, 25, 10, 0, 113]]},
                            {"name": "Officials", "headers": ["OFFICIAL_ID", "FIRST_NAME", "LAST_NAME", "JERSEY_NUM"], "rowSet": [[3, "Marc", "Davis", "8"]]}]}
    sched = {"leagueSchedule": {"seasonYear": "2026-27", "gameDates": [
        {"gameDate": "10/22/2026 00:00:00", "games": [
            {"gameId": "0022600003", "gameStatus": 3, "gameDateEst": "2026-10-22T00:00:00Z", "awayTeam": {"teamTricode": "GSW", "score": 110}, "homeTeam": {"teamTricode": "LAL", "score": 115}},
            {"gameId": "0022600004", "gameStatus": 1, "gameDateEst": "2026-10-22T00:00:00Z", "awayTeam": {"teamTricode": "BOS", "score": 0}, "homeTeam": {"teamTricode": "NYK", "score": 0}}]},
        {"gameDate": "10/28/2026 00:00:00", "games": [
            {"gameId": "0022600050", "gameStatus": 3, "gameDateEst": "2026-10-28T00:00:00Z", "awayTeam": {"teamTricode": "MIA", "score": 99}, "homeTeam": {"teamTricode": "CHI", "score": 101}}]}]}}
    # ESPN: one week of the scoreboard with a regular-season final, a preseason game and a game not yet played; its summary
    def comp(ab, name, home, score, ls):
        return {"homeAway": "home" if home else "away", "team": {"abbreviation": ab, "name": name, "displayName": name}, "score": score,
                "linescores": [{"displayValue": str(x), "value": float(x)} for x in ls]}
    espn_sb = {"events": [
        {"id": "401704001", "date": "2024-10-22T23:30Z", "season": {"year": 2025, "type": 2},
         "competitions": [{"id": "401704001", "date": "2024-10-22T23:30Z", "status": {"type": {"completed": True, "name": "STATUS_FINAL"}},
                           "competitors": [comp("BOS", "Celtics", True, "132", [35, 31, 33, 33]), comp("NY", "Knicks", False, "109", [28, 25, 30, 26])]}]},
        {"id": "401700001", "date": "2024-10-10T23:00Z", "season": {"year": 2025, "type": 1},
         "competitions": [{"id": "401700001", "date": "2024-10-10T23:00Z", "status": {"type": {"completed": True}}, "competitors": [comp("LAL", "Lakers", True, "100", []), comp("PHX", "Suns", False, "99", [])]}]},
        {"id": "401704002", "date": "2024-10-23T02:30Z", "season": {"year": 2025, "type": 2},
         "competitions": [{"id": "401704002", "date": "2024-10-23T02:30Z", "status": {"type": {"completed": False}}, "competitors": [comp("LAL", "Lakers", True, "0", []), comp("MIN", "Timberwolves", False, "0", [])]}]}]}
    espn_sum = {"header": {"competitions": [{"date": "2024-10-22T23:30Z", "competitors": [comp("BOS", "Celtics", True, "132", [35, 31, 33, 33]), comp("NY", "Knicks", False, "109", [28, 25, 30, 26])]}]},
                "boxscore": {"teams": [{"homeAway": "away", "team": {"abbreviation": "NY"}, "statistics": [{"name": "fieldGoalsMade-fieldGoalsAttempted", "displayValue": "40-90"}, {"name": "freeThrowsMade-freeThrowsAttempted", "displayValue": "20-25"},
                                                                                                          {"name": "offensiveRebounds", "displayValue": "10"}, {"name": "turnovers", "displayValue": "12"}]},
                                       {"homeAway": "home", "team": {"abbreviation": "BOS"}, "statistics": [{"name": "fieldGoalsMade-fieldGoalsAttempted", "displayValue": "48-86"}, {"name": "freeThrowsMade-freeThrowsAttempted", "displayValue": "16-20"},
                                                                                                          {"name": "offensiveRebounds", "displayValue": "8"}, {"name": "totalTurnovers", "displayValue": "14"}]}],
                             "players": [{"team": {"abbreviation": "NY"}, "statistics": [{"names": ["MIN", "FG", "3PT", "FT", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "PF", "+/-", "PTS"],
                                                                                           "athletes": [{"athlete": {"id": "3934672", "displayName": "Jalen Brunson", "position": {"abbreviation": "PG"}}, "starter": True, "didNotPlay": False, "stats": ["34", "9-18", "2-5", "5-5", "0", "3", "3", "8", "1", "0", "2", "2", "-12", "25"]},
                                                                                                        {"athlete": {"id": "1", "displayName": "Bench Guy"}, "starter": False, "didNotPlay": False, "stats": ["12", "2-4", "0-1", "0-0", "1", "1", "2", "0", "0", "0", "0", "1", "-3", "4"]},
                                                                                                        {"athlete": {"id": "2", "displayName": "Benched Guy"}, "starter": False, "didNotPlay": True, "reason": "COACH'S DECISION", "stats": []}]}]},
                                         {"team": {"abbreviation": "BOS"}, "statistics": [{"names": ["MIN", "FG", "3PT", "FT", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "PF", "+/-", "PTS"],
                                                                                            "athletes": [{"athlete": {"id": "4065648", "displayName": "Jayson Tatum"}, "starter": True, "didNotPlay": False, "stats": ["36", "14-18", "8-14", "1-1", "0", "4", "4", "10", "1", "0", "1", "2", "+20", "37"]}]}]}]},
                "injuries": [{"team": {"abbreviation": "NY"}, "injuries": [{"status": "Out", "athlete": {"id": "3", "displayName": "Hurt Guy"}, "details": {"type": "Knee"}}]}, {"team": {"abbreviation": "BOS"}, "injuries": []}],
                "gameInfo": {"officials": [{"displayName": "Scott Foster"}, {"displayName": "Tony Brothers"}]}}
    return [("leaguegamelog", log), ("boxscore_0022400001.json", box1), ("boxscoretraditionalv3", trad2), ("boxscoresummaryv2", summ2), ("scheduleLeagueV2", sched),
            ("scoreboard?dates=20241022&", espn_sb), ("summary?event=401704001", espn_sum)]


def _canned_nba_slate():
    """The slate's feeds for 21 and 22 Oct 2026, canned: this season's ledger
    (sixteen clubs at five games, two of them at six on a back to back, a
    seventeenth at two), last season's with a man since traded, the scoreboard
    for the slate day and the morning after, and the league's injury page.
    Returns (payloads, this season's games, last season's games)."""
    clubs = ["BOS", "NYK", "LAL", "GSW", "MIA", "CHI", "DEN", "UTA", "PHI", "MIL", "DAL", "PHX", "CLE", "OKC", "MIN", "SAS"]

    def box(fga):
        return {"fga": fga, "fta": 20, "oreb": 10, "tov": 12, "min": 240.0}

    def roster(ab, extra=None):
        i = clubs.index(ab) if ab in clubs else 99
        return [["9%03d" % i, "%s Star" % NBA_NICK.get(ab, ab), 1, 34.0, 25, 5], ["8%03d" % i, "%s Bench" % NBA_NICK.get(ab, ab), 0, 12.0, 4, -2]] + (extra or [])

    def entry(gid, date, away, home, fa, fh, pa, ph, fga_a, fga_h):
        return {"id": gid, "date": date, "away": away, "home": home, "an": NBA_NICK.get(away, away), "hn": NBA_NICK.get(home, home), "fa": fa, "fh": fh,
                "qa": [fa // 4] * 4, "qh": [fh // 4] * 4, "ota": [], "oth": [], "end": "REG", "sa": box(fga_a), "sh": box(fga_h), "pace": None,
                "pa": pa, "ph": ph, "oa": [], "oh": [], "t": date + "T23:30Z", "off": [], "detail": True}
    now, k = [], 0
    crews = [["Scott Foster", "Tony Brothers", "Marc Davis"], ["Zach Zarba", "Eric Dalen", "Jason Goldenberg"]]
    for r, d in enumerate(["2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17"]):
        for i in range(0, 16, 2):
            away, home = clubs[(i + r) % 16], clubs[(i + 1 + r) % 16]
            k += 1
            # a club scores 100 plus its strength (Boston 15 ... San Antonio 0) whoever it plays; its possessions rise down the list
            now.append(entry("40190%04d" % k, d, away, home, 115 - clubs.index(away), 115 - clubs.index(home), roster(away), roster(home), 85 + clubs.index(away), 85 + clubs.index(home)))
            now[-1]["off"] = crews[k % 2]
    now.append(entry("4019000098", "2026-10-18", "POR", "SAS", 98, 100, roster("POR"), roster("SAS"), 90, 100))
    now.append(entry("4019000099", "2026-10-19", "POR", "SAS", 97, 100, roster("POR"), roster("SAS"), 90, 100))
    # the sixth game, a back to back for both, with the traded man in Boston's rotation for the first time
    now.append(entry("4019000100", "2026-10-20", "BOS", "NYK", 115, 114, roster("BOS", [["7777", "Moved Man", 1, 28.0, 15, 2]]), roster("NYK"), 85, 86))
    prior = [entry("40180%04d" % j, "2025-11-%02d" % j, "GSW", "LAL", 110, 112, roster("GSW"), roster("LAL", [["7777", "Moved Man", 1, 30.0, 18, 3]]), 92, 94) for j in (1, 2, 3)]

    def comp(ab, name, home, score, ls):
        return {"homeAway": "home" if home else "away", "team": {"abbreviation": ab, "name": name, "displayName": name}, "score": score,
                "linescores": [{"displayValue": str(x), "value": float(x)} for x in ls]}

    def ev(gid, date, away, home, done, stype=2, venue="The Arena", odds=None):
        st = {"type": {"completed": done, "description": "Final" if done else "Scheduled", "name": "STATUS_FINAL" if done else "STATUS_SCHEDULED"}}
        c = {"id": gid, "date": date, "status": st, "venue": {"fullName": venue}, "competitors": [home, away]}
        if odds:
            c["odds"] = odds
        return {"id": gid, "date": date, "season": {"year": 2027, "type": stype}, "competitions": [c]}
    # the book on the scoreboard (the user's page of 15 Oct 2026): the lines at the run and where they opened
    dk = [{"provider": {"id": "100", "name": "Draft Kings"}, "details": "NY -1.5", "overUnder": 221.5, "spread": -1.5,
           "moneyline": {"home": {"close": {"odds": "-115"}, "open": {"odds": "-125"}}, "away": {"close": {"odds": "-105"}, "open": {"odds": "+105"}}},
           "pointSpread": {"home": {"close": {"line": "-1.5", "odds": "-108"}, "open": {"line": "-2.5", "odds": "-105"}}, "away": {"close": {"line": "+1.5", "odds": "-112"}, "open": {"line": "+2.5", "odds": "-115"}}},
           "total": {"over": {"close": {"line": "o221.5", "odds": "-115"}, "open": {"line": "o224.5", "odds": "-115"}}, "under": {"close": {"line": "u221.5", "odds": "-105"}, "open": {"line": "u224.5", "odds": "-105"}}}}]
    sb21 = {"events": [ev("4019000090", "2026-10-21T17:00Z", comp("MIA", "Heat", False, "101", [25, 26, 25, 25]), comp("CHI", "Bulls", True, "99", [24, 25, 25, 25]), True),
                       ev("4019000101", "2026-10-22T00:00Z", comp("BOS", "Celtics", False, "0", []), comp("NY", "Knicks", True, "0", []), False, venue="Madison Square Garden", odds=dk),
                       ev("4019000102", "2026-10-22T02:30Z", comp("POR", "Trail Blazers", False, "0", []), comp("LAL", "Lakers", True, "0", []), False),
                       ev("4019000103", "2026-10-22T01:00Z", comp("DEN", "Nuggets", False, "0", []), comp("UTAH", "Jazz", True, "0", []), False, stype=1)]}
    sb22 = {"events": [ev("4019000101", "2026-10-22T00:00Z", comp("BOS", "Celtics", False, "110", [28, 27, 30, 25]), comp("NY", "Knicks", True, "105", [25, 30, 22, 28]), True),
                       ev("4019000104", "2026-10-22T02:00Z", comp("GS", "Warriors", False, "120", []), comp("LAL", "Lakers", True, "118", []), True),
                       ev("4019000105", "2026-10-23T00:00Z", comp("DAL", "Mavericks", False, "0", []), comp("PHX", "Suns", True, "0", []), False)]}
    sum104 = {"header": {"competitions": [{"date": "2026-10-22T02:00Z", "competitors": [comp("LAL", "Lakers", True, "118", [29, 29, 30, 30]), comp("GS", "Warriors", False, "120", [30, 28, 32, 30])]}]},
              "boxscore": {"teams": [], "players": []}, "injuries": [], "gameInfo": {"officials": []}}
    # the injury page as the user's download of 15 Oct 2026 has it: no id on the athlete, only in his links and headshot; his club on his entry
    inj = {"injuries": [
        {"id": "2", "displayName": "Boston Celtics", "injuries": [
            {"status": "Out", "shortComment": "Man (hamstring) is out for Wednesday's game against the Knicks.",
             "athlete": {"displayName": "Moved Man", "shortName": "M. Man", "links": [{"rel": ["playercard"], "href": "https://www.espn.com/nba/player/_/id/7777/moved-man"}],
                         "headshot": {"href": "https://a.espncdn.com/i/headshots/nba/players/full/7777.png"}, "position": {"abbreviation": "F"}, "team": {"abbreviation": "BOS", "displayName": "Boston Celtics"}},
             "details": {"fantasyStatus": {"description": "OUT"}, "type": "Hamstring", "location": "Leg", "detail": "Strain", "returnDate": "2026-10-28"}},
            {"status": "Questionable", "athlete": {"displayName": "Celtics Star", "headshot": {"href": "https://a.espncdn.com/i/headshots/nba/players/full/9000.png"}, "position": {"abbreviation": "G"}, "team": {"abbreviation": "BOS"}},
             "details": {"type": "Ankle"}},
            {"status": "Out", "athlete": {"id": "8888", "displayName": "Rookie Kid"}, "details": {"type": "Knee", "returnDate": "2026-10-19"}}]},
        {"team": {"abbreviation": "NY", "displayName": "New York Knicks"}, "injuries": [
            {"status": "Day-To-Day", "athlete": {"id": "9001", "displayName": "Knicks Star"}, "details": {"type": "Illness"}},
            {"status": "Out", "athlete": {"displayName": "No Id Man"}, "details": {"type": "Rest"}}]},
        {"displayName": "Nowhere Club", "injuries": [{"status": "Out", "athlete": {"id": "1", "displayName": "Nobody"}, "details": {}}]}]}
    # the league's assignments feed as the user's download of 15 Oct 2026 has it: one row a game, the clubs as cities with the
    # tricodes beside them and in the game code, a fourth official slot usually null, the replay centre in a second table
    offs = {"nba": {"Table": {"rows": [
        {"game_id": "0022600003", "game_date": "10/21/2026", "season": "22026", "game_code": "20261021/BOSNYK", "home_team_id": 1610612752, "home_team": "New York", "home_team_abbr": "NYK",
         "away_team_id": 1610612738, "away_team": "Boston", "away_team_abbr": "BOS", "official1": "Scott Foster", "official1_code": 1, "official2": "Tony Brothers", "official2_code": 2,
         "official3": "Marc Davis", "official3_code": 3, "official4": None, "official4_code": None},
        {"game_id": "0022600004", "game_date": "10/21/2026", "game_code": "20261021/PORLAL", "home_team": "Los Angeles", "away_team": "Portland",
         "official1": "Zach Zarba", "official2": "Eric Dalen", "official3": "Jason Goldenberg", "official4": None}]},
                    "Table1": {"rows": [{"game_date": "10/21/2026", "official_code": 1151, "replaycenter_official": "Sean Corbin"}]}},
            "gl": {"Table": {"rows": [{"game_code": "20261021/ABCDEF", "home_team_abbr": "DEF", "away_team_abbr": "ABC", "official1": "G League Ref"}]}}, "wnba": {"Table": {"rows": []}}}
    return [("scoreboard?dates=20261021&", sb21), ("scoreboard?dates=20261022&", sb22), ("summary?event=4019000104", sum104), ("/injuries", inj),
            ("get-game-officials?date=2026-10-21", offs)], now, prior


def _canned_nhl_landing():
    return dict(x for x in _canned_nhl())["/landing"]


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
    box = {"awayTeam": {"abbrev": "NYR", "score": 4, "sog": 31}, "homeTeam": {"abbrev": "XXX", "score": 2, "sog": 28},
           "playerByGameStats": {"awayTeam": {"goalies": [{"playerId": 1, "name": {"default": "I. S"}, "starter": True, "saveShotsAgainst": "26/28", "goalsAgainst": 2, "toi": "59:30"}, {"playerId": 2, "starter": False}]},
                                 "homeTeam": {"goalies": [{"playerId": 9, "name": {"default": "J. S"}, "toi": "60:00", "saveShotsAgainst": "27/31"}]}}}
    landing = {"awayTeam": {"abbrev": "NYR", "score": 2}, "homeTeam": {"abbrev": "BOS", "score": 3}, "gameOutcome": {"lastPeriodType": "REG"},
               "summary": {"linescore": {"byPeriod": [{"periodDescriptor": {"number": 1, "periodType": "REG"}, "away": 1, "home": 0},
                                                      {"periodDescriptor": {"number": 2, "periodType": "REG"}, "away": 1, "home": 2}, {"periodDescriptor": {"number": 3, "periodType": "REG"}, "away": 0, "home": 1}]},
                           "shotsByPeriod": [{"periodDescriptor": {"number": 1}, "away": 10, "home": 9}, {"periodDescriptor": {"number": 2}, "away": 8, "home": 12}, {"periodDescriptor": {"number": 3}, "away": 11, "home": 7}],
                           "scoring": [{"periodDescriptor": {"number": 1}, "goals": [{"teamAbbrev": {"default": "NYR"}, "goalModifier": "none", "strength": "pp"}]},
                                       {"periodDescriptor": {"number": 3}, "goals": [{"teamAbbrev": {"default": "BOS"}, "goalModifier": "empty-net", "strength": "ev"}]}],
                           "penalties": [{"periodDescriptor": {"number": 1}, "penalties": [{"type": "MIN", "teamAbbrev": {"default": "BOS"}}, {"type": "MIN", "teamAbbrev": {"default": "NYR"}}, {"type": "MIS", "teamAbbrev": {"default": "BOS"}}]}]}}
    sjs_now = {"goalies": []}
    sjs_last = club("SJS", [(7, "Yaroslav", "A", 0.908, 1600, 55, 54), (8, "Gone", "Guy", 0.900, 600, 20, 19)])
    sjs_roster = {"goalies": [{"id": 7}, {"id": 9}]}
    # player pages: last season's line for the blend. Igor (1) and Joonas (4) have no page in the
    # canned set, so they keep this season's line alone; Jeremy (3) moved mid-season and is summed.
    def player(rows):
        return {"seasonTotals": [{"season": s, "gameTypeId": gt, "leagueAbbrev": "NHL", "shotsAgainst": sa, "goalsAgainst": ga} for s, gt, sa, ga in rows]}
    p2 = player([(20252026, 2, 1000, 90), (20252026, 3, 200, 10), (20242025, 2, 900, 100)])
    p3 = player([(20252026, 2, 1200, 102), (20252026, 2, 800, 68)])
    gsummary = {"data": [
        {"playerId": 1, "goalieFullName": "Igor S", "teamAbbrevs": "NYR", "savePct": 0.912, "shotsAgainst": 1400, "gamesStarted": 47},
        {"playerId": 2, "goalieFullName": "Jonathan Q", "teamAbbrevs": "NYR", "savePct": 0.902, "shotsAgainst": 500, "gamesStarted": 17},
        {"playerId": 3, "goalieFullName": "Jeremy S", "teamAbbrevs": "BOS", "savePct": 0.921, "shotsAgainst": 1900, "gamesStarted": 60},
        {"playerId": 4, "goalieFullName": "Joonas K", "teamAbbrevs": "BOS", "savePct": 0.898, "shotsAgainst": 300, "gamesStarted": 11},
        {"playerId": 5, "goalieFullName": "Thin Line", "teamAbbrevs": "SJS", "savePct": 0.950, "shotsAgainst": 40, "gamesStarted": 1}]}
    return [
        ("/schedule/2026-10-07", sched7), ("/schedule/2026-10-06", sched6),
        ("team/summary", summary), ("goalie/summary", gsummary),
        ("/club-stats/SJS/now", sjs_now), ("/club-stats/SJS/20252026/2", sjs_last), ("/roster/SJS/current", sjs_roster),
        ("/club-stats/NYR/", nyr), ("/club-stats/BOS/", bos),
        ("/club-schedule-season/NYR/", nyr_season), ("/club-schedule-season/BOS/", bos_season),
        ("/player/2/landing", p2), ("/player/3/landing", p3),
        ("/boxscore", box), ("/landing", landing),
    ]


def _canned_rotowire():
    """RotoWire's lineup page, cut to the markup the parser reads (19 Oct 2026):
    the date line, one game box with both clubs, each list's highlighted goalie
    with his status row, and the tools box that carries no game."""
    def goalie(side, href, name, cls, dot, word):
        return ('<ul class="lineup__list is-%s">\n<li class="lineup__player-highlight">\n<div class="lineup__player-highlight-name">\n'
                '<a href="%s">%s</a>\n</div>\n<div class="flex-row align-center %s" style="padding:3px 0 2px;font-size:11px;">\n'
                '<div class="dot is-medium %s" style="margin-right:5px;"></div>%s\n</div>\n</li>\n'
                '<li class="lineup__title">POWER PLAY #1</li>\n<li class="lineup__player"><div class="lineup__pos">C</div><a title="Some Guy" href="/hockey/player/some-guy-1">S. Guy</a></li>\n</ul>'
                % (side, href, name, cls, dot, word))
    return ('<div class="page-title__secondary">Starting NHL lineups for October 7, 2026<div class="lineup__partner-top"><b>Like a lineup?</b></div></div>\n'
            '<div class="lineups">\n<div class="lineup is-nhl">\n<div class="lineup__meta flex-row"><div class="lineup__time">7:00 PM ET</div></div>\n'
            '<div class="lineup__box"><div class="lineup__top"><div class="lineup__teams">'
            '<a href="/hockey/nhl-depth-charts/rangers-depth-chart-nyr" class="lineup__team is-visit"><div class="lineup__abbr">NYR</div></a>'
            '<a href="/hockey/nhl-depth-charts/bruins-depth-chart-bos" class="lineup__team is-home"><div class="lineup__abbr">BOS</div></a></div></div>\n'
            '<div class="lineup__matchup">\n<a href="/hockey/nhl-depth-charts/rangers-depth-chart-nyr" class="lineup__mteam is-visit white">\n'
            '    Rangers                                        <span class="lineup__wl">(6-3-1)</span>\n</a>\n'
            '<a href="/hockey/nhl-depth-charts/bruins-depth-chart-bos" class="lineup__mteam is-home white">\n'
            '    Bruins                                        <span class="lineup__wl">(5-4-0)</span>\n</a>\n</div>\n<div class="lineup__main">\n'
            + goalie("visit", "/hockey/player/igor-s-1", "I. S", "is-confirmed", "is-green", "Confirmed")
            + goalie("home", "/hockey/player/jeremy-s-3", "Jeremy S", "is-expected", "is-yellow", "Expected")
            + '</div><div class="lineup__bottom"></div></div></div>\n'
            '<div class="lineup is-nhl is-tools"><div class="lineup__tool-name">Lineup optimizer</div></div>\n</div>')


def _canned_cbs():
    """CBS's goalie depth chart, cut to the markup the parser reads: one table
    row a club with CBS's code, the short and long name of each goalie, a news
    tooltip on a starter and an injury tooltip on a reserve."""
    def player(short, long_, pid, tip=None):
        icon = ('<span class="CellPlayerName-icon icon-moon-injury"><div class="Tablebase-tooltip Tablebase-tooltip--playerIcons ">'
                '<div class="Tablebase-tooltipInner">\n                    %s\n                </div></div></span>' % tip) if tip else ""
        return ('<span class="CellPlayerName--short"><span class=""><a href="/nhl/players/%d/x/fantasy/" class="">%s</a>%s</span></span>'
                '<span class="CellPlayerName--long"><span class=""><a href="/nhl/players/%d/x/fantasy/" class="">%s</a>%s</span></span>' % (pid, short, icon, pid, long_, icon))
    def row(code, slug, starter, backup, reserves):
        cells = ['<span class="CellLogoNameLockup"><div class="TeamLogoNameLockup-name"><span class="TeamName"><a href="/nhl/teams/%s/%s/" class="">%s</a></span></div></span>' % (code, slug, code),
                 starter, backup, ('<div class="CellPlayerNames">' + "".join('<div class="CellPlayerNames-name">%s</div>' % r for r in reserves) + "</div>") if reserves else "\n                                        —                 "]
        return '<tr class="TableBase-bodyTr">' + "".join('<td class="TableBase-bodyTd \n                ">%s</td>' % c for c in cells) + "</tr>"
    return ('<table class="TableBase-table"><thead><tr class="TableBase-headTr"><th class="TableBase-headTh">Team</th><th class="TableBase-headTh">Starter</th>'
            '<th class="TableBase-headTh">Backup</th><th class="TableBase-headTh">Reserves</th></tr></thead><tbody>'
            + row("NYR", "new-york-rangers", player("I. S", "Igor S", 1, "Rangers&#x27; Igor S: First goalie off Wednesday"), player("J. Q", "Jonathan Q", 2), [])
            + row("BOS", "boston-bruins", player("J. S", "Jeremy S", 3), player("N. Body", "No Body", 99), [player("J. K", "Joonas K", 4, "Lower Body: IR. Expected to be out until at least Oct 20")])
            + row("CLB", "columbus-blue-jackets", player("J. G", "Jet G", 5), player("C. T", "Cam T", 6), [])
            + "</tbody></table>")


# ---- main ------------------------------------------------------------------
# The slates run for today, the grades for yesterday. The props run was left
# off this list on 19 Oct 2026 and the user's first run wrote an empty file
# for the 18th; the list is a name now, and the self-test reads it.
TODAY_MODES = ("slate", "nhl", "nhl-ledger", "nba", "nba-ledger", "nba-props", "odds")


def default_date(mode, today):
    return (today if mode in TODAY_MODES else today - dt.timedelta(days=1)).isoformat()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write the day's slate (or yesterday's finals) for Call Sheet 2.0.")
    ap.add_argument("mode", nargs="?", choices=["slate", "grade", "nhl", "nhl-grade", "nhl-ledger", "nba", "nba-grade", "nba-ledger", "nba-props", "odds", "odds-history"], default="slate",
                    help="slate (default): today's MLB inputs. grade: MLB finals. nhl: today's NHL inputs. nhl-grade: NHL finals. "
                         "nhl-ledger: every NHL final this season, measured against the sheet's assumptions. "
                         "nba: today's NBA inputs (ratings, pace, rest, who is out, the context lines). nba-grade: NBA finals with the half-time score. "
                         "nba-ledger: every NBA final of a season with quarters, pace and every player's minutes (--season 2024-25 for a past season). "
                         "odds: today's lines, prices, openers, the sharp line, the alternates and every book's price from The Odds API (needs odds_key.txt). "
                         "odds-history: a past season's lines at two moments a day, for the backtest's openers (paid plans; asks before it spends).")
    ap.add_argument("--books", help="odds only: the books to read, first one carded, pinnacle never carded, e.g. fanatics,betmgm,draftkings,pinnacle (default: %s)" % ",".join(ODDS_BOOKS))
    ap.add_argument("--sports", help="odds only: which sports, e.g. NHL,MLB (default: MLB,NHL; odds-history: NHL)")
    ap.add_argument("--date", help="YYYY-MM-DD. Default: today for slate, yesterday for grade.")
    ap.add_argument("--season", help="nhl-ledger, nba-ledger and odds-history: a past season to pull in full, e.g. 20252026 or 2024-25 (for the backtest).")
    ap.add_argument("--from", dest="start", help="odds-history: the first date to pull, YYYY-MM-DD (with --to; else the season's dates).")
    ap.add_argument("--to", dest="end", help="odds-history: the last date to pull, YYYY-MM-DD.")
    ap.add_argument("--times", help="odds-history: the UTC snapshot times a day, e.g. 16:00,23:30 (the hockey default; the NBA's is 22:30 alone); +02:30 means the next day's 02:30.")
    ap.add_argument("--markets", help="odds-history: the markets to pull, e.g. totals or totals,h2h (default totals; the NBA's default h2h; each is 10 credits a snapshot).")
    ap.add_argument("--yes", action="store_true", help="odds-history: pull without asking first.")
    ap.add_argument("--keep", type=int, default=ODDS_HISTORY_KEEP, help="odds-history: stop when this many credits are left for the nightly runs (default %d)." % ODDS_HISTORY_KEEP)
    ap.add_argument("--detail", action="store_true", help="nhl-ledger only: also fetch each game's box score and game page for the starters, their lines, power-play goals and penalties (two calls a game; about 40 minutes a season).")
    ap.add_argument("--refs", action="store_true", help="nhl-ledger only: also fetch each game's side panel for the referees, linesmen and scratches (one call a game; about 20 minutes a season).")
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
        date_iso = default_date(a.mode, today)
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
        elif a.mode == "nhl-ledger":
            path = make_nhl_ledger(date_iso, a.out, log, a.season, a.detail, a.refs)
        elif a.mode == "nba-ledger":
            path = make_nba_ledger(date_iso, a.out, log, a.season)
        elif a.mode == "nba":
            path = make_nba_slate(date_iso, a.out, log)
        elif a.mode == "nba-grade":
            path = make_nba_grade(date_iso, a.out, log)
        elif a.mode == "nba-props":
            path = make_nba_props(date_iso, a.out, log)
        elif a.mode == "odds":
            sports = tuple(s.strip().upper() for s in a.sports.split(",") if s.strip()) if a.sports else ("MLB", "NHL", "NBA")
            path = make_odds(date_iso, a.out, log, a.books, sports)
        elif a.mode == "odds-history":
            sports = tuple(s.strip().upper() for s in a.sports.split(",") if s.strip()) if a.sports else ("NHL",)
            path = make_odds_history(a.out, log, a.books, sports, a.season, a.start, a.end, a.times, a.markets, a.yes, a.keep)
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
