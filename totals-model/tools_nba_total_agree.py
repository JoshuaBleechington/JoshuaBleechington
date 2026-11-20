#!/usr/bin/env python3
"""Does agreement between the model, the simulation and the crew call the game
total? (28 Oct 2026, the user: "if the simulation, the refs and the super model
are all thinking over or under, that should get a green BET signal; two out of
three should be enough. Look at the Lakers and Spurs games: the simulation and
the refs were pointing to the over.")

Each of the three has been measured alone against two seasons of closes and
each measured nothing (NBA.md): the ratings projection is faded the other way
(the market over-moves with it), the sim's own total carries nothing the close
does not (slope 0.002), the crew's over/under record does not carry (t −1.0).
This asks the question the user asked, which is a different one: when two or
three of them point the same way, does the total land there?

Game by game over 2024-25 and 2025-26 (the ledgers joined to KillerSports'
closes, as tools_backtest_nba_sim.py reads them), everything known BEFORE tip:

  the MODEL      the sheet's own total: the close, the ratings projection faded
                 by NBA.FADE (−0.25, shrunk by n/(n+20)) under fifty games and
                 the stage deltas (+1 after the deadline, +2 in the last two
                 weeks), a normal at 18 points: BET at 53%, the page's band
  the SIMULATION the sim's own view, `runs` games from the profiles built on
                 the games before the date (the season before as the prior),
                 the raw chance of the over against the close
  the CREW       each official's over/under record against the close to date
                 (the season before whole, this season to date, the frozen
                 table's shape), z = (W − L) / √(W + L), an official leans at
                 1.5, the crew's z is the sum of its three, the crew leans at 1.5

Then the record against the close, bet at −110, for each alone and for every
agreement: the sim with the crew (the user's two games), the model with
either, all three; by season.

    python3 tools_nba_total_agree.py FOLDER [--runs 400] [--cache rows.json]

FOLDER holds led2425.json, led2526.json, the two KillerSports pages and
nba-tend.json (optional).
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "slate"))
sys.path.insert(0, HERE)
import nbasim  # noqa: E402
from tools_backtest_nba import avg, poss  # noqa: E402
from tools_backtest_nba_sim import load_season  # noqa: E402

FADE, SHRINK_K, FADE_UNTIL, MIN_GAMES, TOTAL_SD = -0.25, 20.0, 50, 10, 18.0
DEADLINE = {"2024-25": "2025-02-06", "2025-26": "2026-02-05"}
LAST2 = {"2024-25": "2025-03-31", "2025-26": "2026-03-30"}
REF_Z, BET_P, SIM_P = 1.5, 0.53, 0.55
PRICE = -110


def phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def units(w, l, price=PRICE):
    return w * (100.0 / -price if price < 0 else price / 100.0) - l


def ref_z(w, l):
    return (w - l) / math.sqrt(w + l) if (w + l) else 0.0


def model_total(close, proj, n, season, date):
    """The sheet's total as the page builds it: the close as the anchor, the faded ratings lean, the stage deltas."""
    mu = close
    if proj is not None and n >= MIN_GAMES and n < FADE_UNTIL:
        mu += FADE * (n / (n + SHRINK_K)) * (proj - close)
    if date >= LAST2[season]:
        mu += 2.0
    elif date > DEADLINE[season]:
        mu += 1.0
    return mu, 1.0 - phi((close - mu) / TOTAL_SD)


def build_rows(folder, runs=400, seed=1):
    files = (("2024-25", "led2425.json", "78766447-query.html", None), ("2025-26", "led2526.json", "a6af4eb0-query.html", "led2425.json"))
    tend = None
    tp = os.path.join(folder, "nba-tend.json")
    if os.path.exists(tp):
        tend = json.load(open(tp))
    crew_past = defaultdict(lambda: [0, 0])    # official -> [over, under] over the seasons before
    rows = []
    for season, led_f, ks_f, prior_f in files:
        led, joined = load_season(folder, led_f, ks_f)
        prior = json.load(open(os.path.join(folder, prior_f)))["games"] if prior_f else None
        closes = {g["id"]: g for g in joined}
        team = defaultdict(list)                   # the ratings to date, as tools_backtest_nba.make_row builds them
        crew_now = defaultdict(lambda: [0, 0])
        cache_date, prof = None, None
        t0 = time.time()
        print("%s: %d games, %d joined to a close" % (season, len(led), len(joined)))
        for i, g in enumerate(led):
            d, A, H = g["date"], g["away"], g["home"]
            if g["id"] in closes:
                cg = closes[g["id"]]
                close, sp = cg["close_total"], cg["close_spread"]
                # the model
                proj, n = None, min(len(team[A]), len(team[H]))
                if n >= MIN_GAMES:
                    lg = [x for h in team.values() for x in h]
                    lg_ortg = 100.0 * sum(x["pts"] for x in lg) / sum(x["poss"] for x in lg)

                    def rt(h):
                        return (100.0 * sum(x["pts"] for x in h) / sum(x["poss"] for x in h), 100.0 * sum(x["opts"] for x in h) / sum(x["oposs"] for x in h),
                                avg([x["poss"] * 48.0 / (x["mins"] / 5.0) for x in h]))
                    ao, ad, ap = rt(team[A]); ho, hd, hp = rt(team[H])
                    pace = (ap + hp) / 2.0
                    proj = pace / 100.0 * (ao + hd - lg_ortg) + pace / 100.0 * (ho + ad - lg_ortg)
                mu, p_model = model_total(close, proj, n, season, d)
                # the crew
                z, found, offs = 0.0, 0, []
                for name in g.get("off") or []:
                    w = crew_past[name][0] + crew_now[name][0]; l = crew_past[name][1] + crew_now[name][1]
                    if w + l >= 5:
                        zz = ref_z(w, l); z += zz; found += 1; offs.append([name, w, l, round(zz, 2)])
                # the simulation
                p_sim, sim_total = None, None
                if d != cache_date:
                    prof = nbasim.profiles_from_ledger(led, d, prior_games=prior, tend=tend)
                    cache_date = d
                a, h = prof["teams"].get(A), prof["teams"].get(H)
                if a and h and min(a["n"], h["n"]) >= 5:
                    setup = nbasim.setup_from_profiles(prof, A, H, d)
                    res = nbasim.simulate(setup, n=runs, seed=seed + i)
                    sm = nbasim.summarize(res, {"total": close, "spread": sp})
                    p_sim = sm["markets"]["total"]["p_raw"] if sm["markets"]["total"]["side"] == "OVER" else 1.0 - sm["markets"]["total"]["p_raw"]
                    sim_total = sm["total"]["mean"]
                rows.append({"season": season, "date": d, "away": A, "home": H, "close": close, "total": g["fa"] + g["fh"], "n": n, "proj": proj, "mu": mu, "p_model": p_model,
                             "p_sim": p_sim, "sim_total": sim_total, "crew_z": round(z, 3), "crew_found": found, "offs": offs})
                if (len(rows) % 300) == 0:
                    print("  %d rows, %.0fs" % (len(rows), time.time() - t0))
            # then record the game for the future
            if g.get("detail") and g.get("sa") and g.get("sh"):
                pa, ph = poss(g["sa"]), poss(g["sh"])
                for side, t, pts, opts, p, op in (("a", A, g["fa"], g["fh"], pa, ph), ("h", H, g["fh"], g["fa"], ph, pa)):
                    team[t].append({"pts": pts, "opts": opts, "poss": p, "oposs": op, "mins": (g["sa"] if side == "a" else g["sh"])["min"]})
                if g["id"] in closes:
                    tot, cl = g["fa"] + g["fh"], closes[g["id"]]["close_total"]
                    if tot != cl:
                        for name in g.get("off") or []:
                            crew_now[name][0 if tot > cl else 1] += 1
        for name, (w, l) in crew_now.items():
            crew_past[name][0] += w; crew_past[name][1] += l
        print("  done, %.0fs" % (time.time() - t0))
    return rows


def record(rs, side_of):
    """(wins, losses, pushes) of calling side_of(r) ('OVER'/'UNDER') against the close."""
    w = l = p = 0
    for r in rs:
        s = side_of(r)
        if r["total"] == r["close"]:
            p += 1
        elif (r["total"] > r["close"]) == (s == "OVER"):
            w += 1
        else:
            l += 1
    return w, l, p


def line(label, rs, side_of):
    w, l, p = record(rs, side_of)
    n = w + l
    if not n:
        return "  %-70s nothing" % label
    z = (w - 0.5 * n) / math.sqrt(0.25 * n)
    return "  %-70s %4d-%-4d %5.1f%%  z %+.1f  %+.1fu%s" % (label, w, l, 100.0 * w / n, z, units(w, l), ("  (%d pushes)" % p) if p else "")


def votes(r):
    """Each voice's side or None: the model at BET, the sim at SIM_P, the crew at its lean."""
    m = "OVER" if r["p_model"] >= BET_P else "UNDER" if r["p_model"] <= 1 - BET_P else None
    s = None if r["p_sim"] is None else "OVER" if r["p_sim"] >= SIM_P else "UNDER" if r["p_sim"] <= 1 - SIM_P else None
    c = "OVER" if r["crew_z"] >= REF_Z else "UNDER" if r["crew_z"] <= -REF_Z else None
    return m, s, c


def report(rows):
    for season in ("2024-25", "2025-26", "both"):
        rs = [r for r in rows if season == "both" or r["season"] == season]
        if not rs:
            continue
        print("\n==== %s: %d games with a close ====" % (season, len(rs)))
        over = sum(1 for r in rs if r["total"] > r["close"]); under = sum(1 for r in rs if r["total"] < r["close"])
        print("  the market: the over %d-%d (%.1f%%)" % (over, under, 100.0 * over / (over + under)))
        print("-- each alone --")
        print(line("the model at BET (53%+), its side", [r for r in rs if votes(r)[0]], lambda r: votes(r)[0]))
        print(line("the model's side at any lean (p off 50%)", [r for r in rs if abs(r["p_model"] - 0.5) > 1e-6], lambda r: "OVER" if r["p_model"] > 0.5 else "UNDER"))
        print(line("the sim's side, any chance", [r for r in rs if r["p_sim"] is not None], lambda r: "OVER" if r["p_sim"] >= 0.5 else "UNDER"))
        print(line("the sim's side at 55%+", [r for r in rs if votes(r)[1]], lambda r: votes(r)[1]))
        print(line("the sim's side at 60%+", [r for r in rs if r["p_sim"] is not None and max(r["p_sim"], 1 - r["p_sim"]) >= 0.60], lambda r: "OVER" if r["p_sim"] >= 0.5 else "UNDER"))
        print(line("the sim's side at 65%+", [r for r in rs if r["p_sim"] is not None and max(r["p_sim"], 1 - r["p_sim"]) >= 0.65], lambda r: "OVER" if r["p_sim"] >= 0.5 else "UNDER"))
        print(line("the crew's lean (z 1.5+)", [r for r in rs if votes(r)[2]], lambda r: votes(r)[2]))
        print(line("the crew's lean at z 2.5+", [r for r in rs if abs(r["crew_z"]) >= 2.5], lambda r: "OVER" if r["crew_z"] > 0 else "UNDER"))
        print("-- two agree --")
        print(line("the SIM (55%+) and the CREW agree [the user's two games]", [r for r in rs if votes(r)[1] and votes(r)[1] == votes(r)[2]], lambda r: votes(r)[1]))
        print(line("the sim (any chance) and the crew agree", [r for r in rs if r["p_sim"] is not None and votes(r)[2] and (("OVER" if r["p_sim"] >= 0.5 else "UNDER") == votes(r)[2])], lambda r: votes(r)[2]))
        print(line("the sim (60%+) and the crew agree", [r for r in rs if r["p_sim"] is not None and votes(r)[2] and max(r["p_sim"], 1 - r["p_sim"]) >= 0.60 and (("OVER" if r["p_sim"] >= 0.5 else "UNDER") == votes(r)[2])], lambda r: votes(r)[2]))
        print(line("the sim (55%+) and the crew agree on the OVER", [r for r in rs if votes(r)[1] == "OVER" and votes(r)[2] == "OVER"], lambda r: "OVER"))
        print(line("the sim (55%+) and the crew agree on the UNDER", [r for r in rs if votes(r)[1] == "UNDER" and votes(r)[2] == "UNDER"], lambda r: "UNDER"))
        print(line("the sim (55%+) and the crew DISAGREE: the sim's side", [r for r in rs if votes(r)[1] and votes(r)[2] and votes(r)[1] != votes(r)[2]], lambda r: votes(r)[1]))
        print(line("the MODEL (BET) and the SIM (55%+) agree", [r for r in rs if votes(r)[0] and votes(r)[0] == votes(r)[1]], lambda r: votes(r)[0]))
        print(line("the model (BET) and the sim (55%+) disagree: the model's side", [r for r in rs if votes(r)[0] and votes(r)[1] and votes(r)[0] != votes(r)[1]], lambda r: votes(r)[0]))
        print(line("the MODEL (BET) and the CREW agree", [r for r in rs if votes(r)[0] and votes(r)[0] == votes(r)[2]], lambda r: votes(r)[0]))
        print("-- the vote --")
        for k in (3, 2):
            def agree_k(r, k=k):
                v = [x for x in votes(r) if x]
                for sd_ in ("OVER", "UNDER"):
                    if v.count(sd_) >= k and v.count("OVER" if sd_ == "UNDER" else "UNDER") == 0:
                        return sd_
                return None
            print(line("%d of 3 point the same way, none against" % k, [r for r in rs if agree_k(r)], agree_k))
        def two_any(r):
            v = [x for x in votes(r) if x]
            for sd_ in ("OVER", "UNDER"):
                if v.count(sd_) >= 2:
                    return sd_
            return None
        print(line("2 of 3 point the same way (the third may oppose)", [r for r in rs if two_any(r)], two_any))
        # the sim and the crew as a slope: the residual on the sim's lean, with and without the crew on the same side
        agree = [r for r in rs if r["p_sim"] is not None and votes(r)[2] and (("OVER" if r["p_sim"] >= 0.5 else "UNDER") == votes(r)[2])]
        if len(agree) >= 30:
            res_ = [(r["total"] - r["close"]) * (1 if votes(r)[2] == "OVER" else -1) for r in agree]
            print("  with the sim and the crew on the same side (n %d): the total lands %+.2f points toward that side on average (sd %.1f, t %+.1f)" % (
                len(res_), avg(res_), (sum((x - avg(res_)) ** 2 for x in res_) / (len(res_) - 1)) ** 0.5, avg(res_) / ((sum((x - avg(res_)) ** 2 for x in res_) / (len(res_) - 1)) ** 0.5 / math.sqrt(len(res_)))))


def main(argv):
    if not argv:
        print(__doc__); return 2
    folder, runs, cache = argv[0], 400, None
    if "--runs" in argv:
        runs = int(argv[argv.index("--runs") + 1])
    if "--cache" in argv:
        cache = argv[argv.index("--cache") + 1]
    if cache and os.path.exists(cache):
        rows = json.load(open(cache))
        print("rows from %s: %d" % (cache, len(rows)))
    else:
        rows = build_rows(folder, runs=runs)
        if cache:
            json.dump(rows, open(cache, "w"))
    report(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
