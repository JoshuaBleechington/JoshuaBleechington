# Call Sheet — the forecaster

Built 2026-08-25, from scratch, to answer a different question than everything
before it.

The gate models (`totals/gameday.py`, `totals/late.py`) asked **"should I
bet?"** and their most common answer was no. That was the right answer to that
question and it made them close to useless as a nightly tool.

This one asks **"which side is more likely, and by how much?"** It names OVER or
UNDER on every card and attaches a probability. There is no PASS.

## The architecture

Every source produces its own **estimate of the final total**, in the units of
the market. The market's own number is one of those estimates and carries the
largest single weight, because measuring it is the one thing this project has
actually done: over 116 logged games the posted line beat a fourteen-input
statistical model on mean absolute error, 3.58 to 3.61.

```
projected = Σ(wᵢ · eᵢ) / Σ(wᵢ)     ← blended estimates
          + Σ(deltas)               ← tonight-only physical factors
P(over)   = Φ((projected − line) / dispersion)
```

Wind and temperature are **deltas**, not estimates. Wind is not an opinion
about how many runs these clubs score; it is an adjustment to whatever number
the opinions land on. Blending it as though it were an estimate is a category
error.

### Two things fall out of that shape

**Missing inputs re-weight themselves.** No head-to-head means the h2h term is
absent from both sums and the surviving weights renormalise. The model does not
stall, does not guess, and does not need a special case — it just becomes a
blend of what is there. This is what "restructure its weight" means, and it is
structural rather than bolted on.

**No coefficient caps are needed.** A weighted mean cannot run away: a signal
screaming 11.7 into a line of 7.5 pulls the blend by its share of the weight
and no further. Every earlier model needed caps because it *summed*
adjustments, and a sum has no ceiling. Averaging has one built in. The only
guards left are typo guards.

There is a test for this — doubling every weight must not change a single
forecast. If it ever does, the blend has stopped being a weighted mean and has
started summing, which is the shape that produced the runaway numbers.

## Weights

| | market | starters | form | h2h |
|---|---|---|---|---|
| **MLB F5** | 3.0 | 2.0 | 1.0 | 0.6 |
| **WNBA** | 3.0 | — | 1.6 (last 10) | 1.0 |

Form and head-to-head both measured null against the residual on the 116-game
log — **t = −0.07** and **t = −0.40**. They are weighted to move a close card,
not to overturn the market and the starters together.

### Head to head is discounted for sample size

An average of one meeting is not the same evidence as an average of eight, and
taking both at full weight is how a single result ends up holding 9% of a
forecast. The h2h weight scales by `meetings / 4`:

| meetings | share of its weight |
|---|---|
| 1 | 25% |
| 2 | 50% |
| 3 | 75% |
| 4+ | 100% |

The old gate model *refused* to read a head-to-head under three meetings.
Refusing is the wrong instinct for something that has to answer every card —
one meeting **is** information, just a quarter as much of it. So enter it and
let the model discount it; judging the sample size is the model's job.

The WNBA weights are reasoned, not fitted. There are 13 logged WNBA totals,
which is not enough to have tuned anything. They are written down so they can be
argued with.

## Why first five innings

This is the part worth taking seriously. F5 is not a smaller version of the full
game, it is a **cleaner** one:

- **The bullpen is gone.** Relief usage is the least predictable component of a
  baseball game and it decides a large share of full-game totals.
- **Blowout effects are gone** — position players pitching, benches emptied, a
  closer sitting because it is 11-2.
- **Extra innings and the ghost runner are gone.**
- What is left is dominated by the two starting pitchers: the most predictable
  inputs in the sport, and known hours ahead.

So the noise being forecast against is genuinely smaller. Dispersion is derived
rather than guessed — F5 carries 53.6% of a game's runs, and run totals behave
close enough to Poisson that sd scales with the square root of the mean:

```
σ_F5 = 4.39 × √0.536 = 3.21
```

Half-run F5 lines also cannot push. 4.5 always resolves.

### The pitcher calibration

A league-average 4.30 ERA implies 2.58 runs over five innings once unearned runs
are added, so two average starters imply **5.16** — half a run above the **4.66**
that F5 games actually average.

The gap is real and has two causes: a starter's ERA is spread over innings that
include the third time through the order, which mostly happens after the fifth;
and starts that collapse early hand F5 innings to the bullpen. Rather than
pretend otherwise, the estimate is calibrated by 4.66/5.16 = **0.903** so that
two average starters project the league average exactly. There is a test
asserting it.

Each starter is also scaled by the opposing lineup's runs per game when it is
given. ERA alone cannot tell a 5.10 offence from a 3.60 one.

## The park

Park factor scales the **statistical** estimates and the wind, and never the
market anchor. The posted number already holds the park; counting it twice is
the double count that put the fourteen-input model behind the naked line.
Anything outside 70–130 is read as a typo and ignored.

## Bands

| P(side) | band | colour |
|---|---|---|
| 62%+ | MAX | deep green |
| 57–62% | STRONG | green |
| 53–57% | LEAN | green |
| 50–53% | COIN FLIP | grey |

Green means confident and nothing else. Over and under keep their own
directional colours so a large under never reads as a green light.

COIN FLIP is **not** a refusal. The side is still named and still printed — the
band just says the honest thing about how thin it is.

## What this gives up

CLV. The gate models judged themselves on closing line value because it
converges in tens of bets rather than hundreds. This one is asked to forecast
likely outcomes instead, which is a harder thing to be right about and a slower
thing to verify.

That is a deliberate trade and it was made on request. It is worth writing down
that at 50 games a true 55% and a true 50% are still hard to tell apart, so the
first real read on whether this works will take a while. Logging the card is
what makes that read possible later, which is why the page keeps one.

## Verification

- `tests/test_forecast.py` — 38 tests. Always answers, re-weighting,
  market anchoring, the bounded blend, the calibration, and the probabilities.
- `web/forecast-cases.json` — 27 games generated from the package.
- `tools_check_forecast_page.js` — replays all 27 through the page in a real
  browser and checks side, band, probability to 1e-4, projection to 1e-6,
  estimate and delta counts, and that green appears only when confident. It
  also round-trips the card: store a game, clear the form, click the row, and
  assert the inputs and the sport come back.

The page exposes full-precision values in `data-p-over` and `data-projected`
because the panel rounds to a tenth of a percent, and a verifier comparing a
rounded display against the package would be testing the formatter rather than
the model.
