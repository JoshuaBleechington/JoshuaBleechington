"""The props' centre (22 Oct 2026). The blowout test (tools_backtest_nba_blowout.py)
found the projection's over rate at its own mean sitting at 46-47% in every
bucket of both seasons: a box-score stat is skewed right, so the mean sits
above the median, and a normal centred on the mean says 50% for a number the
player clears 46% of the time. The books post lines at the median. This
measures the over rate at the mean per market, the shift of the centre (in
sigmas) that puts it at 50%, and whether a shift fitted on the first half of
a season holds on the second.

    python3 tools_backtest_nba_props_median.py LEDGER.json [LEDGER2.json ...]

A 6-item ledger line (2024-25) carries minutes and points only; the other
markets need the 17-item box line.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict

LAST_N = 5
MIN_PRIOR = 5
MIN_PM = 15.0            # the players the books post
SD_K = {"pts": 1.85, "reb": 1.2, "ast": 1.15, "tpm": 1.1, "pra": 1.9}   # slate.py PROPS_SD_K


def inv_ncdf(p):
    # Acklam's approximation
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


def rows_for(path):
    led = json.load(open(path))
    games = sorted(led["games"], key=lambda g: (g["date"], g["id"]))
    hist = defaultdict(list)
    rows = []
    for g in games:
        for side in ("pa", "ph"):
            for p in g.get(side) or []:
                pid, mins = str(p[0]), float(p[3])
                full = len(p) >= 9
                reb, ast, tpm = (p[6], p[7], p[8]) if full else (0, 0, 0)
                h = hist[pid]
                if len(h) >= MIN_PRIOR:
                    m_this = sum(x[0] for x in h)
                    pm = sum(x[0] for x in h[-LAST_N:]) / float(len(h[-LAST_N:]))
                    if m_this > 0 and pm >= MIN_PM:
                        rates = {mk: sum(x[i] for x in h) / m_this for mk, i in (("pts", 1), ("reb", 2), ("ast", 3), ("tpm", 4))}
                        rows.append({"date": g["date"], "pm": pm, "rates": rates, "pts": p[4], "reb": reb, "ast": ast, "tpm": tpm, "full": full})
                if mins > 0:
                    h.append((mins, p[4], reb, ast, tpm))
    return rows


def mu_sd(r, mk):
    rate = r["rates"]["pts"] + r["rates"]["reb"] + r["rates"]["ast"] if mk == "pra" else r["rates"][mk]
    mu = rate * r["pm"]
    return mu, SD_K[mk] * math.sqrt(max(mu, 1.0))


def actual(r, mk):
    return r["pts"] + r["reb"] + r["ast"] if mk == "pra" else r[mk]


def over_rate(rows, mk, shift):
    n = w = 0
    for r in rows:
        mu, sd = mu_sd(r, mk)
        if mu < (6 if mk in ("pts", "pra") else 1.0):
            continue
        n += 1
        w += actual(r, mk) > mu - shift * sd
    return (w / float(n) if n else float("nan")), n


def main(argv):
    if not argv:
        sys.exit(__doc__)
    for path in argv:
        rows = rows_for(path)
        full = all(r["full"] for r in rows[:50])
        mks = ("pts", "reb", "ast", "tpm", "pra") if full else ("pts",)
        print("\n=== %s: %d player-games (last five %.0f+ minutes, five prior games) ===" % (path, len(rows), MIN_PM))
        dates = sorted(set(r["date"] for r in rows))
        mid = dates[len(dates) // 2]
        first = [r for r in rows if r["date"] < mid]
        second = [r for r in rows if r["date"] >= mid]
        print("  market   over at the mean (n)      shift to 50%, sigmas    first-half shift    second half at that shift    at the mean   mean bias")
        for mk in mks:
            rate, n = over_rate(rows, mk, 0.0)
            c = -inv_ncdf(rate)
            r1, n1 = over_rate(first, mk, 0.0)
            c1 = -inv_ncdf(r1)
            r2c, n2 = over_rate(second, mk, c1)
            r2, _ = over_rate(second, mk, 0.0)
            bias = [actual(r, mk) - mu_sd(r, mk)[0] for r in rows if mu_sd(r, mk)[0] >= (6 if mk in ("pts", "pra") else 1.0)]
            print("  %-6s   %5.1f%% (%5d)              %+.3f                  %+.3f (n %5d)      %5.1f%% (n %5d)               %5.1f%%        %+.2f" % (
                mk, rate * 100, n, c, c1, n1, r2c * 100, n2, r2 * 100, sum(bias) / len(bias)))
        print("  (a shift of +0.09 sigmas on a 29-point projection with sigma 10 is 0.9 of a point: the centre moves down to the median)")
        # the whole shape: how often the actual lands past the centre by half a sigma, a sigma, two
        print("  the normal's tails at the mean (should read 31/31, 16/16, 2.3/2.3 if the normal were right):")
        for mk in mks:
            tails = []
            for k in (0.5, 1.0, 2.0):
                hi = over_rate(rows, mk, -k)[0]
                lo = 1 - over_rate(rows, mk, k)[0]
                tails.append("%.1f sd: above %4.1f%% / below %4.1f%%" % (k, hi * 100, lo * 100))
            print("    %-4s " % mk + "   ".join(tails))


if __name__ == "__main__":
    main(sys.argv[1:])
