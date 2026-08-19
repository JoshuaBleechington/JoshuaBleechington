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

* **Up to four independent signals, not one.** The matchup model, the
  head-to-head history, each side's recent form, and -- for WNBA -- each
  side's record against the total all get a vote, weighted by how much
  evidence is behind them. A projection is one opinion; several that agree
  are a trend.

* **Confidence can only be lost, never gained.** The band starts at whatever the
  win probability earns, and every doubt -- signals pointing different ways, a
  starter with no innings behind him at all, a projection miles from the market
  -- knocks it down a step. Nothing knocks it up. Four separate faults in this
  project's history all presented as *high* confidence, so the asymmetry is
  deliberate: an unusually strong number is a reason for suspicion before it is
  a reason for conviction.

  LEAN sits one step below LOW for exactly this reason. A game whose numbers
  earned LOW or better, but that took a single doubt, still deserves a side --
  it is a weaker version of a real read, not nothing. NO PLAY is reserved for
  the games that never earned a read in the first place (win probability under
  52% on the raw numbers) or that took enough doubts to fall all the way
  through. On the logged games so far, NO PLAY as a whole hit 58.8% (n=34) --
  identical whether a game got there by earning it outright or by being
  knocked down -- which is itself evidence the *reason* a game lands there
  says less than the raw win probability does. Revisit this band once each
  tier has the ~50 games the track record page says it needs to mean anything;
  n=34 is not that.

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

# LEAN is landing-only: nothing is ever assessed as LEAN directly from win
# probability (see band_for) -- a game only arrives here by earning LOW or
# better and then losing exactly one step to a downgrade. That keeps the
# meaning fixed: LEAN always means "a real read, but with one doubt attached,"
# never "a slightly-below-coin-flip number that got rounded up."
BANDS = ("NO PLAY", "LEAN", "LOW", "MEDIUM", "HIGH")

# --- how much of the trust budget the trend signals may claim ----------------
#
# Head-to-head and recent form are real information and weak information. They
# are small samples of games played by different pitchers, different rotations
# and sometimes different rosters. Together they may take at most half of
# whatever trust is not being left with the market, and each only reaches its
# share with a full sample behind it. The matchup model always keeps the other
# half -- that invariant is what the two numbers below must always add up to.
#
# Recent form gets the larger share of the two. Both are weak, but head-to-head
# is the weaker: on the games logged so far its own estimate of the total misses
# by 6.4 on average against recent form's 5.0. So the split is uneven rather
# than the extra weight coming out of the matchup model, which is the most
# accurate of the three (4.6) and the one signal that knows who is pitching.
H2H_SHARE = 0.20
FORM_SHARE = 0.30

# WNBA's second trend slot. Head-to-head does not vote there (see H2H_SPORTS
# below), which leaves 0.20 of the 0.50 trend ceiling unclaimed in that sport --
# exactly the room this signal fills, so the matchup model keeps at least half
# in both sports on the same schedule.
#
# UNVALIDATED, unlike the other three shares. Those numbers came from mean
# error on logged games; this one is a placeholder because there is no logged
# history with this signal in it yet. Revisit it -- the ramp, the share, and
# the conversion in ou_signal() below -- once enough WNBA games have been
# logged with an over/under record entered to backtest it the way FORM_SHARE
# was backtested against H2H_SHARE.
OU_SHARE = 0.20

# Games needed before a trend signal is at full strength. Head-to-head counts
# for more in basketball, where the same rosters meet again in the same season;
# in baseball tonight's starters were mostly not involved last time. The
# over/under record accumulates over a whole season, so it clears a given game
# count faster than head-to-head ever does -- but each of those games is
# against a different opponent under different conditions, diluted the way a
# single-season batting average is diluted next to a matchup stat. 12 is a
# guess at "enough games that a lopsided record probably isn't just four early
# blowouts," not a fitted number.
H2H_FULL_GAMES = {"MLB": 8.0, "WNBA": 4.0}
FORM_FULL_GAMES = {"MLB": 10.0, "WNBA": 8.0}
OU_FULL_GAMES = {"WNBA": 12.0}

# Sports where head-to-head votes at all. WNBA teams meet one to three times a
# season, so "head to head" there is not a sample -- it is a single lopsided game
# wearing a trend's clothes. Across the logged WNBA games its reads ran from 5.5
# to 27 points off one to three meetings, which ramping alone did not discount
# nearly enough. So basketball drops the signal outright rather than trusting an
# ever-smaller ramp to contain it: it never enters the signal list, cannot vote,
# cannot corroborate, and the matchup model keeps the share it would have taken.
H2H_SPORTS = frozenset({"MLB"})

# Sports where a team's record against the total votes. MLB starting pitchers
# change the number too much game to game for a season-long team record to mean
# much; WNBA rotations are steadier, so the record says more about the team.
OU_SPORTS = frozenset({"WNBA"})

# A record this lopsided is more likely a typo -- wins and losses swapped, or a
# stray digit -- than a real edge the market has missed all season. Clamped the
# same width both ways: used to flag an extreme raw record, and to keep a small
# sample from swinging the implied value to an unstable extreme.
OU_PCT_CLAMP = (0.15, 0.85)

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


def _team_ou_pct(record: dict[str, Any] | None) -> tuple[float | None, float]:
    """A team's own over rate and game count from a wins/losses record.

    Both fields have to be explicitly present. Defaulting a missing one to
    zero -- "wins: 20" with no losses key read as 20-0 -- is exactly how a
    blank ERA got read as 0.00 and produced this model's largest false-
    confidence bet: a half-filled field silently becoming an extreme, and
    therefore very convincing-looking, number.
    """
    r = record or {}
    wins, losses = r.get("wins"), r.get("losses")
    if wins in (None, "") or losses in (None, ""):
        return None, 0.0
    wins, losses = float(wins), float(losses)
    games = wins + losses
    if games <= 0:
        return None, 0.0
    return wins / games, games


def ou_signal(sport: str, game: dict[str, Any], projection: Projection,
              line: float) -> tuple[float | None, float]:
    """The value implied by both teams' record against the total, and its games.

    Each team's own over rate is a probability, not a points total, so it
    cannot be averaged into a value the way two recent-form totals can. It is
    converted into one instead by reusing the exact machinery ``market_mean``
    itself is built from: solve for the mean at which this game's own
    distribution would produce that probability of going over. That keeps the
    conversion dimensionally honest -- a given percentage swings the value more
    in a high-variance MLB game than a tight WNBA one -- without inventing a
    flat points-per-percent constant this project has no basis for.

    The two teams' rates are averaged before the inversion, the same way two
    recent-form totals are averaged: the neutral read on a game between them.
    ``games`` is the SMALLER of the two team counts, not the larger, so a
    thin record on one side still limits how much the pair can vote --
    the general rule in this model that a weak leg limits the whole signal.
    """
    if sport not in OU_SPORTS:
        return None, 0.0
    record = game.get("over_under_record") or {}
    away_pct, away_games = _team_ou_pct(record.get("away"))
    home_pct, home_games = _team_ou_pct(record.get("home"))
    if away_pct is None or home_pct is None:
        return None, 0.0
    lo, hi = OU_PCT_CLAMP
    combined = min(hi, max(lo, (away_pct + home_pct) / 2.0))
    value = market_implied_total(projection, line, combined)
    return value, min(away_games, home_games)


def build_signals(sport: str, game: dict[str, Any], market_mean: float,
                  model_total: float, trust: float,
                  ou: tuple[float | None, float] = (None, 0.0)) -> list[Signal]:
    """The matchup model plus whichever trend signals apply to this sport.

    Head-to-head is absent entirely in sports outside ``H2H_SPORTS``, and the
    over/under record is absent outside ``OU_SPORTS``, rather than either being
    present at zero weight: a signal that cannot move the projection should not
    be on the page claiming to be one of the votes.
    """
    include_h2h = sport in H2H_SPORTS
    h2h = (game.get("h2h") or {}) if include_h2h else {}
    form = game.get("form") or {}
    ou_value, ou_games = ou

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

    signals = [Signal("Matchup model", model_total, games=1.0)]
    h2h_signal = Signal("Head to head", h2h_value, games=h2h_games) if include_h2h else None
    if h2h_signal is not None:
        signals.append(h2h_signal)
    form_signal = Signal("Recent form", form_value, games=form_games)
    signals.append(form_signal)
    ou_signal_obj = Signal("O/U record", ou_value, games=ou_games) if sport in OU_SPORTS else None
    if ou_signal_obj is not None:
        signals.append(ou_signal_obj)

    h2h_w = (trust * H2H_SHARE * _ramp(h2h_games, H2H_FULL_GAMES[sport])
             if h2h_signal is not None and h2h_signal.present else 0.0)
    form_w = (trust * FORM_SHARE * _ramp(form_games, FORM_FULL_GAMES[sport])
              if form_signal.present else 0.0)
    ou_w = (trust * OU_SHARE * _ramp(ou_games, OU_FULL_GAMES.get(sport, 1.0))
            if ou_signal_obj is not None and ou_signal_obj.present else 0.0)
    if h2h_signal is not None:
        h2h_signal.weight = h2h_w
    form_signal.weight = form_w
    if ou_signal_obj is not None:
        ou_signal_obj.weight = ou_w
    signals[0].weight = trust - h2h_w - form_w - ou_w

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
            # No "only N innings" flag past this. There used to be one below 40,
            # calibrated for a season-long sample. Removed by request to run
            # this field as a last-5-starts window instead -- a real value
            # there is always going to be under 40 by design, so the flag would
            # fire on every single game and say nothing. The blank/zero check
            # above still stands: an ERA with genuinely no innings behind it at
            # all is a different, worse problem than a real short window, and
            # is exactly what turned a 0.00 ERA into this model's largest
            # false-confidence bet before that check existed.

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
    checks = [("form", "away_avg_total", "away recent-form average"),
              ("form", "home_avg_total", "home recent-form average")]
    # Only range-check head-to-head where head-to-head votes. Flagging a number
    # that cannot reach the projection would cost a confidence band over a field
    # the model has already decided to ignore.
    if sport in H2H_SPORTS:
        checks.insert(0, ("h2h", "avg_total", "head-to-head average total"))
    for block, key, label in checks:
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

    # A record this lopsided is more likely wins and losses swapped than a real
    # season-long market miss.
    if sport in OU_SPORTS:
        record = game.get("over_under_record") or {}
        ou_lo, ou_hi = OU_PCT_CLAMP
        for side in ("away", "home"):
            t = game.get(side) or {}
            name = t.get("name") or side
            pct, games = _team_ou_pct(record.get(side))
            if pct is not None and games >= 8 and not ou_lo <= pct <= ou_hi:
                w = record.get(side, {}).get("wins")
                l = record.get(side, {}).get("losses")
                flags.append(
                    f"the {name} over/under record ({w:g}-{l:g}) reads {100 * pct:.0f}% "
                    "over, unusually lopsided for a season — check that entry"
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

    ou = ou_signal(sport, game, projection, line)
    signals = build_signals(sport, game, market_mean, model_total, trust, ou)
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
    # Named dynamically rather than a fixed phrase, because which trends even
    # apply differs by sport (WNBA has no head-to-head; only WNBA has an
    # over/under record).
    if not any(s.present and s.weight > 0 for s in signals[1:]):
        trend_names = " or ".join(s.name.lower() for s in signals[1:])
        downgrades.append(f"no {trend_names} to corroborate it")
        notes.append(
            "Only the matchup model voted. Filling in a trend would confirm the read "
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
