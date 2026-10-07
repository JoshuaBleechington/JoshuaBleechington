"""Backtest the hockey book's inputs against closing totals.

    python3 tools_backtest_nhl.py LEDGER.json CLOSES.html [PRIOR_TEAMS.csv]

LEDGER.json is a season's league ledger (slate.py nhl-ledger --season).
CLOSES.html is KillerSports' saved query page (the query.html in the saved
page's folder) for `date, team, o:team, points, o:points, total, line,
site @ season=YYYY and site=home and playoffs=0`. PRIOR_TEAMS.csv, optional,
is MoneyPuck's team file for the season BEFORE, for the prior-season
expected-goals input. Prints the market's own record by month and, for
each input, the slope of the residual on the input and the weight it
implies. First run 7 Oct 2026 on 2024-25 and 2025-26; CALLSHEET3.md has
the table and what changed.
"""
import re, html, json, collections, sys, csv, datetime as dt, math
from totals.fullgame import fair_total
from totals import nhl as N
NICK = {"ANA":"Ducks","BOS":"Bruins","BUF":"Sabres","CGY":"Flames","CAR":"Hurricanes","CHI":"Blackhawks","COL":"Avalanche","CBJ":"Blue Jackets","DAL":"Stars","DET":"Red Wings","EDM":"Oilers","FLA":"Panthers","LAK":"Kings","MIN":"Wild","MTL":"Canadiens","NSH":"Predators","NJD":"Devils","NYI":"Islanders","NYR":"Rangers","OTT":"Senators","PHI":"Flyers","PIT":"Penguins","SJS":"Sharks","SEA":"Kraken","STL":"Blues","TBL":"Lightning","TOR":"Maple Leafs","UTA":"Mammoth","VAN":"Canucks","VGK":"Golden Knights","WSH":"Capitals","WPG":"Jets"}
def ks_rows(f):
    s = open(f, encoding="utf-8", errors="replace").read()
    out = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", s, flags=re.S):
        c = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, flags=re.S)]
        if len(c) >= 7 and re.match(r"\d{4}-\d{2}-\d{2}", c[0]):
            try: out.append({"date": c[0], "home": c[1], "away": c[2], "total": float(c[5]), "hml": float(c[6]) if c[6] not in ("-", "") else None})
            except ValueError: pass
    return out
def load(ledger, ksfile):
    led = json.load(open(ledger))["games"]
    byk = {(g["date"], NICK.get(g["home"], g["home"]), NICK.get(g["away"], g["away"])): g for g in led}
    joined = []
    for r in ks_rows(ksfile):
        g = byk.get((r["date"], r["home"], r["away"]))
        if g and g.get("p1a") is not None: g = dict(g); g["total"] = r["total"]; g["hml"] = r["hml"]; joined.append(g)
    joined.sort(key=lambda g: (g["date"], g["id"]))
    return joined, led
def team_hist(led):
    """per team, ordered list of (date, goals for, goals against, shots for, shots against, p1 total)"""
    h = collections.defaultdict(list)
    for g in sorted(led, key=lambda g: (g["date"], g["id"])):
        if g.get("p1a") is None: continue
        p1 = g["p1a"] + g["p1h"]
        h[g["home"]].append((g["date"], g["fh"], g["fa"], g["sh"], g["sa"], p1))
        h[g["away"]].append((g["date"], g["fa"], g["fh"], g["sa"], g["sh"], p1))
    return h
def before(hist, team, date):
    return [x for x in hist[team] if x[0] < date]
def avg(xs): return sum(xs)/len(xs) if xs else None
def xg_prior(path):
    out = {}
    for r in csv.DictReader(open(path)):
        if r.get("situation") != "all": continue
        gp = float(r["games_played"]);
        if gp <= 0: continue
        out[r["name"]] = (float(r["xGoalsFor"])/gp, float(r["xGoalsAgainst"])/gp)
    lg = sum(a+b for a,b in out.values())/(2*len(out))
    return out, lg
def features(j, led, xg=None):
    hist = team_hist(led); rows = []
    for g in j:
        d = g["date"]; H, A = g["home"], g["away"]
        hb, ab = before(hist, H, d), before(hist, A, d)
        anchor, _ = fair_total("NHL", g["total"], -110.0, -110.0)
        tot = g["fa"] + g["fh"]
        f = {"date": d, "home": H, "away": A, "tot": tot, "line": g["total"], "anchor": anchor, "resid": tot - anchor, "month": d[5:7]}
        n = min(len(hb), len(ab)); f["n"] = n
        if n >= 5:
            f["l10"] = (avg([x[1]+x[2] for x in hb[-10:]]) + avg([x[1]+x[2] for x in ab[-10:]])) / 2.0            # last-10 total avg, both sides
            f["p1l10"] = (avg([x[5] for x in hb[-10:]]) + avg([x[5] for x in ab[-10:]])) / 2.0                     # first-period last ten
            # season rates to date: shots and goals
            hsf, hsa = avg([x[3] for x in hb]), avg([x[4] for x in hb]); asf, asa = avg([x[3] for x in ab]), avg([x[4] for x in ab])
            f["shots_gap"] = ((asf + hsa)/2 + (hsf + asa)/2 - 2*N.LEAGUE_SHOTS) * (1 - N.LEAGUE_SAVE_PCT)        # extra shots at league SV
            hgf, hga = avg([x[1] for x in hb]), avg([x[2] for x in hb]); agf, aga = avg([x[1] for x in ab]), avg([x[2] for x in ab])
            f["goals_gap"] = (agf + hga)/2 + (hgf + aga)/2 - N.LEAGUE_GOALS_PER_GAME
        # rest
        def rest(b):
            if not b: return None
            return (dt.date.fromisoformat(d) - dt.date.fromisoformat(b[-1][0])).days - 1
        f["b2b"] = (rest(hb) == 0) or (rest(ab) == 0)
        f["p1"] = g["p1a"] + g["p1h"]
        if xg:
            x, lg = xg
            if H in x and A in x:
                f["xg_gap"] = (x[A][0] + x[H][1])/2 + (x[H][0] + x[A][1])/2 - 2*lg
        rows.append(f)
    return rows
def slope(pairs):
    xs = [a for a,b in pairs]; ys = [b for a,b in pairs]; n = len(xs)
    if n < 3: return None, None
    mx, my = sum(xs)/n, sum(ys)/n
    sxx = sum((x-mx)**2 for x in xs); sxy = sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    b = sxy/sxx if sxx else float("nan")
    r = sxy/math.sqrt(sxx*sum((y-my)**2 for y in ys)) if sxx else float("nan")
    return b, r
def report(rows, label):
    print(f"\n===== {label}: {len(rows)} games =====")
    ov = sum(1 for f in rows if f["tot"] > f["line"]); un = sum(1 for f in rows if f["tot"] < f["line"]); pu = len(rows)-ov-un
    print(f"market at the close: over {ov} under {un} push {pu} | mean total {avg([f['tot'] for f in rows]):.2f} mean line {avg([f['line'] for f in rows]):.3f} | residual mean {avg([f['resid'] for f in rows]):+.3f} sd {math.sqrt(avg([(f['resid']-avg([x['resid'] for x in rows]))**2 for f in rows])):.3f}")
    bym = collections.defaultdict(list)
    for f in rows: bym[f["month"]].append(f)
    print("by month: " + "; ".join(f"{m}: {avg([f['tot'] for f in v]):.2f} v line {avg([f['line'] for f in v]):.2f}, O-U {sum(1 for f in v if f['tot']>f['line'])}-{sum(1 for f in v if f['tot']<f['line'])}" for m, v in sorted(bym.items(), key=lambda kv: (kv[0] < '07', kv[0]))))
    print(f"\n{'input (estimate - anchor)':28s} {'n':>5s} {'slope b':>8s} {'corr r':>7s} {'implied w':>9s} {'sign W-L':>10s}")
    for key, name in (("l10", "last-10 total avg"), ("goals_gap", "season goals rates"), ("shots_gap", "season shot rates"), ("xg_gap", "prior-season xG"), ("p1l10", "P1 last ten (vs P1 of total)")):
        pairs = []
        for f in rows:
            if key not in f: continue
            if key in ("l10",): x = f["l10"] - f["anchor"]
            elif key == "p1l10": x = f["p1l10"] - N.P1_SHARE * N.reg_mean(f["anchor"]); 
            else: x = f[key]
            y = f["resid"] if key != "p1l10" else f["p1"] - N.P1_SHARE * N.reg_mean(f["anchor"])
            pairs.append((x, y))
        if not pairs: continue
        b, r = slope(pairs)
        w = 4*b/(1-b) if b is not None and b < 1 else float("nan")
        agree = sum(1 for x,y in pairs if x*y > 0); dis = sum(1 for x,y in pairs if x*y < 0)
        print(f"{name:28s} {len(pairs):5d} {b:8.3f} {r:7.3f} {w:9.2f} {agree:5d}-{dis}")
    b2 = [f for f in rows if f["b2b"]]; nb = [f for f in rows if not f["b2b"]]
    print(f"\nback to back: {len(b2)} games, residual {avg([f['resid'] for f in b2]):+.3f}, under {sum(1 for f in b2 if f['tot']<f['line'])}-{sum(1 for f in b2 if f['tot']>f['line'])} | rested: residual {avg([f['resid'] for f in nb]):+.3f}, under {sum(1 for f in nb if f['tot']<f['line'])}-{sum(1 for f in nb if f['tot']>f['line'])}")
    # P1 calibration vs the total's anchor
    p1pairs = [(N.P1_SHARE*N.reg_mean(f["anchor"]), f["p1"]) for f in rows]
    print(f"first period: predicted from the close {avg([a for a,b in p1pairs]):.3f}, actual {avg([b for a,b in p1pairs]):.3f}; P1 2+ when close>=6.5: {avg([1.0 if f['p1']>=2 else 0.0 for f in rows if f['line']>=6.5]):.3f} vs close<=5.5: {avg([1.0 if f['p1']>=2 else 0.0 for f in rows if f['line']<=5.5]):.3f}")
if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    j, led = load(sys.argv[1], sys.argv[2])
    xg = xg_prior(sys.argv[3]) if len(sys.argv) > 3 else None
    report(features(j, led, xg), sys.argv[1] + (" with prior-season xG" if xg else ""))
