"""In-game structure and pregame metrics on two seasons with closes, 11 Oct 2026.

    python3 tools_backtest_nhl_dive.py FOLDER

FOLDER holds ledger2425r.json, ledger2526r.json (--detail --refs ledgers), q1.html, q2.html (KillerSports closes)
and goalies2324.csv, goalies2425.csv (MoneyPuck priors). Prints: relief-goalie rate, a starter relieved last
time, goalie form (last five starts against his own season), the rest matrix, closing-total level, favourite
size, first-period rates by situation, the final against the close by first-period goals, and third-period
and empty-net scoring by the margin after two. CALLSHEET3.md carries the findings."""
import sys, collections, math, datetime as dt
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import tools_backtest_nhl as B
from totals import nhl as N
U = sys.argv[1].rstrip("/") + "/" if len(sys.argv) > 1 else "./"
def ou(v, key="line"):
    ov = sum(1 for f in v if f["tot"] > f[key]); un = sum(1 for f in v if f["tot"] < f[key])
    return "n=%4d resid %+.3f O-U %d-%d (%.1f%% over)" % (len(v), B.avg([f["resid"] for f in v]) if v else 0, ov, un, 100*ov/max(1, ov+un))
pool = collections.defaultdict(list)
for season, led_f, ks, gp_f in (("2024-25", "ledger2425r.json", "q1.html", "goalies2324.csv"), ("2025-26", "ledger2526r.json", "q2.html", "goalies2425.csv")):
    j, led = B.load(U+led_f, U+ks)
    byid = {g["id"]: g for g in led}
    feats = {(f["date"], f["home"], f["away"]): f for f in B.features(j, led, None, B.goalie_prior(U+gp_f))}
    # per-start goalie history with relief detection
    ghist = collections.defaultdict(list)     # pid -> [(date, sv, sa, relieved?)]
    team_games = collections.defaultdict(list)
    for g in sorted(led, key=lambda g: (g["date"], g["id"])):
        if not g.get("detail"): continue
        # shots the away goalie did not face = home shots - his shots - home's empty-net goals (every EN goal is a shot at the empty net)
        rel_a = g["sh"] - g["ga_sa"] - g["enh"]; rel_h = g["sa"] - g["gh_sa"] - g["ena"]
        g["rel_a"], g["rel_h"] = rel_a, rel_h
        ghist[g["ga_id"]].append((g["date"], g["ga_sv"], g["ga_sa"], rel_a > 0, g["ga_ga"]))
        ghist[g["gh_id"]].append((g["date"], g["gh_sv"], g["gh_sa"], rel_h > 0, g["gh_ga"]))
        team_games[g["away"]].append((g["date"], False)); team_games[g["home"]].append((g["date"], True))
    det = [g for g in j if g.get("detail")]
    rel = [g for g in det if byid[g["id"]]["rel_a"] > 0 or byid[g["id"]]["rel_h"] > 0]
    print(f"\n===== {season}: {len(det)} games with a close and detail =====")
    print(f"relief goalie appeared (starter did not face every shot, empty net excluded): {len(rel)} games ({100*len(rel)/len(det):.1f}%); those games averaged {B.avg([g['fa']+g['fh'] for g in rel]):.2f} goals; starter pulled after allowing on average {B.avg([max(byid[g['id']]['ga_ga'] if byid[g['id']]['rel_a']>0 else 0, byid[g['id']]['gh_ga'] if byid[g['id']]['rel_h']>0 else 0) for g in rel]):.1f}")
    rows = []
    for g in j:
        f = feats.get((g["date"], g["home"], g["away"]))
        if not f: continue
        f = dict(f); gg = byid[g["id"]]; d = g["date"]
        f["hml"] = g.get("hml"); f["p1"] = gg["p1a"] + gg["p1h"]; f["p1a"], f["p1h"] = gg["p1a"], gg["p1h"]
        f["p2"] = gg["p2a"] + gg["p2h"]; f["p3"] = gg["p3a"] + gg["p3h"]; f["en"] = gg["ena"] + gg["enh"]; f["end"] = gg["end"]
        f["m2"] = abs((gg["p1a"] + gg["p2a"]) - (gg["p1h"] + gg["p2h"]))   # margin after two periods
        # each starter's previous start: was he relieved? and his last-5 save pct vs season to date
        pulled_prev = 0; form_gap = []; hot = 0
        for pid, side in ((gg["ga_id"], "a"), (gg["gh_id"], "h")):
            prev = [x for x in ghist.get(pid, []) if x[0] < d]
            if prev and prev[-1][3]: pulled_prev += 1
            if len(prev) >= 8:
                l5 = prev[-5:]; s5 = sum(x[1] for x in l5) / sum(x[2] for x in l5)
                sv_all = sum(x[1] for x in prev) / sum(x[2] for x in prev)
                form_gap.append(N.LEAGUE_SHOTS * (sv_all - s5))      # + = cold lately relative to himself -> over lean
        f["pulled_prev"] = pulled_prev
        if len(form_gap) == 2: f["gform"] = sum(form_gap)
        # rest days each side
        def rest(team):
            prev = [x for x in team_games[team] if x[0] < d]
            return (dt.date.fromisoformat(d) - dt.date.fromisoformat(prev[-1][0])).days - 1 if prev else None
        f["ra"], f["rh"] = rest(g["away"]), rest(g["home"])
        rows.append(f)
    for k, v in (("pulled_prev", None),):
        for n in (0, 1, 2):
            print(f"  starters relieved in their previous start = {n}: {ou([f for f in rows if f['pulled_prev'] == n])}")
    pairs = [(f["gform"], f["resid"]) for f in rows if "gform" in f]
    b, r = B.slope(pairs); agree = sum(1 for x,y in pairs if x*y > 0); dis = sum(1 for x,y in pairs if x*y < 0)
    print(f"  goalie form (last 5 starts vs his own season, both starters, x in goals): n={len(pairs)} slope {b:+.3f} r {r:+.3f} sign {agree}-{dis}")
    pool["gform"] += pairs
    cold = [f for f in rows if "gform" in f and f["gform"] > 0.3]; hot = [f for f in rows if "gform" in f and f["gform"] < -0.3]
    print(f"    both starters cold lately (>0.3 goals): {ou(cold)} | hot lately (<-0.3): {ou(hot)}")
    print("  rest matrix (away rest / home rest), residual and over%:")
    rm = collections.defaultdict(list)
    for f in rows:
        if f["ra"] is None or f["rh"] is None: continue
        rm[(min(f["ra"], 3), min(f["rh"], 3))].append(f)
    for k in sorted(rm):
        if len(rm[k]) >= 60: print(f"    away {k[0]}{'+' if k[0]==3 else ''} / home {k[1]}{'+' if k[1]==3 else ''}: {ou(rm[k])}")
    both_rested = [f for f in rows if f["ra"] is not None and f["rh"] is not None and f["ra"] >= 2 and f["rh"] >= 2]
    print(f"    both sides 2+ days rest: {ou(both_rested)} | either side on 0 rest: {ou([f for f in rows if 0 in (f['ra'], f['rh'])])}")
    print("  closing total level:")
    for lv in sorted(set(f["line"] for f in rows)):
        v = [f for f in rows if f["line"] == lv]
        if len(v) >= 40: print(f"    close {lv}: {ou(v)} | P1 2+ {100*B.avg([1.0 if f['p1']>=2 else 0.0 for f in v]):.1f}%")
    print("  favourite size (home moneyline):")
    for lo, hi, nm in ((-9999, -200, "home -200 or shorter"), (-200, -140, "home -140..-200"), (-140, 100, "near pick"), (100, 140, "home +100..+140"), (140, 9999, "home +140 or longer")):
        v = [f for f in rows if f["hml"] is not None and lo <= f["hml"] < hi]
        if len(v) >= 40: print(f"    {nm:22s}: {ou(v)} | P1 2+ {100*B.avg([1.0 if f['p1']>=2 else 0.0 for f in v]):.1f}%")
    print("  first period:")
    print(f"    P1 goals: mean {B.avg([f['p1'] for f in rows]):.3f}; home {B.avg([f['p1h'] for f in rows]):.3f} away {B.avg([f['p1a'] for f in rows]):.3f}; 0 goals {100*B.avg([1.0 if f['p1']==0 else 0 for f in rows]):.1f}%, 1 {100*B.avg([1.0 if f['p1']==1 else 0 for f in rows]):.1f}%, 2+ {100*B.avg([1.0 if f['p1']>=2 else 0 for f in rows]):.1f}%")
    for nm, sel in (("either side on 0 rest", lambda f: 0 in (f["ra"], f["rh"])), ("both 2+ rest", lambda f: f["ra"] is not None and f["rh"] is not None and f["ra"]>=2 and f["rh"]>=2), ("October", lambda f: f["month"]=="10"), ("a backup in net", lambda f: f.get("backups")==1), ("close >= 6.5", lambda f: f["line"]>=6.5), ("close <= 5.5", lambda f: f["line"]<=5.5)):
        v = [f for f in rows if sel(f)]
        print(f"    P1 2+ when {nm:22s}: {100*B.avg([1.0 if f['p1']>=2 else 0 for f in v]):.1f}% (n={len(v)})")
    print("  after the first period (the game's own count; not a pregame signal):")
    for k in (0, 1, 2, 3):
        v = [f for f in rows if (f["p1"] == k if k < 3 else f["p1"] >= 3)]
        print(f"    P1 = {k}{'+' if k==3 else ' '}: n={len(v):4d} final over the close {100*B.avg([1.0 if f['tot']>f['line'] else 0 for f in v]):.1f}%; rest of game averaged {B.avg([f['tot']-f['p1'] for f in v]):.2f} goals (P2 {B.avg([f['p2'] for f in v]):.2f}, P3 {B.avg([f['p3'] for f in v]):.2f})")
    print("  third period by the margin after two:")
    for k in (0, 1, 2, 3):
        v = [f for f in rows if (f["m2"] == k if k < 3 else f["m2"] >= 3)]
        print(f"    margin {k}{'+' if k==3 else ' '}: n={len(v):4d} P3 goals {B.avg([f['p3'] for f in v]):.2f}, empty-net goals {B.avg([f['en'] for f in v]):.2f}, to OT {100*B.avg([1.0 if f['end']!='REG' else 0 for f in v]):.1f}%")
    pool["rows_" + season] = rows
pairs = pool["gform"]; b, r = B.slope(pairs); agree = sum(1 for x,y in pairs if x*y > 0); dis = sum(1 for x,y in pairs if x*y < 0)
print(f"\nPOOLED goalie form: n={len(pairs)} slope {b:+.3f} r {r:+.3f} sign {agree}-{dis} ({100*agree/max(1,agree+dis):.1f}%)")
