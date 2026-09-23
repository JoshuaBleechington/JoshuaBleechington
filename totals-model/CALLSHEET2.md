# Call Sheet 2.0

One matchup, every market the book posts on it, ranked. Built 23 Sept 2026 on
top of Call Sheet #1 without touching it.

- Package: `totals/callsheet2.py` (49 tests across `tests/test_callsheet2.py` and `tests/test_callsheet2_team_totals.py`)
- Page: `web/callsheet2.html`, assembled by `tools_build_callsheet2.py` from
  `web/callsheet2.head.html` + Call Sheet #1's engine block + `web/callsheet2.tail.js`
- Fixtures: `web/callsheet2-cases.json` (63 cases) from `tools_gen_callsheet2_cases.py`
- Browser harness: `tools_check_callsheet2_page.js` (1,114 checks)

## What it answers

Call Sheet #1 answers one question about a game: which way does the total go,
and how sure. Call Sheet 2.0 answers a broader one: of everything the book will
take a bet on for this matchup — the **full-game total**, the **first-five
total**, the **moneyline** and the **run line** (spread and moneyline for the
WNBA) — which is the best price, and how do tonight's candidates rank against
each other. Then a **day board** puts every priced market on the card in one
order and marks the four to look at.

## What is carried over unchanged

The total is Call Sheet #1's total. Same engine, same number, same band, same
corroboration gate. The page carries #1's JavaScript engine **byte-identical**
— it is copied by `tools_build_callsheet2.py` out of `fullgame.html` between
two sentinel comments, and the browser harness asserts the two copies are equal.
A change to the engine in #1 is a rebuild here, never a hand edit. The two
sheets cannot disagree about a total.

Each sheet keeps its own log in browser storage and its own backup format.
Nothing here reads or writes #1's card.

## The one idea

Everything other than the total is **priced off the market's own numbers**
rather than forecast from scratch.

The book posts a total and a moneyline. Together those two prices pin down how
many runs each side is expected to score: solve for the pair of team means
whose sum is the market's fair total and whose margin distribution gives the
home side exactly the de-vigged moneyline. Once the two means are known, every
derivative market is arithmetic on the run distribution #1 already uses:

| market | how |
|---|---|
| moneyline | P(home > away) on the pair, with a nine-inning tie split in the ratio the decided games showed |
| run line ±1.5 | P(margin ≥ 2) etc. on the same pair; the tied mass moved to ±1 |
| first five | anchored on the F5 market's own prices, moved by the starters over five innings and the weather over 5/9 of the game; **no bullpens** |
| total | Call Sheet #1 |
| team totals | each side's own mean from the same pair, read against its team-total line; WNBA on a per-team SD of 7.96, derived from the total and margin SDs (4s² = 11.5² + 11.0²) |

So a pick here is never "the model thinks the Yankees are better." It is "the
book's own total and moneyline imply the Yankees cover −1.5 at X%, and the book
is charging a price that needs Y%." That is a relative judgement between two of
the book's own quotes, and it is the only kind of judgement this project has
evidence it can make.

**Nothing per-team we hold is unpriced by the moneyline.** The book knew the
probable starters when it posted it. So the arms, the pens and the lineups move
the total and the first five — where they are a differential against a number
that does not already contain them — and nothing else. The total forecast's
move is applied to both team means in proportion; the split is the market's.

### Team totals come free

Books template team totals off the same total and moneyline, rounded to the
half run. The split here is not rounded, so a team-total row asks whether the
book's rounding went your way. They are marked *derived* and need the
moneyline; a line without prices gets a probability and no rank. Each side is
graded on that side's runs alone, and the two share one calibration tile.

## Ranked by edge, not by probability

The card lists probability first because that is the question being asked, but
it **ranks by edge**: the model's probability minus the probability the price
demands. A −180 favourite at 64% is a 64% chance to hit and a losing bet. A
+105 under at 55.6% is a 55.6% chance and the best bet on the board. Ranked by
probability alone, the top four every night would be the heaviest favourites,
which is the surest way there is to lose money slowly.

Both sides of every market are evaluated and the side with the higher edge is
the pick. That can be the less likely side: over at −160 needs 61.5%, under at
+130 needs 43.5%, and a 52/48 market makes the 48% under the better bet. When
neither side clears its price the market says so and sinks.

A "rank by probability instead" toggle exists so the difference can be seen.
It is not the default and the record is kept on the default.

## Why this is the honest answer to "is 55% a bet"

The question came up on 22 Sept and the data answered it: raising #1's BET
floor from 53% to 55% would have lifted the hit rate by two-tenths of a point
and cost two units, because the 14 cards it dropped were collectively
profitable. The number that decides a bet is not the probability, it is the
probability **against the price**. On the same day a 58.3% BET at −180 was on
the card — a −EV bet by the model's own number, because −180 needs 64.3%. The
band ignored the price. This sheet cannot.

## What has NOT been measured

Read this before trusting a number.

- **Per-team dispersion.** Each team's runs are negative binomial with the same
  dispersion index as the full-game total (2.13), which is what independence
  between the two teams implies. Some of the full-game overdispersion is really
  positive correlation between the teams (park, weather, umpire), not per-team
  spread. This is the simplest assumption, not a measured one. It affects the
  run line most.
- **First-five dispersion.** Unmeasured. Uses the full-game index, which is
  almost certainly too wide for five innings with no pen and no extras. Too
  wide pulls every F5 probability toward 50%, so the error is in the
  **conservative** direction. Once the log holds enough F5 finals it can be
  measured the same way `RESIDUAL_SD` was.
- **Walk-offs.** A home side that wins in the ninth or later wins by exactly
  what it needs (bar a home run). The distribution does not know that, so it
  overstates how often a home favourite covers −1.5. Direction known, size not.
- **The tie split.** Extra innings decide a tie in the ratio the nine-inning
  result showed. Standard, approximate.
- **The WNBA margin SD** (11.0) is inherited from the retired spread model,
  not re-fitted.
- **There is no record.** Zero graded 2.0 markets as of this writing. The day
  board exists to accumulate the record that will say whether ranking by edge
  works. On #1's 191 MLB cards, the sign of the edge did **not** predict the
  outcome: positive-edge actioned cards went 14-10 (+1.50u) and negative-edge
  ones 24-14 (+2.48u). That is small-sample noise on a month where 58.6% of
  all games went over, and it is also the honest prior for this sheet: the
  ranking is theoretically right and empirically unproven.

## The day board

Every priced market on the card for a chosen date, best edge first. The top four
are marked and drawn as cards. A row that shares a game with a higher-ranked one
is flagged *corr* — a run line and an under both cash on a pitchers' duel, so
they are one bet in disguise. Flagged, not removed; the reader decides.

The board reads the **frozen** markets on each row — what the model said when
the row was added — so what it shows today is what will be graded tomorrow.

## Grading and the record

A row takes four finals: away runs, home runs, and for MLB the first-five runs
each side. Every market grades itself from those: totals by the sum, the
moneyline by the sign of the margin, run lines and spreads by margin plus line,
pushes on whole numbers. Units are at the stored price.

Picks are frozen when added. **Rescore** re-runs ungraded rows through the model
as it stands today and leaves graded rows alone — a pick that has been graded is
a record, not a draft.

"Is it working" shows per market: record, *says* (mean stated probability),
*does* (hit rate) with its standard error, and units. Plus the **top-4 rule**:
for every date on the card, the four rows the board would have ranked first,
graded. That is the reason the sheet exists, so it has its own tile. It is
computed from frozen picks, retrospectively — a row added late in the day could
displace an earlier top-4 member, so it is a fair record of the rule but not a
perfect record of what was on screen at bet time.

## Automation: what was possible and what was not

Asked for. Tested. Not possible from this page, in this environment:

- `statsapi.mlb.com`, `stats.wnba.com`, `site.api.espn.com` and
  `api.the-odds-api.com` are all refused by the egress proxy this project runs
  behind (HTTP 403 at the CONNECT). Nothing can be fetched to build a daily
  file here.
- A published artifact page cannot `fetch()` any external host at all — the
  content-security policy blocks it silently — so the page cannot pull odds or
  stats on its own either. The one runtime path is the viewer's own connectors,
  and none connected to this account carries sports data.

What was built instead, which is as automatic as a page with no network can be:

- **Paste-to-fill for the WNBA.** Copy the whole advanced table from
  stats.wnba.com and paste it; the page reads `OFFRTG`, `DEFRTG` and `PACE/40`
  off the header, finds the two team rows by name, and fills all eight boxes.
  It refuses a paste without a `PACE/40` column rather than quietly using
  `PACE`, which is a different number and the bug #1 shipped with.
- **One link per input section** to the exact page the number comes from:
  Outlier, Covers (moneyline, run line, total on one page), Vegas Insider,
  Action, RotoWire lineups and weather, FanGraphs relievers, TeamRankings
  runs/game, Statcast park factors, stats.wnba.com advanced, the WNBA schedule.
- **Copy board as text** so the day's ranking can be pasted anywhere.

If a machine with open network access is ever available, `statsapi.mlb.com`
is free, keyless and carries probable pitchers, pitcher season lines, team
runs/game, venue and game-time weather — everything on the MLB form except the
prices. The Python package is written to take those as keyword arguments so a
fetch script would be a thin adapter. Odds still need a paid or keyed source.

## Verification

- `python3 -m unittest discover -s tests` — 455 tests (38 for this sheet)
- `node tools_check_callsheet2_page.js` — 961 checks: 62 fixtures replayed
  through the page against the package (market order, pick, probability,
  edge, anchored/derived, #1's band on the total), the engine block equality,
  the log/board/grade/calibration flow, rescore freezing graded rows, the WNBA
  paste including the PACE/40 refusal, and the build stamp.
- `node tools_check_fullgame_page.js` — still 1,097 checks; #1 is unchanged
  apart from the sentinel comments and the stamp.
