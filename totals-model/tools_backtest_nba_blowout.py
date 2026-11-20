"""The blowout test for the player props (22 Oct 2026). On the second night of
props (21 Oct 2026) seven of eleven games were decided by fifteen or more and
the overs went 105-162 in them against 87-65 in the close games: the
projection takes a man's minutes from his last five games and carries no
blowout risk. This asks a season's ledger, joined to the closing moneylines,
whether the market's expected margin predicts the shortfall in a regular's
minutes against his last five, how big it is, whether it carries from one
half of the season to the other, and what shading the projected minutes by
the expected margin would have done to the projection's bias.

    python3 tools_backtest_nba_blowout.py LEDGER.json ODDS-HISTORY.json [LEDGER2 ODDS2 ...]

The expected margin is read off the de-vigged closing moneyline through the
engine's own normal (12.5 points), since the odds history carries no spread.
A player's team is the favourite when his side's expected margin is positive.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict

MARGIN_SD = 12.5
LAST_N = 5
MIN_PRIOR = 5          # games played this season before a player-game counts
REGULAR = 24.0         # minutes a game, last five: the regulars the props market posts
BENCH = 15.0
KEYS = {"pts": 4, "reb": 6, "ast": 7, "tpm": 8}


def implied(a):
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)


def inv_ncdf(p):
    # Acklam's approximation, good to 1e-9
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def closes(path):
    """{(gdate, away nick, home nick): expected home margin} from the latest snapshot before the start."""
    d = json.load(open(path))
    out = {}
    for g in d["games"].values():
        start = g.get("start") or ""
        snaps = sorted(g["snaps"].items())
        before = [s for s in snaps if s[0] <= start] or snaps[:1]
        if not before:
            continue
        snap = before[-1][1]
        pin = snap.get("pinnacle")
        if pin and pin[3] is not None and pin[4] is not None:
            ih, ia = implied(pin[3]), implied(pin[4])
        else:
            hs = [r[3] for r in snap.values() if r[3] is not None]
            as_ = [r[4] for r in snap.values() if r[4] is not None]
            if not hs or not as_:
                continue
            ih, ia = sum(implied(x) for x in hs) / len(hs), sum(implied(x) for x in as_) / len(as_)
        p_home = ih / (ih + ia)
        out[(g["gdate"], g["away"], g["home"])] = MARGIN_SD * inv_ncdf(min(0.999, max(0.001, p_home)))
    return out


def fit(xs, ys):
    """Slope, intercept and the slope's t on a straight line."""
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    res = [y - (a + b * x) for x, y in zip(xs, ys)]
    s2 = sum(r * r for r in res) / max(1, n - 2)
    t = b / math.sqrt(s2 / sxx) if s2 > 0 else float("inf")
    return b, a, t


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def rows_for(ledger_path, odds_path):
    """One row per player-game with five prior games: (date, role minutes, last-five mean, season rate per minute by market,
    actual minutes and stats, the expected margin from his team's view, the actual margin from his team's view)."""
    led = json.load(open(ledger_path))
    games = sorted(led["games"], key=lambda g: (g["date"], g["id"]))
    cl = closes(odds_path)
    hist = defaultdict(list)      # pid -> [(min, pts, reb, ast, tpm)]
    rows, joined = [], 0
    for g in games:
        key = (g["date"], g.get("an"), g.get("hn"))
        m_home = cl.get(key)
        if m_home is not None:
            joined += 1
        act_margin_home = g["fa"] is not None and g["fh"] is not None and (g["fh"] - g["fa"])
        for side in ("pa", "ph"):
            for p in g.get(side) or []:
                pid, mins = str(p[0]), float(p[3])
                full = len(p) >= 9          # the 17-item box line; a 6-item line (2024-25) carries minutes and points only
                reb, ast, tpm = (p[6], p[7], p[8]) if full else (0, 0, 0)
                h = hist[pid]
                if len(h) >= MIN_PRIOR and m_home is not None and act_margin_home is not False:
                    m_this = sum(x[0] for x in h)
                    rates = {mk: (sum(x[i] for x in h) / m_this if m_this > 0 else 0.0) for mk, i in (("pts", 1), ("reb", 2), ("ast", 3), ("tpm", 4))}
                    pm = mean([x[0] for x in h[-LAST_N:]])
                    sgn = 1.0 if side == "ph" else -1.0
                    rows.append({"date": g["date"], "pm": pm, "rates": rates, "min": mins, "pts": p[4], "reb": reb, "ast": ast, "tpm": tpm, "full": full,
                                 "exp": sgn * m_home, "act": sgn * act_margin_home, "starter": bool(p[2])})
                if mins > 0:
                    h.append((mins, p[4], reb, ast, tpm))
    return rows, len(games), joined


def bucket(x):
    a = abs(x)
    return "0-3" if a < 3 else "3-6" if a < 6 else "6-9" if a < 9 else "9-12" if a < 12 else "12+"


BUCKETS = ["0-3", "3-6", "6-9", "9-12", "12+"]


def report(label, rows):
    print("\n=== %s: %d player-games with five prior games and a close ===" % (label, len(rows)))
    regs = [r for r in rows if r["pm"] >= REGULAR]
    bench = [r for r in rows if r["pm"] < BENCH and r["pm"] >= 5]
    print("regulars (last five %.0f+ minutes): %d; bench (under %.0f): %d" % (REGULAR, len(regs), BENCH, len(bench)))
    print("\n-- how often the expected margin becomes a blowout (the game's actual margin, all player-games' games) --")
    by = defaultdict(list)
    for r in regs:
        by[bucket(r["exp"])].append(abs(r["act"]))
    for b in BUCKETS:
        xs = by[b]
        if xs:
            print("  expected %-5s n %5d  actual margin mean %5.1f  15+ %4.0f%%  20+ %4.0f%%" % (b, len(xs), mean(xs), 100 * mean([x >= 15 for x in xs]), 100 * mean([x >= 20 for x in xs])))
    print("\n-- a regular's minutes against his last five, by the expected margin (his team's view: + favourite, - dog) --")
    for who, sel in (("all regulars", regs), ("favourite's regulars", [r for r in regs if r["exp"] > 0]), ("dog's regulars", [r for r in regs if r["exp"] < 0])):
        by = defaultdict(list)
        for r in sel:
            by[bucket(r["exp"])].append(r["min"] - r["pm"])
        line = "  %-22s" % who
        for b in BUCKETS:
            xs = by[b]
            line += "  %s: %+5.2f (%4d)" % (b, mean(xs), len(xs)) if xs else "  %s:    --      " % b
        f = fit([abs(r["exp"]) for r in sel], [r["min"] - r["pm"] for r in sel])
        print(line + ("   slope %+.3f min/pt, t %+.1f" % (f[0], f[2]) if f else ""))
    print("\n-- the bench's minutes the same way --")
    by = defaultdict(list)
    for r in bench:
        by[bucket(r["exp"])].append(r["min"] - r["pm"])
    line = "  %-22s" % "bench"
    for b in BUCKETS:
        xs = by[b]
        line += "  %s: %+5.2f (%4d)" % (b, mean(xs), len(xs)) if xs else "  %s:    --      " % b
    f = fit([abs(r["exp"]) for r in bench], [r["min"] - r["pm"] for r in bench])
    print(line + ("   slope %+.3f min/pt, t %+.1f" % (f[0], f[2]) if f else ""))
    full = all(r["full"] for r in rows[:50])
    mks = ("pts", "reb", "ast", "pra") if full else ("pts",)

    def bias_table(title, sel, keyf):
        print("\n-- %s --" % title)
        for mk in mks:
            by, over = defaultdict(list), defaultdict(list)
            for r in sel:
                rate = r["rates"]["pts"] + r["rates"]["reb"] + r["rates"]["ast"] if mk == "pra" else r["rates"][mk]
                actual = r["pts"] + r["reb"] + r["ast"] if mk == "pra" else r[mk]
                mu = rate * r["pm"]
                by[keyf(r)].append(actual - mu)
                over[keyf(r)].append(actual > mu)
            line = "  %-4s" % mk
            for b in BUCKETS:
                xs = by[b]
                line += "  %s: %+5.2f over %3.0f%% (%4d)" % (b, mean(xs), 100 * mean(over[b]), len(xs)) if xs else "  %s:    --                " % b
            print(line)

    exp_b = lambda r: bucket(r["exp"])   # noqa: E731
    act_b = lambda r: bucket(r["act"])   # noqa: E731
    bias_table("the stat projection's bias for regulars (actual minus rate x last-five minutes), and the over rate, by the EXPECTED margin", regs, exp_b)
    bias_table("the same for the favourite's regulars", [r for r in regs if r["exp"] > 0], exp_b)
    bias_table("the same for the dog's regulars", [r for r in regs if r["exp"] < 0], exp_b)
    bias_table("the same for the bench", bench, exp_b)
    bias_table("the mechanism: regulars by the ACTUAL margin (what the night of 21 Oct 2026 looked like)", regs, act_b)
    bias_table("the bench by the ACTUAL margin", bench, act_b)
    by = defaultdict(list)
    for r in regs:
        by[bucket(r["act"])].append(r["min"] - r["pm"])
    print("\n-- regulars' minutes against the last five by the ACTUAL margin --\n  " + "  ".join("%s: %+5.2f (%4d)" % (b, mean(by[b]), len(by[b])) for b in BUCKETS if by[b]))
    return regs, bench


def shade(label, regs, bench, slope_regs, slope_bench):
    """What the projection's bias looks like once the minutes are shaded by the expected margin at the fitted slopes."""
    print("\n-- %s: the bias after shading the minutes (regulars %+.3f, bench %+.3f a point of expected margin, from the fitting half) --" % (label, slope_regs, slope_bench))
    full = all(r["full"] for r in (regs + bench)[:50])
    for mk in (("pts", "reb", "ast", "pra") if full else ("pts",)):
        line = "  %-4s" % mk
        for who, sel, sl in (("regulars", regs, slope_regs), ("bench", bench, slope_bench)):
            by, by0 = defaultdict(list), defaultdict(list)
            for r in sel:
                rate = r["rates"]["pts"] + r["rates"]["reb"] + r["rates"]["ast"] if mk == "pra" else r["rates"][mk]
                actual = r["pts"] + r["reb"] + r["ast"] if mk == "pra" else r[mk]
                pm2 = max(0.0, r["pm"] + sl * abs(r["exp"]))
                by[bucket(r["exp"])].append(actual - rate * pm2)
                by0[bucket(r["exp"])].append(actual - rate * r["pm"])
            line += "   %s before/after:" % who
            for b in ("0-3", "6-9", "12+"):
                line += " %s %+.2f/%+.2f" % (b, mean(by0[b]), mean(by[b]))
        print(line)


def main(argv):
    if len(argv) < 2 or len(argv) % 2:
        sys.exit(__doc__)
    all_rows = []
    for i in range(0, len(argv), 2):
        rows, n_games, joined = rows_for(argv[i], argv[i + 1])
        print("%s: %d games, %d joined to a close" % (argv[i], n_games, joined))
        regs, bench = report(argv[i], rows)
        # out of sample: fit the slope on the first half of the season's dates, read the bias on the second
        dates = sorted(set(r["date"] for r in rows))
        mid = dates[len(dates) // 2]
        first = [r for r in regs if r["date"] < mid]
        second = [r for r in regs if r["date"] >= mid]
        fb = [r for r in bench if r["date"] < mid]
        sb = [r for r in bench if r["date"] >= mid]
        f1, f2 = fit([abs(r["exp"]) for r in first], [r["min"] - r["pm"] for r in first]), fit([abs(r["exp"]) for r in second], [r["min"] - r["pm"] for r in second])
        g1, g2 = fit([abs(r["exp"]) for r in fb], [r["min"] - r["pm"] for r in fb]), fit([abs(r["exp"]) for r in sb], [r["min"] - r["pm"] for r in sb])
        print("\n-- does it carry: the slope on the first half of the season against the second (regulars; bench) --")
        print("  regulars: first half %+.3f (t %+.1f, n %d) · second half %+.3f (t %+.1f, n %d)" % (f1[0], f1[2], len(first), f2[0], f2[2], len(second)))
        print("  bench:    first half %+.3f (t %+.1f, n %d) · second half %+.3f (t %+.1f, n %d)" % (g1[0], g1[2], len(fb), g2[0], g2[2], len(sb)))
        shade("second half, slopes from the first", second, sb, f1[0], g1[0])
        all_rows.extend(rows)
    if len(argv) > 2:
        report("ALL SEASONS", all_rows)


if __name__ == "__main__":
    main(sys.argv[1:])
