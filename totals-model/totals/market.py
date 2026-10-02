"""Odds conversion, vig removal, expected value and Kelly staking.

Everything here is pure arithmetic on prices -- no sport-specific logic.
"""

from __future__ import annotations

from dataclasses import dataclass


def american_to_decimal(odds: float) -> float:
    """-110 -> 1.909, +150 -> 2.50."""
    if odds == 0:
        raise ValueError("American odds cannot be 0")
    if odds > 0:
        return 1.0 + odds / 100.0
    return 1.0 + 100.0 / abs(odds)


def decimal_to_american(dec: float) -> float:
    if dec <= 1.0:
        raise ValueError("Decimal odds must be > 1.0")
    if dec >= 2.0:
        return round((dec - 1.0) * 100.0)
    return round(-100.0 / (dec - 1.0))


def american_to_prob(odds: float) -> float:
    """Implied probability *including* the book's vig."""
    return 1.0 / american_to_decimal(odds)


def prob_to_american(prob: float) -> float:
    """Fair (no-vig) American price for a probability."""
    if not 0.0 < prob < 1.0:
        raise ValueError("Probability must be strictly between 0 and 1")
    return decimal_to_american(1.0 / prob)


@dataclass(frozen=True)
class DevigResult:
    p_over: float
    p_under: float
    hold: float  # book's theoretical margin, e.g. 0.0455 == 4.55%


def devig(over_odds: float, under_odds: float, method: str = "multiplicative") -> DevigResult:
    """Strip the vig out of a two-way market to get the market's true estimate.

    ``multiplicative`` just normalises the two implied probabilities so they sum
    to 1. ``power`` raises both to a common exponent, which is a better fit when
    the two sides are priced far apart (a heavy favourite is over-juiced by the
    proportional method).
    """
    raw_over = american_to_prob(over_odds)
    raw_under = american_to_prob(under_odds)
    booksum = raw_over + raw_under
    hold = booksum - 1.0

    if method == "multiplicative":
        return DevigResult(raw_over / booksum, raw_under / booksum, hold)

    if method == "power":
        # Solve for k where raw_over**k + raw_under**k == 1 (bisection is plenty).
        lo, hi = 0.5, 3.0
        for _ in range(200):
            k = (lo + hi) / 2.0
            total = raw_over**k + raw_under**k
            if total > 1.0:
                lo = k
            else:
                hi = k
        k = (lo + hi) / 2.0
        p_over = raw_over**k
        return DevigResult(p_over, 1.0 - p_over, hold)

    raise ValueError(f"Unknown devig method: {method!r}")


def ev_per_unit(prob: float, odds: float, push_prob: float = 0.0) -> float:
    """Expected profit per 1 unit risked. Pushes return the stake, so they only
    dilute -- they are neither a win nor a loss."""
    win = prob
    lose = 1.0 - prob - push_prob
    if lose < -1e-9:
        raise ValueError("prob + push_prob exceeds 1")
    lose = max(lose, 0.0)
    return win * (american_to_decimal(odds) - 1.0) - lose


def kelly_fraction(prob: float, odds: float, push_prob: float = 0.0, multiplier: float = 0.25) -> float:
    """Fraction of bankroll to risk. ``multiplier`` is the fractional-Kelly knob;
    0.25 (quarter Kelly) is the sane default for a model this simple.

    Pushes are handled by renormalising over the decided outcomes.
    """
    decided = 1.0 - push_prob
    if decided <= 0:
        return 0.0
    p = prob / decided
    b = american_to_decimal(odds) - 1.0
    edge = p * b - (1.0 - p)
    if edge <= 0 or b <= 0:
        return 0.0
    return (edge / b) * multiplier * decided
