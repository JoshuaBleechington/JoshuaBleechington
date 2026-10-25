"""nbasim.py -- The Super Model's NBA game simulation (25 Oct 2026).

The user: "run the matchup 500 to 10,000 times to best determine how the game
will likely end, with confidence levels, tied into the model as a scored
metric." This module plays a game possession by possession, many times, and
reports the distributions and the probability of every market side.

The game, each run
  * Possessions: the two clubs' paces relative to the league give the game's
    pace, drawn with the spread the ledger measures, split across the quarters
    by the measured shares. A blowout speeds the fourth up; a close finish adds
    the fouling possessions explicitly (below).
  * A possession: a turnover, a trip to the line, or a shot (a three or a two
    at the club's shares and percentages), a miss rebounded by the offence at
    its rate for another try. The make rates are scaled so the possession's
    expected points equal the target: the club's offensive rating against the
    opponent's defensive rating, league-relative, shifted for home court, rest,
    who is out, the crew's whistle, and who is on the floor.
  * Who is on the floor: the starters' share of each quarter's minutes (the
    club's pattern from the play-by-play, else the league's) and the gap between
    starter-heavy and bench-heavy lineups move the target by the quarter; a
    blowout empties the benches for both sides.
  * The end of a close game: inside the fouling window the trailing side fouls,
    the leader shoots free throws, and the trailer takes quick threes, until the
    clock or the margin ends it. Overtime when level.
  * The crew: the officials' free-throw rate against the league scales the trip
    rate for both clubs.

Everything that moves a number here is a named constant with a measured or
a-priori source, and the backtest (tools_backtest_nba_sim.py) sets the shrink
each market's raw probability gets before it is shown. Pure standard library,
so it runs on the user's machine beside slate.py.
"""
import math
import random

VERSION = 1

# ---- the league's a-priori figures (2025-26 as the ledger measured them; the slate replaces what it can) ----
LEAGUE = {
    "ortg": 114.5,        # points per 100 possessions
    "pace": 99.0,         # possessions a team per 48 minutes
    "pace_sd": 2.0,       # a game's pace around its expectation (the replays: 4.2 made the total's spread 20.6 and 3.0 19.8, against the market's 18.2)
    "tov": 0.135,         # turnovers per possession
    "trip": 0.105,        # trips to the line per possession (two shots each)
    "ft": 0.782,          # free-throw percentage
    "a3": 0.420,          # share of field-goal attempts from three
    "p3": 0.362,          # three-point percentage
    "p2": 0.552,          # two-point percentage
    "oreb": 0.265,        # offensive rebound rate on a missed shot
    "home": 1.73,         # home margin, points a game (the ledger, two seasons)
    "q_share": [0.258, 0.252, 0.256, 0.234],   # each quarter's share of a game's possessions; the fourth's points land at 0.240 of the game once the fouling is added (the ledger, 2025-26)
    "starters": [0.673, 0.595, 0.656, 0.533],  # starters' share of the minutes by quarter (the play-by-play, 900 games of 2025-26)
    "bench_gap": 4.0,     # points per 100 between an all-starter lineup and an all-bench one
    "garbage": 16,        # margin at the start of the fourth that empties the benches (the play-by-play: starters 0.48 of the fourth at 16-20, 0.28 at 21+)
    "garbage_pace": 1.03, # the fourth's pace in garbage time (22.9 possessions against 22.3 in a close one)
    "garbage_ppp": -0.03, # both sides' points per possession in garbage time (1.19 against 1.22)
    "foul_window": 30.0,  # seconds left in which a trailing side within reach fouls
    "foul_reach": 9,      # the margin inside which it fouls
    "quick_a3": 0.80,     # the trailing side's three share in the window
    "quick_secs": 6.5,    # seconds a quick possession takes; a free-throw trip takes 3
    "rest_b2b": -1.0,     # points per 100 for a club on the second night of a back-to-back
    "ot_poss": 10.5,      # possessions a side in overtime
}

# ---- the shrink each market's raw probability gets: "worth" = 0.5 + (p - 0.5) * shrink ----
# tools_backtest_nba_sim.py, 2025-26 at 400 runs a game with the tendencies file, the sim's own view against the closing total
# and spread: the slope of does on says was +0.04 for the total (t 0.2; a 70%+ call landed 52.0%), +0.02 for the spread (t 0.1;
# a 70%+ call 44.4%), +0.97 for the moneyline (t 7.1; a 70%+ call 79.9% at says 77.4%). The close already carries the ratings,
# so a total or spread call is worth a coin whatever it says; the win chance is nearly true.
# The period lines (26 Oct 2026, the user's pull: 588 games of 2025-26 with the first half, the quarters and the team totals at
# the close; 473 of 2024-25 with the first half): the FIRST HALF is a coin from either view (anchored +0.08 then -0.30, the own
# view +0.71 then +0.18; the 2025-26 own-view 70%+ band's 53-35 did not come back in 2024-25's 21-23); the FIRST QUARTER,
# anchored, +0.50 (t 1.0, one season, +16u at 60-65 on 126 games); the TEAM TOTALS, anchored, +0.65 and +0.62 (t 1.2 and 1.0),
# with the calls landing 60.7% at home and 53.9% away over 588 games, because the book's team-total line sits off the number
# the game's total and spread imply: a line a point or more above the implied went under 64.9% of the time (home) and 59.4%
# (away), a point or more below went over 63.5% and 55.8%. One season; the 2024-25 team totals are the next pull.
SHRINK = {"total": 0.05, "h1": 0.1, "spread": 0.0, "ml": 0.97, "team": 0.65, "quarter": 0.5}
BANDS = [(0.70, "STRONG"), (0.65, "BET"), (0.60, "LEAN")]


def band(p):
    """The confidence band for the likelier side's probability."""
    c = max(p, 1.0 - p)
    for cut, name in BANDS:
        if c >= cut:
            return name
    return "no call"


def shrink(p, market):
    k = SHRINK.get(market, 1.0)
    return 0.5 + (p - 0.5) * k


# ---- a possession's points, exactly, from a club's profile ----------------------
def _trip_dist(ft):
    """Two free throws: points 0, 1, 2."""
    return {0: (1 - ft) ** 2, 1: 2 * ft * (1 - ft), 2: ft * ft}


def possession_dist(prof, scale=1.0, depth=3):
    """The distribution of points on one possession: a turnover, a trip to the
    line, or a shot with offensive rebounds for up to `depth` tries; the make
    rates scaled by `scale`."""
    tov, trip, ft, a3, oreb = prof["tov"], prof["trip"], prof["ft"], prof["a3"], prof["oreb"]
    p3, p2 = min(0.95, prof["p3"] * scale), min(0.95, prof["p2"] * scale)
    out = {0: tov}
    live = 1.0 - tov
    tr = _trip_dist(ft)
    for k, v in tr.items():
        out[k] = out.get(k, 0.0) + live * trip * v
    shot = live * (1.0 - trip)
    for _ in range(depth):
        made3, made2 = shot * a3 * p3, shot * (1 - a3) * p2
        out[3] = out.get(3, 0.0) + made3
        out[2] = out.get(2, 0.0) + made2
        missed = shot - made3 - made2
        again = missed * oreb
        out[0] = out.get(0, 0.0) + (missed - again)
        shot = again
    out[0] = out.get(0, 0.0) + shot   # a third miss ends it
    return out


def _mean(dist):
    return sum(k * v for k, v in dist.items())


def possession_table(prof, target_ppp):
    """Cumulative thresholds for points 0..3 whose expectation is target_ppp:
    the club's shot mix with its make rates scaled to fit. Returns (cum, pts)."""
    lo, hi = 0.5, 1.8
    for _ in range(28):
        mid = (lo + hi) / 2.0
        if _mean(possession_dist(prof, mid)) < target_ppp:
            lo = mid
        else:
            hi = mid
    d = possession_dist(prof, (lo + hi) / 2.0)
    pts = sorted(d)
    cum, acc = [], 0.0
    for k in pts:
        acc += d[k]
        cum.append(acc)
    cum[-1] = 1.0
    return cum, pts


def _draw(table, r):
    cum, pts = table
    for i, c in enumerate(cum):
        if r < c:
            return pts[i]
    return pts[-1]


# ---- the game -------------------------------------------------------------------
GRID = 0.01       # the step of the points-per-possession shift the tables are built on
GRID_N = 12       # tables from -12 to +12 steps a side


class Side(object):
    """One club in one game: its profile, its base target and its tables."""

    def __init__(self, prof, ppp_base):
        self.prof = prof
        self.base = ppp_base
        self.tables = {}

    def table(self, shift):
        k = max(-GRID_N, min(GRID_N, int(round(shift / GRID))))
        t = self.tables.get(k)
        if t is None:
            t = self.tables[k] = possession_table(self.prof, self.base + k * GRID)
            self.tables[k] = t
        return t


def _pace_game(a, h, lg):
    return a["pace"] + h["pace"] - lg["pace"]


def _target(off, dfn, lg, home_side):
    """Points per possession for `off` against `dfn`: league-relative ratings,
    home court, rest, absences and the crew."""
    ppp = (off["ortg"] + dfn["drtg"] - lg["ortg"]) / 100.0
    ppp += (lg["home"] / 2.0 if home_side else -lg["home"] / 2.0) / (lg["pace"])   # the home margin, half a side, per possession
    if off.get("b2b"):
        ppp += lg["rest_b2b"] / 100.0
    ppp += (off.get("out_adj") or 0.0) / 100.0
    ppp -= (dfn.get("out_dadj") or 0.0) / 100.0
    return ppp


def _starters_share(prof, lg, q):
    s = prof.get("starters") or lg["starters"]
    return s[q] if q < len(s) else s[-1]


def sim_game(setup, rng):
    """One game. Returns {qa, qh, ota, oth, fa, fh}."""
    lg, a, h = setup["league"], setup["away"], setup["home"]
    sides = setup["_sides"]
    pace = max(80.0, rng.gauss(_pace_game(a, h, lg), lg["pace_sd"]))
    q_share = lg["q_share"]
    qa, qh = [0, 0, 0, 0], [0, 0, 0, 0]
    sa = sh = 0
    gap = lg["bench_gap"] / 100.0
    mean_st = sum(lg["starters"]) / 4.0
    for q in range(4):
        n = pace * q_share[q] + rng.gauss(0.0, 1.0)
        margin = sh - sa
        garbage = q == 3 and abs(margin) >= lg["garbage"]
        if garbage:
            n *= lg["garbage_pace"]
        n = max(12, int(round(n)))
        # who is on the floor this quarter, each side
        sh_a = (0.2 if garbage else _starters_share(a, lg, q)) - mean_st
        sh_h = (0.2 if garbage else _starters_share(h, lg, q)) - mean_st
        shift_a = sh_a * gap + (lg["garbage_ppp"] if garbage else 0.0)
        shift_h = sh_h * gap + (lg["garbage_ppp"] if garbage else 0.0)
        ta, th = sides[0].table(shift_a), sides[1].table(shift_h)
        secs = 720.0 / n
        clock = 720.0
        i = 0
        while i < n:
            # a possession each, the away side first (who gets the extra one is noise)
            pa_ = _draw(ta, rng.random())
            qa[q] += pa_
            sa += pa_
            ph_ = _draw(th, rng.random())
            qh[q] += ph_
            sh += ph_
            clock -= secs
            i += 1
            if q == 3 and clock <= lg["foul_window"]:
                break
        if q == 3 and clock > 0:
            # the end of the game: if the margin is within reach, the trailer fouls
            qa[q], qh[q], sa, sh = _endgame(setup, rng, clock, qa[q], qh[q], sa, sh, ta, th)
    ota = oth = 0
    rounds = 0
    while sa == sh and rounds < 4:
        rounds += 1
        n = max(6, int(round(rng.gauss(lg["ot_poss"], 1.2))))
        ta, th = sides[0].table(0.0), sides[1].table(0.0)
        clock, secs = 300.0, 300.0 / n
        oa = oh = 0
        i = 0
        while i < n:
            pa_ = _draw(ta, rng.random()); oa += pa_; sa += pa_
            ph_ = _draw(th, rng.random()); oh += ph_; sh += ph_
            clock -= secs
            i += 1
            if clock <= lg["foul_window"]:
                break
        if clock > 0:
            oa, oh, sa, sh = _endgame(setup, rng, clock, oa, oh, sa, sh, ta, th)
        ota += oa
        oth += oh
    return {"qa": qa, "qh": qh, "ota": ota, "oth": oth, "fa": sa, "fh": sh}


def _endgame(setup, rng, clock, pa_q, ph_q, sa, sh, ta, th):
    """The last seconds: normal possessions while the margin is out of reach or
    level; inside reach the trailer fouls and shoots quick threes."""
    lg, a, h = setup["league"], setup["away"], setup["home"]
    quick = setup["_quick"]
    while clock > 0:
        margin = sh - sa
        if clock <= 24.0 and abs(margin) <= 3:
            # the last possession (the replay: the sim found overtime 2.9% of the time against the ledger's 4.4%, because a level
            # game kept trading possessions): level, one side holds for the last shot; down one to three, the trailer takes one try
            if margin == 0:
                trailer_home = rng.random() < 0.5
                tq = th if trailer_home else ta
            else:
                trailer_home = margin < 0
                tq = quick[1] if trailer_home else quick[0]
            pts = _draw(tq, rng.random())
            if trailer_home:
                ph_q += pts; sh += pts
            else:
                pa_q += pts; sa += pts
            break
        if margin == 0 or abs(margin) > lg["foul_reach"]:
            # play it out: one possession each at the game's pace
            secs = 14.0
            pa_ = _draw(ta, rng.random()); pa_q += pa_; sa += pa_
            ph_ = _draw(th, rng.random()); ph_q += ph_; sh += ph_
            clock -= secs * 2
            continue
        trailer_home = margin < 0
        # the trailer's quick possession
        tq = quick[1] if trailer_home else quick[0]
        pts = _draw(tq, rng.random())
        if trailer_home:
            ph_q += pts; sh += pts
        else:
            pa_q += pts; sa += pts
        clock -= lg["quick_secs"]
        if clock <= 0:
            break
        margin = sh - sa
        if margin == 0 or abs(margin) > lg["foul_reach"]:
            continue
        # the leader is fouled: two free throws
        ft = (a if trailer_home else h)["ft"]
        made = (1 if rng.random() < ft else 0) + (1 if rng.random() < ft else 0)
        if trailer_home:
            pa_q += made; sa += made
        else:
            ph_q += made; sh += made
        clock -= 3.0
    return pa_q, ph_q, sa, sh


def prepare(setup):
    """Build the per-game tables once; returns the setup with them attached."""
    lg, a, h = setup["league"], setup["away"], setup["home"]
    ft_factor = float(setup.get("ft_factor") or 1.0)
    pa, ph = dict(a), dict(h)
    pa["trip"] = a["trip"] * ft_factor
    ph["trip"] = h["trip"] * ft_factor
    base_a = _target(a, h, lg, False) + (pa["trip"] - a["trip"]) * 2 * a["ft"]   # the crew's extra trips add their points on top
    base_h = _target(h, a, lg, True) + (ph["trip"] - h["trip"]) * 2 * h["ft"]
    setup["_sides"] = [Side(pa, base_a), Side(ph, base_h)]
    qa, qh = dict(pa), dict(ph)
    qa["a3"] = qh["a3"] = lg["quick_a3"]
    qa["trip"] = qh["trip"] = 0.02
    setup["_quick"] = [possession_table(qa, base_a - 0.05), possession_table(qh, base_h - 0.05)]
    setup["_base"] = [base_a, base_h]
    return setup


def simulate(setup, n=5000, seed=None):
    """Run the game n times. Returns the raw results list and a summary."""
    rng = random.Random(seed)
    prepare(setup)
    out = [sim_game(setup, rng) for _ in range(n)]
    return out


def anchor_to_lines(setup, total, spread, n=1500, rounds=3, seed=11):
    """The market-anchored game (25 Oct 2026): the first replay showed the
    sim's own total carries nothing the close does not (slope 0.02), so for
    the derivative markets the distribution is centred on the market: each
    side's base points per possession is nudged until the sim's mean total
    equals `total` and its mean margin equals -`spread` (the home side's).
    The shape (halves, quarters, team totals, overtime) stays the sim's."""
    if total is None:
        return setup
    prepare(setup)
    lg, a, h = setup["league"], setup["away"], setup["home"]
    sp = float(spread) if spread is not None else None
    want_h = (total - sp) / 2.0 if sp is not None else None
    want_a = (total + sp) / 2.0 if sp is not None else None
    for r in range(rounds):
        rng = random.Random(seed + r)
        res = [sim_game(setup, rng) for _ in range(n)]
        ma = sum(x["fa"] for x in res) / float(n)
        mh = sum(x["fh"] for x in res) / float(n)
        poss = _pace_game(a, h, lg)
        if sp is None:
            da = dh = (total - ma - mh) / 2.0 / poss
        else:
            da, dh = (want_a - ma) / poss, (want_h - mh) / poss
        sides = setup["_sides"]
        sides[0].base += da
        sides[1].base += dh
        sides[0].tables, sides[1].tables = {}, {}
        qa, qh = dict(sides[0].prof), dict(sides[1].prof)
        qa["a3"] = qh["a3"] = lg["quick_a3"]
        qa["trip"] = qh["trip"] = 0.02
        setup["_quick"] = [possession_table(qa, sides[0].base - 0.05), possession_table(qh, sides[1].base - 0.05)]
    setup["_anchored"] = {"total": total, "spread": sp}
    return setup


def simulate_anchored(setup, total, spread, n=5000, seed=None):
    """Runs of the market-anchored game; prepare() is not run again."""
    anchor_to_lines(setup, total, spread)
    rng = random.Random(seed)
    return [sim_game(setup, rng) for _ in range(n)]


# ---- the summary: distributions and every market's probability ---------------------
def _q(xs, p):
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * p
    f, c = int(math.floor(k)), int(math.ceil(k))
    return s[f] if f == c else s[f] + (s[c] - s[f]) * (k - f)


def _desc(xs):
    n = len(xs)
    m = sum(xs) / float(n)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else 0.0
    return {"mean": round(m, 2), "median": _q(xs, 0.5), "p25": _q(xs, 0.25), "p75": _q(xs, 0.75), "sd": round(sd, 2)}


def _over(xs, line):
    """P(over), P(push) for a total-style line."""
    if line is None:
        return None, None
    n = float(len(xs))
    return sum(1 for x in xs if x > line) / n, sum(1 for x in xs if x == line) / n


def summarize(results, lines=None, n_label=None):
    """lines: {total, h1, spread (home, negative when favoured), away_total, home_total}."""
    lines = lines or {}
    tot = [r["fa"] + r["fh"] for r in results]
    reg = [sum(r["qa"]) + sum(r["qh"]) for r in results]
    h1 = [r["qa"][0] + r["qa"][1] + r["qh"][0] + r["qh"][1] for r in results]
    h2 = [r["qa"][2] + r["qa"][3] + r["qh"][2] + r["qh"][3] for r in results]
    qs = [[r["qa"][k] + r["qh"][k] for r in results] for k in range(4)]
    margin = [r["fh"] - r["fa"] for r in results]
    at, ht = [r["fa"] for r in results], [r["fh"] for r in results]
    s = {"runs": len(results), "total": _desc(tot), "h1": _desc(h1), "h2": _desc(h2), "quarters": [_desc(x) for x in qs],
         "margin": _desc(margin), "away": _desc(at), "home": _desc(ht),
         "home_win": sum(1 for m in margin if m > 0) / float(len(margin)), "ot": sum(1 for r in results if r["ota"] or r["oth"]) / float(len(results)),
         "q_share": [round(sum(x) / float(sum(reg)), 4) for x in qs] if sum(reg) else None, "markets": {}}
    mk = s["markets"]
    if lines.get("total") is not None:
        po, pp = _over(tot, lines["total"])
        mk["total"] = _market("total", lines["total"], po, pp, "OVER", "UNDER")
    if lines.get("h1") is not None:
        po, pp = _over(h1, lines["h1"])
        mk["h1"] = _market("h1", lines["h1"], po, pp, "OVER", "UNDER")
    if lines.get("spread") is not None:
        # the home side covers when margin + spread > 0 (spread negative for a home favourite)
        sp = lines["spread"]
        cov = sum(1 for m in margin if m + sp > 0) / float(len(margin))
        push = sum(1 for m in margin if m + sp == 0) / float(len(margin))
        mk["spread"] = _market("spread", sp, cov, push, "HOME", "AWAY")
    mk["ml"] = _market("ml", None, s["home_win"], 0.0, "HOME", "AWAY")
    for key, xs, lab in (("away_total", at, "away"), ("home_total", ht, "home")):
        if lines.get(key) is not None:
            po, pp = _over(xs, lines[key])
            mk[key] = _market("team", lines[key], po, pp, "OVER", "UNDER")
    for k in range(4):
        if lines.get("q%d" % (k + 1)) is not None:
            po, pp = _over(qs[k], lines["q%d" % (k + 1)])
            mk["q%d" % (k + 1)] = _market("quarter", lines["q%d" % (k + 1)], po, pp, "OVER", "UNDER")
    return s


def _market(kind, line, p_first, push, first, second):
    """A market's call: the likelier side, its probability (pushes set aside), raw and shrunk, the band."""
    live = max(1e-9, 1.0 - (push or 0.0))
    p = p_first / live
    side, prob = (first, p) if p >= 0.5 else (second, 1.0 - p)
    cal = shrink(prob, kind)
    return {"line": line, "side": side, "p_raw": round(prob, 4), "p": round(cal, 4), "push": round(push or 0.0, 4), "band": band(prob), "first": first}   # the band is the sim's own chance; "p" is what it is worth


# ---- club profiles from the ledger -------------------------------------------------
PACE_FT = 0.44
K_PRIOR = 15.0        # games of this season that weigh as much as last season's whole profile
PROFILE_KEYS = ("ortg", "drtg", "pace", "tov", "trip", "ft", "a3", "p3", "p2", "oreb")


def _team_game_lines(g):
    """(away line, home line) from a ledger game: possessions, points, the box
    sums the profile needs; shooting from the player lines when they are full."""
    out = []
    for side, pl_key, pts, opts in (("away", "pa", g.get("fa"), g.get("fh")), ("home", "ph", g.get("fh"), g.get("fa"))):
        s = g.get("sa" if side == "away" else "sh") or {}
        if not s or pts is None:
            return None
        poss = s["fga"] - s["oreb"] + s["tov"] + PACE_FT * s["fta"]
        line = {"pts": pts, "opts": opts, "poss": poss, "fga": s["fga"], "fta": s["fta"], "oreb": s["oreb"], "tov": s["tov"], "min": s.get("min") or 240.0,
                "fgm": 0, "ftm": 0, "tpm": 0, "tpa": 0, "full": False}
        players = g.get(pl_key) or []
        if players and all(len(p) >= 16 for p in players):
            line["full"] = True
            for p in players:
                line["tpm"] += p[8] or 0
                line["fgm"] += p[14] or 0
                line["ftm"] += p[15] or 0
        tpa = (g.get("tpa") or {}).get(side)     # from the play-by-play pass when it has run
        if tpa:
            line["tpa"] = tpa
        out.append(line)
    return out


def _acc_profile(acc, line, opp_poss):
    acc["n"] += 1
    for k in ("pts", "opts", "poss", "fga", "fta", "oreb", "tov", "fgm", "ftm", "tpm", "tpa", "min"):
        acc[k] += line.get(k) or 0
    acc["oposs"] += opp_poss
    acc["full"] += 1 if line.get("full") else 0


def _new_acc():
    return {"n": 0, "pts": 0, "opts": 0, "poss": 0.0, "oposs": 0.0, "fga": 0, "fta": 0, "oreb": 0, "tov": 0, "fgm": 0, "ftm": 0, "tpm": 0, "tpa": 0, "min": 0.0, "full": 0}


def _profile_of(acc, lg):
    """A club's profile from its accumulated lines; shooting falls back to the
    league's when the lines are not full or the three-point attempts are unknown."""
    if not acc["n"] or acc["poss"] <= 0:
        return None
    p = {"n": acc["n"], "ortg": 100.0 * acc["pts"] / acc["poss"], "drtg": 100.0 * acc["opts"] / acc["oposs"],
         "pace": acc["poss"] * 48.0 / (acc["min"] / 5.0), "tov": acc["tov"] / acc["poss"], "trip": PACE_FT * acc["fta"] / acc["poss"],
         "ft": (acc["ftm"] / float(acc["fta"])) if acc["full"] == acc["n"] and acc["fta"] else lg["ft"]}
    misses = acc["fga"] - acc["fgm"] if acc["full"] == acc["n"] else acc["fga"] * (1.0 - 0.47)
    p["oreb"] = acc["oreb"] / float(misses) if misses > 0 else lg["oreb"]
    if acc["full"] == acc["n"] and acc["tpa"]:
        p["a3"] = acc["tpa"] / float(acc["fga"])
        p["p3"] = acc["tpm"] / float(acc["tpa"])
        twos = acc["fga"] - acc["tpa"]
        p["p2"] = (acc["fgm"] - acc["tpm"]) / float(twos) if twos > 0 else lg["p2"]
    elif acc["full"] == acc["n"] and acc["fga"]:
        tpa = lg["a3"] * acc["fga"]      # the attempts are not in the box line: the league's share, the club's makes
        p["a3"] = lg["a3"]
        p["p3"] = min(0.6, acc["tpm"] / tpa) if tpa else lg["p3"]
        twos = acc["fga"] - tpa
        p["p2"] = min(0.75, (acc["fgm"] - acc["tpm"]) / twos) if twos > 0 else lg["p2"]
    else:
        p["a3"], p["p3"], p["p2"] = lg["a3"], lg["p3"], lg["p2"]
    return p


def profiles_from_ledger(games, date_iso, prior_games=None, league=None, k_prior=K_PRIOR, tend=None):
    """Every club's profile before date_iso: this season's lines blended with
    last season's whole profile by n/(n+k). `tend` (tools_nba_tendencies.py's
    file) supplies what the box score does not carry: the three-point share
    and percentages, and each club's starters' share of the quarters. Returns
    {"league": {...}, "teams": {ab: profile}, "last": {ab: last game date}}."""
    lg = dict(league or LEAGUE)
    tl = (tend or {}).get("league") or {}
    if _sane_mix(tl):
        lg["a3"], lg["p3"], lg["p2"] = tl["a3"], tl["p3"], tl["p2"]
    if tl.get("starters_q") and len(tl["starters_q"]) == 4 and all(0.2 <= x <= 0.95 for x in tl["starters_q"]):
        lg["starters"] = tl["starters_q"]
    this, last_date = {}, {}
    lg_acc = _new_acc()
    for g in sorted(games or [], key=lambda g: (g.get("date") or "", g.get("id") or "")):
        if (g.get("date") or "") >= date_iso or not g.get("detail"):
            continue
        lines = _team_game_lines(g)
        if not lines:
            continue
        for ab, line, other in ((g["away"], lines[0], lines[1]), (g["home"], lines[1], lines[0])):
            _acc_profile(this.setdefault(ab, _new_acc()), line, other["poss"])
            _acc_profile(lg_acc, line, other["poss"])
            last_date[ab] = g["date"]
    if lg_acc["n"] >= 40:
        lp = _profile_of(lg_acc, lg)
        for k in ("ortg", "pace", "tov", "trip", "ft", "oreb"):
            lg[k] = lp[k]
        if lg_acc["full"] == lg_acc["n"] and lg_acc["tpa"]:
            lg["a3"], lg["p3"], lg["p2"] = lp["a3"], lp["p3"], lp["p2"]
    prior = {}
    if prior_games:
        p_acc = {}
        for g in prior_games:
            if not g.get("detail"):
                continue
            lines = _team_game_lines(g)
            if not lines:
                continue
            _acc_profile(p_acc.setdefault(g["away"], _new_acc()), lines[0], lines[1]["poss"])
            _acc_profile(p_acc.setdefault(g["home"], _new_acc()), lines[1], lines[0]["poss"])
        for ab, acc in p_acc.items():
            pr = _profile_of(acc, lg)
            if pr:
                prior[ab] = pr
    teams = {}
    for ab in set(list(this.keys()) + list(prior.keys())):
        t = _profile_of(this[ab], lg) if ab in this else None
        pr = prior.get(ab)
        if t and pr:
            w = t["n"] / (t["n"] + k_prior)
            prof = {k: w * t[k] + (1 - w) * pr[k] for k in PROFILE_KEYS}
            prof["n"] = t["n"]
        elif t:
            w = t["n"] / (t["n"] + k_prior)
            prof = {k: w * t[k] + (1 - w) * lg[k if k not in ("drtg",) else "ortg"] for k in PROFILE_KEYS}
            prof["n"] = t["n"]
        else:
            prof = dict(pr)
            prof["n"] = 0
        prof["ab"] = ab
        tt = ((tend or {}).get("teams") or {}).get(ab) or {}
        if _sane_mix(tt) and tt.get("games", 0) >= 10 and not (t and this[ab]["tpa"]):
            prof["a3"], prof["p3"], prof["p2"] = tt["a3"], tt["p3"], tt["p2"]   # the club's own split, from the play-by-play
        if tt.get("starters_q") and len(tt["starters_q"]) == 4 and tt.get("games", 0) >= 10:
            prof["starters"] = tt["starters_q"]
        teams[ab] = prof
    return {"league": lg, "teams": teams, "last": last_date}


# ---- histograms, for the page: P(over any line) without re-running anything ----
def histogram(xs):
    """{"lo": first value, "c": counts from lo upward} over integer outcomes."""
    if not xs:
        return None
    lo, hi = int(min(xs)), int(max(xs))
    c = [0] * (hi - lo + 1)
    for x in xs:
        c[int(x) - lo] += 1
    return {"lo": lo, "c": c}


def histograms(results):
    """The page's set: the total, the halves, the quarters, the margin, the team totals."""
    return {"total": histogram([r["fa"] + r["fh"] for r in results]),
            "h1": histogram([r["qa"][0] + r["qa"][1] + r["qh"][0] + r["qh"][1] for r in results]),
            "h2": histogram([r["qa"][2] + r["qa"][3] + r["qh"][2] + r["qh"][3] for r in results]),
            "q": [histogram([r["qa"][k] + r["qh"][k] for r in results]) for k in range(4)],
            "margin": histogram([r["fh"] - r["fa"] for r in results]),
            "away": histogram([r["fa"] for r in results]), "home": histogram([r["fh"] for r in results]),
            "ot": round(sum(1 for r in results if r["ota"] or r["oth"]) / float(len(results)), 4)}


def hist_over(h, line):
    """(P over, P push) for a line against a histogram."""
    if not h or line is None:
        return None, None
    n = float(sum(h["c"]))
    over = sum(c for i, c in enumerate(h["c"]) if h["lo"] + i > line)
    push = sum(c for i, c in enumerate(h["c"]) if h["lo"] + i == line)
    return over / n, push / n


def hist_quantile(h, p):
    if not h:
        return None
    n = sum(h["c"])
    acc = 0
    for i, c in enumerate(h["c"]):
        acc += c
        if acc >= p * n:
            return h["lo"] + i
    return h["lo"] + len(h["c"]) - 1


def _sane_mix(d):
    """A shot mix worth using: a three share between a fifth and two thirds, percentages in range."""
    try:
        return 0.20 <= float(d.get("a3")) <= 0.67 and 0.25 <= float(d.get("p3")) <= 0.50 and 0.40 <= float(d.get("p2")) <= 0.70
    except (TypeError, ValueError):
        return False


def rest_flags(last_date, ab, date_iso):
    """Back-to-back: a game yesterday."""
    d = last_date.get(ab)
    if not d:
        return {"b2b": False, "rest": None}
    try:
        import datetime as _dt
        days = (_dt.date.fromisoformat(date_iso) - _dt.date.fromisoformat(d)).days
    except ValueError:
        return {"b2b": False, "rest": None}
    return {"b2b": days == 1, "rest": days}


def setup_from_profiles(prof, away_ab, home_ab, date_iso, ft_factor=1.0, out_adj=None):
    """A game's setup for simulate() from profiles_from_ledger's output."""
    a, h = prof["teams"].get(away_ab), prof["teams"].get(home_ab)
    if not a or not h:
        return None
    a, h = dict(a), dict(h)
    a.update(rest_flags(prof["last"], away_ab, date_iso))
    h.update(rest_flags(prof["last"], home_ab, date_iso))
    a["out_adj"] = (out_adj or {}).get("away", 0.0)
    h["out_adj"] = (out_adj or {}).get("home", 0.0)
    return {"league": prof["league"], "away": a, "home": h, "ft_factor": ft_factor}


# ---- a demonstration setup, for the self-test and the page's example -------------
def demo_setup():
    lg = dict(LEAGUE)
    away = {"ab": "BOS", "ortg": 118.0, "drtg": 110.5, "pace": 100.5, "tov": 0.125, "trip": 0.10, "ft": 0.81, "a3": 0.48, "p3": 0.37, "p2": 0.56, "oreb": 0.24, "b2b": False, "out_adj": 0.0}
    home = {"ab": "NYK", "ortg": 115.5, "drtg": 112.0, "pace": 99.0, "tov": 0.13, "trip": 0.11, "ft": 0.78, "a3": 0.40, "p3": 0.36, "p2": 0.55, "oreb": 0.30, "b2b": True, "out_adj": -1.2}
    return {"league": lg, "away": away, "home": home, "ft_factor": 1.03}


def selftest():
    s = demo_setup()
    res = simulate(s, n=2000, seed=7)
    sm = summarize(res, {"total": 228.5, "h1": 113.5, "spread": 1.5, "home_total": 112.5})
    t = sm["total"]
    assert 215 < t["mean"] < 242, t
    assert 14 < t["sd"] < 22, t
    assert 0.03 < sm["ot"] < 0.09, sm["ot"]
    assert abs(sum(sm["q_share"]) - 1.0) < 1e-3
    assert sm["markets"]["total"]["side"] in ("OVER", "UNDER") and 0.5 <= sm["markets"]["total"]["p"] <= 1.0
    assert sm["markets"]["spread"]["first"] == "HOME"
    assert band(0.71) == "STRONG" and band(0.31) == "BET" and band(0.62) == "LEAN" and band(0.55) == "no call"
    d = possession_dist(demo_setup()["away"], 1.0)
    assert abs(sum(d.values()) - 1.0) < 1e-9 and 1.0 < _mean(d) < 1.3, d
    cum, pts = possession_table(demo_setup()["away"], 1.18)
    assert abs(sum(p * (cum[i] - (cum[i - 1] if i else 0.0)) for i, p in enumerate(pts)) - 1.18) < 0.002
    return sm


if __name__ == "__main__":
    import json
    import sys
    import time
    t0 = time.time()
    sm = selftest()
    print("selftest ok, %.1fs" % (time.time() - t0))
    print(json.dumps({k: sm[k] for k in ("runs", "total", "h1", "margin", "home_win", "ot", "q_share", "markets")}, indent=1))
    if len(sys.argv) > 1 and sys.argv[1] == "--time":
        t0 = time.time()
        simulate(demo_setup(), n=5000, seed=1)
        print("5,000 runs: %.1fs" % (time.time() - t0))
