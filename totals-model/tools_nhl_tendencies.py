#!/usr/bin/env python3
"""The hockey simulation's league constants, measured (29 Oct 2026): what
nhlsim.LEAGUE needs, from MoneyPuck's shot files (every unblocked shot with
its state, period, clock, expected goals, the score and the goalie) joined to
ESPN's play-by-play (slate.py nhl-pbp: the penalties with their clocks, the
officials) through the league ledger (the dates and the NHL game ids).

The play-by-play's penalties give the time each side spends in each strength
state (nhlsim.timeline: a minor is two minutes, a double four, ended by a
power-play goal; fights and misconducts put no one in the box), so every
rate here is per 60 minutes of the state's own time, which the shot file
alone cannot give. The reconstruction is checked against the shot file's
skater counts at every shot.

Measured, regular season only:
  1. shots per 60 and goals per shot by state (5v5, PP, PK, 4v4, 3v3);
  2. minors per 60 by period, the double-minor share; by crew and by club;
  3. score effects at 5v5: rate and quality by the shooting side's margin;
  4. period effects at 5v5 (level or not): rate and quality by period;
  5. home ice: the home side's rate and quality against the away side's;
  6. the empty net: the chance of a pull by the deficit and the seconds
     left at the first empty-net shot, the empty net's rates;
  7. overtime: 3v3 shots per 60 and goals per shot, the shootout's share;
  8. the goalies: goals allowed against expected, the half-to-half
     reliability that sets the shrink;
  9. the reliability of the club figures by half-season (the K's);
 10. the whole as nhlsim.LEAGUE would print it, and nhl-tend.json (the
     crews' and clubs' minors per game) for the slate.

    python3 tools_nhl_tendencies.py --shots shots_2024.csv shots_2025.csv --pbp nhl-pbp-20242025.json nhl-pbp-20252026.json \
        --ledger nhl-ledger-20242025.json nhl-ledger-20252026.json [--out nhl-tend.json]
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


def pct(x):
    return "%.1f%%" % (100 * x)


def corr(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float("nan")


def load_shots(paths):
    """Every shot, per game: {(season, gid5): {"home", "away", "shots": [...]}} with the row fields the measures need."""
    import csv
    games = {}
    for path in paths:
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            for r in csv.DictReader(fh):
                if r.get("isPlayoffGame") not in ("0", "0.0", ""):
                    continue
                key = (r["season"], str(int(float(r["game_id"]))))
                g = games.setdefault(key, {"season": r["season"], "gid": key[1], "home": r["homeTeamCode"], "away": r["awayTeamCode"], "shots": []})
                is_home = nhlsim._flag(r["isHomeTeam"])
                hs, as_ = int(float(r["homeSkatersOnIce"] or 5)), int(float(r["awaySkatersOnIce"] or 5))
                he, ae = nhlsim._flag(r.get("homeEmptyNet")), nhlsim._flag(r.get("awayEmptyNet"))
                g["shots"].append({"p": int(float(r["period"])), "t": int(float(r["time"])), "goal": nhlsim._flag(r["goal"]), "xg": float(r["xGoal"] or 0),
                                   "home": is_home, "st": nhlsim._state_of(hs, as_, he, ae, is_home), "hs": hs, "as": as_, "he": he, "ae": ae,
                                   "hg": int(float(r["homeTeamGoals"])), "ag": int(float(r["awayTeamGoals"])), "gk": str(r.get("goalieIdForShot") or "").split(".")[0],
                                   "gkn": r.get("goalieNameForShot") or "", "en": nhlsim._flag(r.get("shotOnEmptyNet"))})
    for g in games.values():
        g["shots"].sort(key=lambda s: (s["p"], s["t"]))
    return games


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", nargs="+", required=True)
    ap.add_argument("--pbp", nargs="+", required=True)
    ap.add_argument("--ledger", nargs="+", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    shots = load_shots(a.shots)
    # the ledger joins the shot file's game id to a date and the play-by-play's (date, away, home) to the same game
    led = {}
    for p in a.ledger:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        for g in d["games"]:
            gid = str(g["id"])
            led[(gid[:4], gid[-5:])] = g
    pbp = {}
    for p in a.pbp:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        for g in d["games"]:
            pbp[(g["date"], g["away"], g["home"])] = g
    joined = []
    missing = 0
    for key, g in sorted(shots.items()):
        lg = led.get(key)
        if not lg:
            missing += 1
            continue
        pb = pbp.get((lg["date"], lg["away"], lg["home"]))
        if not pb or pb.get("away") != g["away"] or pb.get("home") != g["home"]:
            missing += 1
            continue
        g["date"] = lg["date"]
        g["led"] = lg
        g["pbp"] = pb
        joined.append(g)
    print("%d games with shots, %d joined to the ledger and the play-by-play (%d not), seasons %s" % (len(shots), len(joined), missing, sorted(set(g["season"] for g in joined))))
    n = float(len(joined))

    # ---- the strength timeline checked against the shot file's skaters ----
    agree = total = 0
    times = collections.defaultdict(float)        # state (one side's view, both sides counted) -> seconds
    times_p = collections.defaultdict(float)      # (period, state)
    times_m = collections.defaultdict(float)      # (margin from the side's view, 5v5, period<=3)
    ot_secs = 0.0
    for g in joined:
        segs = nhlsim.timeline(g["pbp"]["plays"])
        g["segs"] = segs
        for t0, t1, per, sa, sh, ga, gh in segs:
            d = t1 - t0
            if per > 3:
                ot_secs += d
                continue
            for mine, theirs, gf, gagainst in ((sa, sh, ga, gh), (sh, sa, gh, ga)):
                st = nhlsim.state_of_skaters(mine, theirs)
                if mine > theirs and mine - theirs >= 2:
                    st = "PP2"
                times[st] += d
                times_p[(per, st)] += d
                if st == "5v5":
                    times_m[max(-3, min(3, gf - gagainst))] += d
        # the state at each shot from the timeline vs the file (the file's time is seconds into the GAME)
        i = 0
        for s in g["shots"]:
            if s["p"] > 3 or s["he"] or s["ae"]:
                continue
            gt = s["t"]
            while i < len(segs) - 1 and segs[i][1] <= gt:
                i += 1
            seg = segs[i]
            total += 1
            if (seg[3], seg[4]) == (s["as"], s["hs"]):
                agree += 1
    print("\n== the strength timeline from the penalties agrees with the shot file's skaters at %s of %d regulation shots ==" % (pct(agree / total), total))
    t55 = times["5v5"] / 2 / n
    tpp = times["PP"] / n   # one side's PP seconds a game = the other's PK
    print("  a game: 5v5 %.0f s (%.1f min), one side on the power play %.0f s, two-man %.0f s, 4v4 %.0f s; overtime %.1f s a game" % (
        t55, t55 / 60, tpp, times["PP2"] / n, times["44"] / 2 / n, ot_secs / n))

    # ---- 1. rates per 60 of the state's time, goals per shot ----
    print("\n== 1. shots per 60 of the state's time (one side) and goals per shot, by state ==")
    by_st = collections.defaultdict(lambda: [0, 0.0, 0])
    for g in joined:
        for s in g["shots"]:
            if s["p"] > 4:
                continue
            st = s["st"]
            if st == "PP":
                mine, theirs = (s["hs"], s["as"]) if s["home"] else (s["as"], s["hs"])
                if mine - theirs >= 2:
                    st = "PP2"
            d = by_st[st]
            d[0] += 1; d[1] += s["xg"]; d[2] += s["goal"]
    league = {}
    # the even-strength states hold both sides' shots over the game's seconds in the state, so one side's rate is half;
    # the power play's and the kill's shots are one side's over the state's seconds already
    for st, secs, sides in (("5v5", times["5v5"] / 2, 2), ("PP", times["PP"], 1), ("PP2", times["PP2"], 1), ("PK", times["PP"] + times["PP2"], 1), ("44", times["44"] / 2, 2), ("33", ot_secs, 2)):
        d = by_st[st]
        per60 = d[0] / secs * 3600 / sides if secs else float("nan")
        print("  %-4s %7.1f shots per 60, one side (%d shots over %.0f s), xG per shot %.4f, goals per shot %.4f" % (st, per60, d[0], secs, d[1] / d[0] if d[0] else 0, d[2] / d[0] if d[0] else 0))
        league[st] = {"per60": per60, "xg": d[1] / d[0] if d[0] else 0, "q": d[2] / d[0] if d[0] else 0}
    print("  the two-man advantage shoots %.2fx the power play's rate at %.2fx its quality" % (league["PP2"]["per60"] / league["PP"]["per60"], league["PP2"]["q"] / league["PP"]["q"]))

    # ---- 2. minors ----
    print("\n== 2. minors that give a power play (one side, per 60 of game time), by period; the double-minor share ==")
    minors_p = [0, 0, 0]
    doubles = 0
    crews = collections.defaultdict(lambda: [0, 0])     # referee -> [games, minors in them]
    clubs = collections.defaultdict(lambda: [0, 0, 0])  # club -> [games, taken, drawn]
    for g in joined:
        mn = nhlsim.minors_taken(g["pbp"]["plays"])
        for p in g["pbp"]["plays"]:
            if p[2] == "P" and p[0] and p[0] <= 3 and p[3] in (0, 1):
                k = nhlsim.pen_kind(p[7])
                if k and k[1] == "double":
                    doubles += 1
        tot_m = sum(mn[0]) + sum(mn[1])
        for per in range(3):
            minors_p[per] += mn[0][per] + mn[1][per]
        refs = [o[0] for o in g["pbp"].get("off") or [] if isinstance(o, list) and o[1] == "R"]
        for r in refs:
            crews[r][0] += 1
            crews[r][1] += tot_m
        for side, ab in ((0, g["away"]), (1, g["home"])):
            c = clubs[ab]
            c[0] += 1; c[1] += sum(mn[side]); c[2] += sum(mn[1 - side])
    tot_minors = sum(minors_p)
    print("  %.3f minors a game per side (%.3f a game both sides); by period %s (both sides); double minors %s of them" % (
        tot_minors / 2 / n, tot_minors / n, ", ".join("%.2f" % (minors_p[p] / n) for p in range(3)), pct(doubles / tot_minors)))
    per_mult = [minors_p[p] / (tot_minors / 3.0) for p in range(3)]
    print("  the period multipliers: %s" % ", ".join("%.3f" % x for x in per_mult))
    ref_rows = sorted(((v[1] / v[0], v[0], k) for k, v in crews.items() if v[0] >= 20), reverse=True)
    if ref_rows:
        print("  referees with 20+ games: %d; minors a game from %.2f (%s, %d games) to %.2f (%s, %d games); league %.2f" % (
            len(ref_rows), ref_rows[0][0], ref_rows[0][2], ref_rows[0][1], ref_rows[-1][0], ref_rows[-1][2], ref_rows[-1][1], tot_minors / n))
        # the reliability of a referee's rate: first half of his games vs second
        halves = []
        for k, v in crews.items():
            pass
    club_rows = sorted(((v[1] / v[0], v[2] / v[0], k) for k, v in clubs.items()), reverse=True)
    print("  clubs: minors taken a game from %.2f (%s) to %.2f (%s); drawn from %.2f to %.2f" % (
        club_rows[0][0], club_rows[0][2], club_rows[-1][0], club_rows[-1][2], max(x[1] for x in club_rows), min(x[1] for x in club_rows)))

    # ---- 3. score effects at 5v5 ----
    print("\n== 3. score effects at 5 on 5 in regulation: the shooting side's shots per 60 and quality by its margin, against level ==")
    sc = collections.defaultdict(lambda: [0, 0.0, 0])
    for g in joined:
        for s in g["shots"]:
            if s["st"] != "5v5" or s["p"] > 3:
                continue
            m = (s["hg"] - s["ag"]) if s["home"] else (s["ag"] - s["hg"])
            m = max(-3, min(3, m))
            d = sc[m]; d[0] += 1; d[1] += s["xg"]; d[2] += s["goal"]
    base_rate = sc[0][0] / times_m[0] * 3600
    base_q = sc[0][2] / sc[0][0]
    base_xg = sc[0][1] / sc[0][0]
    score_rate, score_q = {}, {}
    for m in sorted(sc):
        d = sc[m]
        rate = d[0] / times_m[m] * 3600
        score_rate[m] = rate / base_rate
        score_q[m] = (d[1] / d[0]) / base_xg
        print("  margin %+d: %6.1f shots per 60 (x%.3f), xG per shot %.4f (x%.3f), goals per shot %.4f (x%.3f), over %.0f minutes" % (
            m, rate, rate / base_rate, d[1] / d[0], (d[1] / d[0]) / base_xg, d[2] / d[0], (d[2] / d[0]) / base_q, times_m[m] / 60))

    # ---- 4. period effects at 5v5 ----
    print("\n== 4. the period at 5 on 5: shots per 60 and quality by period against the game ==")
    pp_ = collections.defaultdict(lambda: [0, 0.0, 0])
    for g in joined:
        for s in g["shots"]:
            if s["st"] != "5v5" or s["p"] > 3:
                continue
            d = pp_[s["p"]]; d[0] += 1; d[1] += s["xg"]; d[2] += s["goal"]
    all_rate = sum(pp_[p][0] for p in (1, 2, 3)) / (times["5v5"] / 2) * 3600
    all_xg = sum(pp_[p][1] for p in (1, 2, 3)) / sum(pp_[p][0] for p in (1, 2, 3))
    all_fin = sum(pp_[p][2] for p in (1, 2, 3)) / sum(pp_[p][1] for p in (1, 2, 3))
    period_rate, period_q, period_fin = [], [], []
    for p in (1, 2, 3):
        d = pp_[p]
        secs = times_p[(p, "5v5")] / 2
        rate = d[0] / secs * 3600
        period_rate.append(rate / all_rate)
        period_q.append((d[1] / d[0]) / all_xg)
        period_fin.append((d[2] / d[1]) / all_fin)
        print("  period %d: %6.1f shots per 60 both sides (x%.3f), xG per shot %.4f (x%.3f), goals per shot %.4f, goals per xG %.3f (x%.3f); 5v5 time %.1f min a game" % (
            p, rate, rate / all_rate, d[1] / d[0], (d[1] / d[0]) / all_xg, d[2] / d[0], d[2] / d[1], (d[2] / d[1]) / all_fin, secs / n / 60))
    # the same finishing-by-period on every state (the power play included), for the sim's period multiplier
    pf_all = collections.defaultdict(lambda: [0.0, 0])
    for g in joined:
        for s in g["shots"]:
            if s["p"] <= 3 and s["st"] not in ("EN", "EXTRA"):
                d = pf_all[s["p"]]; d[0] += s["xg"]; d[1] += s["goal"]
    fin_all = sum(pf_all[p][1] for p in (1, 2, 3)) / sum(pf_all[p][0] for p in (1, 2, 3))
    period_fin_all = [(pf_all[p][1] / pf_all[p][0]) / fin_all for p in (1, 2, 3)]
    print("  goals per expected goal by period, every state but the empty net: %s (the first period's shots go in less often than their quality says)" % ", ".join("x%.3f" % x for x in period_fin_all))
    # the first period's whole: goals a game and the share, for the calibration check
    p1g = [sum(1 for s in g["shots"] if s["goal"] and s["p"] == 1) for g in joined]
    regg = [sum(1 for s in g["shots"] if s["goal"] and s["p"] <= 3) for g in joined]
    print("  first-period goals a game %.3f (sd %.3f), %s of regulation goals; regulation goals %.3f" % (statistics.mean(p1g), statistics.pstdev(p1g), pct(sum(p1g) / sum(regg)), statistics.mean(regg)))

    # ---- 5. home ice ----
    print("\n== 5. home ice at 5 on 5: the home side against the away side ==")
    hm = {True: [0, 0.0, 0], False: [0, 0.0, 0]}
    for g in joined:
        for s in g["shots"]:
            if s["st"] == "5v5" and s["p"] <= 3:
                d = hm[s["home"]]; d[0] += 1; d[1] += s["xg"]; d[2] += s["goal"]
    hr = hm[True][0] / float(hm[False][0])
    hq = (hm[True][1] / hm[True][0]) / (hm[False][1] / hm[False][0])
    hgq = (hm[True][2] / hm[True][0]) / (hm[False][2] / hm[False][0])
    print("  shots x%.3f, xG per shot x%.3f, goals per shot x%.3f (the home side's over the away side's); as multipliers on one side: rate %.3f, quality %.3f" % (
        hr, hq, hgq, math.sqrt(hr), math.sqrt(hq)))

    # ---- 6. the empty net ----
    print("\n== 6. the empty net in the third: the pull by the deficit (the first empty-net shot's time), the empty net's rates ==")
    pulls = collections.defaultdict(list)
    pull_games = collections.defaultdict(int)
    chances = collections.defaultdict(int)     # deficit -> games where the trailer was at that deficit inside the last 6 minutes (the chance to pull)
    en_shots = [0, 0.0, 0]
    extra_shots = [0, 0.0, 0]
    empty_secs = 0.0
    for g in joined:
        first = None
        for s in g["shots"]:
            if s["p"] != 3:
                continue
            if s["he"] or s["ae"]:
                if first is None:
                    first = s
                    pulled_home = s["he"]
                    deficit = (s["ag"] - s["hg"]) if pulled_home else (s["hg"] - s["ag"])
                    if 1 <= deficit <= 3:
                        pulls[deficit].append(3600 - s["t"])
                        pull_games[deficit] += 1
                if s["st"] == "EN":
                    en_shots[0] += 1; en_shots[1] += s["xg"]; en_shots[2] += s["goal"]
                elif s["st"] == "EXTRA":
                    extra_shots[0] += 1; extra_shots[1] += s["xg"]; extra_shots[2] += s["goal"]
        if first is not None:
            # the empty time, approximately: from the first empty-net shot to the end of regulation, or to the empty-net goal that
            # settled it (a lower bound: the pull itself came a little before the first shot)
            en_goal = [s for s in g["shots"] if s["p"] == 3 and s["st"] == "EN" and s["goal"]]
            stop = 3600 - en_goal[0]["t"] if en_goal else 0
            empty_secs += max(5.0, (3600 - first["t"]) - stop)
        # the chance to pull: the trailer's deficit with six minutes left in a game not yet decided
        sc3 = None
        for s in g["shots"]:
            if s["p"] == 3 and s["t"] >= 3240:
                sc3 = s
                break
        if sc3 is not None:
            d = abs(sc3["hg"] - sc3["ag"])
            if 1 <= d <= 3:
                chances[d] += 1
    pull_cfg = {}
    for d in (1, 2, 3):
        xs = sorted(pulls[d])
        if not xs:
            continue
        q = [xs[int(len(xs) * f)] for f in (0.10, 0.25, 0.50, 0.75, 0.90)]
        share = min(1.0, len(xs) / float(chances[d])) if chances[d] else float("nan")
        pull_cfg[d] = {"p": round(share, 2), "q": q}
        print("  down %d: the net first empties with %d s left on average (quantiles 10/25/50/75/90: %s) in %d games; pulled in %s of the %d games at that deficit with six minutes left" % (
            d, statistics.mean(xs), "/".join(str(x) for x in q), len(xs), pct(share), chances[d]))
    pg = sum(pull_games.values())
    print("  with the net empty: the leader's shots at it %d (%.3f a pull, %.3f goals per shot), the trailer's six-on-five shots %d (%.3f a pull, goals per shot %.4f); empty time about %.0f s a pull" % (
        en_shots[0], en_shots[0] / pg, en_shots[2] / en_shots[0], extra_shots[0], extra_shots[0] / pg, extra_shots[2] / extra_shots[0], empty_secs / pg))
    en60 = en_shots[0] / empty_secs * 3600
    extra60 = extra_shots[0] / empty_secs * 3600
    print("  per 60 of empty time: the leader %.1f shots at the empty net, the trailer %.1f six on five (the empty time is a lower bound, so these run high; the sim's empty-net goals are checked against %.3f a game)" % (
        en60, extra60, sum(1 for g in joined for s in g["shots"] if s["goal"] and s["st"] == "EN") / n))

    # ---- 7. overtime ----
    print("\n== 7. overtime: three on three, the shootout ==")
    ot_g = sum(1 for g in joined if g["pbp"]["end"] in ("OT", "SO"))
    so_g = sum(1 for g in joined if g["pbp"]["end"] == "SO")
    ot = by_st["33"]
    print("  to overtime %s of games, the shootout %s; 3v3 shots %.1f per 60 (one side), goals per shot %.4f; the home side won %s of shootouts" % (
        pct(ot_g / n), pct(so_g / n), ot[0] / ot_secs * 3600 / 2, ot[2] / ot[0], pct(sum(1 for g in joined if g["pbp"]["end"] == "SO" and g["led"]["fh"] > g["led"]["fa"]) / float(so_g)) if so_g else "-"))

    # ---- 8. goalies ----
    print("\n== 8. goalies: goals allowed against expected, and how much of a goalie's figure to believe ==")
    gk = collections.defaultdict(lambda: {"n": 0, "xg": 0.0, "g": 0, "name": "", "halves": [[0, 0.0, 0], [0, 0.0, 0]], "season": collections.defaultdict(lambda: [0, 0.0, 0])})
    for g in joined:
        half = 0 if (int(g["gid"]) - 20000) < 650 else 1
        for s in g["shots"]:
            if s["st"] == "EN" or not s["gk"] or s["p"] > 4:
                continue
            e = gk[s["gk"]]
            e["n"] += 1; e["xg"] += s["xg"]; e["g"] += s["goal"]; e["name"] = s["gkn"] or e["name"]
            h = e["halves"][half]; h[0] += 1; h[1] += s["xg"]; h[2] += s["goal"]
            ss = e["season"][g["season"]]; ss[0] += 1; ss[1] += s["xg"]; ss[2] += s["goal"]
    rows = [(e["g"] / e["xg"], e["n"], e["name"]) for e in gk.values() if e["xg"] >= 60]
    rows.sort()
    print("  %d goalies with 60+ xG faced: goals against expected from %.3f (%s) to %.3f (%s); sd across them %.3f" % (
        len(rows), rows[0][0], rows[0][2], rows[-1][0], rows[-1][2], statistics.pstdev([r[0] for r in rows])))
    xs, ys = [], []
    for e in gk.values():
        h0, h1 = e["halves"]
        if h0[1] >= 30 and h1[1] >= 30:
            xs.append(h0[2] / h0[1]); ys.append(h1[2] / h1[1])
    r = corr(xs, ys)
    mean_xg = statistics.mean([(e["halves"][0][1] + e["halves"][1][1]) / 2 for e in gk.values() if e["halves"][0][1] >= 30 and e["halves"][1][1] >= 30])
    print("  half to half (30+ xG each half, %d goalies): r %.2f at %.0f xG a half; K = xG (1 - r) / r = %.0f xG" % (len(xs), r, mean_xg, mean_xg * (1 - r) / r if r > 0 else float("nan")))
    xs2, ys2 = [], []
    seasons = sorted(set(g["season"] for g in joined))
    if len(seasons) >= 2:
        for e in gk.values():
            s0, s1 = e["season"].get(seasons[0]), e["season"].get(seasons[1])
            if s0 and s1 and s0[1] >= 40 and s1[1] >= 40:
                xs2.append(s0[2] / s0[1]); ys2.append(s1[2] / s1[1])
        r2 = corr(xs2, ys2)
        mx = statistics.mean([e["season"][seasons[0]][1] for e in gk.values() if e["season"].get(seasons[0]) and e["season"][seasons[0]][1] >= 40 and e["season"].get(seasons[1]) and e["season"][seasons[1]][1] >= 40])
        print("  season to season (40+ xG each, %d goalies): r %.2f at %.0f xG a season; K %.0f xG" % (len(xs2), r2, mx, mx * (1 - r2) / r2 if r2 > 0 else float("nan")))

    # ---- 9. the club figures' reliability ----
    print("\n== 9. the clubs' figures, first half of a season to the second (per 60 of state time): r and K = n (1 - r) / r at the half's games ==")
    acc = collections.defaultdict(lambda: [nhlsim._new_acc(), nhlsim._new_acc()])
    tal_by_game = {}
    for g in joined:
        half = 0 if (int(g["gid"]) - 20000) < 650 else 1
        tal = tallies_of(g)
        st = nhlsim.state_times(g["pbp"]["plays"])
        mn = nhlsim.minors_taken(g["pbp"]["plays"])
        for side in ("away", "home"):
            nhlsim._acc_game(acc[(g["season"], g[side])][half], tal, side, st, mn)
    lgp = dict(nhlsim.LEAGUE)
    lgp.update({"t55": t55, "tpp": tpp, "xg5": league["5v5"]["xg"], "xgpp": league["PP"]["xg"], "pen_game": tot_minors / 2 / n, "sf60": league["5v5"]["per60"], "pp60": league["PP"]["per60"]})
    ks = {}
    for key in nhlsim.PROFILE_KEYS:
        xs, ys, ns = [], [], []
        for (season, ab), halves in acc.items():
            p0, p1 = nhlsim._profile_of(halves[0], lgp), nhlsim._profile_of(halves[1], lgp)
            if p0 and p1 and halves[0]["n"] >= 25 and halves[1]["n"] >= 25:
                xs.append(p0[key]); ys.append(p1[key]); ns.append(halves[0]["n"])
        r = corr(xs, ys)
        nbar = statistics.mean(ns) if ns else 0
        k = nbar * (1 - r) / r if r > 0.05 else 400.0
        ks[key] = round(min(400.0, k), 1)
        print("  %-6s r %.2f on %d club-halves at %.0f games: K %.0f (sd of the figure %.3f)" % (key, r, len(xs), nbar, ks[key], statistics.pstdev(xs) if len(xs) > 1 else 0))

    # ---- 10. LEAGUE as nhlsim would carry it, and nhl-tend.json ----
    out_league = {
        "sf60": round(league["5v5"]["per60"], 2), "q5": round(league["5v5"]["q"], 4),
        "pp60": round(league["PP"]["per60"], 2), "qpp": round(league["PP"]["q"], 4),
        "pk60": round(league["PK"]["per60"], 2), "qpk": round(league["PK"]["q"], 4),
        "two_man": round(league["PP2"]["per60"] / league["PP"]["per60"], 3), "two_man_q": round(league["PP2"]["q"] / league["PP"]["q"], 3),
        "s44": round(league["44"]["per60"], 2), "q44": round(league["44"]["q"], 4),
        "s33": round(ot[0] / ot_secs * 3600 / 2, 2), "q33": round(ot[2] / ot[0], 4),
        "pen60": round(tot_minors / 2 / n, 3), "pen_period": [round(x, 3) for x in per_mult], "double_share": round(doubles / tot_minors, 3),
        "score_rate": {m: round(v, 3) for m, v in score_rate.items()}, "score_q": {m: round(v, 3) for m, v in score_q.items()},
        "period_rate": [round(x, 3) for x in period_rate], "period_q": [round(x, 3) for x in period_q], "period_fin": [round(x, 3) for x in period_fin_all],
        "home_rate": round(math.sqrt(hr), 3), "home_q": round(math.sqrt(hq), 3),
        "pull": pull_cfg, "en60": round(en60, 1), "q_en": round(en_shots[2] / en_shots[0], 3), "extra60": round(extra60, 1), "q_extra": round(extra_shots[2] / extra_shots[0], 4),
        "so_home": round(sum(1 for g in joined if g["pbp"]["end"] == "SO" and g["led"]["fh"] > g["led"]["fa"]) / float(so_g), 3) if so_g else 0.5,
        "t55": round(t55, 1), "tpp": round(tpp, 1), "xg5": round(league["5v5"]["xg"], 4), "xgpp": round(league["PP"]["xg"], 4), "pen_game": round(tot_minors / 2 / n, 3),
    }
    print("\n== 10. nhlsim.LEAGUE, measured ==")
    print(json.dumps(out_league, indent=1, sort_keys=True))
    print("K =", json.dumps(ks, sort_keys=True))
    if a.out:
        doc = {"format": "callsheet3.nhl-tend", "version": 1, "games": len(joined), "seasons": seasons, "league": out_league, "K": ks,
               "refs": {k: {"games": v[0], "minors": round(v[1] / v[0], 3)} for k, v in crews.items() if v[0] >= 5},
               "league_minors": round(tot_minors / n, 3),
               "clubs": {k: {"games": v[0], "taken": round(v[1] / v[0], 3), "drawn": round(v[2] / v[0], 3)} for k, v in clubs.items()}}
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1, sort_keys=True)
        print("wrote %s" % a.out)
    return 0


def tallies_of(g):
    """One joined game's shots to the per-game tallies shots_tallies() builds (the same shape)."""
    out = {"home": g["home"], "away": g["away"], "last": 1, "for": {"home": {}, "away": {}}, "p1": {"home": [[0, 0.0, 0], [0, 0.0, 0]], "away": [[0, 0.0, 0], [0, 0.0, 0]]}, "goalies": {"home": [], "away": []}}
    for s in g["shots"]:
        side, other = ("home", "away") if s["home"] else ("away", "home")
        out["last"] = max(out["last"], s["p"])
        d = out["for"][side].setdefault(s["st"], [0, 0.0, 0])
        d[0] += 1; d[1] += s["xg"]; d[2] += 1 if s["goal"] else 0
        if s["p"] == 1:
            p = out["p1"][side]
            p[0][0] += 1; p[0][1] += s["xg"]; p[0][2] += 1 if s["goal"] else 0
            if s["st"] == "5v5":
                p[1][0] += 1; p[1][1] += s["xg"]; p[1][2] += 1 if s["goal"] else 0
        if s["st"] != "EN" and s["p"] <= 4 and s["gk"]:
            lst = out["goalies"][other]
            e = None
            for x in lst:
                if x[0] == s["gk"]:
                    e = x
                    break
            if e is None:
                e = [s["gk"], s["gkn"], 0, 0.0, 0]
                lst.append(e)
            e[2] += 1; e[3] += s["xg"]; e[4] += 1 if s["goal"] else 0
    return out


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
