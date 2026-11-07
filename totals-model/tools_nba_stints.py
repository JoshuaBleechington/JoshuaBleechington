#!/usr/bin/env python3
"""Who was on the floor: five-man stints from the play-by-play (26 Oct 2026,
the user: "could the simulation test the starting lineups? we have the
individual players' info").

The ledger's box lines say who started; the play-by-play's substitutions
say who came in for whom ([entering, leaving]); the players a period's
plays name before they are subbed in say who began that period. From those
the game is cut into stints, each with the five a side, its seconds, the
points each side scored and its possessions (field goals attempted, turnovers
and 0.44 of the free throws, less the offensive rebounds). Every stint is
checked: five a side, and each man's stint minutes against his box minutes.

Usage: python3 tools_nba_stints.py PBP.json LEDGER.json OUT.json
"""
from __future__ import annotations

import json
import sys

PERIOD_SECS = {1: 720.0, 2: 720.0, 3: 720.0, 4: 720.0}
NON_FLOOR = ("S", "T", "TX", "E", "R", "J")   # plays whose participants need not be on the floor the way a shot's are


def starters(box_side):
    return [str(p[0]) for p in box_side if int(p[2] or 0) == 1][:5]


def period_starters(plays, side, prev_end, box_start, period):
    """The five who began a period: the first five of the side named by a play
    before their own sub-in, the men subbed OUT before any sub-in counting too;
    short of five, the previous period's finishers fill in."""
    if period == 1:
        return list(box_start)
    seen, subbed_in = [], set()
    for p in plays:
        if p[0] != period:
            continue
        code, s, pids = p[2], p[3], p[4]
        if code == "S" and s == side and len(pids) >= 2:
            out = str(pids[1]); inn = str(pids[0])
            if out not in subbed_in and out not in seen:
                seen.append(out)
            subbed_in.add(inn)
        elif code not in NON_FLOOR and s == side and pids:
            pid = str(pids[0])
            if pid not in subbed_in and pid not in seen:
                seen.append(pid)
        if len(seen) >= 5:
            break
    five = seen[:5]
    for pid in prev_end:
        if len(five) >= 5:
            break
        if pid not in five and pid not in subbed_in:
            five.append(pid)
    return five


def cut_game(g, box):
    """-> (stints, anomalies). A stint: [period, seconds, A5, H5, ptsA, ptsH, possA, possH]."""
    plays = g["plays"]
    periods = sorted(set(p[0] for p in plays))
    start = {0: starters(box["pa"]), 1: starters(box["ph"])}
    on = {0: list(start[0]), 1: list(start[1])}
    stints, anomalies = [], {"short": 0, "sub_out_missing": 0, "over": 0}
    for period in periods:
        plen = PERIOD_SECS.get(period, 300.0)
        for side in (0, 1):
            on[side] = period_starters(plays, side, on[side], start[side], period)
            if len(on[side]) != 5:
                anomalies["short"] += 1
        pp = [p for p in plays if p[0] == period]
        t = plen
        cur = {"pts": [0, 0], "fga": [0, 0], "fta": [0, 0], "tov": [0, 0], "oreb": [0, 0]}
        i = 0
        while i < len(pp):
            p = pp[i]
            code, side, pids, sec = p[2], p[3], p[4], p[1]
            if code == "S":
                # close the stint at this clock, then apply every sub at the same clock
                sec = sec if sec is not None else t
                if t - sec > 0:
                    stints.append([period, round(t - sec, 1), list(on[0]), list(on[1]), cur["pts"][0], cur["pts"][1],
                                   round(cur["fga"][0] + cur["tov"][0] + 0.44 * cur["fta"][0] - cur["oreb"][0], 2), round(cur["fga"][1] + cur["tov"][1] + 0.44 * cur["fta"][1] - cur["oreb"][1], 2)])
                    cur = {"pts": [0, 0], "fga": [0, 0], "fta": [0, 0], "tov": [0, 0], "oreb": [0, 0]}
                    t = sec
                while i < len(pp) and pp[i][2] == "S" and (pp[i][1] if pp[i][1] is not None else t) == sec:
                    q = pp[i]; s2 = q[3]; ps = q[4]
                    if len(ps) >= 2:
                        inn, out = str(ps[0]), str(ps[1])
                        if out in on[s2]:
                            on[s2].remove(out)
                        else:
                            anomalies["sub_out_missing"] += 1
                        if inn not in on[s2]:
                            on[s2].append(inn)
                        if len(on[s2]) > 5:
                            anomalies["over"] += 1
                            on[s2] = on[s2][-5:]
                    i += 1
                continue
            if side in (0, 1):
                if code == "M":
                    cur["pts"][side] += int(p[7] or 0); cur["fga"][side] += 1
                elif code == "X":
                    cur["fga"][side] += 1
                elif code == "FT":
                    cur["pts"][side] += int(p[7] or 0); cur["fta"][side] += 1
                elif code == "TV":
                    cur["tov"][side] += 1
                elif code == "OR":
                    cur["oreb"][side] += 1
            i += 1
        if t > 0:
            stints.append([period, round(t, 1), list(on[0]), list(on[1]), cur["pts"][0], cur["pts"][1],
                           round(cur["fga"][0] + cur["tov"][0] + 0.44 * cur["fta"][0] - cur["oreb"][0], 2), round(cur["fga"][1] + cur["tov"][1] + 0.44 * cur["fta"][1] - cur["oreb"][1], 2)])
    return stints, anomalies


def main(argv):
    if len(argv) < 3:
        print(__doc__); return 2
    pbp = json.load(open(argv[0])); led = json.load(open(argv[1]))
    boxes = {g["id"]: g for g in led["games"]}
    out = {"format": "nba-stints", "season": pbp.get("season"), "games": []}
    tot = {"games": 0, "stints": 0, "five": 0, "short": 0, "sub_out_missing": 0, "over": 0, "pts_ok": 0, "min_err": 0.0, "min_n": 0}
    for g in pbp["games"]:
        box = boxes.get(g["id"])
        if not box or len(starters(box["pa"])) != 5 or len(starters(box["ph"])) != 5:
            continue
        stints, an = cut_game(g, box)
        tot["games"] += 1; tot["stints"] += len(stints)
        tot["five"] += sum(1 for s in stints if len(s[2]) == 5 and len(s[3]) == 5)
        for k in ("short", "sub_out_missing", "over"):
            tot[k] += an[k]
        pa, ph = sum(s[4] for s in stints), sum(s[5] for s in stints)
        if pa == g["fa"] and ph == g["fh"]:
            tot["pts_ok"] += 1
        # each man's stint minutes against his box minutes
        mins = {}
        for s in stints:
            for pid in s[2] + s[3]:
                mins[pid] = mins.get(pid, 0.0) + s[1] / 60.0
        for p in box["pa"] + box["ph"]:
            bm = float(p[3] or 0)
            if bm > 0:
                tot["min_err"] += abs(mins.get(str(p[0]), 0.0) - bm); tot["min_n"] += 1
        out["games"].append({"id": g["id"], "date": g["date"], "away": g["away"], "home": g["home"], "fa": g["fa"], "fh": g["fh"], "st": stints})
    json.dump(out, open(argv[2], "w"), separators=(",", ":"))
    print("%s: %d games, %d stints (%.1f a game); five a side in %.2f%%; periods short of five %d, sub-outs not on the floor %d, overfills %d; points add to the final in %.1f%% of games; a man's stint minutes miss his box minutes by %.2f on average over %d lines" % (
        out["season"], tot["games"], tot["stints"], tot["stints"] / max(1, tot["games"]), 100.0 * tot["five"] / max(1, tot["stints"]), tot["short"], tot["sub_out_missing"], tot["over"],
        100.0 * tot["pts_ok"] / max(1, tot["games"]), tot["min_err"] / max(1, tot["min_n"]), tot["min_n"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
