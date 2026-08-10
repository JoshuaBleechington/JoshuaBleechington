"""Shared types: a sport-agnostic projection and the market comparison step."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .distributions import TotalProbs
from .market import devig, ev_per_unit, kelly_fraction, prob_to_american

# How much to trust the model against the posted number. The closing line is a
# strong prior -- it already contains lineups, injuries and money. 0.5 means
# "meet the market halfway", which is where a model this size belongs. Push it
# toward 1.0 only after you have backtested your own inputs.
DEFAULT_MODEL_WEIGHT = 0.5

# Hard ceiling on a single bet, as a percentage of bankroll. Fractional Kelly on
# an overconfident projection will happily suggest 15%; it should not.
DEFAULT_MAX_STAKE_PCT = 2.0


@dataclass
class Projection:
    """What a sport model produces, before any odds are considered.

    ``build_probs`` takes a pair of projected scores and returns a function from
    a betting line to over/under/push probabilities. Keeping it as a builder
    rather than a fixed distribution is what lets the projection be nudged
    toward the market and re-scored without the sport model being involved.
    """

    sport: str
    away: str
    home: str
    away_score: float
    home_score: float
    build_probs: Callable[[float, float], Callable[[float], TotalProbs]]
    notes: dict[str, Any] = field(default_factory=dict)

    @property
    def total(self) -> float:
        return self.away_score + self.home_score

    @property
    def margin(self) -> float:
        """Positive means the home team is favoured."""
        return self.home_score - self.away_score

    def total_probs(self, line: float) -> TotalProbs:
        return self.build_probs(self.away_score, self.home_score)(line)

    def scaled(self, target_total: float) -> "Projection":
        """The same matchup rescaled to a different total, margin lean intact."""
        if self.total <= 0:
            return self
        k = target_total / self.total
        return Projection(
            sport=self.sport,
            away=self.away,
            home=self.home,
            away_score=self.away_score * k,
            home_score=self.home_score * k,
            build_probs=self.build_probs,
            notes=self.notes,
        )


def market_implied_total(projection: Projection, line: float, p_over_decided: float) -> float:
    """The mean that would make this model reproduce the market's own odds.

    A betting line is not a forecast of the mean. At -110 both ways the book is
    saying over and under are equally likely, which puts the line at the MEDIAN.
    Scoring distributions are right-skewed, so the median sits below the mean --
    by half a run to a full run in baseball.

    Blending a model's mean toward the line therefore compares two different
    quantities, and centring a right-skewed distribution on the line leaves more
    than half its mass underneath. The model then reports the under as favoured
    on every game, from the shape of the distribution alone, knowing nothing
    about the teams.

    Solving for the mean that reproduces the market's de-vigged probability
    converts the line into the same units as the projection, so the two can
    actually be averaged -- and deferring completely to the market now means
    agreeing with it, which is the only sensible reading of zero confidence.
    """
    lo, hi = max(0.25, line * 0.25), max(line * 2.5, line + 10.0)
    for _ in range(80):
        mid = (lo + hi) / 2.0
        probs = projection.scaled(mid).total_probs(line)
        decided = 1.0 - probs.p_push
        over = probs.p_over / decided if decided > 0 else probs.p_over
        if over < p_over_decided:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


@dataclass
class Market:
    line: float
    over_odds: float = -110.0
    under_odds: float = -110.0

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "Market | None":
        if not d:
            return None
        return cls(
            line=float(d["line"]),
            over_odds=float(d.get("over_odds", -110)),
            under_odds=float(d.get("under_odds", -110)),
        )


def evaluate(
    projection: Projection,
    market: Market | None,
    kelly_multiplier: float = 0.25,
    devig_method: str = "multiplicative",
    model_weight: float = DEFAULT_MODEL_WEIGHT,
    max_stake_pct: float = DEFAULT_MAX_STAKE_PCT,
) -> dict[str, Any]:
    """Combine a projection with a posted total and report where the edge is."""

    result: dict[str, Any] = {
        "sport": projection.sport,
        "matchup": f"{projection.away} @ {projection.home}",
        "model_away": round(projection.away_score, 2),
        "model_home": round(projection.home_score, 2),
        "model_total": round(projection.total, 2),
        "model_margin": round(projection.margin, 2),
        "notes": projection.notes,
    }

    if market is None:
        result["projected_total"] = result["model_total"]
        return result

    fair = devig(market.over_odds, market.under_odds, devig_method)
    # Put the line into the same units as the projection before averaging them.
    implied = market_implied_total(projection, market.line, fair.p_over)
    used_total = model_weight * projection.total + (1.0 - model_weight) * implied
    blended = projection.scaled(used_total)
    probs = blended.total_probs(market.line)

    over_ev = ev_per_unit(probs.p_over, market.over_odds, probs.p_push)
    under_ev = ev_per_unit(probs.p_under, market.under_odds, probs.p_push)

    side = "OVER" if over_ev >= under_ev else "UNDER"
    side_prob = probs.p_over if side == "OVER" else probs.p_under
    side_odds = market.over_odds if side == "OVER" else market.under_odds
    side_ev = max(over_ev, under_ev)
    market_prob = fair.p_over if side == "OVER" else fair.p_under

    stake = 100.0 * kelly_fraction(side_prob, side_odds, probs.p_push, kelly_multiplier)

    # Compare like with like. The model's probability is a share of *all*
    # outcomes, pushes included; the de-vigged market price is a share of
    # *decided* ones, since a push returns the stake and the book prices the
    # two sides against each other. On a whole-number line that gap is the
    # push probability -- large enough to print a negative edge next to a
    # positive EV, which reads like the model contradicting itself.
    decided = 1.0 - probs.p_push
    side_prob_decided = side_prob / decided if decided > 0 else side_prob

    result.update(
        {
            "line": market.line,
            "model_weight": model_weight,
            "projected_total": round(blended.total, 2),
            # The market's line expressed as a mean, so it can be compared with
            # the model's mean directly. This is the honest benchmark; the line
            # itself is a median and sits lower.
            "market_implied_total": round(implied, 2),
            "raw_edge": round(projection.total - implied, 2),
            "blended_edge": round(blended.total - implied, 2),
            "p_over": round(probs.p_over, 4),
            "p_under": round(probs.p_under, 4),
            "p_push": round(probs.p_push, 4),
            "market_p_over_novig": round(fair.p_over, 4),
            "book_hold": round(fair.hold, 4),
            "best_side": side,
            "best_side_prob": round(side_prob, 4),
            "best_side_odds": side_odds,
            "fair_odds": prob_to_american(side_prob) if 0 < side_prob < 1 else None,
            "prob_edge_vs_market": round(side_prob_decided - market_prob, 4),
            "best_side_prob_decided": round(side_prob_decided, 4),
            "ev_per_unit": round(side_ev, 4),
            "kelly_stake_pct": round(min(stake, max_stake_pct), 2),
            "kelly_uncapped_pct": round(stake, 2),
        }
    )
    return result
