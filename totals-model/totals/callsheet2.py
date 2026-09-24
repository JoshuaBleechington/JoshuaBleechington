"""Call Sheet 2.0 -- one matchup, every market the book posts on it, ranked.

Call Sheet #1 answers one question about a game: which way does the total go,
and how sure. This answers a broader one: of everything the book will take a
bet on for this matchup -- the full-game total, the first-five total, the
moneyline and the run line -- which is the best price, and how do tonight's
candidates rank against each other.

What is carried over unchanged
------------------------------
The total is Call Sheet #1's total. Same engine, same number, same band, same
corroboration gate. The two sheets never disagree about a total, and #1 keeps
its own log so its record is not disturbed by anything here.

What is new, and the one idea behind it
---------------------------------------
Everything else on the card is priced OFF THE MARKET'S OWN NUMBERS rather than
forecast from scratch. The book posts a total and a moneyline. Together those
two prices pin down how many runs each side is expected to score -- solve for
the pair of team means that reproduces both -- and once the two means are
known, every derivative market is arithmetic on the same run distribution
Call Sheet #1 already uses:

* the run line at -1.5 / +1.5 is P(margin >= 2) on that pair of means;
* the moneyline is P(home > away), with a tie split by extra innings;
* the first five is the same pair scaled to the innings the starters cover,
  or anchored on its own market when the book posts one.

So a "pick" here is never "the model thinks the Yankees are better". It is
"the book's own total and moneyline imply the Yankees cover -1.5 at X%, and
the book is charging a price that needs Y%". That is a relative judgement
between two of the book's own quotes, and it is the only kind of judgement
this project has any evidence it can make. Nothing per-team we hold -- the
probable starters, the pens, the lineups -- is unpriced by the moneyline;
the book knew the pitchers when it posted it. So none of it moves the split.
The one input the market prices imperfectly is the weather, and that lives
in the total, which is #1's job.

Ranked by edge, not by probability
-----------------------------------
The card lists probability first because that is the question being asked --
"how likely is this to hit" -- but it RANKS by edge: the model's probability
minus the probability the price demands. A -180 favourite at 64% is a 64%
chance to hit and a losing bet; a +105 under at 55.6% is a 55.6% chance and
the best bet on the board. Ranking by probability alone would fill the top
four with heavy favourites every night, which is the surest way there is to
lose money slowly. Both numbers are on every row so the reader can see the
difference; only one of them orders the list.

What has NOT been measured (read before trusting a number)
----------------------------------------------------------
* The per-team run distribution is negative binomial with the SAME dispersion
  index as the full-game total (2.13), which is what independence between the
  two teams implies. Some of the full-game overdispersion is really positive
  correlation between the teams (park, weather, umpire), not per-team spread.
  Splitting it this way is the simplest assumption, not a measured one.
* The first-five dispersion is unmeasured. It uses the full-game index, which
  is almost certainly too wide for five innings with no bullpen and no extras.
  Too wide pulls every F5 probability toward 50%, so the error is in the
  CONSERVATIVE direction. It is on the log to be measured.
* Walk-offs truncate margins: a home side that wins in the bottom of the
  ninth or later cannot win by more than it needs to (bar a home run). The
  distribution here does not know that, so it will overstate how often a home
  favourite covers -1.5. Direction known, size not; on the log.
* There is no record yet. Every probability here is as good as the
  distribution and the market's two anchors, and nothing else. The day board
  is built to accumulate the record that will say whether the ranking works.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .fullgame import (
    BANDS, DISPERSION_PHI, HOLD_REFERENCE, STARTER_INNINGS, WEIGHTS,
    WNBA_TOTAL_SD, Forecast, _ncdf, devig, fair_total, forecast_mlb,
    forecast_wnba, hold, implied, market_confidence, nb_pmf, nb_split, price_for,
)

# ===========================================================================
# Constants -- each one either inherited or a fraction of the game
# ===========================================================================

#: Empirical spread of a WNBA final margin, home minus away. Inherited from
#: the retired spread model (totals/wnba.py), where it was used for the
#: overtime estimate. Not re-fitted here.
WNBA_MARGIN_SD = 11.0

#: Share of a nine-inning game that the first five innings are. A fraction of
#: the game, not a coefficient -- and used ONLY to size the weather deltas for
#: an F5 card, never as an anchor. The F5 anchor is the F5 market.
F5_SHARE = 5.0 / 9.0

#: Innings an F5 total covers, for the starter differential.
F5_INNINGS = 5.0

#: Per-team dispersion index for MLB runs. If the two teams' runs are
#: independent, the total's index is the mean-weighted average of the two
#: teams' indices -- so a single per-team index equal to the total's is what
#: independence implies. See the module docstring for what that ignores.
TEAM_PHI = DISPERSION_PHI["MLB"]

#: First-five dispersion index. UNMEASURED; the full-game figure, documented
#: above as conservative.
F5_PHI = DISPERSION_PHI["MLB"]

#: A run line the book posts is a whole number and a half; the default.
DEFAULT_RUN_LINE = 1.5

#: How far to sum the per-team pmf. Twenty-five runs by one side is beyond
#: the tail of anything the log holds (the 25-run game of 22 Sept was BOTH
#: sides).
_KMAX = 40


# ===========================================================================
# Results
# ===========================================================================

@dataclass
class Market:
    """One bettable thing on the card, on the side worth taking."""
    key: str            # total | f5 | ml | rl | spread
    label: str          # "Full-game total 6.5"
    pick: str           # "UNDER 6.5" | "Yankees ML" | "Rays +1.5"
    side: str           # OVER | UNDER | HOME | AWAY
    p: float            # P(pick wins | the bet resolves)
    p_push: float       # P(stake refunded), unconditional
    price: float | None
    breakeven: float | None   # implied probability of `price`, vig included
    edge: float | None        # p - breakeven, in probability
    ev: float | None          # expected return per unit staked
    fair: float               # American price this p implies
    #: True when the number comes off a market the book posted for exactly
    #: this thing. False when it is derived from other markets.
    anchored: bool
    #: For the total only: Call Sheet #1's band, so the two sheets agree.
    band: str = ""
    other_side: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        r = lambda v, n=5: None if v is None else round(v, n)  # noqa: E731
        return {
            "key": self.key, "label": self.label, "pick": self.pick, "side": self.side,
            "p": r(self.p), "p_push": r(self.p_push), "price": self.price,
            "breakeven": r(self.breakeven), "edge": r(self.edge), "ev": r(self.ev),
            "fair": round(self.fair, 1), "anchored": self.anchored, "band": self.band,
            "other_side": self.other_side, "notes": self.notes,
        }


@dataclass
class Matchup:
    sport: str
    away: str
    home: str
    markets: list[Market]
    #: The two team means the market's total and moneyline imply, after the
    #: total forecast's move has been applied proportionally. None until a
    #: moneyline is given.
    lam_home: float | None
    lam_away: float | None
    total: Forecast
    notes: list[str] = field(default_factory=list)

    @property
    def matchup(self) -> str:
        return f"{self.away} @ {self.home}"

    def ranked(self) -> list[Market]:
        """Edge first; markets with no price sink below every priced one."""
        return sorted(self.markets, key=lambda m: (m.edge is None, -(m.edge or 0.0), -m.p))

    def to_dict(self) -> dict[str, Any]:
        return {
            "sport": self.sport, "away": self.away, "home": self.home,
            "lam_home": None if self.lam_home is None else round(self.lam_home, 4),
            "lam_away": None if self.lam_away is None else round(self.lam_away, 4),
            "markets": [m.to_dict() for m in self.ranked()],
            "total": self.total.to_dict(), "notes": self.notes,
        }


# ===========================================================================
# Prices
# ===========================================================================

def _payout(price: float) -> float:
    return price / 100.0 if price > 0 else 100.0 / -price


def _priced(p: float, p_push: float, price: float | None) -> tuple[float | None, float | None, float | None]:
    """(breakeven, edge, ev) for a resolved-probability `p` at `price`."""
    if price is None:
        return None, None, None
    be = implied(price)
    live = 1.0 - p_push
    ev = live * (p * _payout(price) - (1.0 - p))
    return be, p - be, ev


def _fair(p: float) -> float:
    return price_for(p)


def _pick(key: str, label: str, sides: list[dict[str, Any]], anchored: bool,
          band: str = "", notes: list[str] | None = None) -> Market:
    """Choose the side worth taking and package it.

    With both prices in, the side with the higher EDGE. Without prices, the
    side with the higher probability. Those can differ: a 52% side at -120 is
    a worse bet than the 48% side at +100, and the point of this sheet is to
    say so.
    """
    priced = [s for s in sides if s["price"] is not None]
    # Ties are broken toward the FIRST side listed (over, home), and a tie is
    # anything inside 1e-9: on a no-information card the two sides differ by
    # a floating-point hair whose sign depends on which erf the platform has,
    # and the Python and the browser must not name different sides for it.
    best = sides[0]
    for s in sides[1:]:
        if priced:
            eb = -9.0 if best["edge"] is None else best["edge"]
            es = -9.0 if s["edge"] is None else s["edge"]
            if es > eb + 1e-9 or (abs(es - eb) <= 1e-9 and s["p"] > best["p"] + 1e-9):
                best = s
        elif s["p"] > best["p"] + 1e-9:
            best = s
    other = [s for s in sides if s is not best][0]
    m = Market(
        key=key, label=label, pick=best["pick"], side=best["side"], p=best["p"],
        p_push=best["p_push"], price=best["price"], breakeven=best["breakeven"],
        edge=best["edge"], ev=best["ev"], fair=_fair(best["p"]), anchored=anchored,
        band=band, notes=list(notes or []),
        other_side={"pick": other["pick"], "p": round(other["p"], 5), "price": other["price"],
                    "edge": None if other["edge"] is None else round(other["edge"], 5)},
    )
    if priced and best["edge"] is not None and best["edge"] <= 0:
        m.notes.append(
            f"Neither side is priced below its probability. {best['pick']} is the closer "
            f"of the two at {best['edge'] * 100:+.1f} points; the book is charging more "
            "than this number is worth on both sides.")
    return m


def _side(pick: str, side: str, p_raw: float, p_push: float, price: float | None) -> dict[str, Any]:
    live = 1.0 - p_push
    p = p_raw / live if live > 0 else 0.5
    be, edge, ev = _priced(p, p_push, price)
    return {"pick": pick, "side": side, "p": p, "p_push": p_push, "price": price,
            "breakeven": be, "edge": edge, "ev": ev}


def _total_market(f: Forecast, line: float, over_price, under_price, dp: int) -> Market:
    """Call Sheet #1's total as a 2.0 market.

    The BAND is #1's verdict on #1's SIDE -- the likelier side. The side this
    sheet picks is the better PRICE, which on a lopsided quote can be the less
    likely side. When the two differ the band must not travel: a BET on the
    over is not a BET on the under, and printing it there was a bug found on
    the first live card that had one.
    """
    m = _pick(
        "total", f"Full-game total {line:g}",
        [_side(f"OVER {line:g}", "OVER", f.p_over, f.p_push, over_price),
         _side(f"UNDER {line:g}", "UNDER", f.p_under, f.p_push, under_price)],
        anchored=True, band=f.band,
        notes=[f"Call Sheet #1's number, unchanged: projected {f.projected:.{dp}f}, {f.band}."])
    if m.side != f.side:
        m.band = ""
        m.notes.append(
            f"Call Sheet #1 names {f.side} {line:g} at {f.p_resolved * 100:.1f}% ({f.band}). This "
            f"side is picked on PRICE, not likelihood -- the book is charging so much for the "
            f"{f.side.lower()} that the {m.side.lower()} is the better bet even though it is the "
            "less likely result. #1's band stays with #1's side.")
    return m


# ===========================================================================
# The two-team run distribution (MLB)
# ===========================================================================

def team_pmf(mu: float, phi: float = TEAM_PHI, kmax: int = _KMAX) -> list[float]:
    pm = [nb_pmf(k, mu, phi) for k in range(kmax + 1)]
    s = sum(pm)
    return [v / s for v in pm] if s > 0 else pm


def margin_probs(lam_home: float, lam_away: float,
                 phi: float = TEAM_PHI) -> tuple[float, float, float, dict[int, float]]:
    """(P home > away, P tie after nine, P away > home, P(margin = d))."""
    h, a = team_pmf(lam_home, phi), team_pmf(lam_away, phi)
    dist: dict[int, float] = {}
    for i, ph in enumerate(h):
        if ph < 1e-15:
            continue
        for j, pa in enumerate(a):
            if pa < 1e-15:
                continue
            dist[i - j] = dist.get(i - j, 0.0) + ph * pa
    win = sum(v for d, v in dist.items() if d > 0)
    tie = dist.get(0, 0.0)
    lose = sum(v for d, v in dist.items() if d < 0)
    return win, tie, lose, dist


def p_home_wins(lam_home: float, lam_away: float, phi: float = TEAM_PHI) -> float:
    """A game cannot end tied. Extra innings are a fresh contest between the
    same two sides, so the tie is split in the ratio the nine-inning result
    already showed. It is an approximation and a standard one."""
    win, tie, lose, _ = margin_probs(lam_home, lam_away, phi)
    decided = win + lose
    return win + tie * (win / decided if decided > 0 else 0.5)


def solve_split(total_mean: float, p_home: float, phi: float = TEAM_PHI) -> tuple[float, float]:
    """The pair of team means with the given sum that gives the home side
    exactly `p_home` to win. Monotone in the home share, so bisection."""
    lo, hi = 0.35, total_mean - 0.35
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if p_home_wins(mid, total_mean - mid, phi) < p_home:
            lo = mid
        else:
            hi = mid
    lam_h = (lo + hi) / 2.0
    return lam_h, total_mean - lam_h


def run_line_probs(lam_home: float, lam_away: float, home_line: float,
                   phi: float = TEAM_PHI) -> tuple[float, float, float]:
    """(P home covers, P push, P away covers) for the home side at `home_line`
    (e.g. -1.5 favourite, +1.5 dog). Home covers when margin + line > 0."""
    win, tie, lose, dist = margin_probs(lam_home, lam_away, phi)
    # A nine-inning tie is not a result. Extras decide it, and the margin is
    # then one run either way far more often than not. Cheapest honest
    # treatment: move the tied mass to +1 and -1 in the ratio the moneyline
    # already splits it.
    share_h = win / (win + lose) if (win + lose) > 0 else 0.5
    cover = push = fail = 0.0
    for d, v in list(dist.items()) + [(1, tie * share_h), (-1, tie * (1.0 - share_h))]:
        if d == 0:
            continue
        x = d + home_line
        if x > 1e-9:
            cover += v
        elif x < -1e-9:
            fail += v
        else:
            push += v
    return cover, push, fail


# ===========================================================================
# MLB
# ===========================================================================

def forecast_matchup_mlb(
    away: str,
    home: str,
    *,
    total_line: float,
    over_price: float | None = None,
    under_price: float | None = None,
    home_ml: float | None = None,
    away_ml: float | None = None,
    run_line: float | None = None,        # HOME side's line, e.g. -1.5
    rl_home_price: float | None = None,
    rl_away_price: float | None = None,
    f5_line: float | None = None,
    f5_over_price: float | None = None,
    f5_under_price: float | None = None,
    **total_inputs: Any,
) -> Matchup:
    """Everything the book posts on one MLB game, priced off its own numbers.

    `total_inputs` are Call Sheet #1's inputs, passed straight through.
    """
    notes: list[str] = []
    f = forecast_mlb(f"{away} @ {home}", total_line, over_price, under_price, **total_inputs)
    markets: list[Market] = []

    # --- full-game total: Call Sheet #1, verbatim ---------------------------
    markets.append(_total_market(f, total_line, over_price, under_price, 2))

    # --- the split ----------------------------------------------------------
    anchor = next(e.total for e in f.estimates if e.name == "Market")
    lam_h = lam_a = None
    if home_ml is not None and away_ml is not None:
        p_home_mkt, _ = devig(home_ml, away_ml)
        ml_hold = hold(home_ml, away_ml)
        lam_h0, lam_a0 = solve_split(anchor, p_home_mkt)
        # The total forecast's move is spread over both sides in proportion.
        # Nothing per-team here is unpriced by the moneyline, so the split
        # itself is the market's.
        scale = f.projected / anchor if anchor > 0 else 1.0
        lam_h, lam_a = lam_h0 * scale, lam_a0 * scale
        notes.append(
            f"{home_ml:+.0f}/{away_ml:+.0f} de-vigs to {p_home_mkt * 100:.1f}% home "
            f"({ml_hold * 100:.1f}% hold). With the market's total of {anchor:.2f} that "
            f"puts the split at {lam_a0:.2f} away, {lam_h0:.2f} home; the total forecast "
            f"moves both by x{scale:.3f}. The moneyline already knows the starters, so "
            "nothing per-team moves this split -- the split IS the market.")
        if ml_hold > HOLD_REFERENCE:
            notes.append(
                f"A {ml_hold * 100:.1f}% moneyline hold is wide for a main line; only "
                f"{market_confidence(ml_hold) * 100:.0f}% of the de-vigged lean is kept, "
                "the same regression Call Sheet #1 applies to a wide total.")

        # --- moneyline ------------------------------------------------------
        p_h = p_home_wins(lam_h, lam_a)
        markets.append(_pick(
            "ml", "Moneyline",
            [_side(f"{home} ML", "HOME", p_h, 0.0, home_ml),
             _side(f"{away} ML", "AWAY", 1.0 - p_h, 0.0, away_ml)],
            anchored=True,
            notes=["Priced off the book's own moneyline; the only thing that can move it "
                   "is the total forecast changing how often the two means tie. An edge "
                   "here is the distribution disagreeing with the book about extra innings, "
                   "and that is a small thing."]))

        # --- run line -------------------------------------------------------
        rl = DEFAULT_RUN_LINE if run_line is None else run_line
        home_line = -abs(rl) if p_home_mkt >= 0.5 else abs(rl)
        if run_line is not None:
            home_line = run_line
        c, pu, fl = run_line_probs(lam_h, lam_a, home_line)
        home_pick = f"{home} {home_line:+g}"
        away_pick = f"{away} {-home_line:+g}"
        rl_notes = [
            "Derived from the total and the moneyline: the run line is where a two-team "
            "run distribution and a book's template can disagree, so this is the market "
            "most worth checking and the one most likely to be the MODEL's error rather "
            "than the book's.",
            "Walk-offs truncate the home margin -- a home side that wins in the ninth or "
            "later wins by exactly what it needed -- so this distribution overstates how "
            "often a home favourite covers -1.5. Direction known, size unmeasured.",
        ]
        markets.append(_pick(
            "rl", f"Run line {home}: {home_line:+g}",
            [_side(home_pick, "HOME", c, pu, rl_home_price),
             _side(away_pick, "AWAY", fl, pu, rl_away_price)],
            anchored=rl_home_price is not None and rl_away_price is not None,
            notes=rl_notes))
    else:
        notes.append("No moneyline entered, so there is no split and no moneyline or "
                     "run line on this card. Both prices are needed -- one side's price "
                     "says the lean, both say the hold.")

    # --- first five -----------------------------------------------------------
    if f5_line is not None:
        mu_f5, how = fair_total("MLB", f5_line, f5_over_price, f5_under_price)
        est: list[tuple[float, float]] = [(mu_f5, WEIGHTS["MLB"]["market"])]
        f5_notes = [f"Anchored on the first-five market: {how}"]
        starters = next((e for e in f.estimates if e.name == "Starters"), None)
        if starters is not None:
            # The starter gap was sized over STARTER_INNINGS; over five it is
            # the same gap per inning.
            gap = (starters.total - anchor) * (F5_INNINGS / STARTER_INNINGS)
            est.append((mu_f5 + gap, starters.weight))
            f5_notes.append(
                f"Starters: {gap:+.2f} runs over five innings, at the same weight the "
                "full-game blend gives them. No bullpens -- they do not pitch in the first "
                "five, which is the whole reason this market exists.")
        deltas = sum(d.runs for d in f.deltas) * F5_SHARE
        tw = sum(w for _, w in est)
        proj_f5 = sum(t * w for t, w in est) / tw + deltas
        if f.deltas:
            f5_notes.append(f"Weather and park deltas scaled by 5/9: {deltas:+.2f}.")
        f5_notes.append(
            "Dispersion is the full-game figure, which is too wide for five innings with "
            "no pen and no extras. That pulls this probability TOWARD 50%, so if anything "
            "it is understated. On the log to be measured.")
        o, pu, u = nb_split(f5_line, proj_f5, F5_PHI)
        markets.append(_pick(
            "f5", f"First five total {f5_line:g}",
            [_side(f"F5 OVER {f5_line:g}", "OVER", o, pu, f5_over_price),
             _side(f"F5 UNDER {f5_line:g}", "UNDER", u, pu, f5_under_price)],
            anchored=f5_over_price is not None and f5_under_price is not None,
            notes=f5_notes + [f"Projected {proj_f5:.2f} against {f5_line:g}."]))

    return Matchup("MLB", away, home, markets, lam_h, lam_a, f, notes)


# ===========================================================================
# WNBA
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


def spread_probs(margin_mean: float, home_line: float, sd: float = WNBA_MARGIN_SD
                 ) -> tuple[float, float, float]:
    """(P home covers, P push, P away covers) with a discretised normal margin.
    Home covers when margin + line > 0. No ties in basketball, so the margin
    can never be zero; a whole-number line can push."""
    if abs(home_line - round(home_line)) < 1e-9:
        k = -home_line
        lo = _ncdf((k - 0.5 - margin_mean) / sd)
        hi = _ncdf((k + 0.5 - margin_mean) / sd)
        # margin == 0 is impossible; hand that sliver to the two sides evenly
        push = hi - lo
        cover = 1.0 - hi
        fail = lo
        if abs(k) < 1e-9:
            cover += push / 2
            fail += push / 2
            push = 0.0
        return cover, push, fail
    cover = 1.0 - _ncdf((-home_line - margin_mean) / sd)
    return cover, 0.0, 1.0 - cover


def forecast_matchup_wnba(
    away: str,
    home: str,
    *,
    total_line: float,
    over_price: float | None = None,
    under_price: float | None = None,
    home_ml: float | None = None,
    away_ml: float | None = None,
    spread: float | None = None,          # HOME side's line, e.g. -4.5
    spread_home_price: float | None = None,
    spread_away_price: float | None = None,
    **total_inputs: Any,
) -> Matchup:
    notes: list[str] = []
    f = forecast_wnba(f"{away} @ {home}", total_line, over_price=over_price,
                      under_price=under_price, **total_inputs)
    markets: list[Market] = [_total_market(f, total_line, over_price, under_price, 1)]

    # --- the margin, from whichever of the two the book posted -----------------
    margin: float | None = None
    src = ""
    if spread is not None:
        if spread_home_price is not None and spread_away_price is not None:
            p_cover, _ = devig(spread_home_price, spread_away_price)
            # solve the mean that gives the home side p_cover at this line
            lo, hi = -40.0, 40.0
            for _ in range(60):
                mid = (lo + hi) / 2.0
                c, pu, fl = spread_probs(mid, spread)
                live = c + fl
                if (c / live if live > 0 else 0.5) < p_cover:
                    lo = mid
                else:
                    hi = mid
            margin = (lo + hi) / 2.0
            src = (f"spread {spread:+g} at {spread_home_price:+.0f}/{spread_away_price:+.0f}, "
                   f"which de-vigs to {p_cover * 100:.1f}% home and moves fair to {margin:+.1f}")
        else:
            margin = -spread
            src = f"spread {spread:+g} taken as the mean margin (no prices)"
    elif home_ml is not None and away_ml is not None:
        p_home_mkt, _ = devig(home_ml, away_ml)
        margin = -WNBA_MARGIN_SD * _inv_ncdf(1.0 - p_home_mkt)
        src = f"moneyline {home_ml:+.0f}/{away_ml:+.0f}, {p_home_mkt * 100:.1f}% home"

    if margin is None:
        notes.append("No spread or moneyline entered, so no side markets on this card.")
        return Matchup("WNBA", away, home, markets, None, None, f, notes)

    notes.append(f"Margin (home minus away) of {margin:+.1f} from the {src}, on a margin "
                 f"SD of {WNBA_MARGIN_SD:g}. The total forecast does not move it -- pace "
                 "and efficiency change how many points, not who scores more of them.")
    half = f.projected / 2.0
    lam_h, lam_a = half + margin / 2.0, half - margin / 2.0

    # --- moneyline ----------------------------------------------------------
    p_h = 1.0 - _ncdf((0.0 - margin) / WNBA_MARGIN_SD)
    markets.append(_pick(
        "ml", "Moneyline",
        [_side(f"{home} ML", "HOME", p_h, 0.0, home_ml),
         _side(f"{away} ML", "AWAY", 1.0 - p_h, 0.0, away_ml)],
        anchored=home_ml is not None and away_ml is not None,
        notes=["Read off the spread through the margin distribution when a spread is in, so "
               "an edge here is the book's moneyline disagreeing with its own spread. That "
               "happens, and it is small."]))

    # --- spread ---------------------------------------------------------------
    if spread is not None:
        c, pu, fl = spread_probs(margin, spread)
        markets.append(_pick(
            "spread", f"Spread {home}: {spread:+g}",
            [_side(f"{home} {spread:+g}", "HOME", c, pu, spread_home_price),
             _side(f"{away} {-spread:+g}", "AWAY", fl, pu, spread_away_price)],
            anchored=spread_home_price is not None and spread_away_price is not None,
            notes=["A spread with both prices in is the anchor, so this side's edge is only "
                   "ever the vig regressed for a wide hold. It is here so the day board can "
                   "rank it against the totals honestly, not because it can find value on "
                   "its own."]))
    return Matchup("WNBA", away, home, markets, lam_h, lam_a, f, notes)


# ===========================================================================
# The day board
# ===========================================================================

@dataclass
class BoardRow:
    matchup: str
    sport: str
    market: Market
    rank: int
    correlated_with: list[int] = field(default_factory=list)


def day_board(matchups: list[Matchup], top: int = 4) -> list[BoardRow]:
    """Every priced market on tonight's card, best edge first.

    The top `top` rows are the picks. Two markets on the same game are
    correlated -- a run line and a total both cash on a blowout -- so a row
    that shares a game with a higher-ranked one is flagged, not removed. The
    reader decides; the sheet only says what it sees.
    """
    rows: list[BoardRow] = []
    for m in matchups:
        for mk in m.markets:
            if mk.edge is None:
                continue
            rows.append(BoardRow(m.matchup, m.sport, mk, 0))
    rows.sort(key=lambda r: (-(r.market.edge or 0.0), -r.market.p))
    for i, r in enumerate(rows):
        r.rank = i + 1
        r.correlated_with = [o.rank for o in rows[:i] if o.matchup == r.matchup]
    return rows


# ===========================================================================
# Grading
# ===========================================================================

def grade(market: Market, *, home_runs: float | None, away_runs: float | None,
          f5_home: float | None = None, f5_away: float | None = None) -> str | None:
    """'win' | 'loss' | 'push' | 'invalid' | None (not gradeable yet).

    'invalid' is a first five that cannot have happened: a side's runs after
    five innings exceed its final. Five rows on the first graded night had
    exactly that, so the market refuses to grade and says so rather than
    scoring a number that is impossible.
    """
    key, side = market.key, market.side
    line = _line_of(market)
    if key in ("total", "f5"):
        if key == "f5":
            if f5_home is None or f5_away is None:
                return None
            if ((home_runs is not None and f5_home > home_runs + 1e-9)
                    or (away_runs is not None and f5_away > away_runs + 1e-9)):
                return "invalid"
            total = f5_home + f5_away
        else:
            if home_runs is None or away_runs is None:
                return None
            total = home_runs + away_runs
        if abs(total - line) < 1e-9:
            return "push"
        hit = total > line if side == "OVER" else total < line
        return "win" if hit else "loss"
    if home_runs is None or away_runs is None:
        return None
    margin = home_runs - away_runs
    if key == "ml":
        return "win" if (margin > 0) == (side == "HOME") else "loss"
    # rl / spread: `line` is the HOME line; the pick carries its own sign
    x = margin + line
    if abs(x) < 1e-9:
        return "push"
    covered = x > 0
    return "win" if covered == (side == "HOME") else "loss"


def _line_of(market: Market) -> float:
    import re
    if market.key in ("total", "f5"):
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*$", market.pick)
        return float(m.group(1)) if m else 0.0
    if market.key == "ml":
        return 0.0
    m = re.search(r"([+-][0-9]+(?:\.[0-9]+)?)\s*$", market.pick)
    v = float(m.group(1)) if m else 0.0
    # the pick's number is on the PICKED side; the home line is what grade() wants
    return v if market.side == "HOME" else -v
