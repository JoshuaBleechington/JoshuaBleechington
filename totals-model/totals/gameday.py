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

Magnitudes are in runs (MLB) or points (WNBA), and positive always means
toward the OVER.

Scope
-----
Totals, both sports. The WNBA *spread* model went 4-5 and is retired -- what is
here is the over/under, which is what the WNBA side of this project was before
the spread pivot. Nothing here prices a side or a spread in either sport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

# Totals only, both sports. The WNBA *spread* model went 4-5 and is retired;
# what came back is the over/under, which is what the WNBA half of this project
# was before the spread pivot.
#
# Measured, not chosen: the observed standard deviation of (final total minus
# posted line). MLB is 4.39 over 116 settled games. WNBA is 11.51 over 13, which
# is far too few to trust as a point estimate -- it is used because it is the
# only measurement available and because it agrees with the 11.0 the spread
# model used for margins, not because 13 games settle anything.
DISPERSION = {"MLB": 4.39, "WNBA": 11.51}

# How big the residual, unpriced edge has to be before it is worth acting on.
# Both are the same fractions of their own dispersion -- about a tenth for a
# LEAN and a fifth for a BET -- so the two sports demand the same evidence in
# the units each is actually measured in. Below that the edge is smaller than
# the vig and the honest answer is no.
MIN_EDGE = {"MLB": 0.45, "WNBA": 1.20}
STRONG_EDGE = {"MLB": 0.90, "WNBA": 2.40}

# A dissenting item only vetoes the bet if it is itself worth something. Half
# the lean bar is the line. Without this, a 0.15-run temperature term stands
# down a game carried by a half-run umpire -- which is precisely the fault that
# killed the old confidence model: a head-to-head signal holding 1.25% of the
# weight could still cost a full band, and four picks were downgraded that way.
# Rediscovered here by watching a warm night in Anaheim veto a real read.
CONTRADICTION_FLOOR = {k: v / 2.0 for k, v in MIN_EDGE.items()}

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
    opened: float | None = None      # the line when it was first posted
    posted: float | None = None      # the line now
    missing: list[str] = field(default_factory=list)
    capped_at_lean: bool = False     # trial mode: provisional cannot reach BET

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
        """Everything needed to make the call, including what would change it.

        A verdict on its own is not a decision aid -- "PASS" tells you nothing
        about whether the game was close or dead, and the difference matters
        when a missing input is still to come. So this prints the arithmetic,
        which gate failed, and exactly how much more evidence would flip it.
        """
        unit = "runs" if self.sport == "MLB" else "pts"
        bar, strong = MIN_EDGE[self.sport], STRONG_EDGE[self.sport]
        L = []

        head = f"{self.matchup}   {self.market}"
        if self.opened is not None:
            mv = self.posted - self.opened if self.posted is not None else None
            if mv:
                who = "under money" if mv < 0 else "over money"
                head += f"   (opened {self.opened:g}, moved {mv:+g} — {who} already in)"
            else:
                head += f"   (opened {self.opened:g}, unmoved)"
        L.append(head)
        L.append(f"  {self.verdict}" + (f"   {self.side}   {self.win_pct * 100:.1f}%"
                                        if self.verdict != "PASS" else ""))
        L.append("")

        if self.evidence:
            L.append("  what I found")
            for e in self.evidence:
                tag = "" if e.basis == "documented" else "  [PROVISIONAL]"
                line = f"    {e.unpriced:+6.2f}  {e.name}{tag}"
                if e.already_moved:
                    line += (f"   (worth {e.worth:+.2f}, line already took "
                             f"{e.already_moved:+.2f})")
                L.append(line)
                L.append(f"            {e.source}")
            L.append(f"    {'-' * 6}")
            L.append(f"    {self.net:+6.2f}  net unpriced {unit}"
                     f"      bar {bar:g} to lean, {strong:g} to bet")
        else:
            L.append("  what I found")
            L.append("    nothing. No late factor was supplied or found.")
        L.append("")

        L.append("  gates")
        for k in ("fresh", "grounded", "unpriced", "uncontradicted"):
            mark = "pass" if self.gates[k] else "FAIL"
            extra = ""
            if k == "unpriced" and not self.gates[k]:
                extra = f"   short by {bar - abs(self.net):.2f} {unit}"
            L.append(f"    {k:<15s} {mark}{extra}")
        L.append("")

        L.append("  what would change it")
        gap_lean = bar - abs(self.net)
        gap_bet = strong - abs(self.net)
        if self.verdict == "PASS" and self.gates["grounded"] and self.gates["uncontradicted"]:
            side = self.side if self.side != "—" else ("OVER" if self.net >= 0 else "UNDER")
            L.append(f"    {gap_lean:+.2f} {unit} more -> LEAN {side}")
            L.append(f"    {gap_bet:+.2f} {unit} more -> BET {side}")
        elif not self.gates["grounded"]:
            L.append("    one documented item. Provisional coefficients cannot carry a bet")
            L.append("    on their own, however large they look.")
        elif not self.gates["uncontradicted"]:
            L.append("    nothing. Two documented items disagree and there is no validated")
            L.append("    way to net them, so this stays a stand-down whatever else turns up.")
        elif self.verdict == "LEAN" and self.capped_at_lean:
            L.append("    nothing — trial mode tops out at LEAN. Provisional")
            L.append("    coefficients do not get to name a top-band bet.")
        elif self.verdict == "LEAN":
            L.append(f"    {gap_bet:+.2f} {unit} more -> BET {self.side}")
        else:
            L.append("    already at the top band.")
        if self.missing:
            L.append(f"    still unchecked: {', '.join(self.missing)}")

        for r in self.reasons:
            L.append(f"    note: {r}")
        return "\n".join(L)


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
           game_day: date | None = None, opened: float | None = None,
           posted: float | None = None,
           missing: Iterable[str] | None = None,
           trial: bool = False) -> Call:
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
    floor = CONTRADICTION_FLOOR[sport]
    contradicting = [e for e in documented
                     if abs(e.unpriced) >= floor and (e.unpriced > 0) != (net > 0)]

    # In trial mode provisional items satisfy the grounded gate, so an idea
    # can be run and logged rather than argued about. It still cannot reach
    # BET: a top-band call on coefficients nobody has measured would be the
    # false confidence this whole model exists to refuse.
    gates = {
        "fresh": bool(fresh),
        "grounded": bool(documented) or (trial and bool(fresh)),
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
            "Everything found rests on provisional coefficients."
            + (" Trial mode: logged as a hypothesis under test. Record it next to "
               "the strict read and compare after thirty or forty games — that "
               "comparison is the only thing that can settle whether these help."
               if trial else " Logged as a hypothesis, not backed.")
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
            f"{e.name} points the other way at {abs(e.unpriced):.2f}, over the "
            f"{floor:.2f} that counts as a real dissent, and is documented. There is "
            "no validated way to net two real signals that disagree. Standing down."
        )

    if all(gates.values()):
        verdict = "BET" if abs(net) >= STRONG_EDGE[sport] else "LEAN"
        if trial and not documented:
            verdict = "LEAN"      # provisional evidence never reaches the top band
            capped = True
        else:
            capped = False
    else:
        verdict = "PASS"
        capped = False

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
        opened=opened,
        posted=posted,
        missing=list(missing or []),
        capped_at_lean=capped,
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


# --------------------------------------------------------------------------
# Evidence builders
#
# Everything that can put a game on the under, plus the two that can push it
# the other way. Each returns an Evidence or None -- None means "no reading",
# which is different from "a reading of zero" and is why the gates can tell
# the difference between a quiet game and an unchecked one.
# --------------------------------------------------------------------------

# The market shades totals upward because recreational money bets overs -- the
# public wants runs. That is a documented structural feature rather than a
# forecast, and the usable signal is the gap between the share of *tickets* and
# the share of *money* on a side: many small bets on the over against fewer,
# larger bets on the under is the standard sharp-money tell.
#
# The direction is well established; the size per game is not, so the term is
# capped hard. A 40-point divergence is worth the same 0.30 runs as an 80-point
# one, because anything more precise would be invented.
PUBLIC_SPLIT_MIN_GAP = 20.0
PUBLIC_SPLIT_RUNS = 0.30


def public_split(ticket_pct_over: float, money_pct_over: float,
                 source: str, as_of=None) -> "Evidence | None":
    """Sharp money against the public, read off the ticket/money divergence.

    Both arguments are the OVER's share, 0-100. Tickets well above money means
    a lot of small over bets and a little large under money, which leans under.
    """
    gap = ticket_pct_over - money_pct_over
    if abs(gap) < PUBLIC_SPLIT_MIN_GAP:
        return None
    runs = -PUBLIC_SPLIT_RUNS if gap > 0 else PUBLIC_SPLIT_RUNS
    lean = "under" if gap > 0 else "over"
    return Evidence(
        "Sharp/public split",
        runs,
        "documented",
        f"{source}: over has {ticket_pct_over:.0f}% of tickets but "
        f"{money_pct_over:.0f}% of money, a {abs(gap):.0f}-point gap. Small bets on "
        f"the over, big money on the {lean}. Capped at {PUBLIC_SPLIT_RUNS} runs "
        "because the direction is documented and the size is not.",
        as_of,
    )


# --- the park -------------------------------------------------------------
#
# A park factor does NOT get a term of its own here, and that is deliberate.
# It is published, season-long and identical every night, so it is inside the
# posted total before anyone looks it up. Adding it as an adjustment is the
# same double count that put the fourteen-input model behind the naked line.
#
# What it legitimately does is change how much TONIGHT's wind is worth. Fifteen
# miles an hour blowing out at a park where balls already carry is not the same
# event as fifteen out where they die on the track, and the line prices the
# park's average conditions rather than this evening's. So the park enters as a
# multiplier on the wind and nowhere else.
#
# The size is reasoning, not measurement: a factor is scaled to pf/100 and held
# inside +/-20%, so a 113 park lifts a 1.00-run wind to 1.13 and a 90 park cuts
# it to 0.90. Big enough to matter on a stacked card, too small to invent a
# signal where the wind was not already saying something.
PARK_NEUTRAL = 100.0
PARK_PLAUSIBLE = (70.0, 130.0)
PARK_WIND_SCALE_CAP = 0.20


def park_wind_scale(park_factor: float | None) -> float:
    """How far tonight's wind is amplified or damped by the park.

    Returns 1.0 for a missing, neutral or implausible figure -- a typo must
    leave the wind alone rather than double it.
    """
    if park_factor is None:
        return 1.0
    lo, hi = PARK_PLAUSIBLE
    if not (lo <= park_factor <= hi):
        return 1.0
    scale = park_factor / PARK_NEUTRAL
    return max(1.0 - PARK_WIND_SCALE_CAP, min(1.0 + PARK_WIND_SCALE_CAP, scale))


def wind(mph: float, direction: str, source: str, as_of=None,
         park_factor: float | None = None) -> "Evidence | None":
    """Wind, the largest weather term and the main physical under-driver.

    Nothing below 8 mph, then 0.10 runs per mph, capped at 1.5. A cross wind is
    explicitly nothing rather than absent -- it is a reading, and it says the
    weather was checked.

    ``park_factor`` scales the result and nothing else; see the note above for
    why the park is not allowed a term of its own.
    """
    d = (direction or "").strip().lower()
    if d not in ("out", "in", "cross"):
        return None
    if d == "cross":
        return Evidence("Wind", 0.0, "documented",
                        f"{source}: {mph:.0f} mph across the field, which carries "
                        "a fly ball neither way.", as_of)
    effective = max(0.0, mph - 8.0)
    mag = min(1.5, effective * 0.10)
    scale = park_wind_scale(park_factor)
    tail = ""
    if scale != 1.0:
        tail = (f" Scaled by {scale:.2f} for a park factor of {park_factor:.0f} "
                "-- the park is not a term of its own, it only changes what "
                "tonight's wind is worth.")
        mag = min(1.5, mag * scale)
    runs = mag if d == "out" else -mag
    return Evidence("Wind", runs, "documented",
                    f"{source}: {mph:.0f} mph blowing {d}.{tail}", as_of)


# --- the umpire, done properly -------------------------------------------
#
# The plate umpire owns the strike zone and the strike zone is the game's
# thermostat: a wide zone means more called strikes, more strikeouts, shorter
# counts and fewer walks, so fewer runs; a tight zone forces pitchers over the
# heart of the plate or into walks, so more. Published work puts the spread
# between the most pitcher-friendly and most hitter-friendly umpire at about
# 1.5 runs a game. It is also the one input that arrives AFTER the opening
# number -- assignments post the morning of the game -- which is what makes it
# worth having at all.
#
# Two things this gets right that the naive version did not.
#
# 1. USE THE OVER/UNDER RECORD, NOT RUNS PER GAME. An umpire's R/Gm is
#    confounded by which parks he drew: a man who happened to work Coors and
#    Cincinnati reads hot for reasons that have nothing to do with his zone.
#    His over/under record is park-adjusted by construction, because the line
#    he was measured against already accounts for the park and the teams. R/Gm
#    survives below only as a fallback, and says it is the weaker input.
#
# 2. DERIVE THE SHRINKAGE, DO NOT PICK IT. The first version used n/(n+120),
#    which implies a true between-umpire spread of 0.40 runs. The 1.5-run
#    figure is the RAW observed spread across ~90 umpires and so contains
#    sampling noise; the true spread is smaller. Treating 1.5 as roughly five
#    standard deviations gives tau ~= 0.30 runs, and k = sd^2/tau^2 = 214.
#
# For the over/under form the same logic becomes a Beta prior: an umpire's true
# over-rate has sd tau/sd_total * phi(0) = 0.027, and the Beta(a,a) with that
# spread has a = 168, i.e. a prior worth 335 games. Umpires work the plate
# about every fourth game, so a season is ~30 -- barely a tenth of the prior.
# That is the honest reason a spectacular-looking single-season line is worth
# almost nothing.
UMPIRE_TAU_RUNS = 0.30
UMPIRE_PRIOR_GAMES = 335.0
UMPIRE_SHRINK_GAMES = 214.0        # for the R/Gm fallback
UMPIRE_CAP_RUNS = 1.0
UMPIRE_PLAUSIBLE_RPG = (6.0, 12.0)


def umpire_ou(over: int, under: int, source: str, as_of=None,
              name: str = "the plate umpire") -> "Evidence | None":
    """From the umpire's over/under record — the park-adjusted input.

    Beta-shrunk toward even, then converted to runs through the observed
    dispersion. A 3-0 umpire at the top of a leaderboard sorted by over-rate
    comes out worth about +0.05 runs, which is the point.
    """
    from statistics import NormalDist
    n = over + under
    if n <= 0:
        return None
    a = UMPIRE_PRIOR_GAMES / 2.0
    p = (over + a) / (n + 2 * a)
    runs = NormalDist().inv_cdf(p) * DISPERSION["MLB"]
    runs = max(-UMPIRE_CAP_RUNS, min(UMPIRE_CAP_RUNS, runs))
    return Evidence(
        "Umpire", runs, "documented",
        f"{source}: {name} is {over}-{under} to the over ({over / n * 100:.0f}%) "
        f"on {n} plate games. Shrunk against a {UMPIRE_PRIOR_GAMES:.0f}-game prior "
        f"that reads {p * 100:.2f}%, worth {runs:+.2f} runs. Umpires work the plate "
        "about every fourth game, so one season is ~30 — a tenth of the prior, "
        "which is why a big single-season split moves almost nothing.",
        as_of,
    )


def umpire_rpg(runs_per_game: float, games: float, source: str,
               league: float = 8.6, as_of=None) -> "Evidence | None":
    """Fallback: the umpire's runs per game, when no over/under record is to hand.

    Weaker than ``umpire_ou`` and labelled as such, because R/Gm is confounded
    by which parks the man drew. Capped at a run either way, and an impossible
    figure is read as a typo and ignored rather than trusted — impossible
    inputs produced the worst calls this project ever made.
    """
    if not (UMPIRE_PLAUSIBLE_RPG[0] <= runs_per_game <= UMPIRE_PLAUSIBLE_RPG[1]):
        return None
    shrink = games / (games + UMPIRE_SHRINK_GAMES) if games > 0 else 0.0
    runs = max(-UMPIRE_CAP_RUNS, min(UMPIRE_CAP_RUNS, (runs_per_game - league) * shrink))
    return Evidence(
        "Umpire (R/Gm fallback)", runs, "documented",
        f"{source}: {runs_per_game:.2f} runs a game against {league:.2f} league, on "
        f"{games:.0f} games — regressed to {runs:+.2f}. This is the weaker of the two "
        "umpire inputs: R/Gm is confounded by which parks he happened to draw, where "
        "his over/under record is park-adjusted by the lines he was measured against.",
        as_of,
    )


def temperature(temp_f: float, source: str, as_of=None) -> "Evidence":
    """Air density. Small, real, and the weather term the market prices best."""
    runs = max(-0.35, min(0.35, (temp_f - 70.0) * 0.008))
    return Evidence("Temperature", runs, "documented",
                    f"{source}: {temp_f:.0f}F against a 70F baseline.", as_of)


# A missing rotation player costs a WNBA team more than in any other league:
# twelve-deep rosters, starters at 32+ minutes, and no bench to absorb it. The
# direction is documented -- absent offensive players pull totals down, absent
# defensive ones push them up -- but the size per player is not, so these are
# capped hard and deliberately conservative. Two points for a starter, three
# and a half for a team's leading scorer, and a ceiling per team however long
# the injury list runs, because the fourth man out is being replaced by someone
# who would not otherwise take the floor and the returns stop compounding well
# before that.
#
# The ceiling is 8.0 rather than the 6.0 first written here. At 6.0 it bound at
# three absences, so three, five and nine all scored identically and the model
# could not tell a thin night from a gutted one. It binds at four now, which
# keeps the granularity that matters and still refuses to let a long list read
# as a huge edge.
POINTS_PER_STARTER_OUT = 2.0
POINTS_LEADING_SCORER_OUT = 3.5
MAX_POINTS_PER_TEAM_OUT = 8.0


def players_out(team: str, starters_out: int, source: str,
                leading_scorer_out: bool = False, as_of=None) -> "Evidence | None":
    """Absent rotation players, as points off the total.

    ``starters_out`` counts rotation regulars, including the leading scorer if
    ``leading_scorer_out``. Returns None at zero rather than an Evidence worth
    nothing -- a team with nobody out is not a reading about tonight.
    """
    if starters_out <= 0:
        return None
    base = (starters_out - 1) * POINTS_PER_STARTER_OUT if leading_scorer_out \
        else starters_out * POINTS_PER_STARTER_OUT
    if leading_scorer_out:
        base += POINTS_LEADING_SCORER_OUT
    points = -min(MAX_POINTS_PER_TEAM_OUT, base)
    who = f"{starters_out} rotation regular{'s' if starters_out != 1 else ''}"
    if leading_scorer_out:
        who += ", including their leading scorer"
    return Evidence(
        f"{team} absences",
        points,
        "documented",
        f"{source}: {who} out. Worth {points:+.1f} on a capped coefficient — "
        "the direction is documented, the size is not, and the cap is what "
        "stops a five-deep injury list reading as a fifteen-point edge.",
        as_of,
    )


# --- the trial tier -------------------------------------------------------
#
# Three inputs the owner asked to try. They are marked provisional, and not as
# a hedge: two of them have been measured on the 116-game log and came back
# null. Correlations against (final - line) were head-to-head t = -0.40 and
# team form t = -0.07, and neither survived a cross-validated fit. So they
# carry small coefficients, they are labelled every time they appear, and by
# default they cannot satisfy the grounded gate on their own.
#
# Pitcher last-five is the exception worth taking seriously. The log only ever
# held *season* starter ERA; a last-five window has never been tested here, so
# it is genuinely a new input rather than a re-run of a failed one.
#
# ``decide(trial=True)`` lets these carry a LEAN so the idea can actually be
# run and logged. Every call should be recorded both ways -- strict and trial
# -- because the only way to find out whether these help is to measure them
# against the same games, which is exactly what was never done the first time.

# Fractions of the gap between what the trend says and what the line says.
# Deliberately small: with a measured effect indistinguishable from zero, any
# coefficient is a guess, and a large guess is how the first two models died.
FORM_FRACTION = 0.15
FORM_CAP = 0.60
H2H_FRACTION = 0.10
H2H_CAP = 0.40
H2H_MIN_MEETINGS = 3

# ERA stabilises slowly. Five starts is roughly 27 innings against a ~120
# innings half-weight point, so a last-five line keeps under a fifth of its
# apparent gap. The starters cover about five of the nine innings each.
ERA_STABILISE_IP = 120.0
STARTER_INNINGS_SHARE = 5.0 / 9.0
PITCHER_CAP = 0.70
LEAGUE_ERA = 4.30


def team_form(away_avg_total: float, home_avg_total: float, games: int,
              line: float, source: str, as_of=None) -> "Evidence | None":
    """Each side's average total over its last N games, against tonight's line.

    Measured null on the logged games (t = -0.07). Kept small and provisional.
    """
    if games <= 0:
        return None
    avg = (away_avg_total + home_avg_total) / 2.0
    gap = avg - line
    runs = max(-FORM_CAP, min(FORM_CAP, gap * FORM_FRACTION))
    return Evidence(
        f"Team form (last {games})", runs, "provisional",
        f"{source}: last-{games} totals average {avg:.1f} against a line of {line:g}, "
        f"a gap of {gap:+.1f} runs. Taken at {FORM_FRACTION:.0%} and capped — this "
        f"input measured t = -0.07 against the residual on 116 logged games.",
        as_of,
    )


def head_to_head(avg_total: float, meetings: int, line: float, source: str,
                 as_of=None) -> "Evidence | None":
    """These two clubs' average total when they have met, against tonight's line.

    Returns nothing under three meetings. One or two games is not a trend, and
    letting a two-game h2h vote is the specific fault that cost four picks a
    confidence band in the old model.
    """
    if meetings < H2H_MIN_MEETINGS:
        return None
    gap = avg_total - line
    runs = max(-H2H_CAP, min(H2H_CAP, gap * H2H_FRACTION))
    return Evidence(
        f"Head to head ({meetings})", runs, "provisional",
        f"{source}: {meetings} meetings averaging {avg_total:.1f} against a line of "
        f"{line:g}, a gap of {gap:+.1f} runs. Taken at {H2H_FRACTION:.0%} and capped — "
        "this input measured t = -0.40 against the residual on 116 logged games.",
        as_of,
    )


def pitchers_last5(away_era: float, away_ip: float, home_era: float,
                   home_ip: float, source: str, league_era: float = LEAGUE_ERA,
                   as_of=None) -> "Evidence | None":
    """Both starters' ERA over their last five starts, regressed for innings.

    The one genuinely untested input of the three: the track record only ever
    held season ERA, so this window has never been measured here. Still
    provisional until it has been.

    Each starter's gap from league is shrunk by ip/(ip + 120) -- five starts is
    about 27 innings, so roughly a fifth of the gap survives -- and then scaled
    by the share of the game a starter actually pitches.
    """
    parts, total = [], 0.0
    for era, ip, who in ((away_era, away_ip, "away"), (home_era, home_ip, "home")):
        if era is None or ip is None or ip <= 0:
            continue
        shrink = ip / (ip + ERA_STABILISE_IP)
        runs = (era - league_era) * shrink * STARTER_INNINGS_SHARE
        total += runs
        parts.append(f"{who} {era:.2f} over {ip:.0f} IP -> {runs:+.2f}")
    if not parts:
        return None
    total = max(-PITCHER_CAP, min(PITCHER_CAP, total))
    return Evidence(
        "Starters, last 5", total, "provisional",
        f"{source}: {'; '.join(parts)} against a {league_era:.2f} league ERA. "
        f"Net {total:+.2f} runs. Five starts is ~27 innings against a 120-inning "
        "half-weight point, so under a fifth of each gap survives regression. "
        "Untested here — the log only ever held season ERA.",
        as_of,
    )


# The bullpen covers roughly four of the nine innings -- more than most people
# credit it with, and the half of the game the starter inputs say nothing
# about. Same regression treatment as the starters, scaled by that share.
#
# Note this is bullpen *form*, not bullpen *availability*. Availability -- who
# threw last night and cannot go -- is the better idea and the one with a real
# claim to being unpriced, but it needs beat-writer notes that are hard to get
# consistently and impossible to check afterwards. Form is what a screenshot
# can actually deliver, so it is what this measures.
BULLPEN_INNINGS_SHARE = 4.0 / 9.0
BULLPEN_STABILISE_IP = 90.0
BULLPEN_CAP = 0.60

# Innings became optional on request: entering two ERAs is the whole job and
# hunting down the innings behind them was not worth the typing. Regression
# still has to happen -- an unshrunk ERA gap is the false precision this model
# exists to refuse -- so a missing figure falls back to roughly a month of
# bullpen work, which shrinks to 110/(110+90) = 0.55 of the gap.
#
# The direction of the assumption matters. A team's SEASON bullpen ERA rests on
# ~450 innings and would earn ~0.84, so assuming a month under-weights a season
# figure rather than over-weighting a recent one. That errs toward not betting,
# which is the right way for a guess to be wrong.
BULLPEN_ASSUMED_IP = 110.0


def bullpens_recent(away_era: float, away_ip: float | None, home_era: float,
                    home_ip: float | None, source: str,
                    league_era: float = LEAGUE_ERA,
                    as_of=None) -> "Evidence | None":
    """Both bullpens' recent ERA, regressed for innings and scaled by their share.

    ``away_ip`` and ``home_ip`` may be None, in which case BULLPEN_ASSUMED_IP
    stands in and the detail string says so -- an assumed number must never be
    reported as though it were entered.
    """
    parts, total = [], 0.0
    for era, ip, who in ((away_era, away_ip, "away"), (home_era, home_ip, "home")):
        if era is None:
            continue
        assumed = ip is None or ip <= 0
        ip = BULLPEN_ASSUMED_IP if assumed else ip
        shrink = ip / (ip + BULLPEN_STABILISE_IP)
        runs = (era - league_era) * shrink * BULLPEN_INNINGS_SHARE
        total += runs
        over = f"{ip:.0f} IP assumed" if assumed else f"{ip:.0f} IP"
        parts.append(f"{who} {era:.2f} over {over} -> {runs:+.2f}")
    if not parts:
        return None
    total = max(-BULLPEN_CAP, min(BULLPEN_CAP, total))
    return Evidence(
        "Bullpens, recent", total, "provisional",
        f"{source}: {'; '.join(parts)} against a {league_era:.2f} league ERA. "
        f"Net {total:+.2f} runs, scaled by the ~4 of 9 innings a pen covers. This "
        "is bullpen form, not availability — availability is the better idea but "
        "needs beat notes a screenshot cannot carry.",
        as_of,
    )
