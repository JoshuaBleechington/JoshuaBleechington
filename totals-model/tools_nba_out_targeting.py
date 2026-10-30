#!/usr/bin/env python3
"""Where does the lift from a club's regulars being out actually land? (27 Oct
2026, the user: "for the cards with the red for the regulars out the unders
tend to go over; should the regulars being out be weighted more? Flagg played
40 minutes and got 11 assists against the under 5.5.") His first week of props
said the picks with a big regulars-out lever lost on BOTH sides (118-153 at a
55% say-so), which is not a lift too small or too large but a lift landing on
the wrong men, and a chance too sure of itself on those nights.

Asked of a season's ledger: every player-game after eight prior games this
season, the projection built the slate's way (his per-minute rate to date
times his last five games' minutes), the club's regulars out that night from
the ledger's own rosters (24+ minutes a game, five games, inside each man's
window with the club), and then:

  1. the minutes lift per 30 minutes a game out, pooled, then by his role and
     by his own minutes tier;
  2. the per-36 lift on points, rebounds and assists per 30 mpg out, pooled,
     then by his usage tier, then against WHAT the absent men did (their
     points, rebounds, assists a game): does an absent creator lift his
     teammates' assists where an absent scorer does not?
  3. the projection's miss in sigmas with regulars out against without: is
     the chance too sure of itself on those nights?

    python3 tools_nba_out_targeting.py slate/nba-ledger-202526.json
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


def tstat(xs):
    n = len(xs)
    if n < 3:
        return 0.0
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    return m / (sd / math.sqrt(n)) if sd > 0 else 0.0


def slope(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx if sxx > 0 else 0.0
    res = [y - my - b * (x - mx) for x, y in zip(xs, ys)]
    se = math.sqrt(sum(r * r for r in res) / max(1, n - 2) / sxx) if sxx > 0 else 0.0
    return b, (b / se if se > 0 else 0.0)


def main(argv):
    if not argv:
        print(__doc__); return 2
    led = json.load(open(argv[0]))
    games = sorted(led["games"], key=lambda g: (g["date"], g["id"]))
    regs = slate.nba_club_regulars(games)
    # each regular's stats a game to date, for "what the absent men did"
    per = defaultdict(lambda: {"g": 0, "min": 0.0, "pts": 0, "reb": 0, "ast": 0, "name": ""})
    hist = defaultdict(list)   # pid -> [(team, min, pts, reb, ast, fga, fta, tov, st)]
    rows = []
    for g in games:
        for key, ab, okey in (("pa", g["away"], "oa"), ("ph", g["home"], "oh")):
            club = regs.get((ab, g["id"])) or {}
            out = club.get("out") or []
            # the absent men's lines a game, to date
            out_mpg = sum(m for _n, m in out)
            out_pts = out_reb = out_ast = 0.0
            for name, _m in out:
                for pid, s in per.items():
                    if s["name"] == name and s["g"] >= 5:
                        out_pts += s["pts"] / s["g"]; out_reb += s["reb"] / s["g"]; out_ast += s["ast"] / s["g"]
                        break
            tline = g["sa"] if key == "pa" else g["sh"]
            for p in g.get(key) or []:
                if len(p) < 17:
                    continue
                pid, mins = str(p[0]), float(p[3] or 0)
                prior = [x for x in hist[pid] if x[0] == ab]
                if mins > 0 and len(prior) >= MIN_PRIOR:
                    pm = sum(x[1] for x in prior)
                    last5 = prior[-5:]
                    mins_proj = sum(x[1] for x in last5) / 5.0
                    usage = 100.0 * sum(x[5] + 0.44 * x[6] + x[7] for x in prior) / max(1.0, sum(x[8] for x in prior))
                    starter = prior[-1][9]
                    r = {"mins": mins, "mins_proj": mins_proj, "mins_season": pm / len(prior), "starter": starter, "usage": usage, "out_mpg": out_mpg, "out_pts": out_pts, "out_reb": out_reb, "out_ast": out_ast, "n_out": len(out)}
                    for mk, idx in (("pts", 4), ("reb", 6), ("ast", 7)):
                        rate = sum(x[{"pts": 2, "reb": 3, "ast": 4}[mk]] for x in prior) / pm
                        r[mk + "_rate36"] = rate * 36.0
                        r[mk + "_act36"] = p[idx] / mins * 36.0
                        proj = rate * mins_proj
                        r[mk + "_proj"] = proj
                        r[mk + "_act"] = p[idx]
                        r[mk + "_sd"] = slate.PROPS_SD_K[mk] * math.sqrt(max(proj, 1.0))
                    rows.append(r)
                tpos = (tline.get("fga") or 0) + 0.44 * (tline.get("fta") or 0) + (tline.get("tov") or 0)
                tm = float(tline.get("min") or 240.0)
                hist[pid].append((ab, mins, p[4], p[6], p[7], p[9], p[10], p[11], tpos * mins / (tm / 5.0) if mins > 0 else 0.0, int(p[2] or 0)))
                s = per[pid]; s["name"] = p[1]
                if mins > 0:
                    s["g"] += 1; s["min"] += mins; s["pts"] += p[4]; s["reb"] += p[6]; s["ast"] += p[7]
    print("%d player-games after %d prior games; %d of them with a regular out (%.0f%%)" % (len(rows), MIN_PRIOR, sum(1 for r in rows if r["out_mpg"] > 0), 100.0 * sum(1 for r in rows if r["out_mpg"] > 0) / len(rows)))

    # 1. the minutes lift
    print("\n== the minutes lift: his minutes less his last five, per 30 minutes a game of regulars out ==")
    def mlift(rs, label):
        xs = [r["out_mpg"] / 30.0 for r in rs]; ys = [r["mins"] - r["mins_proj"] for r in rs]
        b, t = slope(xs, ys)
        print("  %-36s n %6d  %+.2f min per 30 mpg out (t %+.1f)" % (label, len(rs), b, t))
    mlift(rows, "everyone")
    mlift([r for r in rows if r["starter"]], "starters (started his last game)")
    mlift([r for r in rows if not r["starter"]], "bench")
    for lo, hi, lab in ((0, 20, "his minutes under 20"), (20, 28, "20 to 28"), (28, 99, "28 and up")):
        mlift([r for r in rows if lo <= r["mins_season"] < hi], lab)
    for lo, hi, lab in ((0.0001, 30, "one man out, under 30 mpg"), (30, 48, "30 to 48 mpg out"), (48, 999, "48 mpg and up out (two or more)")):
        rs = [r for r in rows if lo <= r["out_mpg"] < hi]
        print("  %-36s n %6d  minutes less his last five: mean %+.2f (t %+.1f)" % (lab, len(rs), sum(r["mins"] - r["mins_proj"] for r in rs) / len(rs), tstat([r["mins"] - r["mins_proj"] for r in rs])))

    # 2. the per-36 lift by market, pooled, by usage, and against what the absent men did
    print("\n== the per-36 lift per 30 mpg out, and against what the absent men did a game ==")
    for mk, lab in (("pts", "points"), ("reb", "rebounds"), ("ast", "assists")):
        rs = [r for r in rows if r[mk + "_rate36"] > 0]
        xs = [r["out_mpg"] / 30.0 for r in rs]; ys = [r[mk + "_act36"] - r[mk + "_rate36"] for r in rs]
        b, t = slope(xs, ys)
        print("  %-9s pooled: %+.2f per 36 per 30 mpg out (t %+.1f, n %d)" % (lab, b, t, len(rs)))
        for lo, hi, ulab in ((0, 18, "usage under 18%"), (18, 24, "18 to 24%"), (24, 99, "24% and up")):
            rs2 = [r for r in rs if lo <= r["usage"] < hi]
            b2, t2 = slope([r["out_mpg"] / 30.0 for r in rs2], [r[mk + "_act36"] - r[mk + "_rate36"] for r in rs2])
            print("      %-18s %+.2f per 36 per 30 mpg out (t %+.1f, n %d)" % (ulab, b2, t2, len(rs2)))
        for st, slab in ((1, "starters"), (0, "bench")):
            rs2 = [r for r in rs if r["starter"] == st]
            b2, t2 = slope([r["out_mpg"] / 30.0 for r in rs2], [r[mk + "_act36"] - r[mk + "_rate36"] for r in rs2])
            print("      %-18s %+.2f per 36 per 30 mpg out (t %+.1f, n %d)" % (slab, b2, t2, len(rs2)))
        # against the absent men's own stat a game (only games with someone out)
        rs3 = [r for r in rs if r["out_mpg"] > 0]
        key = {"pts": "out_pts", "reb": "out_reb", "ast": "out_ast"}[mk]
        b3, t3 = slope([r[key] for r in rs3], [r[mk + "_act36"] - r[mk + "_rate36"] for r in rs3])
        b4, t4 = slope([r["out_mpg"] / 30.0 for r in rs3], [r[mk + "_act36"] - r[mk + "_rate36"] for r in rs3])
        print("      with someone out (n %d): %+.3f per 36 for each %s a game the absent men had (t %+.1f); per 30 mpg out in the same games %+.2f (t %+.1f)" % (len(rs3), b3, lab[:-1] if lab != "assists" else "assist", t3, b4, t4))
        # the absent men's stat a game, in tiers
        for lo, hi, tl in ((0.0001, 5, "absent men had under 5 a game"), (5, 12, "5 to 12"), (12, 99, "12 and up")):
            rs4 = [r for r in rs3 if lo <= r[key] < hi]
            if len(rs4) >= 50:
                ys4 = [r[mk + "_act36"] - r[mk + "_rate36"] for r in rs4]
                print("        %-30s n %5d  lift %+.2f per 36 (t %+.1f)" % (tl, len(rs4), sum(ys4) / len(ys4), tstat(ys4)))

    # 3. the projection's miss in sigmas, with the pooled rule applied, by how much is out
    print("\n== the projection's miss in sigmas (the pooled rule applied) by how much is out: is the chance too sure of itself on those nights? ==")
    for mk, lab in (("pts", "points"), ("reb", "rebounds"), ("ast", "assists")):
        for lo, hi, tl in ((0, 0.0001, "nobody out"), (0.0001, 30, "under 30 mpg out"), (30, 48, "30 to 48"), (48, 999, "48 and up")):
            rs = [r for r in rows if lo <= r["out_mpg"] < hi and r[mk + "_proj"] >= 3]
            if not rs:
                continue
            zs = []
            for r in rs:
                mins = r["mins_proj"] + slate.PROPS_OUT_MIN_PER30 * r["out_mpg"] / 30.0
                rate = r[mk + "_rate36"] / 36.0 + slate.PROPS_OUT_RATE_PER30.get(mk, 0.0) / 36.0 * r["out_mpg"] / 30.0
                proj = rate * mins
                sd = slate.PROPS_SD_K[mk] * math.sqrt(max(proj, 1.0))
                zs.append((r[mk + "_act"] - proj) / sd)
            m = sum(zs) / len(zs); sdz = math.sqrt(sum((z - m) ** 2 for z in zs) / len(zs))
            print("  %-9s %-20s n %6d  bias %+.3f sigmas (t %+.1f)  spread %.2f sigmas  over the mean %.1f%%" % (lab, tl, len(rs), m, tstat(zs), sdz, 100.0 * sum(1 for z in zs if z > 0) / len(zs)))
    return 0


if __name__ == "__main__" and not (len(sys.argv) > 2 and sys.argv[2] == "more"):
    sys.exit(main(sys.argv[1:]))


# ---- 4. out of sample: the rule by role, fitted on the first half of the season, against the pooled rule on the second (27 Oct 2026) ----
#      5. thin histories: the miss in sigmas by how many games the rate rests on, and the sampling term that would square it
#      6. the minutes to project: the mean of his last five against their median and a trimmed mean
def more(argv):
    led = json.load(open(argv[0]))
    games = sorted(led["games"], key=lambda g: (g["date"], g["id"]))
    regs = slate.nba_club_regulars(games)
    per = defaultdict(lambda: {"g": 0, "ast": 0, "name": ""})
    hist = defaultdict(list)
    rows = []
    MID = "2026-01-14"
    for g in games:
        for key, ab in (("pa", g["away"]), ("ph", g["home"])):
            club = regs.get((ab, g["id"])) or {}
            out = club.get("out") or []
            out_mpg = sum(m for _n, m in out)
            out_ast = 0.0
            for name, _m in out:
                for pid, s in per.items():
                    if s["name"] == name and s["g"] >= 5:
                        out_ast += s["ast"] / s["g"]; break
            for p in g.get(key) or []:
                if len(p) < 17:
                    continue
                pid, mins = str(p[0]), float(p[3] or 0)
                prior = [x for x in hist[pid] if x[0] == ab]
                if mins > 0 and len(prior) >= 3:
                    pm = sum(x[1] for x in prior); last5 = prior[-5:]
                    r = {"date": g["date"], "mins": mins, "n_prior": len(prior), "starter": prior[-1][5], "out_mpg": out_mpg, "out_ast": out_ast,
                         "m_mean5": sum(x[1] for x in last5) / len(last5), "m_med5": sorted(x[1] for x in last5)[len(last5) // 2], "m_season": pm / len(prior),
                         "m_trim": (sum(sorted(x[1] for x in last5)[1:-1]) / 3.0) if len(last5) == 5 else sum(x[1] for x in last5) / len(last5)}
                    for mk, idx, hidx in (("pts", 4, 2), ("reb", 6, 3), ("ast", 7, 4)):
                        r[mk + "_rate"] = sum(x[hidx] for x in prior) / pm; r[mk + "_act"] = p[idx]
                    rows.append(r)
                hist[pid].append((ab, mins, p[4], p[6], p[7], int(p[2] or 0)))
                s = per[pid]; s["name"] = p[1]
                if mins > 0:
                    s["g"] += 1; s["ast"] += p[7]
    # 4. the rule by role: fit the minutes and points lifts on the first half, score the second half with each rule
    print("\n== out of sample: the regulars-out rule by role (fitted on the first half of the season) against the pooled rule, on the second half ==")
    fit = [r for r in rows if r["date"] <= MID and r["n_prior"] >= 8]; test = [r for r in rows if r["date"] > MID and r["n_prior"] >= 8]
    def fit_slope(rs, yf):
        return slope([r["out_mpg"] / 30.0 for r in rs], [yf(r) for r in rs])[0]
    pooled_min = fit_slope(fit, lambda r: r["mins"] - r["m_mean5"])
    role_min = {1: fit_slope([r for r in fit if r["starter"]], lambda r: r["mins"] - r["m_mean5"]), 0: fit_slope([r for r in fit if not r["starter"]], lambda r: r["mins"] - r["m_mean5"])}
    print("  fitted on the first half: minutes lift pooled %+.2f per 30 mpg out; starters %+.2f, bench %+.2f" % (pooled_min, role_min[1], role_min[0]))
    for mk in ("pts", "reb", "ast"):
        pooled_r = fit_slope([r for r in fit if r[mk + "_rate"] > 0], lambda r: (r[mk + "_act"] / r["mins"] - r[mk + "_rate"]) * 36.0)
        role_r = {st: fit_slope([r for r in fit if r["starter"] == st and r[mk + "_rate"] > 0], lambda r: (r[mk + "_act"] / r["mins"] - r[mk + "_rate"]) * 36.0) for st in (1, 0)}
        ast_b = slope([r["out_ast"] for r in fit if r["out_mpg"] > 0 and r[mk + "_rate"] > 0], [(r[mk + "_act"] / r["mins"] - r[mk + "_rate"]) * 36.0 for r in fit if r["out_mpg"] > 0 and r[mk + "_rate"] > 0])[0] if mk == "ast" else 0.0
        def proj(r, rule):
            m = r["m_mean5"] + (pooled_min if rule == "pooled" else role_min[r["starter"]]) * r["out_mpg"] / 30.0
            rate = r[mk + "_rate"] + ((pooled_r if rule == "pooled" else role_r[r["starter"]]) * r["out_mpg"] / 30.0) / 36.0
            if rule == "creator" and mk == "ast":
                rate = r[mk + "_rate"] + (ast_b * r["out_ast"]) / 36.0
            return rate * m
        for rule in ("pooled", "role", "creator") if mk == "ast" else ("pooled", "role"):
            errs = [(r[mk + "_act"] - proj(r, rule)) for r in test if r[mk + "_rate"] > 0 and r["out_mpg"] > 0]
            errs_all = [(r[mk + "_act"] - proj(r, rule)) for r in test if r[mk + "_rate"] > 0]
            rmse = math.sqrt(sum(e * e for e in errs) / len(errs)); rmse_all = math.sqrt(sum(e * e for e in errs_all) / len(errs_all))
            print("  %-9s %-8s second half, games with a regular out (n %d): rmse %.3f, bias %+.3f · every game (n %d): rmse %.3f%s" % (mk, rule, len(errs), rmse, sum(errs) / len(errs), len(errs_all), rmse_all,
                  ("   [role: starters %+.2f, bench %+.2f per 36 per 30 mpg]" % (role_r[1], role_r[0])) if rule == "role" else ("   [%+.3f per 36 per assist a game the absent men had]" % ast_b) if rule == "creator" else ("   [pooled %+.2f per 36 per 30 mpg]" % pooled_r)))
    # 5. thin histories
    print("\n== thin histories: the miss in sigmas by how many games the rate rests on (this season alone, no prior) ==")
    for mk in ("pts", "reb", "ast"):
        for lo, hi, lab in ((3, 5, "3 to 5 games"), (6, 9, "6 to 9"), (10, 19, "10 to 19"), (20, 99, "20 and up")):
            rs = [r for r in rows if lo <= r["n_prior"] < hi + 1 and r[mk + "_rate"] * r["m_mean5"] >= 3]
            zs = []
            for r in rs:
                pj = r[mk + "_rate"] * r["m_mean5"]; sd = slate.PROPS_SD_K[mk] * math.sqrt(max(pj, 1.0))
                zs.append((r[mk + "_act"] - pj) / sd)
            m = sum(zs) / len(zs); sdz = math.sqrt(sum((z - m) ** 2 for z in zs) / len(zs))
            # the sampling term: the rate's own error from n games, k sqrt(mu) / sqrt(n) per 36, scaled to his minutes
            ext = [math.sqrt(1.0 + (slate.PROPS_SD_K[mk] ** 2) / max(1, r["n_prior"]) ) for r in rs]
            print("  %-9s %-14s n %6d  spread %.3f sigmas (bias %+.3f) · with the rate's sampling error added, the sigma would widen x%.2f on average" % (mk, lab, len(rs), sdz, m, sum(ext) / len(ext)))
    # 6. the minutes to project
    print("\n== the minutes to project: the mean of his last five against their median, a trimmed mean and the season mean (rmse of his actual minutes, 8+ prior games) ==")
    rs = [r for r in rows if r["n_prior"] >= 8]
    for key, lab in (("m_mean5", "mean of the last five"), ("m_med5", "median of the last five"), ("m_trim", "trimmed mean (drop the high and the low)"), ("m_season", "season mean")):
        errs = [r["mins"] - r[key] for r in rs]
        print("  %-44s rmse %.3f  bias %+.3f" % (lab, math.sqrt(sum(e * e for e in errs) / len(errs)), sum(errs) / len(errs)))
    rs3 = [r for r in rows if 3 <= r["n_prior"] <= 5]
    for key, lab in (("m_mean5", "mean of the last five"), ("m_med5", "median of the last five"), ("m_trim", "trimmed mean"), ("m_season", "season mean")):
        errs = [r["mins"] - r[key] for r in rs3]
        print("  early (3 to 5 prior games) %-25s rmse %.3f  bias %+.3f" % (lab, math.sqrt(sum(e * e for e in errs) / len(errs)), sum(errs) / len(errs)))


if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[2] == "more":
    more(sys.argv[1:])
