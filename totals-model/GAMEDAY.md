# Game-day playbook

What I do when a slate arrives. Written down so it is the same every night and
so the numbers below are auditable rather than invented on the spot.

## The one rule

**The posted line is the best available forecast.** Nothing in this playbook
argues with it from season statistics — that approach was measured over 116
logged games and produced a mean absolute error of 3.61 runs where using the
line alone produced 3.58, with a negative cross-validated R² on all fourteen
of its inputs. The only thing worth looking for is information the number does
not have yet.

And the corollary, which is the part that is easy to forget: **news is not an
edge once the line has moved on it.** When Caitlin Clark was ruled out the
Fever line went −11 to −6 on the announcement. Finding that news afterwards and
betting it is arriving after the market. Every item below has to be scored
twice — what it is worth, and how far the line has already travelled.

## What I need from you

Per game: **teams, the posted number, and roughly when it was posted.** If you
have the opening number as well as the current one, send both — the movement is
half the model. Start times help; without them I will assume evening.

## The checklist

Run top to bottom. Most games produce nothing, and that is the expected result.

### MLB totals

| # | Check | Where | Worth | Basis |
|---|---|---|---|---|
| 1 | **Home plate umpire** | [RotoWire daily](https://www.rotowire.com/baseball/umpire-stats-daily.php), [OddsShark O/U records](https://www.oddsshark.com/mlb/umpire-handicapping-statistics) | His runs/game minus league, shrunk `n/(n+120)`, capped ±1.0 | documented |
| 2 | **Wind speed + direction** | [RotoWire weather](https://www.rotowire.com/baseball/weather.php) | Nothing under 8 mph; then 0.10 runs/mph, capped 1.5. Cross wind = 0 | documented |
| 3 | **Temperature** | same | 0.008 runs/°F from 70°, capped 0.35 | documented |
| 4 | **Bullpen availability** | beat writers, [MLB.com](https://www.mlb.com/scores) | 0.15 runs per unavailable high-leverage arm, max 3/side | *provisional* |
| 5 | **Lineup scratches** | same | 0.12 runs per missing regular, max 3/side | *provisional* |
| 6 | **Line movement since open** | you, or Covers | Subtract from 1–5 | — |

Umpire assignments post the morning of the game and are the single item most
likely to be missing from an opening number. It is also the largest: the spread
between the most pitcher-friendly and most hitter-friendly umpires runs to
about 1.5 runs a game.

### WNBA spreads

| # | Check | Where | Worth | Basis |
|---|---|---|---|---|
| 1 | **Star out / questionable** | team injury reports, beat writers | 2–5 points for a star; a documented single case is Collier at ~3.4 | documented |
| 2 | **Rotation player out** | same | ~1–1.5 points | *provisional* |
| 3 | **Back-to-back / travel** | schedule | ~1.5 points to the rested side | *provisional* |
| 4 | **Line movement since open** | you | Subtract from 1–3 | — |

The WNBA is where the better chance is, and not because the model is smarter.
It is a thinner market — fewer bettors, fewer models, softer opening numbers —
and a twelve-deep roster means one absence is a far larger share of the team
than in any other league. A star sitting is worth several points of spread,
which is an order of magnitude more than anything available on an MLB total.

## The gates

Every candidate has to survive all four (`totals/gameday.py`):

1. **Fresh** — evidence dated to game day. Yesterday's note is a guess.
2. **Grounded** — at least one `documented` item. Provisional coefficients
   alone get logged as a hypothesis, never backed.
3. **Unpriced** — net edge after subtracting line movement must clear
   **0.45 runs** (MLB) or **1.2 points** (WNBA). `BET` needs 0.90 / 2.60.
4. **Uncontradicted** — no documented item pointing the other way. With no
   validated weights there is no honest way to net two real signals that
   disagree, so the answer is stand down.

## How this gets judged

**Closing line value, not win–loss.** At 116 games a true 55% and a true 50%
are statistically indistinguishable — one sigma is about nine percentage
points. Whether the number moved toward the side I took converges in tens of
bets instead of hundreds. Beating the close on better than ~55% is the signal
that something real is underneath.

So every call gets logged with the number I took and the number it closed at.
If after fifty calls I am not beating the close, this playbook is wrong too and
I will say so rather than wait for the win–loss column to bail me out.

## What I will not do

- Produce a pick because a slate deserves one. Most nights the honest output is
  a list of passes.
- Quote a probability I cannot ground. Magnitudes convert through the observed
  dispersion (4.39 runs, 11 points) and nothing else.
- Present a provisional coefficient as though it were measured. Items 4–5 in
  MLB and 2–3 in WNBA are placeholders sized by reasoning and are labelled
  every time they appear.
