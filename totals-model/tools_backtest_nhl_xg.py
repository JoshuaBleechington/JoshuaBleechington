"""Expected goals to date, built the way the slate builds them, against 2024-25 closing totals.

    python3 tools_backtest_nhl_xg.py FOLDER

FOLDER holds nst_games.html (Natural Stat Trick, Games, all situations, 2023-24 and 2024-25,
saved as a page), ledger2425d.json (slate.py nhl-ledger --season 20242025 --detail) and q1.html
(KillerSports closing totals for 2024). Run 7 Oct 2026; CALLSHEET3.md has the table. Also tests
last-season xG, high-danger chances to date, last-ten xG and PDO to date."""
import sys, re, html, collections, math
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import tools_backtest_nhl as B
from totals import nhl as N
U = sys.argv[1].rstrip("/") + "/" if len(sys.argv) > 1 else "./"   # the folder above
import glob
SEASON = int(sys.argv[2]) if len(sys.argv) > 2 else 2024       # the season tested: 2024 = 2024-25
LEDGER = sys.argv[3] if len(sys.argv) > 3 else ("ledger2425d.json" if SEASON == 2024 else "ledger2526d.json")
CLOSES = sys.argv[4] if len(sys.argv) > 4 else ("q1.html" if SEASON == 2024 else "q2.html")
rows, ix = [], {}
for nf in sorted(glob.glob(U + "nst*.html")):     # every Natural Stat Trick games table in the folder
    s = open(nf, encoding="utf-8", errors="replace").read()
    hdr = [html.unescape(re.sub(r"<[^>]+>", "", h)).strip() for h in re.findall(r"<th[^>]*>(.*?)</th>", s, flags=re.S)]
    if hdr: ix = {h: i for i, h in enumerate(hdr)}
    rows += re.findall(r"<tr[^>]*>(.*?)</tr>", s, flags=re.S)
hdr = list(ix)
def nick(full):
    if "Utah" in full: return "Mammoth"
    return full.split()[-1] if not full.endswith("Blue Jackets") and not full.endswith("Red Wings") and not full.endswith("Maple Leafs") and not full.endswith("Golden Knights") else " ".join(full.split()[-2:])
games = {}   # (date, home nick, away nick) -> {"away": row, "home": row}
team_rows = collections.defaultdict(list)   # nick -> [(date, xgf, xga, gf, ga, sf, sa, hdcf, hdca, shpct, svpct)]
for r in rows:
    c = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, flags=re.S)]
    if len(c) < len(hdr): continue
    m = re.match(r"(\d{4}-\d{2}-\d{2}) - (.+?) (\d+), (.+?) (\d+)$", c[0])
    if not m: continue
    d, an, hn = m.group(1), m.group(2), m.group(4)
    an = "Mammoth" if "Utah" in an else an; hn = "Mammoth" if "Utah" in hn else hn
    t = nick(c[ix["Team"]])
    try:
        rec = dict(date=d, xgf=float(c[ix["xGF"]]), xga=float(c[ix["xGA"]]), gf=float(c[ix["GF"]]), ga=float(c[ix["GA"]]),
                   hdcf=float(c[ix["HDCF"]]), hdca=float(c[ix["HDCA"]]), pdo=float(c[ix["PDO"]]))
    except ValueError: continue
    games.setdefault((d, hn, an), {})["home" if t == hn else "away"] = rec
    if not any(x["date"] == d for x in team_rows[t]): team_rows[t].append(rec)   # the tables overlap in Oct 2025
for t in team_rows: team_rows[t].sort(key=lambda r: r["date"])
print("NST games:", len(games), "teams:", len(team_rows), "dates", min(k[0] for k in games), "to", max(k[0] for k in games))
def season_of(d): y = int(d[:4]); return y if int(d[5:7]) >= 8 else y - 1
# prior-season full averages per team (2023-24 for the 2024-25 test)
def season_avg(t, yr):
    v = [r for r in team_rows[t] if season_of(r["date"]) == yr]
    return (B.avg([r["xgf"] for r in v]), B.avg([r["xga"] for r in v]), len(v)) if v else None
# league xG per team-game by season
j, led = B.load(U+LEDGER, U+CLOSES)
feats = B.features(j, led, None, None)
MIN = 5
out = []
for f in feats:
    d, H, A = f["date"], B.NICK.get(f["home"], f["home"]), B.NICK.get(f["away"], f["away"])
    hb = [r for r in team_rows[H] if r["date"] < d and season_of(r["date"]) == SEASON]
    ab = [r for r in team_rows[A] if r["date"] < d and season_of(r["date"]) == SEASON]
    # league mean to date: every team-row this season before d
    lg_rows = [r for t in team_rows for r in team_rows[t] if r["date"] < d and season_of(r["date"]) == SEASON]
    g = dict(f)
    if len(hb) >= MIN and len(ab) >= MIN and lg_rows:
        lg = B.avg([r["xgf"] for r in lg_rows])
        axgf, axga = B.avg([r["xgf"] for r in ab]), B.avg([r["xga"] for r in ab]); hxgf, hxga = B.avg([r["xgf"] for r in hb]), B.avg([r["xga"] for r in hb])
        g["xg_now"] = (axgf + hxga)/2 + (hxgf + axga)/2 - 2*lg
        g["hd_now"] = ((B.avg([r["hdcf"] for r in ab]) + B.avg([r["hdca"] for r in hb]))/2 + (B.avg([r["hdcf"] for r in hb]) + B.avg([r["hdca"] for r in ab]))/2) - 2*B.avg([r["hdcf"] for r in lg_rows])
        g["pdo_now"] = (B.avg([r["pdo"] for r in ab]) + B.avg([r["pdo"] for r in hb]))/2 - 1.0
        # last-ten xG (recent form in xG rather than goals)
        g["xg_l10"] = (B.avg([r["xgf"]+r["xga"] for r in ab[-10:]]) + B.avg([r["xgf"]+r["xga"] for r in hb[-10:]]))/2 - 2*lg
        g["n_games"] = min(len(hb), len(ab))
    pa, ph = season_avg(A, SEASON - 1), season_avg(H, SEASON - 1)
    if pa and ph:
        lg23 = B.avg([r["xgf"] for t in team_rows for r in team_rows[t] if season_of(r["date"]) == SEASON - 1])
        g["xg_prior"] = (pa[0] + ph[1])/2 + (ph[0] + pa[1])/2 - 2*lg23
        if "xg_now" in g:
            # the slate's blend if it blended: this season's games plus half of last season's 82
            n = g["n_games"]; w = n / (n + 41.0)
            g["xg_blend"] = w*g["xg_now"] + (1-w)*g["xg_prior"]
    out.append(g)
def report(key, name):
    pairs = [(g[key], g["resid"]) for g in out if key in g]
    if len(pairs) < 10: return
    b, r = B.slope(pairs); agree = sum(1 for x,y in pairs if x*y>0); dis = sum(1 for x,y in pairs if x*y<0)
    line = f"{name:44s} n={len(pairs):4d} slope {b:+.3f} r {r:+.3f} implied w {4*b/(1-b) if b<1 else float('nan'):+.2f} sign {agree}-{dis}"
    for t in (0.25, 0.5):
        w = l = 0
        for g in out:
            if key not in g or abs(g[key]) < t: continue
            d_ = g["tot"] - g["line"]
            if d_ == 0: continue
            if (d_ > 0) == (g[key] > 0): w += 1
            else: l += 1
        line += f" | |x|>={t}: {w}-{l} ({100*w/max(1,w+l):.1f}%)"
    print(line)
print("\n%d-%02d against the close:" % (SEASON, (SEASON + 1) % 100))
report("xg_now", "this season's xG to date (slate's input)")
report("xg_blend", "xG blended with last season (n/(n+41))")
report("xg_prior", "last season's xG, full season")
report("xg_l10", "last-ten xG total (form in xG)")
report("hd_now", "high-danger chances to date")
report("pdo_now", "PDO to date (luck, + = hot)")
# by stage of season
for lo, hi, nm in ((5, 20, "games 5-19"), (20, 45, "games 20-44"), (45, 99, "games 45+")):
    pairs = [(g["xg_now"], g["resid"]) for g in out if "xg_now" in g and lo <= g["n_games"] < hi]
    b, r = B.slope(pairs); print(f"  xG to date, {nm:12s} n={len(pairs):4d} slope {b:+.3f}")
