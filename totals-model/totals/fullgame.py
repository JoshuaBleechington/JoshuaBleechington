"""Full-game MLB and WNBA totals, modelled as a distribution rather than a mean.

This replaces the first-five model. Three things in the version before it were
wrong in ways worth naming, because each one is a class of error rather than a
typo.

1. THE CALIBRATION ANCHOR WAS A NUMBER I PICKED.

   The F5 pitcher estimate was scaled so two league-average starters projected
   4.66 runs -- a figure derived from 53.6% of an 8.70 full-game average, and I
   chose both of those. Books post 4.5 for an average first five, so every
   projection carried +0.16 runs of push toward the over before a single input
   was read. A game with NO information came back OVER 50.8%.

   The fix is not a better constant. It is a shape that cannot hold the bug:
   every statistical estimate here is a **differential** against the posted
   line. Two league-average starters move the line by exactly zero, so a
   no-information game returns exactly 50.0%, and it does so as arithmetic
   rather than as a calibration that happened to come out right. There is a
   test.

2. THE NORMAL DISTRIBUTION CANNOT PUSH.

   F5 lines are halves, so the old model never had to think about it. Full-game
   totals are frequently whole numbers -- 8 and 9 were on the last board I was
   shown -- and a total of exactly 8 on a line of 8 is a push, not a loss.
   Modelling runs as continuous silently redistributed that probability onto
   the two sides and overstated both.

   Runs are counts, and combined run totals are overdispersed relative to
   Poisson, so this uses a **negative binomial**. It gives an exact P(push),
   and it gets the right-skew of run scoring that a normal misses -- 15-run
   games happen, -2 run games do not.

3. THE PRICES WERE THROWN AWAY.

   The posted line is rounded to the half run. The two prices are not. When the
   over is -120 and the under +100, the book is saying fair sits meaningfully
   above the posted number, and that is more precise information than the line
   itself. De-vigging the pair and inverting through the distribution recovers
   the market's own fair total to a hundredth of a run.

What is deliberately NOT here
-----------------------------
Line movement as a term. The gate model subtracted it, which was right there,
because that model scored news against the number. Here the current line IS the
anchor, so movement is already inside it and subtracting it again would
double-count. It is displayed, never scored.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# LEAGUE CONSTANTS
#
# Every number in this block is a fact about the season that I cannot verify
# from inside this sandbox -- baseball-reference, fangraphs, ESPN, StatMuse and
# TeamRankings all refuse the connection, so these come from web search
# summaries, and that layer has already been caught in this project returning
# team assignments backwards.
#
# So they are quarantined here, dated, and -- most importantly -- the model is
# built so that being wrong about them costs as little as possible. Every
# estimate is a differential against the posted line, which means an error in
# LEAGUE_RPG shifts a projection by roughly (error x 0.6) runs rather than
# setting the level outright. `sensitivity()` at the bottom prints the damage
# for a given error, and a test pins it.
#
# To update: change these four numbers and nothing else.
LEAGUE_SOURCE = "web search, 2026-09-02, unverified against a primary table"
LEAGUE_COMBINED_RPG = 9.04     # both teams, per game, 2026 through early July
LEAGUE_RPG = LEAGUE_COMBINED_RPG / 2.0
LEAGUE_STARTER_ERA = 4.16      # earned runs only, hence below LEAGUE_RPG
LEAGUE_BULLPEN_ERA = 4.05

# Innings split. A modern start is a shade over five innings; the pen covers
# the rest. These are shares of a nine-inning game and must sum to 1.
STARTER_INNINGS = 5.4
BULLPEN_INNINGS = 9.0 - STARTER_INNINGS
UNEARNED_MULTIPLIER = 1.08     # ERA counts earned runs; totals settle on all

# Measured, not chosen: the standard deviation of (final total - posted line)
# over 116 settled MLB games. WNBA is 11.51 over only 13 logged totals, which
# is far too few to trust as a point estimate; it is used because it is the
# only measurement available.
RESIDUAL_SD = {"MLB": 4.39, "WNBA": 11.51}

# Overdispersion, phi = variance / mean, derived rather than picked:
# 4.39^2 / 9.04 = 2.13. Holding phi constant rather than the variance means
# the spread scales with the size of the game, which is how count data
# behaves -- a projected 12-run game is genuinely noisier than a 6-run one.
DISPERSION_PHI = {
    "MLB": RESIDUAL_SD["MLB"] ** 2 / LEAGUE_COMBINED_RPG,
    "WNBA": 1.0,               # basketball totals are ~160; a count model is
}                              # the wrong family, so WNBA stays normal

WNBA_LEAGUE_TOTAL = 160.0

SPORTS = ("MLB", "WNBA")

# Weights. The market is the largest single weight because it is the one thing
# this project has measured: over 116 logged games the posted line beat a
# fourteen-input statistical model on mean absolute error, 3.58 to 3.61.
#
# Everything else is a differential and is weighted by how much information it
# plausibly adds ON TOP of a number that already knows all of it. Form and
# head-to-head both measured null against the residual (t = -0.07 and t =
# -0.40), which is why they are small and say so.
WEIGHTS = {
    "MLB": {"market": 4.0, "starters": 1.6, "bullpens": 0.8,
            "form": 0.8, "h2h": 0.5},
    "WNBA": {"market": 3.0, "form": 1.6, "h2h": 1.0},
}

# One meeting is not eight meetings' worth of evidence.
H2H_FULL_WEIGHT_AT = 4.0

# Bands. Every card gets a side; the band only describes distance from a coin
# flip. COIN FLIP is an answer, not a refusal.
BANDS = ((0.62, "MAX"), (0.57, "STRONG"), (0.53, "LEAN"), (0.00, "COIN FLIP"))

# Tonight-only physical factors, full-game coefficients.
WIND_DEAD_MPH = 8.0
WIND_RUNS_PER_MPH = 0.10
TEMP_BASE_F = 70.0
TEMP_RUNS_PER_DEG = 0.008
PUBLIC_SPLIT_MIN_GAP = 20.0
PUBLIC_SPLIT_RUNS = 0.30
POINTS_PER_STARTER_OUT = 2.0
POINTS_LEADING_SCORER_OUT = 3.5

PLAUSIBLE = {
    "era": (0.00, 15.0),
    "park": (70.0, 130.0),
    "mlb_total": (4.0, 20.0),
    "wnba_total": (110.0, 230.0),
    "price": (-100000.0, 100000.0),
}


def _ok(v, window) -> bool:
    if v is None:
        return False
    lo, hi = PLAUSIBLE[window]
    return lo <= v <= hi


# ===========================================================================
# The distribution
# ===========================================================================

def _lgamma(x: float) -> float:
    return math.lgamma(x)


def nb_pmf(k: int, mu: float, phi: float) -> float:
    """Negative binomial, mean-dispersion form. P(exactly k runs).

    phi is variance/mean. phi -> 1 is Poisson; MLB run totals sit near 2.13,
    which is why a Poisson understates how often a game runs away.
    """
    if k < 0 or mu <= 0:
        return 0.0
    if phi <= 1.0 + 1e-12:                     # Poisson limit
        return math.exp(k * math.log(mu) - mu - _lgamma(k + 1))
    r = mu / (phi - 1.0)
    p = r / (r + mu)
    return math.exp(
        _lgamma(k + r) - _lgamma(r) - _lgamma(k + 1)
        + r * math.log(p) + k * math.log1p(-p)
    )


def nb_split(line: float, mu: float, phi: float) -> tuple[float, float, float]:
    """(P over, P push, P under) for a total of `line` given a mean of `mu`.

    The push term is the whole reason this function exists. On a line of 8, a
    game that lands on exactly 8 is neither won nor lost, and a continuous
    model has no way to say so -- it hands that probability to the two sides
    and overstates both.
    """
    if mu <= 0:
        return 0.0, 0.0, 1.0
    top = int(max(60.0, mu + 12.0 * math.sqrt(max(mu * phi, 1.0))))
    under = push = 0.0
    total = 0.0
    for k in range(0, top + 1):
        pk = nb_pmf(k, mu, phi)
        total += pk
        if k < line:
            under += pk
        elif k == line:
            push += pk
    over = max(0.0, total - under - push)
    # renormalise the tail we truncated rather than leaking it into the over
    if total > 0:
        under, push, over = under / total, push / total, over / total
    return over, push, under


def normal_split(line: float, mu: float, sd: float) -> tuple[float, float, float]:
    """WNBA: totals near 160 are not a count problem. No push on a half line."""
    z = (mu - line) / sd
    over = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    push = 0.0
    if abs(line - round(line)) < 1e-9:
        # a whole-number basketball total can push; approximate the mass in
        # the one-point bin around it rather than pretending it cannot
        lo = 0.5 * (1.0 + math.erf(((line - 0.5) - mu) / (sd * math.sqrt(2.0))))
        hi = 0.5 * (1.0 + math.erf(((line + 0.5) - mu) / (sd * math.sqrt(2.0))))
        push = max(0.0, hi - lo)
        over = 1.0 - hi
        return over, push, lo
    return over, push, 1.0 - over


def split_for(sport: str, line: float, mu: float) -> tuple[float, float, float]:
    if sport == "MLB":
        return nb_split(line, mu, DISPERSION_PHI["MLB"])
    return normal_split(line, mu, RESIDUAL_SD["WNBA"])


# ===========================================================================
# The market's own fair total, recovered from the two prices
# ===========================================================================

def implied(price: float) -> float:
    """American odds to implied probability, vig included."""
    return (-price) / ((-price) + 100.0) if price < 0 else 100.0 / (price + 100.0)


def devig(over_price: float, under_price: float) -> tuple[float, float]:
    """Strip the hold proportionally. Returns (fair P over, fair P under)."""
    o, u = implied(over_price), implied(under_price)
    s = o + u
    return o / s, u / s


def fair_total(sport: str, line: float, over_price: float | None,
               under_price: float | None) -> tuple[float, str]:
    """The total the market is really on, which is not the number it posted.

    A posted line is rounded to the half run; the prices are not. -120/+100 on
    a total of 8.5 says fair is meaningfully north of 8.5, and this recovers
    how far north by solving for the mean that reproduces the de-vigged
    probability. It is the single cheapest piece of information on the board
    and the previous model threw it away.
    """
    quoted = over_price is not None and under_price is not None
    if not quoted:
        # A posted line is NOT a mean. It is the point the market believes
        # splits the two sides evenly, and for a right-skewed count
        # distribution the mean sits ABOVE that point -- the mean of an MLB
        # total is roughly half a run north of its median.
        #
        # Treating the line as a mean is what made a no-information game come
        # back UNDER 55.1%: the model was quietly asserting the market had
        # posted a number the over could not reach. So with no prices the
        # assumption is an evenly-priced market, -110 both ways, and the
        # anchor is solved for exactly as it is when prices are given.
        over_price, under_price = -110.0, -110.0
    p_over, _ = devig(over_price, under_price)
    lo, hi = max(0.5, line - 4.0), line + 4.0
    for _ in range(80):                        # bisection: monotone in mu
        mid = (lo + hi) / 2.0
        o, _push, u = split_for(sport, line, mid)
        # Prices are quoted on the RESOLVED outcome. A push refunds, so it sits
        # outside the pricing entirely -- a book at -110/-110 on a total of 8 is
        # saying the two sides are even GIVEN it resolves, not that P(over) is
        # 50% outright. Matching the unconditional probability instead made an
        # empty card on a whole number come back over 50.0 / under 40.5, which
        # is a lean the market never expressed.
        live = o + u
        conditional = o / live if live > 0 else 0.5
        if conditional < p_over:
            lo = mid
        else:
            hi = mid
    mu = (lo + hi) / 2.0
    hold = implied(over_price) + implied(under_price) - 1.0
    if not quoted:
        return mu, (
            f"No prices given, so an evenly-priced market is assumed. A line of {line:g} "
            f"splitting 50/50 implies a mean of {mu:.2f} — run totals are right-skewed, "
            "so the average game finishes above the number that divides the two sides."
        )
    return mu, (
        f"{over_price:+.0f}/{under_price:+.0f} de-vigs to {p_over * 100:.1f}% over "
        f"({hold * 100:.2f}% hold), which is the market saying fair is {mu:.2f} "
        f"rather than the {line:g} it posted."
    )


# ===========================================================================
# Pieces
# ===========================================================================

@dataclass
class Estimate:
    name: str
    total: float
    weight: float
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "total": round(self.total, 3),
                "weight": round(self.weight, 4), "detail": self.detail}


@dataclass
class Delta:
    name: str
    runs: float
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "runs": round(self.runs, 3), "detail": self.detail}


@dataclass
class Forecast:
    sport: str
    matchup: str
    line: float
    projected: float
    p_over: float
    p_push: float
    p_under: float
    side: str
    band: str
    estimates: list[Estimate]
    deltas: list[Delta]
    notes: list[str] = field(default_factory=list)

    @property
    def p_side(self) -> float:
        """Raw probability of the named side, pushes included in the denominator."""
        return self.p_over if self.side == "OVER" else self.p_under

    @property
    def p_resolved(self) -> float:
        """Probability the named side wins GIVEN the bet resolves.

        This is the number to compare against a price, and the number the band
        is cut from. On a total of 8 with a 9.6% push, a 47.2% over is really a
        52.2% bet -- reading the raw figure called that a coin flip and it is
        not one. Pushes refund; they are not losses.
        """
        live = self.p_over + self.p_under
        return self.p_side / live if live > 0 else 0.5

    @property
    def fair_price(self) -> float:
        """American odds this forecast implies, ignoring the push.

        A push refunds, so the number that matters for a bet is the chance of
        winning GIVEN the bet resolves.
        """
        p = self.p_resolved
        # Even money is +100 by convention. Without this the sign flips on the
        # far side of a floating-point hair at exactly 0.5 and an identical
        # coin flip prints -100 on one card and +100 on the next.
        if abs(p - 0.5) < 1e-9:
            return 100.0
        return -100.0 * p / (1.0 - p) if p > 0.5 else 100.0 * (1.0 - p) / p

    def edge_vs(self, price: float) -> float:
        """Expected return per unit staked at `price`. Push refunds the stake."""
        live = self.p_over + self.p_under
        if live <= 0:
            return 0.0
        win = self.p_side
        lose = live - win
        payout = (price / 100.0) if price > 0 else (100.0 / -price)
        return win * payout - lose

    def to_dict(self) -> dict[str, Any]:
        return {
            "sport": self.sport, "matchup": self.matchup, "line": self.line,
            "projected": round(self.projected, 3),
            "p_over": round(self.p_over, 5), "p_push": round(self.p_push, 5),
            "p_under": round(self.p_under, 5), "p_side": round(self.p_side, 5),
            "p_resolved": round(self.p_resolved, 5),
            "side": self.side, "band": self.band,
            "fair_price": round(self.fair_price, 1),
            "estimates": [e.to_dict() for e in self.estimates],
            "deltas": [d.to_dict() for d in self.deltas],
            "notes": self.notes,
        }

    def brief(self) -> str:
        out = [f"{self.matchup} — {self.side} {self.line:g}  "
               f"{self.p_resolved * 100:.1f}% of resolved bets  [{self.band}]  "
               f"fair {self.fair_price:+.0f}",
               f"  projected {self.projected:.2f} vs a line of {self.line:g}  "
               f"(over {self.p_over * 100:.1f} / push {self.p_push * 100:.1f} / "
               f"under {self.p_under * 100:.1f})"]
        tw = sum(e.weight for e in self.estimates)
        for e in self.estimates:
            out.append(f"    {e.name:<22} {e.total:8.2f}  {e.weight / tw * 100:4.0f}%")
        for d in self.deltas:
            out.append(f"    {d.name:<22} {d.runs:+8.2f}  delta")
        out.extend(f"  note: {n}" for n in self.notes)
        return "\n".join(out)


def h2h_weight(base: float, meetings: float) -> float:
    return base * min(1.0, max(0.0, meetings) / H2H_FULL_WEIGHT_AT)


def park_scale(park_factor: float | None) -> float:
    return park_factor / 100.0 if _ok(park_factor, "park") else 1.0


def arm_differential(era: float | None, league: float, innings: float,
                     opponent_rpg: float | None) -> float | None:
    """What this arm is worth RELATIVE to a league-average one, in runs.

    Differential rather than absolute on purpose. An absolute projection needs
    a league-average total to calibrate against, and picking that number wrong
    is exactly what put a permanent over-lean in the model this replaces. A
    differential of an average arm is zero however wrong the league constant is
    in level terms.
    """
    if not _ok(era, "era"):
        return None
    gap = (era - league) * (innings / 9.0) * UNEARNED_MULTIPLIER
    if opponent_rpg is not None and opponent_rpg > 0:
        gap *= opponent_rpg / LEAGUE_RPG
    return gap


# ===========================================================================
# MLB
# ===========================================================================

def forecast_mlb(
    matchup: str,
    line: float,
    over_price: float | None = None,
    under_price: float | None = None,
    away_starter_era: float | None = None,
    home_starter_era: float | None = None,
    away_rpg: float | None = None,
    home_rpg: float | None = None,
    away_bullpen_era: float | None = None,
    home_bullpen_era: float | None = None,
    away_last10_total: float | None = None,
    home_last10_total: float | None = None,
    h2h_total: float | None = None,
    h2h_meetings: float | None = None,
    park_factor: float | None = None,
    wind_mph: float | None = None,
    wind_direction: str | None = None,
    temp_f: float | None = None,
    dome: bool = False,
    ticket_pct_over: float | None = None,
    money_pct_over: float | None = None,
    opened: float | None = None,
) -> Forecast:
    if not _ok(line, "mlb_total"):
        raise ValueError(f"total {line!r} is outside {PLAUSIBLE['mlb_total']}")

    w = WEIGHTS["MLB"]
    park = park_scale(park_factor)
    notes: list[str] = []

    anchor, anchor_detail = fair_total("MLB", line, over_price, under_price)
    estimates = [Estimate("Market", anchor, w["market"], anchor_detail)]

    # --- starters, as a differential ---------------------------------------
    a = arm_differential(away_starter_era, LEAGUE_STARTER_ERA, STARTER_INNINGS, home_rpg)
    h = arm_differential(home_starter_era, LEAGUE_STARTER_ERA, STARTER_INNINGS, away_rpg)
    if a is not None and h is not None:
        gap = (a + h) * park
        # Anchored to the market's FAIR mean, not the posted line. Anchoring a
        # differential to the line while the market estimate sits at the fair
        # mean makes a zero differential drag the blend down toward the line --
        # two league-average staffs came back UNDER 51.9% that way, which is
        # the same class of hidden lean this rewrite exists to remove.
        estimates.append(Estimate(
            "Starters", anchor + gap, w["starters"],
            f"Away {away_starter_era:.2f} and home {home_starter_era:.2f} against a "
            f"{LEAGUE_STARTER_ERA:.2f} league starter ERA, over the {STARTER_INNINGS:.1f} "
            f"innings a start now covers: {gap:+.2f} runs on the line. Two league-average "
            "arms move it by exactly zero, which is what keeps this from carrying a "
            "hidden lean."))
    elif a is not None or h is not None:
        notes.append("Only one starter's ERA is in. A differential needs both arms, so "
                     "the starters are out of the blend and their weight has gone to "
                     "what is left.")

    # --- bullpens ----------------------------------------------------------
    ab = arm_differential(away_bullpen_era, LEAGUE_BULLPEN_ERA, BULLPEN_INNINGS, home_rpg)
    hb = arm_differential(home_bullpen_era, LEAGUE_BULLPEN_ERA, BULLPEN_INNINGS, away_rpg)
    if ab is not None and hb is not None:
        gap = (ab + hb) * park
        estimates.append(Estimate(
            "Bullpens", anchor + gap, w["bullpens"],
            f"Away {away_bullpen_era:.2f} and home {home_bullpen_era:.2f} against a "
            f"{LEAGUE_BULLPEN_ERA:.2f} league pen, over the {BULLPEN_INNINGS:.1f} innings "
            f"they cover: {gap:+.2f} runs. This is the half of the game first-five threw "
            "away, and it is back because the market being bet is the full nine."))

    # --- form and head to head --------------------------------------------
    if away_last10_total is not None and home_last10_total is not None:
        avg = (away_last10_total + home_last10_total) / 2.0
        estimates.append(Estimate(
            "Last 10", avg * park, w["form"],
            f"Last-ten combined totals average {avg:.1f}. Measured t = -0.07 against the "
            "residual on 116 logged games, so it is weighted to move a close card and "
            "not to overturn the market."))

    if h2h_total is not None and h2h_meetings:
        weight = h2h_weight(w["h2h"], h2h_meetings)
        thin = ""
        if h2h_meetings < H2H_FULL_WEIGHT_AT:
            thin = (f" Discounted to {h2h_meetings:.0f}/{H2H_FULL_WEIGHT_AT:.0f} of its "
                    f"weight because it rests on {h2h_meetings:.0f} meeting(s).")
        estimates.append(Estimate(
            f"Head to head ({h2h_meetings:.0f})", h2h_total * park, weight,
            f"{h2h_meetings:.0f} meetings averaging {h2h_total:.1f}. Measured t = -0.40, "
            "the weakest thing in the blend." + thin))
    elif h2h_total is None:
        notes.append("No head-to-head. Its weight has been redistributed across the "
                     "estimates that are present.")

    # --- tonight-only deltas ----------------------------------------------
    deltas: list[Delta] = []
    if dome:
        deltas.append(Delta("Roof shut", 0.0, "Closed roof — wind and temperature both out."))
    else:
        if wind_mph is not None and wind_direction:
            d = wind_direction.strip().lower()
            if d in ("out", "in"):
                eff = max(0.0, wind_mph - WIND_DEAD_MPH)
                runs = eff * WIND_RUNS_PER_MPH * park
                deltas.append(Delta("Wind", runs if d == "out" else -runs,
                    f"{wind_mph:.0f} mph blowing {d}; nothing counts under "
                    f"{WIND_DEAD_MPH:.0f} mph, then {WIND_RUNS_PER_MPH:.2f} runs per mph "
                    "over it. The one input on this page the market prices imperfectly, "
                    "because it changes after the number posts."))
            elif d == "cross":
                deltas.append(Delta("Wind", 0.0,
                    f"{wind_mph:.0f} mph across the field, which carries a fly ball "
                    "neither way."))
        if temp_f is not None:
            deltas.append(Delta("Temperature", (temp_f - TEMP_BASE_F) * TEMP_RUNS_PER_DEG,
                f"{temp_f:.0f}°F against a {TEMP_BASE_F:.0f}° baseline."))

    if ticket_pct_over is not None and money_pct_over is not None:
        gap = ticket_pct_over - money_pct_over
        if abs(gap) >= PUBLIC_SPLIT_MIN_GAP:
            deltas.append(Delta("Money split",
                -PUBLIC_SPLIT_RUNS if gap > 0 else PUBLIC_SPLIT_RUNS,
                f"Over holds {ticket_pct_over:.0f}% of tickets but {money_pct_over:.0f}% "
                f"of money, a {abs(gap):.0f}-point gap. Small bets on the over, big money "
                f"on the {'under' if gap > 0 else 'over'}. Capped flat: the direction is "
                "documented, the size is not."))

    if opened is not None and abs(opened - line) > 1e-9:
        notes.append(
            f"The number moved {opened:g} to {line:g} ({line - opened:+.1f}). That is NOT "
            "scored — the current line is the anchor, so the move is already inside it and "
            "subtracting it again would double-count. It is here because a large move "
            "against your side is worth knowing before you bet.")

    return _assemble("MLB", matchup, line, estimates, deltas, notes)


# ===========================================================================
# WNBA
# ===========================================================================

def forecast_wnba(
    matchup: str,
    line: float,
    over_price: float | None = None,
    under_price: float | None = None,
    away_last10_total: float | None = None,
    home_last10_total: float | None = None,
    h2h_total: float | None = None,
    h2h_meetings: float | None = None,
    away_starters_out: int = 0,
    home_starters_out: int = 0,
    away_leading_scorer_out: bool = False,
    home_leading_scorer_out: bool = False,
    opened: float | None = None,
) -> Forecast:
    if not _ok(line, "wnba_total"):
        raise ValueError(f"total {line!r} is outside {PLAUSIBLE['wnba_total']}")

    w = WEIGHTS["WNBA"]
    notes: list[str] = []
    anchor, anchor_detail = fair_total("WNBA", line, over_price, under_price)
    estimates = [Estimate("Market", anchor, w["market"], anchor_detail)]

    if away_last10_total is not None and home_last10_total is not None:
        avg = (away_last10_total + home_last10_total) / 2.0
        estimates.append(Estimate(
            "Last 10", avg, w["form"],
            f"Combined totals over the last ten average {away_last10_total:.1f} away and "
            f"{home_last10_total:.1f} home, blending to {avg:.1f}. Ten games is a third of "
            "a WNBA season and there is no starting-pitcher equivalent to lean on."))

    if h2h_total is not None and h2h_meetings:
        weight = h2h_weight(w["h2h"], h2h_meetings)
        thin = ""
        if h2h_meetings < H2H_FULL_WEIGHT_AT:
            thin = (f" Discounted to {h2h_meetings:.0f}/{H2H_FULL_WEIGHT_AT:.0f} of its "
                    "weight for sample size.")
        estimates.append(Estimate(
            f"Head to head ({h2h_meetings:.0f})", h2h_total, weight,
            f"{h2h_meetings:.0f} meetings averaging {h2h_total:.1f}." + thin))
    else:
        notes.append("No head-to-head on file. Its weight has gone to the market and the "
                     "last ten, which now carry the blend between them.")

    deltas: list[Delta] = []
    for team, out, leader in (("Away", away_starters_out, away_leading_scorer_out),
                              ("Home", home_starters_out, home_leading_scorer_out)):
        if out <= 0 and not leader:
            continue
        pts = out * POINTS_PER_STARTER_OUT
        if leader:
            pts += POINTS_LEADING_SCORER_OUT - POINTS_PER_STARTER_OUT
        deltas.append(Delta(f"{team} absences", -pts,
            f"{out} rotation player(s) out"
            + (", including their leading scorer" if leader else "") +
            f". A twelve-deep roster with starters at 32+ minutes has no bench to absorb "
            f"it: {pts:.1f} points off the total."))

    if opened is not None and abs(opened - line) > 1e-9:
        notes.append(f"The number moved {opened:g} to {line:g} ({line - opened:+.1f}). Not "
                     "scored — it is already inside the current line.")

    return _assemble("WNBA", matchup, line, estimates, deltas, notes)


# ===========================================================================

def _assemble(sport, matchup, line, estimates, deltas, notes) -> Forecast:
    tw = sum(e.weight for e in estimates)
    if tw <= 0:
        raise ValueError("no estimates to blend")
    blended = sum(e.total * e.weight for e in estimates) / tw
    projected = blended + sum(d.runs for d in deltas)

    over, push, under = split_for(sport, line, projected)
    # Tie goes to the over by rule, in every implementation of this. A
    # half-point disagreement between the Python and the browser flipped a card
    # once, so the rule is written down rather than left to floating point.
    side = "OVER" if over >= under - 1e-9 else "UNDER"
    p_side = over if side == "OVER" else under
    live = over + under
    band = next(name for floor, name in BANDS
                if (p_side / live if live > 0 else 0.5) >= floor)

    if len(estimates) == 1 and not deltas:
        notes.append("Nothing entered but the number, so the forecast IS the market and "
                     "the answer is a coin flip. That is the correct answer to a question "
                     "with no information in it, not the model being coy.")
    if push > 0.02:
        notes.append(f"The line is a whole number, so {push * 100:.1f}% of the time this "
                     "pushes and the stake comes back. That probability is real and a "
                     "model that treats runs as continuous silently hands it to the two "
                     "sides instead.")
    if band == "MAX":
        notes.append("Top band. Re-read the inputs before acting — in this project a "
                     "spectacular number has more often been a mistyped one than an edge.")
    return Forecast(sport, matchup, line, projected, over, push, under,
                    side, band, estimates, deltas, notes)


# ===========================================================================
# Whether any of this works
# ===========================================================================

@dataclass
class Calibration:
    """Does a 60% call actually win 60% of the time?

    The single most important property of a forecaster, and the thing the model
    this replaces had no way to check. A model can name the right side more
    often than not and still be useless if its confidence is fiction, because
    the confidence is what sizes the bet.
    """

    n: int
    brier: float
    log_loss: float
    hit_rate: float
    mean_forecast: float
    buckets: list[dict[str, Any]]
    verdict: str

    def report(self) -> str:
        out = [f"n = {self.n} settled calls",
               f"  mean forecast {self.mean_forecast * 100:5.1f}%   "
               f"actual {self.hit_rate * 100:5.1f}%   "
               f"gap {(self.hit_rate - self.mean_forecast) * 100:+5.1f} points",
               f"  Brier {self.brier:.4f}   log loss {self.log_loss:.4f}",
               "  bucket        n   said   did    gap"]
        for b in self.buckets:
            out.append(f"  {b['label']:<10} {b['n']:4d}  {b['said'] * 100:5.1f}% "
                       f"{b['did'] * 100:5.1f}%  {(b['did'] - b['said']) * 100:+5.1f}")
        out.append(f"  {self.verdict}")
        return "\n".join(out)


def calibration(records: Iterable[tuple[float, bool]]) -> Calibration:
    """`records` are (probability the model gave its side, did that side win).

    Pushes should be dropped before calling: they refund, so they are neither
    a hit nor a miss and including them as either corrupts the measure.
    """
    rows = [(float(p), bool(w)) for p, w in records]
    if not rows:
        raise ValueError("no settled calls to calibrate on")
    n = len(rows)
    brier = sum((p - w) ** 2 for p, w in rows) / n
    eps = 1e-12
    log_loss = -sum(math.log(max(p if w else 1 - p, eps)) for p, w in rows) / n
    hit = sum(w for _, w in rows) / n
    mean_p = sum(p for p, _ in rows) / n

    edges = [(0.50, 0.53, "50-53%"), (0.53, 0.57, "53-57%"),
             (0.57, 0.62, "57-62%"), (0.62, 1.01, "62%+")]
    buckets = []
    for lo, hi, label in edges:
        sub = [(p, w) for p, w in rows if lo <= p < hi]
        if sub:
            buckets.append({"label": label, "n": len(sub),
                            "said": sum(p for p, _ in sub) / len(sub),
                            "did": sum(w for _, w in sub) / len(sub)})

    # Two separate questions, and an overconfident model fails both, so the
    # verdict reports every one that applies rather than whichever check
    # happens to run first. "Miscalibrated" says WHAT is wrong; the Brier line
    # says whether the thing is worth using at all.
    gap = hit - mean_p
    se = math.sqrt(max(mean_p * (1 - mean_p), 1e-9) / n)
    if n < 50:
        verdict = (f"{n} calls is not enough to judge anything — one standard error on the "
                   f"hit rate is {se * 100:.1f} points. Keep logging.")
    else:
        problems = []
        if abs(gap) > 2 * se:
            problems.append(
                f"Miscalibrated: it says {mean_p * 100:.1f}% and does {hit * 100:.1f}%, "
                f"a gap of {gap * 100:+.1f} against a standard error of {se * 100:.1f}. "
                "The side may still be right; the confidence is not.")
        if brier >= 0.25:
            problems.append(
                f"Brier {brier:.4f} is at or above the 0.25 a coin flip scores, so this is "
                "not adding information and should not be sized on.")
        verdict = " ".join(problems) if problems else (
            f"Calibrated within noise ({gap * 100:+.1f} points against a "
            f"{se * 100:.1f}-point standard error), Brier {brier:.4f}.")
    return Calibration(n, brier, log_loss, hit, mean_p, buckets, verdict)


def sensitivity(error: float = 0.20) -> dict[str, float]:
    """How much a wrong league constant costs, in runs on the projection.

    The league numbers cannot be verified from inside this sandbox, so the
    honest move is to measure the damage rather than pretend to precision.
    Differential form is what keeps this small: the error enters through the
    starters and bullpens only, and only through their share of the weight.
    """
    w = WEIGHTS["MLB"]
    tw = sum(w.values())
    starter = error * (STARTER_INNINGS / 9.0) * UNEARNED_MULTIPLIER * 2 * w["starters"] / tw
    pen = error * (BULLPEN_INNINGS / 9.0) * UNEARNED_MULTIPLIER * 2 * w["bullpens"] / tw
    return {"league_era_error": error, "runs_on_projection": starter + pen,
            "starters_share": starter, "bullpens_share": pen}


def slate(forecasts: list[Forecast]) -> str:
    if not forecasts:
        return "Nothing on the card."
    rows = sorted(forecasts, key=lambda f: -f.p_resolved)
    width = max(len(f.matchup) for f in rows)
    out = [f"{'GAME'.ljust(width)}  LINE   SIDE   PROB   PUSH   FAIR   BAND"]
    for f in rows:
        out.append(f"{f.matchup.ljust(width)}  {f.line:5g}  {f.side:<5}  "
                   f"{f.p_resolved * 100:5.1f}%  {f.p_push * 100:4.1f}%  "
                   f"{f.fair_price:+5.0f}  {f.band}")
    return "\n".join(out)
