#!/usr/bin/env python3
"""The combination markets (27 Oct 2026, the user: "every prop on the date
doesn't have a points + rebounds market"): points + rebounds, points + assists
and rebounds + assists need what every market has, measured on a season's
ledger the way tools_backtest_nba_props.py measured the first five: the sigma's
k (one sigma = k x sqrt(projection)), the over rate at the projection's mean
and the median shift that centres it, the miss in sigmas by usage and by role
(starter against bench), and the floors cleared. The first five are printed
beside them as the check that the method reproduces the constants shipped.

    python3 tools_nba_combo_markets.py slate/nba-ledger-202526.json
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "slate"))
import slate  # noqa: E402

MIN_PRIOR = 8
MARKETS = ("pts", "reb", "ast", "tpm", "pra", "pr", "pa", "ra")
Z95 = 1.6449


def val(p, mk):
    d = {"pts": p[4], "reb": p[6], "ast": p[7], "tpm": p[8]}
    return {"pra": d["pts"] + d["reb"] + d["ast"], "pr": d["pts"] + d["reb"], "pa": d["pts"] + d["ast"], "ra": d["reb"] + d["ast"]}.get(mk, d.get(mk))


def main(argv):
    if not argv:
        print(__doc__); return 2
    led = json.load(open(argv[0]))
    games = sorted(led["games"], key=lambda g: (g["date"], g["id"]))
    hist = defaultdict(list)
    rows = defaultdict(list)
    for g in games:
        for key, ab, tline in (("pa", g["away"], g["sa"]), ("ph", g["home"], g["sh"])):
            tm = float(tline.get("min") or 240.0)
            tpos = (tline.get("fga") or 0) + 0.44 * (tline.get("fta") or 0) + (tline.get("tov") or 0)
            for p in g.get(key) or []:
                if len(p) < 17:
                    continue
                pid, mins = str(p[0]), float(p[3] or 0)
                prior = [x for x in hist[pid] if x["team"] == ab]
                if mins > 0 and len(prior) >= MIN_PRIOR:
                    pm = sum(x["min"] for x in prior); last5 = prior[-5:]
                    mins_proj = sum(x["min"] for x in last5) / len(last5)
                    tu = sum(x["tu"] for x in prior)
                    usage = 100.0 * sum(x["u"] for x in prior) / tu if tu > 0 else None
                    for mk in MARKETS:
                        proj = sum(x["v"][mk] for x in prior) / pm * mins_proj
                        if proj >= 1.0:
                            rows[mk].append({"proj": proj, "act": val(p, mk), "usage": usage, "st": prior[-1]["st"], "date": g["date"]})
                u = (p[9] + 0.44 * p[10] + p[11]) if mins > 0 else 0.0
                hist[pid].append({"team": ab, "min": mins, "st": int(p[2] or 0), "v": {mk: val(p, mk) for mk in MARKETS}, "u": u, "tu": (tpos * mins / (tm / 5.0)) if (mins > 0 and tm > 0) else 0.0})
    print("the sigma's k, the over rate at the mean, the median shift that centres it, the floors; the first five as shipped beside the method's own")
    shipped_k = dict(slate.PROPS_SD_K); shipped_shift = dict(slate.PROPS_MEDIAN_SHIFT)
    out = {}
    for mk in MARKETS:
        rs = rows[mk]
        k = math.sqrt(sum((r["act"] - r["proj"]) ** 2 / r["proj"] for r in rs) / len(rs))
        over_mean = sum(1 for r in rs if r["act"] > r["proj"]) / len(rs)
        # the shift that centres the over rate at 50%, searched in hundredths of a sigma
        best = None
        for s100 in range(0, 60):
            sh = s100 / 100.0
            rate = sum(1 for r in rs if r["act"] > r["proj"] - sh * k * math.sqrt(r["proj"])) / len(rs)
            if best is None or abs(rate - 0.5) < best[1]:
                best = (sh, abs(rate - 0.5), rate)
        # the floors: the 95% number cleared, posted as a whole number
        f95 = [(math.floor(r["proj"] - best[0] * k * math.sqrt(r["proj"]) - Z95 * k * math.sqrt(r["proj"])), r["act"]) for r in rs]
        f95 = [(f, a) for f, a in f95 if f >= 1]
        cleared = sum(1 for f, a in f95 if a >= f) / max(1, len(f95))
        out[mk] = {"k": k, "shift": best[0], "over_mean": over_mean, "n": len(rs)}
        print("  %-4s n %6d  k %.2f%s  over the mean %.1f%%  median shift %.2f sigmas%s (over rate %.1f%% at it)  95%% floor cleared %.1f%% (n %d)" % (
            mk, len(rs), k, ("  (shipped %.2f)" % shipped_k[mk]) if mk in shipped_k else "", 100 * over_mean, best[0], ("  (shipped %.2f)" % shipped_shift[mk]) if mk in shipped_shift else "", 100 * best[2], 100 * cleared, len(f95)))
    print("\nthe miss in sigmas (k above, the median centre) by usage, then by role at each usage: the factor the sigma carries")
    for mk in MARKETS:
        rs = rows[mk]; k = out[mk]["k"]; sh = out[mk]["shift"]
        line = []
        for lo, hi in ((0, 18), (18, 24), (24, 99)):
            sub = [r for r in rs if r["usage"] is not None and lo <= r["usage"] < hi]
            zs = [(r["act"] - (r["proj"] - sh * k * math.sqrt(r["proj"]))) / (k * math.sqrt(r["proj"])) for r in sub]
            m = sum(zs) / len(zs); sd = math.sqrt(sum((z - m) ** 2 for z in zs) / len(zs))
            parts = []
            for st, lab in ((1, "S"), (0, "B")):
                sub2 = [r for r in sub if r["st"] == st]
                zs2 = [(r["act"] - (r["proj"] - sh * k * math.sqrt(r["proj"]))) / (k * math.sqrt(r["proj"])) for r in sub2]
                m2 = sum(zs2) / len(zs2); sd2 = math.sqrt(sum((z - m2) ** 2 for z in zs2) / len(zs2))
                parts.append("%s %.2f" % (lab, sd2))
            line.append("%s-%s: %.2f (%s)" % (lo, hi if hi < 99 else "up", sd, ", ".join(parts)))
        print("  %-4s %s" % (mk, " · ".join(line)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
