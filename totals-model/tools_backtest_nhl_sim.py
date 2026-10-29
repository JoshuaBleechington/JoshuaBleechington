#!/usr/bin/env python3
"""The hockey simulation against a season of closes (29 Oct 2026): what the
sim's own view is worth on the full-game total and the first-period total,
and the shrink each market's raw chance gets before the page shows it.

For every regular-season game of the season, in date order, the club
profiles are built from the games before it (this season's shot tallies and
play-by-play, last season's whole as the prior), the goalies are the ones
who actually started (the first to face a shot), the crew's whistle is the
referees' minors per game to date, and the game is played NHL_SIM_RUNS times
twice: the sim's own view, and anchored to the market's full-game total
(Pinnacle's last number before the puck drop from the odds history, else
the books' median). Then:

  * the full-game total: the own view's P(over the close) against what
    landed, its calibration by bins and the slope of the outcome on it (the
    shrink is one minus the slope); the record of the sim's leans at 55%
    and up; the regression of the landed total on the sim's mean and the
    market's fair total, which says how much weight each deserves;
  * the first period: the sim's P1 mean (own and anchored) against the
    period's goals, beside the naive share of the market's total; the
    calls against DraftKings' first-period line at its price (the user's
    odds-periods pull), the calibration and the record at the sim's
    chance; the log loss against the book's own devigged price.

    python3 tools_backtest_nhl_sim.py --season 2025 --shots shots_2024.csv shots_2025.csv \
        --pbp nhl-pbp-20242025.json nhl-pbp-20252026.json --ledger nhl-ledger-20242025.json nhl-ledger-20252026.json \
        --hist odds-history-NHL-20252026.json [--periods odds-periods-NHL-20252026.json] [--runs 2000] [--cache bt.json] [--score-only]
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "slate"))
import nhlsim  # noqa: E402

NHL_NICK = {"ANA": "Ducks", "BOS": "Bruins", "BUF": "Sabres", "CGY": "Flames", "CAR": "Hurricanes", "CHI": "Blackhawks", "COL": "Avalanche", "CBJ": "Blue Jackets",
            "DAL": "Stars", "DET": "Red Wings", "EDM": "Oilers", "FLA": "Panthers", "LAK": "Kings", "MIN": "Wild", "MTL": "Canadiens", "NSH": "Predators", "NJD": "Devils",
            "NYI": "Islanders", "NYR": "Rangers", "OTT": "Senators", "PHI": "Flyers", "PIT": "Penguins", "SJS": "Sharks", "SEA": "Kraken", "STL": "Blues",
            "TBL": "Lightning", "TOR": "Maple Leafs", "UTA": "Mammoth", "VAN": "Canucks", "VGK": "Golden Knights", "WSH": "Capitals", "WPG": "Jets"}
CREW_K = 25.0   # a referee's minors a game is worth half the league's at this many games


def implied(price):
    p = float(price)
    return 100.0 / (p + 100.0) if p > 0 else -p / (-p + 100.0)


def devig(po, pu):
    a, b = implied(po), implied(pu)
    return a / (a + b)


def logit(p):
    p = min(1 - 1e-6, max(1e-6, p))
    return math.log(p / (1 - p))


def fit_slope(xs, ys):
    """Logistic y ~ a + b x by Newton's method (two parameters); returns (a, b)."""
    a, b = 0.0, 1.0
    for _ in range(25):
        g0 = g1 = h00 = h01 = h11 = 0.0
        for x, y in zip(xs, ys):
            z = a + b * x
            p = 1 / (1 + math.exp(-z)) if z > -30 else 0.0
            w = p * (1 - p)
            g0 += y - p
            g1 += (y - p) * x
            h00 += w
            h01 += w * x
            h11 += w * x * x
        det = h00 * h11 - h01 * h01
        if abs(det) < 1e-12:
            break
        da = (h11 * g0 - h01 * g1) / det
        db = (h00 * g1 - h01 * g0) / det
        a += da
        b += db
        if abs(da) < 1e-8 and abs(db) < 1e-8:
            break
    return a, b


def ols(X, y):
    """Least squares with an intercept: returns the coefficients [b0, b1..]."""
    n, k = len(X), len(X[0])
    A = [[1.0] + list(r) for r in X]
    m = k + 1
    ata = [[sum(A[i][p] * A[i][q] for i in range(n)) for q in range(m)] for p in range(m)]
    aty = [sum(A[i][p] * y[i] for i in range(n)) for p in range(m)]
    # gauss-jordan
    M = [row[:] + [aty[i]] for i, row in enumerate(ata)]
    for c in range(m):
        piv = max(range(c, m), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        if abs(M[c][c]) < 1e-12:
            return None
        f = M[c][c]
        M[c] = [v / f for v in M[c]]
        for r in range(m):
            if r != c and M[r][c]:
                g = M[r][c]
                M[r] = [v - g * w for v, w in zip(M[r], M[c])]
    return [M[i][m] for i in range(m)]


def pct(x):
    return "%.1f%%" % (100 * x)


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", required=True, help="the shot file's season (2025 for 2025-26)")
    ap.add_argument("--shots", nargs="+", required=True)
    ap.add_argument("--pbp", nargs="+", required=True)
    ap.add_argument("--ledger", nargs="+", required=True)
    ap.add_argument("--hist", default=None, help="the season's odds history (the full-game closes); without it the first period alone is scored")
    ap.add_argument("--periods", default=None)
    ap.add_argument("--runs", type=int, default=2000)
    ap.add_argument("--cache", default=None)
    ap.add_argument("--score-only", action="store_true")
    ap.add_argument("--league", default=None, help="nhl-tend.json: its league block replaces nhlsim.LEAGUE")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    season = str(a.season)
    prior_season = str(int(season) - 1)
    rows = []
    if a.cache and os.path.exists(a.cache) and a.score_only:
        rows = load_json(a.cache)["rows"]
    else:
        rows = run(a, season, prior_season)
        if a.cache:
            with open(a.cache, "w", encoding="utf-8") as f:
                json.dump({"season": season, "runs": a.runs, "rows": rows}, f)
    score(rows, season)
    return 0


def run(a, season, prior_season):
    league = dict(nhlsim.LEAGUE)
    if a.league:
        tend = load_json(a.league)
        for k, v in (tend.get("league") or {}).items():
            if k in ("score_rate", "score_q"):
                league[k] = {int(m): x for m, x in v.items()}
            elif k == "pull":
                league[k] = {int(m): x for m, x in v.items()}
            else:
                league[k] = v
        for k, v in (tend.get("K") or {}).items():
            nhlsim.K[k] = v
    tallies = {}
    for p in a.shots:
        t = nhlsim.shots_tallies(p)
        tallies[t["season"]] = t
    this_t, prior_t = tallies.get(season), tallies.get(prior_season)
    if not this_t:
        raise SystemExit("no shot file for season %s" % season)
    led = {}
    for p in a.ledger:
        d = load_json(p)
        for g in d["games"]:
            gid = str(g["id"])
            led[(gid[:4], gid[-5:])] = g
    pbp_by = {}
    for p in a.pbp:
        d = load_json(p)
        for g in d["games"]:
            pbp_by[(g["date"], g["away"], g["home"])] = g
    hist = load_json(a.hist) if a.hist else {"games": {}}
    periods = load_json(a.periods) if a.periods else None
    # dates and the play-by-play per shot-file game id, this season and the prior
    dates, pbp, pbp_prior, dates_prior = {}, {}, {}, {}
    for (yr, gid), g in led.items():
        pb = pbp_by.get((g["date"], g["away"], g["home"]))
        if yr == season:
            dates[gid] = g["date"]
            if pb:
                pbp[gid] = pb["plays"]
        elif yr == prior_season:
            dates_prior[gid] = g["date"]
            if pb:
                pbp_prior[gid] = pb["plays"]
    print("season %s: %d games with shots, %d with play-by-play; prior %s: %d games, %d with play-by-play" % (
        season, len(this_t["games"]), len(pbp), prior_season, len(prior_t["games"]) if prior_t else 0, len(pbp_prior)))
    # the referees' minors per game, accumulated in date order
    ref_games = collections.defaultdict(lambda: [0, 0])
    lg_minors = [0, 0]
    games = sorted(((dates[gid], gid, g) for gid, g in this_t["games"].items() if gid in dates), key=lambda x: (x[0], x[1]))
    if a.limit:
        games = games[:a.limit]
    rows = []
    prof_date, prof = None, None
    done = 0
    for date, gid, g in games:
        lg_ = led[(season, gid)]
        if prof_date != date:
            prof = nhlsim.profiles(this_t, dates, date, pbp=pbp, prior_tallies=prior_t, prior_pbp=pbp_prior, league=league)
            prof_date = date
            # the league's minors to date and the referees' (games before this date only)
        pb = pbp_by.get((date, lg_["away"], lg_["home"]))
        crew = 1.0
        refs = [o[0] for o in (pb.get("off") or []) if isinstance(o, list) and o[1] == "R"] if pb else []
        if refs and lg_minors[0] >= 50:
            lg_rate = lg_minors[1] / float(lg_minors[0])
            fs = []
            for r in refs:
                gms, mins = ref_games[r]
                fs.append(((mins + CREW_K * lg_rate) / (gms + CREW_K)) / lg_rate)
            crew = sum(fs) / len(fs)
        # the starters: the first goalie each side to face a shot
        gk = {}
        for side in ("away", "home"):
            lst = g["goalies"][side]
            gk[side] = lst[0][0] if lst else None
        setup = nhlsim.setup_from_profiles(prof, lg_["away"], lg_["home"], date, goalies=gk, crew=crew)
        if not setup:
            continue
        # the market: the last snapshot before the start, Pinnacle first
        key = "NHL|%s|%s @ %s" % (date, NHL_NICK.get(lg_["away"], lg_["away"]), NHL_NICK.get(lg_["home"], lg_["home"]))
        hg = hist["games"].get(key)
        line = p_over_mkt = None
        if hg:
            snaps = sorted(hg["snaps"].items())
            pre = [s for s in snaps if s[0] <= (hg.get("start") or "9")]
            if pre:
                last = pre[-1][1]
                if last.get("pinnacle"):
                    line, po, pu = last["pinnacle"]
                    p_over_mkt = devig(po, pu)
                else:
                    pts = sorted(v[0] for v in last.values() if v and v[0] is not None)
                    if pts:
                        line = pts[len(pts) // 2]
                        same = [v for v in last.values() if v and v[0] == line]
                        p_over_mkt = sum(devig(v[1], v[2]) for v in same) / len(same)
        p1 = None
        if periods:
            pg = periods["games"].get(key)
            mk = ((pg or {}).get("mk") or {}).get("totals_p1") or {}
            for book in ("draftkings", "fanduel", "espnbet", "betmgm", "fanatics"):
                if mk.get(book):
                    p1 = {"book": book, "line": mk[book][0], "op": mk[book][1], "up": mk[book][2]}
                    break
        seed = int(gid) % 100000
        own = nhlsim.simulate(setup, n=a.runs, seed=seed)
        H = nhlsim.histograms(own)
        sm = nhlsim.summarize(own, {"total": line, "p1": p1["line"] if p1 else None})
        row = {"gid": gid, "date": date, "away": lg_["away"], "home": lg_["home"], "fa": lg_["fa"], "fh": lg_["fh"], "end": lg_["end"],
               "en": (lg_.get("ena") or 0) + (lg_.get("enh") or 0),
               "p1a": g["p1"]["away"][0][2], "p1h": g["p1"]["home"][0][2], "line": line, "p_over_mkt": p_over_mkt,
               "sim_mean": sm["total"]["mean"], "sim_reg": sm["reg"]["mean"], "sim_p1": sm["periods"][0]["mean"], "sim_ot": sm["ot"], "sim_en": sm["en"],
               "sim_p_over": nhlsim.hist_over(H["total"], line)[0] if line is not None else None,
               "sim_p_push": nhlsim.hist_over(H["total"], line)[1] if line is not None else None,
               "sim_p1_over": nhlsim.hist_over(H["p"][0], p1["line"])[0] if p1 else None,
               "sim_p1_push": nhlsim.hist_over(H["p"][0], p1["line"])[1] if p1 else None,
               "p1": p1, "crew": round(crew, 3), "gk": {s: (setup[s].get("gk"), setup[s].get("gk_shots")) for s in ("away", "home")},
               "n_games": (setup["away"].get("n", 0), setup["home"].get("n", 0)), "b2b": (setup["away"].get("b2b"), setup["home"].get("b2b"))}
        # the anchored view, at the close when there is one
        if line is not None:
            fair = line + (p_over_mkt - 0.5) / nhlsim.GOAL_POINTS if p_over_mkt is not None else line   # the density at the line: 0.165 of chance a goal
            setup2 = nhlsim.setup_from_profiles(prof, lg_["away"], lg_["home"], date, goalies=gk, crew=crew)
            if p_over_mkt is not None:
                anc = nhlsim.simulate_anchored(setup2, n=a.runs, seed=seed + 1, line=line, p_over=p_over_mkt, anchor_n=max(300, a.runs // 2))
            else:
                anc = nhlsim.simulate_anchored(setup2, fair, None, n=a.runs, seed=seed + 1, anchor_n=max(300, a.runs // 2))
            HA = nhlsim.histograms(anc)
            row["fair"] = round(fair, 3)
            row["anc_mean"] = round(nhlsim.hist_mean(HA["total"]), 3)
            row["anc_p1"] = round(nhlsim.hist_mean(HA["p"][0]), 3)
            row["anc_p_over"] = nhlsim.hist_over(HA["total"], line)[0]
            row["anc_p_push"] = nhlsim.hist_over(HA["total"], line)[1]
            row["anc_p1_over"] = nhlsim.hist_over(HA["p"][0], p1["line"])[0] if p1 else None
            row["anc_p1_push"] = nhlsim.hist_over(HA["p"][0], p1["line"])[1] if p1 else None
        rows.append(row)
        # the crew tallies, after the game
        if pb:
            mn = nhlsim.minors_taken(pb["plays"])
            tot_m = sum(mn[0]) + sum(mn[1])
            lg_minors[0] += 1
            lg_minors[1] += tot_m
            for r in refs:
                ref_games[r][0] += 1
                ref_games[r][1] += tot_m
        done += 1
        if done % 100 == 0:
            print("  %d games (%s)" % (done, date), flush=True)
    return rows


def score(rows, season):
    rows = [r for r in rows if r.get("line") is not None]
    n = len(rows)
    print("\n== %d games of %s with a close ==" % (n, season))
    tot = [r["fa"] + r["fh"] for r in rows]
    print("  landed %.3f a game (sd %.3f); the sim's own mean %.3f (sd across games %.3f); the market's fair %.3f; overtime landed %s, the sim %s; empty-netters landed %.3f, the sim %.3f" % (
        statistics.mean(tot), statistics.pstdev(tot), statistics.mean(r["sim_mean"] for r in rows), statistics.pstdev([r["sim_mean"] for r in rows]),
        statistics.mean(r["fair"] for r in rows), pct(sum(1 for r in rows if r["end"] != "REG") / n), pct(statistics.mean(r["sim_ot"] for r in rows)),
        statistics.mean(r.get("en") or 0 for r in rows), statistics.mean(r["sim_en"] for r in rows)))
    # the first period landed vs the sim's
    p1 = [r["p1a"] + r["p1h"] for r in rows]
    print("  first period landed %.3f (sd %.3f); the sim's own %.3f, anchored %.3f; the naive share 0.294 x fair %.3f" % (
        statistics.mean(p1), statistics.pstdev(p1), statistics.mean(r["sim_p1"] for r in rows), statistics.mean(r["anc_p1"] for r in rows), 0.294 * statistics.mean(r["fair"] for r in rows)))

    # ---- the full-game total ----
    print("\n== the full-game total: the sim's own view against the close ==")
    live = [r for r in rows if (r["fa"] + r["fh"]) != r["line"]]
    ys = [1 if (r["fa"] + r["fh"]) > r["line"] else 0 for r in live]
    # calibration of the own view's P(over) (pushes set aside: P(over | no push))
    def p_live(r, k):
        push = r.get(k.replace("over", "push")) or 0.0
        return r[k] / max(1e-9, 1 - push)
    xs = [logit(p_live(r, "sim_p_over")) for r in live]
    a_, b_ = fit_slope(xs, ys)
    print("  own view: logistic slope %.2f (intercept %.2f) on %d games: the raw chance is worth %.0f%% of itself -> shrink %.2f" % (b_, a_, len(live), 100 * b_, max(0.0, 1 - b_)))
    xm = [logit(r["p_over_mkt"]) for r in live]
    am, bm = fit_slope(xm, ys)
    print("  the market's own P(over) at its price: slope %.2f (intercept %.2f)" % (bm, am))
    # both together
    both = fit2(xs, xm, ys)
    if both:
        print("  both in one model: the sim's logit %.2f, the market's %.2f (the weight each deserves on the outcome)" % (both[1], both[2]))
    bins = collections.defaultdict(lambda: [0, 0])
    for r, y in zip(live, ys):
        p = p_live(r, "sim_p_over")
        b = min(0.70, max(0.30, math.floor(p * 20) / 20))
        bins[b][0] += 1
        bins[b][1] += y
    print("  calibration (the own view's P(over) bin -> games, the over's share):")
    for b in sorted(bins):
        c = bins[b]
        print("    %.2f-%.2f: %4d games, over %s" % (b, b + 0.05, c[0], pct(c[1] / c[0])))
    for cut in (0.53, 0.55, 0.58, 0.60):
        w = l = 0
        for r, y in zip(live, ys):
            p = p_live(r, "sim_p_over")
            if p >= cut:
                w += y; l += 1 - y
            elif p <= 1 - cut:
                w += 1 - y; l += y
        print("  the sim's leans at %.0f%%+: %d-%d (%s) at -110 that is %+.1f units" % (100 * cut, w, l, pct(w / (w + l)) if w + l else "-", w - l * 1.1))
    # the regression of the landed total on the sim's mean and the market's fair total
    X = [[r["sim_mean"], r["fair"]] for r in rows]
    co = ols(X, tot)
    if co:
        print("  landed total = %.2f + %.3f x sim mean + %.3f x market fair (the weights: sim %.0f%%, market %.0f%%)" % (co[0], co[1], co[2], 100 * co[1] / (co[1] + co[2]) if co[1] + co[2] else 0, 100 * co[2] / (co[1] + co[2]) if co[1] + co[2] else 0))
    co1 = ols([[r["sim_mean"] - r["fair"]] for r in rows], [t - r["fair"] for t, r in zip(tot, rows)])
    print("  landed minus fair = %.3f + %.3f x (sim mean minus fair): the sim's gap carries %.0f%% of itself (t %.1f)" % (co1[0], co1[1], 100 * co1[1], t_of([r["sim_mean"] - r["fair"] for r in rows], [t - r["fair"] for t, r in zip(tot, rows)], co1)))
    # by half of the season
    half = len(rows) // 2
    for lab, part in (("first half", list(zip(live[:len(live) // 2], ys[:len(live) // 2]))), ("second half", list(zip(live[len(live) // 2:], ys[len(live) // 2:])))):
        w = l = 0
        for r, y in part:
            p = p_live(r, "sim_p_over")
            if p >= 0.55:
                w += y; l += 1 - y
            elif p <= 0.45:
                w += 1 - y; l += y
        print("  %s, leans at 55%%+: %d-%d (%s)" % (lab, w, l, pct(w / (w + l)) if w + l else "-"))
    # the anchored view at the close: should sit at the market's chance
    print("  anchored view: mean P(over close | no push) %.3f against the market's %.3f (a check that the anchor holds)" % (
        statistics.mean(p_live(r, "anc_p_over") for r in rows if r.get("anc_p_over") is not None), statistics.mean(r["p_over_mkt"] for r in rows)))

    # ---- the first period ----
    print("\n== the first period ==")
    X = [[r["sim_p1"], r["anc_p1"], 0.294 * r["fair"]] for r in rows]
    co = ols(X, p1)
    if co:
        print("  landed P1 = %.2f + %.3f x own P1 + %.3f x anchored P1 + %.3f x naive share (the weights)" % (co[0], co[1], co[2], co[3]))
    for lab, key in (("own", "sim_p1"), ("anchored", "anc_p1")):
        c = ols([[r[key]] for r in rows], p1)
        print("  landed P1 on the %s P1 alone: slope %.3f (t %.1f); r %.3f" % (lab, c[1], t_of([r[key] for r in rows], p1, c), corr([r[key] for r in rows], p1)))
    c = ols([[0.294 * r["fair"]] for r in rows], p1)
    print("  landed P1 on the naive share alone: slope %.3f (t %.1f); r %.3f" % (c[1], t_of([0.294 * r["fair"] for r in rows], p1, c), corr([0.294 * r["fair"] for r in rows], p1)))
    with_p1 = [r for r in rows if r.get("p1") and r.get("sim_p1_over") is not None]
    if with_p1:
        print("\n== the first-period line (%d games with one, the user's odds-periods pull: %s first) ==" % (len(with_p1), with_p1[0]["p1"]["book"]))
        live1 = [r for r in with_p1 if (r["p1a"] + r["p1h"]) != r["p1"]["line"]]
        y1 = [1 if (r["p1a"] + r["p1h"]) > r["p1"]["line"] else 0 for r in live1]
        lines = collections.Counter(r["p1"]["line"] for r in live1)
        print("  lines: %s" % ", ".join("%g x%d" % (k, v) for k, v in sorted(lines.items())))
        for lab, key in (("own", "sim_p1_over"), ("anchored", "anc_p1_over")):
            x1 = [logit(p_live(r, key)) for r in live1]
            a1, b1 = fit_slope(x1, y1)
            print("  %s view's P(over the line): slope %.2f (intercept %.2f) -> shrink %.2f" % (lab, b1, a1, max(0.0, 1 - b1)))
        xb = [logit(devig(r["p1"]["op"], r["p1"]["up"])) for r in live1]
        ab, bb = fit_slope(xb, y1)
        print("  the book's own devigged P(over): slope %.2f (intercept %.2f)" % (bb, ab))
        both = fit2([logit(p_live(r, "anc_p1_over")) for r in live1], xb, y1)
        if both:
            print("  anchored view and the book together: the sim's logit %.2f, the book's %.2f" % (both[1], both[2]))
        both = fit2([logit(p_live(r, "sim_p1_over")) for r in live1], xb, y1)
        if both:
            print("  own view and the book together: the sim's logit %.2f, the book's %.2f" % (both[1], both[2]))
        # the record at the book's price: bet the sim's side when its chance beats the book's implied by the gap
        for lab, key in (("own", "sim_p1_over"), ("anchored", "anc_p1_over")):
            for gap in (0.03, 0.05, 0.08):
                w = l = 0
                units = 0.0
                for r, y in zip(live1, y1):
                    p = p_live(r, key)
                    po, pu = r["p1"]["op"], r["p1"]["up"]
                    if p - implied(po) >= gap:
                        if y:
                            w += 1; units += 100.0 / -po if po < 0 else po / 100.0
                        else:
                            l += 1; units -= 1
                    elif (1 - p) - implied(pu) >= gap:
                        if not y:
                            w += 1; units += 100.0 / -pu if pu < 0 else pu / 100.0
                        else:
                            l += 1; units -= 1
                print("  %s view, bet when its chance beats the price by %d+ points: %d-%d (%s), %+.1f units" % (lab, round(100 * gap), w, l, pct(w / (w + l)) if w + l else "-", units))
        # calibration of the own view's P1 chance
        bins = collections.defaultdict(lambda: [0, 0])
        for r, y in zip(live1, y1):
            p = p_live(r, "sim_p1_over")
            b = min(0.75, max(0.25, math.floor(p * 20) / 20))
            bins[b][0] += 1
            bins[b][1] += y
        print("  calibration of the own view's P(over the first-period line):")
        for b in sorted(bins):
            c = bins[b]
            print("    %.2f-%.2f: %4d games, over %s" % (b, b + 0.05, c[0], pct(c[1] / c[0])))


def fit2(x1, x2, ys):
    """Logistic y ~ a + b1 x1 + b2 x2, Newton's method."""
    a, b1, b2 = 0.0, 0.5, 0.5
    for _ in range(30):
        g = [0.0, 0.0, 0.0]
        H = [[0.0] * 3 for _ in range(3)]
        for u, v, y in zip(x1, x2, ys):
            z = a + b1 * u + b2 * v
            p = 1 / (1 + math.exp(-z)) if z > -30 else 0.0
            w = p * (1 - p)
            vec = [1.0, u, v]
            for i in range(3):
                g[i] += (y - p) * vec[i]
                for j in range(3):
                    H[i][j] += w * vec[i] * vec[j]
        sol = solve3(H, g)
        if not sol:
            return None
        a += sol[0]; b1 += sol[1]; b2 += sol[2]
        if max(abs(s) for s in sol) < 1e-8:
            break
    return [a, b1, b2]


def solve3(H, g):
    M = [H[i][:] + [g[i]] for i in range(3)]
    for c in range(3):
        piv = max(range(c, 3), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        if abs(M[c][c]) < 1e-12:
            return None
        f = M[c][c]
        M[c] = [v / f for v in M[c]]
        for r in range(3):
            if r != c and M[r][c]:
                k = M[r][c]
                M[r] = [v - k * w for v, w in zip(M[r], M[c])]
    return [M[i][3] for i in range(3)]


def t_of(xs, ys, co):
    """The t statistic of the slope in y = co[0] + co[1] x."""
    n = len(xs)
    res = [y - co[0] - co[1] * x for x, y in zip(xs, ys)]
    s2 = sum(r * r for r in res) / max(1, n - 2)
    mx = sum(xs) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    return co[1] / math.sqrt(s2 / sxx) if sxx > 0 and s2 > 0 else float("nan")


def corr(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float("nan")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
