"""nhlsim.py -- The Super Model's NHL game simulation (29 Oct 2026).

The user: "a simulation for the NHL model too, same set up as the NBA one,
focused on total goals, first-period totals and full-game totals", and "the
NHL simulation will be the final decision for the recommendation on the
totals; taking in consideration all elements, the simulation holds the
heaviest weight." This module plays a hockey game shot by shot, many times,
and reports the distributions and the probability of every market side.

The game, each run
  * The clock runs in game seconds; the next event (a shot by either side, a
    minor on either side) arrives at an exponential wait from the sum of the
    four rates, cut short by whatever is scheduled first: a penalty expiring,
    the period ending, the goalie coming out.
  * A shot becomes a goal at its expected-goal quality: the league's goals per
    unblocked shot in that strength state, times the shooting club's quality
    for, times the defending club's quality against, times the goalie's goals
    allowed against expected, with the score effects, the period and home ice
    on top. The rates work the same way: the league's unblocked shots per 60
    of that state, times the club's rate for, times the opponent's rate
    against.
  * The strength state comes from the penalty box: a minor is two minutes, a
    double minor four, ended by a power-play goal; two minors are a two-man
    advantage; a minor each side is four on four. Minors arrive at the club's
    rate of taking them times the opponent's rate of drawing them, times the
    crew's whistle when the referees are known.
  * The empty net: in the third, the trailing side within three pulls its
    goalie at the measured time left for its deficit (drawn from the measured
    spread), keeps it out while it trails, and puts it back when level or
    four down. The leader shoots at the empty net at the measured rate and
    quality; the trailer shoots six on five.
  * Overtime at three on three for five minutes when level after sixty; the
    first goal wins. Still level, a shootout: the winner's official score
    takes one more goal, which the full-game total carries and the periods do
    not.

Everything that moves a number here is a named constant with a measured or
a-priori source (tools_nhl_tendencies.py, from MoneyPuck's shot files and
ESPN's play-by-play), and the backtest (tools_backtest_nhl_sim.py) sets the
shrink each market's raw probability gets before it is shown. Pure standard
library, so it runs on the user's machine beside slate.py.

Data credit: the shot files are MoneyPuck.com's (moneypuck.com/data.htm).
"""
import csv
import math
import random
import re

VERSION = 1

# ---- the league's figures: measured 29 Oct 2026 on 2024-25 and 2025-26 (tools_nhl_tendencies.py, 2,624 games of
# MoneyPuck's shots joined to ESPN's play-by-play; the strength timeline from the penalties agrees with the shot file's
# skaters at 97.6% of shots), a priori where marked. The slate's nhl-tend.json carries the same block, refreshed. ----
LEAGUE = {
    # five on five, one side, per 60 minutes of five-on-five time (50.2 minutes of a game)
    "sf60": 40.27,        # unblocked shots per 60
    "q5": 0.0605,         # goals per unblocked shot (xG per shot 0.0610)
    # the power play and the kill, per 60 of the state's time (530 seconds of a game on one power play or the other)
    "pp60": 76.15, "qpp": 0.0978,    # the side with the extra man
    "pk60": 12.49, "qpk": 0.0728,    # the shorthanded side
    "two_man": 1.787,                # a two-man advantage: this many times the power play's shot rate
    "two_man_q": 1.746,              # ...and its quality
    # four on four and three on three (overtime), per 60, one side
    "s44": 36.04, "q44": 0.0733,
    "s33": 24.8, "q33": 0.1365,
    # the penalty box
    "pen60": 3.208,       # minors that give a power play, one side, per game (fights and misconducts put no one in the box)
    "pen_period": [0.943, 1.149, 0.908],   # ...by period
    "double_share": 0.013, # the share of minors that are double minors
    "minor": 120.0, "double": 240.0,
    # score effects at five on five: the shooting side's shot rate and quality by its margin, against level
    "score_rate": {-3: 1.046, -2: 1.016, -1: 1.028, 0: 1.00, 1: 0.917, 2: 0.865, 3: 0.859},
    "score_q": {-3: 0.974, -2: 0.996, -1: 0.994, 0: 1.00, 1: 1.015, 2: 1.029, 3: 1.040},
    # the period, at five on five: rate and quality against the game; and the finishing by period on every state (the
    # first period's shots go in less often than their quality says, the second's more)
    "period_rate": [1.008, 1.083, 0.913],
    "period_q": [0.994, 1.019, 0.985],
    "period_fin": [0.967, 1.022, 1.010],
    # home ice
    "home_rate": 1.015, "home_q": 1.009,
    # the empty net: the chance the trailer pulls by the deficit, the seconds left when the net first empties (quantiles 10/25/50/75/90)
    "pull": {1: {"p": 0.92, "q": [35, 65, 93, 122, 154]}, 2: {"p": 1.0, "q": [82, 126, 166, 206, 247]}, 3: {"p": 0.60, "q": [137, 196, 246, 315, 435]}},
    "en60": 28.9, "q_en": 0.521,         # the leader's shots at the empty net per 60 of empty time, goals per shot
    "extra60": 76.1, "q_extra": 0.0722,  # the trailer's six-on-five shots per 60, goals per shot
    # overtime and the shootout
    "ot_len": 300.0, "so_home": 0.50,    # the home side won 49.5% of 197 shootouts: a coin
    # what the profiles need of the league: the seconds a game at five on five and on one power play, xG per shot, minors a game
    "t55": 3009.1, "tpp": 530.3, "xg5": 0.0610, "xgpp": 0.0987, "pen_game": 3.208,
}
# the shrink each market's raw probability gets before it is shown: the share of the lean the replay found worth nothing
# (tools_backtest_nhl_sim.py, 1,312 games of 2025-26 at 1,500 runs a game, the profiles built from the games before each
# date with 2024-25 as the prior). The own view's chance of the over at Pinnacle's close carried a logistic slope of 0.25
# (shrink 0.75): the leans at 58% and up went 207-174, at 60% and up 131-108, and with the market's own price in the same
# model the sim's weight was nil. Against DraftKings' first-period 1.5 the own view's slope was 0.61 (shrink 0.39), the
# anchored view's 0.78, and the book's price itself 1.52: betting the own view where it beat the price by three points
# went 49-56. The team totals, the moneyline, the puck line and the other periods had no closes to measure against and
# keep a priori halves.
SHRINK = {"total": 0.75, "p1": 0.39, "p1_mkt": 0.22, "team": 0.5, "ml": 0.5, "pl": 0.5, "period": 0.5}
BANDS = [(0.62, "STRONG"), (0.58, "BET"), (0.55, "LEAN")]   # on the WORTH; hockey's chances are compressed: a goal of edge on the total is sixteen points at the number
STATES = ("5v5", "PP", "PK", "44", "33", "EN", "EXTRA")


def band(p):
    for cut, name in BANDS:
        if p >= cut:
            return name
    return "no call"


def shrink(p, market):
    """The raw chance pulled toward a coin by the market's shrink: 0.5 + (p - 0.5) * (1 - s)."""
    s = SHRINK.get(market, 0.5)
    return 0.5 + (p - 0.5) * (1.0 - s)


# ---- the play-by-play: penalties to a strength timeline -------------------------
# ESPN's penalty text names the infraction ("Tripping", "High-sticking - double
# minor", "Fighting", "Misconduct", "PS - Hooking on breakaway", "Too many men/ice
# served by ..."). A minor is two minutes, a double minor four, a major five;
# fighting majors are coincidental and misconducts and penalty shots put no one
# in the box, so none of those changes the skaters.
NO_BOX = ("fighting", "misconduct", "ps - ", "penalty shot", "match penalty", "embellishment")


def pen_kind(text):
    """(seconds, kind) for a penalty that changes the skaters, else None. The newer feed's "[Minor 2]" / "[Double Minor 4]"
    / "[Major 5]" / "[Misconduct 10]" suffix (slate.py nhl-pbp version 3) is read first; the older feed's text is parsed."""
    low = str(text or "").lower()
    m = re.search(r"\[([a-z ]+?) (\d+|\?)\]\s*$", low)
    if m:
        kind = m.group(1).strip()
        if "misconduct" in kind or "match" in kind or "penalty shot" in kind or "fighting" in low:
            return None
        if kind.startswith("double"):
            return 240.0, "double"
        if kind.startswith("major"):
            return None if "fighting" in low else (300.0, "major")
        if kind.startswith("bench") or kind.startswith("minor") or m.group(2) == "2":
            return 120.0, "minor"
        return None
    if any(w in low for w in NO_BOX):
        return None
    if "double minor" in low:
        return 240.0, "double"
    if "major" in low:
        return 300.0, "major"
    return 120.0, "minor"


def timeline(plays, reg_len=3600.0):
    """Segments [t0, t1, period, away skaters, home skaters, away goals, home goals] over regulation from the compact
    play-by-play (slate.py nhl-pbp): the box empties at the penalty's end or at a power-play goal against it. Overtime
    is one more segment at three on three. The goalie pull is not in the play-by-play, so the empty net is not here."""
    box = [[], []]          # per side: [end, kind] of the active penalties
    segs = []
    sk = [5, 5]
    score = [0, 0]
    t = 0.0
    period = 1
    events = []
    for p in plays:
        per, secs, code, side = p[0], p[1], p[2], p[3]
        if per is None or secs is None or per > 4:
            continue
        gt = (per - 1) * 1200.0 + secs
        if code == "P" and side in (0, 1):
            k = pen_kind(p[7])
            if k:
                events.append((gt, 0, "P", side, k))
        elif code == "G" and side in (0, 1) and per <= 3:
            events.append((gt, 1, "G", side, None))
        elif code == "G" and side in (0, 1) and per == 4:
            events.append((gt, 1, "G", side, None))
    events.sort(key=lambda e: (e[0], e[1]))
    end = reg_len

    def skaters():
        return [max(3, 5 - min(2, len(box[0]))), max(3, 5 - min(2, len(box[1])))]

    def advance(to):
        nonlocal t, sk
        while True:
            # the next change: a penalty ending, a period ending (a segment never spans two periods), or `to`
            nxt = min([b[0] for b in box[0]] + [b[0] for b in box[1]] + [to, (int(t // 1200) + 1) * 1200.0])
            if nxt > t:
                per_now = min(3, int(t // 1200) + 1)
                segs.append([t, nxt, per_now, sk[0], sk[1], score[0], score[1]])
                t = nxt
            if nxt >= to:
                break
            for s in (0, 1):
                box[s] = [b for b in box[s] if b[0] > t + 1e-9]
            sk = skaters()
    for gt, _, code, side, k in events:
        if gt > end:
            break
        advance(gt)
        if code == "P":
            box[side].append([gt + k[0], k[1]])
            box[side].sort()
            sk = skaters()
        else:
            score[side] += 1
            o = 1 - side
            if sk[side] > sk[o] and box[o]:
                # a power-play goal ends the earliest minor; a double minor loses its first half
                b = box[o][0]
                if b[1] == "double" and b[0] - gt > 120.0:
                    b[0] = gt + 120.0
                    b[1] = "minor"
                elif b[1] != "major":
                    box[o].pop(0)
                box[o].sort()
                sk = skaters()
    advance(end)
    last = max([p[0] for p in plays if p[0]] + [3])
    if last >= 4:
        segs.append([end, end + LEAGUE["ot_len"], 4, 3, 3, score[0], score[1]])
    return segs


def state_of_skaters(mine, theirs):
    if mine == theirs:
        return {5: "5v5", 4: "44", 3: "33"}.get(mine, "5v5")
    return "PP" if mine > theirs else "PK"


def state_times(plays):
    """Per side and period, the seconds in each state ({"5v5", "PP", "PK", "44", "33"}), from timeline()."""
    out = {0: [dict((s, 0.0) for s in ("5v5", "PP", "PK", "44", "33")) for _ in range(3)], 1: [dict((s, 0.0) for s in ("5v5", "PP", "PK", "44", "33")) for _ in range(3)]}
    for t0, t1, per, sa, sh, ga, gh in timeline(plays):
        if per > 3:
            continue
        d = t1 - t0
        out[0][per - 1][state_of_skaters(sa, sh)] += d
        out[1][per - 1][state_of_skaters(sh, sa)] += d
    return out


def minors_taken(plays):
    """Per side and period, the minors that put a man in the box (the shot-rate denominators' other half)."""
    out = {0: [0, 0, 0], 1: [0, 0, 0]}
    for p in plays:
        if p[2] == "P" and p[3] in (0, 1) and p[0] and p[0] <= 3 and pen_kind(p[7]):
            out[p[3]][p[0] - 1] += 1
    return out


# ---- the shot file: per-game tallies -----------------------------------------------
def _state_of(hs, as_, home_empty, away_empty, is_home):
    mine, theirs = (hs, as_) if is_home else (as_, hs)
    my_empty, their_empty = (home_empty, away_empty) if is_home else (away_empty, home_empty)
    if their_empty:
        return "EN"
    if my_empty:
        return "EXTRA"
    if mine == theirs:
        return {5: "5v5", 4: "44", 3: "33"}.get(mine, "5v5")
    return "PP" if mine > theirs else "PK"


def _flag(v):
    return str(v) in ("1", "1.0", "True", "true")


def shots_tallies(path, playoffs=False):
    """A season's shot file (MoneyPuck) to per-game tallies: {"season": "2025", "games": {gid: game}} where gid is the
    NHL game id's last five digits (20001...) and a game is {home, away, last (the last period with a shot),
    "for": {"home"/"away": {state: [shots, xG, goals]}}, "p1": {"home"/"away": [shots, xG, goals]} (five on five
    and all, as [all, 5v5]), "goalies": {"home"/"away": [[id, name, shots faced, xG faced, goals allowed], ...] in order
    of appearance, the empty net left out}}."""
    games = {}
    season = None
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        rd = csv.DictReader(fh)
        for r in rd:
            if not playoffs and r.get("isPlayoffGame") not in ("0", "0.0", ""):
                continue
            gid = str(int(float(r["game_id"])))
            season = season or r.get("season")
            g = games.get(gid)
            if g is None:
                g = games[gid] = {"home": r["homeTeamCode"], "away": r["awayTeamCode"], "last": 1,
                                  "for": {"home": {}, "away": {}}, "p1": {"home": [[0, 0.0, 0], [0, 0.0, 0]], "away": [[0, 0.0, 0], [0, 0.0, 0]]},
                                  "goalies": {"home": [], "away": []}}
            is_home = _flag(r["isHomeTeam"])
            side, other = ("home", "away") if is_home else ("away", "home")
            hs, as_ = int(float(r["homeSkatersOnIce"] or 5)), int(float(r["awaySkatersOnIce"] or 5))
            st = _state_of(hs, as_, _flag(r.get("homeEmptyNet")), _flag(r.get("awayEmptyNet")), is_home)
            per = int(float(r["period"]))
            goal = 1 if _flag(r["goal"]) else 0
            xg = float(r["xGoal"] or 0.0)
            g["last"] = max(g["last"], per)
            d = g["for"][side].setdefault(st, [0, 0.0, 0])
            d[0] += 1
            d[1] += xg
            d[2] += goal
            if per == 1:
                p = g["p1"][side]
                p[0][0] += 1; p[0][1] += xg; p[0][2] += goal
                if st == "5v5":
                    p[1][0] += 1; p[1][1] += xg; p[1][2] += goal
            if st != "EN" and per <= 4:
                gk_id = str(r.get("goalieIdForShot") or "").split(".")[0]
                if gk_id:
                    lst = g["goalies"][other]
                    e = None
                    for x in lst:
                        if x[0] == gk_id:
                            e = x
                            break
                    t_first = (per, int(float(r.get("time") or 0)))
                    if e is None:
                        e = [gk_id, r.get("goalieNameForShot") or "", 0, 0.0, 0, t_first]
                        lst.append(e)
                    elif t_first < e[5]:
                        e[5] = t_first
                    e[2] += 1
                    e[3] += xg
                    e[4] += goal
    # the goalies in order of appearance (the starter first), the time dropped
    for g in games.values():
        for side in ("home", "away"):
            g["goalies"][side].sort(key=lambda e: e[5])
            g["goalies"][side] = [e[:5] for e in g["goalies"][side]]
    return {"season": season, "games": games}


# ---- club profiles -------------------------------------------------------------------
# How much of a club's own figure to believe: the games at which this season's
# figure weighs as much as the prior (last season's whole profile, or the
# league). From the half-to-half reliability of 64 club-seasons (shots for
# r 0.78, against 0.62, quality 0.51 and 0.53, finishing 0.41 at 41 games):
# K = n (1 - r) / r.
K = {"rf": 11.6, "ra": 25.9, "qf": 38.8, "qa": 35.6, "fin": 101.2, "ppr": 41.5, "ppq": 185.2, "pkr": 63.4, "pkq": 400.0, "pen": 31.4, "drawn": 36.5}
K_PRIOR_SEASON = 20.0      # a prior season's profile is worth this many games of this season's
GOALIE_K_XG = 450.0        # a goalie's goals against expected is worth half the league prior at this many expected goals faced (about 7,000 shots:
                           # half to half r 0.11-0.20 at 60-100 xG, season to season 0.16; a goalie's figure barely moves the game, and that is the measurement)
PROFILE_KEYS = ("rf", "ra", "qf", "qa", "fin", "ppr", "ppq", "pkr", "pkq", "pen", "drawn")


def _new_acc():
    return {"n": 0, "secs": dict((s, 0.0) for s in ("5v5", "PP", "PK", "44", "33")), "for": dict((s, [0, 0.0, 0]) for s in STATES), "against": dict((s, [0, 0.0, 0]) for s in STATES),
            "minors": 0, "drawn": 0, "pbp": 0}


def _acc_game(acc, g, side, st_times, minors):
    """One game's tallies into a club's accumulator; st_times/minors from the play-by-play when it is there."""
    other = "home" if side == "away" else "away"
    acc["n"] += 1
    for st, d in g["for"][side].items():
        a = acc["for"].setdefault(st, [0, 0.0, 0]); a[0] += d[0]; a[1] += d[1]; a[2] += d[2]
    for st, d in g["for"][other].items():
        a = acc["against"].setdefault(st, [0, 0.0, 0]); a[0] += d[0]; a[1] += d[1]; a[2] += d[2]
    if st_times:
        i = 1 if side == "home" else 0
        for st in ("5v5", "PP", "PK", "44", "33"):
            acc["secs"][st] += sum(st_times[i][p][st] for p in range(3))
        acc["minors"] += sum(minors[i])
        acc["drawn"] += sum(minors[1 - i])
        acc["pbp"] += 1


def _profile_of(acc, lg):
    """A club's profile, relative to the league, from its accumulator: rates per 60 of state time (the league's state
    times stand in when the play-by-play is missing), qualities as xG per shot over the league's."""
    n = acc["n"]
    if not n:
        return None
    secs = acc["secs"]
    have = acc["pbp"] == n and acc["pbp"] > 0
    t55 = secs["5v5"] if have else n * lg["t55"]
    tpp = secs["PP"] if have else n * lg["tpp"]
    tpk = secs["PK"] if have else n * lg["tpp"]
    f, a = acc["for"], acc["against"]
    xg5 = lg["xg5"]
    p = {"n": n,
         "rf": (f["5v5"][0] / t55 * 3600.0) / lg["sf60"] if t55 > 0 else 1.0,
         "ra": (a["5v5"][0] / t55 * 3600.0) / lg["sf60"] if t55 > 0 else 1.0,
         "qf": (f["5v5"][1] / f["5v5"][0]) / xg5 if f["5v5"][0] else 1.0,
         "qa": (a["5v5"][1] / a["5v5"][0]) / xg5 if a["5v5"][0] else 1.0,
         "fin": (f["5v5"][2] / f["5v5"][1]) if f["5v5"][1] > 0 else 1.0,
         "ppr": (f["PP"][0] / tpp * 3600.0) / lg["pp60"] if tpp > 0 and f["PP"][0] else 1.0,
         "ppq": (f["PP"][1] / f["PP"][0]) / lg["xgpp"] if f["PP"][0] else 1.0,
         "pkr": (a["PP"][0] / tpk * 3600.0) / lg["pp60"] if tpk > 0 and a["PP"][0] else 1.0,
         "pkq": (a["PP"][1] / a["PP"][0]) / lg["xgpp"] if a["PP"][0] else 1.0,
         "pen": (acc["minors"] / float(acc["pbp"]) / lg["pen_game"]) if acc["pbp"] else 1.0,
         "drawn": (acc["drawn"] / float(acc["pbp"]) / lg["pen_game"]) if acc["pbp"] else 1.0}
    p["n_pbp"] = acc["pbp"]
    return p


def _blend(this, prior, lg, k_prior=K_PRIOR_SEASON):
    """This season's profile pulled toward the prior season's (itself pulled toward the league) by n/(n + K) a key."""
    out = {}
    n = this["n"] if this else 0
    n_pen = this.get("n_pbp", 0) if this else 0
    for key in PROFILE_KEYS:
        base = 1.0
        if prior:
            wp = prior["n"] / (prior["n"] + K[key])
            base = wp * prior[key] + (1 - wp)   # last season's figure, itself shrunk toward the league
        if this:
            nn = n_pen if key in ("pen", "drawn") else n
            w = nn / (nn + K[key])
            # the prior season counts as K_PRIOR_SEASON games beside this season's
            if prior:
                w = nn / (nn + K[key] + k_prior * K[key] / (prior["n"] + K[key]) * 0 + k_prior) if False else nn / (nn + k_prior)
                out[key] = w * (this[key] if nn else base) + (1 - w) * base
            else:
                out[key] = w * this[key] + (1 - w) * base
        else:
            out[key] = base
    out["n"] = n
    return out


def goalie_factor(stats, lg_xg_rate=None, k_xg=GOALIE_K_XG):
    """Goals allowed against expected, shrunk: (goals + K) / (xG + K) over the league's goals-against-expected (1.0)."""
    if not stats:
        return 1.0, 0
    shots, xg, goals = stats[0], stats[1], stats[2]
    if xg <= 0:
        return 1.0, shots
    return (goals + k_xg) / (xg + k_xg), shots


def profiles(tallies, dates, date_iso, pbp=None, prior_tallies=None, prior_pbp=None, league=None, log=None):
    """Every club's profile before date_iso, and every goalie's goals against expected.
    tallies: shots_tallies() of this season; dates: {gid: iso date} from the ledger (the shot file carries no dates);
    pbp: {gid: plays} from the ESPN play-by-play matched to the ledger's ids, for the state times and the minors;
    prior_tallies/prior_pbp: last season's. Returns {"league", "teams": {ab: profile}, "goalies": {id: [shots, xG, goals, name]},
    "last": {ab: last game date}}."""
    lg = dict(league or LEAGUE)
    for k in ("t55", "tpp", "xg5", "xgpp", "pen_game"):
        lg.setdefault(k, LEAGUE[k])
    acc, last, goalies = {}, {}, {}

    def run(tal, pb, acc_map, gk_map, before):
        for gid, g in (tal or {}).get("games", {}).items():
            d = (dates or {}).get(gid)
            if before is not None and (not d or d >= before):
                continue
            plays = (pb or {}).get(gid)
            st, mn = (state_times(plays), minors_taken(plays)) if plays else (None, None)
            for side in ("away", "home"):
                ab = g[side]
                _acc_game(acc_map.setdefault(ab, _new_acc()), g, side, st, mn)
                if d and before is not None:
                    last[ab] = max(last.get(ab, ""), d)
                for e in g["goalies"][side]:
                    k = gk_map.setdefault(e[0], [0, 0.0, 0, e[1]])
                    k[0] += e[2]; k[1] += e[3]; k[2] += e[4]
    run(tallies, pbp, acc, goalies, date_iso)
    prior_acc, prior_gk = {}, {}
    if prior_tallies:
        run(prior_tallies, prior_pbp, prior_acc, prior_gk, None)
    # the league's own figures this season refine the a-priori ones once there are enough games
    teams = {}
    prior_prof = dict((ab, _profile_of(a, lg)) for ab, a in prior_acc.items())
    for ab in set(list(acc.keys()) + list(prior_prof.keys())):
        t = _profile_of(acc[ab], lg) if ab in acc else None
        prof = _blend(t, prior_prof.get(ab), lg)
        prof["ab"] = ab
        teams[ab] = prof
    # goalies: this season's shots plus last season's, the prior season worth its whole
    gk = {}
    for gid_, v in list(prior_gk.items()) + list(goalies.items()):
        e = gk.setdefault(gid_, [0, 0.0, 0, v[3]])
        e[0] += v[0]; e[1] += v[1]; e[2] += v[2]
        if v[3]:
            e[3] = v[3]
    return {"league": lg, "teams": teams, "goalies": gk, "last": last}


def rest_flags(last_date, ab, date_iso):
    d = last_date.get(ab)
    if not d:
        return {"b2b": False, "rest": None}
    try:
        import datetime as _dt
        days = (_dt.date.fromisoformat(date_iso) - _dt.date.fromisoformat(d)).days
    except ValueError:
        return {"b2b": False, "rest": None}
    return {"b2b": days == 1, "rest": days}


def setup_from_profiles(prof, away_ab, home_ab, date_iso, goalies=None, crew=1.0):
    """A game's setup for simulate(): goalies = {"away": goalie id or [shots, xG, goals], "home": ...}."""
    a, h = prof["teams"].get(away_ab), prof["teams"].get(home_ab)
    if not a or not h:
        return None
    a, h = dict(a), dict(h)
    a.update(rest_flags(prof["last"], away_ab, date_iso))
    h.update(rest_flags(prof["last"], home_ab, date_iso))
    for side, ab in ((a, "away"), (h, "home")):
        g = (goalies or {}).get(ab)
        stats = prof["goalies"].get(str(g)) if isinstance(g, (str, int)) else g
        side["gk"], side["gk_shots"] = goalie_factor(stats)
        side["gk_name"] = (stats[3] if stats and len(stats) > 3 else "") or ""
    return {"league": prof["league"], "away": a, "home": h, "crew": crew}


# ---- the engine ----------------------------------------------------------------------
class Side:
    """One club's rates per second and qualities, by state, with the dynamic multipliers applied in the loop."""
    __slots__ = ("rate", "q", "pen", "home", "ab")

    def __init__(self, prof, opp, lg, home, crew):
        self.ab = prof.get("ab", "")
        self.home = home
        hr = lg["home_rate"] if home else 1.0
        hq = lg["home_q"] if home else 1.0
        gk = opp.get("gk", 1.0)
        fin = prof.get("fin", 1.0)
        q5 = lg["q5"] * prof["qf"] * opp["qa"] * gk * hq * fin
        self.rate = {
            "5v5": lg["sf60"] * prof["rf"] * opp["ra"] * hr / 3600.0,
            "PP": lg["pp60"] * prof["ppr"] * opp["pkr"] * hr / 3600.0,
            "PP2": lg["pp60"] * prof["ppr"] * opp["pkr"] * hr * lg["two_man"] / 3600.0,
            "PK": lg["pk60"] * prof["rf"] * hr / 3600.0,
            "44": lg["s44"] * prof["rf"] * opp["ra"] * hr / 3600.0,
            "33": lg["s33"] * prof["rf"] * opp["ra"] * hr / 3600.0,
            "EN": lg["en60"] / 3600.0,
            "EXTRA": lg["extra60"] * prof["rf"] * opp["ra"] * hr / 3600.0}
        self.q = {
            "5v5": q5,
            "PP": lg["qpp"] * prof["ppq"] * opp["pkq"] * gk * fin,
            "PP2": lg["qpp"] * prof["ppq"] * opp["pkq"] * gk * fin * lg["two_man_q"],
            "PK": lg["qpk"] * gk,
            "44": lg["q44"] * prof["qf"] * opp["qa"] * gk * fin,
            "33": lg["q33"] * prof["qf"] * opp["qa"] * gk,
            "EN": lg["q_en"],
            "EXTRA": lg["q_extra"] * prof["qf"] * opp["qa"] * gk * fin}
        self.pen = lg["pen60"] * prof["pen"] * opp["drawn"] * crew / 3600.0


def prepare(setup):
    lg, a, h = setup["league"], setup["away"], setup["home"]
    crew = float(setup.get("crew") or 1.0)
    setup["_sides"] = [Side(a, h, lg, False, crew), Side(h, a, lg, True, crew)]
    return setup


def _pull_time(lg, deficit, rng):
    """Seconds left when the trailer's net empties, or None (no pull): the measured quantiles, uniform between them."""
    d = lg["pull"].get(min(3, deficit))
    if not d or rng.random() > d["p"]:
        return None
    q = d["q"]
    u = rng.random()
    cuts = [0.0, 0.10, 0.25, 0.50, 0.75, 0.90, 1.0]
    vals = [q[0] * 0.5] + list(q) + [q[-1] * 1.4]
    for i in range(len(cuts) - 1):
        if u <= cuts[i + 1]:
            f = (u - cuts[i]) / (cuts[i + 1] - cuts[i])
            return vals[i] + f * (vals[i + 1] - vals[i])
    return q[-1]


def sim_game(setup, rng):
    """One game. Returns {pa, ph (goals by period, three each), ota, oth, so (1 home, -1 away, 0 none), ena, enh, fa, fh}."""
    lg = setup["league"]
    S = setup["_sides"]
    score_rate, score_q = lg["score_rate"], lg["score_q"]
    per_rate, per_q, per_pen, per_fin = lg["period_rate"], lg["period_q"], lg["pen_period"], lg.get("period_fin") or [1.0, 1.0, 1.0]
    minor, double, dshare = lg["minor"], lg["double"], lg["double_share"]
    pa, ph = [0, 0, 0], [0, 0, 0]
    goals = [0, 0]
    en = [0, 0]
    box = [[], []]             # [end, kind]
    pulled = [False, False]
    pull_at = [None, None]     # seconds left at which the side pulls (planned)
    t = 0.0
    rnd = rng.random
    exp = rng.expovariate

    def skaters():
        return max(3, 5 - min(2, len(box[0]))), max(3, 5 - min(2, len(box[1])))

    for period in (1, 2, 3):
        pend = period * 1200.0
        pr, pq, pp, pf = per_rate[period - 1], per_q[period - 1], per_pen[period - 1], per_fin[period - 1]
        if period == 3:
            for s in (0, 1):
                d = goals[1 - s] - goals[s]
                pull_at[s] = _pull_time(lg, d, rng) if 1 <= d <= 3 else None
        while t < pend:
            sa, sh = skaters()
            sk = (sa, sh)
            margin = goals[1] - goals[0]
            # the state each side shoots in
            st = [None, None]
            for s in (0, 1):
                o = 1 - s
                if pulled[o]:
                    st[s] = "EN"
                elif pulled[s]:
                    st[s] = "EXTRA"
                elif sk[s] == sk[o]:
                    st[s] = "5v5" if sk[s] == 5 else ("44" if sk[s] == 4 else "33")
                elif sk[s] > sk[o]:
                    st[s] = "PP2" if sk[s] - sk[o] >= 2 else "PP"
                else:
                    st[s] = "PK"
            m0 = max(-3, min(3, -margin))   # the away side's margin
            lam = [0.0, 0.0]
            qq = [0.0, 0.0]
            for s in (0, 1):
                m = m0 if s == 0 else -m0
                r = S[s].rate[st[s]]
                q = S[s].q[st[s]]
                if st[s] == "5v5":
                    r *= score_rate[m] * pr
                    q *= score_q[m] * pq
                if st[s] != "EN":
                    q *= pf
                lam[s] = r
                qq[s] = q
            pen = [S[0].pen * pp, S[1].pen * pp]
            total = lam[0] + lam[1] + pen[0] + pen[1]
            # the next scheduled change: a penalty ending, the period ending, a pull
            nxt = pend
            for s in (0, 1):
                for b in box[s]:
                    if b[0] < nxt:
                        nxt = b[0]
                if pull_at[s] is not None and not pulled[s]:
                    at = 3600.0 - pull_at[s]
                    if t <= at < nxt:
                        nxt = at
            dt = exp(total) if total > 0 else 1e9
            if t + dt >= nxt:
                t = nxt
                for s in (0, 1):
                    box[s] = [b for b in box[s] if b[0] > t + 1e-9]
                    if pull_at[s] is not None and not pulled[s] and t >= 3600.0 - pull_at[s] - 1e-9:
                        pulled[s] = True
                continue
            t += dt
            u = rnd() * total
            if u < lam[0] + lam[1]:
                s = 0 if u < lam[0] else 1
                if rnd() < qq[s]:
                    goals[s] += 1
                    (pa if s == 0 else ph)[period - 1] += 1
                    o = 1 - s
                    if pulled[o]:
                        en[s] += 1
                    # a power-play goal ends the earliest minor on the other side
                    if sk[s] > sk[o] and box[o] and not pulled[s] and not pulled[o]:
                        b = box[o][0]
                        if b[1] == "double" and b[0] - t > minor:
                            b[0] = t + minor
                            b[1] = "minor"
                        elif b[1] != "major":
                            box[o].pop(0)
                    if period == 3:
                        for x in (0, 1):
                            d = goals[1 - x] - goals[x]
                            if pulled[x]:
                                if d <= 0 or d > 3:
                                    pulled[x] = False
                                    pull_at[x] = None
                            else:
                                pull_at[x] = _pull_time(lg, d, rng) if 1 <= d <= 3 else None
            else:
                s = 0 if u < lam[0] + lam[1] + pen[0] else 1
                if rnd() < dshare:
                    box[s].append([t + double, "double"])
                else:
                    box[s].append([t + minor, "minor"])
                box[s].sort()
    ota = oth = 0
    so = 0
    if goals[0] == goals[1]:
        # three on three: the first goal wins
        t = 0.0
        la, lh = S[0].rate["33"], S[1].rate["33"]
        qa_, qh_ = S[0].q["33"], S[1].q["33"]
        while t < lg["ot_len"]:
            dt = exp(la + lh)
            if t + dt >= lg["ot_len"]:
                break
            t += dt
            if rnd() * (la + lh) < la:
                if rnd() < qa_:
                    ota = 1
                    goals[0] += 1
                    break
            else:
                if rnd() < qh_:
                    oth = 1
                    goals[1] += 1
                    break
        if goals[0] == goals[1]:
            so = 1 if rnd() < lg["so_home"] else -1
    fa, fh = goals[0] + (1 if so == -1 else 0), goals[1] + (1 if so == 1 else 0)
    return {"pa": pa, "ph": ph, "ota": ota, "oth": oth, "so": so, "ena": en[0], "enh": en[1], "fa": fa, "fh": fh}


def simulate(setup, n=5000, seed=None):
    rng = random.Random(seed)
    prepare(setup)
    return [sim_game(setup, rng) for _ in range(n)]


def _scale_quality(setup, k_a, k_h):
    """Multiply each side's shot quality (the goalie and the shooters together) by k, all states but the empty net."""
    for S, k in ((setup["_sides"][0], k_a), (setup["_sides"][1], k_h)):
        for st in ("5v5", "PP", "PP2", "PK", "44", "33", "EXTRA"):
            S.q[st] = min(0.95, S.q[st] * k)


GOAL_POINTS = 0.165   # the over's chance moves about this much per goal of mean at a hockey number: the total's density at the line (sd 2.4)
ANCHOR_DAMP = 0.7     # the share of each round's measured gap the anchor steps, so the rounds settle instead of swinging


def anchor_to_lines(setup, total=None, p_home=None, n=1500, rounds=4, seed=11, line=None, p_over=None):
    """The market-anchored game: both sides' shot quality is nudged until the sim's official total sits on the market.
    With `line` and `p_over` (the book's number and its de-vigged chance of the over, pushes aside) the target is that
    chance at that number, the way the sheet reads a price; else the mean equals `total`. With a de-vigged moneyline the
    split is nudged until the home win chance equals `p_home`. The shape (the periods, the empty net, overtime, the
    shootout) stays the sim's."""
    if total is None and (line is None or p_over is None):
        return setup
    prepare(setup)
    for r in range(rounds):
        rng = random.Random(seed + r)
        res = [sim_game(setup, rng) for _ in range(n)]
        fn = float(n)
        ma = sum(x["fa"] for x in res) / fn
        mh = sum(x["fh"] for x in res) / fn
        mean = ma + mh
        if line is not None and p_over is not None:
            over = sum(1 for x in res if x["fa"] + x["fh"] > line) / fn
            push = sum(1 for x in res if x["fa"] + x["fh"] == line) / fn
            p_sim = over / max(1e-9, 1.0 - push)
            # the over's chance moves by the mass at the number under the line per goal of mean (a Poisson identity),
            # read off this round's own runs, pushes aside; a floor keeps a thin tail from a wild step
            at = int(math.floor(line))
            mass = sum(1 for x in res if x["fa"] + x["fh"] == at) / fn
            dens = max(0.08, mass / max(1e-9, 1.0 - push))
            want = mean + ANCHOR_DAMP * (p_over - p_sim) / dens
        else:
            want = total
        k = want / mean if mean > 0 else 1.0
        k = max(0.7, min(1.4, k))
        ka = kh = k
        if p_home is not None:
            ph = sum(1 for x in res if x["fh"] > x["fa"]) / fn
            # a goal of margin is about 17 points of win chance: shift the split by the gap
            d = (p_home - ph) / 0.17 / max(1.0, want) * 2.0
            ka, kh = k * (1 - d / 2.0), k * (1 + d / 2.0)
        _scale_quality(setup, ka, kh)
    setup["_anchored"] = {"total": total, "p_home": p_home, "line": line, "p_over": p_over}
    return setup


def simulate_anchored(setup, total=None, p_home=None, n=5000, seed=None, line=None, p_over=None, anchor_n=None):
    anchor_to_lines(setup, total, p_home, n=anchor_n or min(1500, n), line=line, p_over=p_over)
    rng = random.Random(seed)
    return [sim_game(setup, rng) for _ in range(n)]


# ---- histograms and the summary -----------------------------------------------------
def histogram(xs):
    if not xs:
        return None
    lo, hi = int(min(xs)), int(max(xs))
    c = [0] * (hi - lo + 1)
    for x in xs:
        c[int(x) - lo] += 1
    return {"lo": lo, "c": c}


def histograms(results):
    """The page's set: the official total, the regulation total, each period, the team totals, the margin; the
    overtime, shootout and empty-net shares."""
    n = float(len(results))
    return {"total": histogram([r["fa"] + r["fh"] for r in results]),
            "reg": histogram([sum(r["pa"]) + sum(r["ph"]) for r in results]),
            "p": [histogram([r["pa"][k] + r["ph"][k] for r in results]) for k in range(3)],
            "p1a": histogram([r["pa"][0] for r in results]), "p1h": histogram([r["ph"][0] for r in results]),
            "away": histogram([r["fa"] for r in results]), "home": histogram([r["fh"] for r in results]),
            "margin": histogram([r["fh"] - r["fa"] for r in results]),
            "ot": round(sum(1 for r in results if r["ota"] or r["oth"] or r["so"]) / n, 4),
            "so": round(sum(1 for r in results if r["so"]) / n, 4),
            "en": round(sum(r["ena"] + r["enh"] for r in results) / n, 3)}


def hist_over(h, line):
    if not h or line is None:
        return None, None
    n = float(sum(h["c"]))
    over = sum(c for i, c in enumerate(h["c"]) if h["lo"] + i > line)
    push = sum(c for i, c in enumerate(h["c"]) if h["lo"] + i == line)
    return over / n, push / n


def hist_mean(h):
    if not h:
        return None
    n = float(sum(h["c"]))
    return sum((h["lo"] + i) * c for i, c in enumerate(h["c"])) / n if n else None


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


def _desc(xs):
    n = len(xs)
    m = sum(xs) / float(n)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else 0.0
    s = sorted(xs)
    return {"mean": round(m, 3), "median": s[n // 2], "sd": round(sd, 3)}


def _market(kind, line, p_first, push, first, second):
    live = max(1e-9, 1.0 - (push or 0.0))
    p = p_first / live
    side, prob = (first, p) if p >= 0.5 else (second, 1.0 - p)
    return {"line": line, "side": side, "p_raw": round(prob, 4), "p": round(shrink(prob, kind), 4), "push": round(push or 0.0, 4), "band": band(prob), "first": first}


def summarize(results, lines=None):
    """lines: {total, p1, p2, p3, away_total, home_total, pl (the home side's puck line, -1.5 or +1.5)}."""
    lines = lines or {}
    n = float(len(results))
    tot = [r["fa"] + r["fh"] for r in results]
    reg = [sum(r["pa"]) + sum(r["ph"]) for r in results]
    ps = [[r["pa"][k] + r["ph"][k] for r in results] for k in range(3)]
    margin = [r["fh"] - r["fa"] for r in results]
    at, ht = [r["fa"] for r in results], [r["fh"] for r in results]
    s = {"runs": len(results), "total": _desc(tot), "reg": _desc(reg), "periods": [_desc(x) for x in ps], "margin": _desc(margin),
         "away": _desc(at), "home": _desc(ht), "home_win": sum(1 for m in margin if m > 0) / n,
         "ot": sum(1 for r in results if r["ota"] or r["oth"] or r["so"]) / n, "so": sum(1 for r in results if r["so"]) / n,
         "en": sum(r["ena"] + r["enh"] for r in results) / n, "p1_share": round(sum(ps[0]) / float(sum(reg)), 4) if sum(reg) else None, "markets": {}}
    mk = s["markets"]

    def over(xs, line):
        return sum(1 for x in xs if x > line) / n, sum(1 for x in xs if x == line) / n
    if lines.get("total") is not None:
        po, pp = over(tot, lines["total"])
        mk["total"] = _market("total", lines["total"], po, pp, "OVER", "UNDER")
    for k in range(3):
        key = "p%d" % (k + 1)
        if lines.get(key) is not None:
            po, pp = over(ps[k], lines[key])
            mk[key] = _market("p1" if k == 0 else "period", lines[key], po, pp, "OVER", "UNDER")
    for key, xs in (("away_total", at), ("home_total", ht)):
        if lines.get(key) is not None:
            po, pp = over(xs, lines[key])
            mk[key] = _market("team", lines[key], po, pp, "OVER", "UNDER")
    mk["ml"] = _market("ml", None, s["home_win"], 0.0, "HOME", "AWAY")
    if lines.get("pl") is not None:
        pl = lines["pl"]
        cov = sum(1 for m in margin if m + pl > 0) / n
        push = sum(1 for m in margin if m + pl == 0) / n
        mk["pl"] = _market("pl", pl, cov, push, "HOME", "AWAY")
    return s


# ---- a demonstration setup, for the self-test and the page's example ---------------
def demo_profiles():
    lg = dict(LEAGUE)
    teams = {"EDM": {"ab": "EDM", "n": 30, "rf": 1.06, "ra": 1.02, "qf": 1.05, "qa": 1.03, "fin": 1.04, "ppr": 1.10, "ppq": 1.08, "pkr": 1.02, "pkq": 1.01, "pen": 0.95, "drawn": 1.05},
             "CGY": {"ab": "CGY", "n": 30, "rf": 0.97, "ra": 0.98, "qf": 0.97, "qa": 0.96, "fin": 0.98, "ppr": 0.95, "ppq": 0.97, "pkr": 0.97, "pkq": 0.98, "pen": 1.05, "drawn": 0.98}}
    goalies = {"8479973": [900, 55.0, 52, "Stuart Skinner"], "8481692": [1100, 64.0, 58, "Dustin Wolf"]}
    return {"league": lg, "teams": teams, "goalies": goalies, "last": {"EDM": "2026-11-06", "CGY": "2026-11-05"}}


def demo_setup():
    return setup_from_profiles(demo_profiles(), "EDM", "CGY", "2026-11-07", goalies={"away": "8479973", "home": "8481692"}, crew=1.05)


def selftest():
    s = demo_setup()
    res = simulate(s, n=3000, seed=7)
    sm = summarize(res, {"total": 6.5, "p1": 1.5, "home_total": 3.5, "pl": 1.5})
    t = sm["total"]
    assert 5.3 < t["mean"] < 7.2, t
    assert 1.4 < sm["periods"][0]["mean"] < 2.2, sm["periods"]
    assert 0.15 < sm["ot"] < 0.32, sm["ot"]
    assert 0.2 < sm["en"] < 0.6, sm["en"]
    assert sm["markets"]["total"]["side"] in ("OVER", "UNDER") and sm["markets"]["p1"]["line"] == 1.5
    assert sm["periods"][0]["mean"] < sm["periods"][2]["mean"], sm["periods"]   # the third carries the empty net and the chase
    H = histograms(res)
    po, pu = hist_over(H["total"], 6.5)
    assert abs(po - (sum(1 for r in res if r["fa"] + r["fh"] > 6.5) / 3000.0)) < 1e-9
    assert hist_quantile(H["p"][0], 0.5) in (1, 2)
    # the shootout goal is in the official total and not in the periods
    assert all((r["fa"] + r["fh"]) - (sum(r["pa"]) + sum(r["ph"])) == (1 if (r["ota"] or r["oth"] or r["so"]) else 0) for r in res)
    # the anchored view lands on the market's number
    s2 = demo_setup()
    anc = simulate_anchored(s2, 5.5, 0.60, n=3000, seed=3)
    ma = sum(r["fa"] + r["fh"] for r in anc) / 3000.0
    assert abs(ma - 5.5) < 0.2, ma
    ph = sum(1 for r in anc if r["fh"] > r["fa"]) / 3000.0
    assert abs(ph - 0.60) < 0.06, ph
    # ...and on a priced number: the over's chance at 6, pushes aside, lands on the book's
    s3 = demo_setup()
    anc = simulate_anchored(s3, n=4000, seed=4, line=6.0, p_over=0.56)
    over = sum(1 for r in anc if r["fa"] + r["fh"] > 6) / 4000.0
    push = sum(1 for r in anc if r["fa"] + r["fh"] == 6) / 4000.0
    assert abs(over / (1 - push) - 0.56) < 0.03, (over, push)
    # the play-by-play timeline: a minor, a power-play goal ending it, a double minor
    plays = [[1, 0.0, "PS", -1, "-", 0, 0, ""], [1, 100.0, "P", 0, "E", 0, 0, "A Tripping against B"], [1, 160.0, "G", 1, "P", 0, 1, ""],
             [2, 30.0, "P", 1, "E", 0, 1, "C High-sticking - double minor against D"], [2, 100.0, "P", 0, "E", 0, 1, "E Fighting against F"], [3, 0.0, "PE", -1, "-", 0, 1, ""]]
    st = state_times(plays)
    assert abs(st[1][0]["PP"] - 60.0) < 1e-6 and abs(st[0][0]["PK"] - 60.0) < 1e-6, st
    assert abs(st[0][1]["PP"] - 240.0) < 1e-6 and abs(st[1][1]["PK"] - 240.0) < 1e-6, st
    assert abs(st[0][0]["5v5"] + st[0][1]["5v5"] + st[0][2]["5v5"] - (3600.0 - 300.0)) < 1e-6, st
    assert minors_taken(plays) == {0: [1, 0, 0], 1: [0, 1, 0]}
    assert pen_kind("Nick Foligno Fighting against A.J. Greer") is None and pen_kind("X Misconduct") is None and pen_kind("Y Tripping against Z") == (120.0, "minor")
    assert pen_kind("Sam Bennett Holding against Connor Dewar [Minor 2]") == (120.0, "minor") and pen_kind("E High-sticking - double minor against R [Double Minor 4]") == (240.0, "double")
    assert pen_kind("Matthew Tkachuk Fighting against Parker Wotherspoon [Major 5]") is None and pen_kind("X Misconduct [Misconduct 10]") is None and pen_kind("T Boarding against U [Major 5]") == (300.0, "major")
    # the profiles: a club with no games is the prior season's, shrunk toward the league
    pr = _blend(None, {"n": 82, "rf": 1.20, "ra": 0.9, "qf": 1.1, "qa": 1.0, "fin": 1.0, "ppr": 1.0, "ppq": 1.0, "pkr": 1.0, "pkq": 1.0, "pen": 1.0, "drawn": 1.0}, LEAGUE)
    assert 1.10 < pr["rf"] < 1.20 and pr["n"] == 0, pr
    gf, sh = goalie_factor([1000, 60.0, 50, "G"])
    assert 0.9 < gf < 1.0 and sh == 1000, (gf, sh)
    return True


if __name__ == "__main__":
    import json
    import sys
    if "--selftest" in sys.argv:
        selftest()
        print("nhlsim: all checks passed")
    else:
        s = demo_setup()
        res = simulate(s, n=5000, seed=1)
        print(json.dumps(summarize(res, {"total": 6.5, "p1": 1.5, "pl": 1.5}), indent=1))
