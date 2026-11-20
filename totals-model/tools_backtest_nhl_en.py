"""Each club's empty-net habits, against two seasons of closes.

    python3 tools_backtest_nhl_en.py FOLDER

FOLDER holds ledger2425r.json, ledger2526r.json (every game's empty-net goals by side and how
it ended) and q1.html, q2.html (KillerSports' closing totals). A club's PULL HABIT to date is
the share of its close regulation losses (one or two goals before the empty-netter) in which it
conceded an empty-net goal: the signature of a coach who pulls early and often. Its SCORED
rate is the empty-net goals it scores per game. For each game both clubs' habits to date, five
qualifying losses in, are read against the league's, and the lean is tested three ways: the
slope of the final's residual on the close, the slope of the game's own empty-net goals, and
the over's record when the lean is a quarter above or below the league. Run 13 Oct 2026 at the
user's word ("run the empty-net habits test too"). CALLSHEET3.md has the table.
"""
import sys, os, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tools_backtest_nhl as B                  # noqa: E402
from totals.fullgame import fair_total          # noqa: E402

MIN_LOSSES = 5
MIN_GAMES = 10


def slope_t(pairs):
    b, se = None, None
    xs = [a for a, c in pairs]
    ys = [c for a, c in pairs]
    n = len(xs)
    if n < 4:
        return None, None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None, None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    s2 = sum((y - a - b * x) ** 2 for x, y in zip(xs, ys)) / (n - 2)
    se = math.sqrt(s2 / sxx)
    return b, se


def run(folder, log=print):
    feats = []
    for led_f, q in (("ledger2425r.json", "q1.html"), ("ledger2526r.json", "q2.html")):
        j, led = B.load(os.path.join(folder, led_f), os.path.join(folder, q))
        # per team, ordered: (date, close loss?, conceded an EN goal in it?, EN scored, EN conceded)
        hist = collections.defaultdict(list)
        for g in sorted(led, key=lambda g: (g["date"], g["id"])):
            if g.get("fa") is None or g.get("ena") is None or g.get("enh") is None:
                continue
            ena, enh, end = g["ena"], g["enh"], g.get("end")
            for team, gf, ga, en_for, en_against in ((g["home"], g["fh"], g["fa"], enh, ena), (g["away"], g["fa"], g["fh"], ena, enh)):
                lost_reg = end == "REG" and gf < ga
                pre_margin = (ga - en_against) - gf          # the margin before the empty-netter(s) against
                close_loss = lost_reg and 1 <= pre_margin <= 2
                hist[team].append((g["date"], close_loss, en_against > 0 if close_loss else False, en_for, en_against, gf, ga))
        for g in j:
            d = g["date"]
            a, h = B.before(hist, g["away"], d), B.before(hist, g["home"], d)
            if len(a) < MIN_GAMES or len(h) < MIN_GAMES:
                continue
            def habit(rows):
                cl = [r for r in rows if r[1]]
                return (sum(1 for r in cl if r[2]) / float(len(cl)), len(cl)) if len(cl) >= MIN_LOSSES else (None, len(cl))
            ah, an = habit(a)
            hh, hn = habit(h)
            lg_rows = [r for t in hist for r in hist[t] if r[0] < d]
            lg_cl = [r for r in lg_rows if r[1]]
            if not lg_cl:
                continue
            lg_habit = sum(1 for r in lg_cl if r[2]) / float(len(lg_cl))
            lg_en = B.avg([r[3] for r in lg_rows])
            anchor, _ = fair_total("NHL", g["total"], -110.0, -110.0)
            lg_gpg = B.avg([r[5] + r[6] for r in lg_rows]) if lg_rows else 6.17
            f = {"season": "2024" if "2425" in led_f else "2025", "date": d, "line": g["total"], "anchor": anchor, "tot": g["fa"] + g["fh"], "en": g["ena"] + g["enh"],
                 "en_rate_gap": (B.avg([r[3] for r in a]) + B.avg([r[3] for r in h])) - 2 * lg_en,
                 "concede_gap": (B.avg([r[4] for r in a]) + B.avg([r[4] for r in h])) - 2 * lg_en,
                 # the scoring-rates lean the sheet now fades, so the EN rates can be read beside it
                 "rates_gap": (B.avg([r[5] for r in a]) + B.avg([r[6] for r in h])) / 2.0 + (B.avg([r[5] for r in h]) + B.avg([r[6] for r in a])) / 2.0 - lg_gpg}
            f["net_gap"] = f["concede_gap"] - f["en_rate_gap"]     # trailing late minus leading late: a weakness proxy
            if ah is not None and hh is not None:
                f["habit_gap"] = (ah + hh) / 2.0 - lg_habit
                f["habit_n"] = min(an, hn)
            feats.append(f)
    log("games with both clubs ten games in: %d; with both clubs' pull habit on five close losses or more: %d" % (len(feats), sum(1 for f in feats if "habit_gap" in f)))
    log("the league: %.3f empty-net goals a game over these games; at least one in %.0f%% of them" % (
        B.avg([f["en"] for f in feats]), 100.0 * B.avg([1.0 if f["en"] > 0 else 0.0 for f in feats])))
    log("")
    log("%-44s %5s | %9s %6s | %9s %6s | %s" % ("lean (both clubs, against the league)", "n", "b on tot", "t", "b on EN", "t", "the over at the close, lean a quarter above / below the league"))
    for key, name in (("habit_gap", "pull habit: EN conceded per close reg loss"), ("concede_gap", "EN goals conceded per game"), ("en_rate_gap", "EN goals scored per game")):
        v = [f for f in feats if key in f]
        if len(v) < 10:
            continue
        b1, se1 = slope_t([(f[key], f["tot"] - f["anchor"]) for f in v])
        b2, se2 = slope_t([(f[key], f["en"]) for f in v])
        hi = [f for f in v if f[key] >= 0.25 * (1 if key == "habit_gap" else 0.5)]
        lo = [f for f in v if f[key] <= -0.25 * (1 if key == "habit_gap" else 0.5)]
        def rec(rows):
            ov = sum(1 for f in rows if f["tot"] > f["line"])
            un = sum(1 for f in rows if f["tot"] < f["line"])
            return "%d-%d (%s on %d)" % (ov, un, ("%.1f%%" % (100.0 * ov / (ov + un))) if ov + un else "-", len(rows))
        log("%-44s %5d | %+9.3f %6.1f | %+9.3f %6.1f | above %s · below %s" % (
            name, len(v), b1, b1 / se1 if se1 else float("nan"), b2, b2 / se2 if se2 else float("nan"), rec(hi), rec(lo)))
    # by season, every lean
    log("")
    log("===== by season =====")
    for key, name in (("habit_gap", "pull habit"), ("concede_gap", "EN conceded per game"), ("en_rate_gap", "EN scored per game"), ("net_gap", "net: conceded minus scored")):
        for s in ("2024", "2025"):
            v = [f for f in feats if key in f and f["season"] == s]
            if len(v) < 10:
                continue
            b1, se1 = slope_t([(f[key], f["tot"] - f["anchor"]) for f in v])
            b2, se2 = slope_t([(f[key], f["en"]) for f in v])
            log("  %-28s %s-%s: %4d games, b on the total %+.3f (t %.1f), b on the game's EN goals %+.3f (t %.1f)" % (
                name, s, str(int(s) + 1)[2:], len(v), b1, b1 / se1 if se1 else float("nan"), b2, b2 / se2 if se2 else float("nan")))
    # the net EN lean beside the scoring-rates lean the sheet fades: does it survive?
    log("")
    log("===== the net EN lean beside the scoring-rates lean (two-variable fit of the residual) =====")
    v = [f for f in feats if "net_gap" in f and "rates_gap" in f]
    n = len(v)
    xs1 = [f["net_gap"] for f in v]
    xs2 = [f["rates_gap"] for f in v]
    ys = [f["tot"] - f["anchor"] for f in v]
    m1, m2, my = B.avg(xs1), B.avg(xs2), B.avg(ys)
    s11 = sum((x - m1) ** 2 for x in xs1)
    s22 = sum((x - m2) ** 2 for x in xs2)
    s12 = sum((x - m1) * (y - m2) for x, y in zip(xs1, xs2))
    s1y = sum((x - m1) * (y - my) for x, y in zip(xs1, ys))
    s2y = sum((x - m2) * (y - my) for x, y in zip(xs2, ys))
    det = s11 * s22 - s12 * s12
    if det > 0:
        b1 = (s22 * s1y - s12 * s2y) / det
        b2 = (s11 * s2y - s12 * s1y) / det
        resid = [y - my - b1 * (x1 - m1) - b2 * (x2 - m2) for x1, x2, y in zip(xs1, xs2, ys)]
        s2 = sum(r * r for r in resid) / (n - 3)
        se1 = math.sqrt(s2 * s22 / det)
        se2 = math.sqrt(s2 * s11 / det)
        rr = s12 / math.sqrt(s11 * s22)
        log("  %d games: net EN lean %+.3f (t %.1f) beside the scoring-rates lean %+.3f (t %.1f); the two leans correlate r = %+.2f" % (n, b1, b1 / se1, b2, b2 / se2, rr))
    b0, se0 = slope_t([(f["rates_gap"], f["tot"] - f["anchor"]) for f in v])
    log("  the scoring-rates lean alone on the same games: %+.3f (t %.1f)" % (b0, b0 / se0 if se0 else float("nan")))
    # does the habit persist? first half of a season against the second, per club
    log("")
    log("===== does a club's pull habit persist? (first half of the season against the second) =====")
    for led_f in ("ledger2425r.json", "ledger2526r.json"):
        import json
        led = json.load(open(os.path.join(folder, led_f)))["games"]
        per = collections.defaultdict(lambda: [[0, 0], [0, 0]])
        dates = sorted(set(g["date"] for g in led if g.get("date")))
        mid = dates[len(dates) // 2]
        for g in led:
            if g.get("fa") is None or g.get("ena") is None:
                continue
            for team, gf, ga, en_against in ((g["home"], g["fh"], g["fa"], g["ena"]), (g["away"], g["fa"], g["fh"], g["enh"])):
                if g.get("end") == "REG" and gf < ga and 1 <= (ga - en_against) - gf <= 2:
                    half = 0 if g["date"] < mid else 1
                    per[team][half][0] += 1
                    per[team][half][1] += 1 if en_against > 0 else 0
        pairs = [(v[0][1] / float(v[0][0]), v[1][1] / float(v[1][0])) for v in per.values() if v[0][0] >= MIN_LOSSES and v[1][0] >= MIN_LOSSES]
        b, se = slope_t(pairs)
        n = len(pairs)
        mx, my = B.avg([p[0] for p in pairs]), B.avg([p[1] for p in pairs])
        r = sum((p[0] - mx) * (p[1] - my) for p in pairs) / math.sqrt(sum((p[0] - mx) ** 2 for p in pairs) * sum((p[1] - my) ** 2 for p in pairs))
        log("  %s: %d clubs with five close losses in each half; correlation of the habit between halves r = %+.2f (slope %+.2f, t %.1f); the league conceded one in %.0f%% of close losses" % (
            led_f[6:10] + "-" + str(int(led_f[6:10]) + 1)[2:], n, r, b, b / se if se else float("nan"), 100.0 * (mx + my) / 2))
    return feats


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
