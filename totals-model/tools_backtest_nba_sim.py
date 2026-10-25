"""Backtest of the NBA simulation against the closing total and spread.

    python3 tools_backtest_nba_sim.py FOLDER [--runs 1000] [--season 2025-26] [--seed 1]

FOLDER holds led2425.json, led2526.json and the two KillerSports pages
(78766447-query.html for 2024-25, a6af4eb0-query.html for 2025-26), as
tools_backtest_nba.py reads them. Game by game in date order, each club's
profile is built from the season's games before that date (blended with the
whole of the season before, where the ledger has it), the game is simulated
`runs` times, and the sim's probability for the over, the home cover and the
home win is kept beside what happened. Reported: the sim's total and margin
against the close (bias, spread, the slope of the close's residual on the
sim's lean), the calibration of each market by probability bucket, the record
and units at -110 by confidence band, and the shrink that makes "says" match
"does".
"""
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "slate"))
import nbasim  # noqa: E402
from tools_backtest_nba import ks_rows, TEAMS, ols, avg, sd  # noqa: E402

PRICE = -110


def units(w, l, price=PRICE):
    win = 100.0 / -price if price < 0 else price / 100.0
    return w * win - l


def load_season(folder, led_f, ks_f):
    led = json.load(open(os.path.join(folder, led_f)))["games"]
    led = [g for g in led if g.get("hn") in TEAMS and g.get("an") in TEAMS and g.get("detail")]
    ks = {(r["date"], r["home"], r["away"]): r for r in ks_rows(os.path.join(folder, ks_f))}
    joined = []
    for g in led:
        r = ks.get((g["date"], g["hn"], g["an"]))
        if not r or r["total"] is None or r["spread"] is None or r["hpts"] != g["fh"] or r["apts"] != g["fa"]:
            continue
        g = dict(g)
        g["close_total"], g["close_spread"] = r["total"], r["spread"]
        joined.append(g)
    joined.sort(key=lambda g: (g["date"], g["id"]))
    return sorted(led, key=lambda g: (g["date"], g["id"])), joined


def bucket(p):
    c = max(p, 1 - p)
    return "70+" if c >= 0.70 else "65-70" if c >= 0.65 else "60-65" if c >= 0.60 else "55-60" if c >= 0.55 else "50-55"


def run(folder, runs=1000, seasons=("2024-25", "2025-26"), seed=1, min_games=5):
    files = {"2024-25": ("led2425.json", "78766447-query.html", None), "2025-26": ("led2526.json", "a6af4eb0-query.html", "led2425.json")}
    rows = []
    for season in seasons:
        led_f, ks_f, prior_f = files[season]
        led, joined = load_season(folder, led_f, ks_f)
        prior = json.load(open(os.path.join(folder, prior_f)))["games"] if prior_f else None
        print("%s: %d games with detail, %d joined to a close%s" % (season, len(led), len(joined), ", with the season before as the prior" if prior else ""))
        t0 = time.time()
        cache_date, prof = None, None
        for i, g in enumerate(joined):
            if g["date"] != cache_date:
                prof = nbasim.profiles_from_ledger(led, g["date"], prior_games=prior)
                cache_date = g["date"]
            a, h = prof["teams"].get(g["away"]), prof["teams"].get(g["home"])
            if not a or not h or min(a["n"], h["n"]) < min_games:
                continue
            setup = nbasim.setup_from_profiles(prof, g["away"], g["home"], g["date"])
            res = nbasim.simulate(setup, n=runs, seed=seed + i)
            sm = nbasim.summarize(res, {"total": g["close_total"], "spread": g["close_spread"]})
            tot, mg = g["fa"] + g["fh"], g["fh"] - g["fa"]
            h1 = (g["qa"][0] + g["qa"][1] + g["qh"][0] + g["qh"][1]) if len(g.get("qa") or []) >= 2 and len(g.get("qh") or []) >= 2 else None
            rows.append({"season": season, "date": g["date"], "away": g["away"], "home": g["home"], "n": min(a["n"], h["n"]),
                         "close": g["close_total"], "spread": g["close_spread"], "total": tot, "margin": mg, "h1": h1,
                         "sim_total": sm["total"]["mean"], "sim_sd": sm["total"]["sd"], "sim_margin": sm["margin"]["mean"], "sim_h1": sm["h1"]["mean"],
                         "p_over": sm["markets"]["total"]["p_raw"] if sm["markets"]["total"]["side"] == "OVER" else 1 - sm["markets"]["total"]["p_raw"],
                         "p_home_cover": sm["markets"]["spread"]["p_raw"] if sm["markets"]["spread"]["side"] == "HOME" else 1 - sm["markets"]["spread"]["p_raw"],
                         "p_home": sm["home_win"], "ot": sm["ot"], "q_share": sm["q_share"],
                         "qa": g.get("qa"), "qh": g.get("qh")})
            if (i + 1) % 200 == 0:
                print("  %d games, %.0fs" % (i + 1, time.time() - t0))
        print("  done: %d games simulated, %.0fs" % (len([r for r in rows if r["season"] == season]), time.time() - t0))
    return rows


def report(rows):
    print()
    print("== the sim's numbers against the close ==")
    for season in sorted(set(r["season"] for r in rows)) + ["both"]:
        rs = [r for r in rows if season == "both" or r["season"] == season]
        if not rs:
            continue
        res_close = [r["total"] - r["close"] for r in rs]
        res_sim = [r["total"] - r["sim_total"] for r in rs]
        lean = [r["sim_total"] - r["close"] for r in rs]
        o = ols(lean, res_close)
        mres = [r["margin"] - r["sim_margin"] for r in rs]
        mlean = [r["sim_margin"] + r["spread"] for r in rs]   # the sim's lean on the home side, in points
        mres_close = [r["margin"] + r["spread"] for r in rs]
        om = ols(mlean, mres_close)
        print("%s: %d games. total: final-close %+.2f (sd %.1f), final-sim %+.2f (sd %.1f); sim-close sd %.1f; slope of (final-close) on (sim-close) %+.3f (t %.1f)" % (
            season, len(rs), avg(res_close), sd(res_close), avg(res_sim), sd(res_sim), sd(lean), o[0] if o else float("nan"), o[1] if o else float("nan")))
        print("    margin: final-sim %+.2f (sd %.1f); slope of (home cover residual) on (sim lean) %+.3f (t %.1f); sim's own sd of the total %.1f, OT %.3f" % (
            avg(mres), sd(mres), om[0] if om else float("nan"), om[1] if om else float("nan"), avg([r["sim_sd"] for r in rs]), avg([r["ot"] for r in rs])))
        withq = [r for r in rs if r["q_share"] and r["qa"] and len(r["qa"]) == 4]
        if withq:
            real = [avg([(r["qa"][k] + r["qh"][k]) / float(sum(r["qa"]) + sum(r["qh"])) for r in withq]) for k in range(4)]
            simq = [avg([r["q_share"][k] for r in withq]) for k in range(4)]
            print("    quarter shares, real %s, sim %s" % (" / ".join("%.3f" % x for x in real), " / ".join("%.3f" % x for x in simq)))
        h1s = [r for r in rs if r["h1"] is not None]
        if h1s:
            print("    first half: real %.1f, sim %.1f" % (avg([r["h1"] for r in h1s]), avg([r["sim_h1"] for r in h1s])))
    print()
    print("== calibration: says vs does, and the record at -110 by band ==")
    for name, key, outcome in (("TOTAL over", "p_over", lambda r: r["total"] > r["close"]), ("SPREAD home cover", "p_home_cover", lambda r: r["margin"] + r["spread"] > 0),
                               ("MONEYLINE home", "p_home", lambda r: r["margin"] > 0)):
        rs = [r for r in rows if not (key == "p_over" and r["total"] == r["close"]) and not (key == "p_home_cover" and r["margin"] + r["spread"] == 0)]
        print(name)
        by = {}
        for r in rs:
            p = r[key]
            side_p = p if p >= 0.5 else 1 - p
            hit = outcome(r) if p >= 0.5 else not outcome(r)
            b = bucket(p)
            d = by.setdefault(b, {"n": 0, "w": 0, "says": 0.0})
            d["n"] += 1
            d["w"] += 1 if hit else 0
            d["says"] += side_p
        for b in ("50-55", "55-60", "60-65", "65-70", "70+"):
            d = by.get(b)
            if d:
                print("  %-6s n %4d  says %.1f%%  does %.1f%%  record %d-%d  %+.1fu" % (b, d["n"], 100 * d["says"] / d["n"], 100.0 * d["w"] / d["n"], d["w"], d["n"] - d["w"], units(d["w"], d["n"] - d["w"])))
        # the shrink: slope of (hit - 0.5) on (side_p - 0.5)
        xs = [(r[key] if r[key] >= 0.5 else 1 - r[key]) - 0.5 for r in rs]
        ys = [(1.0 if (outcome(r) if r[key] >= 0.5 else not outcome(r)) else 0.0) - 0.5 for r in rs]
        o = ols(xs, ys)
        brier = avg([(r[key] - (1.0 if outcome(r) else 0.0)) ** 2 for r in rs])
        print("  slope of does on says %+.2f (t %.1f) -> shrink %.2f; Brier %.4f (coin %.4f); n %d" % (o[0], o[1], max(0.0, min(1.5, o[0])), brier, 0.25, len(rs)))
        if key != "p_home":
            for cut in (0.60, 0.65, 0.70):
                sel = [r for r in rs if max(r[key], 1 - r[key]) >= cut]
                w = sum(1 for r in sel if (outcome(r) if r[key] >= 0.5 else not outcome(r)))
                print("  at %.0f%%+: %d-%d, %+.1fu over %d games" % (100 * cut, w, len(sel) - w, units(w, len(sel) - w), len(sel)))


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    folder = argv[0]
    runs, seed, seasons = 1000, 1, ("2024-25", "2025-26")
    i = 1
    while i < len(argv):
        if argv[i] == "--runs":
            runs = int(argv[i + 1]); i += 2
        elif argv[i] == "--seed":
            seed = int(argv[i + 1]); i += 2
        elif argv[i] == "--season":
            seasons = (argv[i + 1],); i += 2
        else:
            i += 1
    rows = run(folder, runs=runs, seasons=seasons, seed=seed)
    out = os.path.join(folder, "sim-backtest.json")
    with open(out, "w") as f:
        json.dump(rows, f)
    report(rows)
    print("\nrows written to %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
