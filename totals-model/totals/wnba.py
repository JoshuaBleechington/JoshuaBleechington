"""WNBA total points.

Basketball totals decompose cleanly into two questions: how many possessions
will there be, and how many points per possession will each side get. Everything
else is noise around those two numbers.

    possessions = pace_A * pace_B / lg_pace
    ppp_A       = off_rating_A * def_rating_B / lg_rating
    points_A    = possessions * ppp_A / 100

Four numbers per team -- pace, offensive rating, defensive rating, days of rest.

Home court is applied to the margin only, not the total: home teams win by more,
they do not systematically play higher- or lower-scoring games.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .core import Projection
from .distributions import normal_pdf, normal_total_probs

# League baselines -- CHECK THESE EVERY SEASON. WNBA plays 40-minute games, so
# pace is possessions per 40, not per 48.
#
# Both constants sit in denominators (possessions divide by lg_pace, efficiency
# divides by lg_rating), so a stale value biases every projection the same way
# rather than washing out. Too low inflates totals and makes the model call the
# over on everything, which is a stuck clock, not an edge.
#
# Calibrate these against the MARKET, not against results. The model's average
# projection should sit on the market's average implied mean; whatever edge a
# four-input model has is in the game-to-game variation, not in knowing the
# league's overall scoring level better than the books do.
#
# That test is also enormously cheaper. Over eight logged games the gap between
# the model's mean and the market's mean had a standard error of 0.8 points; the
# gap between the model's mean and the actual finals had a standard error of
# 3.5. The market is a stable reference with no game randomness in it, so eight
# games calibrate the level. Hundreds would be needed to do it off results.
#
# Measured that way at 105.8 the model sat +2.04 points above the market on
# every game (se 0.80). 107.0 zeroes it.
#
# A tempting alternative derivation is the identity that every point scored is a
# point allowed, so the league's mean offensive and defensive ratings must be
# equal, and equal to this constant. Averaging twelve of the thirteen teams
# gives 108.1 -- and using it makes the model WORSE, pushing it 1.8 points below
# the market. The identity is sound; the inputs violate its premise, because the
# pace figures and the ratings come off different possession estimates. Two
# numbers from different sources cannot be combined by an identity that assumes
# they share a denominator. The market comparison needs no such assumption,
# which is why it is the one to trust.
LEAGUE_PACE = 80.0
LEAGUE_RATING = 107.0

# Empirical spread of a WNBA final total around its projection.
TOTAL_SD = 11.5
# Empirical spread of the final margin, used only for the overtime estimate.
MARGIN_SD = 11.0

HOME_COURT_POINTS = 2.5  # applied to margin, total-neutral
B2B_RATING_PENALTY = 2.0  # points per 100 possessions off a team's offence
B2B_PACE_BUMP = 0.0  # tired legs play a touch slower; left off by default

# One day of rest is not a back-to-back, but it is not rest either. The B2B
# penalty was gated at zero days, and across the first WNBA games logged nothing
# ever hit zero -- the lowest rest entered was 1 -- so the adjustment never fired
# at all, including on two games where both sides were on one day and the total
# missed by 12 to 20 points. WnbaTeam defaults rest_days to 2, which says plainly
# that two days is the normal baseline; one day therefore has to cost something.
# Half the full penalty, to be revisited once more games are logged.
SHORT_REST_RATING_PENALTY = 1.0

OT_POINTS = 19.0  # typical combined scoring in a 5-minute overtime
OT_CALIBRATION = 1.5  # real tie rates run above the normal approximation


@dataclass
class WnbaTeam:
    name: str
    pace: float
    off_rating: float
    def_rating: float
    rest_days: int = 2

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "WnbaTeam":
        return cls(
            name=d.get("name", "?"),
            pace=float(d.get("pace", LEAGUE_PACE)),
            off_rating=float(d.get("off_rating", LEAGUE_RATING)),
            def_rating=float(d.get("def_rating", LEAGUE_RATING)),
            rest_days=int(d.get("rest_days", 2)),
        )

    @property
    def on_back_to_back(self) -> bool:
        return self.rest_days <= 0

    @property
    def on_short_rest(self) -> bool:
        return self.rest_days == 1

    def adjusted_off_rating(self) -> float:
        if self.on_back_to_back:
            return self.off_rating - B2B_RATING_PENALTY
        if self.on_short_rest:
            return self.off_rating - SHORT_REST_RATING_PENALTY
        return self.off_rating

    def adjusted_pace(self) -> float:
        if self.on_back_to_back:
            return self.pace - B2B_PACE_BUMP
        return self.pace


def overtime_points(margin: float) -> float:
    """Expected points added by overtime, given the projected margin.

    Games projected close go to OT more often, and a WNBA overtime adds roughly
    19 combined points when it happens.
    """
    p_ot = min(0.15, OT_CALIBRATION * normal_pdf(0.0, margin, MARGIN_SD))
    return p_ot * OT_POINTS


def project(game: dict[str, Any]) -> Projection:
    league = game.get("league", {})
    lg_pace = float(league.get("pace", LEAGUE_PACE))
    lg_rating = float(league.get("rating", LEAGUE_RATING))

    away = WnbaTeam.from_dict(game["away"])
    home = WnbaTeam.from_dict(game["home"])

    possessions = away.adjusted_pace() * home.adjusted_pace() / lg_pace

    away_ppp = away.adjusted_off_rating() * home.def_rating / lg_rating
    home_ppp = home.adjusted_off_rating() * away.def_rating / lg_rating

    away_pts = possessions * away_ppp / 100.0
    home_pts = possessions * home_ppp / 100.0

    # Total-neutral home court: shift the margin, leave the sum alone.
    hca = float(game.get("home_court_points", HOME_COURT_POINTS))
    home_pts += hca / 2.0
    away_pts -= hca / 2.0

    ot = overtime_points(home_pts - away_pts)
    away_pts += ot / 2.0
    home_pts += ot / 2.0

    sd = float(game.get("total_sd", TOTAL_SD))

    def build_probs(away_score: float, home_score: float):
        return lambda line: normal_total_probs(away_score + home_score, sd, line)

    return Projection(
        sport="WNBA",
        away=away.name,
        home=home.name,
        away_score=away_pts,
        home_score=home_pts,
        build_probs=build_probs,
        notes={
            "projected_possessions": round(possessions, 1),
            "expected_ot_points": round(ot, 2),
            "away_b2b": away.on_back_to_back,
            "home_b2b": home.on_back_to_back,
            "away_short_rest": away.on_short_rest,
            "home_short_rest": home.on_short_rest,
        },
    )
