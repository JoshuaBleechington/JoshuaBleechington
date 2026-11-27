#!/usr/bin/env python3
"""Should last season's prior count for less on a club that changed its roster?
(26 Oct 2026, after the Pacers at the Nets: the sim's profile was 90% last
season's Pacers, who had no Haliburton.)

The club model blends this season's ratings with last season's at a prior
weight of k games (15 in profiles_from_ledger). Here the prior's weight is
scaled by the club's roster continuity, the share of last season's minutes
played by men who have dressed for the club this season, and every 2025-26
game is predicted both ways from the ledgers as they stood before it: the
error of the margin and the total against the final, by month, and whether
either version adds to the close.

Usage: python3 tools_nba_prior_test.py STINTS_DIR NBA_DIR
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "slate"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nbasim  # noqa: E402
from tools_backtest_nba_sim import load_season  # noqa: E402


def continuity(prior_games, this_games, ab, date):
    """The share of last season's minutes for the club played by men who have dressed for it this season before the date."""
    last_mins, dressed = {}, set()
    for g in prior_games:
        for side, key in (("away", "pa"), ("home", "ph")):
            if g[side] != ab:
                continue
            for p in g[key]:
                last_mins[str(p[0])] = last_mins.get(str(p[0]), 0.0) + float(p[3] or 0)
    for g in this_games:
        if g["date"] >= date:
            continue
        for side, key in (("away", "pa"), ("home", "ph")):
            if g[side] != ab:
                continue
            for p in g[key]:
                if float(p[3] or 0) > 0:
                    dressed.add(str(p[0]))
    tot = sum(last_mins.values())
    return (sum(m for pid, m in last_mins.items() if pid in dressed) / tot) if tot else 1.0


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    sdir, ndir = argv[0], argv[1]
    led_prev = json.load(open(os.path.join(sdir, "nba-ledger-202425.json")))["games"]
    led_this = json.load(open(os.path.join(sdir, "nba-ledger-202526.json")))["games"]
    led, joined = load_season(ndir, "led2526.json", "a6af4eb0-query.html")
    full_prior = nbasim.profiles_from_ledger(led_prev, "2025-07-01")   # last season whole
    rows, cache = [], {}
    K = 15.0
    variants = {"k=15 (as the sim)": lambda n, c: K, "k=15 x continuity": lambda n, c: K * c, "k=15 x continuity^2": lambda n, c: K * c * c, "k=8": lambda n, c: 8.0, "k=25": lambda n, c: 25.0}
    for g in sorted(joined, key=lambda g: g["date"]):
        if g["date"] not in cache:
            cache[g["date"]] = nbasim.profiles_from_ledger(led_this, g["date"], prior_games=None)   # this season alone
        this = cache[g["date"]]
        row = {"date": g["date"], "fa": g["fa"], "fh": g["fh"], "close": g["close_total"], "spread": g["close_spread"], "pred": {}}
        ok = True
        for name, kf in variants.items():
            sides = {}
            for ab in (g["away"], g["home"]):
                t, p = this["teams"].get(ab), full_prior["teams"].get(ab)
                if not p:
                    ok = False; break
                n = t["n"] if t else 0
                c = continuity(led_prev, led_this, ab, g["date"])
                k = kf(n, c)
                if n + k <= 0:
                    ok = False; break
                blend = lambda key: ((t[key] * n if t else 0.0) + p[key] * k) / (n + k)  # noqa: E731
                sides[ab] = {"ortg": blend("ortg"), "drtg": blend("drtg"), "pace": blend("pace"), "c": c, "n": n}
            if not ok:
                break
            lg = this["league"] if this["league"].get("n", 0) >= 20 else full_prior["league"]
            a, h = sides[g["away"]], sides[g["home"]]
            poss = a["pace"] + h["pace"] - lg["pace"]
            pa = ((a["ortg"] + h["drtg"] - lg["ortg"]) / 100.0 - lg["home"] / 2.0 / lg["pace"]) * poss
            ph = ((h["ortg"] + a["drtg"] - lg["ortg"]) / 100.0 + lg["home"] / 2.0 / lg["pace"]) * poss
            row["pred"][name] = (pa, ph)
            row["c"] = (a["c"], h["c"]); row["n"] = min(a["n"], h["n"])
        if ok and row["pred"]:
            rows.append(row)
    print("%d games with a close and both clubs profiled; roster continuity at the first game: mean %.2f, lowest %.2f" % (
        len(rows), np.mean([min(r["c"]) for r in rows if r["n"] <= 1] or [0]), min([min(r["c"]) for r in rows] or [0])))

    def table(rs, label):
        print()
        print("== %s: %d games ==" % (label, len(rs)))
        marg = np.array([r["fh"] - r["fa"] for r in rs]); tot = np.array([r["fa"] + r["fh"] for r in rs])
        cm = np.array([-r["spread"] for r in rs]); ct = np.array([r["close"] for r in rs])
        print("  %-22s %12s %12s   %s" % ("prior weight", "margin RMSE", "total RMSE", "adds to the close? (coef, t: margin / total)"))
        print("  %-22s %12.2f %12.2f" % ("the close", np.sqrt(np.mean((marg - cm) ** 2)), np.sqrt(np.mean((tot - ct) ** 2))))
        for name in variants:
            pm = np.array([r["pred"][name][1] - r["pred"][name][0] for r in rs]); pt = np.array([r["pred"][name][0] + r["pred"][name][1] for r in rs])
            def tstat(yv, c, x):
                X = np.column_stack([np.ones(len(yv)), c, x]); beta = np.linalg.lstsq(X, yv, rcond=None)[0]
                resid = yv - X @ beta; s2 = (resid @ resid) / max(1, len(yv) - 3); cov = s2 * np.linalg.inv(X.T @ X)
                return beta[2], beta[2] / np.sqrt(cov[2, 2])
            bm, tm = tstat(marg, cm, pm); bt, tt = tstat(tot, ct, pt)
            print("  %-22s %12.2f %12.2f   %+.2f t %+.1f / %+.2f t %+.1f" % (name, np.sqrt(np.mean((marg - pm) ** 2)), np.sqrt(np.mean((tot - pt) ** 2)), bm, tm, bt, tt))
    table(rows, "every game")
    table([r for r in rows if r["date"] < "2025-11-20"], "the first month (to 19 Nov)")
    table([r for r in rows if r["n"] <= 5], "games where a club had five games or fewer behind it")
    table([r for r in rows if min(r["c"]) < 0.6], "games where a club kept under 60% of last season's minutes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
