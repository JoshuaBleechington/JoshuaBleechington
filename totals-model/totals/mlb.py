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

# A starter's raw ERA is a terrible estimate of how he will pitch tonight. It is
# noisy at any realistic sample size, and the extremes are almost entirely luck:
# nobody's true talent is a 1.50 ERA or a 7.80 one. Betting markets price the
# talent, so a model fed raw ERA will disagree with the market by multiple runs
# and mistake that disagreement for edge.
#
# The fix is to regress toward league average, weighted by how many innings the
# ERA is actually built on:
#
#     regressed = (season_ip * era + PRIOR_IP * lg_era) / (season_ip + PRIOR_IP)
#
# PRIOR_IP is how many innings of league-average pitching to blend in. 100 is in
# line with what projection systems use for pitcher ERA. Feeding FIP or xERA
# instead of ERA is better still -- both are far more predictive, and FanGraphs
# lists them next to ERA on the same page.
STARTER_ERA_PRIOR_IP = 100.0

# Assumed season innings when the caller doesn't say. A rotation regular is
# around here by midsummer; supply the real number for anyone else.
DEFAULT_STARTER_SEASON_IP = 130.0

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


def regress_era(era: float, season_ip: float | None, lg_era: float,
                prior_ip: float = STARTER_ERA_PRIOR_IP) -> float:
    """Shrink a starter's ERA toward league average by how much it is worth.

    A 7.84 ERA over 40 innings says far less than a 3.10 over 160. Without this,
    one small-sample starter swings a projected total by two or three runs.
    """
    if season_ip is None or season_ip <= 0:
        season_ip = DEFAULT_STARTER_SEASON_IP
    return (season_ip * era + prior_ip * lg_era) / (season_ip + prior_ip)


def normalize_park_factor(pf: float) -> float:
    """Accept a park factor on either scale.

    Baseball Savant prints 102; the model wants 1.02. The two scales cannot
    overlap -- no ballpark is 5x run-neutral, and none is 5% of it -- so a value
    above 5 is unambiguously the 100 scale and can be converted rather than
    rejected. Entered on the wrong scale, a park factor is off by 100x and
    silently drives every projection to nonsense.
    """
    if pf > 5.0:
        return pf / 100.0
    return pf


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
    def from_dict(cls, d: dict[str, Any], lg_rpg: float, regress: bool = True) -> "MlbTeam":
        starter = _ra9(d, "starter", lg_rpg)
        if regress:
            # Regress in ERA space, where the prior is expressed, then convert back.
            lg_era = lg_rpg / ERA_TO_RA9
            starter = regress_era(
                starter / ERA_TO_RA9,
                d.get("starter_season_ip"),
                lg_era,
            ) * ERA_TO_RA9
        return cls(
            name=d.get("name", "?"),
            runs_per_game=float(d.get("runs_per_game", lg_rpg)),
            starter_ra9=starter,
            starter_ip=float(d.get("starter_ip", 5.2)),
            bullpen_ra9=_ra9(d, "bullpen", lg_rpg),
            own_park_factor=normalize_park_factor(float(d.get("own_park_factor", 1.0))),
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

    regress = bool(game.get("regress_starters", True))
    away = MlbTeam.from_dict(game["away"], lg_rpg, regress)
    home = MlbTeam.from_dict(game["home"], lg_rpg, regress)

    park = normalize_park_factor(float(game.get("park_factor", 1.0)))
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
