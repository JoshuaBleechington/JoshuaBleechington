"""A point-spread verdict for WNBA games: which side covers, and how sure.

This exists because the totals side of the WNBA model kept getting outvoted by
its own trend signals. Across the logged games the WNBA totals record ran hot
and cold in a way the MLB record did not, and the worst misses shared a shape:
the matchup model read the game about right and a recent-form scoring trend
dragged the projection to the wrong side of the number. A 163.5 that finished
136 was the last straw -- the model's own read leaned under and lost the vote.

The margin is the part of the projection that was never the problem. The same
four team inputs already produce separate away and home scores, home court is
already applied to the margin only, and the empirical margin spread
(``wnba.MARGIN_SD``) has been sitting in the code since the start, used for
nothing but the overtime estimate. So this module asks the model the question
it is better built to answer: not "how many points tonight" but "who wins, and
by how much".

Everything structural is inherited from ``confidence`` rather than reinvented:
the same band ladder with the same thresholds, the same landing-only LEAN, the
same trust budget where the matchup model keeps at least half, the same
confidence-only-goes-down rule, the same "both fields or neither" reading of a
wins/losses record. What changes is the quantity being argued about.

One thing gets SIMPLER in margin space. A totals line is a median on a
right-skewed distribution, so it has to be inverted into a mean before the
signals can vote against it. A margin distribution is symmetric, so the spread
already IS the mean: a home line of -6.5 says the market expects the home team
to win by 6.5, full stop. ``market_margin = -spread`` and no bisection.

Sign conventions, fixed once here and used everywhere:

* ``spread`` is the HOME team's line as the book prints it: -6.5 means the
  home side is favoured by 6.5, +4.5 means the home side is a 4.5 underdog.
* Margins are home minus away. Positive means the home team wins.
* A signal's lean is its margin estimate minus the market's; positive leans
  HOME, negative leans AWAY.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import wnba
from .confidence import (
    DEFAULT_TRUST,
    FIELD_RANGES,
    FORM_FULL_GAMES,
    FORM_SHARE,
    OU_PCT_CLAMP,
    _fmt,
    _ramp,
    _sentence_case,
    _step_down,
    _team_ou_pct,
    band_for,
)
from .core import Projection
from .distributions import normal_cdf

__all__ = ["decide_spread", "SpreadVerdict", "SpreadSignal"]

# The against-the-spread record's share of the trust budget. It fills the same
# slot the over/under record filled on the totals side -- the 0.20 that
# head-to-head leaves unclaimed in a sport where it never votes -- so the
# matchup model keeps at least half of the trust on the same schedule as
# everywhere else in this project.
#
# UNVALIDATED, same as OU_SHARE was: there is no logged spread history yet to
# backtest it against. Revisit the share, the ramp, and the conversion in
# ats_signal() once enough WNBA spread games are in the log.
ATS_SHARE = 0.20
ATS_FULL_GAMES = 12.0

# Same clamp, same reasoning as the totals record: a season-long record more
# lopsided than this is more likely wins and losses swapped than a market that
# has really been wrong about one team 85% of the time.
ATS_PCT_CLAMP = OU_PCT_CLAMP

# A model margin this far from the spread is a symptom, not an edge -- the
# margin-space version of confidence.IMPLAUSIBLE_GAP. The scale is smaller
# than the 12-point totals threshold because margins are smaller numbers:
# with team inputs inside their physical ranges, even an extreme mismatch of
# net ratings only moves the model a handful of points off the market, so a
# nine-point disagreement almost certainly traces to a bad entry (a pace or a
# rating on the wrong scale) rather than to insight. First guess, like the
# totals value was; revisit with data.
MARGIN_IMPLAUSIBLE = 9.0

# How far a signal must lean, in points of margin, before it counts as
# disagreeing with the verdict rather than merely being quiet. Same value as
# the WNBA totals dissent threshold -- the margin SD (11.0) and the total SD
# (11.5) are close enough that a 2.5-point lean means about the same thing in
# either space.
MARGIN_DISSENT = 2.5

# What a spread and a recent-form margin can physically be. The widest WNBA
# closing spreads on record sit under 20 points, and no team averages a
# 40-point margin over any stretch; outside these is a typo.
SPREAD_RANGE = (-35.0, 35.0)
FORM_MARGIN_RANGE = (-40.0, 40.0)


def inv_norm(p: float) -> float:
    """The z at which the standard normal CDF equals ``p``.

    Bisection against normal_cdf rather than a rational approximation: it is
    the same solve-by-bisection style ``market_implied_total`` uses, it is
    exact to the tolerance of the CDF itself, and this module only calls it
    once per verdict.
    """
    lo, hi = -8.0, 8.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if normal_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


@dataclass
class SpreadSignal:
    """One opinion about the final margin, home minus away, in points."""

    name: str
    value: float | None          # its own estimate of the margin
    games: float                 # how many games of evidence behind it
    weight: float = 0.0          # share of the final projection it earns
    lean: float = 0.0            # value - market margin; positive leans HOME

    @property
    def present(self) -> bool:
        return self.value is not None and self.games > 0

    def side(self) -> str | None:
        if not self.present or self.lean == 0:
            return None
        return "HOME" if self.lean > 0 else "AWAY"


@dataclass
class SpreadVerdict:
    sport: str
    matchup: str
    spread: float                # the home line as posted, e.g. -6.5
    market_margin: float         # what that line says the margin is: -spread
    model_margin: float          # the matchup model's own margin
    projected_margin: float      # after the signals vote
    away_score: float
    home_score: float
    side: str                    # "HOME" or "AWAY"
    win_pct: float               # probability the picked side covers
    band: str
    signals: list[SpreadSignal]
    downgrades: list[str] = field(default_factory=list)
    downgrade_notes: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    notes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sport": self.sport,
            "bet_type": "spread",
            "matchup": self.matchup,
            "spread": self.spread,
            "market_margin": round(self.market_margin, 2),
            "model_margin": round(self.model_margin, 2),
            "projected_margin": round(self.projected_margin, 2),
            "away_score": round(self.away_score, 2),
            "home_score": round(self.home_score, 2),
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


def ats_signal(game: dict[str, Any], market_margin: float,
               margin_sd: float) -> tuple[float | None, float]:
    """The margin implied by both teams' record against the spread.

    A cover rate is a probability, not a points value, so -- exactly like the
    over/under record on the totals side -- it has to be converted before it
    can vote. The conversion inverts the same distribution the verdict is
    scored on: if the pair of records says the home side covers p of the time,
    the margin at which a normal(margin_sd) would produce that is
    ``market_margin + z(p) * margin_sd``.

    The two records point in opposite directions by construction. The home
    team covering ITS games says the market underrates it; the away team
    FAILING its games says the market overrates it -- both of those lean home
    tonight. So the combined home-cover tendency is the average of the home
    team's cover rate and the complement of the away team's.

    ``games`` is the smaller of the two team counts: a thin record on one side
    limits how much the pair can vote, the general rule in this model that a
    weak leg limits the whole signal.
    """
    record = game.get("ats_record") or {}
    away_pct, away_games = _team_ou_pct(record.get("away"))
    home_pct, home_games = _team_ou_pct(record.get("home"))
    if away_pct is None or home_pct is None:
        return None, 0.0
    lo, hi = ATS_PCT_CLAMP
    combined = min(hi, max(lo, (home_pct + (1.0 - away_pct)) / 2.0))
    return market_margin + inv_norm(combined) * margin_sd, min(away_games, home_games)


def build_signals(game: dict[str, Any], market_margin: float,
                  model_margin: float, trust: float, hca: float,
                  ats: tuple[float | None, float]) -> list[SpreadSignal]:
    """The matchup model's margin plus the two margin trends.

    Recent form here is each team's average MARGIN over its last N games, not
    its average total. A team's overall average margin is close to venue-
    neutral (roughly half those games were at home), so the neutral estimate
    for tonight is the difference of the two -- and then home court has to be
    added back on, because tonight is not neutral. Skipping that would make
    the form signal lean away by a fixed 2.5 points on every game, a
    systematic dissent against the model and the market both.

    Head-to-head stays out for the same reason it is out of the WNBA totals
    verdict: one to three meetings is a single lopsided game wearing a trend's
    clothes, and a margin from a single game is even noisier than a total.
    """
    form = game.get("form") or {}
    ats_value, ats_games = ats

    form_games = float(form.get("games", 0) or 0)
    away_form = form.get("away_avg_margin")
    home_form = form.get("home_avg_margin")
    have_form = (form_games > 0 and away_form not in (None, "")
                 and home_form not in (None, ""))
    form_value = (float(home_form) - float(away_form) + hca) if have_form else None

    signals = [
        SpreadSignal("Matchup model", model_margin, games=1.0),
        SpreadSignal("Recent form", form_value, games=form_games),
        SpreadSignal("ATS record", ats_value, games=ats_games),
    ]
    form_signal, ats_obj = signals[1], signals[2]

    form_w = (trust * FORM_SHARE * _ramp(form_games, FORM_FULL_GAMES["WNBA"])
              if form_signal.present else 0.0)
    ats_w = (trust * ATS_SHARE * _ramp(ats_games, ATS_FULL_GAMES)
             if ats_obj.present else 0.0)
    form_signal.weight = form_w
    ats_obj.weight = ats_w
    signals[0].weight = trust - form_w - ats_w

    for s in signals:
        if s.present:
            s.lean = s.value - market_margin
    return signals


def quality_flags(game: dict[str, Any], model_margin: float,
                  market_margin: float) -> list[str]:
    """Reasons to trust this particular game's inputs less than usual."""
    flags: list[str] = []

    if abs(model_margin - market_margin) > MARGIN_IMPLAUSIBLE:
        flags.append(
            f"the model's margin is {abs(model_margin - market_margin):.1f} points "
            "from the spread, which is usually a bad input rather than an edge"
        )

    for side in ("away", "home"):
        t = game.get(side) or {}
        name = t.get("name") or side
        for key, (lo, hi, label) in FIELD_RANGES["WNBA"].items():
            v = t.get(key)
            if v in (None, ""):
                flags.append(f"{name} {label} is blank")
                continue
            v = float(v)
            if v <= 0:
                flags.append(f"{name} {label} is blank")
            elif not lo <= v <= hi:
                flags.append(
                    f"{name} {label} is {_fmt(v)}, outside the possible range "
                    f"{_fmt(lo)}–{_fmt(hi)} — check that entry"
                )

    lo, hi = FORM_MARGIN_RANGE
    form = game.get("form") or {}
    for key, label in (("away_avg_margin", "away recent-form margin"),
                       ("home_avg_margin", "home recent-form margin")):
        v = form.get(key)
        if v in (None, ""):
            continue
        v = float(v)
        if not lo <= v <= hi:
            flags.append(
                f"the {label} is {_fmt(v)}, outside the possible range "
                f"{_fmt(lo)}–{_fmt(hi)} — check that entry"
            )

    record = game.get("ats_record") or {}
    ats_lo, ats_hi = ATS_PCT_CLAMP
    for side in ("away", "home"):
        t = game.get(side) or {}
        name = t.get("name") or side
        pct, games = _team_ou_pct(record.get(side))
        if pct is not None and games >= 8 and not ats_lo <= pct <= ats_hi:
            w = record.get(side, {}).get("wins")
            l = record.get(side, {}).get("losses")
            flags.append(
                f"the {name} against-the-spread record ({w:g}-{l:g}) reads "
                f"{100 * pct:.0f}% covers, unusually lopsided for a season — "
                "check that entry"
            )
    return flags


def _margin_probs(projected_margin: float, market_margin: float,
                  margin_sd: float) -> tuple[float, float, float]:
    """P(home covers), P(away covers), P(push), continuity-corrected.

    Final margins are integers, so a whole-number spread can push and gets the
    same half-point correction the totals side uses.
    """
    is_whole = abs(market_margin - round(market_margin)) < 1e-9
    if is_whole:
        p_push = (normal_cdf(market_margin + 0.5, projected_margin, margin_sd)
                  - normal_cdf(market_margin - 0.5, projected_margin, margin_sd))
        p_away = normal_cdf(market_margin - 0.5, projected_margin, margin_sd)
        return 1.0 - p_away - p_push, p_away, p_push
    p_away = normal_cdf(market_margin, projected_margin, margin_sd)
    return 1.0 - p_away, p_away, 0.0


def decide_spread(projection: Projection, game: dict[str, Any]) -> SpreadVerdict:
    """Blend the margin signals against the spread and grade the belief."""
    spread = float(game["spread"])
    trust = float(game.get("trust", DEFAULT_TRUST))
    trust = max(0.0, min(1.0, trust))
    hca = float(game.get("home_court_points", wnba.HOME_COURT_POINTS))
    margin_sd = float(game.get("margin_sd", wnba.MARGIN_SD))

    # The spread already is the market's margin, sign flipped: home -6.5 means
    # the market expects home minus away to land on +6.5. No inversion needed
    # -- a margin distribution is symmetric, so its median is its mean.
    market_margin = -spread
    model_margin = projection.margin

    ats = ats_signal(game, market_margin, margin_sd)
    signals = build_signals(game, market_margin, model_margin, trust, hca, ats)
    projected = market_margin + sum(s.weight * s.lean for s in signals if s.present)

    p_home, p_away, p_push = _margin_probs(projected, market_margin, margin_sd)
    decided = 1.0 - p_push
    p_home_decided = p_home / decided if decided > 0 else p_home
    side = "HOME" if p_home_decided >= 0.5 else "AWAY"
    win_pct = p_home_decided if side == "HOME" else 1.0 - p_home_decided

    band = band_for(win_pct)
    downgrades: list[str] = []
    notes: list[str] = []

    for s in signals:
        if not s.present or s.weight <= 0:
            continue
        if s.side() and s.side() != side and abs(s.lean) >= MARGIN_DISSENT:
            downgrades.append(f"{s.name.lower()} points the other way ({s.side().lower()})")
            notes.append(
                f"It reads {s.value:+.1f}, a gap of {abs(s.lean):.1f} points the other "
                f"way. The projection is an average of signals that disagree, which is "
                f"a weaker thing than three that line up."
            )

    flags = quality_flags(game, model_margin, market_margin)
    if flags:
        downgrades.append("the inputs behind it are thin")
        notes.append(_sentence_case("; ".join(flags)) + ".")

    if not any(s.present and s.weight > 0 for s in signals[1:]):
        trend_names = " or ".join(s.name.lower() for s in signals[1:])
        downgrades.append(f"no {trend_names} to corroborate it")
        notes.append(
            "Only the matchup model voted. Filling in a trend would confirm the read "
            "or catch a bad input, and could put the band back up."
        )

    band = _step_down(band, len(downgrades))

    return SpreadVerdict(
        sport="WNBA",
        matchup=f"{projection.away} @ {projection.home}",
        spread=spread,
        market_margin=market_margin,
        model_margin=model_margin,
        projected_margin=projected,
        away_score=projection.away_score,
        home_score=projection.home_score,
        side=side,
        win_pct=win_pct,
        band=band,
        signals=signals,
        downgrades=downgrades,
        downgrade_notes=notes,
        flags=flags,
        notes=dict(projection.notes, p_push=round(p_push, 4), trust=trust,
                   margin_sd=margin_sd),
    )
