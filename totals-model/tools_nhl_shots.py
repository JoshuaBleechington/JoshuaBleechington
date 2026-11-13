#!/usr/bin/env python3
"""What the hockey simulation needs from MoneyPuck's shot files (29 Oct 2026,
the user: "a simulation for the NHL model too, same set up as the NBA one,
focused on total goals, first-period totals and full-game totals"). Every
unblocked shot of a season with its period, clock, the skaters on the ice,
the empty net, the score at the time, the shooter, the goalie and its
expected-goal value (data: MoneyPuck.com).

Measured, regular season only:

  1. shots (unblocked attempts) per 60 and expected goals per shot by the
     strength state: 5 on 5, the power play and the kill (5v4, 4v5, 5v3,
     3v5, 4v4), 3 on 3 overtime, the empty net both ways;
  2. by period: the share of the game's shots and goals in each, and the
     first period's rates;
  3. score effects at 5 on 5: shots per 60 and xG per shot by the margin;
  4. the goalie pull: when the net empties by the deficit, how long it stays
     empty, what lands in it and what the trailing side scores with the
     extra man;
  5. goals against expected: the league's shooting on the xG scale, by state;
  6. the spread: goals a game against Poisson, by period, and how often a
     game goes to overtime and the shootout (the shootout adds a goal to the
     official score that the full-game total carries);
  7. the team spread: how far the clubs' 5v5 shot rates and xG quality sit
     from the league, the inputs the profiles will carry.

    python3 tools_nhl_shots.py shots_2024.csv shots_2025.csv [shots_2026.csv]
"""
from __future__ import annotations

import collections
import csv
import math
import statistics
import sys


def state_of(hs, as_, home_empty, away_empty, is_home):
    """The strength state from the shooting side's view: '5v5', 'PP' (more skaters), 'PK', '4v4', '3v3', 'EN' (shooting at an empty net), 'EXTRA' (the shooting side's net is empty, the extra attacker on)."""
    mine, theirs = (hs, as_) if is_home else (as_, hs)
    my_empty, their_empty = (home_empty, away_empty) if is_home else (away_empty, home_empty)
    if their_empty:
        return "EN"
    if my_empty:
        return "EXTRA"
    if mine == theirs:
        return {5: "5v5", 4: "4v4", 3: "3v3"}.get(mine, "%dv%d" % (mine, theirs))
    return "PP" if mine > theirs else "PK"


def load(files):
    games = {}
    for f in files:
        with open(f, newline="", encoding="utf-8", errors="replace") as fh:
            rd = csv.DictReader(fh)
            for r in rd:
                if r.get("isPlayoffGame") not in ("0", "0.0", ""):
                    continue
                gid = (r["season"], r["game_id"])
                g = games.setdefault(gid, {"season": r["season"], "home": r["homeTeamCode"], "away": r["awayTeamCode"], "shots": []})
                is_home = r["isHomeTeam"] in ("1", "1.0")
                hs, as_ = int(float(r["homeSkatersOnIce"] or 5)), int(float(r["awaySkatersOnIce"] or 5))
                he, ae = r.get("homeEmptyNet") in ("1", "1.0"), r.get("awayEmptyNet") in ("1", "1.0")
                g["shots"].append({
                    "p": int(r["period"]), "t": int(float(r["time"])), "ev": r["event"], "goal": r["goal"] in ("1", "1.0"), "xg": float(r["xGoal"] or 0),
                    "home": is_home, "st": state_of(hs, as_, he, ae, is_home), "hg": int(float(r["homeTeamGoals"])), "ag": int(float(r["awayTeamGoals"])),
                    "on": r.get("shotWasOnGoal") in ("1", "1.0"), "en": r.get("shotOnEmptyNet") in ("1", "1.0"), "goalie": r.get("goalieNameForShot") or "",
                    "hs": hs, "as": as_, "he": he, "ae": ae})
    for g in games.values():
        g["shots"].sort(key=lambda s: (s["p"], s["t"]))
    return games


def pct(x):
    return "%.1f%%" % (100 * x)


def main(argv):
    if not argv:
        print(__doc__); return 2
    games = load(argv)
    print("%d regular-season games with shots, seasons %s" % (len(games), sorted(set(g["season"] for g in games.values()))))
    # the final score of each game from the last shot's running score plus that shot's goal, and the end
    finals = {}
    for gid, g in games.items():
        hg = ag = 0; last_p = 1
        for s in g["shots"]:
            last_p = max(last_p, s["p"])
            if s["goal"]:
                if s["home"]: hg += 1
                else: ag += 1
        finals[gid] = (hg, ag, last_p)
    tot = [h + a for h, a, p in finals.values()]
    reg = [sum(1 for s in g["shots"] if s["goal"] and s["p"] <= 3) for g in games.values()]
    n = len(games)
    ot = sum(1 for h, a, p in finals.values() if p >= 4); so = sum(1 for h, a, p in finals.values() if p >= 5)
    print("\n== 6. goals a game (the shot files' goals; the shootout goal is NOT in these rows) ==")
    print("  goals a game %.3f (sd %.3f, Poisson would be %.3f); regulation goals %.3f; to overtime %s (the shootout is not in the shot file: the ledger says 7.5%% of games)" % (
        statistics.mean(tot), statistics.pstdev(tot), math.sqrt(statistics.mean(tot)), statistics.mean(reg), pct(ot / n)))
    # 2. by period
    print("\n== 2. by period: shots (unblocked), goals, xG; the share of regulation ==")
    per = collections.defaultdict(lambda: [0, 0, 0.0])
    for g in games.values():
        for s in g["shots"]:
            d = per[s["p"]]; d[0] += 1; d[1] += s["goal"]; d[2] += s["xg"]
    reg_goals = sum(per[p][1] for p in (1, 2, 3)); reg_shots = sum(per[p][0] for p in (1, 2, 3))
    for p in sorted(per):
        d = per[p]
        print("  period %d: %.2f shots a game, %.3f goals a game (%s of regulation goals; shots %s), xG per shot %.4f, goals per shot %.4f" % (
            p, d[0] / n, d[1] / n, pct(d[1] / reg_goals) if p <= 3 else "-", pct(d[0] / reg_shots) if p <= 3 else "-", d[2] / d[0], d[1] / d[0]))
    p1 = [sum(1 for s in g["shots"] if s["goal"] and s["p"] == 1) for g in games.values()]
    print("  first-period goals a game %.3f (sd %.3f, Poisson %.3f); P(0) %s, P(1) %s, P(2) %s, P(3+) %s" % (
        statistics.mean(p1), statistics.pstdev(p1), math.sqrt(statistics.mean(p1)), pct(p1.count(0) / n), pct(p1.count(1) / n), pct(p1.count(2) / n), pct(sum(1 for x in p1 if x >= 3) / n)))
    # 1. by strength state: time in each state is not in the shot file, so the rates are per game-share; the shares of shots and goals by state
    print("\n== 1. by strength state (the shooting side's view): share of shots, xG per shot, goals per shot ==")
    st = collections.defaultdict(lambda: [0, 0, 0.0, 0])
    for g in games.values():
        for s in g["shots"]:
            d = st[s["st"]]; d[0] += 1; d[1] += s["goal"]; d[2] += s["xg"]; d[3] += s["on"]
    allshots = sum(d[0] for d in st.values())
    for k in sorted(st, key=lambda k: -st[k][0]):
        d = st[k]
        print("  %-6s shots %s of all (%.2f a game), on goal %s, xG per shot %.4f, goals per shot %.4f, goals a game %.3f" % (k, pct(d[0] / allshots), d[0] / n, pct(d[3] / d[0]), d[2] / d[0], d[1] / d[0], d[1] / n))
    # 3. score effects at 5v5 by the shooting side's margin, regulation
    print("\n== 3. score effects at 5 on 5 in regulation: the shooting side's shots and xG by its margin (shots per game-period, both sides summed is the pace) ==")
    sc = collections.defaultdict(lambda: [0, 0.0, 0])
    for g in games.values():
        for s in g["shots"]:
            if s["st"] != "5v5" or s["p"] > 3:
                continue
            m = (s["hg"] - s["ag"]) if s["home"] else (s["ag"] - s["hg"])
            m = max(-3, min(3, m))
            d = sc[m]; d[0] += 1; d[1] += s["xg"]; d[2] += s["goal"]
    base = sc[0][0]
    for m in sorted(sc):
        d = sc[m]
        print("  margin %+d: shots %6d (%.2fx the tied count), xG per shot %.4f, goals per shot %.4f" % (m, d[0], d[0] / base, d[1] / d[0], d[2] / d[0]))
    # 4. the goalie pull: the first shot with a net empty in the third, by the trailing side's deficit; what happened after
    print("\n== 4. the empty net in the third period: when it opens by the deficit, and what lands ==")
    pulls = collections.defaultdict(list); en_goals = collections.defaultdict(lambda: [0, 0]); extra_goals = collections.defaultdict(lambda: [0, 0])
    for g in games.values():
        seen = None
        for s in g["shots"]:
            if s["p"] != 3:
                continue
            empty_home, empty_away = s["he"], s["ae"]
            if (empty_home or empty_away) and seen is None:
                trailing_home = empty_home
                deficit = (s["ag"] - s["hg"]) if trailing_home else (s["hg"] - s["ag"])
                seen = (deficit, s["t"])
                pulls[max(1, min(3, deficit))].append(3600 - s["t"])   # the clock counts seconds into the game
        hg = ag = 0
        for s in g["shots"]:
            if s["p"] == 3 and (s["he"] or s["ae"]):
                trailing_home = s["he"]
                deficit = max(1, min(3, (s["ag"] - s["hg"]) if trailing_home else (s["hg"] - s["ag"])))
                if s["st"] == "EN": en_goals[deficit][0] += s["goal"]; en_goals[deficit][1] += 1
                elif s["st"] == "EXTRA": extra_goals[deficit][0] += s["goal"]; extra_goals[deficit][1] += 1
    for dfc in sorted(pulls):
        xs = pulls[dfc]
        print("  down %d: the net first empties with %.0f seconds left on average (median %.0f) in %d games; shots at the empty net %d (%d goals), the extra man's shots %d (%d goals)" % (
            dfc, statistics.mean(xs), statistics.median(xs), len(xs), en_goals[dfc][1], en_goals[dfc][0], extra_goals[dfc][1], extra_goals[dfc][0]))
    eng = sum(1 for g in games.values() for s in g["shots"] if s["goal"] and s["st"] == "EN")
    print("  empty-net goals a game %.3f; games with one %s" % (eng / n, pct(sum(1 for g in games.values() if any(s["goal"] and s["st"] == "EN" for s in g["shots"])) / n)))
    # 5. goals against expected
    print("\n== 5. goals against expected goals, by state ==")
    for k in ("5v5", "PP", "PK", "4v4", "3v3", "EN", "EXTRA"):
        d = st.get(k)
        if d: print("  %-6s goals %d against xG %.1f: %.3f of expected" % (k, d[1], d[2], d[1] / d[2] if d[2] else 0))
    # 7. the team spread at 5v5: shots for per game and xG for per shot, by club-season
    print("\n== 7. the clubs at 5 on 5 (regulation): shots for a game and xG per shot for and against, the spread across clubs ==")
    club = collections.defaultdict(lambda: [0, 0, 0.0, 0.0, 0])   # (season, team) -> shots for, shots against, xG for, xG against, games
    for g in games.values():
        for side, ab in (("home", g["home"]), ("away", g["away"])):
            d = club[(g["season"], ab)]; d[4] += 1
            for s in g["shots"]:
                if s["st"] != "5v5" or s["p"] > 3: continue
                if (s["home"] and side == "home") or (not s["home"] and side == "away"): d[0] += 1; d[2] += s["xg"]
                else: d[1] += 1; d[3] += s["xg"]
    sf = [d[0] / d[4] for d in club.values()]; sa = [d[1] / d[4] for d in club.values()]; qf = [d[2] / d[0] for d in club.values()]; qa = [d[3] / d[1] for d in club.values()]
    print("  %d club-seasons: shots for a game %.2f (sd %.2f), against %.2f (sd %.2f); xG per shot for %.4f (sd %.4f), against %.4f (sd %.4f)" % (
        len(club), statistics.mean(sf), statistics.pstdev(sf), statistics.mean(sa), statistics.pstdev(sa), statistics.mean(qf), statistics.pstdev(qf), statistics.mean(qa), statistics.pstdev(qa)))
    # how much of a club's rate persists: first half of a season against the second (the profiles' worth)
    halves = collections.defaultdict(lambda: [[0, 0, 0.0, 0.0, 0], [0, 0, 0.0, 0.0, 0]])
    for gid, g in sorted(games.items(), key=lambda kv: int(kv[0][1])):
        half = 0 if (int(gid[1]) - 20000) < 650 else 1   # the season's first 650 games against the rest (game ids run 20001 up)
        for side, ab in (("home", g["home"]), ("away", g["away"])):
            d = halves[(g["season"], ab)][half]; d[4] += 1
            for s in g["shots"]:
                if s["st"] != "5v5" or s["p"] > 3: continue
                if (s["home"] and side == "home") or (not s["home"] and side == "away"): d[0] += 1; d[2] += s["xg"]
                else: d[1] += 1; d[3] += s["xg"]
    def corr(xs, ys):
        mx, my = statistics.mean(xs), statistics.mean(ys)
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys)); sxx = sum((x - mx) ** 2 for x in xs); syy = sum((y - my) ** 2 for y in ys)
        return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else 0.0
    pairs = [(a, b) for a, b in halves.values() if a[4] >= 20 and b[4] >= 20]
    print("  first half to second, across %d club-seasons: shots for a game r %.2f, shots against r %.2f, xG per shot for r %.2f, xG per shot against r %.2f, goals for a game r %.2f" % (
        len(pairs), corr([a[0] / a[4] for a, b in pairs], [b[0] / b[4] for a, b in pairs]), corr([a[1] / a[4] for a, b in pairs], [b[1] / b[4] for a, b in pairs]),
        corr([a[2] / a[0] for a, b in pairs], [b[2] / b[0] for a, b in pairs]), corr([a[3] / a[1] for a, b in pairs], [b[3] / b[1] for a, b in pairs]),
        corr([a[2] for a, b in pairs], [b[2] for a, b in pairs])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
