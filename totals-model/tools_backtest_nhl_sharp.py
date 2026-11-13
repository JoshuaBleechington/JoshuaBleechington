"""The sharp line against the retail books, and the sheet against the sharp line.

    python3 tools_backtest_nhl_sharp.py FOLDER SEASON CLOSES.html [GOALIES_PRIOR.csv]

FOLDER holds odds-history-NHL-SEASON.json (slate.py odds-history: every book's total at
two moments a day, Pinnacle among them) and nhl-ledger-SEASON.json (the finals, with the
starters). CLOSES.html is KillerSports' closing-total page (tools_backtest_nhl.py), the
anchor the earlier backtests used, so the sheet's inputs can be read against both numbers.
GOALIES_PRIOR.csv is MoneyPuck's goalie file for the season before.

Four questions. (1) PINNACLE AGAINST THE RETAIL BOOKS: Pinnacle's total and prices give a
mean (fair_total); that mean prices every retail book's number (nhl_split); where a retail
price is cheaper than Pinnacle's chance by two, three or five points, bet it at that book
and grade it. At the close and at the opener. (2) THE BEST PRICE: how much shopping the
retail books gains over the carded book's price. (3) THE MOVE: whether the sheet's own
inputs (the goalies, the last ten, a backup in net) say which way the line will move from
the opener to the close -- closing line value, the honest measure of an edge. (4) THE SHEET
AGAINST PINNACLE: the residual of the final on Pinnacle's own mean, regressed on each input,
beside the same regression on the KillerSports close. Run 13 Oct 2026 on 2025-26, the night
the history pull came in ("let's make some magic"); CALLSHEET3.md has the table.
"""
import sys, os, json, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tools_backtest_nhl as B                    # noqa: E402
import tools_backtest_nhl_odds as O               # noqa: E402
from totals.fullgame import fair_total, implied   # noqa: E402
from totals import nhl as N                       # noqa: E402

SHARP = "pinnacle"
THRESH = (0.02, 0.03, 0.05)


def payout(a):
    return a / 100.0 if a > 0 else 100.0 / -a


def grade(side, line, tot):
    if abs(tot - line) < 1e-9:
        return "P"
    return "W" if ((tot > line) == (side == "over")) else "L"


class Rec:
    def __init__(self):
        self.w = self.l = self.p = 0
        self.units = 0.0

    def add(self, r, price):
        if r == "W":
            self.w += 1
            self.units += payout(price)
        elif r == "L":
            self.l += 1
            self.units -= 1
        else:
            self.p += 1

    def text(self):
        n = self.w + self.l
        return "%d-%d-%d (%s on %d) %+.1fu, %+.1f%% a bet" % (self.w, self.l, self.p, ("%.1f%%" % (100.0 * self.w / n)) if n else "-", n + self.p, self.units, 100.0 * self.units / (n + self.p) if n + self.p else 0.0)


def pin_mean(row):
    """Pinnacle's [line, over price, under price] -> the mean its prices imply."""
    return fair_total("NHL", float(row[0]), float(row[1]), float(row[2]))[0]


def p_over(mu, line):
    o, _p, u = N.nhl_split(float(line), mu)
    return o / (o + u) if o + u > 0 else 0.5


def snaps_before(g):
    return sorted((ts, s) for ts, s in (g.get("snaps") or {}).items() if ts < (g.get("start") or "9"))


def retail_rows(snap, books):
    return [(b, snap[b][0], snap[b][1], snap[b][2]) for b in books if b != SHARP and b in snap and snap[b][0] is not None]


def sharp_vs_retail(games, books, when, log):
    """Pinnacle's mean prices every retail number; bet the retail side cheaper than that chance."""
    recs = {t: {"all": Rec(), "same": Rec(), "diff": Rec()} for t in THRESH}
    own = Rec()
    n_pin = 0
    for g, tot in games:
        sb = snaps_before(g)
        if not sb:
            continue
        snap = sb[-1][1] if when == "close" else sb[0][1]
        pin = snap.get(SHARP)
        if not pin or pin[0] is None:
            continue
        n_pin += 1
        mu = pin_mean(pin)
        # Pinnacle's own juiced side at its own number and price
        if pin[1] != pin[2]:
            side = "over" if pin[1] < pin[2] else "under"
            own.add(grade(side, pin[0], tot), pin[1] if side == "over" else pin[2])
        best = None
        for b, line, op, up in retail_rows(snap, books):
            po = p_over(mu, line)
            for side, price, p in (("over", op, po), ("under", up, 1 - po)):
                e = p - implied(float(price))
                if best is None or e > best["edge"]:
                    best = {"edge": e, "side": side, "line": line, "price": price, "book": b, "same": abs(float(line) - float(pin[0])) < 1e-9}
        if not best:
            continue
        for t in THRESH:
            if best["edge"] >= t:
                r = grade(best["side"], best["line"], tot)
                recs[t]["all"].add(r, best["price"])
                recs[t]["same" if best["same"] else "diff"].add(r, best["price"])
    log("Pinnacle priced %d %ss. Its own juiced side, at its number and price: %s" % (n_pin, when, own.text()))
    for t in THRESH:
        log("  retail side cheaper than Pinnacle's chance by %d+ points: %s" % (round(t * 100), recs[t]["all"].text()))
        log("      at Pinnacle's number (a price gap): %s" % recs[t]["same"].text())
        log("      at a different number (a line gap): %s" % recs[t]["diff"].text())


def best_price_gain(games, books, log):
    gain, better, n = 0.0, 0, 0
    for g, tot in games:
        sb = snaps_before(g)
        if not sb:
            continue
        rows = retail_rows(sb[-1][1], books)
        if not rows:
            continue
        carded = rows[0]
        for side, idx in (("over", 2), ("under", 3)):
            cp = implied(float(carded[idx]))
            bp = min(implied(float(r[idx])) for r in rows if abs(float(r[1]) - float(carded[1])) < 1e-9)
            n += 1
            gain += cp - bp
            if cp - bp > 1e-9:
                better += 1
    log("the best retail price at the carded book's number beat the carded price on %d of %d sides, by %.2f points of implied chance on average (%.2f when it did)" % (
        better, n, 100.0 * gain / n if n else 0.0, 100.0 * gain / better if better else 0.0))


def move_and_sheet(games, books, feats, log):
    """What the sheet's inputs say about the move from the opener to the close, and the sheet against Pinnacle's mean."""
    byk = {(f["date"], B.NICK.get(f["home"], f["home"]), B.NICK.get(f["away"], f["away"])): f for f in feats}
    moves = []       # (feature row, move in goals, opener line, close line, tot)
    resid = []       # (feature row, tot - pinnacle mean, pinnacle mean)
    for g, tot in games:
        f = byk.get((g["gdate"], g["home"], g["away"]))
        if not f:
            continue
        sb = snaps_before(g)
        if len(sb) >= 2:
            o, c = retail_rows(sb[0][1], books), retail_rows(sb[-1][1], books)
            if o and c:
                moves.append((f, float(c[0][1]) - float(o[0][1]), float(o[0][1]), float(c[0][1]), tot))
        if sb and sb[-1][1].get(SHARP) and sb[-1][1][SHARP][0] is not None:
            mu = pin_mean(sb[-1][1][SHARP])
            resid.append((f, tot - mu, mu))
    log("")
    log("===== the move, opener to close, against the sheet's inputs (%d games with both) =====" % len(moves))
    log("%-34s %5s %10s %12s | %s" % ("lean", "n", "moved with", "moved against", "the lean bet at the opener's number, -110 assumed"))
    def lean_test(name, rows, side_of):
        w = a = 0
        rec = Rec()
        for f, mv, ol, cl, tot in rows:
            side = side_of(f)
            if side is None:
                continue
            s = 1 if side == "over" else -1
            if mv * s > 1e-9:
                w += 1
            elif mv * s < -1e-9:
                a += 1
            rec.add(grade(side, ol, tot), -110.0)
        log("%-34s %5d %10d %12d | %s" % (name, w + a + (rec.p + rec.w + rec.l - w - a), w, a, rec.text()))
    lean_test("goalies, lean of 0.12+ goals", moves, lambda f: ("over" if f["goalie_gap"] > 0 else "under") if "goalie_gap" in f and abs(f["goalie_gap"]) >= 0.12 else None)
    lean_test("last ten, 0.5+ off the line", moves, lambda f: ("over" if f["l10"] - f["line"] > 0 else "under") if "l10" in f and abs(f["l10"] - f["line"]) >= 0.5 else None)
    lean_test("one backup in net (the under)", moves, lambda f: "under" if f.get("backups") == 1 else None)
    lean_test("back to back (the under)", moves, lambda f: "under" if f.get("b2b") else None)
    up = sum(1 for m in moves if m[1] >= 0.5)
    dn = sum(1 for m in moves if m[1] <= -0.5)
    log("the line moved half a goal or more in %d of %d (%d up, %d down)" % (up + dn, len(moves), up, dn))
    log("")
    log("===== the sheet's inputs against Pinnacle's own mean at the close (%d games) =====" % len(resid))
    log("%-34s %5s %9s %7s %9s | %9s %7s %9s" % ("input", "n", "b vs Pin", "t", "weight", "b vs KS", "t", "weight"))
    for key, name in (("goalie_gap", "goalies (starters, blended)"), ("l10", "last-10 total avg"), ("goals_gap", "season goals rates"), ("shots_gap", "season shot rates"), ("special_gap", "special teams"), ("h2h", "head to head")):
        pin_pairs, ks_pairs = [], []
        for f, r, mu in resid:
            if key not in f:
                continue
            x = f[key] - mu if key in ("l10", "h2h") else f[key]
            xk = f[key] - f["anchor"] if key in ("l10", "h2h") else f[key]
            pin_pairs.append((x, r))
            ks_pairs.append((xk, f["resid"]))
        if len(pin_pairs) < 10:
            continue
        b1, se1 = O_slope(pin_pairs)
        b2, se2 = O_slope(ks_pairs)
        w = lambda b: (4 * b / (1 - b)) if b is not None and b < 1 else float("nan")
        log("%-34s %5d %+9.3f %7.2f %9.2f | %+9.3f %7.2f %9.2f" % (name, len(pin_pairs), b1, b1 / se1 if se1 else float("nan"), w(b1), b2, b2 / se2 if se2 else float("nan"), w(b2)))
    err_pin = B.avg([abs(r) for f, r, mu in resid])
    err_ks = B.avg([abs(f["resid"]) for f, r, mu in resid])
    log("mean absolute error of the mean against the final: Pinnacle %.3f, the KillerSports close %.3f" % (err_pin, err_ks))


def O_slope(pairs):
    xs = [a for a, b in pairs]
    ys = [b for a, b in pairs]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0 or n < 4:
        return 0.0, None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    s2 = sum((y - a - b * x) ** 2 for x, y in zip(xs, ys)) / (n - 2)
    return b, math.sqrt(s2 / sxx)


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    folder, season, closes = argv[0], argv[1], argv[2]
    hist = json.load(open(os.path.join(folder, "odds-history-NHL-%s.json" % season), encoding="utf-8"))
    ledger = os.path.join(folder, "nhl-ledger-%s.json" % season)
    led = json.load(open(ledger, encoding="utf-8"))
    books = hist.get("books") or []
    byk = {(g["date"], B.NICK.get(g["away"], g["away"]), B.NICK.get(g["home"], g["home"])): g for g in led.get("games") or [] if g.get("fa") is not None}
    games = []
    for g in hist.get("games", {}).values():
        f = byk.get((g["gdate"], g["away"], g["home"]))
        if f:
            games.append((g, f["fa"] + f["fh"]))
    print("%s: %d games on the feed joined to a final; books %s" % (season, len(games), ", ".join(books)))
    print("")
    print("===== Pinnacle against the retail books, at the CLOSE =====")
    sharp_vs_retail(games, books, "close", print)
    print("")
    print("===== Pinnacle against the retail books, at the OPENER =====")
    sharp_vs_retail(games, books, "open", print)
    print("")
    print("===== the best price =====")
    best_price_gain(games, books, print)
    j, led_all = B.load(ledger, closes)
    gp = B.goalie_prior(argv[3]) if len(argv) > 3 else None
    feats = B.features(j, led_all, None, gp)
    move_and_sheet(games, books, feats, print)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
