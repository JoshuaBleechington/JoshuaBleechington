"""The basketball book's inputs against two seasons of closes, the hockey way.

    python3 tools_backtest_nba.py FOLDER

FOLDER holds led2425.json and led2526.json (slate.py nba-ledger --season, the two ledgers
the user ran 15 Oct 2026: every regular-season final with quarters, the box lines, every
player's minutes and who sat, the crew) and the two KillerSports pages saved as
a6af4eb0-query.html (2025-26) and 78766447-query.html (2024-25):
`date, team, o:team, points, o:points, line, total, site, rest @ season=YYYY and site=home
and playoffs=0` (line is the HOME spread, negative when the home side is favoured).

Prints, for both seasons and pooled: the market's own record (the total's residual and the
spread's, over/under and against the spread), the league constants the engine needs, and
for each candidate input the slope of the close's residual on the input's lean with its t
and the record bet at the line, on the total and on the side. Inputs: the pace-times-
efficiency projection from the box lines to date, the last ten, rest (back to back, three
in four, the second night on the road), time zones, missing regulars by minutes and by
scoring, the referee crew, and the stage of the season. Run 15 Oct 2026, the night the
ledgers arrived. NBA.md has the table.
"""
import sys, os, re, html, json, math, collections, datetime as dt

NICK = {"Seventysixers": "76ers", "Trailblazers": "Trail Blazers"}
TEAMS = {"76ers": "PHI", "Bucks": "MIL", "Bulls": "CHI", "Cavaliers": "CLE", "Celtics": "BOS", "Clippers": "LAC", "Grizzlies": "MEM", "Hawks": "ATL",
         "Heat": "MIA", "Hornets": "CHA", "Jazz": "UTA", "Kings": "SAC", "Knicks": "NYK", "Lakers": "LAL", "Magic": "ORL", "Mavericks": "DAL",
         "Nets": "BKN", "Nuggets": "DEN", "Pacers": "IND", "Pelicans": "NOP", "Pistons": "DET", "Raptors": "TOR", "Rockets": "HOU", "Spurs": "SAS",
         "Suns": "PHX", "Thunder": "OKC", "Timberwolves": "MIN", "Trail Blazers": "POR", "Warriors": "GSW", "Wizards": "WAS"}
# the arena's clock, hours from UTC in winter (Phoenix keeps it all year)
TZ = {"ATL": -5, "BOS": -5, "BKN": -5, "CHA": -5, "CHI": -6, "CLE": -5, "DAL": -6, "DEN": -7, "DET": -5, "GSW": -8, "HOU": -6, "IND": -5,
      "LAC": -8, "LAL": -8, "MEM": -6, "MIA": -5, "MIL": -6, "MIN": -6, "NOP": -6, "NYK": -5, "OKC": -6, "ORL": -5, "PHI": -5, "PHX": -7,
      "POR": -8, "SAC": -8, "SAS": -6, "TOR": -5, "UTA": -7, "WAS": -5}
ALTITUDE = {"DEN", "UTA"}
DEADLINE = {"2024-25": "2025-02-06", "2025-26": "2026-02-05"}
HCA = 1.7          # the measured home margin, both seasons
FT_POSS = 0.44
REGULAR_MPG = 20.0  # a regular: this many minutes a game to date, five games in
REGULAR_GAMES = 5
MIN_GAMES = 10      # ratings to date need this many games a side


def ks_rows(f):
    s = open(f, encoding="utf-8", errors="replace").read()
    out = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", s, flags=re.S):
        c = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, flags=re.S)]
        if len(c) >= 9 and re.match(r"\d{4}-\d{2}-\d{2}", c[0]):
            try:
                out.append({"date": c[0], "home": NICK.get(c[1], c[1]), "away": NICK.get(c[2], c[2]), "hpts": int(c[3]), "apts": int(c[4]),
                            "spread": float(c[5]) if c[5] not in ("-", "") else None, "total": float(c[6]) if c[6] not in ("-", "") else None,
                            "rest": int(c[8]) if c[8] not in ("-", "") else None})
            except ValueError:
                pass
    return out


def load(folder):
    seasons = []
    for led_f, ks_f, season in (("led2425.json", "78766447-query.html", "2024-25"), ("led2526.json", "a6af4eb0-query.html", "2025-26")):
        led = json.load(open(os.path.join(folder, led_f)))["games"]
        led = [g for g in led if g.get("hn") in TEAMS and g.get("an") in TEAMS]      # the All-Star games out
        ks = {(r["date"], r["home"], r["away"]): r for r in ks_rows(os.path.join(folder, ks_f))}
        joined, miss = [], 0
        for g in led:
            r = ks.get((g["date"], g["hn"], g["an"]))
            if not r or r["total"] is None or r["spread"] is None:
                miss += 1
                continue
            if r["hpts"] != g["fh"] or r["apts"] != g["fa"]:
                miss += 1
                continue
            g = dict(g)
            g["total"], g["spread"], g["ks_rest"] = r["total"], r["spread"], r["rest"]
            joined.append(g)
        joined.sort(key=lambda g: (g["date"], g["id"]))
        seasons.append({"season": season, "led": sorted(led, key=lambda g: (g["date"], g["id"])), "joined": joined, "missing": miss, "ks": len(ks)})
    return seasons


def avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / float(len(xs)) if xs else None


def sd(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    m = avg(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def ols(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = my - b * mx
    sse = sum((y - a - b * x) ** 2 for x, y in zip(xs, ys))
    se = math.sqrt(sse / (n - 2) / sxx)
    return b, (b / se if se else float("nan")), n


def poss(line):
    return line["fga"] - line["oreb"] + line["tov"] + FT_POSS * line["fta"]


def features(season):
    """One row per joined game with everything to date BEFORE the game."""
    led, joined = season["led"], season["joined"]
    team = collections.defaultdict(list)      # tricode -> ordered per-game records
    player = collections.defaultdict(list)    # pid -> ordered (date, team, mins, pts, pm)
    crew = collections.defaultdict(list)      # official -> ordered (date, fta both, total, close) (close only on joined)
    close_of = {g["id"]: (g["total"], g["spread"]) for g in joined}
    with_close = {g["id"]: g for g in joined}
    rows = []
    for g in led:
        d = g["date"]
        A, H = g["away"], g["home"]
        if g["id"] in with_close:
            rows.append(make_row(with_close[g["id"]], season["season"], team, player, crew))
        # ---- then record the game for the future ----
        if g.get("detail") and g.get("sa") and g.get("sh"):
            pa, ph = poss(g["sa"]), poss(g["sh"])
            tot = g["fa"] + g["fh"]
            for side, t, opp, pts, opts, p, op, home in (("a", A, H, g["fa"], g["fh"], pa, ph, False), ("h", H, A, g["fh"], g["fa"], ph, pa, True)):
                team[t].append({"date": d, "opp": opp, "home": home, "pts": pts, "opts": opts, "poss": p, "oposs": op, "tot": tot,
                                "mins": (g["sa"] if side == "a" else g["sh"])["min"], "t": g.get("t")})
            for side, t in (("pa", A), ("ph", H)):
                for p in g.get(side) or []:
                    player[p[0]].append({"date": d, "team": t, "name": p[1], "mins": p[3], "pts": p[4], "pm": p[5], "start": p[2]})
            fta = g["sa"]["fta"] + g["sh"]["fta"]
            for o in g.get("off") or []:
                crew[o].append({"date": d, "fta": fta, "tot": tot, "close": close_of.get(g["id"], (None, None))[0]})
    return rows


def rest_days(hist, d):
    if not hist:
        return None
    return (dt.date.fromisoformat(d) - dt.date.fromisoformat(hist[-1]["date"])).days - 1


def games_in_window(hist, d, days):
    lo = (dt.date.fromisoformat(d) - dt.timedelta(days=days - 1)).isoformat()
    return sum(1 for x in hist if lo <= x["date"] < d)


def make_row(g, season, team, player, crew):
    d, A, H = g["date"], g["away"], g["home"]
    ha, hh = team[A], team[H]
    f = {"season": season, "date": d, "away": A, "home": H, "tot": g["fa"] + g["fh"], "margin": g["fh"] - g["fa"], "close": g["total"], "spread": g["spread"],
         "month": d[5:7], "pace": g.get("pace"), "ot": g.get("end") == "OT", "q": (g.get("qa"), g.get("qh"))}
    f["tres"] = f["tot"] - f["close"]                     # the total's residual on the close
    f["mres"] = f["margin"] - (-f["spread"])              # the margin's residual on the spread (home favoured = negative line)
    f["n"] = min(len(ha), len(hh))
    # ratings to date: points per 100 possessions for and against, pace
    if len(ha) >= MIN_GAMES and len(hh) >= MIN_GAMES:
        lg = []
        for t, h in team.items():
            lg.extend(h)
        lg_ortg = 100.0 * sum(x["pts"] for x in lg) / sum(x["poss"] for x in lg)
        lg_pace = avg([x["poss"] * 48.0 / (x["mins"] / 5.0) for x in lg])
        def rt(h):
            o = 100.0 * sum(x["pts"] for x in h) / sum(x["poss"] for x in h)
            dd = 100.0 * sum(x["opts"] for x in h) / sum(x["oposs"] for x in h)
            pc = avg([x["poss"] * 48.0 / (x["mins"] / 5.0) for x in h])
            return o, dd, pc
        ao, ad, ap = rt(ha)
        ho, hd, hp = rt(hh)
        pace = (ap + hp) / 2.0
        exp_a = pace / 100.0 * (ao + hd - lg_ortg)
        exp_h = pace / 100.0 * (ho + ad - lg_ortg)
        f["proj_total"] = exp_a + exp_h
        f["proj_margin"] = exp_h - exp_a + HCA
        f["pace_lean"] = pace - lg_pace
        f["l10"] = (avg([x["tot"] for x in ha[-10:]]) + avg([x["tot"] for x in hh[-10:]])) / 2.0
        f["ppg_lean"] = (avg([x["pts"] + x["opts"] for x in ha]) + avg([x["pts"] + x["opts"] for x in hh])) / 2.0 - avg([x["tot"] for x in lg])
    # rest and the schedule
    ra, rh = rest_days(ha, d), rest_days(hh, d)
    f["arest"], f["hrest"] = ra, rh
    f["a_b2b"], f["h_b2b"] = ra == 0, rh == 0
    f["a_3in4"], f["h_3in4"] = games_in_window(ha, d, 4) >= 2, games_in_window(hh, d, 4) >= 2
    f["a_road_b2b"] = ra == 0 and bool(ha) and not ha[-1]["home"]           # the second night on the road
    f["a_trip"] = 0
    for x in reversed(ha):
        if x["home"]:
            break
        f["a_trip"] += 1
    f["tz"] = TZ.get(H, -5) - TZ.get(A, -5)                                    # hours the away side moved: negative = west
    f["altitude"] = H in ALTITUDE
    # missing regulars: a regular has played REGULAR_GAMES games to date at REGULAR_MPG minutes
    for side, t, key in (("a", A, "oa"), ("h", H, "oh")):
        miss_min = miss_pts = miss_pm = 0.0
        names = []
        for p in g.get(key) or []:
            hist = [x for x in player.get(p[0], []) if x["team"] == t]
            if len(hist) >= REGULAR_GAMES:
                mpg = avg([x["mins"] for x in hist])
                if mpg >= REGULAR_MPG:
                    miss_min += mpg
                    miss_pts += avg([x["pts"] for x in hist])
                    miss_pm += avg([x["pm"] for x in hist])
                    names.append(p[1])
        f[side + "_miss_min"], f[side + "_miss_pts"], f[side + "_miss_pm"], f[side + "_miss"] = miss_min, miss_pts, miss_pm, names
    # the crew: each official's games to date, the free throws and the total's residual against the close
    ftas, res = [], []
    for o in g.get("off") or []:
        h = crew.get(o, [])
        if len(h) >= 10:
            ftas.append(avg([x["fta"] for x in h]))
            r = [x["tot"] - x["close"] for x in h if x["close"] is not None]
            if len(r) >= 10:
                res.append(avg(r))
    f["crew_fta"] = avg(ftas)
    f["crew_res"] = avg(res)
    f["fta"] = (g["sa"]["fta"] + g["sh"]["fta"]) if g.get("sa") and g.get("sh") else None
    # the stage
    f["post_deadline"] = d > DEADLINE[season]
    f["last_two_weeks"] = d >= ("2025-03-31" if season == "2024-25" else "2026-03-30")
    f["cup_night"] = False
    return f


def rec(v, key, line_key, sign=1):
    """W-L-P of betting the over/home side when the lean says so."""
    w = l = p = 0
    for r in v:
        res = r[key]
        if res > 0:
            w += 1
        elif res < 0:
            l += 1
        else:
            p += 1
    return w, l, p


def slope_table(rows, items, resid, log, title, lean_at):
    log("")
    log("===== %s =====" % title)
    log("  %-54s %6s %8s %6s %22s %18s" % ("input lean (+ = more / home)", "n", "slope", "t", "by season 24-25 / 25-26", "bet at %.1f" % lean_at))
    for key, name, fn in items:
        pts = []
        for r in rows:
            x = fn(r)
            if x is None:
                continue
            pts.append((x, r[resid], r))
        o = ols([p[0] for p in pts], [p[1] for p in pts])
        if not o:
            continue
        b, t, n = o
        by = []
        for s in ("2024-25", "2025-26"):
            os_ = ols([p[0] for p in pts if p[2]["season"] == s], [p[1] for p in pts if p[2]["season"] == s])
            by.append("%+.3f" % os_[0] if os_ else "-")
        bet = [p for p in pts if abs(p[0]) >= lean_at and p[1] != 0]
        win = sum(1 for p in bet if (p[1] > 0) == (p[0] > 0))
        lose = len(bet) - win
        log("  %-54s %6d %+8.3f %6.1f %22s %6d-%-5d %+7.1fu" % (name, n, b, t, " / ".join(by), win, lose, win * 100.0 / 110.0 - lose))


def flag_table(rows, flags, resid, log, title, unit):
    log("")
    log("===== %s =====" % title)
    log("  %-54s %6s %9s %6s %12s %22s" % ("spot", "n", "residual", "t", unit, "by season"))
    for name, fn in flags:
        v = [r for r in rows if fn(r)]
        if len(v) < 20:
            continue
        res = [r[resid] for r in v]
        m, s = avg(res), sd(res)
        t = m / (s / math.sqrt(len(v))) if s else float("nan")
        w = sum(1 for r in v if r[resid] > 0); l = sum(1 for r in v if r[resid] < 0)
        by = " / ".join("%+.2f (%d)" % (avg([r[resid] for r in v if r["season"] == ss]) or 0, sum(1 for r in v if r["season"] == ss)) for ss in ("2024-25", "2025-26"))
        log("  %-54s %6d %+9.2f %6.1f %5d-%-6d %22s" % (name, len(v), m, t, w, l, by))


def run(folder, log=print):
    seasons = load(folder)
    rows = []
    for s in seasons:
        log("%s: %d regular-season games in the ledger, %d KillerSports closes, %d joined (%d not joined)" % (s["season"], len(s["led"]), s["ks"], len(s["joined"]), s["missing"]))
        rows.extend(features(s))
    log("")
    log("===== the market at the close =====")
    for label, v in (("both seasons", rows), ("2024-25", [r for r in rows if r["season"] == "2024-25"]), ("2025-26", [r for r in rows if r["season"] == "2025-26"])):
        ov = sum(1 for r in v if r["tres"] > 0); un = sum(1 for r in v if r["tres"] < 0); pu = len(v) - ov - un
        hc = sum(1 for r in v if r["mres"] > 0); ac = sum(1 for r in v if r["mres"] < 0); pp = len(v) - hc - ac
        log("  %-12s %4d games | total: mean close %.1f, final %.1f, residual %+.2f sd %.1f, over %d-%d-%d | spread: home %+.2f, residual %+.2f sd %.1f, home covers %d-%d-%d | OT %.1f%%" % (
            label, len(v), avg([r["close"] for r in v]), avg([r["tot"] for r in v]), avg([r["tres"] for r in v]), sd([r["tres"] for r in v]), ov, un, pu,
            avg([r["margin"] for r in v]), avg([r["mres"] for r in v]), sd([r["mres"] for r in v]), hc, ac, pp, 100.0 * avg([1.0 if r["ot"] else 0.0 for r in v])))
    bym = collections.defaultdict(list)
    for r in rows:
        bym[r["month"]].append(r)
    log("  by month: " + "; ".join("%s: close %.1f, final %.1f (%+.1f), O-U %d-%d, home ATS %d-%d" % (m, avg([r["close"] for r in v]), avg([r["tot"] for r in v]), avg([r["tres"] for r in v]),
                                                                                                    sum(1 for r in v if r["tres"] > 0), sum(1 for r in v if r["tres"] < 0), sum(1 for r in v if r["mres"] > 0), sum(1 for r in v if r["mres"] < 0))
                                 for m, v in sorted(bym.items(), key=lambda kv: (kv[0] < "07", kv[0]))))
    # constants
    log("")
    log("===== the league constants for the engine =====")
    q = [r for r in rows if r["q"][0] and r["q"][1] and len(r["q"][0]) == 4 and len(r["q"][1]) == 4]
    half = [r["q"][0][0] + r["q"][0][1] + r["q"][1][0] + r["q"][1][1] for r in q]
    reg = [sum(r["q"][0]) + sum(r["q"][1]) for r in q]
    log("  first-half share of regulation points %.4f (sd of the half's residual on half the close: %.2f); quarters %s" % (
        sum(half) / float(sum(reg)), sd([h - 0.5 * r["close"] * (sum(r["q"][0]) + sum(r["q"][1])) / r["tot"] for h, r in zip(half, q)]) or 0,
        " / ".join("%.4f" % (sum(r["q"][0][k] + r["q"][1][k] for r in q) / float(sum(reg))) for k in range(4))))
    log("  the half against half the close: residual %+.2f, sd %.2f (the first-half market's spread)" % (avg([h - r["close"] / 2.0 for h, r in zip(half, q)]), sd([h - r["close"] / 2.0 for h, r in zip(half, q)])))
    log("  pace %.1f (sd %.1f); home margin %+.2f; the margin's residual on the spread sd %.1f; the total's residual sd %.1f" % (
        avg([r["pace"] for r in rows]), sd([r["pace"] for r in rows]), avg([r["margin"] for r in rows]), sd([r["mres"] for r in rows]), sd([r["tres"] for r in rows])))
    # the spread as a win-chance: home win rate by spread bucket (the moneyline calibration without a moneyline)
    log("  home wins by the closing spread: " + "; ".join("%s: %.1f%% (%d)" % (lab, 100.0 * avg([1.0 if r["margin"] > 0 else 0.0 for r in v]), len(v)) for lab, v in (
        ("home -10 or more", [r for r in rows if r["spread"] <= -10]), ("-9.5 to -5", [r for r in rows if -10 < r["spread"] <= -5]), ("-4.5 to -1", [r for r in rows if -5 < r["spread"] < 0]),
        ("pick to +4.5", [r for r in rows if 0 <= r["spread"] < 5]), ("+5 to +9.5", [r for r in rows if 5 <= r["spread"] < 10]), ("+10 or more", [r for r in rows if r["spread"] >= 10])) if v))
    # ---- the total ----
    slope_table(rows, [
        ("proj", "pace x efficiency projection to date, minus the close", lambda r: (r["proj_total"] - r["close"]) if "proj_total" in r else None),
        ("l10", "last ten average total, minus the close", lambda r: (r["l10"] - r["close"]) if "l10" in r else None),
        ("ppg", "season points per game (both), minus the league", lambda r: r.get("ppg_lean")),
        ("pace", "pace to date (both), minus the league, in possessions", lambda r: r.get("pace_lean")),
        ("miss", "missing regulars' minutes, both sides (per 48)", lambda r: (r["a_miss_min"] + r["h_miss_min"]) / 48.0 if "a_miss_min" in r else None),
        ("misspts", "missing regulars' points a game, both sides (per 10)", lambda r: (r["a_miss_pts"] + r["h_miss_pts"]) / 10.0 if "a_miss_pts" in r else None),
        ("crewfta", "crew's free throws a game to date, minus 45 (per 10)", lambda r: (r["crew_fta"] - 45.0) / 10.0 if r.get("crew_fta") else None),
        ("crewres", "crew's own over/under residual to date", lambda r: r.get("crew_res")),
    ], "tres", log, "the TOTAL: the close's residual on each input's lean (points)", 3.0)
    flag_table(rows, [
        ("either side on a back to back", lambda r: r["a_b2b"] or r["h_b2b"]), ("away side on a back to back", lambda r: r["a_b2b"]), ("home side on a back to back", lambda r: r["h_b2b"]),
        ("both on a back to back", lambda r: r["a_b2b"] and r["h_b2b"]), ("away side, second night on the road", lambda r: r["a_road_b2b"]),
        ("either side three in four nights", lambda r: r["a_3in4"] or r["h_3in4"]), ("both rested 2+ days", lambda r: (r["arest"] or 0) >= 2 and (r["hrest"] or 0) >= 2),
        ("away side 4th game or later of a road trip", lambda r: r["a_trip"] >= 4), ("away side crossed 2+ time zones west", lambda r: r["tz"] <= -2), ("away side crossed 2+ time zones east", lambda r: r["tz"] >= 2),
        ("at altitude (Denver, Utah)", lambda r: r["altitude"]), ("after the trade deadline", lambda r: r["post_deadline"]), ("the last two weeks of the season", lambda r: r["last_two_weeks"]),
        ("a missing regular on either side", lambda r: r.get("a_miss") or r.get("h_miss")), ("40+ minutes of regulars missing, either side", lambda r: r.get("a_miss_min", 0) >= 40 or r.get("h_miss_min", 0) >= 40),
        ("closing total 240 or more", lambda r: r["close"] >= 240), ("closing total 220 or less", lambda r: r["close"] <= 220),
    ], "tres", log, "the TOTAL by spot: the close's residual (points), over W-L", "over-under")
    # ---- the side ----
    slope_table(rows, [
        ("projm", "pace x efficiency margin projection, minus the spread's", lambda r: (r["proj_margin"] - (-r["spread"])) if "proj_margin" in r else None),
        ("missd", "missing regulars' minutes, away minus home (per 48)", lambda r: (r["a_miss_min"] - r["h_miss_min"]) / 48.0 if "a_miss_min" in r else None),
        ("missptsd", "missing regulars' points, away minus home (per 10)", lambda r: (r["a_miss_pts"] - r["h_miss_pts"]) / 10.0 if "a_miss_pts" in r else None),
        ("misspmd", "missing regulars' plus-minus a game, away minus home (per 5)", lambda r: (r["a_miss_pm"] - r["h_miss_pm"]) / 5.0 if "a_miss_pm" in r else None),
        ("restd", "rest days, home minus away (capped at 3)", lambda r: (min(r["hrest"], 3) - min(r["arest"], 3)) if r["arest"] is not None and r["hrest"] is not None else None),
        ("tz", "time zones the away side crossed (west negative), as home lean", lambda r: -r["tz"] if r["tz"] else None),
    ], "mres", log, "the SIDE: the margin's residual on the spread, on each input's lean (points, + = home)", 2.0)
    flag_table(rows, [
        ("away side on a back to back (home lean)", lambda r: r["a_b2b"]), ("home side on a back to back", lambda r: r["h_b2b"]), ("away side, second night on the road", lambda r: r["a_road_b2b"]),
        ("away side three in four", lambda r: r["a_3in4"]), ("home side three in four", lambda r: r["h_3in4"]), ("away side 4th+ game of a trip", lambda r: r["a_trip"] >= 4),
        ("away side crossed 2+ zones west", lambda r: r["tz"] <= -2), ("away side crossed 2+ zones east", lambda r: r["tz"] >= 2), ("at altitude", lambda r: r["altitude"]),
        ("after the deadline", lambda r: r["post_deadline"]), ("the last two weeks", lambda r: r["last_two_weeks"]),
        ("home favoured by 10+", lambda r: r["spread"] <= -10), ("home dog of 5+", lambda r: r["spread"] >= 5),
        ("away side missing 40+ minutes of regulars", lambda r: r.get("a_miss_min", 0) >= 40), ("home side missing 40+ minutes of regulars", lambda r: r.get("h_miss_min", 0) >= 40),
    ], "mres", log, "the SIDE by spot: the margin's residual on the spread (points, + = home), home covers W-L", "home ATS")
    # the crews: do they predict free throws at all?
    pts = [(r["crew_fta"], r["fta"]) for r in rows if r.get("crew_fta") and r.get("fta")]
    o = ols([p[0] for p in pts], [p[1] for p in pts])
    if o:
        log("")
        log("  crews DO predict tonight's free throws: slope %.2f (t %.1f) of the night's FTA on the crew's average to date, n %d" % (o[0], o[1], o[2]))
    # the first half: share by total level, for the half's pricing
    log("")
    log("===== the first half's share by closing total =====")
    for lab, v in (("220 or less", [r for r in q if r["close"] <= 220]), ("220.5 to 229.5", [r for r in q if 220 < r["close"] < 230]), ("230 to 239.5", [r for r in q if 230 <= r["close"] < 240]), ("240 or more", [r for r in q if r["close"] >= 240])):
        if v:
            h = [r["q"][0][0] + r["q"][0][1] + r["q"][1][0] + r["q"][1][1] for r in v]
            rg = [sum(r["q"][0]) + sum(r["q"][1]) for r in v]
            log("  %-16s %4d games: share %.4f, half %.1f against half the close %.1f (%+.2f)" % (lab, len(v), sum(h) / float(sum(rg)), avg(h), avg([r["close"] / 2.0 for r in v]), avg(h) - avg([r["close"] / 2.0 for r in v])))
    return rows


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
