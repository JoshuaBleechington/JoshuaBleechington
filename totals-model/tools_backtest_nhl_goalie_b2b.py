"""The goalie on consecutive nights, against two seasons of closes.

    python3 tools_backtest_nhl_goalie_b2b.py FOLDER

FOLDER holds ledger2425r.json, ledger2526r.json (slate.py nhl-ledger --season --detail: every
game's starters with saves and shots) and q1.html, q2.html (KillerSports' closing totals and
home moneylines). For each game, each starting goalie is flagged TIRED when he also started
the day before, and his club is flagged on a back to back when it played the day before.
Prints: how often it happens; the tired goalie's save percentage against his own season rate;
the total's residual on the close and the over's record at the close, split by whether the
club on a back to back sent the same goalie back out or a different one; the sides (home
won against the market's chance) when the tired goalie is in the home or the away net; and
the first period. Run 13 Oct 2026 at the user's word ("run the consecutive-nights goalie
test tonight"). CALLSHEET3.md has the table.
"""
import sys, os, math, collections, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tools_backtest_nhl as B                 # noqa: E402
from totals.fullgame import fair_total, implied  # noqa: E402
from totals import nhl as N                     # noqa: E402

HOLD = 0.045


def yesterday(d):
    return (dt.date.fromisoformat(d) - dt.timedelta(days=1)).isoformat()


def rec_text(w, l, p=0):
    n = w + l
    return "%d-%d%s (%s on %d)" % (w, l, ("-%d" % p) if p else "", ("%.1f%%" % (100.0 * w / n)) if n else "-", n + p)


def run(folder, log=print):
    rows = []
    for led_f, q in (("ledger2425r.json", "q1.html"), ("ledger2526r.json", "q2.html")):
        j, led = B.load(os.path.join(folder, led_f), os.path.join(folder, q))
        starts = collections.defaultdict(set)        # pid -> dates started
        team_days = collections.defaultdict(set)     # team -> dates played
        season_sv = collections.defaultdict(lambda: [0.0, 0.0])   # pid -> [saves, shots] over the season
        for g in led:
            if not g.get("detail"):
                continue
            for side, t in (("a", g["away"]), ("h", g["home"])):
                pid = g.get("g%s_id" % side)
                if pid is not None:
                    starts[pid].add(g["date"])
                    sa, sv = g.get("g%s_sa" % side), g.get("g%s_sv" % side)
                    if sa is not None and sv is not None:
                        season_sv[pid][0] += sv
                        season_sv[pid][1] += sa
                team_days[t].add(g["date"])
        for g in j:
            if not g.get("detail") or g.get("ga_id") is None or g.get("gh_id") is None:
                continue
            d, y = g["date"], yesterday(g["date"])
            anchor, _ = fair_total("NHL", g["total"], -110.0, -110.0)
            tot = g["fa"] + g["fh"]
            r = {"season": led_f[6:10], "date": d, "line": g["total"], "anchor": anchor, "tot": tot, "resid": tot - anchor,
                 "p1": g["p1a"] + g["p1h"], "margin": g["fh"] - g["fa"], "hml": g.get("hml")}
            for side, team, pid in (("a", g["away"], g["ga_id"]), ("h", g["home"], g["gh_id"])):
                r[side + "_tired"] = y in starts[pid]
                r[side + "_b2b"] = y in team_days[team]
                sa, sv = g.get("g%s_sa" % side), g.get("g%s_sv" % side)
                r[side + "_sa"], r[side + "_sv"] = sa, sv
                tot_sv, tot_sa = season_sv[pid]
                # the goalie's own season rate with this game taken out, so the night is not scored against itself
                own = (tot_sv - (sv or 0)) / (tot_sa - (sa or 0)) if (tot_sa - (sa or 0)) >= 200 else None
                r[side + "_own"] = own
            rows.append(r)
    log("games with both starters known: %d (%s)" % (len(rows), ", ".join("%s %d" % (s, sum(1 for r in rows if r["season"] == s)) for s in sorted(set(r["season"] for r in rows)))))
    tired = [r for r in rows if r["a_tired"] or r["h_tired"]]
    both = [r for r in rows if r["a_tired"] and r["h_tired"]]
    b2b_same = [r for r in rows if (r["a_b2b"] and r["a_tired"]) or (r["h_b2b"] and r["h_tired"])]
    b2b_other = [r for r in rows if (r["a_b2b"] and not r["a_tired"]) or (r["h_b2b"] and not r["h_tired"])]
    log("a goalie on consecutive nights in %d games (%.1f%%), both goalies in %d; a club on a back to back sent the same goalie out in %d games and a different one in %d" % (
        len(tired), 100.0 * len(tired) / len(rows), len(both), len(b2b_same), len(b2b_other)))
    # 1. the tired goalie's own night against his own season rate
    log("")
    log("===== the tired goalie's save percentage =====")
    for label, pick in (("tired (started yesterday)", lambda r, s: r[s + "_tired"]), ("rested, club on a back to back", lambda r, s: r[s + "_b2b"] and not r[s + "_tired"]), ("everyone else", lambda r, s: not r[s + "_b2b"])):
        sv = sa = 0.0
        diffs = []
        for r in rows:
            for s in ("a", "h"):
                if pick(r, s) and r[s + "_sa"]:
                    sv += r[s + "_sv"]
                    sa += r[s + "_sa"]
                    if r[s + "_own"] is not None:
                        diffs.append(r[s + "_sv"] / r[s + "_sa"] - r[s + "_own"])
        if sa:
            se = math.sqrt(B.avg([(x - B.avg(diffs)) ** 2 for x in diffs]) / len(diffs)) if len(diffs) > 2 else 0
            log("  %-34s %5d starts: .%03.0f on %d shots; %+.4f against the goalie's own season rate (se %.4f, t %.1f)" % (
                label, len(diffs), 1000 * sv / sa, sa, B.avg(diffs), se, B.avg(diffs) / se if se else float("nan")))
    # 2. the total
    log("")
    log("===== the total at the close =====")
    def tot_line(label, v):
        if not v:
            return
        ov = sum(1 for r in v if r["tot"] > r["line"])
        un = sum(1 for r in v if r["tot"] < r["line"])
        res = B.avg([r["resid"] for r in v])
        se = math.sqrt(B.avg([(r["resid"] - res) ** 2 for r in v]) / len(v)) if len(v) > 2 else 0
        units = sum((100.0 / 110.0) if r["tot"] > r["line"] else (-1.0 if r["tot"] < r["line"] else 0.0) for r in v)
        log("  %-46s %5d games: residual %+.3f (se %.3f, t %.1f), mean close %.2f, the over %s, %+.1fu at -110" % (
            label, len(v), res, se, res / se if se else float("nan"), B.avg([r["line"] for r in v]), rec_text(ov, un, len(v) - ov - un), units))
    tot_line("a goalie on consecutive nights (either net)", tired)
    tot_line("  one tired goalie only", [r for r in tired if not (r["a_tired"] and r["h_tired"])])
    tot_line("  both goalies tired", both)
    for s in ("2024", "2025"):
        tot_line("  tired goalie, %s-%s" % (s, str(int(s) + 1)[2:]), [r for r in tired if r["season"] == s])
    tot_line("club on a back to back, SAME goalie out again", b2b_same)
    tot_line("club on a back to back, a DIFFERENT goalie", b2b_other)
    tot_line("no club on a back to back", [r for r in rows if not r["a_b2b"] and not r["h_b2b"]])
    # does the market move the total for a tired goalie? compare the close to the league mean
    log("  (the market's view: the close averages %.2f in tired-goalie games against %.2f elsewhere)" % (B.avg([r["line"] for r in tired]), B.avg([r["line"] for r in rows if not (r["a_tired"] or r["h_tired"])])))
    # 3. the sides
    log("")
    log("===== the sides: home won against the market's chance =====")
    def side_line(label, v):
        if not v:
            return
        v = [r for r in v if r["hml"] is not None]
        hw = sum(1 for r in v if r["margin"] > 0)
        pm = B.avg([min(max(implied(r["hml"]) - HOLD / 2, 0.02), 0.98) for r in v])
        log("  %-40s %5d games: home won %.1f%% against %.1f%% priced (%+.1f points)" % (label, len(v), 100.0 * hw / len(v), 100.0 * pm, 100.0 * (hw / len(v) - pm)))
    side_line("the AWAY goalie is tired, the home one is not", [r for r in rows if r["a_tired"] and not r["h_tired"]])
    side_line("the HOME goalie is tired, the away one is not", [r for r in rows if r["h_tired"] and not r["a_tired"]])
    side_line("neither goalie tired", [r for r in rows if not r["a_tired"] and not r["h_tired"]])
    # 4. the first period
    log("")
    log("===== the first period =====")
    for label, v in (("a goalie on consecutive nights", tired), ("no goalie tired", [r for r in rows if not (r["a_tired"] or r["h_tired"])])):
        pred = B.avg([N.P1_SHARE * N.reg_mean(r["anchor"]) for r in v])
        log("  %-34s %5d games: first-period goals %.3f against %.3f the close implies (%+.3f)" % (label, len(v), B.avg([r["p1"] for r in v]), pred, B.avg([r["p1"] for r in v]) - pred))
    return rows


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
