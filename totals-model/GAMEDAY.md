# Game-day playbook — totals

What I do when a slate arrives. Written down so it is the same every night and
so the numbers below are auditable rather than invented on the spot.

**Scope: totals, both sports, under-weighted.** The WNBA *spread* model went
4-5 and is retired; what is here is the over/under, which is what the WNBA side
of this project was before the spread pivot. Nothing here prices a side or a
spread in either sport.

## The one rule

**The posted line is the best available forecast.** Nothing here argues with it
from season statistics — that approach was measured over 116 logged games and
produced a mean absolute error of 3.61 runs where using the line alone produced
3.58, with a negative cross-validated R² on all fourteen of its inputs.

And the corollary: **news is not an edge once the line has moved on it.** Every
item below is scored twice — what it is worth, and how far the number has
already travelled. Only the remainder counts.

## Why unders, honestly

Two different claims get bundled together here, and only one of them survives
contact with the data.

**"Bad offences underperform, so their games go under."** This is not supported.
In the 116-game log, combined runs per game correlates with (final − line) at
**t = +0.60**. Team scoring level does not predict which side of the *line* a
game lands on, because the market already knows which offences are bad and has
priced it. Unders in that log went 61-52-3 (54.0%), which is inside one
standard error of a coin flip.

**"Totals are shaded upward because the public bets overs."** This one is real,
and it is a market-structure fact rather than a forecast. Recreational money
wants runs, so books shade totals up to balance the book. That creates a
standing, small tilt toward unders — and, more usefully, a *detectable* one:
when the over holds a large share of **tickets** but a much smaller share of
**money**, the small bets are on the over and the large ones are on the under.
That is the standard sharp-money tell and it is checkable on the day.

So: unders get the benefit of the doubt for a documented reason, not because
anyone is flaking.

## What I need from you

**I am behind an egress proxy that blocks every data site on this list.**
Verified on 2026-08-24: rotowire.com, covers.com, refmetrics.com,
sportsbettingdime.com, mlb.com, actionnetwork.com, baseballsavant.mlb.com and
api.weather.gov all refuse the connection. Web *search* works and returns
headlines; it does not return the tables. So I can reason, but on most nights I
cannot fetch the two documented inputs myself.

That inverts what is worth screenshotting. The Covers **Stats** tab — records,
ATS, O/U splits, last-10, head-to-head, season pitcher lines — is the priced
category and I do not need any of it. What I cannot get and cannot substitute:

1. **The odds board with the Open column**, which is the single most valuable
   screenshot. Movement from the open is half the model, and it is the only way
   to tell an unpriced edge from one the market already bought.
2. **The weather page** — wind speed *and direction* per park, temperature,
   roof open or closed. Direction is what matters; speed alone is unusable.
3. **The umpire assignments** — tonight's plate umpire and his runs/game.
4. **Prices on both sides** (o7.5 −118 / u7.5 −102). The vig asymmetry says
   where the money is.

Without 2 and 3 there is usually no documented item, and the grounded gate
fails, and the honest answer for the whole board is PASS. That is not the model
being coy — it is the model refusing to bet on nothing.

## The checklist — MLB

Run top to bottom. Most games produce nothing; that is the expected result.

| # | Check | Where | Worth | Basis |
|---|---|---|---|---|
| 1 | **Wind speed + direction** | [RotoWire weather](https://www.rotowire.com/baseball/weather.php) | Nothing under 8 mph; then 0.10 runs/mph, capped 1.5. Cross wind = 0 | documented |
| 2 | **Home plate umpire** | [RotoWire daily](https://www.rotowire.com/baseball/umpire-stats-daily.php), [OddsShark O/U records](https://www.oddsshark.com/mlb/umpire-handicapping-statistics) | His **over/under record**, Beta-shrunk against a 335-game prior, capped ±1.0. R/Gm only as a fallback | documented |
| 3 | **Ticket vs money split** | [Action Network](https://www.actionnetwork.com/mlb/public-betting), [Covers consensus](https://contests.covers.com/consensus/topconsensus/mlb/overall) | ±0.30 runs when the gap is 20+ points. Capped flat — direction documented, size not | documented |
| 4 | **Temperature** | RotoWire | 0.008 runs/°F from 70°, capped 0.35 | documented |
| 5 | **Lineup scratches** | beat writers, [MLB.com](https://www.mlb.com/scores) | 0.12 runs per missing regular, max 3/side | *provisional* |
| 6 | **Line movement since open** | you, or Covers | Subtract from 1–5 | — |

### The trial tier

Asked for on 2026-08-24. Two of these have been measured on the 116-game log
and came back null — head-to-head **t = −0.40**, team form **t = −0.07** — so
they carry deliberately small coefficients and say so every time they print.
Pitcher last-five is the exception worth taking seriously: the log only ever
held *season* starter ERA, so that window has genuinely never been tested here.

| Check | From your screenshot | Worth |
|---|---|---|
| **Team form, last 5** | each side's last-5 average total | 15% of the gap to the line, cap 0.60 |
| **Head to head** | average total in the meetings | 10% of the gap, cap 0.40, **needs 3+ meetings** |
| **Starters, last 5** | each starter's last-5 ERA and IP | gap from league, shrunk `ip/(ip+120)`, × 5/9 innings, cap 0.70 |
| **Bullpens, recent** | each pen's recent ERA and IP | gap from league, shrunk `ip/(ip+90)`, × 4/9 innings, cap 0.60 |

The h2h floor at three meetings is not arbitrary: letting a two-game
head-to-head vote is the specific fault that cost four picks a confidence band
in the old model.

Bullpen here is **form, not availability**. Availability — who threw last night
and cannot go — is the better idea and the one with a real claim to being
unpriced, but it needs beat notes that are hard to get consistently and
impossible to verify afterwards. Form is what a screenshot can carry.

**How the trial runs.** In strict mode these cannot satisfy the grounded gate,
so a card carried only by them reads PASS. `decide(trial=True)` lets them carry
a **LEAN** — never a BET, because a top-band call on unmeasured coefficients is
the false confidence this model exists to refuse. Every game gets logged both
ways, strict and trial, against the same line. After thirty or forty games the
comparison answers the question, which is the thing that was never done the
first time these inputs were in a model.

**Read the hourly row and the prose, never the headline.** The weather cards
head each game with "N MPH wind blowing X in CITY", and when no direction is
given that "in" is the preposition, not the direction — "8 MPH wind blowing in
West Sacramento" is a card whose own hourly row and prose both say the wind is
blowing **out**. Reading the headline literally flips the sign on the largest
term in the model. Same trap on "blowing in Washington, D.C.", where the prose
says the breeze crosses the diamond left to right.

Wind blowing in is the single largest under-driver available — 20 mph in is
worth more than a full run, which is over twice anything else on this list.
Umpire assignments post the morning of the game and are the item most likely to
be missing from an opening number.

**Ask for the over/under record, not runs per game.** R/Gm is confounded by
which parks the man happened to draw — work a month of Coors and Cincinnati and
you read hot for reasons that have nothing to do with your zone. His O/U record
is park-adjusted by construction, because every line he was measured against
already accounted for the park and the teams. `umpire_rpg()` survives as a
fallback and labels itself the weaker input.

**And read the game count before the percentage.** Umpires work the plate about
every fourth game, so one season is ~30 — against a prior worth 335. A
leaderboard sorted by over-rate therefore puts the *smallest* samples on top:
the 3-0, 100% umpire heading such a list is worth **+0.05 runs** after
shrinking, while a 185-115 career line that looks unremarkable is worth
**+0.61**. Twelve times as much, from a number that reads worse.

The shrinkage is derived, not chosen. `k = sd² / τ²`, where sd is the observed
4.39 and τ is the true between-umpire spread. The 1.5-run figure quoted for the
gap between extremes is the *raw* spread across ~90 umpires and so contains
sampling noise; treating it as roughly five standard deviations gives τ ≈ 0.30
and k ≈ 214. The first version used 120, which quietly assumed τ = 0.40 — the
optimistic end, and it made every umpire look twice as important as he is.

The split at #3 is deliberately capped flat: a 40-point divergence scores the
same as an 80-point one, because the direction is documented and the magnitude
is not, and inventing a curve there would be exactly the false precision that
sank the previous two models.

## The checklist — WNBA

| # | Check | Where | Worth | Basis |
|---|---|---|---|---|
| 1 | **Rotation players out** | team injury report, beat writers | 2.0 pts per starter, 3.5 if their leading scorer, ceiling 8.0 per team | documented direction, capped size |
| 2 | **Line movement since open** | you | Subtract from 1 | — |

This is the one place where a single item can carry a bet. A twelve-deep roster
with starters at 32+ minutes has no bench to absorb an absence, so it costs a
WNBA team more than the same news costs any other league's team.

The ceiling is 8.0 and binds at four absences. It was 6.0 first, which bound at
three and made three, five and nine score identically — the model could not
tell a thin night from a gutted one. Below the ceiling the ladder runs 3.5,
5.5, 7.5, 8.0.

**Thresholds are the same fraction of dispersion as MLB** — a tenth for a LEAN,
a fifth for a BET — so neither sport is the soft one. WNBA dispersion is 11.51
points, measured over only 13 logged totals, which is far too few to trust as a
point estimate; it is used because it is the only measurement available and
because it agrees with the 11.0 the spread model used for margins.

## The gates

Every candidate has to survive all four (`totals/gameday.py`):

1. **Fresh** — evidence dated to game day. Yesterday's note is a guess.
2. **Grounded** — at least one `documented` item. Provisional coefficients
   alone get logged as a hypothesis, never backed.
3. **Unpriced** — net edge after line movement must clear **0.45 runs** (MLB)
   or **1.20 points** (WNBA). A `BET` needs **0.90** / **2.40**.
4. **Uncontradicted** — no documented item pointing the other way *by at least
   half the lean bar*. With no validated weights there is no honest way to net
   two real signals that disagree, so the answer is stand down.

   The floor matters. Without it a 0.15-run temperature term stood down a game
   carried by a half-run umpire — which is exactly the fault that killed the
   old confidence model, where a head-to-head signal holding 1.25% of the
   weight could still cost a full band and did so on four logged picks. Same
   bug, different model, found again by watching a warm night in Anaheim veto
   a real read.

A stacked under — wind in, pitcher's umpire, sharp money under, cold — clears
0.90 comfortably and is the shape worth waiting for. One of those alone
usually is not.

## How this gets judged

**Closing line value, not win–loss.** At 116 games a true 55% and a true 50%
are statistically indistinguishable — one sigma is about nine percentage
points. Whether the number moved toward the side I took converges in tens of
bets instead of hundreds. Beating the close on better than ~55% is the signal
that something real is underneath.

Every call gets logged with the number I took and the number it closed at. If
after fifty calls I am not beating the close, this playbook is wrong too and I
will say so rather than wait for the win–loss column to bail me out.

## What I will not do

- Produce a pick because a slate deserves one. Most nights the honest output is
  a list of passes.
- Take an under because an offence looks bad. That is the claim the data
  refuses, and it is already in the price.
- Quote a probability I cannot ground. Magnitudes convert through the observed
  dispersion of 4.39 runs and nothing else.
- Present a provisional coefficient as though it were measured. Items 5 and 6
  are placeholders sized by reasoning and are labelled every time they appear.
