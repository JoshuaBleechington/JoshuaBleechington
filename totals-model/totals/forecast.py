"""A forecaster, not a gate.

Every previous model in this project answered "should I bet?" and its most
common answer was no. This one answers a different question: **which side is
more likely, and how much more likely.** It names OVER or UNDER on every card
and attaches a probability. There is no PASS.

That is a real change of job, not a change of tone, so it needs a structure
that can support it.

The architecture
----------------
Each source of information produces its own **estimate of the final total**,
in the units of the market. The market's own number is one of those estimates
and carries the largest single weight, because measuring it is the one thing
this project has actually done: over 116 logged games the posted line beat a
fourteen-input statistical model on mean absolute error, 3.58 to 3.61.

The forecast is the weighted mean of the estimates:

    projected = sum(w_i * e_i) / sum(w_i)

and then tonight-only physical factors (wind, temperature) are added as deltas,
because they are not estimates of a total -- they are reasons the total should
differ from what the estimates say.

Two properties fall out of that shape, and both are things earlier versions had
to bolt on:

1. **Missing inputs re-weight themselves.** No head-to-head means the h2h term
   is simply absent from both sums, and the surviving weights renormalise. The
   model does not stall and does not need a special case -- it just becomes a
   blend of what is there. That is what "restructure its weight" means here.

2. **No coefficient caps are needed.** A weighted mean cannot run away: a
   signal screaming 11.7 into a line of 7.5 pulls the blend by its share of the
   weight and no further. Earlier models needed caps because they *summed*
   adjustments, and a sum has no ceiling. Averaging has one built in. The only
   guards left are typo guards.

Probability
-----------
    P(over) = Phi((projected - line) / dispersion)

Dispersion is the standard deviation of (final total - posted line), measured
where it could be measured. It is what stops a two-run projection gap turning
into a 90% claim: two runs is well under one standard deviation of MLB noise.

MLB is first five innings
-------------------------
This is the part worth taking seriously. F5 is not a smaller version of the
full game, it is a **cleaner** one:

* The bullpen is gone. Relief usage is the least predictable component of a
  baseball game and it decides a large share of full-game totals.
* Blowout effects are gone -- position players pitching, benches emptied, a
  closer sitting because it is 11-2.
* Extra innings and the ghost runner are gone.
* What is left is dominated by the two starting pitchers, who are the most
  predictable inputs in the sport, and who are known hours ahead.

So the noise the model is fighting is genuinely smaller. Dispersion is derived
rather than guessed: F5 scoring is about 53.6% of a full game, and run totals
behave close enough to Poisson that the standard deviation scales with the
square root of the mean, giving 4.39 * sqrt(0.536) = 3.21.

Half-run F5 lines also cannot push, which is a small structural gift: 4.5
always resolves.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

# --- league constants ------------------------------------------------------
#
# All of these are the anchors that make the estimates unbiased at league
# average. Get one wrong and every projection tilts the same way, which is the
# quietest kind of error a model of this shape can have.
LEAGUE_ERA = 4.30              # starter ERA, per 9
LEAGUE_RPG = 4.35              # runs per team per game
FULL_GAME_TOTAL = 8.70         # league average combined runs, all nine
F5_TOTAL = 4.66                # league average combined runs, first five
F5_SHARE = F5_TOTAL / FULL_GAME_TOTAL      # 0.536

F5_INNINGS = 5.0
UNEARNED_MULTIPLIER = 1.08     # ERA is earned runs; totals settle on all runs

# A league-average starter's ERA implies 2.58 runs across five innings once
# unearned runs are added, so two of them imply 5.16 -- half a run above the
# 4.66 that F5 games actually average. The gap is real and has two causes: a
# starter's ERA is spread over innings that include the third time through the
# order, which mostly happens after the fifth, and starts that collapse early
# hand F5 innings to the bullpen. Rather than pretend otherwise, the pitcher
# estimate is calibrated so two average starters project the league average.
PITCHER_CALIBRATION = F5_TOTAL / (
    2.0 * (LEAGUE_ERA / 9.0) * F5_INNINGS * UNEARNED_MULTIPLIER
)

# Standard deviation of (final total - posted line).
#
# MLB full-game 4.39 is measured over 116 settled games. F5 is derived from it
# rather than measured, because there is no F5 log yet: run totals are close
# enough to Poisson that sd scales with sqrt(mean), and F5 carries 53.6% of the
# runs. WNBA 11.51 comes from only 13 logged totals, which is far too few to
# trust as a point estimate; it is used because it is the only measurement
# available and because it agrees with the 11.0 the retired spread model used.
DISPERSION = {
    "MLB_F5": 4.39 * math.sqrt(F5_SHARE),
    "WNBA": 11.51,
}

# --- weights ---------------------------------------------------------------
#
# The market's weight is not modesty, it is the one measured fact this project
# owns. Everything else is weighted by how much independent information it
# plausibly carries once the market has spoken.
#
# MLB: the starters dominate F5 by construction, so they get the largest
# non-market weight. Form and head-to-head both measured null against the
# residual on the 116-game log (t = -0.07 and t = -0.40), so they are here on
# request and weighted accordingly -- present, able to move a close card, not
# able to overturn the market and the starters together.
#
# WNBA: no starter equivalent exists, so last-10 form carries the load. The
# sample behind these is 13 games, which is not enough to have tuned anything;
# they are reasoned, and they are stated here so they can be argued with.
WEIGHTS = {
    "MLB_F5": {"market": 3.0, "starters": 2.0, "form": 1.0, "h2h": 0.6},
    "WNBA": {"market": 3.0, "form": 1.6, "h2h": 1.0},
}

# --- bands -----------------------------------------------------------------
#
# Every card gets a side. The band describes how far from a coin flip it is,
# and nothing more. COIN FLIP is not a refusal to answer -- the answer is still
# printed, it just says the honest thing about how thin it is.
BANDS = (
    (0.62, "MAX"),
    (0.57, "STRONG"),
    (0.53, "LEAN"),
    (0.00, "COIN FLIP"),
)

# Plausibility windows. Everything here is a typo guard rather than a model
# choice: a blank field read as 0.00 and 401 innings per start both arrived
# dressed as unusually high confidence in earlier versions of this project.
PLAUSIBLE = {
    "era": (0.00, 15.0),
    "park": (70.0, 130.0),
    "mlb_total": (2.0, 20.0),
    "wnba_total": (110.0, 230.0),
}

# Wind and temperature, scaled to five innings from the full-game coefficients.
WIND_DEAD_MPH = 8.0
WIND_RUNS_PER_MPH = 0.10 * F5_SHARE
TEMP_BASE_F = 70.0
TEMP_RUNS_PER_DEG = 0.008 * F5_SHARE

# WNBA absences. A twelve-deep roster with starters at 32+ minutes has no bench
# to absorb a loss, so it costs a WNBA team more than the same news costs any
# other league's team.
POINTS_PER_STARTER_OUT = 2.0
POINTS_LEADING_SCORER_OUT = 3.5


def _ok(value: float | None, window: str) -> bool:
    if value is None:
        return False
    lo, hi = PLAUSIBLE[window]
    return lo <= value <= hi


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


@dataclass
class Estimate:
    """One source's opinion about tonight's total, and how much it counts."""

    name: str
    total: float
    weight: float
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "total": round(self.total, 2),
                "weight": self.weight, "detail": self.detail}


@dataclass
class Delta:
    """A tonight-only reason the total should differ from the estimates.

    Kept separate from Estimate on purpose. Wind is not an opinion about how
    many runs these teams score, it is a physical adjustment to whatever number
    the opinions land on, and blending it as though it were an estimate would
    be a category error.
    """

    name: str
    runs: float
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "runs": round(self.runs, 3),
                "detail": self.detail}


@dataclass
class Forecast:
    sport: str
    matchup: str
    line: float
    projected: float
    p_over: float
    side: str
    band: str
    estimates: list[Estimate]
    deltas: list[Delta]
    notes: list[str] = field(default_factory=list)

    @property
    def p_side(self) -> float:
        """The probability of the side actually named."""
        return self.p_over if self.side == "OVER" else 1.0 - self.p_over

    @property
    def edge_runs(self) -> float:
        return self.projected - self.line

    def to_dict(self) -> dict[str, Any]:
        return {
            "sport": self.sport,
            "matchup": self.matchup,
            "line": self.line,
            "projected": round(self.projected, 2),
            "p_over": round(self.p_over, 4),
            "p_side": round(self.p_side, 4),
            "side": self.side,
            "band": self.band,
            "estimates": [e.to_dict() for e in self.estimates],
            "deltas": [d.to_dict() for d in self.deltas],
            "notes": self.notes,
        }

    def brief(self) -> str:
        arrow = "over" if self.side == "OVER" else "under"
        out = [
            f"{self.matchup} — {self.side} {self.line:g}  "
            f"{self.p_side * 100:.1f}%  [{self.band}]",
            f"  projected {self.projected:.2f} against a line of {self.line:g} "
            f"({self.edge_runs:+.2f} to the {arrow})",
        ]
        total_w = sum(e.weight for e in self.estimates)
        for e in self.estimates:
            share = e.weight / total_w * 100 if total_w else 0.0
            out.append(f"    {e.name:<16} {e.total:7.2f}  {share:4.0f}% of weight")
        for d in self.deltas:
            out.append(f"    {d.name:<16} {d.runs:+7.2f}  delta")
        out.extend(f"  note: {n}" for n in self.notes)
        return "\n".join(out)


# ===========================================================================
# MLB, first five innings
# ===========================================================================

def starter_f5_runs(era: float, opponent_rpg: float | None = None) -> float:
    """Runs a starter is expected to allow across five innings.

    ERA is per nine and counts earned runs only, so it is scaled to five
    innings, lifted for unearned runs, and calibrated so a league-average pair
    projects the league-average F5 total. If the opposing lineup's runs per
    game is known the estimate scales with it -- a 5.10 offence is not the same
    assignment as a 3.60 one, and ERA alone cannot tell them apart.
    """
    runs = era / 9.0 * F5_INNINGS * UNEARNED_MULTIPLIER * PITCHER_CALIBRATION
    if opponent_rpg is not None and opponent_rpg > 0:
        runs *= opponent_rpg / LEAGUE_RPG
    return runs


def park_scale(park_factor: float | None) -> float:
    """Tonight's park as a multiplier, or 1.0 for missing or implausible.

    This is applied to the estimates built from team and pitcher statistics,
    which are park-neutral by construction, and never to the market anchor --
    the posted number already holds the park, and applying it twice is the
    double count that put the fourteen-input model behind the naked line.
    """
    if not _ok(park_factor, "park"):
        return 1.0
    return park_factor / 100.0


def forecast_mlb_f5(
    matchup: str,
    line: float,
    away_starter_era: float | None = None,
    home_starter_era: float | None = None,
    away_rpg: float | None = None,
    home_rpg: float | None = None,
    away_last5_total: float | None = None,
    home_last5_total: float | None = None,
    h2h_total: float | None = None,
    h2h_meetings: int | None = None,
    park_factor: float | None = None,
    wind_mph: float | None = None,
    wind_direction: str | None = None,
    temp_f: float | None = None,
    dome: bool = False,
) -> Forecast:
    """Forecast the first-five-innings total.

    Form and head-to-head are given as **full-game** averages, because that is
    what every site publishes, and converted to F5 internally. Asking for a
    number nobody prints is how inputs end up guessed at.
    """
    if not _ok(line, "mlb_total"):
        raise ValueError(f"F5 line {line!r} is outside {PLAUSIBLE['mlb_total']}")

    w = WEIGHTS["MLB_F5"]
    park = park_scale(park_factor)
    estimates: list[Estimate] = [
        Estimate("Market", line, w["market"],
                 f"The posted F5 number, {line:g}. Carries the largest single "
                 "weight because it is the only estimate here that has been "
                 "measured against results — over 116 logged games the line "
                 "beat a fourteen-input model on mean error, 3.58 to 3.61.")
    ]
    notes: list[str] = []

    # --- the starters ------------------------------------------------------
    if _ok(away_starter_era, "era") and _ok(home_starter_era, "era"):
        away_runs = starter_f5_runs(away_starter_era, home_rpg)
        home_runs = starter_f5_runs(home_starter_era, away_rpg)
        total = (away_runs + home_runs) * park
        lineup = ""
        if away_rpg or home_rpg:
            lineup = (" Scaled for the lineups each man faces"
                      f"{f' (home {home_rpg:.2f}' if home_rpg else ''}"
                      f"{f', away {away_rpg:.2f} runs per game)' if away_rpg else ')' if home_rpg else ''}.")
        estimates.append(Estimate(
            "Starters", total, w["starters"],
            f"Away {away_starter_era:.2f} ERA projects {away_runs:.2f} runs over five, "
            f"home {home_starter_era:.2f} projects {home_runs:.2f}.{lineup}"
            + (f" Park {park_factor:.0f} scales it to {total:.2f}." if park != 1.0 else "")
            + " This is the input F5 exists to isolate: no bullpen, no blowout "
              "effects, no extra innings — just the two most predictable arms in "
              "the game.")
        )
    elif _ok(away_starter_era, "era") or _ok(home_starter_era, "era"):
        notes.append("Only one starter's ERA was given. The pair is scored together "
                     "or not at all, so the starters are out of the blend and their "
                     "weight has gone to the market and whatever else is present.")

    # --- recent form -------------------------------------------------------
    if away_last5_total is not None and home_last5_total is not None:
        full = (away_last5_total + home_last5_total) / 2.0
        total = full * F5_SHARE * park
        estimates.append(Estimate(
            "Recent form", total, w["form"],
            f"Last-five full-game totals average {full:.1f}, which is {full * F5_SHARE:.2f} "
            f"across five innings"
            + (f", {total:.2f} in this park" if park != 1.0 else "") +
            ". Measured t = −0.07 against the residual on 116 games, so it is "
            "weighted to move a close card and not to overturn one."
        ))

    # --- head to head ------------------------------------------------------
    if h2h_total is not None and h2h_meetings:
        total = h2h_total * F5_SHARE * park
        estimates.append(Estimate(
            f"Head to head ({h2h_meetings})", total, w["h2h"],
            f"{h2h_meetings} meetings averaging {h2h_total:.1f} full-game, "
            f"{total:.2f} across five innings. Measured t = −0.40, the weakest "
            "thing in the blend, and it holds the smallest weight because of it."
        ))
        if h2h_meetings < 3:
            notes.append(f"Only {h2h_meetings} head-to-head meeting(s). Two games is "
                         "not a trend — treat that estimate as barely information.")
    elif h2h_total is None:
        notes.append("No head-to-head. Its weight has been redistributed across the "
                     "estimates that are present, so the forecast is a blend of "
                     "those rather than a partial answer.")

    # --- tonight-only deltas ----------------------------------------------
    deltas: list[Delta] = []
    if dome:
        deltas.append(Delta("Roof shut", 0.0,
                            "Closed roof — wind and temperature are both out."))
    else:
        if wind_mph is not None and wind_direction:
            d = wind_direction.strip().lower()
            if d in ("out", "in"):
                effective = max(0.0, wind_mph - WIND_DEAD_MPH)
                runs = effective * WIND_RUNS_PER_MPH * park
                deltas.append(Delta("Wind", runs if d == "out" else -runs,
                    f"{wind_mph:.0f} mph blowing {d}. Nothing counts under "
                    f"{WIND_DEAD_MPH:.0f} mph, then {WIND_RUNS_PER_MPH:.3f} runs per mph "
                    "over it — the full-game coefficient cut to five innings."))
            elif d == "cross":
                deltas.append(Delta("Wind", 0.0,
                    f"{wind_mph:.0f} mph across the field, which carries a fly ball "
                    "neither way."))
        if temp_f is not None:
            deltas.append(Delta("Temperature", (temp_f - TEMP_BASE_F) * TEMP_RUNS_PER_DEG,
                f"{temp_f:.0f}°F against a {TEMP_BASE_F:.0f}° baseline."))

    return _assemble("MLB_F5", matchup, line, estimates, deltas, notes)


# ===========================================================================
# WNBA
# ===========================================================================

def forecast_wnba(
    matchup: str,
    line: float,
    away_last10_total: float | None = None,
    home_last10_total: float | None = None,
    h2h_total: float | None = None,
    h2h_meetings: int | None = None,
    away_starters_out: int = 0,
    home_starters_out: int = 0,
    away_leading_scorer_out: bool = False,
    home_leading_scorer_out: bool = False,
) -> Forecast:
    """Forecast a WNBA total from last-ten form, head to head and absences."""
    if not _ok(line, "wnba_total"):
        raise ValueError(f"WNBA line {line!r} is outside {PLAUSIBLE['wnba_total']}")

    w = WEIGHTS["WNBA"]
    estimates = [
        Estimate("Market", line, w["market"],
                 f"The posted total, {line:g}. Largest single weight for the same "
                 "reason as always: it is the estimate with a measured record.")
    ]
    notes: list[str] = []

    if away_last10_total is not None and home_last10_total is not None:
        total = (away_last10_total + home_last10_total) / 2.0
        estimates.append(Estimate(
            "Last 10", total, w["form"],
            f"Combined totals over the last ten average {away_last10_total:.1f} away "
            f"and {home_last10_total:.1f} home, blending to {total:.1f}. Ten games is "
            "a third of a WNBA season, which is why this carries the largest "
            "non-market weight here — there is no starting-pitcher equivalent to "
            "lean on."
        ))

    if h2h_total is not None and h2h_meetings:
        estimates.append(Estimate(
            f"Head to head ({h2h_meetings})", h2h_total, w["h2h"],
            f"{h2h_meetings} meetings averaging {h2h_total:.1f}. Same clubs, same "
            "matchup problems, and in a twelve-team league they meet often enough "
            "for it to mean something."
        ))
        if h2h_meetings < 3:
            notes.append(f"Only {h2h_meetings} head-to-head meeting(s) — thin.")
    else:
        notes.append("No head-to-head on file. Its weight has gone to the market and "
                     "the last-ten form, which now carry the whole blend between "
                     "them. The forecast is not weaker for the absence, it is just "
                     "built from fewer things.")

    deltas: list[Delta] = []
    for team, out, leader in (("Away", away_starters_out, away_leading_scorer_out),
                              ("Home", home_starters_out, home_leading_scorer_out)):
        if out <= 0 and not leader:
            continue
        points = out * POINTS_PER_STARTER_OUT
        if leader:
            points += POINTS_LEADING_SCORER_OUT - POINTS_PER_STARTER_OUT
        deltas.append(Delta(f"{team} absences", -points,
            f"{out} rotation player(s) out"
            + (", including their leading scorer" if leader else "") +
            f". A twelve-deep roster with starters at 32+ minutes has no bench to "
            f"absorb it, so this is worth more here than the same news is worth in "
            f"any other league: {points:.1f} points off the total."))

    return _assemble("WNBA", matchup, line, estimates, deltas, notes)


# ===========================================================================

def _assemble(sport: str, matchup: str, line: float,
              estimates: list[Estimate], deltas: list[Delta],
              notes: list[str]) -> Forecast:
    """Blend the estimates, apply the deltas, and name a side.

    The renormalisation is the whole trick: weights are divided by whatever
    total is actually present, so a missing input costs the model information
    and never costs it an answer.
    """
    total_weight = sum(e.weight for e in estimates)
    if total_weight <= 0:                       # unreachable: market is always there
        raise ValueError("no estimates to blend")

    blended = sum(e.total * e.weight for e in estimates) / total_weight
    projected = blended + sum(d.runs for d in deltas)

    sd = DISPERSION[sport]
    p_over = normal_cdf((projected - line) / sd)

    # A tie goes to the over by the same rule in every implementation of this,
    # because a half-point difference between the Python and the browser was a
    # real bug once and it flipped a card.
    side = "OVER" if p_over >= 0.5 - 1e-9 else "UNDER"
    p_side = p_over if side == "OVER" else 1.0 - p_over
    band = next(name for floor, name in BANDS if p_side >= floor)

    if len(estimates) == 1:
        notes.append("Nothing was entered but the line, so the forecast IS the line "
                     "and the answer is a coin flip. That is not the model being coy "
                     "— with no information the posted number is the best estimate "
                     "there is.")
    if band == "MAX":
        notes.append("Top band. Worth re-reading the inputs before acting on it — "
                     "in this project a spectacular number has more often been a "
                     "mistyped one than a real edge.")
    return Forecast(sport, matchup, line, projected, p_over, side, band,
                    estimates, deltas, notes)


def slate(forecasts: list[Forecast]) -> str:
    """The night's card, strongest conviction first."""
    if not forecasts:
        return "Nothing on the card."
    rows = sorted(forecasts, key=lambda f: -f.p_side)
    width = max(len(f.matchup) for f in rows)
    out = [f"{'GAME'.ljust(width)}  LINE   SIDE   PROB   BAND"]
    for f in rows:
        out.append(f"{f.matchup.ljust(width)}  {f.line:5g}  {f.side:<5}  "
                   f"{f.p_side * 100:5.1f}%  {f.band}")
    return "\n".join(out)
