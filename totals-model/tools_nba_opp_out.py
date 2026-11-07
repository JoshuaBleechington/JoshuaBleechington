#!/usr/bin/env python3
"""Does the OPPONENT'S regulars being out lift a man's stat line? (28 Oct 2026,
the user, after a rough night on the props: "when players are out that's going
to help the next man go over, not under, yet it seems to think the same for the
defence even when certain main players are out.") The props carry his own
club's absences (the pooled regulars-out rule) and the simulation's view beside
the card takes two fifths of an absence off the club's DEFENCE, but the scored
matchup lever reads the opponent's full-strength rating: nothing in the
projection says the defence is short-handed tonight.

Asked of a season's ledger: every player-game after eight prior games this
season, the projection built the slate's way, the opponent's regulars out that
night from the ledger's own rosters (24+ minutes a game, five games), and then:

  1. the per-36 lift on points, rebounds, assists and threes per 30 minutes a
     game of OPPONENT regulars out, beside his own club's, in one regression;
  2. the same by WHO is out for them: a centre, a forward, a guard;
  3. by what the absent men did (their points, rebounds, assists a game), and
     by his own position against the absent centre's minutes;
  4. the projection's miss in sigmas (the slate's rules, no opponent lever) by
     how much of the opponent is out: is the model under the mark on those
     nights, as the user saw?
  5. out of sample: the lift fitted on the first half of the season, scored on
     the second, against no lever and against the rule by the absent men's
     position;
  6. what the simulation's defensive share (0.4 of the cost per 100) says the
     lift should be, for comparison.

    python3 tools_nba_opp_out.py slate/nba-ledger-202526.json
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
MID = "2026-01-14"
MARKETS = (("pts", "points"), ("reb", "rebounds"), ("ast", "assists"), ("tpm", "threes"))


def tstat(xs):
    n = len(xs)
    if n < 3:
        return 0.0
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    return m / (sd / math.sqrt(n)) if sd > 0 else 0.0


def ols(rows_x, ys):
    """Least squares with an intercept: [(b, t), ...] for each column of rows_x."""
    n, k = len(rows_x), len(rows_x[0]) + 1
    X = [[1.0] + list(r) for r in rows_x]
    xtx = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    xty = [sum(X[i][a] * ys[i] for i in range(n)) for a in range(k)]
    # invert xtx by Gauss-Jordan
    inv = [[1.0 if a == b else 0.0 for b in range(k)] for a in range(k)]
    m = [row[:] for row in xtx]
    for c in range(k):
        piv = max(range(c, k), key=lambda r: abs(m[r][c]))
        if abs(m[piv][c]) < 1e-12:
            return [(0.0, 0.0)] * (k - 1)
        m[c], m[piv] = m[piv], m[c]; inv[c], inv[piv] = inv[piv], inv[c]
        f = m[c][c]
        m[c] = [v / f for v in m[c]]; inv[c] = [v / f for v in inv[c]]
        for r in range(k):
            if r != c and m[r][c] != 0.0:
                f = m[r][c]
                m[r] = [a - f * b for a, b in zip(m[r], m[c])]; inv[r] = [a - f * b for a, b in zip(inv[r], inv[c])]
    beta = [sum(inv[a][b] * xty[b] for b in range(k)) for a in range(k)]
    res = [ys[i] - sum(X[i][a] * beta[a] for a in range(k)) for i in range(n)]
    s2 = sum(r * r for r in res) / max(1, n - k)
    return [(beta[a], beta[a] / math.sqrt(s2 * inv[a][a]) if inv[a][a] > 0 else 0.0) for a in range(1, k)]


def build(games):
    regs = slate.nba_club_regulars(games)
    per = defaultdict(lambda: {"g": 0, "min": 0.0, "pts": 0, "reb": 0, "ast": 0, "name": "", "pos": ""})
    hist = defaultdict(list)   # pid -> [(team, min, pts, reb, ast, tpm, fga, fta, tov, team poss share, st)]
    name_pid = defaultdict(dict)   # club -> name -> pid
    rows = []
    for g in games:
        for key, ab, opp in (("pa", g["away"], g["home"]), ("ph", g["home"], g["away"])):
            own = (regs.get((ab, g["id"])) or {}).get("out") or []
            theirs = (regs.get((opp, g["id"])) or {}).get("out") or []
            own_mpg = sum(m for _n, m in own)
            opp_mpg = sum(m for _n, m in theirs)
            bypos = {"C": 0.0, "F": 0.0, "G": 0.0}
            opp_pts = opp_reb = opp_ast = 0.0
            for name, m in theirs:
                pid = name_pid[opp].get(name)
                s = per.get(pid) if pid else None
                pos = slate.POS3.get(str((s or {}).get("pos") or "").upper(), "")
                if pos:
                    bypos[pos] += m
                if s and s["g"] >= 5:
                    opp_pts += s["pts"] / s["g"]; opp_reb += s["reb"] / s["g"]; opp_ast += s["ast"] / s["g"]
            tline = g["sa"] if key == "pa" else g["sh"]
            for p in g.get(key) or []:
                d = slate.nba_player_dict(p)
                if not d["full"]:
                    continue
                pid, mins = d["id"], float(d["min"] or 0)
                prior = [x for x in hist[pid] if x[0] == ab]
                if mins > 0 and len(prior) >= MIN_PRIOR:
                    pm = sum(x[1] for x in prior)
                    last5 = prior[-5:]
                    usage = 100.0 * sum(x[6] + 0.44 * x[7] + x[8] for x in prior) / max(1.0, sum(x[9] for x in prior))
                    r = {"date": g["date"], "mins": mins, "mins_proj": sum(x[1] for x in last5) / 5.0, "starter": prior[-1][10], "usage": usage,
                         "pos": slate.POS3.get(str(d.get("pos") or per[pid]["pos"] or "").upper(), ""),
                         "own": own_mpg, "opp": opp_mpg, "oppC": bypos["C"], "oppF": bypos["F"], "oppG": bypos["G"],
                         "opp_pts": opp_pts, "opp_reb": opp_reb, "opp_ast": opp_ast, "n_opp": len(theirs)}
                    for mk, hidx in (("pts", 2), ("reb", 3), ("ast", 4), ("tpm", 5)):
                        rate = sum(x[hidx] for x in prior) / pm
                        r[mk + "_rate36"] = rate * 36.0
                        r[mk + "_act36"] = (d[mk] or 0) / mins * 36.0
                        r[mk + "_act"] = d[mk] or 0
                    rows.append(r)
                tpos = (tline.get("fga") or 0) + 0.44 * (tline.get("fta") or 0) + (tline.get("tov") or 0)
                tm = float(tline.get("min") or 240.0)
                hist[pid].append((ab, mins, d["pts"] or 0, d["reb"] or 0, d["ast"] or 0, d["tpm"] or 0, d["fga"] or 0, d["fta"] or 0, d["tov"] or 0,
                                  tpos * mins / (tm / 5.0) if mins > 0 else 0.0, int(d["st"] or 0)))
                s = per[pid]; s["name"] = d["n"]
                if d.get("pos"):
                    s["pos"] = d["pos"]
                name_pid[ab][d["n"]] = pid
                if mins > 0:
                    s["g"] += 1; s["min"] += mins; s["pts"] += d["pts"] or 0; s["reb"] += d["reb"] or 0; s["ast"] += d["ast"] or 0
    return rows


def lift(rs, mk):
    return [r[mk + "_act36"] - r[mk + "_rate36"] for r in rs]


def main(argv):
    if not argv:
        print(__doc__); return 2
    led = json.load(open(argv[0]))
    games = sorted(led["games"], key=lambda g: (g["date"], g["id"]))
    rows = build(games)
    n_opp = sum(1 for r in rows if r["opp"] > 0)
    print("%d player-games after %d prior games; the opponent had a regular out in %d of them (%.0f%%), his own club in %d (%.0f%%)" % (
        len(rows), MIN_PRIOR, n_opp, 100.0 * n_opp / len(rows), sum(1 for r in rows if r["own"] > 0), 100.0 * sum(1 for r in rows if r["own"] > 0) / len(rows)))

    # 1. pooled, own and opponent side by side
    print("\n== 1. the per-36 lift per 30 minutes a game of regulars out, his own club's and the OPPONENT'S in one regression ==")
    for mk, lab in MARKETS:
        rs = [r for r in rows if r[mk + "_rate36"] > 0]
        (b1, t1), (b2, t2) = ols([(r["own"] / 30.0, r["opp"] / 30.0) for r in rs], lift(rs, mk))
        print("  %-9s n %6d  own club out %+.2f per 36 per 30 mpg (t %+.1f)   OPPONENT out %+.2f per 36 per 30 mpg (t %+.1f)" % (lab, len(rs), b1, t1, b2, t2))
    (b1, t1), (b2, t2) = ols([(r["own"] / 30.0, r["opp"] / 30.0) for r in rows], [r["mins"] - r["mins_proj"] for r in rows])
    print("  %-9s n %6d  own club out %+.2f minutes per 30 mpg (t %+.1f)   OPPONENT out %+.2f minutes per 30 mpg (t %+.1f)" % ("minutes", len(rows), b1, t1, b2, t2))
    for st, slab in ((1, "starters"), (0, "bench")):
        rs = [r for r in rows if r["starter"] == st]
        (b1, t1), (b2, t2) = ols([(r["own"] / 30.0, r["opp"] / 30.0) for r in rs], [r["mins"] - r["mins_proj"] for r in rs])
        print("    minutes, %-8s n %6d  own %+.2f (t %+.1f)   opponent %+.2f (t %+.1f)" % (slab, len(rs), b1, t1, b2, t2))
    print("  in tiers of the opponent's minutes out (the lift as a plain mean):")
    for mk, lab in MARKETS:
        line = []
        for lo, hi, tl in ((0, 0.0001, "nobody"), (0.0001, 30, "under 30"), (30, 48, "30 to 48"), (48, 999, "48 and up")):
            rs = [r for r in rows if lo <= r["opp"] < hi and r[mk + "_rate36"] > 0]
            ys = lift(rs, mk)
            line.append("%s %+.2f (n %d, t %+.1f)" % (tl, sum(ys) / len(ys), len(ys), tstat(ys)))
        print("    %-9s %s" % (lab, " · ".join(line)))

    # 2. by who is out for them
    print("\n== 2. by WHO is out for them: the absent men's minutes a game by position, his own club's out held ==")
    for mk, lab in MARKETS:
        rs = [r for r in rows if r[mk + "_rate36"] > 0]
        res = ols([(r["own"] / 30.0, r["oppC"] / 30.0, r["oppF"] / 30.0, r["oppG"] / 30.0) for r in rs], lift(rs, mk))
        print("  %-9s a centre out %+.2f per 36 per 30 mpg (t %+.1f) · a forward %+.2f (t %+.1f) · a guard %+.2f (t %+.1f)" % (lab, res[1][0], res[1][1], res[2][0], res[2][1], res[3][0], res[3][1]))
    print("  by HIS position against the absent centre's minutes (does the missing big lift the guards' points, the bigs' rebounds?):")
    for mk, lab in MARKETS:
        line = []
        for pos in ("G", "F", "C"):
            rs = [r for r in rows if r[mk + "_rate36"] > 0 and r["pos"] == pos]
            res = ols([(r["own"] / 30.0, r["oppC"] / 30.0, (r["oppF"] + r["oppG"]) / 30.0) for r in rs], lift(rs, mk))
            line.append("%s: centre out %+.2f (t %+.1f), others %+.2f (t %+.1f), n %d" % (slate.POS_WORD[pos], res[1][0], res[1][1], res[2][0], res[2][1], len(rs)))
        print("    %-9s %s" % (lab, " · ".join(line)))

    # 3. by what the absent men did
    print("\n== 3. by what the absent men did a game (games with an opponent regular out) ==")
    for mk, lab in MARKETS:
        rs = [r for r in rows if r[mk + "_rate36"] > 0 and r["opp"] > 0]
        res = ols([(r["own"] / 30.0, r["opp_pts"], r["opp_reb"], r["opp_ast"]) for r in rs], lift(rs, mk))
        print("  %-9s n %5d  per point a game the absent men had %+.3f (t %+.1f) · per rebound %+.3f (t %+.1f) · per assist %+.3f (t %+.1f)" % (
            lab, len(rs), res[1][0], res[1][1], res[2][0], res[2][1], res[3][0], res[3][1]))

    # 4. the miss in sigmas with the slate's rules (own-club lever, no opponent lever)
    print("\n== 4. the projection's miss in sigmas (the slate's own-club rule applied, nothing for the opponent's absences) by how much of the opponent is out ==")
    for mk, lab in MARKETS:
        for lo, hi, tl in ((0, 0.0001, "nobody out"), (0.0001, 30, "under 30 mpg out"), (30, 48, "30 to 48"), (48, 999, "48 and up")):
            rs = [r for r in rows if lo <= r["opp"] < hi]
            zs = []
            for r in rs:
                mins = r["mins_proj"] + slate.PROPS_OUT_MIN_PER30 * r["own"] / 30.0
                rate = r[mk + "_rate36"] / 36.0 + slate.PROPS_OUT_RATE_PER30.get(mk, 0.0) / 36.0 * r["own"] / 30.0
                proj = rate * mins
                if proj < 3 and mk != "tpm" or (mk == "tpm" and proj < 1):
                    continue
                sd = slate.PROPS_SD_K[mk] * math.sqrt(max(proj, 1.0))
                zs.append((r[mk + "_act"] - proj) / sd)
            if len(zs) < 30:
                continue
            m = sum(zs) / len(zs); sdz = math.sqrt(sum((z - m) ** 2 for z in zs) / len(zs))
            print("  %-9s %-18s n %6d  bias %+.3f sigmas (t %+.1f)  spread %.2f  over the mean %.1f%%" % (lab, tl, len(zs), m, tstat(zs), sdz, 100.0 * sum(1 for z in zs if z > 0) / len(zs)))

    # 5. out of sample
    print("\n== 5. out of sample: the opponent lever fitted on the first half (to %s), scored on the second half's games with an opponent regular out ==" % MID)
    fit = [r for r in rows if r["date"] <= MID]; test = [r for r in rows if r["date"] > MID]
    print("  fit %d player-games, test %d (%d with an opponent regular out)" % (len(fit), len(test), sum(1 for r in test if r["opp"] > 0)))
    for mk, lab in MARKETS:
        f = [r for r in fit if r[mk + "_rate36"] > 0]
        pooled = ols([(r["own"] / 30.0, r["opp"] / 30.0) for r in f], lift(f, mk))[1][0]
        bp = ols([(r["own"] / 30.0, r["oppC"] / 30.0, r["oppF"] / 30.0, r["oppG"] / 30.0) for r in f], lift(f, mk))
        bypos = {"C": bp[1][0], "F": bp[2][0], "G": bp[3][0]}

        def proj(r, rule):
            mins = r["mins_proj"] + slate.PROPS_OUT_MIN_PER30 * r["own"] / 30.0
            rate36 = r[mk + "_rate36"] + slate.PROPS_OUT_RATE_PER30.get(mk, 0.0) * r["own"] / 30.0
            if rule == "pooled":
                rate36 += pooled * r["opp"] / 30.0
            elif rule == "bypos":
                rate36 += sum(bypos[p] * r["opp" + p] / 30.0 for p in ("C", "F", "G"))
            elif rule == "half":
                rate36 += 0.5 * pooled * r["opp"] / 30.0
            return rate36 / 36.0 * mins
        out = []
        for rule in ("none", "pooled", "half", "bypos"):
            t_ = [r for r in test if r[mk + "_rate36"] > 0 and r["opp"] > 0]
            errs = [r[mk + "_act"] - proj(r, rule) for r in t_]
            t_all = [r for r in test if r[mk + "_rate36"] > 0]
            errs_all = [r[mk + "_act"] - proj(r, rule) for r in t_all]
            out.append("%s: rmse %.4f bias %+.3f (all games rmse %.4f)" % (rule, math.sqrt(sum(e * e for e in errs) / len(errs)), sum(errs) / len(errs), math.sqrt(sum(e * e for e in errs_all) / len(errs_all))))
        print("  %-9s fitted pooled %+.2f per 36 per 30 mpg; by position C %+.2f F %+.2f G %+.2f" % (lab, pooled, bypos["C"], bypos["F"], bypos["G"]))
        for o in out:
            print("      %s" % o)
        # the second half's own slope, for the drift
        t2 = [r for r in test if r[mk + "_rate36"] > 0]
        b2, tt2 = ols([(r["own"] / 30.0, r["opp"] / 30.0) for r in t2], lift(t2, mk))[1]
        print("      the second half's own slope %+.2f (t %+.1f)" % (b2, tt2))

    # 6. the simulation's view
    print("\n== 6. what the simulation's defensive share says: 0.4 of (0.15 x his points + 0.03 x his minutes) per 100 possessions off the club's defence ==")
    rs = [r for r in rows if r["opp"] > 0]
    cost = [0.4 * (slate.NBA_SIM_OUT_PPG * r["opp_pts"] + slate.NBA_SIM_OUT_MPG * r["opp"]) for r in rs]
    ppp = 114.0
    print("  across the games with an opponent regular out: mean %.2f per 100 off the defence, %.1f%% of a %.0f rating" % (sum(cost) / len(cost), 100.0 * sum(cost) / len(cost) / ppp, ppp))
    print("  on a man scoring 20 per 36 that is %+.2f points per 36 a game the opponent is short a regular; measured above, pooled: see section 1" % (20.0 * (sum(cost) / len(cost)) / ppp))
    mean_opp = sum(r["opp"] for r in rs) / len(rs)
    print("  (the mean opponent absence in those games is %.0f mpg; the simulation's lift per 30 mpg at that rate is about %+.2f per 36 on a 20-per-36 scorer)" % (mean_opp, 20.0 * (sum(cost) / len(cost)) / ppp / (mean_opp / 30.0)))

    # 7. the one piece that is both sizeable and sensible: the missing big man. Each candidate rule by half, then out of sample
    print("\n== 7. the missing big man, by half and out of sample: does it persist? ==")
    cands = (
        ("rebounds, forwards and centres, per 30 mpg of an opposing CENTRE out", "reb", lambda r: r["pos"] in ("F", "C"), lambda r: r["oppC"] / 30.0),
        ("rebounds, everyone, per 30 mpg of an opposing centre out", "reb", lambda r: True, lambda r: r["oppC"] / 30.0),
        ("rebounds, everyone, per rebound a game the absent men had", "reb", lambda r: True, lambda r: r["opp_reb"]),
        ("rebounds, forwards and centres, per rebound a game the absent men had", "reb", lambda r: r["pos"] in ("F", "C"), lambda r: r["opp_reb"]),
        ("points, everyone, per 30 mpg of an opposing centre out", "pts", lambda r: True, lambda r: r["oppC"] / 30.0),
        ("points, everyone, per rebound a game the absent men had", "pts", lambda r: True, lambda r: r["opp_reb"]),
        ("points, guards and forwards, per 30 mpg of an opposing centre out", "pts", lambda r: r["pos"] in ("G", "F"), lambda r: r["oppC"] / 30.0),
        ("assists, everyone, per 30 mpg of an opposing forward out", "ast", lambda r: True, lambda r: r["oppF"] / 30.0),
    )
    for label, mk, keep, xf in cands:
        f = [r for r in fit if keep(r) and r[mk + "_rate36"] > 0]; t_ = [r for r in test if keep(r) and r[mk + "_rate36"] > 0]
        b1, t1 = ols([(r["own"] / 30.0, xf(r)) for r in f], lift(f, mk))[1]
        b2, t2 = ols([(r["own"] / 30.0, xf(r)) for r in t_], lift(t_, mk))[1]
        ball, tall = ols([(r["own"] / 30.0, xf(r)) for r in f + t_], lift(f + t_, mk))[1]

        def proj(r, b):
            mins = r["mins_proj"] + slate.PROPS_OUT_MIN_PER30 * r["own"] / 30.0
            rate36 = r[mk + "_rate36"] + slate.PROPS_OUT_RATE_PER30.get(mk, 0.0) * r["own"] / 30.0 + b * xf(r)
            return rate36 / 36.0 * mins
        hit = [r for r in t_ if xf(r) > 0]
        e0 = [r[mk + "_act"] - proj(r, 0.0) for r in hit]; e1 = [r[mk + "_act"] - proj(r, b1) for r in hit]; eh = [r[mk + "_act"] - proj(r, 0.5 * b1) for r in hit]
        rm = lambda es: math.sqrt(sum(e * e for e in es) / len(es))  # noqa: E731
        print("  %s:\n      first half %+.3f (t %+.1f, n %d) · second half %+.3f (t %+.1f, n %d) · whole season %+.3f (t %+.1f)\n      second half, the games it applies to (n %d): rmse none %.4f, the first half's rule %.4f, half of it %.4f; bias none %+.3f, rule %+.3f" % (
            label, b1, t1, len(f), b2, t2, len(t_), ball, tall, len(hit), rm(e0), rm(e1), rm(eh), sum(e0) / len(e0), sum(e1) / len(e1)))
    # the tiers of an opposing centre out, forwards and centres, rebounds: the lift as a plain mean, by half
    print("  rebounds for forwards and centres by the opposing centre's minutes out, as plain means:")
    for lo, hi, tl in ((0, 0.0001, "no centre out"), (0.0001, 25, "under 25 mpg"), (25, 35, "25 to 35"), (35, 99, "35 and up")):
        parts = []
        for half, rs_ in (("first", fit), ("second", test)):
            rs = [r for r in rs_ if r["pos"] in ("F", "C") and lo <= r["oppC"] < hi and r["reb_rate36"] > 0]
            ys = lift(rs, "reb")
            parts.append("%s half %+.2f (n %d, t %+.1f)" % (half, sum(ys) / len(ys) if ys else 0.0, len(ys), tstat(ys)))
        print("    %-14s %s" % (tl, " · ".join(parts)))

    # 8. which carries it, the centre's minutes or the absent men's rebounds a game; and the chance in sigmas, the median shift in, with and without the rule
    print("\n== 8. the centre's minutes against the absent men's rebounds a game, in one regression (forwards and centres, rebounds) ==")
    for half, rs_ in (("first half", fit), ("second half", test), ("whole season", rows)):
        rs = [r for r in rs_ if r["pos"] in ("F", "C") and r["reb_rate36"] > 0]
        res = ols([(r["own"] / 30.0, r["oppC"] / 30.0, r["opp_reb"]) for r in rs], lift(rs, "reb"))
        print("  %-13s per 30 mpg of an opposing centre out %+.3f (t %+.1f) · per rebound a game the absent men had %+.3f (t %+.1f)" % (half, res[1][0], res[1][1], res[2][0], res[2][1]))
    print("\n== the chance, the median shift in: forwards' and centres' rebounds against the slate's centre, with an opposing centre out and without, by half ==")
    for b, blab in ((0.0, "no rule"), (0.69, "the rule at 0.69 per 36 per 30 mpg")):
        for half, rs_ in (("first", fit), ("second", test)):
            parts = []
            for lo, hi, tl in ((0, 0.0001, "no centre out"), (0.0001, 99, "a centre out")):
                zs = []
                for r in rs_:
                    if r["pos"] not in ("F", "C") or not (lo <= r["oppC"] < hi):
                        continue
                    mins = r["mins_proj"] + slate.PROPS_OUT_MIN_PER30 * r["own"] / 30.0
                    rate36 = r["reb_rate36"] + b * r["oppC"] / 30.0
                    proj = rate36 / 36.0 * mins
                    if proj < 3:
                        continue
                    sd = slate.PROPS_SD_K["reb"] * math.sqrt(max(proj, 1.0))
                    zs.append((r["reb_act"] - (proj - slate.PROPS_MEDIAN_SHIFT["reb"] * sd)) / sd)
                parts.append("%s: over the centre %.1f%%, bias %+.3f sigmas (n %d, t %+.1f)" % (tl, 100.0 * sum(1 for z in zs if z > 0) / len(zs), sum(zs) / len(zs), len(zs), tstat(zs)))
            print("  %-36s %s half: %s" % (blab, half, " · ".join(parts)))

    # 9. the size that lands: the rule scanned against the projection's miss on those nights (the slate's way, the median shift in), whole season
    print("\n== 9. the rule's size against the miss on those nights (forwards and centres, rebounds, an opposing centre out, the median shift in), whole season ==")
    hit = [r for r in rows if r["pos"] in ("F", "C") and r["oppC"] > 0]
    dm = [r["mins"] - r["mins_proj"] for r in hit]
    print("  his minutes on those nights against his last five: %+.2f (n %d, t %+.1f); the per-36 lift as a plain mean %+.2f (t %+.1f)" % (sum(dm) / len(dm), len(dm), tstat(dm), sum(lift(hit, "reb")) / len(hit), tstat(lift(hit, "reb"))))
    for b in (0.0, 0.2, 0.3, 0.35, 0.4, 0.5, 0.6, 0.69):
        zs, raw = [], []
        for r in hit:
            mins = r["mins_proj"] + slate.PROPS_OUT_MIN_PER30 * r["own"] / 30.0
            rate36 = r["reb_rate36"] + b * r["oppC"] / 30.0
            proj = rate36 / 36.0 * mins
            if proj < 3:
                continue
            sd = slate.PROPS_SD_K["reb"] * math.sqrt(max(proj, 1.0))
            zs.append((r["reb_act"] - (proj - slate.PROPS_MEDIAN_SHIFT["reb"] * sd)) / sd); raw.append(r["reb_act"] - proj)
        print("  rule %.2f per 36 per 30 mpg: bias %+.3f sigmas (t %+.1f), over the centre %.1f%%, rmse %.4f (n %d)" % (b, sum(zs) / len(zs), tstat(zs), 100.0 * sum(1 for z in zs if z > 0) / len(zs), math.sqrt(sum(e * e for e in raw) / len(raw)), len(zs)))
    rest = []
    for r in rows:
        if r["pos"] not in ("F", "C") or r["oppC"] > 0:
            continue
        mins = r["mins_proj"] + slate.PROPS_OUT_MIN_PER30 * r["own"] / 30.0
        proj = r["reb_rate36"] / 36.0 * mins
        if proj < 3:
            continue
        sd = slate.PROPS_SD_K["reb"] * math.sqrt(max(proj, 1.0))
        rest.append((r["reb_act"] - (proj - slate.PROPS_MEDIAN_SHIFT["reb"] * sd)) / sd)
    print("  the other nights (no opposing centre out): bias %+.3f sigmas, over the centre %.1f%% (n %d)" % (sum(rest) / len(rest), 100.0 * sum(1 for z in rest if z > 0) / len(rest), len(rest)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
