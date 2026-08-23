"""The game-day model: decide whether to bet, not what the score will be.

What every previous version of this project got wrong
-----------------------------------------------------
The totals verdict projected a score from season statistics and bet the gap
against the posted line. Measured over 116 logged games it had a mean absolute
error of 3.61 runs where simply using the line had 3.58, and a ridge fit on all
fourteen of its inputs, leave-one-out cross-validated, produced a *negative*
out-of-sample R-squared at every regularisation strength. Every input it used
was published and already inside the number before it was posted.

The late-factor model that replaced it fixed the premise -- anchor on the line,
adjust only for what breaks late -- but kept two habits worth dropping:

1. It summed unvalidated coefficients into a precise-looking probability.
   "57.3%" from numbers nobody has ever backtested is a false precision, and
   false precision is exactly how this project talked itself into bad bets four
   separate times.
2. It treated a known late factor as automatically an edge. It is not. When
   Caitlin Clark was ruled out the Fever line went from -11 to -6 on the
   announcement. Reading that news afterwards and betting it is not an edge; it
   is arriving after the market. **The edge is the gap between what a factor is
   worth and what the line has already moved**, and a model that does not ask
   that question is just a slower version of the wire.

So this module decides. It takes evidence gathered on the day, asks whether it
clears a set of gates, and answers BET, LEAN or PASS. PASS is the expected
answer and is not a failure of the model.

The gates
---------
A recommendation has to survive all four:

* **Fresh.** Evidence has to be from game day. Yesterday's bullpen note is
  tonight's stale guess.
* **Grounded.** At least one item has to be ``documented`` -- an effect size
  from published research or public data, not a placeholder.
* **Unpriced.** The net magnitude is what is left after subtracting the line
  movement the market has already made for the same news.
* **Uncontradicted.** No documented item may point against the net direction.
  With no validated weights there is no honest way to net two real signals that
  disagree, so the honest answer is to stand down.

Magnitudes are signed in the sport's own unit -- runs for a total, points of
margin for a spread -- and positive always means "toward the side named".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

# How big the residual, unpriced edge has to be before it is worth acting on.
# Sized off the observed spread of outcomes: MLB totals scatter with a standard
# deviation of 4.39 runs around the line, WNBA margins about 11 points, so
# these are each roughly a tenth of a standard deviation. Below that the edge
# is smaller than the vig and the honest answer is no.
MIN_EDGE = {"MLB": 0.45, "WNBA": 1.20}
STRONG_EDGE = {"MLB": 0.90, "WNBA": 2.60}

# Converting a magnitude into a win probability needs a dispersion. These are
# measured, not chosen: 4.39 from the 116 settled MLB games in the track record,
# 11.0 for WNBA margins from the spread model.
DISPERSION = {"MLB": 4.39, "WNBA": 11.0}

BASES = ("documented", "provisional")
VERDICTS = ("PASS", "LEAN", "BET")


@dataclass
class Evidence:
    """One thing found on game day that the posted number may not know.

    ``worth`` is what the factor is worth in the sport's unit, signed toward
    the side it favours. ``already_moved`` is how far the line has already
    travelled on this same news -- the part of ``worth`` that is spent. What
    survives is ``unpriced``.
    """

    name: str
    worth: float
    basis: str
    source: str
    as_of: date | None = None
    already_moved: float = 0.0

    def __post_init__(self) -> None:
        if self.basis not in BASES:
            raise ValueError(f"basis must be one of {BASES}, got {self.basis!r}")

    @property
    def unpriced(self) -> float:
        """What is left after the market has moved on the same information.

        Clamped at zero rather than allowed to flip sign: a line that moved
        *further* than the factor is worth is the market disagreeing with this
        estimate, not a signal to bet the other way. Fading a move on the
        strength of an unvalidated coefficient is exactly the overconfidence
        this module exists to refuse.
        """
        if self.worth >= 0:
            return max(0.0, self.worth - max(0.0, self.already_moved))
        return min(0.0, self.worth - min(0.0, self.already_moved))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "worth": round(self.worth, 2),
            "already_moved": round(self.already_moved, 2),
            "unpriced": round(self.unpriced, 2),
            "basis": self.basis,
            "source": self.source,
            "as_of": self.as_of.isoformat() if self.as_of else None,
        }


@dataclass
class Call:
    sport: str
    matchup: str
    market: str                  # what is posted: "total 8.5", "home -6.5"
    side: str
    verdict: str
    net: float
    win_pct: float
    evidence: list[Evidence]
    gates: dict[str, bool]
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sport": self.sport,
            "matchup": self.matchup,
            "market": self.market,
            "side": self.side,
            "verdict": self.verdict,
            "net": round(self.net, 2),
            "win_pct": round(self.win_pct, 4),
            "gates": self.gates,
            "evidence": [e.to_dict() for e in self.evidence],
            "reasons": self.reasons,
        }

    def brief(self) -> str:
        """One screen, for reading a slate."""
        lines = [f"{self.matchup}  ({self.market})",
                 f"  {self.verdict}"
                 + (f"  {self.side}  net {self.net:+.2f}  {self.win_pct * 100:.1f}%"
                    if self.verdict != "PASS" else "")]
        for e in self.evidence:
            lines.append(f"    {e.unpriced:+.2f}  {e.name}  [{e.basis}]"
                         + (f"  (worth {e.worth:+.2f}, line already moved {e.already_moved:+.2f})"
                            if e.already_moved else ""))
            lines.append(f"           {e.source}")
        for r in self.reasons:
            lines.append(f"    - {r}")
        return "\n".join(lines)


def _win_pct(net: float, sport: str) -> float:
    """Magnitude to probability, through the sport's observed dispersion.

    Deliberately the only place a probability is produced, and deliberately
    unflattering: a full run of unpriced MLB edge is a quarter of a standard
    deviation and comes out near 59%, and the realistic edges this model finds
    are a third of that.
    """
    from .distributions import normal_cdf
    sd = DISPERSION[sport]
    return normal_cdf(abs(net) / sd, 0.0, 1.0)


def decide(sport: str, matchup: str, market: str, positive_side: str,
           negative_side: str, evidence: Iterable[Evidence],
           game_day: date | None = None) -> Call:
    """Run the gates over one game's evidence.

    ``positive_side`` is the side a positive magnitude favours -- OVER for a
    total, the home team for a spread -- and ``negative_side`` its opposite.
    """
    sport = sport.upper()
    if sport not in MIN_EDGE:
        raise ValueError(f"sport must be one of {sorted(MIN_EDGE)}, got {sport!r}")
    items = list(evidence)

    fresh = [e for e in items if game_day is None or e.as_of == game_day]
    stale = [e for e in items if e not in fresh]

    net = sum(e.unpriced for e in fresh)
    side = positive_side if net >= 0 else negative_side

    documented = [e for e in fresh if e.basis == "documented"]
    # A documented item counts as contradicting only if it is itself still
    # unpriced and points the other way. An item the market has fully absorbed
    # is not an argument about tonight; it is history.
    contradicting = [e for e in documented
                     if e.unpriced != 0 and (e.unpriced > 0) != (net > 0)]

    gates = {
        "fresh": bool(fresh),
        "grounded": bool(documented),
        "unpriced": abs(net) >= MIN_EDGE[sport],
        "uncontradicted": not contradicting,
    }

    reasons: list[str] = []
    if stale:
        reasons.append(
            f"{len(stale)} item(s) dropped as not game-day: "
            + ", ".join(e.name for e in stale)
        )
    if not fresh:
        reasons.append("Nothing found today. The posted number is the best estimate here.")
    elif not documented:
        reasons.append(
            "Everything found rests on provisional coefficients. Logged as a "
            "hypothesis, not backed."
        )
    if fresh and not gates["unpriced"]:
        spent = sum(abs(e.already_moved) for e in fresh)
        reasons.append(
            f"Net unpriced edge is {abs(net):.2f}, under the {MIN_EDGE[sport]:.2f} "
            f"{'runs' if sport == 'MLB' else 'points'} this model needs"
            + (f" — the line has already moved {spent:.2f} on this news." if spent
               else ".")
        )
    for e in contradicting:
        reasons.append(
            f"{e.name} points the other way and is documented, so there is no "
            "honest way to net it out. Standing down."
        )

    if all(gates.values()):
        verdict = "BET" if abs(net) >= STRONG_EDGE[sport] else "LEAN"
    else:
        verdict = "PASS"

    return Call(
        sport=sport,
        matchup=matchup,
        market=market,
        side=side if verdict != "PASS" else "—",
        verdict=verdict,
        net=net,
        win_pct=_win_pct(net, sport) if verdict != "PASS" else 0.5,
        evidence=fresh,
        gates=gates,
        reasons=reasons,
    )


def slate(calls: Iterable[Call]) -> str:
    """A whole board, strongest first, with the passes counted not listed.

    Listing twelve PASSes is how a card of nothing starts looking like a card.
    """
    ordered = sorted(calls, key=lambda c: (VERDICTS.index(c.verdict), abs(c.net)),
                     reverse=True)
    acted = [c for c in ordered if c.verdict != "PASS"]
    passed = [c for c in ordered if c.verdict == "PASS"]
    out = []
    for c in acted:
        out.append(c.brief())
        out.append("")
    if passed:
        out.append(f"PASS ({len(passed)}): " + "; ".join(c.matchup for c in passed))
    if not acted:
        out.append("Nothing on this board clears the gates. That is the read, "
                   "not a missing one.")
    return "\n".join(out)
