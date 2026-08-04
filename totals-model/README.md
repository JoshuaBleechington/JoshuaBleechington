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
| `starter_ip` | Innings you expect that starter to go | Their IP/GS this season; 5.0–6.0 covers most |
| `bullpen_era` *or* `bullpen_ra9` | Team bullpen ERA | FanGraphs team relief pitching |
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

---

## Command line

```
python3 -m totals {mlb|wnba} FILE [options]

  --min-ev 0.02        only show plays with at least 2% EV
  --kelly 0.25         fractional Kelly multiplier
  --model-weight 0.5   how far to trust the model over the line (0–1)
  --max-stake 2.0      cap on a single stake, % of bankroll
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
`prob_edge_vs_market`, `ev_per_unit`, `kelly_stake_pct`, `kelly_uncapped_pct`.

## Tests

```
python3 -m unittest discover -s tests -v
```

46 tests, covering the odds math, the distributions, both sport models, the
shrinkage behaviour and the staking rails.

---

## Tuning it

League baselines live at the top of `totals/mlb.py` and `totals/wnba.py` and
should be refreshed once a season:

```python
# mlb.py
LEAGUE_RUNS_PER_GAME = 4.40
RUN_DISPERSION       = 4.0    # variance = mean + mean²/r

# wnba.py
LEAGUE_PACE   = 80.0          # possessions per 40 min
LEAGUE_RATING = 101.0
TOTAL_SD      = 11.5          # spread of a final total around projection
```

The weather coefficients in `mlb.py` (4% per 10°F, 0.8% per mph of wind) are
deliberately small and clamped to ±10%. Treat them as a nudge, not a signal.

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
