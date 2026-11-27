"""The player props' constants, measured on a season's NBA ledger with the box
lines (19 Oct 2026). Nothing here needs a line: it asks of the ledger alone
whether a projection built the slate's way is unbiased, how wide its miss
is, whether missing regulars lift a player, whether a player's own home and
road split persists, and whether a defence's lean by position carries from
one half of the season to the other.

    python3 tools_backtest_nba_props.py slate/nba-ledger-202526.json

Read against 2025-26 (1,235 games, 26,628 player lines) on 19 Oct 2026; the
figures went into slate/slate.py as PROPS_SD_K, PROPS_OUT_MIN_PER30,
PROPS_OUT_RATE_PER30 and PROPS_DVP_WEIGHT, and the home/road split into the
"shown, not scored" line. Run it again on a new season before trusting the
old numbers.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, defaultdict

KEYS = {"pts": 4, "reb": 6, "ast": 7, "tpm": 8}
POS3 = {"PG": "G", "SG": "G", "G": "G", "SF": "F", "PF": "F", "F": "F", "C": "C"}


def val(p, mk):
    if mk == "pra":
        return p[4] + p[6] + p[7]
    if mk == "pr":    # the combination markets (27 Oct 2026)
        return p[4] + p[6]
    if mk == "pa":
        return p[4] + p[7]
    if mk == "ra":
        return p[6] + p[7]
    return p[KEYS[mk]]


def load(path):
    led = json.load(open(path))
    games = sorted(led["games"], key=lambda g: (g["date"], g["id"]))
    lens = Counter(len(p) for g in games for p in (g.get("pa") or []) + (g.get("ph") or []))
    if lens.get(17, 0) < sum(lens.values()):
        sys.exit("this ledger carries %s player lines; run the ledger once more so every line is 17 long (the box stats)" % dict(lens))
    return games


def scatter(games):
    """A rate x last-five-minutes projection from the player's prior games this season: bias and the miss, per market."""
    out = {}
    for mk in ("pts", "reb", "ast", "tpm", "pra", "pr", "pa", "ra"):
        hist, errs = defaultdict(list), []
        for g in games:
            for key in ("pa", "ph"):
                for p in g.get(key) or []:
                    pid, mins, v = str(p[0]), float(p[3]), val(p, mk)
                    h = hist[pid]
                    if len(h) >= 8:
                        m_this = sum(x[0] for x in h)
                        rate = sum(x[1] for x in h) / m_this if m_this > 0 else 0.0
                        pm = sum(x[0] for x in h[-5:]) / 5.0
                        mu = rate * pm
                        if pm >= 15 and mu >= (6 if mk in ("pts", "pra", "pr", "pa") else 1.0):
                            errs.append((mu, v))
                    h.append((mins, v))
        n = len(errs)
        bias = sum(a - m for m, a in errs) / n
        k = math.sqrt(sum((a - m) ** 2 / m for m, a in errs) / n)
        inside = sum(1 for m, a in errs if abs(a - m) <= k * math.sqrt(m)) / n
        out[mk] = (n, bias, k, inside)
        print("%-4s n %6d  bias %+.2f  one sigma = %.2f x sqrt(projection)  within one sigma %.3f (a normal says 0.683)" % (mk, n, bias, k, inside))
    return out


def regulars_out(games):
    """Pooled: a player's minutes and per-36 rates against the minutes a game of his club's regulars who did not play."""
    tot = defaultdict(lambda: {"g": 0, "min": 0.0, "team": None, "s": defaultdict(float)})
    for g in games:
        for key, ab in (("pa", g["away"]), ("ph", g["home"])):
            for p in g.get(key) or []:
                d = tot[str(p[0])]
                d["g"] += 1
                d["min"] += p[3]
                d["team"] = ab
                for mk in KEYS:
                    d["s"][mk] += val(p, mk)
    regular = {pid for pid, d in tot.items() if d["g"] >= 30 and d["min"] / d["g"] >= 24}
    club = defaultdict(set)
    for pid in regular:
        club[tot[pid]["team"]].add(pid)
    rows = []
    for g in games:
        for key, ab in (("pa", g["away"]), ("ph", g["home"])):
            played = {str(p[0]) for p in g.get(key) or []}
            miss = sum(tot[pid]["min"] / tot[pid]["g"] for pid in club.get(ab, ()) if pid not in played)
            for p in g.get(key) or []:
                d = tot[str(p[0])]
                if d["g"] < 20 or d["min"] / d["g"] < 15 or p[3] <= 0:
                    continue
                rows.append((miss, p[3] - d["min"] / d["g"], {mk: val(p, mk) / p[3] * 36 - d["s"][mk] / d["min"] * 36 for mk in KEYS}))
    xs = [r[0] for r in rows]
    mx = sum(xs) / len(xs)
    sxx = sum((x - mx) ** 2 for x in xs)

    def slope(ys):
        my = sum(ys) / len(ys)
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
        se = math.sqrt(sum((y - my - b * (x - mx)) ** 2 for x, y in zip(xs, ys)) / (len(xs) - 2) / sxx)
        return b * 30, b / se
    print("regulars out, per 30 minutes a game missing (%d player-games): minutes %+.2f (t %.1f)" % ((len(rows),) + slope([r[1] for r in rows])))
    for mk in KEYS:
        print("   %s per 36 %+.3f (t %.1f)" % ((mk,) + slope([r[2][mk] for r in rows])))


def home_road(games):
    """Does a player's own home/road split over the first half of the season predict the second half's?"""
    mid = games[len(games) // 2]["date"]
    first, second = defaultdict(lambda: {"h": [0.0, 0.0], "r": [0.0, 0.0]}), defaultdict(lambda: {"h": [0.0, 0.0], "r": [0.0, 0.0]})
    for g in games:
        tgt = first if g["date"] < mid else second
        for key, side in (("pa", "r"), ("ph", "h")):
            for p in g.get(key) or []:
                d = tgt[str(p[0])][side]
                d[0] += float(p[3])
                d[1] += float(p[4])
    xs, ys = [], []
    for pid in first:
        a, b = first[pid], second.get(pid)
        if not b or min(a["h"][0], a["r"][0], b["h"][0], b["r"][0]) < 300:
            continue
        xs.append(a["h"][1] / a["h"][0] * 36 - a["r"][1] / a["r"][0] * 36)
        ys.append(b["h"][1] / b["h"][0] * 36 - b["r"][1] / b["r"][0] * 36)
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    r = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    print("home/road split in points per 36, first half against second half of the season: n %d, correlation %.3f" % (n, r))


def defence_by_position(games):
    """A defence's first-half lean by position (per minute, against the league) against second-half outcomes relative to each player's own first-half rate."""
    mid = games[len(games) // 2]["date"]
    for mk in KEYS:
        allowed = defaultdict(lambda: [0.0, 0.0])
        for g in games:
            if g["date"] >= mid:
                continue
            for key, opp in (("pa", g["home"]), ("ph", g["away"])):
                for p in g.get(key) or []:
                    ps = POS3.get(p[16])
                    if not ps or p[3] <= 0:
                        continue
                    a = allowed[(opp, ps)]
                    a[0] += val(p, mk)
                    a[1] += p[3]
        lg = defaultdict(lambda: [0.0, 0.0])
        for (opp, ps), (s, m) in allowed.items():
            lg[ps][0] += s
            lg[ps][1] += m
        factor = {k: (v[0] / v[1]) / (lg[k[1]][0] / lg[k[1]][1]) for k, v in allowed.items() if v[1] > 0}
        own = defaultdict(lambda: [0.0, 0.0])
        for g in games:
            if g["date"] >= mid:
                continue
            for key in ("pa", "ph"):
                for p in g.get(key) or []:
                    o = own[str(p[0])]
                    o[0] += val(p, mk)
                    o[1] += p[3]
        xs, ys = [], []
        for g in games:
            if g["date"] < mid:
                continue
            for key, opp in (("pa", g["home"]), ("ph", g["away"])):
                for p in g.get(key) or []:
                    ps = POS3.get(p[16])
                    o = own.get(str(p[0]))
                    f = factor.get((opp, ps)) if ps else None
                    if not o or o[1] < 400 or p[3] < 15 or f is None:
                        continue
                    exp = o[0] / o[1] * 36
                    if exp < (6 if mk == "pts" else 1.0):
                        continue
                    xs.append(f - 1.0)
                    ys.append(val(p, mk) / p[3] * 36 / exp - 1.0)
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        sxx = sum((x - mx) ** 2 for x in xs)
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
        se = math.sqrt(sum((y - my - b * (x - mx)) ** 2 for x, y in zip(xs, ys)) / (len(xs) - 2) / sxx)
        print("defence v position, %s: n %d, the second half carries %.2f of the defence's first-half lean (t %.1f); the leans' spread sd %.3f" % (mk, len(xs), b, b / se, statistics.pstdev(list(factor.values()))))


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    games = load(argv[1])
    print("%d games" % len(games))
    scatter(games)
    regulars_out(games)
    home_road(games)
    defence_by_position(games)


if __name__ == "__main__":
    main(sys.argv)
