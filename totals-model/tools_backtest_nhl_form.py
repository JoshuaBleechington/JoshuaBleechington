"""Time-decayed form against two seasons of closes: does weighting recent games beat the flat last ten?

    python3 tools_backtest_nhl_form.py FOLDER

FOLDER holds ledger2425r.json, ledger2526r.json and q1.html, q2.html (KillerSports' closing
totals). The sheet's form input is each club's flat average total over its last ten games,
both clubs averaged, read against the market's anchor at weight 0.6 (slope +0.14 on 2,445
closes, 7 Oct 2026). The pro models (Dixon-Coles and its descendants) weight every game by
how long ago it was, a half-life in games or days, so the whole season counts and the last
week counts most. This measures, on every game with five or more played by both clubs:
flat last-N for several N; an exponential decay by games and by days at several half-lives;
and the same decays on each club's RESIDUAL form, its totals against their own closes, which
is the form a market-aware model would use. For each: the slope of the close's residual on
the lean, its t, the implied weight, the slopes by season, and the record bet at the line
at a quarter of a goal of lean. Run 14 Oct 2026 at the user's word ("run the time-decayed
form test too"). CALLSHEET3.md has the table.
"""
import sys, os, math, collections, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tools_backtest_nhl as B                 # noqa: E402
from totals.fullgame import fair_total          # noqa: E402

MIN_GAMES = 5
LEAN = 0.25


def ols(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = my - b * mx
    sse = sum((y - a - b * x) ** 2 for x, y in zip(xs, ys))
    se = math.sqrt(sse / (n - 2) / sxx)
    return b, (b / se if se else float("nan")), n


def decayed(vals, weights):
    sw = sum(weights)
    return sum(v * w for v, w in zip(vals, weights)) / sw if sw > 0 else None


def run(folder, log=print):
    rows = []
    for led_f, q in (("ledger2425r.json", "q1.html"), ("ledger2526r.json", "q2.html")):
        season = "2024" if "2425" in led_f else "2025"
        j, led = B.load(os.path.join(folder, led_f), os.path.join(folder, q))
        hist = B.team_hist(led)                      # team -> ordered (date, gf, ga, sf, sa, p1)
        close_of = {(g["date"], g["home"], g["away"]): g["total"] for g in j}
        # each club's games with the close of that game, where it had one
        chist = collections.defaultdict(list)       # team -> ordered (date, total, close or None)
        for g in sorted(led, key=lambda g: (g["date"], g["id"])):
            if g.get("p1a") is None:
                continue
            c = close_of.get((g["date"], g["home"], g["away"]))
            for t in (g["home"], g["away"]):
                chist[t].append((g["date"], g["fa"] + g["fh"], c))
        for g in j:
            d, H, A = g["date"], g["home"], g["away"]
            hb, ab = [x for x in chist[H] if x[0] < d], [x for x in chist[A] if x[0] < d]
            if min(len(hb), len(ab)) < MIN_GAMES:
                continue
            anchor, _ = fair_total("NHL", g["total"], -110.0, -110.0)
            tot = g["fa"] + g["fh"]
            r = {"season": season, "date": d, "line": g["total"], "anchor": anchor, "tot": tot, "resid": tot - anchor, "n": min(len(hb), len(ab))}
            day = dt.date.fromisoformat(d)
            for name, b in (("home", hb), ("away", ab)):
                totals = [x[1] for x in b]
                ages_g = list(range(len(b) - 1, -1, -1))                                    # games ago: 0 = the latest
                ages_d = [(day - dt.date.fromisoformat(x[0])).days for x in b]
                for N in (5, 10, 15, 20, 82):
                    r.setdefault("flat%d" % N, []).append(sum(totals[-N:]) / len(totals[-N:]))
                for hl in (3, 5, 10, 20, 40):
                    r.setdefault("gdecay%d" % hl, []).append(decayed(totals, [0.5 ** (k / hl) for k in ages_g]))
                for hd in (7, 14, 30, 60):
                    r.setdefault("ddecay%d" % hd, []).append(decayed(totals, [0.5 ** (k / hd) for k in ages_d]))
                # residual form: the club's totals against their own closes, games with a close only
                rb = [(x[1] - x[2], k, kd) for x, k, kd in zip(b, ages_g, ages_d) if x[2] is not None]
                if len(rb) >= MIN_GAMES:
                    rv = [x[0] for x in rb]
                    r.setdefault("rflat10", []).append(sum(rv[-10:]) / len(rv[-10:]))
                    r.setdefault("rflat82", []).append(sum(rv) / len(rv))
                    for hl in (5, 10, 20):
                        r.setdefault("rgdecay%d" % hl, []).append(decayed(rv, [0.5 ** (x[1] / hl) for x in rb]))
                    for hd in (14, 30):
                        r.setdefault("rddecay%d" % hd, []).append(decayed(rv, [0.5 ** (x[2] / hd) for x in rb]))
            rows.append(r)
    log("games with five or more played by both clubs and a close: %d (%s)" % (len(rows), ", ".join("%s %d" % (s, sum(1 for r in rows if r["season"] == s)) for s in ("2024", "2025"))))
    VARIANTS = [("flat5", "flat last 5"), ("flat10", "flat last 10 (the sheet, weight 0.6)"), ("flat15", "flat last 15"), ("flat20", "flat last 20"), ("flat82", "season to date"),
                ("gdecay3", "decay, half-life 3 games"), ("gdecay5", "decay, half-life 5 games"), ("gdecay10", "decay, half-life 10 games"), ("gdecay20", "decay, half-life 20 games"), ("gdecay40", "decay, half-life 40 games"),
                ("ddecay7", "decay, half-life 7 days"), ("ddecay14", "decay, half-life 14 days"), ("ddecay30", "decay, half-life 30 days"), ("ddecay60", "decay, half-life 60 days"),
                ("rflat10", "RESIDUAL form, flat last 10 (vs own closes)"), ("rflat82", "RESIDUAL form, season to date"), ("rgdecay5", "RESIDUAL form, half-life 5 games"), ("rgdecay10", "RESIDUAL form, half-life 10 games"),
                ("rgdecay20", "RESIDUAL form, half-life 20 games"), ("rddecay14", "RESIDUAL form, half-life 14 days"), ("rddecay30", "RESIDUAL form, half-life 30 days")]
    log("")
    log("  %-46s %6s %8s %6s %9s %18s %14s" % ("form lean (goals; + = more goals)", "n", "slope", "t", "implied w", "by season 24-25/25-26", "bet at 0.25"))
    for key, name in VARIANTS:
        pts = []
        for r in rows:
            v = r.get(key)
            if not v or len(v) != 2 or any(x is None for x in v):
                continue
            est = (v[0] + v[1]) / 2.0
            x = est - r["anchor"] if not key.startswith("r") else est          # residual form is already a lean against the market
            pts.append((x, r["resid"], r))
        o = ols([p[0] for p in pts], [p[1] for p in pts])
        if not o:
            continue
        b, t, n = o
        w = 4 * b / (1 - b) if b < 1 else float("nan")
        by = []
        for s in ("2024", "2025"):
            os_ = ols([p[0] for p in pts if p[2]["season"] == s], [p[1] for p in pts if p[2]["season"] == s])
            by.append("%+.2f" % os_[0] if os_ else "-")
        bet = [p for p in pts if abs(p[0]) >= LEAN and p[2]["tot"] != p[2]["line"]]
        win = sum(1 for p in bet if (p[2]["tot"] > p[2]["line"]) == (p[0] > 0)); lose = len(bet) - win
        log("  %-46s %6d %+8.3f %6.1f %9.2f %18s %5d-%-4d %+6.1fu" % (name, n, b, t, w, " / ".join(by), win, lose, win * 100.0 / 110.0 - lose))
    # does the decay add anything beyond the flat ten? the two together
    pts = [(r["flat10"], r["gdecay5"], r) for r in rows if r.get("flat10") and r.get("gdecay5") and len(r["flat10"]) == 2 and len(r["gdecay5"]) == 2]
    x1 = [(p[0][0] + p[0][1]) / 2 - p[2]["anchor"] for p in pts]; x2 = [(p[1][0] + p[1][1]) / 2 - p[2]["anchor"] for p in pts]; ys = [p[2]["resid"] for p in pts]
    n = len(ys)
    if n > 10:
        m1, m2, my = sum(x1) / n, sum(x2) / n, sum(ys) / n
        s11 = sum((a - m1) ** 2 for a in x1); s22 = sum((c - m2) ** 2 for c in x2); s12 = sum((a - m1) * (c - m2) for a, c in zip(x1, x2))
        s1y = sum((a - m1) * (y - my) for a, y in zip(x1, ys)); s2y = sum((c - m2) * (y - my) for c, y in zip(x2, ys))
        det = s11 * s22 - s12 * s12
        if det:
            b1 = (s1y * s22 - s2y * s12) / det; b2 = (s2y * s11 - s1y * s12) / det
            log("")
            log("  flat ten and the 5-game decay together: flat %+.3f, decay %+.3f (they correlate at r %.2f)" % (b1, b2, s12 / math.sqrt(s11 * s22)))
    return rows


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
