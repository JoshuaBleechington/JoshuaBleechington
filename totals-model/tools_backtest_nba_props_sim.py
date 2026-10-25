"""Does the game's expected scoring help the player props? (25 Oct 2026)

    python3 tools_backtest_nba_props_sim.py LEDGER.json KILLERSPORTS.html [sim-backtest.json]

The props projection is rate x minutes from the player's own games. Two
candidate levers from the game itself, tested on every player-game of a
season with eight prior games and fifteen projected minutes:

  market: the club's points implied by the closing total and spread,
          (total -/+ spread) / 2, against the club's points a game to date;
  sim:    the club's points in the simulation's own view (tools_backtest_nba_sim.py's
          rows, when given), against the same.

Each lever scales the projection by the ratio to a power (0, 0.5, 1.0).
Reported, per market: the bias, the root mean square miss, and the slope of
the projection's miss on the lever (the honest test: does the lever explain
what the projection gets wrong?). A lever that cuts the miss goes into
props_project; one that does not stays out.
"""
import json
import math
import sys
from collections import defaultdict

from tools_backtest_nba import ks_rows, TEAMS, ols
from tools_backtest_nba_props import val, load

MIN_PRIOR = 8
MIN_MINUTES = 15


def team_points_to_date(games):
    """{(date, ab): (points a game, possessions a game) before that date}, from the ledger; and the league's possessions a game."""
    acc = defaultdict(lambda: [0, 0, 0.0])
    lg = [0.0, 0]
    out = {}
    for g in games:
        for ab, pts, line in ((g["away"], g["fa"], g.get("sa") or {}), (g["home"], g["fh"], g.get("sh") or {})):
            a = acc[ab]
            out[(g["date"], ab)] = (a[0] / float(a[1]), a[2] / float(a[1]), lg[0] / lg[1] if lg[1] else None) if a[1] else None
            poss = (line.get("fga", 0) - line.get("oreb", 0) + line.get("tov", 0) + 0.44 * line.get("fta", 0)) if line else 0.0
            a[0] += pts
            a[1] += 1
            a[2] += poss
            lg[0] += poss
            lg[1] += 1
    return out


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    games = load(argv[0])
    games = [g for g in games if g.get("hn") in TEAMS and g.get("an") in TEAMS]
    ks = {(r["date"], r["home"], r["away"]): r for r in ks_rows(argv[1])}
    sim = {}
    if len(argv) > 2:
        for r in json.load(open(argv[2])):
            sim[(r["date"], r["away"], r["home"])] = r
    ppg = team_points_to_date(games)
    hist = defaultdict(list)
    rows = []
    for g in games:
        k = ks.get((g["date"], g["hn"], g["an"]))
        s = sim.get((g["date"], g["away"], g["home"]))
        for key, ab, opp in (("pa", g["away"], g["home"]), ("ph", g["home"], g["away"])):
            implied = None
            if k and k["total"] is not None and k["spread"] is not None:
                implied = (k["total"] + k["spread"]) / 2.0 if key == "pa" else (k["total"] - k["spread"]) / 2.0   # the spread is the home side's
            own = None
            if s:
                own = (s["sim_total"] - s["sim_margin"]) / 2.0 if key == "pa" else (s["sim_total"] + s["sim_margin"]) / 2.0
            td, to = ppg.get((g["date"], ab)), ppg.get((g["date"], opp))
            base = td[0] if td else None
            # the pace lever the props run already carries: the game's expected possessions against the club's own
            pace_ratio = None
            if td and to and td[1] and td[2]:
                pace_ratio = max(0.8, min(1.25, (td[1] + to[1] - td[2]) / td[1]))
            for p in g.get(key) or []:
                pid, mins = str(p[0]), float(p[3])
                h = hist[pid]
                if len(h) >= MIN_PRIOR and base:
                    m_this = sum(x[0] for x in h)
                    pm = sum(x[0] for x in h[-5:]) / 5.0
                    if pm >= MIN_MINUTES and m_this > 0:
                        row = {"pm": pm, "implied": implied, "own": own, "base": base, "pace": pace_ratio, "act": {}, "mu": {}}
                        for mk in ("pts", "reb", "ast", "pra"):
                            rate = sum(x[1][mk] for x in h) / m_this
                            row["mu"][mk] = rate * pm
                            row["act"][mk] = val(p, mk)
                        rows.append(row)
                h.append((mins, {mk: val(p, mk) for mk in ("pts", "reb", "ast", "pra")}))
    print("%d player-games with a projection; %d with the market's implied points, %d with the sim's own" % (
        len(rows), sum(1 for r in rows if r["implied"]), sum(1 for r in rows if r["own"])))
    for lever in ("market", "sim"):
        key = "implied" if lever == "market" else "own"
        rs = [r for r in rows if r[key] and r["base"]]
        if not rs:
            continue
        print()
        print("== the %s lever: the club's expected points against its points a game to date (%d player-games) ==" % (lever, len(rs)))
        for mk in ("pts", "reb", "ast", "pra"):
            floor = 6 if mk in ("pts", "pra") else 1.0
            sel = [r for r in rs if r["mu"][mk] >= floor]
            xs = [math.log(r[key] / r["base"]) for r in sel]
            line = "%-4s n %6d " % (mk, len(sel))
            for alpha in (0.0, 0.5, 1.0):
                errs = [(r["act"][mk] - r["mu"][mk] * (r[key] / r["base"]) ** alpha) for r in sel]
                rmse = math.sqrt(sum(e * e for e in errs) / len(errs))
                bias = sum(errs) / len(errs)
                line += " | a=%.1f bias %+.2f rmse %.3f" % (alpha, bias, rmse)
            ys = [(r["act"][mk] - r["mu"][mk]) / math.sqrt(r["mu"][mk]) for r in sel]
            o = ols(xs, ys)
            line += " | miss on log ratio: slope %+.2f (t %.1f)" % (o[0], o[1]) if o else ""
            print(line)
        # beyond the pace lever: the base scaled by the game's expected possessions, and the lever's remainder (its efficiency part)
        print("  beyond the pace lever the props already carry:")
        for mk in ("pts", "reb", "ast", "pra"):
            floor = 6 if mk in ("pts", "pra") else 1.0
            sel = [r for r in rs if r["mu"][mk] >= floor and r["pace"]]
            xs = [math.log(r[key] / r["base"] / r["pace"]) for r in sel]
            out = "  %-4s n %6d " % (mk, len(sel))
            for alpha in (0.0, 0.5, 1.0):
                errs = [(r["act"][mk] - r["mu"][mk] * r["pace"] * (r[key] / r["base"] / r["pace"]) ** alpha) for r in sel]
                out += " | pace x rest^%.1f rmse %.3f" % (alpha, math.sqrt(sum(e * e for e in errs) / len(errs)))
            ys = [(r["act"][mk] - r["mu"][mk] * r["pace"]) / math.sqrt(r["mu"][mk]) for r in sel]
            o = ols(xs, ys)
            out += " | miss after pace on the rest: slope %+.2f (t %.1f)" % (o[0], o[1]) if o else ""
            print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
