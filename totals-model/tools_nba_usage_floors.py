#!/usr/bin/env python3
"""Two questions the user asked of the props (26 Oct 2026): does a player's
USAGE RATE say anything the projection does not, and are the model's FLOORS
honest, the number a man clears 95% (90%, 80%) of the time, which is what an
alternate line like "10+ points" is priced on.

Both are asked of a season's ledger alone, the way tools_backtest_nba_props.py
asks its questions: every player-game after eight prior games this season,
the projection built the slate's way (his per-minute rate to date times his
last five games' minutes, the chance read around the median with the
measured sigma), the actual from the box.

    python3 tools_nba_usage_floors.py slate/nba-ledger-202526.json
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "slate"))
import slate  # noqa: E402

KEYS = {"pts": 4, "reb": 6, "ast": 7, "tpm": 8}
Z = {0.80: 0.8416, 0.90: 1.2816, 0.95: 1.6449}
MIN_PRIOR = 8


def val(p, mk):
    return p[4] + p[6] + p[7] if mk == "pra" else p[KEYS[mk]]


def main(argv):
    if not argv:
        print(__doc__); return 2
    led = json.load(open(argv[0]))
    games = sorted(led["games"], key=lambda g: (g["date"], g["id"]))
    hist = defaultdict(lambda: {"g": [], "team": None})
    rows = []
    for g in games:
        for key, ab, tline in (("pa", g["away"], g["sa"]), ("ph", g["home"], g["sh"])):
            tm = float(tline.get("min") or 240.0)
            tpos = (tline.get("fga") or 0) + 0.44 * (tline.get("fta") or 0) + (tline.get("tov") or 0)
            for p in g.get(key) or []:
                if len(p) < 17:
                    continue
                pid, mins = str(p[0]), float(p[3] or 0)
                h = hist[pid]
                prior = [x for x in h["g"] if x["team"] == ab]
                if mins > 0 and len(prior) >= MIN_PRIOR:
                    pm = sum(x["min"] for x in prior)
                    last5 = prior[-5:]
                    mins_proj = sum(x["min"] for x in last5) / len(last5)
                    usage = 100.0 * sum(x["u"] for x in prior) / sum(x["tu"] for x in prior) if sum(x["tu"] for x in prior) > 0 else None
                    for mk in ("pts", "reb", "ast", "tpm", "pra"):
                        rate = sum(x["v"][mk] for x in prior) / pm if pm > 0 else 0.0
                        proj = rate * mins_proj
                        if proj < 1.0:
                            continue
                        sd = slate.PROPS_SD_K[mk] * math.sqrt(proj)
                        med = proj - slate.PROPS_MEDIAN_SHIFT[mk] * sd
                        rows.append({"mk": mk, "proj": proj, "med": med, "sd": sd, "act": val(p, mk), "usage": usage, "mins": mins, "mins_proj": mins_proj, "date": g["date"], "gid": g["id"], "team": ab, "pid": pid, "st_prev": prior[-1]["st"], "st": int(p[2] or 0)})
                # the player's own usage share of his club's possessions while he is on the floor
                u = (p[9] + 0.44 * p[10] + p[11]) if mins > 0 else 0.0
                tu = (tpos * mins / (tm / 5.0)) if (mins > 0 and tm > 0) else 0.0   # the club's possessions while he is on the floor: its 240 player-minutes are 48 of game
                h["g"].append({"team": ab, "min": mins, "st": int(p[2] or 0), "v": {mk: val(p, mk) for mk in ("pts", "reb", "ast", "tpm", "pra")}, "u": u, "tu": tu})
    print("%d player-game projections after %d prior games" % (len(rows), MIN_PRIOR))
    us = sorted(r["usage"] for r in rows if r["mk"] == "pts" and r["usage"] is not None)
    print("usage to date, points rows: 10th %.1f  median %.1f  90th %.1f  (n %d)" % (us[len(us) // 10], us[len(us) // 2], us[9 * len(us) // 10], len(us)))
    # 1. usage: the projection's miss and the over rate by the player's usage to date
    print()
    print("== usage rate: the projection's miss by the player's usage to date (points and PRA, the usage markets) ==")
    buckets = [("under 18%", 0, 18), ("18 to 24%", 18, 24), ("24% and up", 24, 99)]
    for mk in ("pts", "pra", "ast", "reb"):
        print("  %s" % mk)
        for lab, lo, hi in buckets:
            rs = [r for r in rows if r["mk"] == mk and r["usage"] is not None and lo <= r["usage"] < hi]
            if len(rs) < 100:
                continue
            miss = [r["act"] - r["proj"] for r in rs]
            z = [(r["act"] - r["med"]) / r["sd"] for r in rs]
            over = sum(1 for r in rs if r["act"] > r["med"]) / len(rs)
            sdz = statistics.pstdev(z)
            print("    %-12s n %5d  miss %+.2f (t %+.1f)  over the median %.1f%%  miss in sigmas %.2f  within one sigma %.0f%%" % (
                lab, len(rs), statistics.mean(miss), statistics.mean(miss) / (statistics.pstdev(miss) / math.sqrt(len(miss))), 100 * over, sdz, 100 * sum(1 for x in z if abs(x) <= 1) / len(z)))
    # 1a. starters against the bench, by usage: the miss in sigmas and the over rate, with "started his last game" as what the slate can know
    print()
    print("== starters against the bench (started his previous game), by usage: the miss in sigmas, the over rate, the 90% floor cleared ==")
    for mk in ("pts", "pra", "reb", "ast"):
        for lab, lo, hi in buckets:
            parts = []
            for st_lab, st in (("starter", 1), ("bench", 0)):
                rs = [r for r in rows if r["mk"] == mk and r["usage"] is not None and lo <= r["usage"] < hi and r["st_prev"] == st]
                if len(rs) < 200:
                    continue
                z = [(r["act"] - r["med"]) / r["sd"] for r in rs]
                fl = [r for r in rs if r["med"] - Z[0.90] * r["sd"] >= 0.5]
                hit = sum(1 for r in fl if r["act"] >= r["med"] - Z[0.90] * r["sd"]) / len(fl) if fl else float("nan")
                parts.append("%s n %5d sigmas %.2f over %.1f%% 90%% floor %.1f%% (%d)" % (st_lab, len(rs), statistics.pstdev(z), 100 * sum(1 for r in rs if r["act"] > r["med"]) / len(rs), 100 * hit, len(fl)))
            if parts:
                print("  %-4s %-11s %s" % (mk, lab, " · ".join(parts)))
    # 1b. is the usage-sigma stable? the miss in sigmas by bucket, first half of the season against the second
    print()
    print("== the sigma by usage, first half of the season (to 14 Jan) against the second: stable, and it is a factor worth carrying ==")
    for mk in ("pts", "pra", "reb", "ast"):
        parts = []
        for lab, lo, hi in buckets:
            for half, sel in (("H1", lambda r: r["date"] < "2026-01-15"), ("H2", lambda r: r["date"] >= "2026-01-15")):
                rs = [r for r in rows if r["mk"] == mk and r["usage"] is not None and lo <= r["usage"] < hi and sel(r)]
                if len(rs) < 100:
                    continue
                parts.append("%s %s %.2f (n %d)" % (lab, half, statistics.pstdev([(r["act"] - r["med"]) / r["sd"] for r in rs]), len(rs)))
        print("  %-4s %s" % (mk, " · ".join(parts)))
    # 2. the floors: how often the man clears the number the model says he clears 80, 90, 95% of the time
    print()
    print("== the floors: the share of games the man clears the model's 80 / 90 / 95% number (a floor under 0.5 is skipped) ==")
    for mk in ("pts", "reb", "ast", "tpm", "pra"):
        rs = [r for r in rows if r["mk"] == mk]
        line = "  %-4s n %5d " % (mk, len(rs))
        for q, zq in sorted(Z.items()):
            sel = [r for r in rs if r["med"] - zq * r["sd"] >= 0.5]
            hit = sum(1 for r in sel if r["act"] >= r["med"] - zq * r["sd"]) / len(sel) if sel else float("nan")
            line += "  %.0f%% floor: cleared %.1f%% (%d)" % (100 * q, 100 * hit, len(sel))
        print(line)
    # 3. the floors at a whole number, the way an alternate line is posted: the floor rounded DOWN to the next half point
    print()
    print("== the same, with the floor posted as a book's line (the model's number rounded down to the half point, 'x+' meaning x or more) ==")
    for mk in ("pts", "reb", "ast", "pra"):
        rs = [r for r in rows if r["mk"] == mk]
        line = "  %-4s " % mk
        for q, zq in sorted(Z.items()):
            sel, hit = 0, 0
            for r in rs:
                f = math.floor(r["med"] - zq * r["sd"])
                if f < 1:
                    continue
                sel += 1; hit += 1 if r["act"] >= f else 0
            line += "  %.0f%%: %d+ lines cleared %.1f%% (%d)" % (100 * q, 0, 100.0 * hit / sel if sel else float("nan"), sel) if False else "  %.0f%% line cleared %.1f%% (%d)" % (100 * q, 100.0 * hit / sel if sel else float("nan"), sel)
        print(line)
    # 4. a three-leg floor ladder (points, rebounds, assists at the 95% number, one man): how often all three clear
    print()
    print("== three legs at the 95% number for one man (points, rebounds, assists in the same game): all three cleared ==")
    by_game = defaultdict(dict)
    for g in games:
        pass
    # rows carry no game id; rebuild the ladder from the rows' order: consecutive pts/reb/ast/tpm/pra rows belong to one player-game
    legs, ok, n = {}, 0, 0
    i = 0
    while i < len(rows):
        grp = {}
        j = i
        while j < len(rows) and len(grp) < 5 and rows[j]["mk"] not in grp:
            grp[rows[j]["mk"]] = rows[j]; j += 1
        if all(k in grp for k in ("pts", "reb", "ast")):
            fl = {k: math.floor(grp[k]["med"] - Z[0.95] * grp[k]["sd"]) for k in ("pts", "reb", "ast")}
            if all(v >= 1 for v in fl.values()):
                n += 1; ok += 1 if all(grp[k]["act"] >= fl[k] for k in fl) else 0
        i = j
    print("  %d player-games with three floors at 1 or more: all three cleared %.1f%% (the model's say-so for three independent 95%% legs: %.1f%%)" % (n, 100.0 * ok / max(1, n), 100 * 0.95 ** 3))
    # 5. two props in the same game (26 Oct 2026, the user: "the ones that hit quickly were same game parlays with 2 legs"):
    #    how often both legs land against what two independent legs would, same club and opposite clubs, at the median and at the 80% floor
    print()
    print("== two legs in the same game: both landing, against the product of the two chances (points, players projected at 10 or more) ==")
    from itertools import combinations
    by_game = defaultdict(list)
    for r in rows:
        if r["mk"] == "pts" and r["proj"] >= 10:
            by_game[r["gid"]].append(r)
    for lab, zq, say in (("over the median, both", 0.0, 0.5 * 0.5), ("over the 80% floor, both", Z[0.80], 0.8 * 0.8)):
        same = [0, 0]; opp = [0, 0]
        for gid, rs in by_game.items():
            for a, b in combinations(rs, 2):
                if a["pid"] == b["pid"]:
                    continue
                ha = a["act"] > a["med"] - zq * a["sd"] if zq else a["act"] > a["med"]
                hb = b["act"] > b["med"] - zq * b["sd"] if zq else b["act"] > b["med"]
                t = same if a["team"] == b["team"] else opp
                t[0] += 1; t[1] += 1 if (ha and hb) else 0
        print("  %-26s same club: %.1f%% of %d pairs (independent %.1f%%) · opposite clubs: %.1f%% of %d (independent %.1f%%)" % (
            lab, 100.0 * same[1] / max(1, same[0]), same[0], 100 * say, 100.0 * opp[1] / max(1, opp[0]), opp[0], 100 * say))
    # one over and one under in the same game
    both = [0, 0, 0, 0]   # same club over+under hits, n; opposite over+under hits, n
    for gid, rs in by_game.items():
        for a, b in combinations(rs, 2):
            if a["pid"] == b["pid"]:
                continue
            ha, hb = a["act"] > a["med"], b["act"] < b["med"]
            i = 0 if a["team"] == b["team"] else 2
            both[i + 1] += 1; both[i] += 1 if (ha and hb) else 0
    print("  %-26s same club: %.1f%% of %d (independent 25.0%%) · opposite clubs: %.1f%% of %d" % ("one over, one under", 100.0 * both[0] / max(1, both[1]), both[1], 100.0 * both[2] / max(1, both[3]), both[3]))
    # the same man, two markets: points with rebounds, points with assists, rebounds with assists, both over the median and both over the 80% floor
    print()
    print("== the same man, two markets in one game: both landing against the product ==")
    bypg = defaultdict(dict)
    for r in rows:
        bypg[(r["gid"], r["pid"])][r["mk"]] = r
    for a_mk, b_mk in (("pts", "reb"), ("pts", "ast"), ("reb", "ast"), ("pts", "tpm")):
        for lab, zq, say in (("median", 0.0, 0.25), ("80% floor", Z[0.80], 0.64)):
            n = hit = 0
            for d in bypg.values():
                a, b = d.get(a_mk), d.get(b_mk)
                if not a or not b or a["proj"] < (6 if a_mk == "pts" else 1.5) or b["proj"] < 1.5:
                    continue
                ha = a["act"] > a["med"] - zq * a["sd"] if zq else a["act"] > a["med"]
                hb = b["act"] > b["med"] - zq * b["sd"] if zq else b["act"] > b["med"]
                n += 1; hit += 1 if (ha and hb) else 0
            print("  %s + %s over the %-9s both %.1f%% of %d (independent %.0f%%)" % (a_mk, b_mk, lab, 100.0 * hit / max(1, n), n, 100 * say))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
