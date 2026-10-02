# What the logged games actually say

Every claim here is reproducible from the exported track record. Kept so the
same ideas do not get re-litigated from memory every week.

## 1. Season statistics do not predict which side of the line a game lands on

Over 116 settled MLB games:

| | |
|---|---|
| Mean absolute error, model's projected total | **3.61 runs** |
| Mean absolute error, *just using the posted line* | **3.58 runs** |

Single-feature correlations against (final − line), largest first: temperature
t = −1.60, dome t = +0.93, combined starter ERA t = +0.87, combined runs/game
t = +0.60, park factor t = −0.57, head-to-head t = −0.40, recent form t = −0.07.
**Nothing cleared |t| = 2.**

Ridge on all fourteen inputs, leave-one-out cross-validated, gave a **negative**
out-of-sample R² at every regularisation strength (best −0.055), improving
monotonically as the fit was forced toward using none of them. Betting that
fit's own out-of-sample side went **44-69 (38.9%)**.

Sweeping the trend weights from 0.30 to 0 never moved the record off ~50%.

## 2. No team-level over/under trend survives scrutiny

The Texas Rangers looked like a finding: **0-8 to the under, t = −2.83**. It
died three times over, and the sequence is worth keeping because every future
"trend" will need the same three checks.

1. **Team names were not normalised.** The log contains both "Texas Rangers"
   and "Texas Rnagers". Exact-match splitting treated them as two clubs — and
   the single game under the typo'd spelling is the one that went over. The
   real record is **1-8**.
2. **29 teams had 5+ games, so 29 comparisons were made.** Raw p = 0.039;
   corrected for the number of tests, **p = 1.00**. Getting one or two splits
   past |t| = 2 out of ~25 is the *expected* result of testing that many, not
   a discovery.
3. **The nine games are three opponents across three series** — LAA ×3,
   WSH ×3, OAK ×3, inside ten days. Consecutive games against the same club in
   the same park with the same staffs are not independent trials.

The Yankees (1-7) and Nationals (1-7) both go to corrected p = 1.00 the same way.

**A wrong-signed result is a tell.** Games at 80°F+ went under 63% of the time
(t = −1.68), but hot air is thinner and balls carry further — totals should go
*up*. When a split has a plausible t-stat and the wrong sign for its own
mechanism, it is noise nearly every time.

## 3. The under-lean in the log is not skill and not significant

Blind UNDER on every logged MLB game: **61-52-3, 54.0%**. The model's own UNDER
picks: **33-28, 54.1%** — identical, so the model added nothing over betting
under blind. And 61-52 on 113 decided games is inside one standard error of a
coin flip.

The real reason to lean under is market structure, not prediction: the public
bets overs, so books shade totals up. The checkable version is the gap between
the over's share of **tickets** and its share of **money**.

## The bar for a future finding

Before anything here becomes a rule it has to clear all three:

1. **A mechanism stated before looking at the data.** Wind blowing in suppresses
   fly balls — that is a reason. "Team X goes under" is a description.
2. **Correction for how many things were tested.** Divide by the number of
   splits, not by the one that looked best.
3. **Independence.** Spread across many opponents and weeks, not one hot streak
   or one series.

Wind clears all three. Nothing found by mining the log has cleared any.
