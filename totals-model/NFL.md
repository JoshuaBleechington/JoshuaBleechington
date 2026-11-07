# NFL spreads

## Why the spread and not the total

The MLB model's best feature is that it models a **discrete** distribution and
so gets P(push) exactly, where a continuous model silently hands that
probability to the two sides. NFL margins are far more violently discrete than
baseball run totals, and the effect is several times larger.

The multipliers below are **fitted**, not chosen: each is the ratio of the
published frequency for that margin to what a smooth curve of the same width
gives. The resulting distribution reproduces the documented figures to within
0.03 of a percentage point, and a test pins that.

| margin | published | modelled | multiplier |
|---|---|---|---|
| 1 | 2.9% | 2.91% | 0.52 |
| **3** | **9.5%** | **9.48%** | **1.73** |
| 4 | 4.0% | 3.99% | 0.74 |
| 6 | 4.5% | 4.48% | 0.87 |
| **7** | **6.5%** | **6.49%** | **1.30** |
| 10 | 4.5% | 4.47% | 1.01 |
| 14 | 3.5% | 3.50% | 0.99 |
| 17 | 2.5% | 2.50% | 0.88 |

**The fit contradicts the folklore.** Four and six are *not* key numbers — they
come in at 0.74 and 0.87, meaning they are **rarer** than a smooth curve
predicts, because three and seven take the mass. Only 3, 7 and 10 are genuinely
over-represented. Totals have nothing remotely comparable.

## What this model actually claims

**It will not reliably beat the closing NFL spread.** That market is the most
efficiently priced in sports, and seventeen games a week will never accumulate
the sample to demonstrate an edge over it — the MLB log already showed that
proving a two-point edge takes roughly 4,900 settled bets.

What it does claim is narrower and checkable: **it prices the half point.** That
is arithmetic on the margin distribution, not an opinion about who wins, and you
can verify it game by game against what a book is charging.

### The headline finding

With the projection sitting on the line, no half point on the board is worth the
flat 20–25 cents books charge for it:

```
line     to      push out    fair
-3      -2.5       5.2%      11.5c     the best one on the board
-3.5    -3         0.0%      12.2c
-7      -6.5       3.9%       8.4c
-10     -9.5       3.0%       6.4c
-2      -1.5       3.0%       6.7c
```

So: **never buy a half point at 20 cents.** Use the number to shop books
instead — take a better line whenever it costs *less* than the fair value shown.
A test pins the claim that the best case stays under 20.

### And a line is not an expected margin

An even market on −3 implies a true margin of **+2.38**, not 3. Home covering −3
needs a margin of 4, which the fit says is *rarer* than a smooth curve predicts,
while the mirror numbers 3 and 7 on the away side are boosted. The same
arithmetic reproduces the best-known asymmetry in the sport from first
principles: −2.5 is worth most of a full point of margin over −3, because at
−2.5 the single most common outcome in football covers for you instead of
pushing.

## Inputs, and what is deliberately missing

| input | weight | note |
|---|---|---|
| Spread + both prices | 4.0 | de-vigged and inverted through the distribution |
| Net points per game | 1.2 | differential; earns full weight at 8 games |
| Starting QB out | **0** | shown, never scored |

**Games played is not optional.** A net-points rating after one game is one game
of noise, so it earns `games / 8` of its weight. In week 2 the model will barely
move, which is the honest answer rather than a gap.

**The quarterback is deliberately unscored.** He is worth roughly 5 points and an
NFL line moves three to seven on the announcement, so the news is already inside
the number being read. Counting it again would double it. Tick the box and use
it as a *check*: if a starter is out and the line has not moved, the market does
not believe the report.

No weather. Wind suppresses both offences roughly equally, so it belongs in a
totals model, not a spread one — and inventing a coefficient for it is exactly
what this project keeps removing.

## Verification

- `tests/test_nfl.py` — 36 tests. The distribution against published
  frequencies, neutrality to six decimal places, pushes only on whole numbers,
  the sample-size discipline, the quarterback provably unscored, and the
  cents scale not exploding across the century.
- `web/nfl-cases.json` — 16 cases generated from the package by
  `tools_gen_nfl_cases.py`.
- `tools_check_nfl_page.js` — replays all 16 in a real browser against side,
  band, resolved probability, push, location, fair price and the half-point
  quote to the cent, then grades five stored rows to check an NFL row settles on
  **margin** rather than on a total.

### Two bugs the tests caught

**The bisection searched the wrong side of zero.** The candidate is a margin, so
it lives near `-spread`, not near `spread`. Bracketing around the spread put the
root outside the range on every home favourite and an empty card on −7 came back
AWAY 69%.

**Cents exploded across the century.** American odds jump from +100 to −100 for
the same bet, so subtracting them directly reported a ten-cent move as two
hundred. `_price_index` maps the ladder onto a continuous scale.

## What happened to WNBA

The live WNBA totals model is **deleted**, not archived — dead code with passing
tests is the thing that rots. `forecast_wnba`, its constants, its nine tests and
its eight browser fixtures are all gone, and its slot on the page is now NFL.

One file survives: `totals/wnba.py`, which belongs to the **retired gate models**
(`gameday.py`, `late.py`, `confidence.py`, `spread.py`) and is imported by
`spread.py`. Those answer a different question — "should I bet?" rather than
"what is the number?" — and were already documented as retired in `GAMEDAY.md`.
Deleting it would break them for no gain.

## Kept separate from MLB on purpose

`assembleNfl()` in the page and `totals/nfl.py` in the package share no code path
with the MLB model beyond the calibration panel. One model going wrong must not
take the other with it, and the two browser checkers are separate so a failure
names the right one.
