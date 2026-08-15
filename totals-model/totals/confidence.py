"""A verdict model: which side, and how sure, on a High / Medium / Low scale.

This is a separate read on the same games as ``run_game``, not a replacement for
it, and it answers a different question. ``run_game`` asks "is this priced
wrong, and what should I risk". This asks only "do the numbers and the trends
agree that the total is going over, or under, and how strongly".

Three consequences follow from that, and they are the whole design:

* **No odds, no stake, no Kelly.** The only market input is the posted total.
  That is enough, because a line at even money is the point where the book
  thinks over and under are equally likely -- so solving for the mean at which
  this model would agree converts the line into the same units as a projection.
  Everything downstream is a probability, never a price.

* **Three independent signals, not one.** The matchup model, the head-to-head
  history and each side's recent form all get a vote, weighted by how much
  evidence is behind them. A projection is one opinion; three opinions that
  agree are a trend.

* **Confidence can only be lost, never gained.** The band starts at whatever the
  win probability earns, and every doubt -- signals pointing different ways, a
  starter with nine innings behind him, a projection miles from the market --
  knocks it down a step. Nothing knocks it up. Four separate faults in this
  project's history all presented as *high* confidence, so the asymmetry is
  deliberate: an unusually strong number is a reason for suspicion before it is
  a reason for conviction.

Park factors apply only to the park being played in. A team's own park does not
adjust its season rates here. That is a deliberate simplification: it costs a
little accuracy for road teams from extreme parks, and it removes a per-team
input that is easy to enter on the wrong scale and silently ruinous when it is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .core import Projection, market_implied_total

# --- how far a win probability has to get before it earns each band ----------
#
# These are deliberately not far above a coin flip. A totals model working from
# a handful of team numbers does not produce 65% reads; anything claiming to has
# almost always got a bad input rather than an insight. The bands describe how
# much the evidence leans, not how certain anyone should feel.
BAND_HIGH = 0.580
BAND_MEDIUM = 0.545
BAND_LOW = 0.520

BANDS = ("NO PLAY", "LOW", "MEDIUM", "HIGH")

# --- how much of the trust budget the trend signals may claim ----------------
#
# Head-to-head and recent form are real information and weak information. They
# are small samples of games played by different pitchers, different rotations
# and sometimes different rosters. Each may take at most a quarter of whatever
# trust is not being left with the market, and only reaches that share with a
# full sample behind it. The matchup model always keeps at least half.
H2H_SHARE = 0.25
FORM_SHARE = 0.25

# Games needed before a trend signal is at full strength. Head-to-head counts
# for more in basketball, where the same rosters meet again in the same season;
# in baseball tonight's starters were mostly not involved last time.
H2H_FULL_GAMES = {"MLB": 8.0, "WNBA": 4.0}
FORM_FULL_GAMES = {"MLB": 10.0, "WNBA": 8.0}

# A projection this far from the market is treated as a symptom, not a signal.
# Every large disagreement this model has produced in practice traced back to an
# input -- a park factor on the wrong scale, a blank ERA read as 0.00, a stale
# league constant -- rather than to an edge.
IMPLAUSIBLE_GAP = {"MLB": 2.0, "WNBA": 12.0}

# How far a signal must lean before it counts as disagreeing with the verdict,
# rather than merely being quiet.
DISSENT_THRESHOLD = {"MLB": 0.35, "WNBA": 2.5}

# What each field can physically be. A number outside its range is a typo, and
# typos do not announce themselves -- they get absorbed. An average of 401
# innings per start was silently read as "this starter pitches all nine", which
# removed the bullpen from the calculation entirely and moved the projection
# half a run. The model had no way to say so, because 401 clamps quietly to 9.
#
# These bounds are deliberately generous: they are not "unlikely", they are
# "impossible". Nobody's bullpen has a 0.4 ERA and nobody starts 40 innings.
# Anything outside them names itself in the flags and costs a confidence band.
FIELD_RANGES: dict[str, dict[str, tuple[float, float, str]]] = {
    "MLB": {
        "runs_per_game": (2.0, 8.0, "runs per game"),
        "starter_era": (0.5, 15.0, "starter ERA"),
        "starter_season_ip": (0.0, 300.0, "starter season IP"),
        "starter_ip": (1.0, 9.0, "average IP per start"),
        "bullpen_era": (1.0, 9.0, "bullpen ERA"),
    },
    "WNBA": {
        "pace": (60.0, 110.0, "pace"),
        "off_rating": (80.0, 130.0, "offensive rating"),
        "def_rating": (80.0, 130.0, "defensive rating"),
        "rest_days": (0.0, 14.0, "days rest"),
    },
}

# Plausible range for a game total, used to sanity-check the trend inputs.
TOTAL_RANGE = {"MLB": (0.0, 30.0), "WNBA": (100.0, 280.0)}


def _fmt(v: float) -> str:
    return f"{v:g}"


def _sentence_case(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


DEFAULT_TRUST = 0.5


@dataclass
class Signal:
    """One opinion about the total, in runs or points."""

    name: str
    value: float | None          # its own estimate of the mean total
    games: float                 # how many games of evidence behind it
    weight: float = 0.0          # share of the final projection it earns
    lean: float = 0.0            # value - market implied mean

    @property
    def present(self) -> bool:
        return self.value is not None and self.games > 0

    def side(self) -> str | None:
        if not self.present or self.lean == 0:
            return None
        return "OVER" if self.lean > 0 else "UNDER"


@dataclass
class Verdict:
    sport: str
    matchup: str
    line: float
    market_mean: float
    model_total: float
    projected_total: float
    side: str
    win_pct: float
    band: str
    signals: list[Signal]
    downgrades: list[str] = field(default_factory=list)
    downgrade_notes: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    notes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sport": self.sport,
            "matchup": self.matchup,
            "line": self.line,
            "market_mean": round(self.market_mean, 2),
            "model_total": round(self.model_total, 2),
            "projected_total": round(self.projected_total, 2),
            "side": self.side,
            "win_pct": round(self.win_pct, 4),
            "band": self.band,
            "signals": [
                {
                    "name": s.name,
                    "value": None if s.value is None else round(s.value, 2),
                    "games": s.games,
                    "weight": round(s.weight, 3),
                    "lean": round(s.lean, 2),
                    "side": s.side(),
                }
                for s in self.signals
            ],
            "downgrades": self.downgrades,
            "downgrade_notes": self.downgrade_notes,
            "flags": self.flags,
            "notes": self.notes,
        }


def _ramp(games: float, full: float) -> float:
    """0 with no evidence, 1 at a full sample, straight line between."""
    if games <= 0:
        return 0.0
    return min(1.0, games / full)


def build_signals(sport: str, game: dict[str, Any], market_mean: float,
                  model_total: float, trust: float) -> list[Signal]:
    """The matchup model, head-to-head, and recent form -- each with its share."""
    h2h = game.get("h2h") or {}
    form = game.get("form") or {}

    h2h_games = float(h2h.get("games", 0) or 0)
    h2h_value = h2h.get("avg_total")
    h2h_value = float(h2h_value) if h2h_value not in (None, "") and h2h_games > 0 else None

    form_games = float(form.get("games", 0) or 0)
    away_form = form.get("away_avg_total")
    home_form = form.get("home_avg_total")
    have_form = form_games > 0 and away_form not in (None, "") and home_form not in (None, "")
    # Each team's recent games are a sample of totals in games *they* were in.
    # Averaging the two is the neutral estimate for a game between them.
    form_value = (float(away_form) + float(home_form)) / 2.0 if have_form else None

    signals = [
        Signal("Matchup model", model_total, games=1.0),
        Signal("Head to head", h2h_value, games=h2h_games),
        Signal("Recent form", form_value, games=form_games),
    ]

    h2h_w = trust * H2H_SHARE * _ramp(h2h_games, H2H_FULL_GAMES[sport]) if signals[1].present else 0.0
    form_w = trust * FORM_SHARE * _ramp(form_games, FORM_FULL_GAMES[sport]) if signals[2].present else 0.0
    signals[1].weight = h2h_w
    signals[2].weight = form_w
    signals[0].weight = trust - h2h_w - form_w

    for s in signals:
        if s.present:
            s.lean = s.value - market_mean
    return signals


def quality_flags(sport: str, game: dict[str, Any], model_total: float,
                  market_mean: float) -> list[str]:
    """Reasons to trust this particular game's inputs less than usual."""
    flags: list[str] = []

    if abs(model_total - market_mean) > IMPLAUSIBLE_GAP[sport]:
        flags.append(
            f"the model is {abs(model_total - market_mean):.1f} "
            f"{'runs' if sport == 'MLB' else 'points'} from the market, which is "
            "usually a bad input rather than an edge"
        )

    for side in ("away", "home"):
        t = game.get(side) or {}
        name = t.get("name") or side

        if sport == "MLB":
            ip = t.get("starter_season_ip")
            if ip in (None, "") or float(ip or 0) <= 0:
                flags.append(
                    f"no season innings for the {name} starter, so he is a league average arm"
                )
            elif float(ip) < 40:
                flags.append(f"only {float(ip):.0f} innings behind the {name} starter's ERA")

        for key, (lo, hi, label) in FIELD_RANGES[sport].items():
            v = t.get(key)
            if v in (None, ""):
                # Season IP is the one field where blank is a real answer, and it
                # is already reported above.
                if key != "starter_season_ip":
                    flags.append(f"{name} {label} is blank")
                continue
            v = float(v)
            if key == "starter_season_ip" and v <= 0:
                continue  # already reported
            if v <= 0:
                flags.append(f"{name} {label} is blank")
            elif not lo <= v <= hi:
                flags.append(
                    f"{name} {label} is {_fmt(v)}, outside the possible range "
                    f"{_fmt(lo)}–{_fmt(hi)} — check that entry"
                )

    lo, hi = TOTAL_RANGE[sport]
    for block, key, label in (("h2h", "avg_total", "head-to-head average total"),
                              ("form", "away_avg_total", "away recent-form average"),
                              ("form", "home_avg_total", "home recent-form average")):
        src = game.get(block) or {}
        v = src.get(key)
        if v in (None, ""):
            continue
        v = float(v)
        if not lo <= v <= hi:
            flags.append(
                f"the {label} is {_fmt(v)}, outside the possible range "
                f"{_fmt(lo)}–{_fmt(hi)} — check that entry"
            )
    return flags


def band_for(win_pct: float) -> str:
    if win_pct >= BAND_HIGH:
        return "HIGH"
    if win_pct >= BAND_MEDIUM:
        return "MEDIUM"
    if win_pct >= BAND_LOW:
        return "LOW"
    return "NO PLAY"


def _step_down(band: str, steps: int = 1) -> str:
    i = BANDS.index(band)
    return BANDS[max(0, i - steps)]


def decide(sport: str, projection: Projection, game: dict[str, Any]) -> Verdict:
    """Project, blend the trends in, and grade how much to believe the result."""
    line = float(game["line"])
    trust = float(game.get("trust", DEFAULT_TRUST))
    trust = max(0.0, min(1.0, trust))

    # A line at even money is the market's median. Solve for the mean at which
    # this model reproduces it, so the line and the projection are comparable.
    market_mean = market_implied_total(projection, line, 0.5)
    model_total = projection.total

    signals = build_signals(sport, game, market_mean, model_total, trust)
    projected = market_mean + sum(s.weight * s.lean for s in signals if s.present)

    probs = projection.scaled(projected).total_probs(line)
    decided = 1.0 - probs.p_push
    p_over = probs.p_over / decided if decided > 0 else probs.p_over
    side = "OVER" if p_over >= 0.5 else "UNDER"
    win_pct = p_over if side == "OVER" else 1.0 - p_over

    band = band_for(win_pct)
    # Each downgrade carries a note saying what to actually look at. The headline
    # alone ("the inputs behind it are thin") names a category; the note names
    # the number. Kept as two parallel lists rather than one list of pairs so a
    # log saved before the notes existed still loads.
    downgrades: list[str] = []
    notes: list[str] = []
    unit = "runs" if sport == "MLB" else "points"

    # Dissent: a present signal pointing the other way, hard enough to mean it.
    for s in signals:
        if not s.present or s.weight <= 0:
            continue
        if s.side() and s.side() != side and abs(s.lean) >= DISSENT_THRESHOLD[sport]:
            downgrades.append(f"{s.name.lower()} points the other way ({s.side().lower()})")
            notes.append(
                f"It reads {s.value:.1f}, a gap of {abs(s.lean):.1f} {unit} the other way. "
                f"The projection is an average of signals that disagree, which is a weaker "
                f"thing than three that line up."
            )

    flags = quality_flags(sport, game, model_total, market_mean)
    if flags:
        downgrades.append("the inputs behind it are thin")
        notes.append(_sentence_case("; ".join(flags)) + ".")

    # No trend evidence at all means the matchup model is talking to itself.
    if not any(s.present and s.weight > 0 for s in signals[1:]):
        downgrades.append("no head-to-head or recent form to corroborate it")
        notes.append(
            "Only the matchup model voted. Filling in either trend would confirm the read "
            "or catch a bad input, and could put the band back up."
        )

    band = _step_down(band, len(downgrades))

    return Verdict(
        sport=sport,
        matchup=f"{projection.away} @ {projection.home}",
        line=line,
        market_mean=market_mean,
        model_total=model_total,
        projected_total=projected,
        side=side,
        win_pct=win_pct,
        band=band,
        signals=signals,
        downgrades=downgrades,
        downgrade_notes=notes,
        flags=flags,
        notes=dict(projection.notes, p_push=round(probs.p_push, 4), trust=trust),
    )
