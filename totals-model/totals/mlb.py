"""MLB total runs.

The engine is the standard odds-ratio (log5-style) matchup: a team's expected
runs are the league average scaled by how good the offence is and how good the
opposing run prevention is.

    runs = lg_rpg * (offence / lg_rpg) * (opposing_run_prevention / lg_rpg)
           * park * weather

Run prevention is a blend of the announced starter and the bullpen, weighted by
how deep the starter is expected to go. That single input does most of the work
in baseball totals, which is why it is worth entering by hand.

Only five numbers per team are required:
  runs_per_game, starter ERA (or RA/9), starter innings, bullpen ERA (or RA/9),
  plus the park factor for the venue.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .core import Projection
from .distributions import convolve, discrete_total_probs, negative_binomial_pmf

# League baselines -- CHECK THIS EVERY SEASON. 2026 is running ~9.04 combined
# runs per game, so 4.52 per team.
#
# This constant is not cosmetic. Expanding the odds-ratio leaves it net in the
# denominator (runs = offence * opposing_run_prevention / lg_rpg), so a stale
# value biases every single projection in the same direction. Setting it low
# inflates totals and tilts the model toward the over; setting it high does the
# reverse. At 4.40 against a true 4.52 environment, every game projected 2.7%
# high -- about a quarter of a run, enough to flip marginal games to the over.
LEAGUE_RUNS_PER_GAME = 4.52

# Earned runs are ~93% of all runs, so RA/9 runs a touch above ERA.
ERA_TO_RA9 = 1.075

# Negative binomial r. variance = mean + mean^2 / r; r = 4.0 gives sd ~3.0 at a
# 4.4 run mean, which matches the real distribution of team runs per game.
RUN_DISPERSION = 4.0

# Weather nudges, per unit, applied to the game total. Deliberately small.
TEMP_COEF_PER_DEGREE = 0.004  # ~4% swing per 10F away from 70F
WIND_COEF_PER_MPH = 0.008  # positive = blowing out, negative = blowing in
WEATHER_CLAMP = 0.10  # never let weather move the total more than 10%


def _ra9(team: dict[str, Any], prefix: str, default: float) -> float:
    """Accept either an RA/9 or an ERA for starter/bullpen."""
    if f"{prefix}_ra9" in team:
        return float(team[f"{prefix}_ra9"])
    if f"{prefix}_era" in team:
        return float(team[f"{prefix}_era"]) * ERA_TO_RA9
    return default


def _park_neutral(rate: float, own_park_factor: float) -> float:
    """Season rates are half home, half road, so a team's own park inflates them.

    Divide that out before applying tonight's park, otherwise a Coors team gets
    counted twice when they visit Coors and unfairly when they play in Seattle.
    """
    if own_park_factor == 1.0:
        return rate
    return rate / ((1.0 + own_park_factor) / 2.0)


def weather_factor(weather: dict[str, Any] | None) -> float:
    if not weather or weather.get("dome") or weather.get("roof_closed"):
        return 1.0
    factor = 1.0
    if "temp_f" in weather:
        factor *= 1.0 + TEMP_COEF_PER_DEGREE * (float(weather["temp_f"]) - 70.0)
    if "wind_mph_out" in weather:
        factor *= 1.0 + WIND_COEF_PER_MPH * float(weather["wind_mph_out"])
    return max(1.0 - WEATHER_CLAMP, min(1.0 + WEATHER_CLAMP, factor))


@dataclass
class MlbTeam:
    name: str
    runs_per_game: float
    starter_ra9: float
    starter_ip: float
    bullpen_ra9: float
    own_park_factor: float = 1.0

    @classmethod
    def from_dict(cls, d: dict[str, Any], lg_rpg: float) -> "MlbTeam":
        return cls(
            name=d.get("name", "?"),
            runs_per_game=float(d.get("runs_per_game", lg_rpg)),
            starter_ra9=_ra9(d, "starter", lg_rpg),
            starter_ip=float(d.get("starter_ip", 5.2)),
            bullpen_ra9=_ra9(d, "bullpen", lg_rpg),
            own_park_factor=float(d.get("own_park_factor", 1.0)),
        )

    def offence_index(self, lg_rpg: float) -> float:
        return _park_neutral(self.runs_per_game, self.own_park_factor) / lg_rpg

    def run_prevention_index(self, lg_rpg: float) -> float:
        """Blended starter + bullpen RA/9, relative to league, park-neutralised."""
        share = max(0.0, min(1.0, self.starter_ip / 9.0))
        blended = share * self.starter_ra9 + (1.0 - share) * self.bullpen_ra9
        return _park_neutral(blended, self.own_park_factor) / lg_rpg


def project(game: dict[str, Any]) -> Projection:
    league = game.get("league", {})
    lg_rpg = float(league.get("runs_per_game", LEAGUE_RUNS_PER_GAME))

    away = MlbTeam.from_dict(game["away"], lg_rpg)
    home = MlbTeam.from_dict(game["home"], lg_rpg)

    park = float(game.get("park_factor", 1.0))
    wx = weather_factor(game.get("weather"))
    # Home teams skip the bottom of the 9th when they lead, which cancels out
    # against hitting last. Left at 1.0; move it if your own numbers say so.
    home_factor = float(game.get("home_offence_factor", 1.0))

    away_runs = lg_rpg * away.offence_index(lg_rpg) * home.run_prevention_index(lg_rpg) * park * wx
    home_runs = (
        lg_rpg * home.offence_index(lg_rpg) * away.run_prevention_index(lg_rpg) * park * wx * home_factor
    )

    dispersion = float(game.get("dispersion", RUN_DISPERSION))

    def build_probs(away_score: float, home_score: float):
        pmf = convolve(
            negative_binomial_pmf(away_score, dispersion),
            negative_binomial_pmf(home_score, dispersion),
        )
        return lambda line: discrete_total_probs(pmf, line)

    return Projection(
        sport="MLB",
        away=away.name,
        home=home.name,
        away_score=away_runs,
        home_score=home_runs,
        build_probs=build_probs,
        notes={
            "park_factor": round(park, 3),
            "weather_factor": round(wx, 3),
            "away_starter_ra9": round(away.starter_ra9, 2),
            "home_starter_ra9": round(home.starter_ra9, 2),
        },
    )
