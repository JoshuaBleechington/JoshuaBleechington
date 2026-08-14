# Totals Model — MLB Runs & WNBA Points

A small, dependency-free model for game totals. You supply a handful of numbers
per team, it returns a projected total, over/under probabilities, the fair
price, expected value against the posted odds, and a suggested stake.

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
| `rest_days` | Days since last game; `0` = back-to-back | The schedule |

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
that team 2.0 points per 100 possessions. Overtime is added as an expected value
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

92 tests, covering the odds math, the distributions, both sport models, the
shrinkage behaviour and the staking rails.

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
r["band"], r["side"], r["win_pct"]   # ('MEDIUM', 'OVER', 0.5715)
```

**No odds.** The only market input is the posted total. At even money the line
is the point where the book has over and under equally likely, so solving for
the mean at which the model reproduces it converts the line into the
projection's own units — enough to compare against, with no price involved.

**Three signals, not one.** The matchup model, the head-to-head history and each
side's recent form each vote, weighted by the evidence behind them. Head-to-head
and recent form may take at most a quarter of the trust budget each, and only at
a full sample; the matchup model always keeps at least half. A projection is one
opinion, three that agree are a trend.

**Confidence only ever falls.** The win probability sets the ceiling — HIGH at
58%, MEDIUM at 54.5%, LOW at 52% — and each doubt knocks it down a step:
signals pointing different ways, thin inputs, a projection implausibly far from
the market. Nothing knocks it up. That asymmetry is deliberate. Four separate
faults in this model's history all presented as unusually high confidence, so an
exceptional number is a reason to check the inputs before it is a reason to bet.

**Impossible numbers name themselves.** Every field has a physical range —
not "unlikely", *impossible* — and anything outside it is flagged by name, marks
the offending box on the form, and costs a confidence band. A typo does not
announce itself; it gets absorbed. An average of 401 innings per start was read
as "this starter goes all nine", which took the bullpen out of the calculation
and moved the projection half a run, because 401 clamps quietly to 9.

**Park factors apply only to the park being played in.** A team's own home park
does not adjust its season rates here. That costs some accuracy for road teams
from extreme parks, and removes a per-team input that is easy to enter on the
wrong scale and silently ruinous when it is.

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
