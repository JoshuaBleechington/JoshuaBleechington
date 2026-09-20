"""Full-game MLB totals, modelled as a distribution rather than a mean.

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

# --- how much a starter's own ERA is worth knowing -------------------------
# An ERA is a measurement, and a short one is a noisy measurement. Without
# this block a September call-up's 5.24 in 22 innings carries exactly the
# authority of an ace's 5.24 in 190, which is plainly wrong and was costing
# whole runs of projection on call-up starts.
#
# Two numbers turn an innings count into a weight. Both are derived.
#
# ERA_OVERDISPERSION -- earned runs are not Poisson. They arrive in clusters,
# because the event that scores a run tends to score the two men already on.
# Measured at 1.75x Poisson variance, the same figure used elsewhere here.
#
# STARTER_TALENT_SD -- qualified starters' ERAs are spread about 1.05 apart.
# At a full season's ~150 innings the measurement noise alone is 0.60. Real
# spread and noise add in variance, so they subtract the same way:
# sqrt(1.05^2 - 0.60^2) = 0.86. Most of the gap between two starters at this
# point in a season is real talent. Not all of it.
ERA_OVERDISPERSION = 1.75
STARTER_TALENT_SD = 0.85

# The innings count at which a starter's own number is worth exactly as much
# as the league prior -- where you would split the difference 50/50. This is
# not chosen. It falls out of the two constants above:
#
#   measurement variance of an ERA over n innings = 9 * overdispersion * ERA / n
#   weight on the observation = talent_var / (talent_var + measurement_var)
#                             = n / (n + 9 * overdispersion * ERA / talent_var)
#
# The trailing term is this constant, about 91 innings. A call-up with 22
# innings keeps 20% of his own ERA and takes 80% of the league's. A starter
# at 143 innings keeps 61%. Nobody ever keeps 100%, which is correct: a
# season is a sample, not a reading.
ERA_STABLE_AT = 9.0 * ERA_OVERDISPERSION * LEAGUE_STARTER_ERA / STARTER_TALENT_SD ** 2

# Measured, not chosen: the standard deviation of (final total - posted line)
# over 116 settled MLB games.
RESIDUAL_SD = {"MLB": 4.39}

# Overdispersion, phi = variance / mean, derived rather than picked:
# 4.39^2 / 9.04 = 2.13. Holding phi constant rather than the variance means
# the spread scales with the size of the game, which is how count data
# behaves -- a projected 12-run game is genuinely noisier than a 6-run one.
DISPERSION_PHI = {"MLB": RESIDUAL_SD["MLB"] ** 2 / LEAGUE_COMBINED_RPG}

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
}

# One meeting is not eight meetings' worth of evidence.
H2H_FULL_WEIGHT_AT = 4.0

# Bands. Every card gets a side; the band says what to do about it.
#
# These were called MAX / STRONG / LEAN / COIN FLIP, which described a distance
# from even and left the reader to work out whether that was a bet. It is not a
# reader's job to translate "LEAN 56.5%" into an action, and a 56.5% call losing
# then reads as a broken model rather than as the 43.5% of the time it is
# supposed to lose. The floors are unchanged to the decimal -- only the words.
BANDS = ((0.62, "MAX BET"), (0.57, "STRONG BET"), (0.53, "BET"), (0.00, "NO BET"))

#: Card rows written before the rename. Kept so an old backup still groups with
#: the new names instead of splitting the record across two spellings.
LEGACY_BANDS = {"MAX": "MAX BET", "STRONG": "STRONG BET",
                "LEAN": "BET", "COIN FLIP": "NO BET"}

# --- corroboration ---------------------------------------------------------
# An input that was MEASURED to be worth nothing may move the forecast. It may
# not, on its own, buy a confidence band.
#
# Four of the MLB inputs are tagged `mechanism=False`. Form and head to head
# because they measured null against the residual on 116 games (t = -0.07 and
# t = -0.40) and because they are absolutes rather than differentials, so they
# lean toward the league mean regardless of where the line sits. The public
# money split because its coefficient is a flat hand-capped 0.30 -- the
# direction is documented, the size is not.
#
# And, added 2026-09-20, THE STARTERS. Measured the same way on 156 settled
# games, the starter differential correlates with the market's error at
# r = -0.076, t = -0.95 -- null, and pointing the wrong way. It also carries
# the worst mean absolute error of any real input on the board (3.157 against
# the market's 2.803), and the full blend containing it predicts finals WORSE
# than the market anchor alone (2.868 against 2.803).
#
# That is a stronger case than either of the two already tagged, so leaving it
# untagged was the inconsistency. It keeps its 1.6 weight and still moves every
# projection; it simply may no longer buy a band by itself.
#
# The band is therefore cut from the LESS confident of two reads: the full
# blend, and the same blend with those four deleted. If deleting them changes
# the side, there is no call and the band is held at NO BET.
#
# Nothing outside MLB is ever tagged, and the reason matters. The t statistics
# above come from an MLB residual study; no equivalent exists for any other
# book here. Demoting an input on evidence is discipline. Demoting one on a
# hunch is the sort of unjustified coefficient this model exists to remove.

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
    "innings": (0.0, 400.0),
    "percent": (0.0, 100.0),
    "park": (70.0, 130.0),
    "mlb_total": (4.0, 20.0),
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


def split_for(sport: str, line: float, mu: float) -> tuple[float, float, float]:
    if sport == "MLB":
        return nb_split(line, mu, DISPERSION_PHI["MLB"])
    return nb_split(line, mu, DISPERSION_PHI["MLB"])


# ===========================================================================
# The market's own fair total, recovered from the two prices
# ===========================================================================

def implied(price: float) -> float:
    """American odds to implied probability, vig included."""
    return (-price) / ((-price) + 100.0) if price < 0 else 100.0 / (price + 100.0)


def hold(over_price: float, under_price: float) -> float:
    """The bookmaker's margin on the pair. Main-line totals run 4-5%."""
    return implied(over_price) + implied(under_price) - 1.0


# A wide market is not a sharper opinion, it is a less certain one.
#
# Found on 2026-09-04: a total entered at 8.5 when the main number had moved to
# 9 picked up an ALTERNATE-line quote of -150/-110 -- a 12.4% hold where every
# other game on that card sat at 2.4-4.8%. De-vigging that proportionally read
# 53.4% over and pushed the card from LEAN to STRONG.
#
# Proportional de-vig assumes the margin splits between the two sides in
# proportion to their probabilities. That assumption is harmless at a 5% hold
# and increasingly arbitrary at 12%, because most of what is being split is
# markup rather than opinion. So the de-vigged deviation from even is shrunk by
# how far the hold exceeds a normal main-line one, and the answer regresses
# toward the no-information point instead of toward a number the quote never
# really expressed.
#
# Note this is NOT Shin's method, which was the first thing tried. Shin corrects
# favourite-longshot bias and moves the favourite UP (-150/-110 reads 53.8%
# under Shin against 53.4% proportional). That is a real effect and the wrong
# one here: it would have made the alt line more confident, not less.
HOLD_REFERENCE = 0.05

# --- one price is not no price ---------------------------------------------
# A card with the over at -120 and the under box left empty used to have its
# price thrown away entirely: `fair_total` fell back to "assume -110/-110" and
# the heaviest input on the board (weight 4.0) went in blind. On a real card
# that cost 1.8 points of probability -- a -120 over is the book saying fair
# sits north of the posted number, and that survives perfectly well without its
# partner.
#
# The missing side is reconstructed by assuming the book charged its usual
# margin. Both numbers below are MEASURED on 133 priced cards in the logged
# book, not chosen:
#
#     5th pct 4.34% | 25th 4.62% | median 4.71% | 75th 6.44% | 90th 6.80%
#
# The point estimate uses the median. The CONFIDENCE uses the 90th percentile,
# because a reconstructed quote is a less certain thing than a real one and
# should not be handed the same authority. That is the same posture as the
# corroboration gate: when two readings are available, act on the less
# confident one. At a -120 over it keeps 51.5% rather than the 52.0% a real
# 4.71%-hold pair would have given.
TYPICAL_HOLD = 0.047
HOLD_90TH = 0.068


def complete_pair(over_price: float | None,
                  under_price: float | None) -> tuple[float, float] | None:
    """Reconstruct a missing side of a quote at the book's usual margin.

    Returns None when both sides are present (nothing to do) or when neither
    is (nothing to work from).
    """
    have_o = over_price is not None
    have_u = under_price is not None
    if have_o == have_u:
        return None
    known = implied(over_price if have_o else under_price)
    other = (1.0 + TYPICAL_HOLD) - known
    # A quote so lopsided that the usual margin cannot cover it is not a main
    # line. Fall back rather than invent a price on the far side of certainty.
    if not (0.01 < other < 0.99):
        return None
    other_price = price_for(other)
    return (over_price, other_price) if have_o else (other_price, under_price)


def market_confidence(book_hold: float) -> float:
    """How much of a de-vigged deviation from even to keep, 0 to 1."""
    if book_hold <= HOLD_REFERENCE:
        return 1.0
    return HOLD_REFERENCE / book_hold


def devig(over_price: float, under_price: float, shrink: bool = True,
          confidence_hold: float | None = None) -> tuple[float, float]:
    """Strip the hold. Returns (fair P over, fair P under).

    With ``shrink`` the deviation from even is regressed for an unusually wide
    market; pass False for the raw proportional figure.

    ``confidence_hold`` cuts the confidence against a different hold than the
    one the pair actually shows. It exists for a reconstructed quote, whose
    hold is assumed rather than observed and which therefore must not inherit
    the full authority of a real one.
    """
    o, u = implied(over_price), implied(under_price)
    s = o + u
    p_over = o / s
    if shrink:
        against = (s - 1.0) if confidence_hold is None else confidence_hold
        p_over = 0.5 + (p_over - 0.5) * market_confidence(against)
    return p_over, 1.0 - p_over


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
    rebuilt = None if quoted else complete_pair(over_price, under_price)
    if rebuilt is not None:
        over_price, under_price = rebuilt
        quoted = True
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
    p_over, _ = devig(over_price, under_price,
                      confidence_hold=None if rebuilt is None else HOLD_90TH)
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
    book_hold = hold(over_price, under_price)
    conf = market_confidence(book_hold)
    if not quoted:
        return mu, (
            f"No prices given, so an evenly-priced market is assumed. A line of {line:g} "
            f"splitting 50/50 implies a mean of {mu:.2f} — run totals are right-skewed, "
            "so the average game finishes above the number that divides the two sides."
        )
    raw, _ = devig(over_price, under_price, shrink=False)
    if rebuilt is not None:
        kept = market_confidence(HOLD_90TH)
        return mu, (
            f"Only one price was given, so the other side was reconstructed at the "
            f"{TYPICAL_HOLD * 100:.1f}% hold this book typically charges (measured across the "
            f"logged card), giving {over_price:+.0f}/{under_price:+.0f}. That de-vigs to "
            f"{p_over * 100:.1f}% over and puts fair at {mu:.2f} rather than the {line:g} "
            f"posted — a one-sided price still says which way the market leans. Because the "
            f"hold here is assumed rather than observed, the confidence is cut against the "
            f"{HOLD_90TH * 100:.1f}% this book charges at its 90th percentile, so only "
            f"{kept * 100:.0f}% of the {raw * 100:.1f}% read is kept. Enter both prices and "
            f"none of this guesswork is needed."
        )
    tail = ""
    if conf < 1.0:
        tail = (f" That is a {book_hold * 100:.1f}% hold where a main line runs "
                f"{HOLD_REFERENCE * 100:.0f}% — most likely an ALTERNATE line rather than "
                f"the main number. A wide market is a less certain one, not a sharper one, "
                f"so the read has been pulled back from {raw * 100:.1f}% toward even and only "
                f"{conf * 100:.0f}% of it is kept. Enter the main line and its prices if you "
                f"have them.")
    return mu, (
        f"{over_price:+.0f}/{under_price:+.0f} de-vigs to {p_over * 100:.1f}% over "
        f"({book_hold * 100:.2f}% hold), which is the market saying fair is {mu:.2f} "
        f"rather than the {line:g} it posted." + tail
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
    #: False for an input measured to be worth ~nothing, or capped by hand. It
    #: still moves the forecast; it just cannot buy a band on its own.
    mechanism: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "total": round(self.total, 3),
                "weight": round(self.weight, 4), "detail": self.detail,
                "mechanism": self.mechanism}


@dataclass
class Delta:
    name: str
    runs: float
    detail: str
    mechanism: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "runs": round(self.runs, 3), "detail": self.detail,
                "mechanism": self.mechanism}


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
    #: The same blend with the measured-null and hand-capped inputs deleted.
    projected_corroborated: float = 0.0
    #: `p_resolved` of that read, on the side the full blend named. Below 0.5
    #: means the soft inputs are the only reason for the side.
    p_corroborated: float = 0.5
    #: What the band would have been without the gate. Shown, never acted on.
    band_ungated: str = "NO BET"

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
            "band_ungated": self.band_ungated,
            "projected_corroborated": round(self.projected_corroborated, 3),
            "p_corroborated": round(self.p_corroborated, 5),
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


def era_weight(innings: float | None) -> float:
    """How much of a starter's own ERA survives, given his innings count.

    Returns 1.0 when innings are unknown. That is deliberate and it is what
    keeps this change invisible to every card logged before it existed: leave
    the field blank and the ERA goes in at face value, exactly as it always
    did. The weight only ever comes down, never up, so supplying innings can
    only ever pull a starter toward league average -- it cannot manufacture
    an extreme.
    """
    if innings is None or not _ok(innings, "innings") or innings <= 0:
        return 1.0
    return innings / (innings + ERA_STABLE_AT)


def shrink_era(era: float | None, innings: float | None,
               league: float = LEAGUE_STARTER_ERA) -> float | None:
    """A starter's ERA pulled toward the league on the strength of its sample.

    Empirical Bayes, with the league mean as the prior and the innings count
    setting the weight. The posted 5.24 of a man with 22 innings is not a
    claim that he allows 5.24 runs per nine; it is a noisy reading whose 68%
    interval runs from 3.5 to 7.0. This returns the middle of what the number
    actually supports.
    """
    if era is None:
        return None
    return league + era_weight(innings) * (era - league)


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
    away_starter_ip: float | None = None,
    home_starter_ip: float | None = None,
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
    # Each ERA is first pulled toward the league by how many innings stand
    # behind it. Blank innings means no pull at all, so a card typed the old
    # way scores the old way to the decimal.
    aw, hw = era_weight(away_starter_ip), era_weight(home_starter_ip)
    away_era_used = shrink_era(away_starter_era, away_starter_ip)
    home_era_used = shrink_era(home_starter_era, home_starter_ip)
    a = arm_differential(away_era_used, LEAGUE_STARTER_ERA, STARTER_INNINGS, home_rpg)
    h = arm_differential(home_era_used, LEAGUE_STARTER_ERA, STARTER_INNINGS, away_rpg)
    if a is not None and h is not None:
        gap = (a + h) * park
        shrunk = ""
        if aw < 1.0 or hw < 1.0:
            parts = []
            if aw < 1.0:
                parts.append(f"away {away_starter_era:.2f} over {away_starter_ip:.1f} IP "
                             f"is worth {aw:.0%} of itself, so it enters at "
                             f"{away_era_used:.2f}")
            if hw < 1.0:
                parts.append(f"home {home_starter_era:.2f} over {home_starter_ip:.1f} IP "
                             f"is worth {hw:.0%} of itself, so it enters at "
                             f"{home_era_used:.2f}")
            shrunk = (" Pulled toward the league on sample size: " + "; ".join(parts) +
                      f". An ERA is worth half the league prior at {ERA_STABLE_AT:.0f} "
                      "innings, which is why a short season cannot carry a card.")
        # Anchored to the market's FAIR mean, not the posted line. Anchoring a
        # differential to the line while the market estimate sits at the fair
        # mean makes a zero differential drag the blend down toward the line --
        # two league-average staffs came back UNDER 51.9% that way, which is
        # the same class of hidden lean this rewrite exists to remove.
        estimates.append(Estimate(
            "Starters", anchor + gap, w["starters"],
            f"Away {away_era_used:.2f} and home {home_era_used:.2f} against a "
            f"{LEAGUE_STARTER_ERA:.2f} league starter ERA, over the {STARTER_INNINGS:.1f} "
            f"innings a start now covers: {gap:+.2f} runs on the line. Two league-average "
            "arms move it by exactly zero, which is what keeps this from carrying a "
            "hidden lean." + shrunk +
            " Measured null against the market's error on 156 games (r = -0.076, "
            "t = -0.95, sign backwards), so it moves this projection but cannot buy "
            "a band on its own.", mechanism=False))
        # A BLANK innings box is not "no shrinkage needed" -- it is "trust this
        # arm completely", which is more than 210 innings earns. So filling one
        # side and leaving the other empty makes the empty arm artificially
        # dominant, and on a 3.00-against-5.50 card it flips the side purely on
        # which box got typed into.
        if (aw < 1.0) != (hw < 1.0):
            notes.append(
                "Innings are in for one starter and not the other. A blank innings box "
                "means the ERA is trusted in full — more than any real innings count "
                "earns — so shrinking one arm while the other keeps full authority "
                "tilts the differential toward whichever box was left empty. On a close "
                "card that alone can flip the side. Fill in both or neither.")
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
            "not to overturn the market.", mechanism=False))

    if h2h_total is not None and h2h_meetings:
        weight = h2h_weight(w["h2h"], h2h_meetings)
        thin = ""
        if h2h_meetings < H2H_FULL_WEIGHT_AT:
            thin = (f" Discounted to {h2h_meetings:.0f}/{H2H_FULL_WEIGHT_AT:.0f} of its "
                    f"weight because it rests on {h2h_meetings:.0f} meeting(s).")
        estimates.append(Estimate(
            f"Head to head ({h2h_meetings:.0f})", h2h_total * park, weight,
            f"{h2h_meetings:.0f} meetings averaging {h2h_total:.1f}. Measured t = -0.40, "
            "the weakest thing in the blend." + thin, mechanism=False))
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

    # A percentage outside 0-100 is not a reading, it is a typo. A logged card
    # once carried money% = 925 (for 92.5) and the split delta fired at full
    # strength on it, moving that projection 0.30 runs. Same posture as an
    # implausible ERA: drop it and say so rather than believe it.
    for _name, _val in (("ticket", ticket_pct_over), ("money", money_pct_over)):
        if _val is not None and not _ok(_val, "percent"):
            notes.append(
                f"The {_name} percentage reads {_val:g}, which is not a percentage. It has "
                "been dropped rather than scored — check for a missing decimal point.")
    if not _ok(ticket_pct_over, "percent"):
        ticket_pct_over = None
    if not _ok(money_pct_over, "percent"):
        money_pct_over = None

    if ticket_pct_over is not None and money_pct_over is not None:
        gap = ticket_pct_over - money_pct_over
        if abs(gap) >= PUBLIC_SPLIT_MIN_GAP:
            deltas.append(Delta("Money split",
                -PUBLIC_SPLIT_RUNS if gap > 0 else PUBLIC_SPLIT_RUNS,
                f"Over holds {ticket_pct_over:.0f}% of tickets but {money_pct_over:.0f}% "
                f"of money, a {abs(gap):.0f}-point gap. Small bets on the over, big money "
                f"on the {'under' if gap > 0 else 'over'}. Capped flat: the direction is "
                "documented, the size is not.", mechanism=False))

    if opened is not None and abs(opened - line) > 1e-9:
        notes.append(
            f"The number moved {opened:g} to {line:g} ({line - opened:+.1f}). That is NOT "
            "scored — the current line is the anchor, so the move is already inside it and "
            "subtracting it again would double-count. It is here because a large move "
            "against your side is worth knowing before you bet.")

    return _assemble("MLB", matchup, line, estimates, deltas, notes)


# ===========================================================================
# ===========================================================================

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
    p_resolved = p_side / live if live > 0 else 0.5
    band_ungated = next(name for floor, name in BANDS if p_resolved >= floor)

    # --- corroboration -----------------------------------------------------
    # Re-run the blend with the measured-null and hand-capped inputs deleted,
    # and read the result on the side the full blend named. Nothing is tagged
    # when only the market and the arms are in, so this is a no-op on those
    # cards rather than an approximation of one.
    core = [e for e in estimates if e.mechanism]
    core_w = sum(e.weight for e in core)
    if core_w > 0:
        core_blend = sum(e.total * e.weight for e in core) / core_w
        core_proj = core_blend + sum(d.runs for d in deltas if d.mechanism)
    else:
        core_proj = projected
    c_over, _c_push, c_under = split_for(sport, line, core_proj)
    c_live = c_over + c_under
    c_side = c_over if side == "OVER" else c_under
    p_corroborated = c_side / c_live if c_live > 0 else 0.5

    if p_corroborated < 0.5:
        # The soft inputs are not merely adding confidence, they are the reason
        # for the side. That is not a bet.
        band = BANDS[-1][1]
    else:
        band = next(name for floor, name in BANDS
                    if min(p_resolved, p_corroborated) >= floor)

    if band != band_ungated:
        notes.append(
            f"Held at {band}, down from {band_ungated}. Delete last ten, head to head "
            f"and the money split -- the inputs measured worth nothing and the one "
            f"capped by hand -- and this card reads "
            + (f"{'OVER' if side == 'UNDER' else 'UNDER'} "
               f"{(1 - p_corroborated) * 100:.1f}%, the other side."
               if p_corroborated < 0.5 else
               f"{side} {p_corroborated * 100:.1f}% rather than "
               f"{p_resolved * 100:.1f}%.")
            + " Those inputs may move a forecast; they may not buy a band on their own.")

    if len(estimates) == 1 and not deltas:
        notes.append("Nothing entered but the number, so the forecast IS the market and "
                     "the answer is a coin flip. That is the correct answer to a question "
                     "with no information in it, not the model being coy.")
    if push > 0.02:
        notes.append(f"The line is a whole number, so {push * 100:.1f}% of the time this "
                     "pushes and the stake comes back. That probability is real and a "
                     "model that treats runs as continuous silently hands it to the two "
                     "sides instead.")
    if band == BANDS[0][1]:
        notes.append("Top band. Re-read the inputs before acting — in this project a "
                     "spectacular number has more often been a mistyped one than an edge.")
    return Forecast(sport, matchup, line, projected, over, push, under,
                    side, band, estimates, deltas, notes,
                    projected_corroborated=core_proj,
                    p_corroborated=p_corroborated,
                    band_ungated=band_ungated)


# ===========================================================================
# ALTERNATE LINES
#
# The strongest thing this file can do, and the only part that does not need the
# model to be right about anything.
#
# A book prices its main line efficiently -- that is the one fact this project
# has actually established, over 116 games. But it prices the ALTERNATE ladder
# off a template, and templates are coarse. Given the market's own fair total,
# recovered from the two main-line prices, the fair price at every other number
# is arithmetic on the same distribution. Comparing that to what the book offers
# is a RELATIVE judgement: it needs the main line to be efficient, and nothing
# else. No opinion about who wins, no forecasting edge, no thousands of settled
# bets to prove.
# ===========================================================================

def _price_index(p: float) -> float:
    """American odds as a CONTINUOUS scale, so cents can be subtracted.

    They are discontinuous at the century -- +100 and -100 are the same bet --
    so subtracting them directly reports a ten-cent move as two hundred. This
    maps ... +120, +110, 100, -110, -120 ... onto ... -20, -10, 0, +10, +20 ...
    """
    p = min(max(p, 1e-9), 1 - 1e-9)
    if p >= 0.5:
        return 100.0 * p / (1.0 - p) - 100.0
    return 100.0 - 100.0 * (1.0 - p) / p


def price_for(p: float) -> float:
    """Fair American odds for a resolved-outcome probability."""
    if abs(p - 0.5) < 1e-9:
        return 100.0
    return -100.0 * p / (1.0 - p) if p > 0.5 else 100.0 * (1.0 - p) / p


def cents_between(p_fair: float, offered: float) -> float:
    """How many cents better than fair the offered price is. Positive is value.

    The sign was backwards on the first pass and a test caught it: the index
    rises with implied probability, and a HIGHER implied probability is a WORSE
    price for the bettor -- you are laying more for the same outcome. So fair
    comes first. A test now pins that this never disagrees in sign with the
    expected value, which is the thing it is a proxy for.
    """
    return _price_index(p_fair) - _price_index(implied(offered))


@dataclass
class AltRung:
    line: float
    p_over: float          # resolved, push excluded
    p_push: float
    fair_over: float
    fair_under: float

    def to_dict(self) -> dict[str, Any]:
        return {"line": self.line, "p_over": round(self.p_over, 5),
                "p_push": round(self.p_push, 5),
                "fair_over": round(self.fair_over, 1),
                "fair_under": round(self.fair_under, 1)}


def alt_ladder(sport: str, main_line: float, over_price: float | None = None,
               under_price: float | None = None, span: float = 3.0,
               step: float = 0.5, mu: float | None = None) -> list[AltRung]:
    """Fair prices at every alternate total around `main_line`.

    `mu` overrides the anchor, so the same function serves both ladders: the
    MARKET one (leave it None -- derived from the main line's own prices, and
    the one worth acting on) and the MODEL one (pass the blended projection,
    which is only as good as the model).
    """
    if mu is None:
        mu, _why = fair_total(sport, main_line, over_price, under_price)
    rungs = []
    steps = int(round(span / step))
    for k in range(-steps, steps + 1):
        line = round(main_line + k * step, 2)
        if line <= 0:
            continue
        over, push, under = split_for(sport, line, mu)
        live = over + under
        p_over = over / live if live > 0 else 0.5
        rungs.append(AltRung(line, p_over, push,
                             price_for(p_over), price_for(1.0 - p_over)))
    return rungs


def alt_edge(rung: AltRung, side: str, offered: float) -> dict[str, Any]:
    """What the book is giving away, or taking, on one alternate rung."""
    p = rung.p_over if side == "OVER" else 1.0 - rung.p_over
    fair = rung.fair_over if side == "OVER" else rung.fair_under
    payout = (offered / 100.0) if offered > 0 else (100.0 / -offered)
    return {
        "line": rung.line, "side": side, "offered": offered, "fair": fair,
        "cents": cents_between(p, offered),
        "ev_per_unit": p * payout - (1.0 - p),
        "p_resolved": p,
        "p_push": rung.p_push,
    }


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


@dataclass
class MarginGuard:
    """How many points of margin over break-even are indistinguishable from none.

    The page used to carry a hand-written `OVERCONFIDENCE = 3.0`, whose comment
    claimed it was "measured, not chosen: the model has said 54.2% and done
    51.1%". That measurement was real when it was taken and is no longer true --
    on 110 graded calls the model now says 55.41% and does 55.45%, a gap of
    +0.05. A frozen constant that cites a live measurement goes stale silently,
    which is worse than an honest guess, because nobody re-checks a number that
    says it was measured.

    So it is computed instead, from two parts that are both real:

      bias  -- how overconfident the model has actually been, floored at zero.
               Running UNDERconfident does not buy anyone extra margin.
      noise -- the standard error on that hit rate. A gap you cannot tell from
               zero is not a gap, and at 110 calls one standard error is still
               4.8 points.

    The sum tightens on its own as the card grows -- 4.8 points at 110 calls,
    2.5 at 400, 1.6 at 1000 -- with no constant to go stale.
    """

    points: float
    n: int
    bias: float
    noise: float
    detail: str


def margin_guard(records: Iterable[tuple[float, bool]]) -> MarginGuard:
    """`records` as for `calibration()`: (probability given, did it win)."""
    rows = [(float(p), bool(w)) for p, w in records]
    n = len(rows)
    if n == 0:
        return MarginGuard(
            float("inf"), 0, 0.0, float("inf"),
            "No graded calls yet, so the model's calibration is entirely "
            "unmeasured. Nothing here has an established margin.")
    mean_p = sum(p for p, _ in rows) / n
    hit = sum(w for _, w in rows) / n
    bias = max(0.0, mean_p - hit)
    noise = math.sqrt(max(mean_p * (1.0 - mean_p), 1e-9) / n)
    points = bias + noise
    return MarginGuard(
        points, n, bias, noise,
        f"Over {n} graded calls the model says {mean_p * 100:.1f}% and does "
        f"{hit * 100:.1f}%. Overconfidence {bias * 100:.1f} points, standard error "
        f"{noise * 100:.1f}. A margin under {points * 100:.1f} points cannot be "
        "told apart from no margin at all.")


@dataclass
class ResidualSpread:
    """The measured spread of (final - line), against the constant in use.

    `RESIDUAL_SD` sets `DISPERSION_PHI`, which sets the skew, which sets how far
    above the line the distribution's mean sits. It was measured once, over 116
    games, and then frozen. This makes the drift visible instead of requiring
    someone to remember to go and re-measure it.

    It deliberately does NOT change the constant. A sample standard deviation is
    a noisy thing -- at 112 games the 95% interval is roughly a full run wide --
    and re-fitting a dispersion parameter to every fortnight is how a model ends
    up chasing its own residuals.
    """

    n: int
    measured: float
    lo: float
    hi: float
    assumed: float
    consistent: bool
    detail: str


def _chi2_quantile(p: float, k: int) -> float:
    """Wilson-Hilferty. Accurate to a fraction of a percent above k = 30."""
    z = _inv_norm(p)
    t = 1.0 - 2.0 / (9.0 * k) + z * math.sqrt(2.0 / (9.0 * k))
    return k * t ** 3


def _inv_norm(p: float) -> float:
    """Acklam's inverse normal CDF, plenty accurate for a confidence interval."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > ph:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def residual_spread(residuals: Iterable[float],
                    assumed: float | None = None) -> ResidualSpread:
    """`residuals` are (final total - posted line), pushes included."""
    xs = [float(x) for x in residuals]
    n = len(xs)
    if assumed is None:
        assumed = RESIDUAL_SD["MLB"]
    if n < 3:
        return ResidualSpread(n, 0.0, 0.0, float("inf"), assumed, True,
                              f"{n} settled games is not enough to measure a spread.")
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    sd = math.sqrt(var)
    k = n - 1
    lo = sd * math.sqrt(k / _chi2_quantile(0.975, k))
    hi = sd * math.sqrt(k / _chi2_quantile(0.025, k))
    ok = lo <= assumed <= hi
    return ResidualSpread(
        n, sd, lo, hi, assumed, ok,
        f"Over {n} settled games the spread of (final - line) measures {sd:.2f} "
        f"runs, 95% interval {lo:.2f} to {hi:.2f}. The model assumes {assumed:.2f}, "
        + ("which is inside that interval, so there is nothing to change yet."
           if ok else
           "which is OUTSIDE that interval. The dispersion constant, and the skew "
           "it sets, no longer match the games being logged."))


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
