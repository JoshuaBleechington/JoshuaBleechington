# Call Sheet — the full-game model

Built 2026-09-02, replacing the first-five forecaster. It names OVER or UNDER on
every card with a probability, models the push, reads the prices, and grades
itself once the games land.

## What went wrong in the version before it

Three failures, each a class of error rather than a typo. They are written down
because the fix in every case was a change of *shape*, not a better constant.

### 1. The calibration anchor was a number I picked

The F5 pitcher estimate was scaled so two league-average starters projected
4.66 runs — 53.6% of an 8.70 full-game average, and I chose both of those.
Books post 4.5 for an average first five, so **every projection carried +0.16
runs toward the over before a single input was read.** A game with no
information came back OVER 50.8%.

That bias is why four of four calls on 2026-08-31 were overs. It does not
explain a 4.25-run miss at Coors, and I am not claiming it does.

**The fix is a shape that cannot hold the bug.** Every statistical estimate is
now a **differential** against the market's fair total. Two league-average
starters move it by exactly zero; league-average everything returns exactly
50.0%. That is arithmetic, not a calibration that came out right, and there are
tests at eight decimal places.

It also makes the unverifiable league constants cheap to be wrong about. A 0.20
error in league ERA now moves a projection **0.07 runs**. `sensitivity()`
prints the damage and a test pins it under 0.10.

### 2. The normal distribution cannot push

F5 lines are halves, so it never came up. Full-game totals are frequently whole
numbers — 8 and 9 were both on the last board — and a game landing on exactly 8
against a line of 8 is a **push**, not a loss. Treating runs as continuous
silently redistributed that mass onto the two sides and overstated both.

Runs are counts and combined totals are overdispersed relative to Poisson, so
this uses a **negative binomial** with `phi = variance/mean = 4.39² / 9.04 =
2.13`, derived rather than picked. It gives an exact P(push) — about **9% on a
whole number** — and it captures the right skew a normal misses. Fifteen-run
games happen; minus-two-run games do not.

That skew matters beyond the push: **a posted line is the point that splits the
two sides evenly, not the average.** The mean of an MLB total sits about half a
run above it. Treating the line as a mean made an empty card come back UNDER
55.1%.

### 3. The prices were thrown away

A posted total is rounded to the half run. The prices are not. Over −120 with
the under at +100 is the book saying fair sits well north of the number it
posted, and de-vigging the pair and inverting through the distribution recovers
it to a hundredth of a run. The old model read the line and ignored the two
most informative numbers on the board.

## Two more found while building it

**Prices are quoted on the resolved outcome.** A book at −110/−110 on a total of
8 says the sides are even *given it resolves*, not that P(over) is 50% outright.
Matching the unconditional probability made an empty card on a whole number
come back over 50.0 / under 40.5 — a lean the market never expressed.

**The band has to read the resolved probability too.** On a total of 8 with a
9.6% push, a 47.2% over is a **52.2% bet**. Reading the raw figure called that a
coin flip and it is not one.

## A wide market is a less certain one

Added 2026-09-04, from a real card. A total entered at 8.5 when the main number
had moved to 9 picked up an **alternate-line** quote of −150/−110 — a **12.4%
hold** where every other game that night sat at 2.4–4.8%. De-vigging that
proportionally read 53.4% over and pushed the card from LEAN to STRONG on what
was mostly markup rather than opinion.

Proportional de-vig assumes the margin splits between the two sides in
proportion to their probabilities. That is harmless at a 5% hold and
increasingly arbitrary at 12%. So the de-vigged deviation from even is now
shrunk by how far the hold exceeds a normal main-line one:

```
confidence = min(1, 5% / hold)
p_over     = 0.5 + (p_devig − 0.5) × confidence
```

| quote | hold | keep | raw | shrunk |
|---|---|---|---|---|
| −110/−110 | 4.8% | 100% | 50.0% | 50.0% |
| −120/+100 | 4.6% | 100% | 52.2% | 52.2% |
| **−150/−110** | **12.4%** | **40%** | **53.4%** | **51.4%** |
| −180/+140 | 6.0% | 84% | 60.7% | 59.0% |

It never flips a side, never crosses even, and leaves a symmetric quote exactly
even at any hold — so the neutrality property survives untouched. Across the
eighteen games logged to that date, **one changed, by 1.6 points.**

The estimate also says out loud when it thinks it is looking at an alternate
line, and tells you to enter the main number instead.

### Shin's method was tried first and rejected

Shin corrects favourite–longshot bias, and it moves the favourite **up**:
−150/−110 reads **53.8%** under Shin against 53.4% proportional. That is a real
effect and the wrong one here — it would have made the alternate line *more*
confident, not less, and it adds confidence across the board that an 18-game
record cannot justify. There is a test pinning the direction so it does not get
re-added on the theory that it fixes this.

## Architecture

```
anchor    = fair total, solved from the two prices through the distribution
estimates = anchor + differential   (starters, bullpens)
          | absolute total          (last 10, head to head)
projected = Σ(wᵢ·eᵢ)/Σ(wᵢ) + Σ(deltas)      ← wind, temperature, splits
(over, push, under) = NegBin(projected, phi) split at the line
```

| | market | starters | bullpens | form | h2h |
|---|---|---|---|---|---|
| **MLB** | 4.0 | 1.6 | 0.8 | 0.8 | 0.5 |
| **WNBA** | 3.0 | — | — | 1.6 | 1.0 |

The market carries the largest weight because it is the one thing this project
has measured: over 116 logged games the posted line beat a fourteen-input model
on mean absolute error, 3.58 to 3.61.

**Missing inputs re-weight themselves** — a term absent from both sums leaves the
survivors renormalised. **No caps are needed**: a weighted mean is bounded by its
own inputs, where the summed-adjustment models it replaced were not. A test
asserts that tripling every weight changes no forecast.

Head to head is discounted by `meetings / 4`, so one meeting counts a quarter.
Enter it anyway — judging the sample is the model's job.

## What is deliberately not here

**Line movement as a term.** The gate model subtracted it, correctly, because it
scored news against the number. Here the current line *is* the anchor, so a move
is already inside it and subtracting it again would double-count. It is
displayed, never scored.

**Park factor on the market anchor.** The posted number already holds the park.
It scales the differentials and the wind and nothing else.

## Does it work

`calibration()` and the page's **Is it working** panel answer the only question
that matters: does a 60% call win 60% of the time? A model can name the right
side more often than not and still be useless if its confidence is fiction,
because the confidence is what sizes the bet.

Pushes are excluded rather than counted either way — they refund, and folding
one into either column corrupts the measure. Brier, log loss, bucketed
said-vs-did, and a verdict that says plainly when the thing is miscalibrated or
below the 0.25 a coin flip scores.

Under 50 graded calls it refuses to judge and says so.

## The league constants

`LEAGUE_COMBINED_RPG = 9.04`, `LEAGUE_STARTER_ERA = 4.16`,
`LEAGUE_BULLPEN_ERA = 4.05`, `STARTER_INNINGS = 5.4`.

**These come from a web search summary and could not be verified.**
Baseball-Reference, FanGraphs, ESPN, StatMuse and TeamRankings all refuse the
connection from this sandbox, and that search layer has already been caught in
this project returning team assignments backwards. They are quarantined in one
block, dated, and the differential architecture is what keeps an error in them
cheap. To update, change those four numbers and nothing else.

## Verification

- `tests/test_fullgame.py` — 58 tests. Neutrality to nine decimal places, the
  distribution's mean and spread against the measured 4.39, push arithmetic,
  price inversion, the resolved-probability band, calibration detection of an
  overconfident model, and the guards.
- `web/fullgame-cases.json` — 36 games generated from the package by
  `tools_gen_fullgame_cases.py`, which recomputes only the expectations so a
  model change never means hand-editing a probability.
- `tools_check_fullgame_page.js` — replays all 36 in a real browser against side,
  band, resolved probability, push, projection, fair price, estimate and delta
  counts, and that green appears only when confident. Then it stores a game,
  grades it a loss, grades a second as a push, checks the push is excluded from
  calibration, reloads the browser and asserts the card, the grades and the
  half-typed draft all survive. Last it checks the roof marker: a domed game is
  tagged, an open-air one is not, and a basketball row does not inherit a
  left-over tick from the ballgame before it.

The browser needed a **full-precision erf** for this to pass. The Abramowitz &
Stegun approximation that had been in every page in this project is good to
1.5e-7, which was enough to flip the side on a dead-even WNBA card and to move
the fair-total bisection by 4e-5. An approximation good enough to display is not
good enough to invert.

## Retired

`totals/forecast.py` and its page are deleted, not archived — dead code with
passing tests is the thing that rots. The gate models (`gameday.py`, `late.py`,
`confidence.py`, `spread.py`) stay: they answer a different question ("should I
bet?") and are documented as retired in `GAMEDAY.md`.
