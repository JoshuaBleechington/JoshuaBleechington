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

## A measured-null input cannot buy a band

Detroit at Cleveland, 4 September. Head to head at 6.4 over nine meetings, plus
a public-money flag, dragged a card into an UNDER **LEAN** — against the price,
and against a market-plus-arms read that said OVER. It went twelve runs.

Twelve was a 19.6% outcome, so the loss proves nothing. The reasoning was the
problem: **the two loudest voices on that card were the two the model itself
documents as worth nothing.**

```
Market            8.74   w 4.00        remove H2H     -1.6 pts
Bullpens          8.60   w 0.80        remove split   -3.2 pts
Last 10           8.77   w 0.80        ------------------------
Starters          7.99   w 1.60        market + arms only: OVER 50.5%
Head to head (9)  6.27   w 0.50        full blend:        UNDER 54.0%
```

So the band is now cut from the **less confident of two reads**: the full blend,
and the same blend with `mechanism=False` inputs deleted. If deleting them
changes the side, the band is held at COIN FLIP.

**This paragraph is out of date and is kept as written for the history.** At the
time, three MLB inputs were tagged: form and head to head, because they measured
null against the residual on 116 games (t = −0.07 and t = −0.40) and are
absolutes rather than differentials; and the money split, because its
coefficient was a flat hand-capped 0.30 — the direction documented, the size not.

Since then the **starters** were tagged too, on the same a-priori rule (below),
and the **money split is no longer scored at all**, so it can no longer be soft —
there is nothing left of it to tag. The current set is starters, form and head to
head. Note what that does to the Detroit card that motivated this whole section:
without the split it no longer reaches a bet on either read, so the gate has
nothing left to do there.

**The headline probability is untouched.** The gate governs the band only. The
probability is the best estimate of what happens; the band is the
recommendation. Moving the first to justify the second would corrupt the
calibration measure, which reads the probability.

Across the 33 logged cards it moves 9, and all four STRONGs become LEAN:

| | before | after |
|---|---|---|
| STRONG | 4-0 | — |
| LEAN | 4-2 | 8-0 |
| COIN FLIP | 4-4 | 4-6 |

**That 8-0 is not evidence and must not be read as any.** The rule was written
after looking at which of these games lost, on eighteen settled calls. The
justification is the a-priori one — measured t-statistics and a hand-capped
coefficient — and nothing else. The table is here to show the blast radius, not
to argue the rule works.

### Not applied outside MLB

Those t-statistics come from an MLB residual study. No equivalent exists for any
other book here. Demoting an input on evidence is discipline; demoting one on a
hunch is exactly the unjustified coefficient this model exists to remove, so
nothing outside MLB is tagged.

The WNBA model has been deleted outright rather than archived — dead code with
passing tests is the thing that rots. Its slot on the page is now **NFL
spreads**; see `NFL.md`.

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

## No constant may cite a measurement it does not re-take

Added 2026-09-17, after an outside audit of this model. That audit made five
claims. Two it retracted itself, one does not survive checking, and two are
real. All five are written down because which ones failed is the useful part.

### Retracted by the auditor, correctly

**"Side selection writes UNDER on picks whose projection says OVER."** It reads
the side from the probability split, which is right. With `phi = 2.13` the run
distribution is right-skewed, so the mean sits about half a run above the
median, and a projection of 7.93 on a 7.5 line genuinely is UNDER 51.1%. A mean
above the line does not imply the over.

**"The de-vig is broken."** Misread screenshots. `fairTotal` was correct.

### Does not survive checking

**"Overs and unders are miscalibrated in opposite directions, so one constant
averages two errors."** The numbers replicate almost exactly — over calls say
56.14% and do 62.82%; under calls say 53.62% and do 37.50%, a 22.8-point split
at z = +2.17. The diagnosis is still wrong. Games in this window went over
**62.7%**, and:

| side | n | model hits | blind ticket | model edge |
|---|---|---|---|---|
| OVER | 78 | 62.8% | 62.7% | **+0.1** |
| UNDER | 32 | 37.5% | 37.3% | **+0.2** |

Both sides land within a fifth of a point of their blind-ticket rate. The split
is the window running over, not a defect in the model. Correcting it would have
fitted a hot fortnight, which is the exact failure this project exists to avoid.

**"`RESIDUAL_SD = 4.39` is too high."** Measured over 112 settled games it is
**3.90**, 95% interval **3.44 to 4.49** — 4.39 is inside. The push rate fits too:
33 whole-number lines predicted 3.1 pushes against 2 observed, −0.7 sigma. Not
established, so the constant does not move.

### Real, and fixed

The auditor was right about something more general than the number it was
aiming at. `OVERCONFIDENCE = 3.0` sat in the page under this comment:

> *Measured, not chosen: across the logged card the model has said 54.2% and
> done 51.1%.*

That was true when written. At 110 graded calls the model says **55.41%** and
does **55.45%** — a gap of **+0.05**. The constant was frozen; the measurement
it cited had moved. **A number labelled "measured" is the one nobody goes back
to re-check**, which makes it more dangerous than an honest guess.

It is now computed, from two parts that are both real:

```
guard = max(0, says - does)  +  sqrt(p(1-p)/n)
        \___ measured bias __/   \___ its standard error ___/
```

Running *under*confident is floored at zero — beating your stated number does
not buy a thinner bet. And a gap you cannot tell from zero is not a gap, so the
standard error is added rather than ignored. At 110 graded calls that is **4.7
points**, wider than the 3.0 it replaces, because 3.0 was pretending to know
something. It tightens on its own: 3.5 at 200 calls, 2.5 at 400, 1.6 at 1000.
There is no constant left to go stale.

`RESIDUAL_SD` gets the same treatment in the opposite direction: the calibration
panel now prints the live measured spread of (final − line) with its confidence
interval, against the constant in use, and says plainly when the constant falls
outside it. It **reports and never refits** — re-fitting a dispersion parameter
to each fortnight's residuals is how a model ends up chasing its own noise — and
a test pins that `RESIDUAL_SD` is still 4.39 after being handed a sample far
tighter than it.

Neither change touches the forecast. All 33 fixtures regenerate byte-identical.

## The team box is a controlled list

Added 2026-09-16, after a question about which teams tend to go over turned up
something else first: across 67 logged games the free-text team field had
produced **fifty spellings of thirty clubs**. St Louis alone appeared as
`St Louis Cardinals`, `St Louis`, `ST louis Cardinals`, `Cardinals` and
`St Louis Cardninals` — plus `Cleveland Gaurdians`, `Houston Astro`,
`Boston RedSox`, `Cincinnati Red`, and several pairs differing only by a
trailing space.

This is not cosmetic. Splitting a sample manufactures results: unmerged, **27 of
those 50 names carried a flawless over or under record**, and coin flips at the
same sample sizes predict 26.4. Any breakdown by team, park, or division was
reading fragmentation as signal.

The fix is a datalist of the thirty MLB (or thirty-two NFL) clubs plus an
ordered first-hit-wins matcher. Three properties matter and each has a test:

- **Ordered, because patterns overlap.** `Red Sox` is tested before `Reds` or
  the word `red` captures it. Same for `White Sox`.
- **Scoped by sport, not global.** `Arizona` is the Diamondbacks in MLB and the
  Cardinals in NFL; `SF` is the Giants or the 49ers. Cardinals and Giants are
  each a club in both leagues.
- **Ambiguous input is left exactly as typed.** `Chicago`, `LA` and `NY` name
  two clubs apiece, and an unknown string comes back unchanged. A wrong merge is
  worse than no merge, and losing what someone typed is worse than both.

Rows logged before this run through a one-time backfill on load. It rewrites the
**name only** — finals, bands, probabilities and grades are untouched, the same
rule the rescore button follows, and four tests pin it.

After merging, the answer to the original question was: 30 teams, 130 graded
appearances, median 4 per club, **nothing survives a Sidak correction** (best is
the Astros at z = −2.30 against a 3.14 threshold). At four appearances the
smallest detectable bias is 70 points. The Rockies' 3-0 has a Wilson interval of
43.8%–100%.

## What is deliberately not here

**Line movement as a term.** The gate model subtracted it, correctly, because it
scored news against the number. Here the current line *is* the anchor, so a move
is already inside it and subtracting it again would double-count. It is
displayed, never scored.

**Park factor on the market anchor.** The posted number already holds the park.
It scales the differentials and the wind and nothing else.

## A blank field does not warn you

Added 2026-09-20, from two rows that sat incomplete through three separate
re-saves while the card looked finished.

`Blue Jays @ Rangers` had both runs/game blank and `Cubs @ Reds` had the away
last-10 blank. Nothing on screen said so. The estimate simply drops out of the
blend and the row renders exactly like a complete one — so the reported
probability rests on less than it appears to, and there is no way to tell.

Two guards, both display-only. Neither can move a probability or a band.

### The missing-input chip

A row now carries a `n missing` chip naming what is absent, and the header
counts the flagged rows. Only fields whose absence actually changes the
forecast are listed:

| group | flagged when |
|---|---|
| prices | **both** are blank — one alone is reconstructed |
| starter ERAs | either is blank; the pair drops as a unit |
| bullpen ERAs | either is blank |
| last-10 totals | either is blank |
| runs/game | either is blank |

Park factor, weather and the public split are genuinely optional and are never
flagged. Run against the real 174-row card it flags exactly four, which is the
correct answer.

### A percentage outside 0-100 is a typo

A logged card carried `money% = 925`, meaning 92.5. The split delta fired at
full strength on it and moved that projection **0.30 runs**. The model now drops
it and says so, the same posture it already takes to an implausible ERA:

> *The money percentage reads 925, which is not a percentage. It has been
> dropped rather than scored — check for a missing decimal point.*

A test pins that 925 now scores bit-identically to the field being empty.

### One assertion of mine was too specific

The dome check asserted `/Dome$/` — the chip anchored to the END of the row
text. That broke the moment a second chip could follow it. The page was right
and the test was over-specific; it now matches the chip itself.

## The money split is shown and never scored

Added 2026-09-20, on the observation that *"the over tickets and money doesn't
seem to matter either."* It doesn't.

It used to move the projection a flat **0.30 runs** whenever tickets and money
on the over were **20 points** apart. Both constants were picked by hand, and
the code's own comment admitted it: *"Capped flat: the direction is documented,
the size is not."*

### What the log says

Residual = final minus the market's own fair mean. A positive gap (more tickets
than money on the over) is supposed to mean big money on the under, so the
residual should come out **negative**. Over 172 settled games:

```
all 161 cards with both percentages   r = +0.0220   t = +0.28
only the 58 where the delta fires     r = +0.0500   t = +0.37
```

Near zero, and the sign is **backwards** — the gap is associated with slightly
*more* runs while the model subtracted them. On the 58 cards that fired, the
delta pointed the right way **27 times, 46.6%**, z = −0.53 against a coin.

It cannot be rescued by moving the threshold. Sweeping it:

```
  5 pts  n=128  right 46.1%   25 pts  n= 34  right 50.0%
 10 pts  n= 99  right 48.5%   30 pts  n= 28  right 46.4%
 15 pts  n= 82  right 46.3%   35 pts  n= 20  right 45.0%
 20 pts  n= 58  right 46.6%   40 pts  n= 14  right 42.9%
```

Not one cut beats a coin. Best |z| over eight thresholds is 0.88 against a Sidak
requirement of 2.73 — and those samples are nested, so that is really one
observation, not eight.

### What the log does NOT say

**It does not prove the split is worthless.** A true 0.30-run edge against a
4.39-run spread is the delta pointing right 52.7% of the time, not 50%. Telling
52.7% from 50% at 95% with 80% power needs about **2,644 firing cards**. There
are 58. The 95% ceiling on 27/58 is 59.4%, which corresponds to an effect of up
to +1.04 runs — that ceiling does not exclude 0.30.

So this is not "measured null" in the way the starters are. It is: *no evidence,
in a test that could only have caught something three times larger than the
constant being claimed.*

### Which is exactly why it goes

The deciding argument is structural, not statistical. Compare the starters: they
are continuous, and their size is **arithmetic** — ERA gap × innings × the
unearned multiplier. Nothing was chosen. They measured null and were demoted to
`mechanism=False`, but kept, because the number they produce is derived.

The split has a hand-picked threshold and a hand-picked magnitude, and no
derivation for either. This model already has a category for exactly that, and
has had from the start: **shown, never scored** — the opening line, and the NFL
quarterback. Both are things worth seeing before you bet with no honest number
to attach. The split belongs there and always did. Putting it there is not a new
rule; it is an existing rule finally applied.

It is still on the page, still entered, and a 20-point gap still prints a note
saying which way the money went — and saying that it was not scored.

### What it cost

```
                    n     says     does    Brier     MAE
with the split     168   54.72%   56.55%   0.24470   2.8090
split deleted      168   54.23%   55.36%   0.24471   2.7944
```

Brier is identical to the fourth decimal. MAE is 0.0146 runs *better* without
it. `does` drops 1.19 points because the side flips on 10 cards, and on those 10
the split's side went 6-4 while the other went 4-6 — a two-card difference on
ten cards, which is nothing.

Band by band:

```
with the split   MAX 0-1 | STRONG 8-1 | BET 29-17 | NO BET 58-54
split deleted    MAX 0-1 | STRONG 9-1 | BET 26-17 | NO BET 58-56
```

**Be honest about this: the deletion is not an improvement.** Every number above
is inside the noise. The case for it is that the model should not carry a
coefficient nobody can derive and nobody can measure, not that removing it makes
better calls.

### It was bigger than it looked

A delta is applied to the projection at **full strength**, after the blend —
unlike an estimate, which gets diluted by its weight. So this "small" input was
worth a straight 0.30 runs, larger than almost anything else on the card. The
Tigers @ Guardians card that motivated the corroboration gate in the first place
moved from 53.97% to 50.78% when it came out, and now falls under the bet floor
on its own. `TestSoftInputsCannotBuyABand` keeps that card for the history and
tests the gate against a live 20 Sept card instead.

### How to undo it

In `totals/fullgame.py` and `web/fullgame.html`, the note that begins *"Over
holds …% of tickets"* was a `Delta`/`delta` call tagged `mechanism=False`. Turn
it back into one and regenerate `web/fullgame-cases.json`. One fixture changes:
the split-only card goes from 1 delta back to 0.

## The banner says how likely, not what to do

Added 2026-09-20, on request: *"I don't like the no bet/bet banner anymore. If
the percentage is high enough on the probability then fine make it green or
something. But I'd rather have the probability percentage and not so much the
details for the fair price and etc. I think the no bets are not helping and I'd
rather make the fine call myself and would rather the model tell the likelihood
of the total."*

The headline is now the resolved probability, at 42px, tinted at the band
floors — plain below 53%, ink at 53%, green at 57%, deep green at 62%. The
words MAX BET / STRONG BET / BET / NO BET no longer appear on the banner. The
card's Prob column is tinted the same way, so the slate reads by colour.

### Nothing about the model changed

Not one number. `readMlb()` and `readNfl()` are untouched; the band is still
computed, still written to `dataset.band`, still stored on every card row, and
the band-by-band record and the calibration panel still run off it. This is
presentation only. Every one of the 375 package tests and 600-odd browser
checks passes unchanged apart from the ones that asserted on the banner's
markup.

That distinction matters more here than usual, because the bands are the only
thing in this project that has ever earned anything:

```
n=168   MAX BET 1-1 | STRONG BET 9-3 (75.0%) | BET 39-28 (58.2%) | NO BET 46-41 (52.9%)
```

Removing the word from the banner does not remove that ordering; it moves the
decision to the reader, which is what was asked for.

### The core read is now the banner's only warning

With the verdict gone, a held card had nothing left to say that it was held.
So the corroborated probability — the same game with the measured-null inputs
(starters, form, head-to-head) deleted — is drawn as a chip beside the pick on
**every** card, not only the gated ones, and turns amber when the two reads
disagree by a whole band.

The case that forced this, from the night the change was asked for:

```
Athletics @ Guardians   6.5   full 58.7%   core 51.0%   final 1 run
```

58.7% in green with nothing beside it would have read as the best card on the
slate. It was the worst. `core 51.0%` in amber is the whole of the warning the
verdict used to carry, and it is now permanent furniture rather than something
that only shows up on a subset of cards.

### The price is a footnote

The three price boxes — Fair price / You get / Edge, each set at 17px, the same
visual weight as the call — collapsed into one muted line:

```
-110 needs 52.4% to break even, so you are +6.3 points above the price.
Fair -142, edge 11.8%.
```

Nothing was dropped. The fair price, the posted price, the edge, the break-even
number, the margin and the margin-guard warning are all still there, in the
order that reads as a sentence, in small grey text under the call. A likelihood
is only worth what the book charges for it, so the price stays; it just stops
competing with the number it qualifies.

### What this cannot fix

It does not make the model better. It makes the model quieter about a decision
it was making on the reader's behalf. If the record gets worse from here — if
cards the gate used to hold start getting bet — that is the cost of the change,
and the band-by-band table is where it will show up. It is still on the page.

## The starters measure null too

Added 2026-09-20, after being asked to find whichever version of this model was
the most accurate and go back to it. The honest answer is that there isn't one.

### Accuracy has never changed

Every version of the model, scored on the same 160 logged cards:

| version | says | does | Brier | record | units |
|---|---|---|---|---|---|
| 02 Sep — the full-game rebuild | 55.11% | 55.26% | 0.2449 | 57-43 | +1.38u |
| 04 Sep — + wide-market pullback | 54.82% | 54.61% | 0.2457 | 55-42 | +0.98u |
| 04 Sep — + the corroboration gate | 54.82% | 54.61% | 0.2457 | 44-33 | +1.06u |
| 07 Sep | 54.82% | 54.61% | 0.2457 | 44-33 | +1.06u |
| 18 Sep | 54.83% | 54.61% | 0.2456 | 44-33 | +1.06u |
| **20 Sep — starters tagged** | 54.79% | 54.61% | 0.2451 | **33-17** | **+7.29u** |

**The entire Brier range across the model's life is 0.2449 to 0.2457.** 112 of
160 cards are bit-identical from the first build to today, and the largest any
card has ever moved is 2.38 points. The forecast has never improved and has
never degraded.

**Every gain has come from betting less.** The gate cut 23 bets; this cuts 27
more. The decision rule is the only lever that has ever moved anything, which
is worth knowing before reaching for the weights again.

### Why the starters were demoted

Three independent measurements, none of them a sweep:

- **Correlation with the market's error**, the same test that tagged form and
  head to head: `r = -0.076, t = -0.95` on 156 settled games — null, and the
  **sign points backwards**. Form was tagged at t = -0.07, head to head at
  t = -0.40. Starters fails harder than either.
- **Mean absolute error against the final**: 3.157, the worst of any real input
  (market 2.803, bullpens 2.813, form 2.850).
- **The blend is worse than its own anchor**: the full projection scores 2.868
  against the market anchor's 2.803. Everything the model adds on top of the
  market makes it less accurate.

Leaving it untagged was the inconsistency. It keeps its 1.6 weight and still
moves every projection — it simply may no longer buy a band alone.

### What the backtest is, and is not

Tagging gains **+2.46u** across the log. That is not the justification and must
not be read as one. The 29 bets it stops taking went **14-15 (48.3%)** against a
claimed 56.2% — `z = -0.85`, indistinguishable from noise — and it was chosen
after fourteen configurations had been tried against the same games, where
Sidak needs |z| > 2.88.

What makes the dropped basket worth dropping is not that it lost. It is that a
coin flip at prices needing **53.2%** is a losing basket by arithmetic.

### It cannot corrupt the record

The gate governs the band and never the probability, so **all 160 probabilities
are unchanged to twelve decimals** and the calibration history carries across
the change unbroken. A test pins that.

### How to undo it

If a re-measure at 400+ games finds a real positive correlation between the
starter differential and the market's error, take the tag off. At n=156 the
smallest detectable |r| is 0.160 and the observed is 0.076, so this is a
demotion on the evidence available, not a verdict.

## One price is not no price

Added 2026-09-17, from a real card: Brewers at Pirates, over **−120**, under box
left empty. The model reported OVER 51.3%.

`fair_total` required *both* prices to de-vig. With one side missing it fell
back to "assume −110/−110" and **threw the price away entirely** — so the input
carrying weight 4.0, the heaviest thing in the blend, went in blind. A −120 over
is the book saying fair sits north of the posted number, and that survives
perfectly well without its partner.

### The missing side is reconstructed, not invented

Assume the book charged its usual margin, and solve for the other price. Both
constants are **measured across 133 priced cards in the logged book**, not
chosen:

| 5th | 25th | median | 75th | 90th | 95th |
|---|---|---|---|---|---|
| 4.34% | 4.62% | **4.71%** | 6.44% | **6.80%** | 7.11% |

The point estimate uses the **median**. The confidence is cut against the **90th
percentile**, because a reconstructed quote is a less certain thing than a real
one and must not inherit the same authority. That is the same posture as the
corroboration gate: when two readings are available, act on the less confident.

A lone −120 over therefore reads 51.5% rather than the 52.1% a real 4.71%-hold
pair would have given, and the card says so in full:

> *Only one price was given, so the other side was reconstructed at the 4.7%
> hold this book typically charges… Because the hold here is assumed rather than
> observed, the confidence is cut against the 6.8% this book charges at its 90th
> percentile, so only 74% of the 52.1% read is kept. Enter both prices and none
> of this guesswork is needed.*

### The ablation, which is the real test

Hide one side of all 133 two-priced cards, rebuild it, and compare against the
answer the full quote actually gives:

| | mean projection error | wrong side | wrong band |
|---|---|---|---|
| price discarded (old) | 0.209 runs | 14 | 43 |
| **reconstructed, under hidden** | **0.056 runs** | **4** | **14** |
| **reconstructed, over hidden** | **0.046 runs** | **4** | **13** |

**73–78% closer**, and **122 of 133 cards improve** against 11 that get worse
(z = 9.6). Graded against the real finals on 122 settled cards, Brier goes
0.2478 → 0.2442, against 0.2448 for the true two-priced answer — it lands on
the truth rather than merely nearer it.

### Guards

It fires **only** when exactly one price is present. Both prices, or neither,
behave exactly as before — all 33 pre-existing fixtures regenerate
byte-identical. A quote so lopsided that the usual margin cannot cover it
(roughly +1650 or longer) falls back rather than inventing a price on the far
side of certainty.

One test expectation of mine was wrong and the suite caught it: I asserted a
lone −140 over and a lone −140 under move the anchor by the same number of runs.
They do not, and should not — the reconstruction is exactly symmetric in
*probability*, but the run distribution is right-skewed, so the map from
probability to mean is not linear. The test now pins the property that is
actually true.

The card that prompted this goes from OVER 51.3% to **OVER 52.6%**, and is still
NO BET: −120 demands 54.55%, so the margin is −1.96 points either way.

## A starter's ERA is a measurement, not a reading

Added 2026-09-16, **off by default**, and the backtest below does not prove it
works. Read the whole section before turning it on.

### The problem is real and is pure arithmetic

Until this change, `arm_differential` took whatever ERA it was handed at face
value. A September call-up's 5.24 in 22 innings carried exactly the authority of
an ace's 5.24 in 190. That is plainly wrong, and the size of the error is not
debatable:

```
Liberatore  5.53 on 143.1 IP   1 SD = 0.68    68% band  4.85 - 6.21
Molina      5.24 on  22.1 IP   1 SD = 1.72    68% band  3.52 - 6.96
```

Measurement sd of an ERA over `n` innings is `sqrt(9 * overdispersion * ERA / n)`.
At 22 innings that is 1.72 — the number could honestly be anywhere from a good
starter to an unplayable one, and the model was reading it to two decimals.

### The correction, and why its constant is not a dial

Empirical Bayes, league mean as the prior:

```
weight on the observation = n / (n + ERA_STABLE_AT)
ERA_STABLE_AT = 9 * ERA_OVERDISPERSION * LEAGUE_STARTER_ERA / STARTER_TALENT_SD^2
              = 9 * 1.75 * 4.16 / 0.85^2
              = 90.7 innings
```

Both inputs are derived. `ERA_OVERDISPERSION = 1.75` is the same clustering
factor used elsewhere here. `STARTER_TALENT_SD = 0.85` comes from subtracting
variances: qualified starters' ERAs are spread about 1.05, of which 0.60 is
measurement noise at a full season's innings, and `sqrt(1.05^2 - 0.60^2) = 0.86`.

`ERA_STABLE_AT` is therefore **computed, and a test fails if anyone edits it by
hand** — which is exactly the sort of quiet backtest-tuning this project exists
to prevent.

A call-up at 22 IP keeps 20% of his own number. A starter at 143 IP keeps 61%.
Nobody keeps 100%, which is correct: a season is a sample.

### What the backtest actually said

67 logged games, 65 gradeable. No innings are recorded in the log, so the real
feature **cannot be tested directly**. What was tested is the direction it
pushes, by shrinking both starters globally and sweeping the weight:

| keep | says | does | Brier |
|---|---|---|---|
| 100% (today) | 54.41% | 49.23% | 0.2500 |
| 61% | 53.81% | 52.31% | 0.2470 |
| 20% | 53.33% | 53.85% | 0.2440 |
| 0% | 53.19% | 56.92% | 0.2427 |

Brier improves monotonically. It is tempting to call that a win. It is not:

1. **The best score is at keep-0%.** That is the instruction *delete the starter
   input*, not *shrink it by sample size*. A test that cannot separate those two
   has not validated this feature.
2. **The improvement does not survive the sweep.** Best paired t = 2.11 over ten
   looks; Sidak needs 2.80.
3. **The mechanism test found nothing.** If over-trusted starter ERAs were the
   problem, cards where the starters pull hardest should be the worst
   calibrated. Split three ways by how far the starters move the blend, the gaps
   are −3.34 (n=18), −6.87 (n=19), −5.21 (n=28). No pattern, and the middle
   bucket is the worst.

### So it ships off

Blank innings reproduces the old behaviour **bit for bit** — verified on all 67
logged cards and pinned by `test_a_blank_innings_field_changes_absolutely_nothing`.
All 28 pre-existing fixtures regenerated byte-identical.

It is not a small change when switched on. With both starters at a realistic 150
IP, 38 of 67 cards move by more than half a point and **13 change band, all of
them downward**. The old model went 4-8 on those 13, which is suggestive and is
also n=13, which is nothing.

The honest position: the a-priori case is strong and the empirical case is
absent. Type the innings when a starter is genuinely short-sample — a call-up, a
returning injury, an opener — and leave them blank otherwise until there are
enough logged games to settle it.

## What this total looks like

Added 2026-09-20, replacing the alternate-line panel on the page, on request.

It draws the full run distribution — one bar per possible final score, coloured
by which side of the line it falls on, with the line ruled through it — plus the
average, the median and the modal score, and then the model's own graded record
at this card's confidence.

### Why this, of all the things that could go there

Because of a real question, asked about a real card: *"the model will say under
at 54% chance for 8.5 on the braves/astros game but have the projected at 8.62.
Wouldn't the projected line be lower if the model thinks the game is going to go
under?"*

That is the single most important thing to understand about this model and it
was nowhere on the page. The answer is that runs cannot go below zero and can go
to sixteen, so the distribution is right-skewed and **the mean sits above the
median**. The model bets the median.

```
  runs   chance   running total
    7    9.89%       44.40%   <- the single likeliest score
    8    9.59%       53.99%   <- UNDER wins here and below
    9    8.83%       62.82%
   13+               12.93%   <- the tail that drags the average up
                  mean 8.62, median 8
```

Solved on the distribution at every line, the crossing is astonishingly stable:

```
  line  6.5 -> over is the favourite once the projection passes  7.043
  line  7.5 ->                                                   8.043
  line  8.5 ->                                                   9.043
  line 11.5 ->                                                  12.043
```

**Line + 0.543, every time.** The panel computes it per card rather than storing
it, but that is the rule of thumb. It is also why "projection above the line, so
bet the over" is a trap — it writes OVER on that Braves card and loses. An
outside audit of this model made exactly that error and reported it as a bug.

Everything on the chart is read off the same negative binomial the banner's
probability comes from. Nothing new is estimated, no constant is introduced, and
the browser check asserts the bars sum to the page's own probabilities, so a
picture that disagreed with the number above it would fail the build.

### And the second half: what the model has actually done here

Under the chart, the model's graded record **at this card's confidence**, bucketed
by the band floors — no new constants, and it matches the colour of the headline.

```
What this model has done at 53-57%: 39-28 (58.2%) over 67 graded calls.
It said 54.6% and did 58.2%, +3.6 points. At 67 calls one standard error
is 6.0 points, so that gap is inside the noise and is not established.
```

Under five graded calls in the bucket it refuses to report a rate at all and says
so. Pushes are excluded. This is the only place on the page that checks a
probability against the reader's own log at the number being offered, rather than
over everything at once.

### What was given up

The alternate-line panel was, on the evidence, the best-supported feature here —
it is the only part that **did not need the model to be right about anything**. A
book prices its main line sharply and its alternate ladder off a coarse template,
so a mispriced rung was a relative judgement rather than a forecast. Removing it
from the page is a real loss and worth stating plainly.

`alt_ladder()` and `alt_edge()` remain in `totals/fullgame.py` with their tests,
including the sign fix below — the arithmetic did not stop being correct. Only
the panel is gone. To put it back, restore the `#altCard` section and `renderAlt`
from the history of `web/fullgame.html`.

## Alternate lines (the package function)

Added 2026-09-16, and it is the strongest thing in this file because it is the
only part that **does not need the model to be right about anything**.

A book prices its **main** line sharply — that is the single fact this project
has actually established, over 116 games. It prices the **alternate ladder off a
template**, and templates are coarse. Given the market's own fair total,
recovered from the two main-line prices, the fair price at every other rung is
arithmetic on the same distribution:

```
main 8.5 at -115/-105  ->  market fair total 8.57

  alt    push    fair over   fair under
  7.5     —         -154        +154
  8      9.5%       -130        +130
  8.5     —         -104        +104   <- main
  9      9.0%       +116        -116
  10     8.2%       +171        -171
  10.5    —         +195        -195
```

So if a book shows OVER 10.5 at **+250** when its own main line implies +195,
that is **55 cents of value and +0.186 a unit** — and the judgement needed none
of the pitching inputs, none of the weather, and no opinion about who wins. It
needs the main line to be efficient, and nothing else.

At **+145** the same rung is 50 cents *worse* than fair. That is the template
charging you for the move.

### The sign was backwards and a test caught it

`_price_index` rises with implied probability, and a **higher implied
probability is a worse price** — you are laying more for the same outcome. The
first version subtracted the wrong way round and reported a book offering +145
against a fair +195 as **fifty cents of value** while its expected value was
−0.17 a unit. There is now a test that sweeps the whole ladder, both sides, and
eight prices per rung asserting that cents and expected value never disagree in
sign.

### Two ladders, and they must not be confused

`alt_ladder()` takes an optional `mu`. Left alone it uses the **market** anchor —
the number the book itself is standing on, and the one worth acting on. Passed
the blended projection it gives the **model** ladder, which is only as good as
the model. On 106 logged games the model has added nothing over the base rate,
so the page shows the market ladder.

## Does it work

`calibration()` and the page's **Is it working** panel answer the only question
that matters: does a 60% call win 60% of the time? A model can name the right
side more often than not and still be useless if its confidence is fiction,
because the confidence is what sizes the bet.

Pushes are excluded rather than counted either way — they refund, and folding
one into either column corrupts the measure. Brier, log loss, bucketed
said-vs-did, and a verdict that says plainly when the thing is miscalibrated or
below the 0.25 a coin flip scores.

The page also breaks the record down **band by band** — covered, missed, hit
rate, what it said, the gap, and pushes kept in their own column. The bands are
the units the decision is actually made in; nobody stakes off "56.3%", they
stake off STRONG. The test is whether the bands *order*: a model that wins
overall but whose STRONG is no better than its COIN FLIP is telling you nothing
about how much to put on, which is the only thing the confidence is for.

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

- `tests/test_fullgame.py` — 116 tests (375 across the suite), including the corroboration gate: the
  Tigers card held at COIN FLIP, the headline probability provably untouched, a
  no-soft-input card identical to twelve decimal places, the gate acting as a
  veto rather than a tax, the band never exceeding either read, and WNBA
  tagging nothing. Plus neutrality to nine decimal places, the distribution's
  mean and spread against the measured 4.39, push arithmetic, price inversion,
  the resolved-probability band, calibration detection of an overconfident
  model, and the guards.
- `web/fullgame-cases.json` — 38 games generated from the package by
  `tools_gen_fullgame_cases.py`, which recomputes only the expectations so a
  model change never means hand-editing a probability.
- `tools_check_fullgame_page.js` — 726 checks. It replays all 38 in a real browser against side,
  band, resolved probability, push, projection, fair price, estimate and delta
  counts, the gate's core projection and core probability, the core chip showing
  the corroborated probability on every card and turning amber only when held,
  the headline tinted at the band floors, the banner printing no verdict at all,
  and that green appears only when confident. Then it stores a game,
  grades it a loss, grades a second as a push, checks the push is excluded from
  calibration, reloads the browser and asserts the card, the grades and the
  half-typed draft all survive. It loads a hand-built card of known results and
  checks the per-band table reports 2-0, 1-1 and 0-1 with the push in its own
  column and an empty band left out, and that the card's Prob column is tinted at
  the same floors as the banner. It checks that the money split moves the
  projection, the probability and the band by exactly nothing while still
  printing its note, and that the run-distribution chart's bars sum to the
  page's own over, push and under probabilities, that the push row appears only
  on a whole number, and that the track record reports 3-2 from a seeded card
  with the push excluded. Last it checks the roof marker: a domed game is
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
