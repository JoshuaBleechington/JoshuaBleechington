#!/usr/bin/env python3
"""Does a player's usage differ at home and on the road, and does his own
split persist (26 Oct 2026, the user: "does the simulation also account for
usage on the road vs home")? Asked of a season's ledger with the full box
lines: the pooled usage by venue, each player's home-less-road split, whether
the split over the first half of the season predicts the second half's, and
the points projection's miss by venue.

    python3 tools_nba_usage_venue.py slate/nba-ledger-202526.json
"""
import json, math, sys
from collections import defaultdict

led = json.load(open(sys.argv[1]))
games = sorted(led["games"], key=lambda g: (g["date"], g["id"]))
MID = "2026-01-14"
pg = defaultdict(list)           # pid -> [(date, home, mins, u, tu, pts, team)]
for g in games:
    for key, ab, tline, home in (("pa", g["away"], g["sa"], 0), ("ph", g["home"], g["sh"], 1)):
        tm = float(tline.get("min") or 240.0)
        tpos = (tline.get("fga") or 0) + 0.44 * (tline.get("fta") or 0) + (tline.get("tov") or 0)
        for p in g.get(key) or []:
            if len(p) < 17:
                continue
            mins = float(p[3] or 0)
            if mins < 10:
                continue
            u = p[9] + 0.44 * p[10] + p[11]
            tu = tpos * mins / (tm / 5.0)
            pg[str(p[0])].append((g["date"], home, mins, u, tu, p[4], ab))

def usage(rows):
    tu = sum(r[4] for r in rows)
    return 100.0 * sum(r[3] for r in rows) / tu if tu > 0 else None

# 1. pooled: usage at home against on the road, every player-game of 10+ minutes
allrows = [r for rs in pg.values() for r in rs]
home = [r for r in allrows if r[1]]; road = [r for r in allrows if not r[1]]
print("pooled usage: home %.2f%% (n %d) · road %.2f%% (n %d)" % (usage(home), len(home), usage(road), len(road)))
# per player, the whole season: his usage at home less on the road, the spread of the split
diffs = []
for pid, rs in pg.items():
    h = [r for r in rs if r[1]]; a = [r for r in rs if not r[1]]
    if len(h) >= 15 and len(a) >= 15:
        diffs.append(usage(h) - usage(a))
diffs.sort()
print("per player (15+ games each venue, n %d): home less road, median %+.2f, middle half %+.2f to %+.2f, 10th/90th %+.2f/%+.2f" % (len(diffs), diffs[len(diffs)//2], diffs[len(diffs)//4], diffs[3*len(diffs)//4], diffs[len(diffs)//10], diffs[9*len(diffs)//10]))

# 2. does a player's own split persist? first half (to 14 Jan) against the second
xs, ys = [], []
for pid, rs in pg.items():
    h1 = [r for r in rs if r[0] <= MID]; h2 = [r for r in rs if r[0] > MID]
    hh1 = [r for r in h1 if r[1]]; ha1 = [r for r in h1 if not r[1]]; hh2 = [r for r in h2 if r[1]]; ha2 = [r for r in h2 if not r[1]]
    if min(len(hh1), len(ha1), len(hh2), len(ha2)) < 8:
        continue
    xs.append(usage(hh1) - usage(ha1)); ys.append(usage(hh2) - usage(ha2))
n = len(xs); mx = sum(xs)/n; my = sum(ys)/n
sxx = sum((x-mx)**2 for x in xs); syy = sum((y-my)**2 for y in ys); sxy = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
r = sxy / math.sqrt(sxx*syy)
print("a player's own home-less-road usage, first half against the second (8+ games each venue each half, n %d): r %.3f, slope %.3f" % (n, r, sxy/sxx))
print("  the first-half split's spread: sd %.2f points of usage; the second half's: sd %.2f" % (math.sqrt(sxx/n), math.sqrt(syy/n)))

# 3. the same for points per 36 at home less on the road (the split the panel shows, never scored)
xs, ys = [], []
def p36(rows):
    m = sum(r[2] for r in rows); return 36.0 * sum(r[5] for r in rows) / m if m > 0 else None
for pid, rs in pg.items():
    h1 = [r for r in rs if r[0] <= MID]; h2 = [r for r in rs if r[0] > MID]
    hh1 = [r for r in h1 if r[1]]; ha1 = [r for r in h1 if not r[1]]; hh2 = [r for r in h2 if r[1]]; ha2 = [r for r in h2 if not r[1]]
    if min(len(hh1), len(ha1), len(hh2), len(ha2)) < 8:
        continue
    xs.append(p36(hh1) - p36(ha1)); ys.append(p36(hh2) - p36(ha2))
n = len(xs); mx = sum(xs)/n; my = sum(ys)/n
sxx = sum((x-mx)**2 for x in xs); syy = sum((y-my)**2 for y in ys); sxy = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
print("points per 36 home less road, the same players and halves: r %.3f (pooled home edge in the first half %+.2f per 36, second %+.2f)" % (sxy/math.sqrt(sxx*syy), mx, my))

# 4. the projection's miss by venue: rate-times-minutes built from his games to date, pooled, points
hist = defaultdict(list); miss = {0: [], 1: []}; over = {0: [0, 0], 1: [0, 0]}
for g in games:
    for key, ab, home in (("pa", g["away"], 0), ("ph", g["home"], 1)):
        for p in g.get(key) or []:
            if len(p) < 17:
                continue
            pid, mins = str(p[0]), float(p[3] or 0)
            prior = [x for x in hist[pid] if x[0] == ab]
            if mins > 0 and len(prior) >= 8:
                pm = sum(x[1] for x in prior); last5 = prior[-5:]
                proj = sum(x[2] for x in prior) / pm * (sum(x[1] for x in last5) / len(last5))
                if proj >= 5:
                    sd = 1.85 * math.sqrt(proj); med = proj - 0.08 * sd
                    miss[home].append((p[4] - proj) / sd)
                    over[home][0] += 1 if p[4] > med else 0; over[home][1] += 1
            hist[pid].append((ab, mins, p[4]))
for home in (1, 0):
    m = miss[home]; n = len(m); mean = sum(m)/n; sd = math.sqrt(sum((x-mean)**2 for x in m)/n)
    print("the points projection's miss %s: %+.3f sigmas (t %+.1f, n %d) · over the median %.1f%%" % ("at home" if home else "on the road", mean, mean/(sd/math.sqrt(n)), n, 100.0*over[home][0]/over[home][1]))
