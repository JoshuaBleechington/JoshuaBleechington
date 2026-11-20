#!/usr/bin/env python3
"""Does a model built from the players beat the model built from the clubs?
(26 Oct 2026, the user: "could the simulation test the starting lineups? we
have the individual players' info.")

1. Player impact ratings from the stints (tools_nba_stints.py): a ridge
   regression of each stint's points per 100 possessions on who was on the
   floor, an offence and a defence number per man (adjusted plus-minus, the
   standard way), the previous season's stints as the prior at a weight, the
   ridge strength chosen on a held-out slice.
2. A club's rating for a game from its men: each man's number times his
   share of the 240 minutes. Three versions: the actual minutes played that
   night (what a perfect rotation call would give), the rotation projected
   from the club's last games before the night (what the slate could know),
   and the club model the simulation uses now (profiles_from_ledger).
3. Every 2025-26 game predicted from ratings fit on the games before its
   week, against the final and against the close: the error of each model's
   margin and total, and whether the player model adds anything the close
   does not already carry (a regression of the result on the close and the
   model together).

Usage: python3 tools_nba_lineups.py STINTS_DIR NBA_DIR [--prior-weight 0.5] [--lambda L]
  STINTS_DIR holds nba-stints-202425.json and nba-stints-202526.json and the ledgers
  NBA_DIR holds led2425.json, led2526.json and the KillerSports pages for the closes
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

import numpy as np
from scipy import sparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "slate"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nbasim  # noqa: E402
from tools_backtest_nba_sim import load_season  # noqa: E402


def load_stints(path):
    return json.load(open(path))["games"]


def rows_from(games, weight=1.0, before=None):
    """One observation per stint per offence: (offence five, defence five, home offence?, pts per 100 poss, weight)."""
    out = []
    for g in games:
        if before and g["date"] >= before:
            continue
        for s in g["st"]:
            per, secs, a5, h5, pa, ph, qa, qh = s
            if len(a5) != 5 or len(h5) != 5:
                continue
            if qa >= 1.0:
                out.append((a5, h5, 0, 100.0 * pa / qa, qa * weight))
            if qh >= 1.0:
                out.append((h5, a5, 1, 100.0 * ph / qh, qh * weight))
    return out


def fit(obs, lam):
    """Ridge fit -> (intercept, home, {pid: (off, def)}) with the possessions as weights."""
    ids = {}
    for o5, d5, _h, _y, _w in obs:
        for p in o5 + d5:
            if p not in ids:
                ids[p] = len(ids)
    n, m = len(obs), len(ids)
    rows, cols, vals = [], [], []
    y = np.zeros(n); w = np.zeros(n); home = np.zeros(n)
    for i, (o5, d5, h, yy, ww) in enumerate(obs):
        for p in o5:
            rows.append(i); cols.append(ids[p]); vals.append(1.0)
        for p in d5:
            rows.append(i); cols.append(m + ids[p]); vals.append(1.0)
        y[i] = yy; w[i] = ww; home[i] = h
    X = sparse.csr_matrix((vals, (rows, cols)), shape=(n, 2 * m))
    # centre on the weighted mean and the home court, then ridge on the players
    wsum = w.sum()
    mu = float((w * y).sum() / wsum)
    hcoef = float((w * home * (y - mu)).sum() / max(1e-9, (w * home * home).sum()))   # a crude home-court, refined below with the players in
    yc = y - mu - hcoef * home
    Xw = sparse.diags(w) @ X
    A = (X.T @ Xw).toarray() + lam * np.eye(2 * m)
    b = X.T @ (w * yc)
    beta = np.linalg.solve(A, b)
    # the home court with the players accounted for
    resid = yc - X @ beta
    hcoef2 = hcoef + float((w * home * resid).sum() / max(1e-9, (w * home * home).sum()))
    rate = {p: (float(beta[j]), float(beta[m + j])) for p, j in ids.items()}
    return mu, hcoef2, rate


def predict_stint(model, o5, d5, h):
    mu, hc, rate = model
    return mu + hc * h + sum(rate.get(p, (0.0, 0.0))[0] for p in o5) + sum(rate.get(p, (0.0, 0.0))[1] for p in d5)


def holdout(obs_train, obs_test, lams):
    out = []
    for lam in lams:
        model = fit(obs_train, lam)
        se = sum(ww * (yy - predict_stint(model, o5, d5, h)) ** 2 for o5, d5, h, yy, ww in obs_test)
        wsum = sum(ww for *_r, ww in obs_test)
        base = sum(ww * (yy - model[0] - model[1] * h) ** 2 for o5, d5, h, yy, ww in obs_test)
        out.append((lam, (se / wsum) ** 0.5, (base / wsum) ** 0.5))
    return out


def club_minutes(box_side):
    return {str(p[0]): float(p[3] or 0) for p in box_side if float(p[3] or 0) > 0}


def lineup_rating(model, mins):
    """A club's offence and defence from its men's numbers at their minutes (five on the floor: the shares sum to five)."""
    tot = sum(mins.values()) or 1.0
    off = sum(model[2].get(p, (0.0, 0.0))[0] * m / tot * 5.0 for p, m in mins.items())
    dfn = sum(model[2].get(p, (0.0, 0.0))[1] * m / tot * 5.0 for p, m in mins.items())
    return off, dfn


def projected_minutes(history, ab, date, last=3):
    """The rotation the slate could know: the club's men over its last games before the date, each at his average minutes in them."""
    games = [g for g in history.get(ab, []) if g["date"] < date][-last:]
    if not games:
        return {}
    mins = {}
    for g in games:
        for pid, m in g["mins"].items():
            mins.setdefault(pid, []).append(m)
    return {pid: sum(v) / len(games) for pid, v in mins.items()}


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    sdir, ndir = argv[0], argv[1]
    prior_w, lam_fixed = 0.5, None
    i = 2
    while i < len(argv):
        if argv[i] == "--prior-weight":
            prior_w = float(argv[i + 1]); i += 2
        elif argv[i] == "--lambda":
            lam_fixed = float(argv[i + 1]); i += 2
        else:
            i += 1
    st2425 = load_stints(os.path.join(sdir, "nba-stints-202425.json"))
    st2526 = load_stints(os.path.join(sdir, "nba-stints-202526.json"))
    led2425 = json.load(open(os.path.join(sdir, "nba-ledger-202526.json")))   # the ledgers: last season's for the prior, this one's for the boxes
    # (the stints' season tags: 2024-25 stints come from nba-pbp-202425 and the ledger nba-ledger-202425)
    led_prev = json.load(open(os.path.join(sdir, "nba-ledger-202425.json")))
    led_this = led2425
    # 1. the ridge strength on a held-out slice of 2024-25: fit on games before 1 March, test on the rest
    print("== the ridge strength, 2024-25 held out from 1 March ==")
    train = rows_from(st2425, before="2025-03-01"); test = [o for o in rows_from(st2425) if o not in train] if False else None
    test = []
    for g in st2425:
        if g["date"] >= "2025-03-01":
            test += rows_from([g])
    lams = [lam_fixed] if lam_fixed else [500.0, 1000.0, 2000.0, 4000.0, 8000.0]
    best = None
    for lam, rmse, base in holdout(train, test, lams):
        print("  lambda %6.0f: held-out stint error %.2f per 100 (the league mean alone %.2f)" % (lam, rmse, base))
        if best is None or rmse < best[1]:
            best = (lam, rmse)
    lam = best[0]
    print("  using lambda %.0f" % lam)
    # 2. the game test on 2025-26, ratings refit each week on 2024-25 (at %.2f weight) and 2025-26 to date
    led, joined = load_season(ndir, "led2526.json", "a6af4eb0-query.html")
    boxes = {g["id"]: g for g in led_this["games"]}
    prior_games = led_prev["games"]
    history = {}
    for g in sorted(led_this["games"], key=lambda g: g["date"]):
        for side, key in (("away", "pa"), ("home", "ph")):
            history.setdefault(g[side], []).append({"date": g["date"], "mins": club_minutes(g[key])})
    print("== 2025-26: %d games with a close; ratings refit weekly on 2024-25 at weight %.2f plus this season to date ==" % (len(joined), prior_w))
    rows = []
    week_of = lambda d: (dt.date.fromisoformat(d) - dt.date(2025, 10, 20)).days // 7  # noqa: E731
    cache = {}
    prof_cache = {}
    lg_prev = nbasim.LEAGUE
    for g in sorted(joined, key=lambda g: g["date"]):
        wk = week_of(g["date"])
        if wk < 1:
            continue   # the first week has no games of this season behind it
        if wk not in cache:
            cutoff = (dt.date(2025, 10, 20) + dt.timedelta(days=7 * wk)).isoformat()
            obs = rows_from(st2425, weight=prior_w) + rows_from(st2526, before=cutoff)
            cache[wk] = fit(obs, lam)
            print("  week %2d (from %s): fit on %d stint-sides" % (wk, cutoff, len(obs)), file=sys.stderr)
        model = cache[wk]
        box = boxes.get(g["id"])
        if not box:
            continue
        if g["date"] not in prof_cache:
            prof_cache[g["date"]] = nbasim.profiles_from_ledger(led_this["games"], g["date"], prior_games=prior_games)
        prof = prof_cache[g["date"]]
        ta, th = prof["teams"].get(g["away"]), prof["teams"].get(g["home"])
        if not ta or not th:
            continue
        lgp = prof["league"]
        poss = ta["pace"] + th["pace"] - lgp["pace"]
        # the club model's points: the simulation's own formula without the extras
        ppa_club = (ta["ortg"] + th["drtg"] - lgp["ortg"]) / 100.0 - lgp["home"] / 2.0 / lgp["pace"]
        pph_club = (th["ortg"] + ta["drtg"] - lgp["ortg"]) / 100.0 + lgp["home"] / 2.0 / lgp["pace"]
        # the player model's points: the lineup's offence into the lineup's defence, around the stints' league mean and home court
        mu, hc, _r = model
        def pts(mins_a, mins_h):
            oa, da = lineup_rating(model, mins_a); oh, dh = lineup_rating(model, mins_h)
            return (mu + oa + dh) / 100.0 * poss, (mu + hc + oh + da) / 100.0 * poss
        act_a, act_h = pts(club_minutes(box["pa"]), club_minutes(box["ph"]))
        pm_a, pm_h = projected_minutes(history, g["away"], g["date"]), projected_minutes(history, g["home"], g["date"])
        if pm_a and pm_h:
            prj_a, prj_h = pts(pm_a, pm_h)
        else:
            prj_a = prj_h = None
        rows.append({"date": g["date"], "week": wk, "away": g["away"], "home": g["home"], "fa": g["fa"], "fh": g["fh"], "close": g["close_total"], "spread": g["close_spread"],
                     "club": (ppa_club * poss, pph_club * poss), "actual_mins": (act_a, act_h), "projected": (prj_a, prj_h) if prj_a is not None else None, "n": min(ta["n"], th["n"])})
    def table(rs, label):
        print()
        print("== %s: %d games ==" % (label, len(rs)))
        marg = np.array([r["fh"] - r["fa"] for r in rs]); tot = np.array([r["fa"] + r["fh"] for r in rs])
        cl_m = np.array([-r["spread"] for r in rs]); cl_t = np.array([r["close"] for r in rs])
        print("  %-34s %12s %12s   %s" % ("model", "margin RMSE", "total RMSE", "adds to the close? (t of the model beside the close, margin / total)"))
        print("  %-34s %12.2f %12.2f" % ("the close", np.sqrt(np.mean((marg - cl_m) ** 2)), np.sqrt(np.mean((tot - cl_t) ** 2))))
        for key, lab in (("club", "the club model (as the sim uses)"), ("actual_mins", "players at the minutes they played"), ("projected", "players at the projected rotation")):
            sel = [r for r in rs if r.get(key)]
            if len(sel) < 30:
                continue
            m = np.array([r["fh"] - r["fa"] for r in sel]); t = np.array([r["fa"] + r["fh"] for r in sel])
            pm = np.array([r[key][1] - r[key][0] for r in sel]); pt = np.array([r[key][0] + r[key][1] for r in sel])
            cm = np.array([-r["spread"] for r in sel]); ct = np.array([r["close"] for r in sel])
            def tstat(yv, c, x):
                X = np.column_stack([np.ones(len(yv)), c, x]); beta, res, rk, sv = np.linalg.lstsq(X, yv, rcond=None)
                resid = yv - X @ beta; s2 = (resid @ resid) / max(1, len(yv) - 3); cov = s2 * np.linalg.inv(X.T @ X)
                return beta[2], beta[2] / np.sqrt(cov[2, 2])
            bm, tm = tstat(m, cm, pm); bt, tt = tstat(t, ct, pt)
            print("  %-34s %12.2f %12.2f   coef %+.2f t %+.1f / coef %+.2f t %+.1f%s" % (lab, np.sqrt(np.mean((m - pm) ** 2)), np.sqrt(np.mean((t - pt) ** 2)), bm, tm, bt, tt, "" if len(sel) == len(rs) else " (%d games)" % len(sel)))
    table(rows, "every game from the second week")
    table([r for r in rows if r["date"] < "2025-11-20"], "the first month (to 19 Nov), where the rosters are newest")
    table([r for r in rows if r["date"] >= "2026-01-01"], "from January")
    json.dump(rows, open(os.path.join(sdir, "lineup-test.json"), "w"))
    # the latest ratings, for a look
    model = cache[max(cache)]
    top = sorted(model[2].items(), key=lambda kv: -(kv[1][0] - kv[1][1]))[:12]
    names = {}
    for g in led_this["games"] + led_prev["games"]:
        for p in g["pa"] + g["ph"]:
            names[str(p[0])] = p[1]
    print()
    print("== the twelve biggest impacts in the last fit (offence + defence, per 100 possessions on the floor) ==")
    for pid, (o, d) in top:
        print("  %-24s %+5.1f  (offence %+.1f, defence %+.1f)" % (names.get(pid, pid), o - d, o, -d))
    json.dump({"mu": model[0], "home": model[1], "lambda": lam, "prior_weight": prior_w, "players": {pid: {"n": names.get(pid, pid), "off": round(o, 2), "def": round(d, 2)} for pid, (o, d) in model[2].items()}},
              open(os.path.join(sdir, "nba-players-202526.json"), "w"), indent=0)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
