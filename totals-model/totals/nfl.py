"""NFL point spreads, modelled as a discrete margin distribution.

WHY SPREAD AND NOT TOTAL
------------------------
The MLB model's best feature is that it models a DISCRETE distribution and so
gets P(push) exactly, where a continuous model silently hands that probability
to the two sides. NFL margins are far more violently discrete than baseball run
totals, and the effect is much larger:

    margin of exactly 3  ~9.5% of games
    margin of exactly 7  ~6.5%
    3, 7, 6, 10, 14      roughly a quarter of all games between them

Totals have nothing remotely comparable. So the spread is where this
architecture has something real to say.

More importantly, it gives an edge that does NOT require out-predicting the
market. The question "what is half a point worth here?" is arithmetic on the
margin distribution, not an opinion about who wins. Books routinely charge 20-25
cents to buy from -3 to -2.5; the fair price is around 8-12. Knowing which side
of that you are on is mechanical, checkable game by game, and does not need the
thousands of settled bets that proving a forecasting edge requires.

WHAT THIS MODEL DOES NOT CLAIM
------------------------------
It will not reliably beat the closing NFL spread. That market is the most
efficiently priced in sports and 17 games a week will never accumulate the
sample to demonstrate an edge over it. `half_point_value()` is the part that
earns its keep; the power rating is there to stop the card being empty and is
weighted accordingly.

CONVENTION
----------
`spread` is always the HOME team's number: -3.5 means the home side is favoured
by three and a half. `margin` is always home points minus away points. The home
side covers when `margin > -spread`, and pushes when `margin == -spread`, which
can only happen on a whole number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# LEAGUE CONSTANTS
#
# Same quarantine as the MLB model, and for the same reason: none of this can be
# verified from inside the sandbox -- every stats site is blocked by the proxy.
# These come from memory of well-established figures, and the model is built so
# that being wrong about them costs as little as possible. `sensitivity()` at
# the bottom prints the damage and a test pins it.
#
# To update: change the numbers in this block and nothing else.
SOURCE = "from memory, 2026-09-13, unverified against a primary table"

#: Standard deviation of (final margin - closing spread). The single most
#: important number here. Commonly quoted between 13.0 and 13.9; the midpoint
#: is used and the model is deliberately insensitive to it at this precision.
MARGIN_SD = 13.5

#: Modern home-field advantage in points. Historically about 3; it has fallen
#: through the 2020s and now sits nearer 1.5. Only used to define what a
#: "neutral" matchup means, so an error here cancels rather than accumulates.
HOME_FIELD = 1.6

#: Points per game, one team. Used to scale a net-points-per-game rating.
LEAGUE_PPG = 22.5

#: How many games before a net-points-per-game rating is worth full weight.
#: In week 2 a team's season rating is one game of noise, so it earns almost
#: nothing. Same sample-size discipline as head-to-head in the MLB model.
RATING_STABLE_AT = 8.0

#: Regression applied to a raw net-points difference. Two teams whose season
#: ratings differ by 10 points do not play to a 10-point margin; simple power
#: ratings overstate, and the standard correction is around 0.7.
RATING_SHRINK = 0.70

# Key numbers. Multipliers on the probability of each ABSOLUTE margin, applied
# to a normal kernel and then renormalised. Relative, so they do not depend on
# who is favoured -- a 3-point margin is common whichever side it falls.
#
# These are FITTED, not chosen: each one is the ratio of the published frequency
# for that margin to what a smooth curve of the same width would give. The
# resulting distribution reproduces the documented figures to within 0.03 of a
# percentage point, and a test pins that.
#
# The fit says something the folklore gets backwards. Four and six are NOT key
# numbers -- they come in at 0.74 and 0.87, meaning they are rarer than a smooth
# curve predicts, because three and seven take the mass. Only 3, 7 and 10 are
# genuinely over-represented.
#
# Set every value to 1.0 and this model degrades cleanly to a normal, which is
# what a model that gets these wrong should do.
KEY_NUMBERS = {
    3: 1.73,    # far and away the most common margin
    7: 1.30,
    10: 1.01,
    14: 0.99,
    17: 0.88,
    6: 0.87,    # LESS common than a smooth curve says, not more
    4: 0.74,
    1: 0.52,    # one-point games are much rarer than the folklore suggests
}

#: The SD the multipliers were fitted at. League-wide margins are wider than a
#: single game's residual because the spreads themselves vary, so the fit is
#: done here and the relative lumpiness carries over to per-game use.
KEY_FIT_SD = 14.5

#: A wide market is a less certain one, not a sharper one. Same treatment and
#: same reference as the MLB model -- a normal main-line spread holds ~4.8%.
HOLD_REFERENCE = 0.05

#: Bands. The floors match the MLB model so one record reads across both.
BANDS = ((0.62, "MAX BET"), (0.57, "STRONG BET"), (0.53, "BET"), (0.00, "NO BET"))

WEIGHTS = {"market": 4.0, "rating": 1.2, "qb": 1.0}

#: A starting quarterback is the largest single swing in the sport. This is the
#: value of losing an average starter to an average backup; it is NOT scored by
#: default, because the market moves on the announcement and counting it again
#: would double-count. It is used only to say whether the line has already moved
#: far enough to have absorbed the news.
QB_POINTS = 5.0

PLAUSIBLE = {"spread": (-30.0, 30.0), "ppg": (-30.0, 30.0), "games": (0.0, 25.0)}


def _ok(v: float | None, window: str) -> bool:
    lo, hi = PLAUSIBLE[window]
    return v is not None and lo <= v <= hi


# ===========================================================================
# The margin distribution
# ===========================================================================

def key_multiplier(margin: int) -> float:
    """Relative weight for an absolute margin. 1.0 for every non-key number."""
    return KEY_NUMBERS.get(abs(int(margin)), 1.0)


def _normal_kernel(m: int, mu: float, sd: float) -> float:
    z = (m - mu) / sd
    return math.exp(-0.5 * z * z)


def distribution_mean(location: float, sd: float = MARGIN_SD) -> float:
    """The actual mean of the modelled distribution.

    The key-number multipliers are anchored to ABSOLUTE margins, so away from
    zero they pull the distribution off its kernel's centre -- by 0.07 points at
    a location of 3 and 0.15 at 7. Small, but the location parameter is not the
    expected margin and should not be printed as though it were.
    """
    pmf = margin_pmf(location, sd)
    return sum(m * p for m, p in pmf.items())


def margin_pmf(mu: float, sd: float = MARGIN_SD) -> dict[int, float]:
    """P(margin = m) for every plausible m, as a normalised discrete mass.

    `mu` is the LOCATION of the kernel, not the mean of the result -- see
    `distribution_mean`.

    A normal kernel carries the shape; the key-number multipliers carry the
    lumpiness that makes NFL spreads worth modelling at all. Zero is excluded:
    regulation ties are vanishingly rare and every margin of 0 in the record is
    a game that went to overtime and resolved.
    """
    lo, hi = int(mu - 6 * sd), int(mu + 6 * sd)
    raw = {}
    for m in range(lo, hi + 1):
        if m == 0:
            continue
        raw[m] = _normal_kernel(m, mu, sd) * key_multiplier(m)
    total = sum(raw.values())
    return {m: p / total for m, p in raw.items()}


def margin_split(spread: float, mu: float,
                 sd: float = MARGIN_SD) -> tuple[float, float, float]:
    """(home covers, push, away covers) for a HOME spread.

    Home covers when margin > -spread. The push term is the whole point of
    doing this discretely: on a home line of -3 with the margin landing on
    exactly 3, nobody wins, and that is nearly a tenth of all games.
    """
    pmf = margin_pmf(mu, sd)
    need = -spread
    home = push = away = 0.0
    for m, p in pmf.items():
        if abs(m - need) < 1e-9:
            push += p
        elif m > need:
            home += p
        else:
            away += p
    return home, push, away


def half_point_value(spread: float, mu: float,
                     sd: float = MARGIN_SD) -> dict[str, float]:
    """What moving the home line half a point is worth.

    This is the part of the model that does not require an opinion. Buying from
    -3 to -2.5 removes the push and turns some pushes into wins; the fair price
    of that is arithmetic. Books charge a flat 20-25 cents for it almost
    everywhere, which is a large overcharge off a key number and a considerable
    bargain on one.
    """
    base_home, base_push, base_away = margin_split(spread, mu, sd)
    base_live = base_home + base_away
    base_p = base_home / base_live if base_live > 0 else 0.5

    better_home, _bp, better_away = margin_split(spread + 0.5, mu, sd)
    better_live = better_home + better_away
    better_p = better_home / better_live if better_live > 0 else 0.5

    gain = better_p - base_p
    return {
        "spread": spread,
        "half_point_to": spread + 0.5,
        "probability_gain": gain,
        "cents": _cents_for(base_p, gain),
        "push_removed": base_push,
    }


def _price_index(p: float) -> float:
    """American odds as a CONTINUOUS scale, so cents can be subtracted.

    American odds are discontinuous at the century: +100 and -100 are the same
    bet, so subtracting them directly double-counts the gap and reports a
    ten-cent move as two hundred. This maps the ladder
    ... +120, +110, 100, -110, -120 ... onto ... -20, -10, 0, +10, +20 ...
    which is monotone in p and is what "cents" means to a trader.
    """
    p = min(max(p, 1e-9), 1 - 1e-9)
    if p >= 0.5:
        return 100.0 * p / (1.0 - p) - 100.0
    return 100.0 - 100.0 * (1.0 - p) / p


def _cents_for(p: float, gain: float) -> float:
    """Convert a probability gain into the cents of price it is worth.

    This is what a book is charging for when it quotes -110 on one number and
    -130 half a point better: twenty cents.
    """
    return abs(_price_index(p + gain) - _price_index(p))


def fair_price(p: float) -> float:
    """American odds implied by a resolved-outcome probability."""
    if abs(p - 0.5) < 1e-9:
        return 100.0
    return -100.0 * p / (1.0 - p) if p > 0.5 else 100.0 * (1.0 - p) / p


# ===========================================================================
# Reading the market
# ===========================================================================

def implied(price: float) -> float:
    return (-price) / ((-price) + 100.0) if price < 0 else 100.0 / (price + 100.0)


def hold(home_price: float, away_price: float) -> float:
    return implied(home_price) + implied(away_price) - 1.0


def market_confidence(book_hold: float) -> float:
    if book_hold <= HOLD_REFERENCE:
        return 1.0
    return HOLD_REFERENCE / book_hold


def fair_spread(spread: float, home_price: float | None,
                away_price: float | None) -> tuple[float, str]:
    """Recover the market's real number from the two prices.

    A posted spread is rounded to the half point; the prices are not. Home -3
    at -125 is a market saying the true number is nearer -3.5, and that
    difference is enormous when it is sitting on a key number.
    """
    quoted = home_price is not None and away_price is not None
    if not quoted:
        home_price = away_price = -110.0
    h, a = implied(home_price), implied(away_price)
    s = h + a
    book_hold = s - 1.0
    conf = market_confidence(book_hold)
    raw_home = h / s
    p_home = 0.5 + (raw_home - 0.5) * conf

    # The candidate is a MARGIN (home minus away, positive = home better), so it
    # lives near -spread, not near spread. Searching around `spread` put the
    # root outside the bracket on every home favourite and the bisection walked
    # to the wrong end -- an empty card on -7 came back AWAY 69%.
    lo, hi = -spread - 12.0, -spread + 12.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        ch, _cp, ca = margin_split(spread, mid)
        live = ch + ca
        cond = ch / live if live > 0 else 0.5
        if cond < p_home:
            lo = mid
        else:
            hi = mid
    mu = (lo + hi) / 2.0

    tail = ""
    if conf < 1.0:
        tail = (f" That is a {book_hold * 100:.1f}% hold where a main line runs "
                f"{HOLD_REFERENCE * 100:.0f}% -- most likely an alternate number. A wide "
                f"market is a less certain one, so the read has been pulled back from "
                f"{raw_home * 100:.1f}% toward even and only {conf * 100:.0f}% of it kept.")
    if quoted:
        why = (f"{home_price:+.0f}/{away_price:+.0f} de-vigs to {p_home * 100:.1f}% home "
               f"({book_hold * 100:.2f}% hold), which is the market saying the true margin "
               f"is {mu:+.2f} rather than the {-spread:+g} the posted number implies." + tail)
    else:
        why = (f"No prices given, so -110 both ways is assumed. A home line of {spread:+g} "
               f"priced evenly implies a true margin of {mu:+.2f}.")
    return mu, why


# ===========================================================================
# Forecast
# ===========================================================================

@dataclass
class Estimate:
    name: str
    margin: float
    weight: float
    detail: str


@dataclass
class Delta:
    name: str
    points: float
    detail: str


@dataclass
class SpreadForecast:
    matchup: str
    spread: float
    projected: float          # expected margin, home minus away
    p_home: float
    p_push: float
    p_away: float
    side: str                 # "HOME" or "AWAY"
    band: str
    expected_margin: float    # the distribution's actual mean, not the location
    estimates: list[Estimate]
    deltas: list[Delta]
    half_point: dict[str, float]
    notes: list[str] = field(default_factory=list)

    @property
    def p_side(self) -> float:
        return self.p_home if self.side == "HOME" else self.p_away

    @property
    def p_resolved(self) -> float:
        live = self.p_home + self.p_away
        return self.p_side / live if live > 0 else 0.5

    @property
    def fair_price(self) -> float:
        return fair_price(self.p_resolved)

    def edge_vs(self, price: float) -> float:
        live = self.p_home + self.p_away
        if live <= 0:
            return 0.0
        win = self.p_side
        lose = live - win
        payout = (price / 100.0) if price > 0 else (100.0 / -price)
        return win * payout - lose

    def to_dict(self) -> dict[str, Any]:
        return {
            "sport": "NFL", "matchup": self.matchup, "spread": self.spread,
            "projected": round(self.projected, 3),
            "expected_margin": round(self.expected_margin, 3),
            "p_home": round(self.p_home, 5), "p_push": round(self.p_push, 5),
            "p_away": round(self.p_away, 5),
            "p_resolved": round(self.p_resolved, 5),
            "side": self.side, "band": self.band,
            "fair_price": round(self.fair_price, 1),
            "half_point": {k: round(v, 5) for k, v in self.half_point.items()},
            "estimates": [{"name": e.name, "margin": round(e.margin, 3),
                           "weight": round(e.weight, 4), "detail": e.detail}
                          for e in self.estimates],
            "deltas": [{"name": d.name, "points": round(d.points, 3),
                        "detail": d.detail} for d in self.deltas],
            "notes": self.notes,
        }

    def brief(self) -> str:
        out = [f"{self.matchup} -- {self.side} {self.spread:+g}  "
               f"{self.p_resolved * 100:.1f}% of resolved bets  [{self.band}]  "
               f"fair {self.fair_price:+.0f}",
               f"  projected margin {self.projected:+.2f} (home minus away)  "
               f"home {self.p_home * 100:.1f} / push {self.p_push * 100:.1f} / "
               f"away {self.p_away * 100:.1f}"]
        tw = sum(e.weight for e in self.estimates)
        for e in self.estimates:
            out.append(f"    {e.name:<22} {e.margin:+8.2f}  {e.weight / tw * 100:4.0f}%")
        for d in self.deltas:
            out.append(f"    {d.name:<22} {d.points:+8.2f}  delta")
        hp = self.half_point
        out.append(f"  half point to {hp['half_point_to']:+g} is worth "
                   f"{hp['cents']:.0f} cents")
        out.extend(f"  note: {n}" for n in self.notes)
        return "\n".join(out)


def rating_weight(base: float, games_played: float | None) -> float:
    """Sample-size discipline, same shape as head-to-head in the MLB model.

    A net-points rating after one game is one game of noise. It earns full
    weight at RATING_STABLE_AT and a proportion of it before that.
    """
    if games_played is None:
        return 0.0
    return base * min(1.0, max(0.0, games_played) / RATING_STABLE_AT)


def forecast_nfl(
    matchup: str,
    spread: float,
    home_price: float | None = None,
    away_price: float | None = None,
    home_net_ppg: float | None = None,
    away_net_ppg: float | None = None,
    games_played: float | None = None,
    home_qb_out: bool = False,
    away_qb_out: bool = False,
    opened: float | None = None,
) -> SpreadForecast:
    if not _ok(spread, "spread"):
        raise ValueError(f"spread {spread!r} is outside {PLAUSIBLE['spread']}")

    notes: list[str] = []
    anchor, anchor_detail = fair_spread(spread, home_price, away_price)
    estimates = [Estimate("Market", anchor, WEIGHTS["market"], anchor_detail)]

    # --- power rating, as a differential -----------------------------------
    # Two league-average teams differ by zero, so the estimate lands exactly on
    # the market anchor and moves the forecast by exactly nothing. That is the
    # property that keeps a hidden lean out, and it is arithmetic rather than a
    # calibration that came out right.
    if _ok(home_net_ppg, "ppg") and _ok(away_net_ppg, "ppg"):
        w = rating_weight(WEIGHTS["rating"], games_played)
        raw = (home_net_ppg - away_net_ppg) * RATING_SHRINK
        thin = ""
        if games_played is not None and games_played < RATING_STABLE_AT:
            thin = (f" Discounted to {games_played:.0f}/{RATING_STABLE_AT:.0f} of its weight: "
                    f"a net-points rating on {games_played:.0f} game(s) is mostly noise.")
        if w > 0:
            estimates.append(Estimate(
                "Power rating", anchor + raw, w,
                f"Home {home_net_ppg:+.1f} and away {away_net_ppg:+.1f} net points per game, "
                f"regressed at {RATING_SHRINK:.2f}, is {raw:+.1f} points of margin. Two "
                f"league-average teams move this by exactly zero." + thin))
        else:
            notes.append("No games played entered, so the power rating is out of the blend. "
                         "Early in a season that is the honest answer, not a gap.")
    elif home_net_ppg is not None or away_net_ppg is not None:
        notes.append("Only one team's net points is in. A differential needs both, so the "
                     "rating is out of the blend and its weight has gone to the market.")

    # --- quarterback, displayed and NOT scored ------------------------------
    deltas: list[Delta] = []
    if home_qb_out or away_qb_out:
        who = "Home" if home_qb_out and not away_qb_out else (
            "Away" if away_qb_out and not home_qb_out else "Both")
        notes.append(
            f"{who} starting quarterback out. Worth roughly {QB_POINTS:.0f} points, and it "
            "is NOT scored here -- an NFL line moves three to seven points on the "
            "announcement, so it is already inside the number you are reading. Check "
            "whether the line actually moved; if it has not, the market does not believe "
            "the report.")

    if opened is not None and abs(opened - spread) > 1e-9:
        notes.append(
            f"The number moved {opened:+g} to {spread:+g} ({spread - opened:+.1f}). Not "
            "scored -- the current line is the anchor, so the move is already inside it. "
            "It is here because a move through a key number is worth seeing before you bet.")

    return _assemble(matchup, spread, estimates, deltas, notes)


def _assemble(matchup, spread, estimates, deltas, notes) -> SpreadForecast:
    tw = sum(e.weight for e in estimates)
    if tw <= 0:
        raise ValueError("no estimates to blend")
    projected = sum(e.margin * e.weight for e in estimates) / tw
    projected += sum(d.points for d in deltas)

    home, push, away = margin_split(spread, projected)
    side = "HOME" if home >= away - 1e-9 else "AWAY"
    p_side = home if side == "HOME" else away
    live = home + away
    p_resolved = p_side / live if live > 0 else 0.5
    band = next(name for floor, name in BANDS if p_resolved >= floor)

    hp = half_point_value(spread, projected)

    if abs(spread - round(spread)) < 1e-9 and push > 0.02:
        notes.append(
            f"The number is whole, so {push * 100:.1f}% of the time this pushes and the "
            f"stake comes back. On a key number that is the largest single outcome on the "
            f"board and a model treating margins as continuous hands it to the two sides.")
    key = abs(round(-spread))
    if key in KEY_NUMBERS and KEY_NUMBERS[key] > 1.0:
        notes.append(
            f"This line sits on {key}, a key number -- margins land there "
            f"{KEY_NUMBERS[key]:.2f}x as often as a smooth curve says. Half a point through "
            f"it is worth {hp['cents']:.0f} cents, against the 20-25 books usually charge.")
    if len(estimates) == 1 and not deltas:
        notes.append("Nothing entered but the number, so the forecast IS the market and the "
                     "answer is a coin flip. That is the correct answer to a question with "
                     "no information in it.")
    if band == BANDS[0][1]:
        notes.append("Top band. Re-read the inputs before acting -- in this project a "
                     "spectacular number has more often been a mistyped one than an edge.")
    return SpreadForecast(matchup, spread, projected, home, push, away,
                          side, band, distribution_mean(projected),
                          estimates, deltas, hp, notes)


# ===========================================================================
# Whether any of this works
# ===========================================================================

def sensitivity(sd_error: float = 1.0) -> dict[str, float]:
    """How much a wrong MARGIN_SD costs, in probability points on a live card."""
    mu, spread = 2.5, -3.0
    base = margin_split(spread, mu, MARGIN_SD)
    off = margin_split(spread, mu, MARGIN_SD + sd_error)
    bl, ol = base[0] + base[2], off[0] + off[2]
    return {
        "sd_error": sd_error,
        "probability_points": abs(base[0] / bl - off[0] / ol) * 100.0,
        "push_points": abs(base[1] - off[1]) * 100.0,
    }


def calibration(records: Iterable[tuple[float, bool]]):
    """Delegates to the MLB implementation -- one measure across both books."""
    from totals.fullgame import calibration as _c
    return _c(records)


def slate(forecasts: list[SpreadForecast]) -> str:
    if not forecasts:
        return "Nothing on the card."
    rows = sorted(forecasts, key=lambda f: -f.p_resolved)
    width = max(len(f.matchup) for f in rows)
    out = [f"{'GAME'.ljust(width)}  LINE    SIDE   PROB   PUSH   FAIR   HALF PT  BAND"]
    for f in rows:
        out.append(f"{f.matchup.ljust(width)}  {f.spread:+6g}  {f.side:<5}  "
                   f"{f.p_resolved * 100:5.1f}%  {f.p_push * 100:4.1f}%  "
                   f"{f.fair_price:+5.0f}  {f.half_point['cents']:5.0f}c  {f.band}")
    return "\n".join(out)
