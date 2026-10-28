#!/usr/bin/env python3
"""Middles on NBA totals, measured (28 Oct 2026, the user: "I use four apps,
FanDuel, BetMGM, DraftKings and Fanatics; how could we use the model to
capitalize on middle betting?"). A middle is the over at one number and the
under at a higher one; the final between them wins both legs, outside them
one leg loses and the other wins, so the pair pays when the final lands
between often enough to cover the juice: at -110 on both legs that is 4.8%
of the time, and an NBA final sits within a point of the market's number
about 4.5% of the time, so each point of gap is worth about 2.2%.

Read off the lines history (slate.py odds-history: every book's total at
noon and 6:30 pm Eastern from two days before each game) against the
finals in the ledgers:

  A. the gap between the apps' numbers at the last snapshot before tip, the
     lowest over against the highest under, and what the pair did;
  B. the move: the earliest snapshot against the last, the best app at each
     time, by how far the number moved;
  C. the rule the page uses, the pair taken whenever the sheet's normal says
     it pays (the chance of the final landing between, less the pushes,
     against the two prices), by the size of the gap;
  D. how often a window of each width existed somewhere in the two days;
  E. the normal at 18 points against what landed, for the sizing.

    python3 tools_nba_middles.py odds-history-NBA-2025-26.json nba-ledger-202526.json [more pairs...]
"""
from __future__ import annotations

import collections
import json
import math
import statistics
import sys

APPS = ("fanduel", "betmgm", "draftkings", "fanatics")
SD = 18.0
NICK = {"Seventysixers": "76ers", "Trailblazers": "Trail Blazers"}


def phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def win_amount(price):
    return 100.0 / -price if price < 0 else price / 100.0


def middle_ev(lo, lo_price, hi, hi_price, mu, sd=SD):
    """The pair's expected units per two units staked, from a normal around mu on
    integer totals: both win between the numbers, a push on an integer line."""
    wo, wu = win_amount(lo_price), win_amount(hi_price)
    ev = 0.0; p_both = 0.0
    a, b = int(math.floor(mu - 6 * sd)), int(math.ceil(mu + 6 * sd))
    for t in range(a, b + 1):
        p = phi((t + 0.5 - mu) / sd) - phi((t - 0.5 - mu) / sd)
        o = None if t == lo else t > lo
        u = None if t == hi else t < hi
        units = (0.0 if o is None else (wo if o else -1.0)) + (0.0 if u is None else (wu if u else -1.0))
        ev += p * units
        if o and u:
            p_both += p
    return ev, p_both


def grade(T, lo, hi):
    o = None if T == lo else T > lo
    u = None if T == hi else T < hi
    return o, u


def units(price, win):
    if win is None:
        return 0.0
    return win_amount(price) if win else -1.0


def load(hist_f, led_f):
    H = json.load(open(hist_f))["games"]
    L = json.load(open(led_f))["games"]
    finals = {}
    for g in L:
        if g.get("fa") is None or g.get("fh") is None:
            continue
        finals[(g["date"], NICK.get(g.get("an"), g.get("an")), NICK.get(g.get("hn"), g.get("hn")))] = g["fa"] + g["fh"]
    rows = []
    for g in H.values():
        T = finals.get((g["gdate"], g["away"], g["home"]))
        if T is None:
            continue
        snaps = [(t, s) for t, s in sorted(g["snaps"].items()) if t < g["start"]]
        if snaps:
            rows.append((g, T, snaps))
    return rows


def apps_at(s):
    return [(b, v) for b, v in s.items() if b in APPS and v[0] is not None]


def line(label, f, h, m, u, e=None):
    n = f + h + m
    if not n:
        return "  %-44s nothing" % label
    return "  %-44s n %4d  both win %3d (%.1f%%%s)  one pushes+one wins %3d  one loses %3d  units %+.1f (%+.1f%% of the stake)" % (
        label, n, f, 100.0 * f / n, (", the normal said %.1f%%" % (100.0 * e / n)) if e is not None else "", h, m, u, 100.0 * u / (2 * n))


def run(rows, label):
    print("\n==== %s: %d games with a final and lines ====" % (label, len(rows)))
    # A. the apps' gap at the last snapshot
    widths = collections.Counter(); res = collections.defaultdict(lambda: [0, 0, 0, 0.0, 0.0])
    for g, T, snaps in rows:
        books = apps_at(snaps[-1][1])
        if len(books) < 2:
            continue
        lo_b, lo = min(books, key=lambda x: x[1][0]); hi_b, hi = max(books, key=lambda x: x[1][0])
        w = round(hi[0] - lo[0], 1); widths[w] += 1
        if w <= 0:
            continue
        o, u = grade(T, lo[0], hi[0]); full = o is True and u is True; half = (o is None and u is True) or (u is None and o is True)
        k = "%.1f" % w if w < 3 else "3.0+"
        r = res[k]; r[0] += full; r[1] += half; r[2] += (not full and not half); r[3] += units(lo[1], o) + units(hi[2], u)
        r[4] += middle_ev(lo[0], lo[1], hi[0], hi[2], statistics.median(v[0] for b, v in books))[1]
    print("  A. the apps' numbers at the last snapshot before tip, how far apart:", ", ".join("%s: %d" % (w, n) for w, n in sorted(widths.items())))
    for k in sorted(res):
        f, h, m, u, e = res[k]
        print(line("gap %s" % k, f, h, m, u, e))
    # B. the move, by its size
    mv = collections.defaultdict(lambda: [0, 0, 0, 0.0, 0.0])
    # C. the page's rule: the pair whenever the normal says it pays, at the last snapshot against the first leg at the earliest
    rule = collections.defaultdict(lambda: [0, 0, 0, 0.0, 0.0]); rule_n = 0
    for g, T, snaps in rows:
        if len(snaps) < 2:
            continue
        b0, b1 = apps_at(snaps[0][1]), apps_at(snaps[-1][1])
        if not b0 or not b1:
            continue
        m0 = statistics.median(v[0] for b, v in b0); m1 = statistics.median(v[0] for b, v in b1)
        move = m1 - m0
        if move > 0:
            lo_b, lo = min(b0, key=lambda x: x[1][0]); hi_b, hi = max(b1, key=lambda x: x[1][0])
        else:
            hi_b, hi = max(b0, key=lambda x: x[1][0]); lo_b, lo = min(b1, key=lambda x: x[1][0])
        w = hi[0] - lo[0]
        if w <= 0:
            continue
        o, u = grade(T, lo[0], hi[0]); full = o is True and u is True; half = (o is None and u is True) or (u is None and o is True)
        ev, pb = middle_ev(lo[0], lo[1], hi[0], hi[2], m1)
        if abs(move) >= 1.5:
            k = "1.5-2" if abs(move) < 2.5 else "2.5-3" if abs(move) < 3.5 else "3.5-4.5" if abs(move) < 5 else "5+"
            r = mv[k]; r[0] += full; r[1] += half; r[2] += (not full and not half); r[3] += units(lo[1], o) + units(hi[2], u); r[4] += pb
        if ev > 0:
            k = "gap %s" % ("under 3" if w < 3 else "3-4" if w < 4.5 else "4.5-6" if w < 6.5 else "6.5+")
            r = rule[k]; r[0] += full; r[1] += half; r[2] += (not full and not half); r[3] += units(lo[1], o) + units(hi[2], u); r[4] += pb; rule_n += 1
    print("  B. the move: the earliest snapshot (two days out) against the last before tip, the best app at each time")
    for k in ("1.5-2", "2.5-3", "3.5-4.5", "5+"):
        if k in mv:
            f, h, m, u, e = mv[k]
            print(line("the number moved %s" % k, f, h, m, u, e))
    print("  C. the page's rule: the second leg whenever the normal says the pair pays (%d of %d games)" % (rule_n, len(rows)))
    tf = th = tm = 0; tu = te = 0.0
    for k in ("gap under 3", "gap 3-4", "gap 4.5-6", "gap 6.5+"):
        if k in rule:
            f, h, m, u, e = rule[k]; tf += f; th += h; tm += m; tu += u; te += e
            print(line(k, f, h, m, u, e))
    print(line("all the pairs the rule takes", tf, th, tm, tu, te))
    # D. the widest window the two days offered
    best = collections.Counter()
    for g, T, snaps in rows:
        pts = [v[0] for t, s in snaps for b, v in apps_at(s)]
        if not pts:
            continue
        w = max(pts) - min(pts)
        best["0-1" if w < 1.5 else "1.5-2" if w < 2.5 else "2.5-3" if w < 3.5 else "3.5-4.5" if w < 5 else "5+"] += 1
    print("  D. the widest window the two days offered across the apps (with hindsight):", ", ".join("%s: %d" % (k, best[k]) for k in ("0-1", "1.5-2", "2.5-3", "3.5-4.5", "5+")))
    # E. the normal's sizing against what landed
    close = []
    for g, T, snaps in rows:
        pts = [v[0] for b, v in snaps[-1][1].items() if v[0] is not None]
        if pts:
            close.append((T, statistics.median(pts)))
    for k in (1, 2, 3, 4, 5):
        hit = sum(1 for T, c in close if abs(T - c) <= k / 2.0)
        print("  E. the final within %.1f of the last number: %.1f%% (a %d-integer middle; the normal at %.0f says %.1f%%)" % (k / 2.0, 100.0 * hit / len(close), k, SD, 100.0 * (phi((k / 2.0) / SD) - phi((-k / 2.0) / SD))))


def main(argv):
    if len(argv) < 2 or len(argv) % 2:
        print(__doc__); return 2
    for i in range(0, len(argv), 2):
        rows = load(argv[i], argv[i + 1])
        run(rows, argv[i])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
