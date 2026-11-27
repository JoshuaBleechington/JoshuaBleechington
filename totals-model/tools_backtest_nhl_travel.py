"""Travel spots, from the schedule alone, against two seasons of closes.

    python3 tools_backtest_nhl_travel.py FOLDER

FOLDER holds ledger2425r.json, ledger2526r.json (every game's date, home and away club) and
q1.html, q2.html (KillerSports' closing totals and home moneylines). From each club's sequence
of games: where it played last and when, how many road games in a row, how many games in the
last four and six nights, the time zones crossed since its last game and against its own
clock, and the miles flown. Each spot is read against the close two ways: the total's
residual and the over's record, and the home side's wins against the market's chance. Then
the continuous measures (miles, zones, games in four nights, trip length) as slopes on both.
Run 13 Oct 2026 at the user's word ("run the travel spots test too"). CALLSHEET3.md has the
table.
"""
import sys, os, math, collections, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tools_backtest_nhl as B                   # noqa: E402
from totals.fullgame import fair_total, implied  # noqa: E402

HOLD = 0.045
# arena coordinates and time zones (hours behind UTC in winter: ET 5, CT 6, MT 7, PT 8)
CLUBS = {
    "ANA": (33.81, -117.88, 8), "BOS": (42.37, -71.06, 5), "BUF": (42.88, -78.88, 5), "CGY": (51.04, -114.05, 7),
    "CAR": (35.80, -78.72, 5), "CHI": (41.88, -87.67, 6), "COL": (39.75, -105.01, 7), "CBJ": (39.97, -83.01, 5),
    "DAL": (32.79, -96.81, 6), "DET": (42.33, -83.06, 5), "EDM": (53.55, -113.49, 7), "FLA": (26.16, -80.33, 5),
    "LAK": (34.04, -118.27, 8), "MIN": (44.94, -93.10, 6), "MTL": (45.50, -73.57, 5), "NSH": (36.16, -86.78, 6),
    "NJD": (40.73, -74.17, 5), "NYI": (40.72, -73.59, 5), "NYR": (40.75, -73.99, 5), "OTT": (45.30, -75.93, 5),
    "PHI": (39.90, -75.17, 5), "PIT": (40.44, -79.99, 5), "SJS": (37.33, -121.90, 8), "SEA": (47.62, -122.35, 8),
    "STL": (38.63, -90.20, 6), "TBL": (27.94, -82.45, 5), "TOR": (43.64, -79.38, 5), "UTA": (40.77, -111.90, 7),
    "VAN": (49.28, -123.11, 8), "VGK": (36.10, -115.18, 8), "WSH": (38.90, -77.02, 5), "WPG": (49.89, -97.14, 6),
    "ARI": (33.53, -112.26, 7),
}


def miles(a, b):
    la1, lo1, _ = CLUBS[a]
    la2, lo2, _ = CLUBS[b]
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = math.radians(la2 - la1), math.radians(lo2 - lo1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 3959.0 * 2 * math.asin(math.sqrt(h))


def days(a, b):
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def spots(led):
    """team -> {date: spot dict} built from the club's own sequence of games."""
    seq = collections.defaultdict(list)
    for g in sorted(led, key=lambda g: (g["date"], g["id"])):
        if g.get("fa") is None:
            continue
        seq[g["home"]].append((g["date"], g["home"], True))
        seq[g["away"]].append((g["date"], g["home"], False))
    out = collections.defaultdict(dict)
    for team, games in seq.items():
        if team not in CLUBS:
            continue
        for i, (d, loc, home) in enumerate(games):
            prev = games[i - 1] if i else None
            road = 0
            for j in range(i - 1, -1, -1):
                if games[j][2]:
                    break
                road += 1
            in4 = sum(1 for j in range(i - 1, -1, -1) if days(games[j][0], d) <= 3)
            in6 = sum(1 for j in range(i - 1, -1, -1) if days(games[j][0], d) <= 5)
            s = {"rest": days(prev[0], d) - 1 if prev else None,
                 "miles": miles(prev[1], loc) if prev and loc in CLUBS and prev[1] in CLUBS else 0.0,
                 "zones_moved": (CLUBS[loc][2] - CLUBS[prev[1]][2]) if prev and loc in CLUBS and prev[1] in CLUBS else 0,
                 "clock": (CLUBS[loc][2] - CLUBS[team][2]) if loc in CLUBS else 0,   # + is west of the club's own clock
                 "road_game": (road + 1) if not home else 0,
                 "homecoming": home and road >= 3,
                 "in4": in4 + 1, "in6": in6 + 1}
            out[team][d] = s
    return out


def run(folder, log=print):
    rows = []
    for led_f, q in (("ledger2425r.json", "q1.html"), ("ledger2526r.json", "q2.html")):
        j, led = B.load(os.path.join(folder, led_f), os.path.join(folder, q))
        sp = spots(led)
        for g in j:
            d = g["date"]
            a, h = sp.get(g["away"], {}).get(d), sp.get(g["home"], {}).get(d)
            if not a or not h or a["rest"] is None or h["rest"] is None:
                continue
            anchor, _ = fair_total("NHL", g["total"], -110.0, -110.0)
            rows.append({"season": "2024" if "2425" in led_f else "2025", "line": g["total"], "anchor": anchor, "tot": g["fa"] + g["fh"],
                         "resid": g["fa"] + g["fh"] - anchor, "hw": 1.0 if g["fh"] > g["fa"] else 0.0,
                         "pm": min(max(implied(g["hml"]) - HOLD / 2, 0.02), 0.98) if g.get("hml") is not None else None, "a": a, "h": h})
    log("games with both clubs' schedule spots: %d" % len(rows))
    log("")
    log("%-52s %5s | %9s %6s %9s | %9s %6s" % ("spot", "n", "resid", "t", "the over", "home won", "vs mkt"))

    def line(name, v):
        if len(v) < 20:
            return
        res = B.avg([r["resid"] for r in v])
        se = math.sqrt(B.avg([(r["resid"] - res) ** 2 for r in v]) / len(v))
        ov = sum(1 for r in v if r["tot"] > r["line"])
        un = sum(1 for r in v if r["tot"] < r["line"])
        w = [r for r in v if r["pm"] is not None]
        hw = B.avg([r["hw"] for r in w]) if w else float("nan")
        pm = B.avg([r["pm"] for r in w]) if w else float("nan")
        log("%-52s %5d | %+9.3f %6.1f %4d-%-4d | %8.1f%% %+6.1f" % (name, len(v), res, res / se if se else float("nan"), ov, un, 100 * hw, 100 * (hw - pm)))
    line("everything", rows)
    line("away club crossed 2+ zones since its last game", [r for r in rows if abs(r["a"]["zones_moved"]) >= 2])
    line("  ...flying west (clock later)", [r for r in rows if r["a"]["zones_moved"] >= 2])
    line("  ...flying east (clock earlier)", [r for r in rows if r["a"]["zones_moved"] <= -2])
    line("away club 2+ zones off its own clock", [r for r in rows if abs(r["a"]["clock"]) >= 2])
    line("  ...an eastern club out west", [r for r in rows if r["a"]["clock"] >= 2])
    line("  ...a western club back east", [r for r in rows if r["a"]["clock"] <= -2])
    line("home club crossed 2+ zones to get home", [r for r in rows if abs(r["h"]["zones_moved"]) >= 2])
    line("away club 1,500+ miles since its last game", [r for r in rows if r["a"]["miles"] >= 1500])
    line("either club 1,500+ miles AND played yesterday", [r for r in rows if (r["a"]["miles"] >= 1500 and r["a"]["rest"] == 0) or (r["h"]["miles"] >= 1500 and r["h"]["rest"] == 0)])
    line("away club's 4th+ game of a road trip", [r for r in rows if r["a"]["road_game"] >= 4])
    line("away club's 1st game of a road trip", [r for r in rows if r["a"]["road_game"] == 1])
    line("home club's first game home after 3+ on the road", [r for r in rows if r["h"]["homecoming"]])
    line("away club's 3rd game in 4 nights", [r for r in rows if r["a"]["in4"] >= 3])
    line("home club's 3rd game in 4 nights", [r for r in rows if r["h"]["in4"] >= 3])
    line("both clubs' 3rd game in 4 nights", [r for r in rows if r["a"]["in4"] >= 3 and r["h"]["in4"] >= 3])
    line("either club's 4th game in 6 nights", [r for r in rows if r["a"]["in6"] >= 4 or r["h"]["in6"] >= 4])
    line("both clubs on 2+ days' rest", [r for r in rows if r["a"]["rest"] >= 2 and r["h"]["rest"] >= 2])
    line("home rested 2+, away played yesterday", [r for r in rows if r["h"]["rest"] >= 2 and r["a"]["rest"] == 0])
    line("away rested 2+, home played yesterday", [r for r in rows if r["a"]["rest"] >= 2 and r["h"]["rest"] == 0])
    log("")
    log("===== continuous measures, as slopes =====")
    log("%-44s %9s %6s | %9s %6s" % ("measure", "b on tot", "t", "b on home", "t"))

    def slope(pairs):
        xs = [a for a, b in pairs]
        ys = [b for a, b in pairs]
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        if sxx <= 0 or n < 4:
            return float("nan"), float("nan")
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
        a = my - b * mx
        s2 = sum((y - a - b * x) ** 2 for x, y in zip(xs, ys)) / (n - 2)
        return b, math.sqrt(s2 / sxx)
    for name, fx in (("miles since the last game, both clubs (per 1,000)", lambda r: (r["a"]["miles"] + r["h"]["miles"]) / 1000.0),
                     ("away miles minus home miles (per 1,000)", lambda r: (r["a"]["miles"] - r["h"]["miles"]) / 1000.0),
                     ("zones the away club sits off its clock", lambda r: abs(r["a"]["clock"])),
                     ("away games in 4 nights minus home's", lambda r: r["a"]["in4"] - r["h"]["in4"]),
                     ("both clubs' games in 4 nights", lambda r: r["a"]["in4"] + r["h"]["in4"]),
                     ("away road-trip game number", lambda r: r["a"]["road_game"]),
                     ("away rest minus home rest (capped 3)", lambda r: min(r["a"]["rest"], 3) - min(r["h"]["rest"], 3))):
        b1, se1 = slope([(fx(r), r["resid"]) for r in rows])
        w = [r for r in rows if r["pm"] is not None]
        b2, se2 = slope([(fx(r), r["hw"] - r["pm"]) for r in w])
        log("%-44s %+9.3f %6.1f | %+9.4f %6.1f" % (name, b1, b1 / se1, b2, b2 / se2))
    return rows


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
