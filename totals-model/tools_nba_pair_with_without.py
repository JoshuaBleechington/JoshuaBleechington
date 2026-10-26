#!/usr/bin/env python3
"""Does a specific teammate's presence help a man? For every (player, regular teammate) pair with eight or more games
each way, his points per 36 (and PRA per 36) with the teammate on the floor that night against without; the pooled
mean; whether a pair's own split persists from the first half of the season to the second; and the spread of pair
splits against what shuffling the with/without labels gives. python3 tools_nba_pair_with_without.py slate/nba-ledger-202526.json
(26 Oct 2026, the user: "I imagine Cedric Coward may have helped with Ty Jerome's stats to some degree?")"""
import json, math, random, sys
from collections import defaultdict

led = json.load(open(sys.argv[1]))
games = sorted(led["games"], key=lambda g: (g["date"], g["id"]))
MID = "2026-01-14"
# per club per game: who played (10+ minutes), each man's line
club_games = defaultdict(list)   # club -> [(date, {pid: (min, pts, reb, ast)})]
mins = defaultdict(lambda: [0.0, 0, ""])
for g in games:
    for key, ab in (("pa", g["away"]), ("ph", g["home"])):
        line = {}
        for p in g.get(key) or []:
            if len(p) < 17 or (p[3] or 0) <= 0:
                continue
            line[p[0]] = (float(p[3]), p[4], p[6], p[7], p[1])
            s = mins[(ab, p[0])]; s[0] += float(p[3]); s[1] += 1; s[2] = p[1]
        club_games[ab].append((g["date"], line))
regs = {(ab, pid) for (ab, pid), (m, n, _) in mins.items() if n >= 10 and m / n >= 24.0}
rows = []   # (player, teammate, diff pts36, diff pra36, n_with, n_without, h1 diff, h2 diff)
rng = random.Random(7)
shuffled = []
for ab, gl in club_games.items():
    players = {pid for _d, line in gl for pid in line}
    for (ab2, tm) in regs:
        if ab2 != ab:
            continue
        # the teammate's window: between his first and last game with the club
        dates = [d for d, line in gl if tm in line]
        if not dates:
            continue
        lo, hi = min(dates), max(dates)
        for pid in players:
            if pid == tm:
                continue
            w, wo = [], []
            for d, line in gl:
                if pid not in line or not (lo <= d <= hi) or line[pid][0] < 10:
                    continue
                (w if tm in line else wo).append((d, line[pid]))
            if len(w) < 8 or len(wo) < 8:
                continue
            def per36(rs, k):
                m = sum(r[1][0] for r in rs); return 36.0 * sum(r[1][k] for r in rs) / m
            def pra36(rs):
                m = sum(r[1][0] for r in rs); return 36.0 * sum(r[1][1] + r[1][2] + r[1][3] for r in rs) / m
            d_pts = per36(w, 1) - per36(wo, 1); d_pra = pra36(w) - pra36(wo)
            w1 = [r for r in w if r[0] <= MID]; w2 = [r for r in w if r[0] > MID]; o1 = [r for r in wo if r[0] <= MID]; o2 = [r for r in wo if r[0] > MID]
            h = (per36(w1, 1) - per36(o1, 1), per36(w2, 1) - per36(o2, 1)) if min(len(w1), len(w2), len(o1), len(o2)) >= 5 else None
            rows.append((pid, tm, d_pts, d_pra, len(w), len(wo), h, mins[(ab, pid)][2], mins[(ab, tm)][2]))
            # the same pair with the labels shuffled: what noise alone gives
            pool = w + wo; rng.shuffle(pool); sw, so = pool[:len(w)], pool[len(w):]
            shuffled.append(per36(sw, 1) - per36(so, 1))
n = len(rows)
dp = sorted(r[2] for r in rows); dpra = sorted(r[3] for r in rows)
print("pairs with 8+ games each way: %d" % n)
print("points per 36 WITH the teammate less WITHOUT: mean %+.2f, median %+.2f, middle half %+.2f to %+.2f" % (sum(dp) / n, dp[n // 2], dp[n // 4], dp[3 * n // 4]))
print("PRA per 36: mean %+.2f, median %+.2f" % (sum(dpra) / n, dpra[n // 2]))
print("share of pairs where the man scores MORE per 36 with the teammate: %.1f%%" % (100.0 * sum(1 for x in dp if x > 0) / n))
sd = math.sqrt(sum((x - sum(dp) / n) ** 2 for x in dp) / n); sds = math.sqrt(sum((x - sum(shuffled) / n) ** 2 for x in shuffled) / n)
print("spread of the pair splits: sd %.2f points per 36; with the with/without labels shuffled: sd %.2f (pure noise)" % (sd, sds))
hs = [r[6] for r in rows if r[6]]
if len(hs) >= 10:
    mx = sum(h[0] for h in hs) / len(hs); my = sum(h[1] for h in hs) / len(hs)
    sxy = sum((h[0] - mx) * (h[1] - my) for h in hs); sxx = sum((h[0] - mx) ** 2 for h in hs); syy = sum((h[1] - my) ** 2 for h in hs)
    print("a pair's own split, first half of the season against the second (5+ games each way each half, %d pairs): r %.3f" % (len(hs), sxy / math.sqrt(sxx * syy)))
# the biggest "helpers" by the split, and how big the samples are
rows.sort(key=lambda r: -r[2])
print("the five pairs where a man scored most MORE with the teammate (points per 36 with less without, games with/without):")
for r in rows[:5]:
    print("   %s with %s: %+.1f (%d/%d)" % (r[7], r[8], r[2], r[4], r[5]))
print("the five where he scored most LESS with him:")
for r in rows[-5:]:
    print("   %s with %s: %+.1f (%d/%d)" % (r[7], r[8], r[2], r[4], r[5]))
