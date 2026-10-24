"""Backtest the hockey SIDES: can the sheet's inputs pick a winner better than the moneyline?

    python3 tools_backtest_nhl_sides.py FOLDER
    python3 tools_backtest_nhl_sides.py --selftest

FOLDER holds ledger2425r.json and ledger2526r.json (slate.py nhl-ledger --season --detail),
q1.html and q2.html (KillerSports: date, team, o:team, points, o:points, total, line, site; the
line is the home moneyline at the close), nst*.html (Natural Stat Trick games tables, 2023-24 to
2025-26, for expected goals to date and the prior season) and goalies2324.csv / goalies2425.csv
(MoneyPuck goalie files, the prior each starter's line is blended with).

The market is the home moneyline de-vigged with a 4.5% hold assumed (one price is kept by the
query), then calibrated by a logistic fit on the first season. Each input is signed home minus
away and read two ways: the slope of (home won minus the market's chance) on the input, and a
logistic model of the market plus the input, fitted on 2024-25 and scored on 2025-26 out of
sample, by log-loss and by the record of betting the side the model likes by three points or
more at the closing price. Then the base rates the pick leans on: the favourite's record by
price, the dog +1.5 cover rate by price, home ice. Run 12 Oct 2026, the day the pick went in
("pick the best, most likely ... moneyline or upset type of game"); CALLSHEET3.md has the table.
"""
import sys, os, re, html, glob, json, math, collections, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tools_backtest_nhl as B   # noqa: E402
from totals import nhl as N      # noqa: E402

HOLD = 0.045          # the moneyline's hold, assumed: the query keeps one price
PRIOR_SHARE = 0.5     # half of last season's goalie line rides with this season's, as the sheet does
MIN_GAMES = 5
EDGE = 0.03           # the model must like a side by three points to bet it in the test
FEATURES = [("gd", "goal difference per game to date"), ("sd", "shot difference per game to date"), ("xgd", "expected-goal difference to date (NST)"),
            ("xgd_prior", "expected-goal difference, last season"), ("form", "last-ten goal difference"), ("goalie", "the goalies (starters, blended, shrunk)"),
            ("rest", "rest days (capped at 3)"), ("b2b", "back to back (the other side tired)"), ("backup", "a backup in the other net")]


def implied(a):
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)


def american(p):
    return -100.0 * p / (1 - p) if p >= 0.5 else 100.0 * (1 - p) / p


def payout(a):
    return a / 100.0 if a > 0 else 100.0 / -a


def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def sigmoid(z):
    return 1.0 / (1.0 + math.exp(-z)) if z > -700 else 0.0


def nick(full):
    if "Utah" in full:
        return "Mammoth"
    w = full.split()
    return " ".join(w[-2:]) if " ".join(w[-2:]) in ("Blue Jackets", "Red Wings", "Maple Leafs", "Golden Knights") else w[-1]


def season_of(d):
    y = int(d[:4])
    return y if int(d[5:7]) >= 8 else y - 1


def nst_rows(folder):
    """nick -> sorted [(date, xgf, xga)] from every Natural Stat Trick games table in the folder."""
    out = collections.defaultdict(dict)
    for nf in sorted(glob.glob(os.path.join(folder, "nst*.html"))):
        s = open(nf, encoding="utf-8", errors="replace").read()
        hdr = [html.unescape(re.sub(r"<[^>]+>", "", h)).strip() for h in re.findall(r"<th[^>]*>(.*?)</th>", s, flags=re.S)]
        ix = {h: i for i, h in enumerate(hdr)}
        if "Team" not in ix or "xGF" not in ix:
            continue
        for r in re.findall(r"<tr[^>]*>(.*?)</tr>", s, flags=re.S):
            c = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, flags=re.S)]
            if len(c) < len(hdr):
                continue
            m = re.match(r"(\d{4}-\d{2}-\d{2}) - ", c[0])
            if not m:
                continue
            try:
                out[nick(c[ix["Team"]])][m.group(1)] = (float(c[ix["xGF"]]), float(c[ix["xGA"]]))
            except ValueError:
                continue
    return {t: sorted((d, v[0], v[1]) for d, v in dd.items()) for t, dd in out.items()}


def features(j, led, nst, gprior, season):
    """One row per joined game: the market, the result, and every input signed home minus away."""
    hist = B.team_hist(led)
    ghist = B.goalie_hist(led)
    sthist, tghist = B.starts_hist(led)
    rows = []
    for g in j:
        d, H, A = g["date"], g["home"], g["away"]
        if g.get("hml") is None:
            continue
        f = {"date": d, "home": H, "away": A, "hml": g["hml"], "margin": g["fh"] - g["fa"], "y": 1 if g["fh"] > g["fa"] else 0,
             "p_raw": min(max(implied(g["hml"]) - HOLD / 2, 0.02), 0.98), "end": g.get("end")}
        hb, ab = B.before(hist, H, d), B.before(hist, A, d)
        if len(hb) >= MIN_GAMES and len(ab) >= MIN_GAMES:
            f["gd"] = B.avg([x[1] - x[2] for x in hb]) - B.avg([x[1] - x[2] for x in ab])
            f["sd"] = B.avg([x[3] - x[4] for x in hb]) - B.avg([x[3] - x[4] for x in ab])
            f["form"] = B.avg([x[1] - x[2] for x in hb[-10:]]) - B.avg([x[1] - x[2] for x in ab[-10:]])
        hn, an = B.NICK.get(H, H), B.NICK.get(A, A)
        hx = [r for r in nst.get(hn, []) if r[0] < d and season_of(r[0]) == season]
        ax = [r for r in nst.get(an, []) if r[0] < d and season_of(r[0]) == season]
        if len(hx) >= MIN_GAMES and len(ax) >= MIN_GAMES:
            f["xgd"] = B.avg([r[1] - r[2] for r in hx]) - B.avg([r[1] - r[2] for r in ax])
        hp = [r for r in nst.get(hn, []) if season_of(r[0]) == season - 1]
        ap = [r for r in nst.get(an, []) if season_of(r[0]) == season - 1]
        if len(hp) >= 20 and len(ap) >= 20:
            f["xgd_prior"] = B.avg([r[1] - r[2] for r in hp]) - B.avg([r[1] - r[2] for r in ap])
        if g.get("detail") and g.get("ga_id") is not None and g.get("gh_id") is not None:
            gaps = {}
            for side, pid in (("a", g["ga_id"]), ("h", g["gh_id"])):
                prev = [x for x in ghist.get(pid, []) if x[0] < d]
                saves, shots = sum(x[1] for x in prev), sum(x[2] for x in prev)
                if gprior and pid in gprior:
                    saves += PRIOR_SHARE * gprior[pid][0]
                    shots += PRIOR_SHARE * gprior[pid][1]
                gaps[side] = N.goalie_gap(N.shrink_sv(saves / shots, shots)) if shots > 0 else 0.0
            f["goalie"] = gaps["a"] - gaps["h"]     # goals the away goalie gives up above the home one: positive favours home
            nb = {}
            for side, t, pid in (("a", A, g["ga_id"]), ("h", H, g["gh_id"])):
                n = sum(1 for x in tghist[t] if x < d)
                s = sum(1 for x in sthist[(t, pid)] if x < d)
                nb[side] = 1 if (n >= N.BACKUP_MIN_STARTS and s < N.BACKUP_SHARE * n) else 0
            f["backup"] = nb["a"] - nb["h"]
        def rest(b):
            return (dt.date.fromisoformat(d) - dt.date.fromisoformat(b[-1][0])).days - 1 if b else None
        rh, ra = rest(hb), rest(ab)
        if rh is not None and ra is not None:
            f["rest"] = min(rh, 3) - min(ra, 3)
            f["b2b"] = (1 if ra == 0 else 0) - (1 if rh == 0 else 0)
        rows.append(f)
    return rows


# ---- a small logistic regression, Newton's method, no numpy -------------------

def solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        if abs(M[c][c]) < 1e-12:
            continue
        for r in range(n):
            if r != c and M[r][c]:
                k = M[r][c] / M[c][c]
                for cc in range(c, n + 1):
                    M[r][cc] -= k * M[c][cc]
    return [M[i][n] / M[i][i] if abs(M[i][i]) > 1e-12 else 0.0 for i in range(n)]


def logistic_fit(X, y, iters=30, l2=1e-4):
    k = len(X[0])
    w = [0.0] * k
    for _ in range(iters):
        g = [0.0] * k
        Hm = [[0.0] * k for _ in range(k)]
        for xi, yi in zip(X, y):
            p = sigmoid(sum(a * b for a, b in zip(w, xi)))
            r = yi - p
            for a in range(k):
                g[a] += r * xi[a]
                for b in range(k):
                    Hm[a][b] += p * (1 - p) * xi[a] * xi[b]
        for a in range(k):
            Hm[a][a] += l2
            g[a] -= l2 * w[a]
        step = solve(Hm, g)
        w = [a + b for a, b in zip(w, step)]
        if max(abs(s) for s in step) < 1e-9:
            break
    # standard errors from the inverse Hessian
    se = []
    for a in range(k):
        e = [0.0] * k
        e[a] = 1.0
        se.append(math.sqrt(max(solve(Hm, e)[a], 0.0)))
    return w, se


def logloss(X, y, w):
    s = 0.0
    for xi, yi in zip(X, y):
        p = min(max(sigmoid(sum(a * b for a, b in zip(w, xi))), 1e-9), 1 - 1e-9)
        s -= yi * math.log(p) + (1 - yi) * math.log(1 - p)
    return s / len(y)


def design(rows, keys, scale):
    X, y, kept = [], [], []
    for f in rows:
        if any(k not in f for k in keys):
            continue
        X.append([1.0, logit(f["p_raw"])] + [(f[k] - scale[k][0]) / scale[k][1] for k in keys])
        y.append(f["y"])
        kept.append(f)
    return X, y, kept


def scales(rows, keys):
    out = {}
    for k in keys:
        v = [f[k] for f in rows if k in f]
        m = B.avg(v) if v else 0.0
        sd = math.sqrt(B.avg([(x - m) ** 2 for x in v])) if len(v) > 1 else 1.0
        out[k] = (m, sd if sd > 1e-9 else 1.0)
    return out


def bet_test(rows, X, w, w0):
    """Bet the side the model likes by EDGE over the calibrated market, at the closing price."""
    n = wn = ln = 0
    units = 0.0
    ups = upw = 0
    for f, xi in zip(rows, X):
        pm = sigmoid(sum(a * b for a, b in zip(w, xi)))
        pk = sigmoid(w0[0] + w0[1] * xi[1])
        if pm - pk >= EDGE:
            side, price = "home", f["hml"]
        elif pk - pm >= EDGE:
            side, price = "away", american(min(max(1 + HOLD - implied(f["hml"]), 0.02), 0.98))
        else:
            continue
        won = (f["y"] == 1) == (side == "home")
        n += 1
        if won:
            wn += 1
            units += payout(price)
        else:
            ln += 1
            units -= 1
        if price > 0:
            ups += 1
            upw += 1 if won else 0
    return {"n": n, "w": wn, "l": ln, "units": units, "dogs": ups, "dogs_won": upw}


def slope_se(pairs):
    xs = [a for a, b in pairs]
    ys = [b for a, b in pairs]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0 or n < 4:
        return None, None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    s2 = sum((y - a - b * x) ** 2 for x, y in zip(xs, ys)) / (n - 2)
    return b, math.sqrt(s2 / sxx)


def base_rates(rows, log):
    n = len(rows)
    hw = sum(f["y"] for f in rows)
    log("home ice: the home side won %d of %d (%.1f%%); the market's de-vigged home chance averaged %.1f%%" % (hw, n, 100.0 * hw / n, 100.0 * B.avg([f["p_raw"] for f in rows])))
    buckets = [(-10000, -200, "fav -200 or more"), (-199, -150, "fav -199 to -150"), (-149, -120, "fav -149 to -120"), (-119, -101, "fav -119 to -101")]
    log("%-22s %5s %8s %8s %10s %10s %10s" % ("favourite's price", "n", "fav won", "implied", "dog +1.5", "fav -1.5", "fav ML ROI"))
    for lo, hi, name in buckets:
        v = []
        for f in rows:
            if f["hml"] < 0:
                favp, fav_won, m = f["hml"], f["y"] == 1, f["margin"]
            elif f["hml"] > 100:
                ap = american(min(max(1 + HOLD - implied(f["hml"]), 0.02), 0.98))
                favp, fav_won, m = ap, f["y"] == 0, -f["margin"]
            else:
                continue
            if lo <= favp <= hi:
                v.append((favp, fav_won, m))
        if not v:
            continue
        fw = sum(1 for x in v if x[1])
        dog15 = sum(1 for x in v if x[2] <= 1)        # the dog wins, or loses by one (every OT and SO loss is by one)
        fav15 = sum(1 for x in v if x[2] >= 2)
        roi = sum((payout(x[0]) if x[1] else -1.0) for x in v) / len(v)
        log("%-22s %5d %7.1f%% %7.1f%% %9.1f%% %9.1f%% %+9.1f%%" % (name, len(v), 100.0 * fw / len(v), 100.0 * B.avg([implied(x[0]) for x in v]), 100.0 * dog15 / len(v), 100.0 * fav15 / len(v), 100 * roi))
    dogs = [f for f in rows if f["hml"] > 100 or f["hml"] < 0]
    dog_roi = 0.0
    for f in dogs:
        if f["hml"] > 100:
            dog_roi += payout(f["hml"]) if f["y"] == 1 else -1.0
        else:
            ap = american(min(max(1 + HOLD - implied(f["hml"]), 0.02), 0.98))
            dog_roi += payout(ap) if f["y"] == 0 else -1.0
    log("every dog on the moneyline at the close: %+.1f%% a bet on %d; every favourite: see the ROI column (the hold is the house's)" % (100 * dog_roi / len(dogs), len(dogs)))


def run(folder, log=print):
    nst = nst_rows(folder)
    log("Natural Stat Trick: %d teams, %d team-games" % (len(nst), sum(len(v) for v in nst.values())))
    seasons = {}
    for season, led, q, gp in ((2024, "ledger2425r.json", "q1.html", "goalies2324.csv"), (2025, "ledger2526r.json", "q2.html", "goalies2425.csv")):
        j, led_all = B.load(os.path.join(folder, led), os.path.join(folder, q))
        gprior = B.goalie_prior(os.path.join(folder, gp)) if os.path.exists(os.path.join(folder, gp)) else None
        rows = features(j, led_all, nst, gprior, season)
        seasons[season] = rows
        log("%d-%02d: %d games joined with a closing moneyline; inputs present: %s" % (season, (season + 1) % 100, len(rows), ", ".join("%s %d" % (k, sum(1 for f in rows if k in f)) for k, _ in FEATURES)))
    train, test = seasons[2024], seasons[2025]
    keys = [k for k, _ in FEATURES]
    sc = scales(train, keys)
    log("")
    log("===== base rates, both seasons (%d games) =====" % (len(train) + len(test)))
    base_rates(train + test, log)
    # the market alone, calibrated on 2024-25
    X0, y0, _ = design(train, [], sc)
    w0, se0 = logistic_fit(X0, y0)
    Xt0, yt0, _ = design(test, [], sc)
    ll_train0, ll_test0 = logloss(X0, y0, w0), logloss(Xt0, yt0, w0)
    log("")
    log("===== the market alone: home win = f(home moneyline), fitted on 2024-25 =====")
    log("calibration: intercept %+.3f (se %.3f), slope on the market's logit %.3f (se %.3f); a slope of 1 and an intercept of 0 is a perfectly priced market" % (w0[0], se0[0], w0[1], se0[1]))
    log("log-loss: 2024-25 %.4f (in sample), 2025-26 %.4f (out of sample); a coin flip is %.4f" % (ll_train0, ll_test0, math.log(2)))
    log("")
    log("===== each input, signed home minus away, against the market =====")
    log("%-42s %5s %9s %8s | %9s %8s %7s | %s" % ("input", "n", "slope/SD", "t", "coef/SD", "se", "t", "2025-26 out of sample: log-loss, bets at 3+ points (record, dogs, units)"))
    for k, name in FEATURES:
        pairs = [((f[k] - sc[k][0]) / sc[k][1], f["y"] - sigmoid(w0[0] + w0[1] * logit(f["p_raw"]))) for f in train + test if k in f]
        b, se = slope_se(pairs)
        X1, y1, _ = design(train, [k], sc)
        w1, se1 = logistic_fit(X1, y1)
        Xt1, yt1, kept = design(test, [k], sc)
        ll1 = logloss(Xt1, yt1, w1)
        bt = bet_test(kept, Xt1, w1, w0)
        log("%-42s %5d %+9.4f %8.2f | %+9.3f %8.3f %7.2f | %.4f (%+.4f) · %d-%d%s, %su" % (
            name, len(pairs), b, b / se if se else float("nan"), w1[2], se1[2], w1[2] / se1[2] if se1[2] else float("nan"),
            ll1, ll1 - ll_test0, bt["w"], bt["l"], (", %d dogs %d won" % (bt["dogs"], bt["dogs_won"])) if bt["dogs"] else "", "%+.1f" % bt["units"]))
    # everything the sheet has, together
    allk = [k for k, _ in FEATURES if k != "sd"]     # shots and goals carry the same signal; shots stay out of the joint model
    Xa, ya, _ = design(train, allk, sc)
    wa, sea = logistic_fit(Xa, ya)
    Xta, yta, kepta = design(test, allk, sc)
    lla = logloss(Xta, yta, wa)
    bta = bet_test(kepta, Xta, wa, w0)
    log("")
    log("===== all inputs together (shots left out), fitted on 2024-25, scored on 2025-26 =====")
    log("coefficients per SD: " + ", ".join("%s %+.3f (t %.1f)" % (k, wa[i + 2], wa[i + 2] / sea[i + 2] if sea[i + 2] else float("nan")) for i, k in enumerate(allk)))
    log("market's logit keeps a slope of %.3f beside them (1 = the inputs add nothing the price lacks)" % wa[1])
    log("log-loss 2025-26: %.4f against the market's %.4f (%+.4f); %d games" % (lla, ll_test0, lla - ll_test0, len(yta)))
    log("betting the side the model likes by 3+ points at the close: %d-%d, %+.1f units on %d bets (%+.1f%% a bet)%s" % (
        bta["w"], bta["l"], bta["units"], bta["n"], 100.0 * bta["units"] / bta["n"] if bta["n"] else 0.0,
        ("; %d of those were dogs, %d won" % (bta["dogs"], bta["dogs_won"])) if bta["dogs"] else ""))
    # the pick's own rule: the likeliest side by chance is the market favourite; the model only changes it when it flips the favourite
    flips = sum(1 for f, xi in zip(kepta, Xta) if (sigmoid(sum(a * b for a, b in zip(wa, xi))) >= 0.5) != (sigmoid(w0[0] + w0[1] * xi[1]) >= 0.5))
    log("games where the model's favourite differs from the market's: %d of %d" % (flips, len(kepta)))
    return {"ll0": ll_test0, "lla": lla, "bets": bta, "w0": w0, "wa": wa}


def selftest():
    import random
    random.seed(7)
    fails = []

    def check(name, cond):
        print(("  ok   " if cond else "  FAIL ") + name)
        if not cond:
            fails.append(name)
    check("implied and american round-trip", abs(american(implied(-150)) + 150) < 1e-9 and abs(american(implied(130)) - 130) < 1e-9 and abs(payout(-200) - 0.5) < 1e-12)
    check("nicknames", nick("Columbus Blue Jackets") == "Blue Jackets" and nick("Utah Hockey Club") == "Mammoth" and nick("Boston Bruins") == "Bruins")
    check("the season of a date", season_of("2025-10-08") == 2025 and season_of("2026-03-01") == 2025)
    # a synthetic league: a hidden strength the market half-prices with its own noise, and a feature that reads it
    def make(n):
        rows = []
        for i in range(n):
            s = random.gauss(0, 0.6)
            p_true = sigmoid(0.2 + s)
            p_mkt = sigmoid(0.2 + 0.5 * s + random.gauss(0, 0.35))
            y = 1 if random.random() < p_true else 0
            rows.append({"p_raw": p_mkt, "y": y, "hml": american(p_mkt), "margin": 1 if y else -1, "feat": s + random.gauss(0, 0.3), "noise": random.gauss(0, 1)})
        return rows
    tr, te = make(3000), make(3000)
    sc = scales(tr, ["feat", "noise"])
    X0, y0, _ = design(tr, [], sc)
    w0, _ = logistic_fit(X0, y0)
    X1, y1, _ = design(tr, ["feat"], sc)
    w1, se1 = logistic_fit(X1, y1)
    Xt0, yt0, _ = design(te, [], sc)
    Xt1, yt1, kept = design(te, ["feat"], sc)
    check("a real input earns a positive coefficient with a t above 4", w1[2] > 0 and w1[2] / se1[2] > 4)
    check("and lowers the out-of-sample log-loss", logloss(Xt1, yt1, w1) < logloss(Xt0, yt0, w0) - 0.005)
    X2, y2, _ = design(tr, ["noise"], sc)
    w2, se2 = logistic_fit(X2, y2)
    check("noise earns nothing (|t| under 2.5)", abs(w2[2] / se2[2]) < 2.5)
    bt = bet_test(kept, Xt1, w1, w0)
    check("betting the model's 3-point leans on a half-priced market makes money", bt["n"] > 100 and bt["units"] > 0)
    b, se = slope_se([(f["feat"], f["y"] - f["p_raw"]) for f in tr])
    check("the residual slope on the input is positive and clear", b > 0 and b / se > 4)
    print("all checks passed" if not fails else "%d FAILED" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
