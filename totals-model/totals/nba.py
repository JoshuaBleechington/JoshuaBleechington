"""The basketball book: an NBA total, first half, spread and moneyline on the
market-anchored architecture, with only what the backtest supports.

Built 15 Oct 2026, five days before the season, from two seasons of the user's
own ledger (slate.py nba-ledger) against KillerSports' closes
(tools_backtest_nba.py; NBA.md has the table). What the record said:

* The SPREAD is priced against everything the box score holds: the pace times
  efficiency margin projection reads 0.00 against it, rest, travel and time
  zones flip sign between seasons, announced absences are in the number. So
  the sides are read off the book's own number and shown, never picked. The
  moneyline follows the spread through a normal margin at MARGIN_SD, which
  fits the home win rate within a few points at every spread.
* The TOTAL carries three things the close does not. The market OVER-MOVES
  with the pace x efficiency projection early in the season (slope -0.22 under
  fifty games, t -2.6, both seasons; null after fifty), the hockey
  scoring-rates result again: a FADE, tagged. It sits a point low after the
  trade deadline (+1.36, t 2.3, both seasons) and two low in the last fortnight
  (+2.25, t 1.8, both seasons; April +3.2): two STAGE deltas, tagged. And two
  clubs ran over it both seasons (the Nuggets +5.1 / +4.3, the Jazz +3.0 /
  +5.7, home and away): a LABEL on the card, since a club's own residual does
  not persist within a season (slope -0.05).
* The FIRST HALF carries 0.5036 of regulation points at every total level,
  with an 11.9-point spread on half the close: its own market is the anchor
  and the full game's lean comes over at the share.
* Rest, back to backs, the second night on the road, three in four, time
  zones, the trip's length, the crews: in the number. Shown as labels.

Every constant below is MEASURED on 2,449 closes unless the line says a
priori. The daily slate fills the ratings, pace, games, rest and the
who-is-out list; the engine never reads the names, only the minutes.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from .callsheet2 import Market, Matchup, _pick, _side, _total_market, spread_probs
from .fullgame import (
    Delta, Estimate, Forecast, HOLD_90TH, HOLD_REFERENCE, PLAUSIBLE, TYPICAL_HOLD, _assemble, _ncdf, _ok,
    complete_pair, devig, hold, market_confidence, normal_split, register_split,
)

# ===========================================================================
# League constants -- MEASURED 15 Oct 2026 on 2,449 joined games, 2024-25 and
# 2025-26 (tools_backtest_nba.py)
# ===========================================================================

LEAGUE_SOURCE = "measured on 2,449 closes, the 2024-25 and 2025-26 ledgers, 15 Oct 2026"
#: Points a game, both teams, at the close: 228.8 (226.9 and 230.7 by season).
LEAGUE_POINTS = 228.8
#: The total's residual on the close, sd: 18.0, flat across closing levels
#: (17.4 under 220, 20.1 at 240 and up).
TOTAL_SD = 18.0
#: The margin's residual on the spread, sd: 13.7 raw. A normal margin at 12.5
#: fits the HOME WIN RATE by spread within two to four points at every bucket
#: (95% observed at -15 or more against 91%; 73% at -9.5 to -5 against 72%),
#: where 13.7 overstates the dog (18% against 10% at +10). The moneyline reads
#: at 12.5; the spread's own split uses it too, since the two must agree.
MARGIN_SD = 12.5
#: The first half's share of regulation points: 0.5036, the same at every
#: closing level (0.5037 under 220, 0.5003 at 240 and up); the half's
#: residual on half the close +0.56 with sd 11.9.
HALF_SHARE = 0.5036
HALF_SD = 11.9
#: Home margin +1.73; overtime 4.7%; pace 101.5 possessions a side (sd 5.5).
HOME_COURT = 1.7
OT_RATE = 0.047
LEAGUE_PACE = 101.5
#: Points per 100 possessions, the league: 228.8 / 2 over 101.5 possessions.
LEAGUE_RATING = round(LEAGUE_POINTS / 2.0 / LEAGUE_PACE * 100.0, 1)   # 112.7

WEIGHTS = {"market": 4.0, "h1mkt": 4.0}

# --- the ratings fade, TAGGED ---------------------------------------------
#: The pace x efficiency projection (each offence into the defence it faces,
#: over the two paces' mean) minus the close ran the WRONG way against the
#: final: -0.135 a point of lean (t -2.1; -0.10 and -0.16 by season), and the
#: whole of it sits in the first fifty games a side (-0.22, t -2.6; shrunk by
#: n/(n+20), -0.37) with nothing after (+0.003). A projection 8+ over the
#: close landed 1.7 under it, 8+ under landed 2.3 over. The public and the
#: book move with the early tables and move too far. So the lean goes on the
#: line at RATINGS_FADE times the shrunk lean, under RATINGS_FADE_UNTIL games,
#: sized under the measurement and tagged: it cannot buy a band.
RATINGS_FADE = -0.25
RATINGS_SHRINK_K = 20.0
RATINGS_FADE_UNTIL = 50
RATINGS_MIN_GAMES = 10
# --- the stage of the season, TAGGED --------------------------------------
#: After the trade deadline the total ran +1.36 on the close (933 games, t
#: 2.3; +1.17 and +1.56 by season); the last two weeks +2.25 (224 games, t
#: 1.8; +1.40 and +3.10), April alone +3.2 (t 2.4). Tanking, bench minutes,
#: no defence: a mechanism, and the market under-prices it. Two deltas, the
#: second replacing the first, both tagged.
DEADLINE_DELTA = 1.0
LAST_TWO_WEEKS_DELTA = 2.0
#: The 2026-27 calendar, A PRIORI until the league publishes it: the deadline
#: is the first Thursday of February, the season ends the second Sunday of
#: April. Corrected by hand when known.
SEASON_DATES = {"deadline": "2027-02-04", "last_two_weeks": "2027-03-29", "end": "2027-04-11"}
#: Two clubs the close has run under both seasons, home and away. A LABEL.
WATCHED_CLUBS = {"Nuggets": "+5.1 and +4.3 a game over the close", "Jazz": "+3.0 and +5.7 a game over the close"}
#: The WNBA card's spread pattern tried on the NBA (15 Oct 2026): the ratings'
#: side of the spread LOSES over two seasons at every lean (669-716 at 2+
#: points, 394-394 at 4+, 212-196 at 6+; the blend the WNBA card scores,
#: ratings 1.2 against the market's 4.0, 351-344 at a point of lean), except
#: in a club's first thirty games, where the ratings' side at 4+ points went
#: 148-124 (54.4%; slope +0.156 a point, t 1.5), then 135-143 from thirty to
#: sixty and 113-125 after. One season's worth of a weak early signal: a
#: WATCH on the card, not scored, measured on the record from opening night.
EARLY_SIDE_GAMES = 30
EARLY_SIDE_LEAN = 4.0
#: THE UPSET WATCH (16 Oct 2026, the user: "look for potential upsets too"): the
#: dog's outright wins against the spread's own model (a normal margin at 12.5)
#: on 2,448 games, by signal. Nothing clears noise with the same sign both
#: seasons: the favourite missing 40+ minutes of regulars +2.1 points (z 1.5;
#: -0.2 and +3.4), a favourite of ten or more on a back to back +3.9 (z 1.0,
#: 86 games), the ratings liking the dog by 4+ in a club's first thirty games
#: +10.0 (z 2.0, but +0.4 and +25.5 by season: one season's). The other way:
#: after the deadline dogs won 2.4 points LESS than priced and in the last two
#: weeks 4.9 less (z -1.8): the favourites run through the tankers. Named on
#: the card, none scored; the record decides.
UPSET_FAV_OUT_MIN = 40.0
UPSET_BIG_FAV = 10.0
#: A regular is a player at this many minutes a game; the who-is-out list is
#: shown, not scored (announced absences are in the close; the live card
#: measures the late ones).
REGULAR_MPG = 20.0

PLAUSIBLE["nba_total"] = (170.0, 300.0)
PLAUSIBLE["nba_half"] = (80.0, 150.0)
PLAUSIBLE["nba_pace"] = (85.0, 120.0)
PLAUSIBLE["nba_rating"] = (90.0, 135.0)


# ===========================================================================
# The distribution: a discretised normal, as the WNBA book's, at the measured
# spreads; registered so the anchor solve, the blend and the gate inherit it
# ===========================================================================

def nba_split(line: float, mu: float) -> tuple[float, float, float]:
    return normal_split(line, mu, TOTAL_SD)


def nba_half_split(line: float, mu: float) -> tuple[float, float, float]:
    return normal_split(line, mu, HALF_SD)


register_split("NBA", nba_split)
register_split("NBA_H1", nba_half_split)

#: The bracket the anchor is solved inside. fullgame.fair_total brackets four
#: runs, which is right for a run total and too narrow for a basketball total
#: that moves 18 points a sigma; this is the same solve with a wide bracket.
FAIR_SPAN = 30.0


def nba_fair_total(sport: str, line: float, over_price: float | None, under_price: float | None) -> tuple[float, str]:
    """fullgame.fair_total with a basketball-sized bracket; the same de-vig,
    the same reconstruction of a missing price, the same confidence cut."""
    quoted = over_price is not None and under_price is not None
    rebuilt = None if quoted else complete_pair(over_price, under_price)
    if rebuilt is not None:
        over_price, under_price = rebuilt
        quoted = True
    if not quoted:
        over_price, under_price = -110.0, -110.0
    p_over, _ = devig(over_price, under_price, confidence_hold=None if rebuilt is None else HOLD_90TH)
    lo, hi = max(0.5, line - FAIR_SPAN), line + FAIR_SPAN
    for _ in range(80):
        mid = (lo + hi) / 2.0
        o, _push, u = (nba_half_split if sport == "NBA_H1" else nba_split)(line, mid)
        live = o + u
        conditional = o / live if live > 0 else 0.5
        if conditional < p_over:
            lo = mid
        else:
            hi = mid
    mu = (lo + hi) / 2.0
    book_hold = hold(over_price, under_price)
    conf = market_confidence(book_hold)
    if not quoted:
        return mu, (f"No prices given, so an evenly-priced market is assumed. A line of {line:g} splitting 50/50 "
                    f"implies a mean of {mu:.1f}: a basketball total is symmetric, so the mean sits on the number.")
    raw, _ = devig(over_price, under_price, shrink=False)
    if rebuilt is not None:
        kept = market_confidence(HOLD_90TH)
        return mu, (f"Only one price was given, so the other side was reconstructed at the {TYPICAL_HOLD * 100:.1f}% hold "
                    f"this book typically charges, giving {over_price:+.0f}/{under_price:+.0f}. That de-vigs to "
                    f"{p_over * 100:.1f}% over and puts fair at {mu:.1f} rather than the {line:g} posted; the confidence is cut "
                    f"against the {HOLD_90TH * 100:.1f}% 90th-percentile hold, so only {kept * 100:.0f}% of the {raw * 100:.1f}% read is kept.")
    tail = ""
    if conf < 1.0:
        tail = (f" That is a {book_hold * 100:.1f}% hold where a main line runs {HOLD_REFERENCE * 100:.0f}%: most likely an "
                f"ALTERNATE line. The read has been pulled back from {raw * 100:.1f}% toward even and only {conf * 100:.0f}% of it is kept.")
    return mu, (f"{over_price:+.0f}/{under_price:+.0f} de-vigs to {p_over * 100:.1f}% over ({book_hold * 100:.2f}% hold), "
                f"which is the market saying fair is {mu:.1f} rather than the {line:g} it posted." + tail)


# ===========================================================================
# The total
# ===========================================================================

def _ratings_sides(away_ort, home_ort, away_drt, home_drt, away_pace, home_pace,
                   league_rating: float | None = None, league_pace: float | None = None) -> tuple[float, float, float, float] | None:
    """Each offence into the defence it faces, per 100 possessions, over the
    mean of the two paces: (away points, home points, pace, league rating)."""
    four = (away_ort, home_ort, away_drt, home_drt)
    if not all(v is not None and _ok(v, "nba_rating") for v in four):
        return None
    lg = league_rating if league_rating is not None and _ok(league_rating, "nba_rating") else LEAGUE_RATING
    lp = league_pace if league_pace is not None and _ok(league_pace, "nba_pace") else LEAGUE_PACE
    paces = [p for p in (away_pace, home_pace) if p is not None and _ok(p, "nba_pace")]
    pace = sum(paces) / len(paces) if len(paces) == 2 else lp
    exp_a = pace / 100.0 * (away_ort + home_drt - lg)
    exp_h = pace / 100.0 * (home_ort + away_drt - lg)
    return exp_a, exp_h, pace, lg


def ratings_projection(away_ort, home_ort, away_drt, home_drt, away_pace, home_pace,
                       league_rating: float | None = None, league_pace: float | None = None) -> tuple[float, str] | None:
    """The pace x efficiency total: each offence into the defence it faces, per
    100 possessions, over the mean of the two paces. The backtest's input."""
    s = _ratings_sides(away_ort, home_ort, away_drt, home_drt, away_pace, home_pace, league_rating, league_pace)
    if s is None:
        return None
    exp_a, exp_h, pace, lg = s
    why = (f"away {away_ort:.1f} into {home_drt:.1f} and home {home_ort:.1f} into {away_drt:.1f}, each less the league's "
           f"{lg:.1f}, over {pace:.1f} possessions: {exp_a:.1f} and {exp_h:.1f}, {exp_a + exp_h:.1f} together")
    return exp_a + exp_h, why


def ratings_margin(away_ort, home_ort, away_drt, home_drt, away_pace, home_pace,
                   league_rating: float | None = None, league_pace: float | None = None) -> float | None:
    """The same projection as a margin, home minus away: the spread's own
    projection, priced against two seasons of closes (slope -0.01). A watch."""
    s = _ratings_sides(away_ort, home_ort, away_drt, home_drt, away_pace, home_pace, league_rating, league_pace)
    return None if s is None else s[1] - s[0]


def stage_of(game_date: str | None) -> tuple[float, str] | None:
    """The stage delta for a date: after the deadline, the last two weeks, or none."""
    if not game_date:
        return None
    try:
        d = dt.date.fromisoformat(str(game_date)[:10])
    except ValueError:
        return None
    s = {k: dt.date.fromisoformat(v) for k, v in SEASON_DATES.items()}
    if d > s["end"]:
        return None
    if d >= s["last_two_weeks"]:
        return LAST_TWO_WEEKS_DELTA, "the last two weeks of the season"
    if d > s["deadline"]:
        return DEADLINE_DELTA, "after the trade deadline"
    return None


def forecast_nba(
    matchup: str,
    line: float,
    over_price: float | None = None,
    under_price: float | None = None,
    *,
    away_ort: float | None = None, home_ort: float | None = None,
    away_drt: float | None = None, home_drt: float | None = None,
    away_pace: float | None = None, home_pace: float | None = None,
    away_games: float | None = None, home_games: float | None = None,
    league_rating: float | None = None, league_pace: float | None = None,
    away_rest_days: float | None = None, home_rest_days: float | None = None,
    away_out_minutes: float | None = None, home_out_minutes: float | None = None,
    away: str | None = None, home: str | None = None,
    game_date: str | None = None,
    opened: float | None = None,
) -> Forecast:
    if not _ok(line, "nba_total"):
        raise ValueError(f"total {line!r} is outside {PLAUSIBLE['nba_total']}")
    w = WEIGHTS
    notes: list[str] = []
    anchor, why = nba_fair_total("NBA", line, over_price, under_price)
    estimates = [Estimate("Market", anchor, w["market"], why)]
    deltas: list[Delta] = []

    # --- the ratings projection, FADED and tagged ----------------------------
    rp = ratings_projection(away_ort, home_ort, away_drt, home_drt, away_pace, home_pace, league_rating, league_pace)
    if rp is not None:
        n = min(v for v in (away_games, home_games) if v is not None) if (away_games is not None and home_games is not None) else None
        lean = rp[0] - anchor
        if n is None or n < RATINGS_MIN_GAMES:
            notes.append(f"Ratings projection {rp[0]:.1f} ({rp[1]}), {lean:+.1f} on the market's {anchor:.1f}. SHOWN, NOT SCORED: "
                         f"the fade needs {RATINGS_MIN_GAMES} games a side" + ("" if n is None else f" and the lesser side has {n:g}") + ".")
        elif n >= RATINGS_FADE_UNTIL:
            notes.append(f"Ratings projection {rp[0]:.1f} ({rp[1]}), {lean:+.1f} on the market's {anchor:.1f}. SHOWN, NOT SCORED: "
                         f"past {RATINGS_FADE_UNTIL} games a side the market has the ratings priced (slope +0.003 on 944 games).")
        else:
            shrunk = lean * n / (n + RATINGS_SHRINK_K)
            size = RATINGS_FADE * shrunk
            fade_why = (f"Pace x efficiency projects {rp[0]:.1f} ({rp[1]}), {lean:+.1f} on the market's {anchor:.1f}; shrunk by "
                        f"{n:g}/({n:g}+{RATINGS_SHRINK_K:g}) games to {shrunk:+.1f}. The market OVER-MOVES with early-season ratings: "
                        f"against two seasons of closes the final ran 0.22 a point the OTHER way per point of lean under {RATINGS_FADE_UNTIL} "
                        f"games (t -2.6, both seasons), nothing after. So {RATINGS_FADE:+.2f} a point goes on the line, {size:+.2f}; "
                        "tagged, it cannot buy a band.")
            deltas.append(Delta("Ratings, faded", size, fade_why, mechanism=False))
            notes.append("Ratings, faded: " + fade_why)
    elif any(v is not None for v in (away_ort, home_ort, away_drt, home_drt)):
        notes.append("The four ratings travel together, each offence into the defence it faces; a partial set is dropped.")

    # --- the stage of the season, tagged ------------------------------------
    st = stage_of(game_date)
    if st is not None:
        st_why = (f"{st[1].capitalize()}: against two seasons of closes the total ran " +
                  ("+2.25 a game in the last two weeks (224 games, +1.40 and +3.10 by season; April alone +3.2)" if st[0] == LAST_TWO_WEEKS_DELTA
                   else "+1.36 a game after the deadline (933 games, +1.17 and +1.56 by season)") +
                  f". Tanking, bench minutes and no defence; the market under-prices it. {st[0]:+.1f} on the line, tagged.")
        deltas.append(Delta("Stage of the season", st[0], st_why, mechanism=False))
        notes.append("Stage of the season, " + st_why)

    # --- labels: shown, not scored -------------------------------------------
    for side, name in (("away", away), ("home", home)):
        if name in WATCHED_CLUBS:
            notes.append(f"<b>{name}</b> games ran {WATCHED_CLUBS[name]} both seasons, home and away. WATCHED, NOT SCORED: "
                         "a club's own over/under residual does not persist within a season (slope -0.05 on 2,137 games).")
    rest_bits = []
    for side, r in (("away", away_rest_days), ("home", home_rest_days)):
        if r is not None and r <= 0:
            rest_bits.append(side)
    if rest_bits:
        notes.append("Back to back for the " + " and ".join(rest_bits) + " side. A LABEL: rest, the second night on the road, three in "
                     "four and the time zones all flipped sign between seasons against two seasons of closes. The market prices rest.")
    out_bits = []
    for side, m in (("away", away_out_minutes), ("home", home_out_minutes)):
        if m is not None and m > 0:
            out_bits.append(f"{side} {m:.0f}")
    if out_bits:
        notes.append("Regulars out, minutes a game: " + ", ".join(out_bits) + ". SHOWN, NOT SCORED: announced absences are in the "
                     "close (slope -0.01 on the total, +0.29 on the side, t 1.2); games with 40+ minutes of regulars out ran +0.87 "
                     "over the close (t 1.8). The card measures the late ones from opening night.")
    if opened is not None and abs(opened - line) > 1e-9:
        notes.append(f"The number moved {opened:g} to {line:g} ({line - opened:+.1f}). Not scored -- the current line is the anchor "
                     "and the move is already inside it.")
    return _assemble("NBA", matchup, line, estimates, deltas, notes)


# ===========================================================================
# The matchup: total, first half, spread, moneyline
# ===========================================================================

def _inv_ncdf(p: float) -> float:
    lo, hi = -8.0, 8.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if _ncdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def margin_from_spread(spread: float, home_price: float | None, away_price: float | None) -> tuple[float, str]:
    """The mean margin (home minus away) the spread and its prices imply."""
    if home_price is not None and away_price is not None:
        p_cover, _ = devig(home_price, away_price)
        lo, hi = -40.0, 40.0
        for _ in range(60):
            mid = (lo + hi) / 2.0
            c, pu, fl = spread_probs(mid, spread, MARGIN_SD)
            live = c + fl
            if (c / live if live > 0 else 0.5) < p_cover:
                lo = mid
            else:
                hi = mid
        m = (lo + hi) / 2.0
        return m, (f"spread {spread:+g} at {home_price:+.0f}/{away_price:+.0f}, which de-vigs to {p_cover * 100:.1f}% home "
                   f"and moves fair to {m:+.1f}")
    return -spread, f"spread {spread:+g} taken as the mean margin (no prices)"


def forecast_matchup_nba(
    away: str,
    home: str,
    *,
    total_line: float,
    over_price: float | None = None,
    under_price: float | None = None,
    home_ml: float | None = None,
    away_ml: float | None = None,
    spread: float | None = None,            # HOME side's line, e.g. -4.5
    spread_home_price: float | None = None,
    spread_away_price: float | None = None,
    h1_line: float | None = None,
    h1_over_price: float | None = None,
    h1_under_price: float | None = None,
    **total_inputs: Any,
) -> Matchup:
    notes: list[str] = []
    f = forecast_nba(f"{away} @ {home}", total_line, over_price, under_price, away=away, home=home, **total_inputs)
    markets: list[Market] = [_total_market(f, total_line, over_price, under_price, 1)]
    anchor = next(e.total for e in f.estimates if e.name == "Market")

    # --- the first half: its own market is the anchor; the game's lean comes over at the share --
    if h1_line is not None:
        if not _ok(h1_line, "nba_half"):
            raise ValueError(f"first-half total {h1_line!r} is outside {PLAUSIBLE['nba_half']}")
        mu_h1, how = nba_fair_total("NBA_H1", h1_line, h1_over_price, h1_under_price)
        lean = (f.projected - anchor) * HALF_SHARE
        proj_h1 = mu_h1 + lean
        h1_notes = [f"Anchored on the first-half market: {how}",
                    f"The full game's lean, {f.projected - anchor:+.1f} on its anchor, comes over at the half's {HALF_SHARE:.1%} share: {lean:+.1f}. "
                    f"The share holds at every total level (0.5037 under 220, 0.5003 at 240 and up); the half spreads {HALF_SD:g} points on its number."]
        o, pu, u = nba_half_split(h1_line, proj_h1)
        markets.append(_pick(
            "h1", f"First half total {h1_line:g}",
            [_side(f"1H OVER {h1_line:g}", "OVER", o, pu, h1_over_price), _side(f"1H UNDER {h1_line:g}", "UNDER", u, pu, h1_under_price)],
            anchored=h1_over_price is not None and h1_under_price is not None,
            notes=h1_notes + [f"Projected {proj_h1:.1f} against {h1_line:g}."]))

    # --- the margin: the book's own number, moved by nothing ------------------
    margin: float | None = None
    src = ""
    if spread is not None:
        margin, src = margin_from_spread(spread, spread_home_price, spread_away_price)
    elif home_ml is not None and away_ml is not None:
        p_home_mkt, _ = devig(home_ml, away_ml)
        margin = -MARGIN_SD * _inv_ncdf(1.0 - p_home_mkt)
        src = f"moneyline {home_ml:+.0f}/{away_ml:+.0f}, {p_home_mkt * 100:.1f}% home"
    if margin is None:
        notes.append("No spread or moneyline entered, so no side markets on this card.")
        return Matchup("NBA", away, home, markets, None, None, f, notes)
    notes.append(f"Margin (home minus away) of {margin:+.1f} from the {src}, on a margin SD of {MARGIN_SD:g}. Nothing on this sheet "
                 "moves it: against two seasons of closes the pace x efficiency margin projection read 0.00 on the spread, and rest, "
                 "travel, time zones and announced absences all sat inside the number. The sides are the book's own number read back, "
                 "shown and graded, never the pick.")
    half = f.projected / 2.0
    lam_h, lam_a = half + margin / 2.0, half - margin / 2.0
    if spread is not None and spread <= -10:
        notes.append("A home favourite of ten or more: against two seasons of closes these covered by +0.84 a game (426 games, +1.28 and "
                     "+0.42 by season, t 1.3). Watched, not scored.")
    # --- the WNBA card's pattern, early in the season: a watch, not scored ----
    rm = ratings_margin(total_inputs.get("away_ort"), total_inputs.get("home_ort"), total_inputs.get("away_drt"), total_inputs.get("home_drt"),
                        total_inputs.get("away_pace"), total_inputs.get("home_pace"), total_inputs.get("league_rating"), total_inputs.get("league_pace"))
    ag, hg = total_inputs.get("away_games"), total_inputs.get("home_games")
    n_side = min(ag, hg) if ag is not None and hg is not None else None
    if rm is not None and n_side is not None and RATINGS_MIN_GAMES <= n_side < EARLY_SIDE_GAMES and abs(rm - margin) >= EARLY_SIDE_LEAN:
        toward = home if rm > margin else away
        notes.append(f"Early-season side watch: the ratings' margin projects {rm:+.1f} against the market's {margin:+.1f}, {abs(rm - margin):.1f} points "
                     f"toward the {toward}. WATCHED, NOT SCORED: in a club's first {EARLY_SIDE_GAMES} games the ratings' side at {EARLY_SIDE_LEAN:g}+ points "
                     "of lean went 148-124 (54.4%; slope +0.156 a point, t 1.5) against two seasons of closes, then 135-143 from thirty to sixty games and "
                     "113-125 after, 394-394 over the whole. The WNBA card's spread scores the ratings at 1.2 against the market's 4.0 and is 7-0 informed on "
                     "seven games; on the NBA that blend went 351-344 at a point of lean. The record section keeps this watch from opening night.")
    # --- the upset watch: named, not scored ------------------------------------
    fav_home = margin >= 0
    dog, fav = (away, home) if fav_home else (home, away)
    a_out, h_out = total_inputs.get("away_out_minutes") or 0.0, total_inputs.get("home_out_minutes") or 0.0
    fav_out = h_out if fav_home else a_out
    a_rest, h_rest = total_inputs.get("away_rest_days"), total_inputs.get("home_rest_days")
    fav_rest, dog_rest = (h_rest, a_rest) if fav_home else (a_rest, h_rest)
    watch = []
    if fav_out >= UPSET_FAV_OUT_MIN:
        watch.append(f"{fav} missing {fav_out:.0f} minutes a game of regulars: dogs won +2.1 points more than priced on 926 such games (z 1.5; -0.2 and +3.4 by season)")
    if abs(margin) >= UPSET_BIG_FAV and fav_rest is not None and fav_rest <= 0:
        watch.append(f"{fav} a favourite of ten or more on a back to back: dogs won +3.9 points more than priced on 86 games (z 1.0; +0.4 and +7.2)")
    if rm is not None and n_side is not None and RATINGS_MIN_GAMES <= n_side < EARLY_SIDE_GAMES and ((rm - margin) >= EARLY_SIDE_LEAN if not fav_home else (margin - rm) >= EARLY_SIDE_LEAN):
        watch.append(f"the ratings like {dog} by {abs(rm - margin):.1f} points more than the market in the first thirty games: dogs won +10.0 points more than priced on 89 games (z 2.0, but +0.4 and +25.5 by season: one season's)")
    st_now = stage_of(total_inputs.get("game_date"))
    if st_now is not None:
        watch.append(f"{st_now[1]}: FEWER upsets, dogs won {'4.9' if st_now[0] == LAST_TWO_WEEKS_DELTA else '2.4'} points less than priced (z -1.8); the favourites run through the tankers")
    if watch:
        notes.append(f"Upset watch, {dog}" + (f" at {away_ml if fav_home else home_ml:+.0f}" if (away_ml is not None and home_ml is not None) else "") + ": " + "; ".join(watch) +
                     ". WATCHED, NOT SCORED: none of these clears noise with the same sign both seasons; the record decides.")
    p_h = 1.0 - _ncdf((0.0 - margin) / MARGIN_SD)
    markets.append(_pick(
        "ml", "Moneyline",
        [_side(f"{home} ML", "HOME", p_h, 0.0, home_ml), _side(f"{away} ML", "AWAY", 1.0 - p_h, 0.0, away_ml)],
        anchored=home_ml is not None and away_ml is not None,
        notes=[f"Read off the margin through a normal at {MARGIN_SD:g}, which fits the spread's home win rate within a few points at "
               "every bucket (big home dogs win a little less than it says). An edge here is only the book's moneyline disagreeing "
               "with its own spread."]))
    if spread is not None:
        c, pu, fl = spread_probs(margin, spread, MARGIN_SD)
        markets.append(_pick(
            "spread", f"Spread {home}: {spread:+g}",
            [_side(f"{home} {spread:+g}", "HOME", c, pu, spread_home_price), _side(f"{away} {-spread:+g}", "AWAY", fl, pu, spread_away_price)],
            anchored=spread_home_price is not None and spread_away_price is not None,
            notes=["The spread with both prices in is the anchor and nothing moves it off: the sides are priced. Shown and graded, "
                   "never the pick."]))
    return Matchup("NBA", away, home, markets, lam_h, lam_a, f, notes)


# ===========================================================================
# Grading
# ===========================================================================

def _line_of(market: Market) -> float:
    import re
    if market.key in ("total", "h1"):
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*$", market.pick)
        return float(m.group(1)) if m else 0.0
    if market.key == "ml":
        return 0.0
    m = re.search(r"([+-][0-9]+(?:\.[0-9]+)?)\s*$", market.pick)
    v = float(m.group(1)) if m else 0.0
    return v if market.side == "HOME" else -v


def grade(market: Market, *, home_points: float | None, away_points: float | None,
          h1_home: float | None = None, h1_away: float | None = None) -> str | None:
    """'win' | 'loss' | 'push' | 'invalid' | None. The final includes overtime;
    the half is the score at the break, 'invalid' if it exceeds the final."""
    key, side = market.key, market.side
    line = _line_of(market)
    if key in ("total", "h1"):
        if key == "h1":
            if h1_home is None or h1_away is None:
                return None
            if ((home_points is not None and h1_home > home_points + 1e-9) or (away_points is not None and h1_away > away_points + 1e-9)):
                return "invalid"
            total = h1_home + h1_away
        else:
            if home_points is None or away_points is None:
                return None
            total = home_points + away_points
        if abs(total - line) < 1e-9:
            return "push"
        return "win" if ((total > line) if side == "OVER" else (total < line)) else "loss"
    if home_points is None or away_points is None:
        return None
    margin = home_points - away_points
    if key == "ml":
        return "win" if (margin > 0) == (side == "HOME") else "loss"
    x = margin + line
    if abs(x) < 1e-9:
        return "push"
    return "win" if (x > 0) == (side == "HOME") else "loss"
