"""The late-factor model: adjust the posted total, never try to replace it.

Why this exists
---------------
The old MLB verdict projected a total from team season stats -- runs per game,
starter ERA, bullpen ERA, park, temperature -- and bet the gap between that
projection and the posted line. Over 116 logged games it did not work, and the
reason is measurable rather than a matter of taste:

* Mean absolute error of the projection against the final total: 3.61 runs.
  Mean absolute error of *just using the posted line*: 3.58 runs. The model was
  a slightly noisier copy of the number it was betting against.
* Ridge regression on all fourteen collected inputs, leave-one-out
  cross-validated, produced a negative out-of-sample R-squared at every
  regularisation strength (best -0.055), improving monotonically as the fit was
  forced toward using none of them. Betting that fit's own out-of-sample side
  went 44-69.
* The largest single-feature correlation with (final total - posted line) was
  temperature at t = -1.60. Nothing cleared |t| = 2.

That is not a weighting problem. Every one of those inputs is published,
public, and already inside the number before it is posted. There is no gap to
find, so no arrangement of them finds one.

The premise here
----------------
The posted total is the best forecast available, and this model does not
compete with it. It starts from the line and adjusts only for things that

1. have a documented effect on run scoring large enough to matter, and
2. are not reliably in the number at the time you see it -- they break late,
   or they are ignored by the recreational money that sets the opening price.

If none of those inputs are supplied, the model returns no edge. It does not
manufacture one out of season statistics. A read with nothing behind it is the
failure mode this whole rewrite exists to remove.

Honesty about the coefficients
------------------------------
Each adjustment carries a ``basis`` of either ``"documented"`` or
``"provisional"``. Documented means the effect size comes from published
research or public umpire/park data. Provisional means it is a placeholder
sized by reasoning, waiting on enough logged games to fit properly, and the
verdict says so out loud. Nothing here is tuned on the 116 games above --
those games contain none of these inputs, which is exactly why they are new.

Everything is measured in runs, and the sign convention is: positive pushes
the total up (toward the over), negative pushes it down.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .distributions import TotalProbs, normal_total_probs

# Standard deviation of (final total - posted line), measured over the 116
# settled MLB games in the track record. This is the number that converts a
# run adjustment into a win probability, and it is why small edges stay small:
# a full run of adjustment is only a quarter of a standard deviation.
RESIDUAL_SD = 4.39

# League baseline for the umpire comparison. Overridable per game.
LEAGUE_RUNS_PER_GAME = 8.6

# Umpire samples are noisy. An umpire with 40 plate games behind his figure
# gets his difference from league shrunk hard; one with 400 keeps most of it.
# Shrinkage is n / (n + UMPIRE_SHRINK_GAMES).
UMPIRE_SHRINK_GAMES = 120.0
# Every other term here is bounded and this one was not: an umpire typed in at
# 40 runs a game on 200 games produced a +23 run adjustment and a 100% verdict.
# Impossible inputs were the source of the worst calls this project ever made,
# so the term is capped and the raw figure is range-checked as well.
UMPIRE_CAP_RUNS = 1.0
UMPIRE_PLAUSIBLE_RPG = (6.0, 12.0)

# Wind does nothing below this, then scales roughly linearly. Sized so that a
# 15 mph wind straight out moves the total about 0.7 runs and 20 mph about
# 1.2 -- inside the 1-2 run range the published work reports for strong winds.
WIND_DEAD_ZONE_MPH = 8.0
WIND_RUNS_PER_MPH = 0.10
WIND_CAP_RUNS = 1.5

# Runs per degree away from a 70F baseline. Small, real, and the one weather
# term the market does price reasonably well, so it is deliberately modest.
TEMP_BASELINE_F = 70.0
TEMP_RUNS_PER_DEGREE = 0.008
TEMP_CAP_RUNS = 0.35

# Provisional. One unavailable high-leverage reliever means roughly an inning
# thrown by a worse arm; the gap between a setup man and the long man is on
# the order of a run and a half of ERA, over about an inning.
RUNS_PER_UNAVAILABLE_RELIEVER = 0.15
MAX_RELIEVERS_COUNTED = 3

# Provisional. A regular replaced by a bench bat, over four or five plate
# appearances.
RUNS_PER_MISSING_REGULAR = 0.12
MAX_REGULARS_COUNTED = 3

# Bands, in win probability. Deliberately stricter than the old ladder: -110
# needs 52.38% to break even, so the first band that names a bet starts above
# it rather than at it.
BREAKEVEN_110 = 0.5238
BAND_STRONG = 0.560
BAND_PLAYABLE = 0.535
BAND_SLIM = BREAKEVEN_110
BANDS = ("NO EDGE", "SLIM", "PLAYABLE", "STRONG")


@dataclass
class Adjustment:
    """One reason tonight's total should differ from the posted number."""

    name: str
    runs: float
    basis: str          # "documented" or "provisional"
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "runs": round(self.runs, 3),
            "basis": self.basis,
            "detail": self.detail,
        }


def _f(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def umpire_adjustment(game: dict[str, Any]) -> Adjustment | None:
    """The home plate umpire's own run environment, regressed for sample size.

    The input is the umpire's runs per game across the games he has worked the
    plate, which RotoWire, OddsShark and RefMetrics all publish daily alongside
    the assignment. Assignments post the morning of the game, which is the
    point: the opening total does not always have them.

    Rather than assume an effect size, this uses the umpire's own measured
    number and shrinks it toward league average by how many games are behind
    it. An umpire 0.6 runs above league on 300 games keeps most of that; the
    same 0.6 on 30 games keeps a fifth of it.
    """
    ump = game.get("umpire") or {}
    rpg = _f(ump.get("runs_per_game"))
    if rpg is None:
        return None
    games = _f(ump.get("games")) or 0.0
    league = _f(ump.get("league_runs_per_game")) or LEAGUE_RUNS_PER_GAME
    name = ump.get("name") or "the plate umpire"
    lo, hi = UMPIRE_PLAUSIBLE_RPG
    if not (lo <= rpg <= hi):
        return Adjustment(
            "Umpire", 0.0, "documented",
            f"{rpg:.2f} runs a game is outside the {lo:.0f}-{hi:.0f} range any umpire "
            "lives in, so it is being read as a typo and ignored rather than trusted.",
        )
    raw = rpg - league
    shrink = games / (games + UMPIRE_SHRINK_GAMES) if games > 0 else 0.0
    runs = max(-UMPIRE_CAP_RUNS, min(UMPIRE_CAP_RUNS, raw * shrink))
    return Adjustment(
        "Umpire",
        runs,
        "documented",
        f"{name} runs {rpg:.2f} a game against a {league:.2f} league average, "
        f"on {games:.0f} games. Regressed for that sample it is worth "
        f"{runs:+.2f} runs, not the {raw:+.2f} the raw split shows.",
    )


def wind_adjustment(game: dict[str, Any]) -> Adjustment | None:
    """Wind speed and direction, which is the largest weather term by far.

    Direction is what matters and it is why the old model's lone ``wind_mph_out``
    field was close to useless: it was almost never filled in, and it carried no
    sense of a cross wind doing nothing. Accepts "out", "in", or "cross".
    """
    weather = game.get("weather") or {}
    if weather.get("dome"):
        return Adjustment("Wind", 0.0, "documented", "Roof is closed; wind is not a factor.")
    mph = _f(weather.get("wind_mph"))
    direction = (weather.get("wind_direction") or "").strip().lower()
    if mph is None or direction not in ("out", "in", "cross"):
        return None
    if direction == "cross":
        return Adjustment(
            "Wind", 0.0, "documented",
            f"{mph:.0f} mph across the field, which does not carry a fly ball either way.",
        )
    effective = max(0.0, mph - WIND_DEAD_ZONE_MPH)
    magnitude = min(WIND_CAP_RUNS, effective * WIND_RUNS_PER_MPH)
    runs = magnitude if direction == "out" else -magnitude
    if effective <= 0:
        detail = (f"{mph:.0f} mph is below the {WIND_DEAD_ZONE_MPH:.0f} mph "
                  "where wind starts to carry, so no adjustment.")
    else:
        detail = (f"{mph:.0f} mph blowing {direction}, which is {effective:.0f} mph "
                  f"past the dead zone and worth {runs:+.2f} runs.")
    return Adjustment("Wind", runs, "documented", detail)


def temperature_adjustment(game: dict[str, Any]) -> Adjustment | None:
    """Air density. Real, small, and largely priced -- kept modest on purpose."""
    weather = game.get("weather") or {}
    if weather.get("dome"):
        return None
    temp = _f(weather.get("temp_f"))
    if temp is None:
        return None
    raw = (temp - TEMP_BASELINE_F) * TEMP_RUNS_PER_DEGREE
    runs = max(-TEMP_CAP_RUNS, min(TEMP_CAP_RUNS, raw))
    return Adjustment(
        "Temperature", runs, "documented",
        f"{temp:.0f}F against a {TEMP_BASELINE_F:.0f}F baseline, worth {runs:+.2f} runs.",
    )


def bullpen_availability_adjustment(game: dict[str, Any]) -> Adjustment | None:
    """Who threw last night and cannot go tonight.

    This is the input with the best claim to being genuinely unpriced: it
    breaks after lines open, it is reported in beat writers' morning notes
    rather than in any stat line, and season bullpen ERA cannot see it at all.
    The coefficient is provisional until there are logged games to fit it to.
    """
    total = 0.0
    parts: list[str] = []
    for side in ("away", "home"):
        team = game.get(side) or {}
        out = _f(team.get("relievers_unavailable"))
        if out is None or out <= 0:
            continue
        counted = min(out, MAX_RELIEVERS_COUNTED)
        total += counted * RUNS_PER_UNAVAILABLE_RELIEVER
        name = team.get("name") or side
        parts.append(f"{name} are down {counted:.0f} high-leverage arm"
                     f"{'s' if counted != 1 else ''}")
    if not parts:
        return None
    return Adjustment(
        "Bullpen availability", total, "provisional",
        "; ".join(parts) + f". Worth {total:+.2f} runs on a placeholder "
        "coefficient that has not been backtested yet.",
    )


def lineup_adjustment(game: dict[str, Any]) -> Adjustment | None:
    """Regulars out of tonight's lineup. Provisional, same as the bullpen term."""
    total = 0.0
    parts: list[str] = []
    for side in ("away", "home"):
        team = game.get(side) or {}
        out = _f(team.get("regulars_out"))
        if out is None or out <= 0:
            continue
        counted = min(out, MAX_REGULARS_COUNTED)
        total -= counted * RUNS_PER_MISSING_REGULAR
        name = team.get("name") or side
        parts.append(f"{name} are without {counted:.0f} regular"
                     f"{'s' if counted != 1 else ''}")
    if not parts:
        return None
    return Adjustment(
        "Lineup", total, "provisional",
        "; ".join(parts) + f". Worth {total:+.2f} runs on a placeholder "
        "coefficient that has not been backtested yet.",
    )


BUILDERS = (
    umpire_adjustment,
    wind_adjustment,
    temperature_adjustment,
    bullpen_availability_adjustment,
    lineup_adjustment,
)


def band_for(win_pct: float) -> str:
    if win_pct >= BAND_STRONG:
        return "STRONG"
    if win_pct >= BAND_PLAYABLE:
        return "PLAYABLE"
    if win_pct >= BAND_SLIM:
        return "SLIM"
    return "NO EDGE"


@dataclass
class LateVerdict:
    matchup: str
    line: float
    adjustments: list[Adjustment]
    total_runs: float
    projected_total: float
    side: str
    win_pct: float
    p_push: float
    band: str
    documented_runs: float
    provisional_runs: float
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": "late-factor",
            "matchup": self.matchup,
            "line": self.line,
            "adjustments": [a.to_dict() for a in self.adjustments],
            "total_runs": round(self.total_runs, 3),
            "projected_total": round(self.projected_total, 2),
            "side": self.side,
            "win_pct": round(self.win_pct, 4),
            "p_push": round(self.p_push, 4),
            "band": self.band,
            "documented_runs": round(self.documented_runs, 3),
            "provisional_runs": round(self.provisional_runs, 3),
            "notes": self.notes,
        }


def decide_late(game: dict[str, Any]) -> LateVerdict:
    """Adjust tonight's posted total, and say how little that is worth.

    Raises if no line is supplied. Returns NO EDGE -- honestly, with the reason
    named -- when no late factor is known, rather than inventing a lean out of
    season statistics.
    """
    line = _f(game.get("line"))
    if line is None:
        raise ValueError("A posted total is required: set 'line'.")

    away = (game.get("away") or {}).get("name") or "Away"
    home = (game.get("home") or {}).get("name") or "Home"

    adjustments = [a for a in (b(game) for b in BUILDERS) if a is not None]
    total_runs = sum(a.runs for a in adjustments)
    documented = sum(a.runs for a in adjustments if a.basis == "documented")
    provisional = sum(a.runs for a in adjustments if a.basis == "provisional")

    projected = line + total_runs
    probs: TotalProbs = normal_total_probs(projected, RESIDUAL_SD, line)
    decided = 1.0 - probs.p_push
    p_over = probs.p_over / decided if decided > 0 else probs.p_over
    # With no adjustment the two sides are exactly even, and which one gets
    # named is a coin flip that floating point should not be deciding -- the
    # page's erf and this one disagree in the last bit and picked different
    # sides for the same game. A dead heat is OVER by convention, and the band
    # is NO EDGE either way, so the label is all that is at stake.
    side = "OVER" if p_over >= 0.5 - 1e-9 else "UNDER"
    win_pct = p_over if side == "OVER" else 1.0 - p_over

    notes: list[str] = []
    if not adjustments:
        notes.append(
            "No late factor was supplied, so there is nothing here the posted "
            "number does not already know. That is a genuine no-bet, not a "
            "weak read: this model has no opinion without an umpire, a wind, "
            "or an availability note."
        )
    if provisional and abs(provisional) > abs(documented):
        notes.append(
            f"Most of this edge ({provisional:+.2f} of {total_runs:+.2f} runs) rests "
            "on coefficients that have not been backtested. Treat it as a "
            "hypothesis being logged, not a priced bet."
        )
    if abs(total_runs) >= 1.0:
        notes.append(
            f"A {abs(total_runs):.2f} run adjustment is large for this model. "
            "Check the inputs before the number."
        )

    band = band_for(win_pct) if adjustments else "NO EDGE"

    return LateVerdict(
        matchup=f"{away} @ {home}",
        line=line,
        adjustments=adjustments,
        total_runs=total_runs,
        projected_total=projected,
        side=side,
        win_pct=win_pct,
        p_push=probs.p_push,
        band=band,
        documented_runs=documented,
        provisional_runs=provisional,
        notes=notes,
    )


def closing_line_value(opening: float, closing: float, side: str) -> dict[str, Any]:
    """Did the number move toward the side we took, and by how much.

    This is the metric the model is judged on now, not win-loss. Over 116 games
    a true 55% edge and a true 50% edge are statistically indistinguishable --
    the one standard deviation band is about nine points wide. Closing line
    value converges in a small fraction of that, because it measures whether
    the market agreed with us rather than whether the ball bounced our way.

    Beat the close on more than about 55% of bets and there is a real edge
    underneath, whatever the win-loss column happens to say that month.
    """
    move = closing - opening
    # We took the over: the number moving up means we got the better of it.
    beat = move > 0 if side == "OVER" else move < 0
    return {
        "opening": opening,
        "closing": closing,
        "side": side,
        "move": round(move, 2),
        "beat_close": bool(move != 0 and beat),
        "no_move": move == 0,
    }
