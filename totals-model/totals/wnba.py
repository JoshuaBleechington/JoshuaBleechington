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

# League baselines -- update once a season. WNBA plays 40-minute games, so pace
# is possessions per 40, not per 48. These are 2024-25 ballpark figures.
LEAGUE_PACE = 80.0
LEAGUE_RATING = 101.0

# Empirical spread of a WNBA final total around its projection.
TOTAL_SD = 11.5
# Empirical spread of the final margin, used only for the overtime estimate.
MARGIN_SD = 11.0

HOME_COURT_POINTS = 2.5  # applied to margin, total-neutral
B2B_RATING_PENALTY = 2.0  # points per 100 possessions off a team's offence
B2B_PACE_BUMP = 0.0  # tired legs play a touch slower; left off by default

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

    def adjusted_off_rating(self) -> float:
        if self.on_back_to_back:
            return self.off_rating - B2B_RATING_PENALTY
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
        },
    )
