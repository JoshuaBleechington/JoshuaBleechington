"""Referee crews against the close, 7 Oct 2026.

    python3 tools_backtest_nhl_refs.py FOLDER

FOLDER holds ledger2425r.json and ledger2526r.json (slate.py nhl-ledger --season X --detail --refs)
and q1.html, q2.html (KillerSports closing totals for 2024 and 2025). Each referee's penalties,
power-play goals and over/under residual in the games he worked to date (this season, with last
season at half as a prior where there is one), shrunk toward the league, as a crew lean on tonight.
Result: crews predict tonight's penalties (slope 0.8) and nothing about the total against the close
(penalty lean -0.45 / +0.46 by season, pooled -0.08; a referee's own over/under history -0.67 /
-0.80). Referees are not an input. CALLSHEET3.md has the table."""
import sys, collections, math
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import tools_backtest_nhl as B
U = sys.argv[1].rstrip("/") + "/" if len(sys.argv) > 1 else "./"
K = 20   # a referee's own rate is worth half the league prior at K games
def anchor_of(g):
    return B.fair_total("NHL", g["total"], -110.0, -110.0)[0]
def ref_hist(led, closes_by_id):
    """referee -> ordered (date, penalties in the game, pp goals, total goals, residual vs close or None)"""
    h = collections.defaultdict(list)
    for g in sorted(led, key=lambda g: (g["date"], g["id"])):
        if not g.get("refs") or not g.get("detail"): continue
        pen = g["pena"] + g["penh"]; ppg = g["ppga"] + g["ppgh"]; tot = g["fa"] + g["fh"]
        res = (tot - closes_by_id[g["id"]]) if g["id"] in closes_by_id else None
        for r in g["refs"]:
            h[r].append((g["date"], pen, ppg, tot, res))
    return h
pooled = collections.defaultdict(list)
for season, led_f, ks, prior_f in (("2024-25", "ledger2425r.json", "q1.html", None), ("2025-26", "ledger2526r.json", "q2.html", "ledger2425r.json")):
    j, led = B.load(U+led_f, U+ks)
    closes = {g["id"]: anchor_of(g) for g in j}
    hist = ref_hist(led, closes)
    prior = None
    if prior_f:
        pj, pled = B.load(U+prior_f, U+"q1.html")
        prior = ref_hist(pled, {g["id"]: anchor_of(g) for g in pj})
    lg_pen = B.avg([g["pena"] + g["penh"] for g in led if g.get("detail")])
    lg_ppg = B.avg([g["ppga"] + g["ppgh"] for g in led if g.get("detail")])
    rows = []
    for g in j:
        d = g["date"]; tot = g["fa"] + g["fh"]; anc = closes[g["id"]]; resid = tot - anc
        crew = []
        for r in g.get("refs", []):
            prev = [x for x in hist.get(r, []) if x[0] < d]
            n = len(prev); pen = sum(x[1] for x in prev); ppg = sum(x[2] for x in prev); res = [x[4] for x in prev if x[4] is not None]
            if prior and r in prior:
                pp = prior[r]; n += 0.5 * len(pp); pen += 0.5 * sum(x[1] for x in pp); ppg += 0.5 * sum(x[2] for x in pp)
                res += [x[4] for x in pp if x[4] is not None][: len(pp) // 2]
            if n <= 0: continue
            w = n / (n + K)
            crew.append((lg_pen + w * (pen / n - lg_pen), lg_ppg + w * (ppg / n - lg_ppg), (w * B.avg(res)) if res else 0.0, n))
        if len(crew) < 2: continue
        f = {"date": d, "tot": tot, "line": g["total"], "anchor": anc, "resid": resid,
             "pen_lean": B.avg([c[0] for c in crew]) - lg_pen, "ppg_lean": B.avg([c[1] for c in crew]) - lg_ppg,
             "res_lean": B.avg([c[2] for c in crew]), "n_min": min(c[3] for c in crew), "pen": g["pena"] + g["penh"]}
        rows.append(f)
    print(f"\n===== {season}: {len(rows)} games with a close and two referees with history; league {lg_pen:.2f} penalties, {lg_ppg:.2f} PP goals a game =====")
    # does the crew's penalty rate predict tonight's penalties? (it should, or the input is noise)
    b, r = B.slope([(f["pen_lean"], f["pen"] - lg_pen) for f in rows]); print(f"crew penalty lean -> tonight's penalties: slope {b:+.3f} r {r:+.3f}  (1.0 would be perfect persistence)")
    for key, name in (("pen_lean", "crew penalties/game lean (x = penalties)"), ("ppg_lean", "crew PP goals/game lean (x = goals)"), ("res_lean", "crew over/under residual to date")):
        pairs = [(f[key], f["resid"]) for f in rows if f["n_min"] >= 10]
        b, r = B.slope(pairs); agree = sum(1 for x,y in pairs if x*y > 0); dis = sum(1 for x,y in pairs if x*y < 0)
        print(f"{name:44s} n={len(pairs):4d} slope {b:+.3f} r {r:+.3f} sign {agree}-{dis} ({100*agree/max(1,agree+dis):.1f}%)")
        pooled[key] += pairs
    # terciles of the penalty lean: does the market move the close with the crew, and does the game follow?
    v = sorted([f for f in rows if f["n_min"] >= 10], key=lambda f: f["pen_lean"]); n3 = len(v)//3
    for nm, part in (("low-penalty crews", v[:n3]), ("middle", v[n3:2*n3]), ("high-penalty crews", v[2*n3:])):
        ov = sum(1 for f in part if f["tot"] > f["line"]); un = sum(1 for f in part if f["tot"] < f["line"])
        print(f"  {nm:20s} n={len(part):4d} lean {B.avg([f['pen_lean'] for f in part]):+.2f} pens tonight {B.avg([f['pen'] for f in part]):.2f} close {B.avg([f['line'] for f in part]):.3f} total {B.avg([f['tot'] for f in part]):.2f} resid {B.avg([f['resid'] for f in part]):+.3f} O-U {ov}-{un} ({100*ov/max(1,ov+un):.1f}%)")
print("\n===== POOLED =====")
for key, pairs in pooled.items():
    b, r = B.slope(pairs); agree = sum(1 for x,y in pairs if x*y > 0); dis = sum(1 for x,y in pairs if x*y < 0)
    print(f"{key:12s} n={len(pairs)} slope {b:+.3f} r {r:+.3f} sign {agree}-{dis} ({100*agree/max(1,agree+dis):.1f}%)")
