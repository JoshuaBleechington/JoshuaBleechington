"""Tendencies from the NBA play-by-play, for the simulation (25 Oct 2026).

    python3 tools_nba_tendencies.py nba-pbp-202526.json nba-ledger-202526.json [more pbp/ledger pairs...] [--out nba-tend.json]

From every game's plays: possessions and points per possession by quarter;
the fourth quarter by the margin at its start (garbage time, close games);
the points inside the last minute by the margin at that moment (the fouling
end); the league's and each club's shot mix (threes, twos, trips to the line,
turnovers, offensive rebounds); the starters' share of each quarter's minutes
for the league and each club, and in the fourth by the margin; each club's
timeouts; each player's fouls by quarter and how often he picks up two in the
first, with the minutes that costs. Written compact for nbasim to read.
"""
import json
import os
import sys
from collections import defaultdict

PACE_FT = 0.44
FOUL_CODES = ("PF", "SF", "LF", "OF", "TK", "FF", "XF")


def load_pairs(argv):
    pairs, out = [], "nba-tend.json"
    i = 0
    while i < len(argv):
        if argv[i] == "--out":
            out = argv[i + 1]; i += 2; continue
        pairs.append((argv[i], argv[i + 1] if i + 1 < len(argv) else None)); i += 2
    return pairs, out


def starters_of(ledger_game, side):
    key = "pa" if side == 0 else "ph"
    return [str(p[0]) for p in (ledger_game.get(key) or []) if len(p) > 2 and p[2]]


def margin_bucket(m):
    m = abs(m)
    return "0-5" if m <= 5 else "6-10" if m <= 10 else "11-15" if m <= 15 else "16-20" if m <= 20 else "21+"


def analyse(pbp_games, ledger_by_id):
    L = {"games": 0, "q_poss": [0.0] * 4, "q_pts": [0] * 4, "fga": 0, "tpa": 0, "tpm": 0, "fgm2": 0, "fga2": 0, "ft": 0, "ftm": 0, "tov": 0, "oreb": 0, "poss": 0.0,
         "q4_margin": defaultdict(lambda: {"n": 0, "poss": 0.0, "pts": 0}), "end60": defaultdict(lambda: {"n": 0, "pts": 0, "poss": 0.0}),
         "starters_q": [0.0] * 4, "starters_q4_margin": defaultdict(lambda: {"n": 0, "share": 0.0}), "timeouts_q": [0] * 4,
         "first_sub": [], "ot": 0}
    T = defaultdict(lambda: {"games": 0, "fga": 0, "tpa": 0, "tpm": 0, "fgm2": 0, "fga2": 0, "ft": 0, "ftm": 0, "tov": 0, "oreb": 0, "poss": 0.0, "pts": 0,
                             "starters_q": [0.0] * 4, "timeouts": 0, "players": 0})
    P = defaultdict(lambda: {"n": 0, "pf": 0, "q1": 0, "two_q1": 0, "three_h1": 0, "min": 0.0, "min_two": 0.0, "n_two": 0, "name": ""})
    for g in pbp_games:
        plays = g.get("plays") or []
        if len(plays) < 100:
            continue
        lg = ledger_by_id.get(g["id"])
        sides = [g.get("away"), g.get("home")]
        if not lg or not sides[0] or not sides[1]:
            continue
        L["games"] += 1
        if g.get("ot"):
            L["ot"] += 1
        # per quarter, per side: attempts, rebounds, turnovers, free throws, points
        qstat = [[{"fga": 0, "tpa": 0, "tpm": 0, "fgm2": 0, "fga2": 0, "ft": 0, "ftm": 0, "tov": 0, "oreb": 0, "pts": 0} for _ in range(4)] for _ in range(2)]
        fouls = defaultdict(lambda: [0, 0, 0, 0])      # pid -> fouls by quarter
        starters = [starters_of(lg, 0), starters_of(lg, 1)]
        floor = [set(starters[0]), set(starters[1])]
        on_time = [[0.0] * 4, [0.0] * 4]               # starter-seconds by quarter, each side
        q4_by_margin_time = [0.0, 0.0]
        prev_clock, prev_period = 720.0, 1
        q_start_margin = [0, 0, 0, 0]
        end_window = {}                                 # period 4: the margin when the clock first hit 60
        first_sub = [None, None]
        tos = [[0] * 4, [0] * 4]
        used = [set(starters[0]), set(starters[1])]
        for pl in plays:
            period, clock, code, side, pids, aw, hm, pts = pl
            if period < 1 or period > 4 or clock is None:
                continue
            q = period - 1
            if period != prev_period:
                prev_clock, prev_period = 720.0, period
                q_start_margin[q] = hm - aw
            elapsed = max(0.0, prev_clock - clock)
            for s in (0, 1):
                on_time[s][q] += elapsed * len(floor[s] & set(starters[s]))
            prev_clock = clock
            if period == 4 and clock <= 60.0 and "m" not in end_window:
                end_window["m"] = hm - aw
                end_window["pts_at"] = aw + hm
            if side in (0, 1):
                st = qstat[side][q]
                if code == "M":
                    st["fga"] += 1
                    if pts == 3:
                        st["tpa"] += 1; st["tpm"] += 1
                    else:
                        st["fga2"] += 1; st["fgm2"] += 1
                    st["pts"] += pts
                elif code == "X":
                    st["fga"] += 1
                    if pts == 3:
                        st["tpa"] += 1
                    else:
                        st["fga2"] += 1
                elif code == "FT":
                    st["ft"] += 1
                    st["ftm"] += 1 if pts else 0
                    st["pts"] += pts
                elif code == "TV":
                    st["tov"] += 1
                elif code == "OR":
                    st["oreb"] += 1
                elif code == "T":
                    tos[side][q] += 1
                elif code == "S" and len(pids) >= 2:
                    pin, pout = pids[0], pids[1]
                    floor[side].discard(pout)
                    floor[side].add(pin)
                    used[side].add(pin)
                    if first_sub[side] is None and q == 0:
                        first_sub[side] = 720.0 - clock
                elif code in FOUL_CODES and pids:
                    fouls[pids[0]][q] += 1
        # tally the game
        for s in (0, 1):
            ab = sides[s]
            T[ab]["games"] += 1
            T[ab]["timeouts"] += sum(tos[s])
            T[ab]["players"] += len(used[s])
            for q in range(4):
                st = qstat[s][q]
                poss = st["fga"] - st["oreb"] + st["tov"] + PACE_FT * st["ft"]
                L["q_poss"][q] += poss
                L["q_pts"][q] += st["pts"]
                for k in ("fga", "tpa", "tpm", "fgm2", "fga2", "ft", "ftm", "tov", "oreb"):
                    L[k] += st[k]; T[ab][k] += st[k]
                L["poss"] += poss; T[ab]["poss"] += poss; T[ab]["pts"] += st["pts"]
                share = on_time[s][q] / (5.0 * 720.0)
                L["starters_q"][q] += share
                T[ab]["starters_q"][q] += share
                if q == 3:
                    b = margin_bucket(q_start_margin[3])
                    d = L["q4_margin"][b]
                    d["n"] += 1; d["poss"] += poss; d["pts"] += st["pts"]
                    e = L["starters_q4_margin"][b]
                    e["n"] += 1; e["share"] += share
            if first_sub[s] is not None:
                L["first_sub"].append(first_sub[s])
            for q in range(4):
                L["timeouts_q"][q] += tos[s][q]
        if "m" in end_window:
            b = "within9" if 1 <= abs(end_window["m"]) <= 9 else ("level" if end_window["m"] == 0 else "out")
            d = L["end60"][b]
            d["n"] += 1
            d["pts"] += (g.get("fa") or 0) + (g.get("fh") or 0) - end_window["pts_at"] if not g.get("ot") else 0
        # players' fouls and minutes
        mins = {}
        for key in ("pa", "ph"):
            for p in lg.get(key) or []:
                mins[str(p[0])] = (float(p[3]) if len(p) > 3 else 0.0, p[1] if len(p) > 1 else "")
        for pid, fq in fouls.items():
            d = P[pid]
            d["n"] += 1
            d["pf"] += sum(fq)
            d["q1"] += fq[0]
            m, name = mins.get(pid, (0.0, ""))
            d["name"] = d["name"] or name
            d["min"] += m
            if fq[0] >= 2:
                d["two_q1"] += 1; d["min_two"] += m; d["n_two"] += 1
            if fq[0] + fq[1] >= 3:
                d["three_h1"] += 1
    return L, T, P


def finish(L, T, P):
    n = float(L["games"]) or 1.0
    poss = L["poss"] or 1.0
    out = {"format": "callsheet3.nba-tend", "version": 1, "games": L["games"],
           "league": {"q_poss": [round(x / sum(L["q_poss"]), 4) for x in L["q_poss"]] if sum(L["q_poss"]) else None,
                      "q_ppp": [round(L["q_pts"][q] / L["q_poss"][q], 4) if L["q_poss"][q] else None for q in range(4)],
                      "poss_per_team_game": round(poss / (2 * n), 2), "ppp": round(sum(L["q_pts"]) / poss, 4),
                      "a3": round(L["tpa"] / float(L["fga"]), 4) if L["fga"] else None, "p3": round(L["tpm"] / float(L["tpa"]), 4) if L["tpa"] else None,
                      "p2": round(L["fgm2"] / float(L["fga2"]), 4) if L["fga2"] else None, "ft": round(L["ftm"] / float(L["ft"]), 4) if L["ft"] else None,
                      "trip": round(PACE_FT * L["ft"] / poss, 4), "tov": round(L["tov"] / poss, 4),
                      "oreb": round(L["oreb"] / float(L["fga"] - L["tpm"] - L["fgm2"]), 4) if L["fga"] else None,
                      "starters_q": [round(x / (2 * n), 4) for x in L["starters_q"]],
                      "starters_q4_by_margin": {b: round(d["share"] / d["n"], 4) for b, d in L["starters_q4_margin"].items() if d["n"]},
                      "q4_by_margin": {b: {"n": d["n"], "poss": round(d["poss"] / d["n"], 2), "ppp": round(d["pts"] / d["poss"], 4) if d["poss"] else None} for b, d in L["q4_margin"].items() if d["n"]},
                      "last_minute_pts": {b: {"n": d["n"], "pts": round(d["pts"] / float(d["n"]), 2)} for b, d in L["end60"].items() if d["n"]},
                      "timeouts_q": [round(x / (2 * n), 2) for x in L["timeouts_q"]],
                      "first_sub_secs": round(sum(L["first_sub"]) / len(L["first_sub"]), 1) if L["first_sub"] else None,
                      "ot_rate": round(L["ot"] / n, 4)},
           "teams": {}, "players": {}}
    for ab, t in sorted(T.items()):
        g = float(t["games"]) or 1.0
        tp = t["poss"] or 1.0
        out["teams"][ab] = {"games": t["games"], "a3": round(t["tpa"] / float(t["fga"]), 4) if t["fga"] else None, "p3": round(t["tpm"] / float(t["tpa"]), 4) if t["tpa"] else None,
                            "p2": round(t["fgm2"] / float(t["fga2"]), 4) if t["fga2"] else None, "ft": round(t["ftm"] / float(t["ft"]), 4) if t["ft"] else None,
                            "trip": round(PACE_FT * t["ft"] / tp, 4), "tov": round(t["tov"] / tp, 4),
                            "oreb": round(t["oreb"] / float(t["fga"] - t["tpm"] - t["fgm2"]), 4) if t["fga"] else None,
                            "starters_q": [round(x / g, 4) for x in t["starters_q"]], "timeouts": round(t["timeouts"] / g, 2), "players_used": round(t["players"] / g, 2)}
    two_min, two_n, all_min, all_n = 0.0, 0, 0.0, 0
    for pid, d in P.items():
        if d["n"] < 5:
            continue
        out["players"][pid] = {"name": d["name"], "n": d["n"], "pf": round(d["pf"] / float(d["n"]), 2), "two_q1": round(d["two_q1"] / float(d["n"]), 3),
                               "three_h1": round(d["three_h1"] / float(d["n"]), 3), "min": round(d["min"] / float(d["n"]), 1),
                               "min_two": round(d["min_two"] / float(d["n_two"]), 1) if d["n_two"] else None}
        if d["min"] / d["n"] >= 24 and d["n_two"]:
            two_min += d["min_two"]; two_n += d["n_two"]; all_min += d["min"]; all_n += d["n"]
    out["league"]["foul_trouble"] = {"regulars_two_q1_rate": round(sum(d["two_q1"] for d in P.values() if d["n"] >= 5 and d["min"] / d["n"] >= 24) / float(sum(d["n"] for d in P.values() if d["n"] >= 5 and d["min"] / d["n"] >= 24) or 1), 4),
                                     "minutes_with_two_q1": round(two_min / two_n, 1) if two_n else None, "minutes_usual": round(all_min / all_n, 1) if all_n else None}
    return out


def main(argv):
    pairs, out = load_pairs(argv)
    if not pairs:
        print(__doc__); return 2
    L = T = P = None
    games, ledger = [], {}
    for pbp_f, led_f in pairs:
        d = json.load(open(pbp_f))
        games.extend(d.get("games") or [])
        if led_f and os.path.exists(led_f):
            for g in json.load(open(led_f)).get("games") or []:
                ledger[str(g.get("id"))] = g
        print("%s: %d games; ledger %s" % (pbp_f, len(d.get("games") or []), led_f))
    L, T, P = analyse(games, ledger)
    doc = finish(L, T, P)
    with open(out, "w") as f:
        json.dump(doc, f, separators=(",", ":"))
    lg = doc["league"]
    print("games %d" % doc["games"])
    print("possessions by quarter %s; points per possession %s" % (lg["q_poss"], lg["q_ppp"]))
    print("shot mix: a3 %s p3 %s p2 %s ft %s trip %s tov %s oreb %s; %s possessions a team-game" % (lg["a3"], lg["p3"], lg["p2"], lg["ft"], lg["trip"], lg["tov"], lg["oreb"], lg["poss_per_team_game"]))
    print("starters' share by quarter %s; in the fourth by margin at its start %s" % (lg["starters_q"], lg["starters_q4_by_margin"]))
    print("fourth quarter by margin at its start: %s" % json.dumps(lg["q4_by_margin"]))
    print("points in the last minute by the margin then: %s" % json.dumps(lg["last_minute_pts"]))
    print("timeouts a team by quarter %s; first sub after %s s; foul trouble %s" % (lg["timeouts_q"], lg["first_sub_secs"], json.dumps(lg["foul_trouble"])))
    print("wrote %s (%d teams, %d players)" % (out, len(doc["teams"]), len(doc["players"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
