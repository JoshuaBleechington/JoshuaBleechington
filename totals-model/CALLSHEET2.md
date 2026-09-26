# Call Sheet 2.0

One matchup, every market the book posts on it, ranked. Built 23 Sept 2026 on
top of Call Sheet #1 without touching it.

- Package: `totals/callsheet2.py` (41 tests in `tests/test_callsheet2.py`)
- Page: `web/callsheet2.html`, assembled by `tools_build_callsheet2.py` from
  `web/callsheet2.head.html` + Call Sheet #1's engine block + `web/callsheet2.tail.js`
- Fixtures: `web/callsheet2-cases.json` (62 cases) from `tools_gen_callsheet2_cases.py`
- Browser harness: `tools_check_callsheet2_page.js` (1,020 checks)

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

## The rail ranks by edge; the board serves both

Both sides of every market are evaluated. The **pick** on a row is the side
with the better price — the higher edge — because that is the honest answer to
"which side of this market, if any". When both sides are priced above their
probability the market says so and its edge is negative.

**"This matchup, ranked" orders by edge.** Probability is the big number on
every row; edge, in gold or red, is the order. This went to chance-to-hit for
an afternoon on 23 Sept and came back the same evening, after the first two
graded games showed the shape of the argument: a 62% favourite at −185 lost
and the edge picks on the same card went 3-1. Two games are not evidence and
the record tiles exist to gather it, but the user chose the edge order having
seen it, and that is the order the rail keeps.

The rail also carries the parlay marks, named so they cannot be misread: a
green *parlay leg* on the game's leg (the side, its chance, its price, its
value ratio and, when #1 has a verdict on it, *#1 says BET*), and an amber
*likeliest … beyond* naming the likeliest priced thing on the game when that
is priced beyond the leg cap. The green mark can sit on the side opposite the
one the row shows, because the row shows the better price and the leg rule
has its own order (below).

**The day board serves both uses.** *The parlay four* is one leg per game,
inside the cap: #1's verdict on the total when it clears its price, else the
best value side. *Best straight bets* is by edge, positive edge only. **One sport only** runs the same two rules once per sport, MLB and
WNBA side by side, each with its own parlay legs (and their all-hit price) and
its own straight bets, so a night can be read as just one sport at a glance; a
column appears only when that sport has games on the date. The table beneath
them orders by chance unless *rank table by edge*
is ticked; the toggle touches the table only.

The moneyline will lead a chance ranking most nights and never an edge one,
and that is not a contradiction: the moneyline is the anchor, so its
probability is the market's and its edge is only ever the vig.

### Call Sheet #1's band stays with #1's side

Found on the first live card with a lopsided quote: the total's BET chip was
printed on the side this sheet had picked for price, which was the opposite of
the side #1 had named. A BET on the over is not a BET on the under. The band now
travels only when the two sides agree; otherwise the row says #1 named the
other side, at what probability, and that this side is picked on price.

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

Every priced market on the card for a chosen date, in one table, with two
groups of picks above it. **Click any pick card or table row** and that matchup
loads into the form.

**The parlay four.** One leg per game, in two tiers.

1. *Call Sheet #1's verdict.* A full-game total that #1 calls BET, STRONG
   BET or MAX BET, on #1's side, when that side also clears its price inside
   the **leg cap** (−170 by default, set on the board and remembered). The
   verdict is the one mark on the board that carries #1's corroboration gate
   — a total is only BET when the inputs agree with each other — and the user
   asked for these legs by name ("the ones saying bet or strong bet").
2. *Best value.* On a game with no such total: the side, of any market priced
   inside the cap, with the highest chance-to-breakeven ratio.

In both tiers only a side whose ratio clears one qualifies. A parlay's
expected return is the product over its legs of (chance ÷ what the price
needs) — the boost multiplies the whole thing and does not change which legs
are best — so a leg priced above its chance drags the parlay down however
often it hits, and a 55% over at −120 beats a 61% dog at −155. Across games
the verdict legs rank first, then by ratio. Fewer than four games qualifying
means fewer legs, and the card says so. Each leg card says what it is — *Call
Sheet #1 says BET on this total and it clears its price*, naming the
richer-priced side it passed over when there is one — and names the likelier
side on the game when that differs. Under the four: the all-hit chance (the
product of the chances), the fair parlay price, **worth N×** — the product of
the ratios, the parlay's value before any boost — and how many of the legs
carry #1's verdict.

How it got here. The first rule was "likeliest leg per game". It went on 25
Sept, after White Sox @ Royals on the 24th: the likeliest leg inside the cap was Royals +1.5 at
−155 (61.3%, ratio 1.008) and the sheet's straight-bet pick was over 8.5 at
−120 (55.3%, ratio 1.014, #1: BET). The game went 9–1 White Sox: the over
cashed early and the run line lost. The value tier came from that; the
verdict tier came the same day, from the user's preference, and was tested
against the two nights logged before it went in: #1's verdict totals went 6-3
on their own; the two-tier rule's legs went 5-3 (3-1 and 2-2) against 4-3-1
for value alone (2-2 and 2-1-1) and 5-3 for likeliest alone; the two-tier
parlays were worth 1.21× and 1.57× fair against 1.34× and 1.60× for value
alone. Neither rule landed a four-leg parlay on either night. Two nights are
not evidence for any of this; the record tile keeps score, and the value
tier is still there underneath for the games #1 has no call on.

On the matchup rail the same rule shows as the green *parlay leg* mark, with
*#1 says BET* appended when the leg is a verdict leg.

**Best straight bets.** The other ranking — the stored picks (better price per
market), positive edge only, best edge first, up to four, same-game rows
flagged. Nothing with a negative edge qualifies, so on a night the book has
every side covered this group is empty and says so.

The table below both groups ranks every priced market by chance to hit (or by
edge, with the toggle) and highlights whichever four the toggle corresponds to.

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

**An impossible first five refuses to grade.** A side's runs after five
innings cannot exceed its final. Five rows on the first graded night (23 Sept)
had exactly that, so the F5 market on such a row shows *F5 > final — recheck*
instead of a result and is left out of the record until the score is fixed.
The other three markets on the row grade normally.

**Graded rows lock.** Once both finals are in, the row's score boxes go
read-only and its remove button disappears; the only way back is the row's own
*unlock*, which exists for correcting a typo and lasts until the page is
reopened. Nothing about the lock is stored — the finals are the lock. Opening a
graded row into the form (from the card, a pick card or a board row) shows it
**locked**: every input, the sport toggle, the paste box and Add are disabled
until Clear, so a record cannot be edited or logged twice by accident.

**Opening a graded row grades the rail.** While the form holds exactly that
row's inputs, "This matchup, ranked" prints the final score and the card's
record above the list, and each market carries its win / loss / push chip and a
coloured edge. The rail and the card row grade from the same finals with the
same function, so they cannot disagree.

"Is it working" is split by sport — an MLB block and a WNBA block, each drawn
only once that sport has a graded market — because the markets differ (first
five and run line are baseball, the spread is basketball), the distributions
differ, and a pooled record would hide which book is working. Each leg of the
two fours is credited to the sport it came from. Within a block it shows per
market: record, *says* (mean stated probability),
*does* (hit rate) with its standard error, and units — and, on a second
line, the same record **by side**: over against under on the totals and the
first five, home against away on the moneyline, run line and spread, so a
17-10 can be read as the unders carrying it or not. The full-game tile also
keeps the record of the rows that carried #1's verdict (BET or better), the
rows the parlay legs lean on. Asked for on 25 Sept.

Two more lines come from **labels**, which are the sheet's way of testing a
hunch without betting on it: a label moves no number, it only splits the
record. *Cold-under profile* (MLB) marks a card with a total of 7 or lower,
wind in at 10 mph or more, both bullpens under 3.75 and at least one team's
last ten below the line — Guardians @ Red Sox on 23 and 24 Sept, 1-0 both
nights, is the archetype, and Rays @ Yankees the same nights, which looked
alike, failed it on the Rays' pen and went 11 and 10. *Same lean* / *split
lean* marks whether the full-game pick and the first-five pick are the same
side; on the first 21 games the full-game pick went 11-4 when they agreed and
2-4 when they split. Both chips show on the rail and on the card table, in
grey, and each has its own record on the two total tiles. If a label's record
holds up at forty or more games it earns a coefficient then; if not it cost
nothing.

A third label came on 26 Sept from asking what the two best days on record
(12 and 20 Sept, 6-1 and 11-3) had in common. Both were over-heavy nights on
which the market agreed with every over: the book's prices leaned over, the
last tens sat above the line, the public money was on the over. Tested on
all 224 graded MLB totals across both sheets: an over with none of those
three against it went 79-44 (64%); an over with any of them against it went
11-15 (42%); unders were 37-38 with or without them. So *over against the
grain* marks an over pick where the two prices lean under (implied over a
point below implied under), the two last tens average a run or more under
the line, or 80%+ of the money is on the under. It shows amber on the rail,
the card table and the pick cards, and has its own record line on the
full-game tile. Unders get no chip: the same signals said nothing about
them. Like the other labels it moves no number; if it holds at forty games
it earns a place in the corroboration gate. Plus the two **top-4
fours**: for every date on the card, *the parlay four* (as the board defines
it, at the current cap) and *best straight bets*, graded. Choosing between them
is the reason the sheet exists, so each has its own tile. It is
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
