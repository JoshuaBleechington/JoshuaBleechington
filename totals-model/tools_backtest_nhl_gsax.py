"""Goals saved above expected (GSAx) as the goalie's quality, against two seasons of closes.

    python3 tools_backtest_nhl_gsax.py FOLDER

FOLDER holds ledger2425r.json, ledger2526r.json (slate.py nhl-ledger --season --detail:
every game's starters with saves and shots), q1.html, q2.html (KillerSports' closing
totals) and MoneyPuck's goalie season files for the season BEFORE each ledger:
goalies2324.csv for 2024-25 and goalies2425.csv for 2025-26 (playerId, situation,
icetime, xGoals, goals, ongoal). The sheet scores each starter's save percentage to
date, blended with half of last season's raw line and shrunk toward the league. The
platforms (MoneyPuck, Evolving-Hockey) rate a goalie by goals saved above EXPECTED,
which credits the shots he faced for how hard they were. This asks whether that prior
beats the raw one: each variant's lean in goals against the close's residual, the slope
and its t, the sign record at a tenth of a goal, and a regression of the residual on the
sheet's input AND the GSAx prior together, on games with two regular starters (the only
games where the goalie lean has ever scored). Run 14 Oct 2026 at the user's word ("run
the GSAx goalie test tonight"). CALLSHEET3.md has the table.
"""
import sys, os, math, csv, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tools_backtest_nhl as B                 # noqa: E402
from totals import nhl as N                     # noqa: E402

PRIOR_SHARE = 0.5        # the sheet's blend: half of last season's line
LEAN = 0.10              # a tenth of a goal of lean, the sign test


def mp_goalies(path):
    """playerId -> dict(shots, goals, xg, ice) from MoneyPuck's 'all' rows."""
    out = {}
    for r in csv.DictReader(open(path)):
        if r.get("situation") != "all":
            continue
        try:
            pid = int(r["playerId"]); shots = float(r["ongoal"]); goals = float(r["goals"]); xg = float(r["xGoals"]); ice = float(r["icetime"])
        except (KeyError, ValueError):
            continue
        if shots > 0:
            out[pid] = {"shots": shots, "goals": goals, "xg": xg, "ice": ice}
    return out


def gap_of(saves, shots):
    """The sheet's goalie gap from a saves/shots line: shrunk toward the league, in goals a game."""
    if shots <= 0:
        return 0.0
    return N.goalie_gap(N.shrink_sv(saves / shots, shots))


def ols(xs, ys):
    """slope, intercept, t of the slope, r, n."""
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
    se = math.sqrt(sse / (n - 2) / sxx) if n > 2 else float("nan")
    syy = sum((y - my) ** 2 for y in ys)
    r = sxy / math.sqrt(sxx * syy) if syy > 0 else float("nan")
    return b, a, (b / se if se else float("nan")), r, n


def ols2(x1, x2, ys):
    """y = a + b1 x1 + b2 x2: (b1, t1, b2, t2, n) by the normal equations."""
    n = len(ys)
    if n < 4:
        return None
    m1, m2, my = sum(x1) / n, sum(x2) / n, sum(ys) / n
    s11 = sum((a - m1) ** 2 for a in x1); s22 = sum((b - m2) ** 2 for b in x2); s12 = sum((a - m1) * (b - m2) for a, b in zip(x1, x2))
    s1y = sum((a - m1) * (y - my) for a, y in zip(x1, ys)); s2y = sum((b - m2) * (y - my) for b, y in zip(x2, ys))
    det = s11 * s22 - s12 * s12
    if det == 0:
        return None
    b1 = (s1y * s22 - s2y * s12) / det
    b2 = (s2y * s11 - s1y * s12) / det
    a = my - b1 * m1 - b2 * m2
    sse = sum((y - a - b1 * p - b2 * q) ** 2 for p, q, y in zip(x1, x2, ys))
    s2 = sse / (n - 3)
    se1 = math.sqrt(s2 * s22 / det); se2 = math.sqrt(s2 * s11 / det)
    return b1, (b1 / se1 if se1 else float("nan")), b2, (b2 / se2 if se2 else float("nan")), n


def run(folder, log=print):
    rows = []
    for led_f, q, prior_f in (("ledger2425r.json", "q1.html", "goalies2324.csv"), ("ledger2526r.json", "q2.html", "goalies2425.csv")):
        season = "2024" if "2425" in led_f else "2025"
        j, led = B.load(os.path.join(folder, led_f), os.path.join(folder, q))
        prior = mp_goalies(os.path.join(folder, prior_f))
        gprior = {pid: (p["shots"] - p["goals"], p["shots"]) for pid, p in prior.items()}
        feats = B.features(j, led, None, gprior)       # the sheet's input (goalie_gap) and the backup count, one row per game of j
        ghist = B.goalie_hist(led)
        n_prior = 0
        for g, f in zip(j, feats):
            if not g.get("detail") or g.get("ga_id") is None or g.get("gh_id") is None or "goalie_gap" not in f:
                continue
            d = g["date"]
            r = {"season": season, "date": d, "line": g["total"], "anchor": f["anchor"], "resid": f["resid"], "tot": f["tot"], "backups": f.get("backups", 0),
                 "sheet": f["goalie_gap"], "todate": 0.0, "prior_raw": 0.0, "prior_gsax": 0.0, "blend_gsax": 0.0, "both_prior": True}
            for pid in (g["ga_id"], g["gh_id"]):
                prev = [x for x in ghist.get(pid, []) if x[0] < d]
                saves, shots = float(sum(x[1] for x in prev)), float(sum(x[2] for x in prev))
                r["todate"] += gap_of(saves, shots)
                p = prior.get(pid)
                if p is None:
                    r["both_prior"] = False
                    r["blend_gsax"] += gap_of(saves, shots)
                    continue
                # last season raw, and last season with the shots he faced credited for how hard they were:
                # saves above expected per shot, on top of the league rate
                raw_sv = (p["shots"] - p["goals"]) / p["shots"]
                adj_sv = N.LEAGUE_SAVE_PCT + (p["xg"] - p["goals"]) / p["shots"]
                r["prior_raw"] += gap_of(raw_sv * p["shots"], p["shots"])
                r["prior_gsax"] += gap_of(adj_sv * p["shots"], p["shots"])
                r["blend_gsax"] += gap_of(saves + PRIOR_SHARE * adj_sv * p["shots"], shots + PRIOR_SHARE * p["shots"])
            if r["both_prior"]:
                n_prior += 1
            rows.append(r)
        log("%s-%s: %d games with both starters known, %d with both goalies in last season's MoneyPuck file (%s)" % (season, str(int(season) + 1)[2:], sum(1 for r in rows if r["season"] == season), n_prior, prior_f))
    VARIANTS = (("sheet", "the sheet: to date + half of last season raw, shrunk"), ("todate", "to date only, shrunk"),
                ("prior_raw", "last season only, raw save pct"), ("prior_gsax", "last season only, GSAx (xG-adjusted)"),
                ("blend_gsax", "to date + half of last season GSAx, shrunk"))

    def table(label, v):
        if len(v) < 10:
            return
        log("")
        log("===== %s: %d games =====" % (label, len(v)))
        log("  %-50s %6s %8s %6s %9s %10s %12s" % ("goalie lean (goals a game, + = more goals)", "n", "slope", "t", "implied w", "sign W-L", "bet at 0.1"))
        for key, name in VARIANTS:
            pairs = [(r[key], r["resid"]) for r in v]
            o = ols([a for a, b in pairs], [b for a, b in pairs])
            if not o:
                continue
            b, a, t, rr, n = o
            w = 4 * b / (1 - b) if b < 1 else float("nan")
            agree = sum(1 for x, y in pairs if x * y > 0 and abs(x) >= LEAN); dis = sum(1 for x, y in pairs if x * y < 0 and abs(x) >= LEAN)
            bet = [r for r in v if abs(r[key]) >= LEAN]
            win = sum(1 for r in bet if (r["tot"] > r["line"]) == (r[key] > 0) and r["tot"] != r["line"])
            lose = sum(1 for r in bet if (r["tot"] > r["line"]) != (r[key] > 0) and r["tot"] != r["line"])
            units = win * 100.0 / 110.0 - lose
            log("  %-50s %6d %+8.3f %6.1f %9.2f %5d-%-4d %5d-%-4d %+6.1fu" % (name, n, b, t, w, agree, dis, win, lose, units))
        # the two priors against each other, and GSAx given the sheet's input
        pr = ols([r["prior_raw"] for r in v], [r["prior_gsax"] for r in v])
        if pr:
            log("  the two priors agree at r %.2f; mean |raw - GSAx| %.3f goals" % (pr[3], B.avg([abs(r["prior_raw"] - r["prior_gsax"]) for r in v])))
        o2 = ols2([r["sheet"] for r in v], [r["prior_gsax"] for r in v], [r["resid"] for r in v])
        if o2:
            log("  residual on the sheet's input AND the GSAx prior together: sheet %+.3f (t %.1f), GSAx %+.3f (t %.1f), n %d" % o2)
        o3 = ols2([r["prior_raw"] for r in v], [r["prior_gsax"] for r in v], [r["resid"] for r in v])
        if o3:
            log("  residual on last season raw AND last season GSAx together: raw %+.3f (t %.1f), GSAx %+.3f (t %.1f), n %d" % o3)

    both = [r for r in rows if r["both_prior"]]
    table("every game, both starters in last season's file", both)
    table("two regular starters (no backup by the sheet's rule)", [r for r in both if r["backups"] == 0])
    for s in ("2024", "2025"):
        table("two regular starters, %s-%s" % (s, str(int(s) + 1)[2:]), [r for r in both if r["backups"] == 0 and r["season"] == s])
    table("one backup in net", [r for r in both if r["backups"] == 1])
    # early season, where the prior carries the most weight: the first 25 games of the season per club is where
    # to-date lines are thin; approximate by date
    early = [r for r in both if r["backups"] == 0 and r["date"][5:7] in ("10", "11")]
    table("two regular starters, October and November (the prior matters most)", early)
    late = [r for r in both if r["backups"] == 0 and r["date"][5:7] not in ("10", "11")]
    table("two regular starters, December on", late)
    return rows


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
