# Totals Model — MLB Runs & WNBA Points

A small, dependency-free model for game totals. You supply a handful of numbers
per team, it returns a projected total, over/under probabilities, the fair
price, expected value against the posted odds, and a suggested stake.

WNBA also has a **spread** read — which side covers, and how sure — built on
the same team inputs. See [The spread verdict](#the-spread-verdict--wnba).

No libraries to install, no API keys, no data pipeline. Python 3.9+ and the
standard library.

```
python3 -m totals mlb  examples/mlb_slate.json
python3 -m totals wnba examples/wnba_slate.json
```

**Prefer to point and click?** Open `web/index.html` in any browser. It's the
same model ported to JavaScript — a form for the inputs, results that update as
you type, and a chart of the outcome distribution. One file, no server, works
offline. Numbers were checked against the Python to six decimal places.

It also keeps a **track record**, which is the part that matters if you ever
want to know whether any of this works. See below.

## Read this first: the MLB totals verdict was retired

The season-statistics verdict for MLB totals does not work, and it is not a
tuning problem. Measured over 116 settled games in the track record:

| | |
|---|---|
| Mean absolute error, model's projected total | **3.61 runs** |
| Mean absolute error, *just using the posted line* | **3.58 runs** |

The projection was a slightly noisier copy of the number it was betting
against. Two further checks agree:

* **Nothing predicts the residual.** Correlating each collected input against
  (final total − posted line), the largest was temperature at t = −1.60.
  Combined runs/game reached t = +0.60, combined starter ERA t = +0.87, park
  factor t = −0.57, recent form t = −0.07. Nothing cleared |t| = 2.
* **No combination of them does either.** Ridge regression on all fourteen
  inputs, leave-one-out cross-validated, gave a *negative* out-of-sample
  R² at every regularisation strength (best −0.055), improving monotonically
  as the fit was forced toward using none of them. Betting that fit's own
  out-of-sample side went **44-69 (38.9%)**.
* **And the weights never mattered.** Sweeping `FORM_SHARE` from 0.30 to 0 and
  `H2H_SHARE` from 0.35 to 0, every combination landed between 48.7% and 53.1%
  overall and 48.0%–50.0% on the actionable picks.

Every input that model uses is published, public, and inside the posted number
before you see it. There is no gap to find, so no arrangement of them finds
one. `run_verdict` still exists and still runs — the code is unchanged and the
tests still pass — but it is not the one to bet.

## The late-factor model — `totals/late.py`

The replacement starts from the opposite premise: **the posted total is the
best forecast available, and this model does not compete with it.** It adjusts
the line, and only for things that (a) have a documented effect on run scoring
and (b) are not reliably in the number when you see it.

```python
from totals import run_late_verdict

r = run_late_verdict({
    "away": {"name": "Toronto", "relievers_unavailable": 2},
    "home": {"name": "Yankees"},
    "weather": {"temp_f": 74, "wind_mph": 14, "wind_direction": "out"},
    "umpire": {"name": "Ed Hickox", "runs_per_game": 9.3, "games": 210},
    "line": 8.5,
})
r["side"], r["win_pct"], r["band"]   # ('OVER', 0.6233, 'STRONG')
```

| Adjustment | Basis | What it needs |
|---|---|---|
| **Umpire** | documented | His own runs/game and games worked, regressed toward league by `n/(n+120)` — published daily by RotoWire, OddsShark, RefMetrics, and posted the morning of the game |
| **Wind** | documented | Speed **and direction** (`out`/`in`/`cross`). Dead below 8 mph, then 0.10 runs/mph, capped at 1.5. A cross wind is explicitly zero |
| **Temperature** | documented | Degrees from a 70°F baseline at 0.008 runs each, capped at 0.35 — deliberately modest, since it is the weather term the market prices best |
| **Bullpen availability** | *provisional* | High-leverage arms unavailable per side. The best claim to being unpriced: it breaks after lines open and season bullpen ERA cannot see it |
| **Lineup** | *provisional* | Regulars out per side |

Three things are different in kind from the old model:

**It refuses to invent an edge.** With no late factor supplied it returns
`NO EDGE` and says why — not a 51% lean squeezed out of season stats. Feeding
it the old model's entire feature set changes nothing; those fields are not
read at all.

**The numbers are small, because the measurement says they should be.**
`RESIDUAL_SD = 4.39` is the observed standard deviation of (final − line) over
those 116 games. A *full run* of adjustment is a quarter of one standard
deviation. That is why an honest edge here reads 53%, not 62%, and why the
first band that names a bet (`SLIM`) starts at 52.38% — the actual −110
breakeven — rather than at it.

**Placeholder coefficients announce themselves.** Every adjustment carries a
`basis` of `documented` or `provisional`, the verdict reports the two subtotals
separately, and if most of an edge rests on placeholders it says so in the
notes. Nothing here was tuned on the 116 games — those games contain none of
these inputs, which is the entire point.

## The page

`web/verdict.html` runs the late-factor model for MLB and the spread model for
WNBA, both ported from the package and checked against it case by case
(`test-late.js`, `test-spread.js` — fixtures regenerated from Python, never
hand-edited).

Three things about the MLB form are deliberate:

**It ships blank.** No default umpire, no default wind, no default line. This
one was a real bug for a while: the form shipped pre-filled with the example
umpire and wind, so every game a user opened inherited a fabricated edge before
they typed anything — the precise failure the model exists to end. The Example
button still loads a worked game; nothing else fills a box. `test-blank.js`
runs in a clean browser context to check it, because the page remembers what
you last typed and testing defaults after any other suite would be testing
`localStorage`.

**There are no trend inputs at all.** Head-to-head and recent form were two of
the fourteen features that cross-validated to nothing. The card is gone rather
than hidden, and `test-late.js` checks that values left in the DOM from a WNBA
session cannot reach the verdict.

**Reopening an older logged game says so.** MLB games logged under the
season-statistics verdict cannot be re-run — their inputs have no box on this
form — so the recall banner says that outright instead of showing `NO EDGE`
over an empty form as though the model changed its mind.

The track record now has a **Close** column and a **CLV** column beside the
final, and a "Beat the close" tile in the summary. That is the metric this
model would rather be judged on; see below.

## Closing line value, and why the record isn't the point

A win/loss record is a terrible way to evaluate a model, because the sample
sizes are brutal:

| If you are truly a… | Bets needed to prove it (95%, one-sided) |
|---|---|
| 54% winner | ~2,581 |
| 55% winner | ~986 |
| 56% winner | ~517 |
| 58% winner | ~214 |

Breakeven at -110 is 52.38%. A genuinely excellent 55% bettor needs about a
thousand bets before the record itself is convincing. A 3-0 start happens 12.5%
of the time by coin flip.

**Closing line value is the shortcut.** Record the line when you bet and the
line at game time. If you bet OVER 8.5 and it closes at 9, you got a better
number than the market's final answer — that is +1.0 of CLV, whether the bet
wins or loses. Because CLV measures a continuous quantity against a sharp
benchmark instead of a coin flip, it reads in dozens of bets rather than
thousands.

The web page tracks it automatically. Run a game, hit **Bet it**, **Passed**, or
**Bet the other side**, and later fill in the closing line and final score. It
keeps three separate records:

- **Yours** — what you actually bet
- **The model's** — every green recommendation, bet blindly
- **The gap between them** — whether your overrides help or hurt

Those diverge whenever you fade the model, which is exactly when the comparison
is worth having. Everything is stored in your browser, exportable to CSV, and
never leaves your machine.

**Log the games you pass on too.** A record of only the games you liked cannot
tell you whether the model works — the ones you skipped are half the evidence.

```
WNBA totals -- 3 game(s), model weight 0.5

  Sky @ Sun          model 145.85  line  158.5  proj 152.18  UNDER -115.0  win%  70.9  EV +32.52%  stake  2.00%  *
  Fever @ Mystics    model 179.65  line  170.5  proj 175.08  OVER  -112.0  win%  65.5  EV +23.92%  stake  2.00%  *
  Aces @ Liberty     model 170.29  line  167.5  proj 168.90  OVER  -110.0  win%  54.8  EV  +4.68%  stake  1.29%  *

  * = positive expected value at the posted price
```

---

## What you plug in

### MLB — five numbers per team, plus the park

| Field | What it is | Where to get it |
|---|---|---|
| `runs_per_game` | Team runs scored per game | FanGraphs team batting, or Baseball Reference |
| `starter_era` *or* `starter_ra9` | Tonight's announced starter | FanGraphs pitcher page (`RA9` if you have it, ERA is fine) |
| `starter_ip` | Average innings per start (IP ÷ GS) | FanGraphs, same row as ERA; 5.0–6.0 covers most |
| `bullpen_era` *or* `bullpen_ra9` | Team bullpen ERA | [Inside The Pen](https://insidethepen.com/bullpen-era-rankings.html) — one list, all 30 teams |
| `own_park_factor` | Park factor of the team's *home* stadium | Baseball Savant park factors (100 → 1.00) |
| `park_factor` | Park factor of tonight's venue (game-level) | Same source |
| `weather` | `temp_f`, `wind_mph_out` (negative = blowing in), or `dome: true` | Any forecast |

```json
{
  "away": {"name": "Dodgers", "runs_per_game": 5.05, "own_park_factor": 1.00,
           "starter_era": 3.05, "starter_ip": 6.0, "bullpen_era": 3.60},
  "home": {"name": "Rockies", "runs_per_game": 4.95, "own_park_factor": 1.28,
           "starter_era": 5.40, "starter_ip": 5.0, "bullpen_era": 5.10},
  "park_factor": 1.28,
  "weather": {"temp_f": 84, "wind_mph_out": 5},
  "market": {"line": 11.5, "over_odds": -105, "under_odds": -115}
}
```

Only `runs_per_game` is really required — every field has a league-average
default, so you can start with three inputs and add the rest as you go.

### WNBA — four numbers per team

| Field | What it is | Where to get it |
|---|---|---|
| `pace` | Possessions per 40 minutes | Her Hoop Stats, Basketball Reference team stats |
| `off_rating` | Points scored per 100 possessions | Same |
| `def_rating` | Points allowed per 100 possessions | Same |
| `rest_days` | Days since last game; `0` = back-to-back, `1` = short rest | The schedule |

```json
{
  "away": {"name": "Aces", "pace": 81.5, "off_rating": 108.0, "def_rating": 99.5, "rest_days": 2},
  "home": {"name": "Liberty", "pace": 79.0, "off_rating": 109.5, "def_rating": 96.0, "rest_days": 3},
  "market": {"line": 167.5, "over_odds": -110, "under_odds": -110}
}
```

WNBA pace is **per 40 minutes**, not per 48 like the NBA. If your source gives
per-48 numbers, multiply by 40/48 or the totals will come out ~20% too high.

The `market` block is optional in both sports. Leave it off and you get a bare
projection; include it and you get the full grading.

---

## How it works

**MLB** uses the standard odds-ratio matchup. A team's expected runs are the
league average, scaled by how good their offence is and how bad the opposing run
prevention is:

```
runs = lg_rpg × (offence / lg_rpg) × (opposing_run_prevention / lg_rpg) × park × weather
```

Run prevention blends the starter and the bullpen by expected workload — a
starter going 6 gets 2/3 of the weight, the pen gets the rest. That single input
moves baseball totals more than anything else, which is why it is worth
entering by hand.

Each team's runs then become a **negative binomial** distribution (mean 4.4,
sd ≈ 3.0, matching real team run distributions), and the two are convolved into
a distribution over the game total. That is what produces honest probabilities
for whole-number lines, where a push is genuinely possible.

**WNBA** splits the total into possessions and efficiency:

```
possessions = pace_away × pace_home / lg_pace
points_A    = possessions × (off_rating_A × def_rating_B / lg_rating) / 100
```

Home court is applied to the **margin only**, not the total — home teams win by
more, they do not play systematically higher-scoring games. A back-to-back costs
that team 2.0 points per 100 possessions, and one day of rest costs 1.0 — the
penalty used to gate on zero days, which never once fired on a real slate,
because the schedule almost never produces a true zero-day turnaround and
`rest_days` already treats two days as the normal baseline. Overtime is added as an expected value
weighted by how close the game projects (a pick-'em adds about a point; a
20-point mismatch adds almost nothing). The final total is treated as normal
with sd 11.5.

**Both sports** then get the same treatment: shrink toward the market, compare
to the no-vig price, size the bet.

---

## The two safety rails

These matter more than the model itself.

**Market shrinkage (`--model-weight`, default 0.5).** The posted line already
contains lineups, injuries, umpires and sharp money. A model with five inputs
per team does not beat that outright. So the projection used for grading is a
blend:

```
projection = w × model + (1 − w) × line
```

At the default 0.5 the model meets the market halfway. Raise it toward 1.0 only
after you have backtested your own inputs and know they hold up. Set it to 0.0
and the model always agrees with the market and never bets — which is the
correct behaviour for a model with no demonstrated edge.

**Stake cap (`--max-stake`, default 2%).** Bets are sized with quarter Kelly
(`--kelly 0.25`) and then hard-capped. Kelly on an overconfident projection will
cheerfully suggest 18% of bankroll; the cap is what stops it. The uncapped
number is still reported as `kelly_uncapped_pct` so you can see when the model
is straining.

**Stake floor (`--min-stake`, default 0.25%).** Kelly is continuous; a
recommendation should not be. It returns 0.01% as readily as 1.5%, and any
positive number reads as a green light — so a play the model can barely
distinguish from a coin flip gets bet at whatever size you normally bet at.
Across a real 18-bet sample the plays sized between 0.01% and 0.17% went 1-3
and lost more than the ten genuine ones combined. Below the floor, `recommended`
is `False` and `kelly_stake_pct` is 0; `kelly_uncapped_pct` still shows the real
size, so nothing is hidden.

**Side filter (`--sides`, default `both`).** Restricts which sides may be
recommended. It filters the *recommendation*, never the projection: a bettor
taking overs only still needs an honest probability for the under, because it is
the same number seen from the other end, and suppressing one would corrupt the
other. A filtered game reports the model's real read, its real probability and
its real EV, and declines to bet — `not_recommended_because` says which of the
three rails stopped it (side filter, juice, or stake floor).

---

## Command line

```
python3 -m totals {mlb|wnba} FILE [options]

  --min-ev 0.02        only show plays with at least 2% EV
  --kelly 0.25         fractional Kelly multiplier
  --model-weight 0.5   how far to trust the model over the line (0–1)
  --max-stake 2.0      cap on a single stake, % of bankroll
  --min-stake 0.25     floor on a single stake; below it, not a recommendation
  --sides over         restrict recommendations to one side (both|over|under)
  --format json        machine-readable output
```

The input file can be a single game object, a list of games, or
`{"games": [...]}`. Slates are sorted best-EV first.

## As a library

```python
from totals import run_game, run_slate

report = run_game("mlb", game_dict)
print(report["projected_total"], report["best_side"], report["ev_per_unit"])

for r in run_slate("wnba", games, model_weight=0.6):
    print(r["matchup"], r["kelly_stake_pct"])
```

Output keys: `model_total` (raw model), `projected_total` (after shrinkage),
`raw_edge` / `blended_edge`, `p_over` / `p_under` / `p_push`,
`market_p_over_novig`, `book_hold`, `best_side`, `fair_odds`,
`prob_edge_vs_market`, `ev_per_unit`, `recommended`,
`not_recommended_because`, `kelly_stake_pct`, `kelly_uncapped_pct`.

## Tests

```
python3 -m unittest discover -s tests -v
```

129 tests, covering the odds math, the distributions, both sport models, the
verdict and spread verdicts, the shrinkage behaviour and the staking rails.

---

## The verdict model

A second, separate read on the same games, in `totals/confidence.py` and
`web/verdict.html`. It answers a different question — *which side, and how
sure* — and shares none of the pricing machinery.

```python
from totals import run_verdict

r = run_verdict("mlb", {
    "away": {"name": "Cubs", "runs_per_game": 5.16, "starter_era": 4.38,
             "starter_season_ip": 132, "starter_ip": 5.7, "bullpen_era": 3.87},
    "home": {"name": "Nationals", "runs_per_game": 5.36, "starter_era": 4.74,
             "starter_season_ip": 62, "starter_ip": 5.0, "bullpen_era": 5.07},
    "park_factor": 1.02, "weather": {"temp_f": 86},
    "line": 9.0,
    "h2h":  {"avg_total": 10.5, "games": 4},
    "form": {"away_avg_total": 9.8, "home_avg_total": 10.1, "games": 5},
})
r["band"], r["side"], r["win_pct"]   # ('MEDIUM', 'OVER', 0.571)
```

**No odds.** The only market input is the posted total. At even money the line
is the point where the book has over and under equally likely, so solving for
the mean at which the model reproduces it converts the line into the
projection's own units — enough to compare against, with no price involved.

**Several signals, not one.** The matchup model, the head-to-head history and
each side's recent form each vote, weighted by the evidence behind them. The
trends take at most half the trust budget between them — 30% recent form, 20%
head-to-head, and each only at a full sample; the matchup model always keeps the
other half. A projection is one opinion, several that agree are a trend.

Recent form outweighs head-to-head because head-to-head is the weaker of the
two: over the games logged so far its own estimate of the total misses the final
by 6.4 against recent form's 5.0. The matchup model is the most accurate of the
three at 4.6 and the only one that knows who is pitching, which is why raising
form's share comes out of head-to-head and never out of it.

**Basketball trades head-to-head for a team's own over/under record.** WNBA
teams meet one to three times a season, so head-to-head there is not a sample —
it is a single lopsided game wearing a trend's clothes, and across the logged
games it read between 5.5 and 27 points off the market. So the WNBA drops the
signal outright rather than ramping it ever smaller: it never enters the signal
list, its input is hidden, its range is not checked, and the matchup model keeps
the share it would have taken.

In its place, WNBA totals can vote a team's own win-loss record against the
total — `over_under_record`, wins and losses for each side. That number is a
*rate* ("the market's line has been right about this team X% of the time"),
not a *value* like the other three, so it cannot be averaged into a total the
way two scoring rates can. It is converted instead by reusing the exact
machinery `market_mean` itself is built from: solve for the mean at which this
game's own distribution would produce that probability of going over. **This
share (20%) is unvalidated**, unlike the other three, which came from mean
error on logged games — there is no history with this signal in it yet.
Revisit the share, the ramp, and the conversion once WNBA games have been
logged with a record entered, the same way `FORM_SHARE` was checked against
`H2H_SHARE`.

> **The page no longer runs WNBA on totals** — it runs the spread verdict
> below. `run_verdict("wnba", …)` still works, and the over/under record
> signal with it; the library kept the capability, the page changed which
> question it asks. See **The spread verdict** below for why.

**`starter_season_ip` is a season figure again.** Under 40 innings it is
flagged and costs a band. The field still works arithmetically for any window
-- it means "innings behind this ERA," full stop — regress_era() shrinks toward league average by whatever
number goes there, whether that is a full season or a starter's last 5 starts.
Swap in a shorter window by moving the ERA, this field, and `starter_ip`
(average IP per start) together as a set; a short window regresses harder
toward average on its own, which is the correction. There used to be a
confidence downgrade for anything under 40 innings, calibrated for a season-
long sample. It was removed by request to run this field as a last-5 window,
since a real value there is always under 40 by design and the flag would have
fired on every single game and said nothing. Leaving the field blank or at
zero still costs a downgrade — an ERA with no innings behind it at all is a
different, worse problem than a real short one, and is what turned a 0.00 ERA
into this model's largest false-confidence bet before that check existed.

**The band is the edge, and only the edge.** The win probability sets it —
HIGH at 58%, MEDIUM at 54.5%, LOW at 52%, NO PLAY below that — and nothing else
moves it. A doubt does not cost a rung.

It used to. Every complaint — signals pointing different ways, thin inputs, a
projection implausibly far from the market — knocked the band down one step. The
track record is what retired that rule. NO PLAY ended up holding two completely
different kinds of game under one label: the ones that earned it, with no edge
to speak of, and the ones that earned LOW or better and got marked down. On 147
logged games those two went **7-8** and **10-5**. Nothing in the log could tell
them apart, because the band was answering two questions with one word.

**Input quality is its own answer.** `input_grade` is `clean`, `flagged` (one
doubt) or `shaky` (two or more), reported next to the band rather than
subtracted from it. Same evidence, same complaints, same notes — they just no
longer masquerade as a smaller edge. This is a reporting change, not a claim
about which way the doubts point: separating the two axes is what makes that
question answerable from the next hundred games instead of unanswerable forever.

**A read is never an abstention.** Every verdict names a side and a number,
including NO PLAY, and the page now shows the pick at every band. It used to
hide it below LOW, which read as the model declining to answer. It never was:
one of two things happens tonight, and the model always had an opinion. NO PLAY
means *thin edge* — below the 52.4% a -110 bet has to clear — not *no pick*.

`LEAN` remains in `BANDS` so logs written under the old rule still render, but
nothing produces it any more; it was only ever reachable by stepping down.

**Impossible numbers name themselves.** Every field has a physical range —
not "unlikely", *impossible* — and anything outside it is flagged by name, marks
the offending box on the form, and grades the inputs shaky. A typo does not
announce itself; it gets absorbed. An average of 401 innings per start was read
as "this starter goes all nine", which took the bullpen out of the calculation
and moved the projection half a run, because 401 clamps quietly to 9.

**Park factors apply only to the park being played in.** A team's own home park
does not adjust its season rates here. That costs some accuracy for road teams
from extreme parks, and removes a per-team input that is easy to enter on the
wrong scale and silently ruinous when it is.

---

## The spread verdict — WNBA

`totals/spread.py`. Same question as the verdict model, asked about the margin
instead of the total: **which side covers, and how sure.** MLB stays on totals;
this is WNBA only.

```python
from totals import run_spread_verdict

r = run_spread_verdict("wnba", {
    "away": {"name": "Wings", "pace": 79.8, "off_rating": 104.9,
             "def_rating": 112.1, "rest_days": 2},
    "home": {"name": "Lynx", "pace": 79.5, "off_rating": 114.0,
             "def_rating": 104.0, "rest_days": 2},
    "league": {"pace": 79.3, "rating": 109.4},
    "spread": -9.5,                       # the HOME line, as the book prints it
    "form": {"away_avg_margin": -5.5, "home_avg_margin": 7.0, "games": 5},
    "ats_record": {"away": {"wins": 13, "losses": 19},
                   "home": {"wins": 18, "losses": 14}},
})
r["band"], r["side"], r["win_pct"]   # ('HIGH', 'HOME', 0.5996)
```

**Why the margin and not the total.** The WNBA totals verdicts swung hard game
to game while the same model's *margin* internals sat unused: `project()` has
always returned separate away and home scores, home court has always been
applied to the margin only (it moves who wins, not how much scoring there is),
and `MARGIN_SD = 11.0` had been sitting in `wnba.py` doing nothing but feeding
the overtime estimate. The margin is the half of that projection the model is
better built to defend.

**Sign conventions, fixed once and used everywhere.** `spread` is the home
line as posted: `-6.5` means the home side is favoured by 6.5, `+4.5` means it
is a 4.5-point underdog. Margins are home minus away, so positive means the
home team wins. A signal's lean is its margin minus the market's — positive
leans `HOME`, negative leans `AWAY`.

**One thing gets simpler.** A totals line is a *median* on a right-skewed
distribution and has to be solved into a mean before anything can be compared
against it. A margin distribution is symmetric, so the spread already *is* the
expected margin: `market_margin = -spread`, no bisection anywhere.

**Recent form is a margin, and home court goes back on.** `away_avg_margin`
and `home_avg_margin` are each team's average margin over its own last N games
— points scored minus points allowed, so a team losing by 4 a night is `-4`.
That average is roughly venue-neutral (about half those games were at home), so
the neutral read on tonight is the difference of the two, plus home court.
Without that add-back, form would dissent toward the away side by a flat 2.5
points on *every* game — a systematic argument against the model and the market
at once.

**`ats_record` replaces the over/under record.** Wins and losses against the
spread for each side. Like the over/under record it is a *rate*, not a value,
so it is converted by inverting the same distribution the verdict is scored on:
`market_margin + z(p) × margin_sd`. The two records point in opposite
directions by construction — the home team covering *its* games says the market
underrates it, the away team *failing* its games says the market overrates it,
and both of those lean home tonight — so the combined figure averages the home
cover rate with the complement of the away one. **The 20% share is unvalidated**,
exactly as the over/under record's was: there is no logged spread history to
check it against yet.

Everything structural is inherited rather than reinvented: the same band ladder
with the same thresholds, the same trust budget where the matchup model keeps
at least half, the same separation of the edge band from the input grade, and
the same refusal to read a half-filled wins/losses box as a number.

In the track record a spread pick is graded from **both scores, away first** —
`74-88` is a 14-point home win, which covers `-9.5`. Entries carry a `bet_type`
so a mixed log grades each row by its own rules; WNBA games logged before the
pivot are still counted and still graded as the totals bets they were, but the
projector will not reopen one, because reading a 163.5 total as a spread would
produce confident nonsense.

---

## Reading the recommendation

Three things on the page exist to stop a band being read as more than it is.

**The band's own record, under the band.** A band is a claim about a hit rate.
Directly beneath it the page prints what that band has actually done in your
log — scoped to the same sport, the same bet type, and the same model version,
because an MLB totals LOW and a WNBA spread LOW are different claims that
happen to share a name. Below 20 settled games it says so and stays quiet;
past that, if the band is more than 5 points under what it claimed, it says
that instead.

**Backed against passed.** The summary shows the games you took and the games
you skipped side by side. The skipped games are the control group: the model's
advice, unbet. If they are out-hitting the games you backed, the page says so
outright — that is the single most useful fact a track record can produce, and
it used to be buried in the exported report.

**A model version stamp.** Every logged game records which configuration
produced it (`MODEL_VERSION`). Eight days of early logs turned out to contain
at least four different models — the form share moved, the trust slider spent a
day at 1.00, the pitching window went to last-5 and back, LEAN appeared partway
through — and nothing recorded which games came from which, so the band table
could only report on four models averaged together. Bump the stamp when a
constant that moves a verdict changes; leave it alone for display-only changes.

---

## Tuning it

League baselines live at the top of `totals/mlb.py` and `totals/wnba.py` and
should be refreshed once a season:

```python
# mlb.py
LEAGUE_RUNS_PER_GAME = 4.52
RUN_DISPERSION       = 4.0    # variance = mean + mean²/r

# wnba.py
LEAGUE_PACE   = 80.0          # possessions per 40 min
LEAGUE_RATING = 107.0
TOTAL_SD      = 11.5          # spread of a final total around projection
```

The weather coefficients in `mlb.py` (0.15% per °F from a 74°F reference, 0.2%
per mph of wind) are deliberately small and clamped to ±5%. Treat them as a
nudge, not a signal.

**Calibrate the baselines against the market, not against results.** Every one
of these constants sits in a denominator, so a stale value biases every game the
same direction rather than washing out — which is exactly what makes it hard to
notice and easy to mistake for edge. The test is to average the model's raw
projection and the market's implied mean over your logged games; the gap should
be near zero. That comparison has no game randomness in it, so a dozen games
settle it. Grading against actual finals needs hundreds.

Beware of deriving a baseline from an identity instead. The league's mean
offensive and defensive ratings must be equal, and equal to `LEAGUE_RATING` —
true, but only if the pace and rating figures you enter share a possession
estimate. When they came off different sources, that derivation put the WNBA
constant at 108.1 and made the model 1.8 points *worse* against the market than
107.0 did.

## Why a projection above the line can still say UNDER

This trips everyone up once. Run scoring is right-skewed: blowouts drag the
*average* up without moving the *typical* game. A projection of 8.91 runs has a
median of 8, so `P(over 8.5)` is 48.8% even though the mean sits above the line.

```
projected 8.91 runs
line  8.5   P(over) = 0.4880   P(under) = 0.5120
line  9.5   P(over) = 0.3982   P(under) = 0.6018
```

Trust the win probability, not the gap between the projection and the line. This
is the whole reason the model convolves distributions instead of comparing two
numbers — a mean-only model would confidently pick the wrong side of the median.
The web page calls this out automatically whenever it happens.

## Honest limitations

- **It does not know about today.** Bullpen usage over the last three days,
  a scratched starter, a rest day for a star, a called-up September roster —
  none of that is in here. Check the news before you act on a number.
- **Season-long rates are lagging inputs.** A team's April run rate is not its
  August one. Consider using last-30-day splits once the sample supports it.
- **The park adjustment assumes a balanced home/road split.** Early in the
  season, when a team has played 70% of its games at home, `own_park_factor`
  will over-correct.
- **It has not been backtested.** The structure is sound and the components are
  standard, but no closing-line-value study has been run on it. Track your
  results against closing lines before you trust the EV numbers.
- **A 30%+ EV means your inputs are wrong**, not that you found a mispriced
  game. Real edges in liquid markets are 1–3%. Anything larger is a typo, a
  stale line, or a per-48 pace number.

Sports betting involves risk. This is a modelling tool, not advice, and no model
guarantees a profit.
