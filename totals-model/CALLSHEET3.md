# Call Sheet 3.0 — MLB, NHL and WNBA on one page

`web/callsheet3.html`, published as its own artifact. Built 1 October 2026
for the start of the NHL season, as MLB and NHL only; the WNBA button was
switched on the same day when the user asked for all three books on one
page, to keep one log. The hockey book is priced from **BetMGM**.

- Engine, Python: `totals/nhl.py` (35 tests in `tests/test_nhl.py`)
- Engine, browser: `web/nhl.engine.js`, ported line for line
- Page: derived at build time by `tools_build_callsheet3.py`
- Fixtures: `tools_gen_callsheet3_cases.py` → `web/callsheet3-cases.json`
- Browser harness: `tools_check_callsheet3_page.js` (889 checks)

## How the page is built

3.0 is **derived from 2.0's sources, not copied**. The build reads
`web/callsheet2.head.html` and `web/callsheet2.tail.js`, applies a fixed
list of edits — each anchor must match exactly once, or the build stops and
names the one that did not — inserts the NHL form sections from
`web/callsheet3.nhl-fields.html`, and places the NHL block after Call Sheet
#1's engine block. So a fix to 2.0 reaches 3.0 on the next build, and a
change to 2.0 that would silently break 3.0 breaks the build loudly instead.
The page is head + ENGINE BLOCK (verbatim from `fullgame.html`, byte-checked
by the harness) + NHL BLOCK (verbatim from `nhl.engine.js`, byte-checked)
+ tail.

The NHL block changes nothing inside the engine block. The goal
distribution is registered by reassigning `splitFor` (a function declaration
is a mutable binding in the same scope), the plausibility windows are added
to the engine's `PLAUSIBLE` object, and the team table gets an NHL page the
same way. The Python does the equivalent through `fullgame.register_split`.

The MLB and WNBA pages are Call Sheet 2.0 to the digit: their fixtures in
`callsheet3-cases.json` are 2.0's, unchanged. **Load a backup** takes a 3.0
backup as a restore (it replaces the card) and a 2.0 backup as a move: its
rows, baseball and basketball alike, join the card, a matchup already here
(same sport, teams and date) is left as it is, and incoming rows take fresh
ids. So the 2.0 log can be brought over more than once without doubling.

## The hockey book

Same architecture as baseball. The market total, de-vigged, is the anchor
and carries the dominant weight (4.0). Everything else is a differential.

**Goalies** are the starting pitcher. A save percentage is shrunk toward the
league (.898) by the shots behind it, exactly as an ERA is shrunk by its
innings, and the constant is derived the same way: goalie talent is spread
about .008 of save percentage, a proportion's noise over n shots is
p(1−p)/n, so a goalie's own number is worth half the league prior at about
1,430 shots. The league figure was .905 a priori until 5 Oct 2026, when the
slate's first 62 goalie lines (37,931 shots, this season blended with half
of last) averaged .898 shots-weighted; against .905 every goalie read cold,
every total leaned over, and #1 called BET on the over in 8 of the first 31
games (3-5). It is measured on the card's starters, so it is the prior for
a named starter; re-measure at the end of the month. Each goalie is read
against the league's shot rate — the opponent's shot rate was removed on
7 Oct 2026 (see the backtest below). A league-average goalie moves the
number by exactly zero. Weight 1.6, measured on 7 Oct 2026: the detail
pass named every starter of two seasons, each line built the way the
sheet builds it (this season to date plus half of the season before,
shrunk, from the user's MoneyPuck goalie files for 2023-24 and 2024-25).
Over every game the lean was near null (slope +0.31 in 2025-26, −0.25 in
2024-25; pooled +0.07), and the backup flag explained it. With **two
regular starters** the lean ran the right way both seasons (+0.07 and
+0.92; pooled +0.55 on 1,744 games, 561-496 betting a tenth of a goal of
lean, 53.1%). With **a backup in net** it ran against, both seasons,
whichever goalie's line was asked (767 games). So goalies are scored at
1.6 with two regular starters and **not scored with a backup in net**,
where the backup delta carries what the backtest found. One goalie alone
is scored against a league-average partner, with a note.

**Whose line is on the card.** On 11 Oct 2026 the season ledger's detail
pass (every game's actual starters) was matched against the card's first
150 goalie boxes, each box's number rebuilt for every goalie on the club:
101 boxes held the goalie who played, 42 held the **other** goalie's line,
7 could not be matched, and many of the 42 had Confirmed ticked. The
record did not hinge on it (totals went 13-20 with both lines right and
16-19 with one wrong; the over bias was the loss), but a quarter of the
scored input was the wrong man. So: the slate writes every goalie on each
club into the row (`ngoalies`, with his line, starts and the club's
starts) and the named starter's name (`agname`, `hgname`); the Goalies
card shows **Who is in net** for each side, and a pick fills the line,
writes the name and sets the Backup box by the rule; the morning grade
file carries **who actually started** from the box score (`starters`),
the row keeps him (`agstart`, `hgstart`) and whether he matched the
carded name by last name (`agok`, `hgok`), the row's total is chipped
"goalies right" or "goalie line wrong", and the total tile keeps both
records. The engines do not read the names; nothing scores differently.

**The one input a hockey market prices imperfectly is a late change in
net.** The sheet says out loud when a goalie is not confirmed, and the
slate names the likely starter; the user confirms on the daily sites.

**Special teams** (both power plays, both kills) are shown, not scored,
since the detail pass of 7 Oct 2026: each side's power play and kill to
date, through the gap the sheet used to score, ran the wrong way against
2,445 closing totals (slopes −0.20 and −0.51 by season; the power-play half
−0.06/−0.47, the kill half −0.43/−0.54). The market has them. **Last ten**
is tagged as in MLB; **head to head** is shown, not scored. **Back to
back** is shown, not scored: its usual consequence, the backup, already
arrives through the goalie line, and its effect on the total has a
disputed sign.

**A backup in net** is the one flag the detail pass found. A starter with
under 30% of his club's starts, ten starts in, is a backup; with ONE
backup in a game the total landed 0.18 under the close (737 games, the
under 396-341, 53.7%; −0.19 and −0.18 by season, at every threshold tried;
the mean close in those games 6.21 against 6.02 otherwise). The market
bumps the total for a backup and bumps it too far. One backup puts a
tagged −0.15 on the line (sized under the measurement; it cannot buy a
band) and the total tile keeps the under's record on these games. When
the backup's own line reads **cold** (his shrunk save percentage costs
more than 0.05 goals against a league goalie) the market over-bumped
harder: 182 games landed 0.44 under the close, the under 100-74 (57.5%;
−0.53 and −0.39 by season), against 0.10 under and 52.6% for a warm or
even backup. A cold backup takes −0.25. With a backup in both nets (105
games) the sign flipped on no sample, so nothing moves. The slate ticks
the box from the club's starts; the user fixes it from Daily Faceoff.

The same pass tested the schedule and found nothing to score: three games
in four nights ran 0.13 under (849 games, 52.1%, both seasons, near the
back-to-back label); a road trip's fifth game and later, divisional
games, two-plus time zones of travel, the stretch after the All-Star
break and April all flipped sign between seasons or sat at a coin.

**The goal total is a mixture**: a regulation count (negative binomial at
the Poisson floor, index 1.01) plus the empty-net lump (0.39 expected goals
a game) plus the overtime goal with probability 0.23. The mean of the
mixture is the projection exactly. A total of 6 pushes about 16% of the
time, which is what hockey does. The constants were a priori until 7 Oct
2026, when the league ledger measured them on 2,624 games (2024-25 and
2025-26): 6.17 goals a game (October runs 6.4 both years, the highest
month), 0.39 empty-net goals a game, 22.8% tied after sixty, 28.1 shots a
team, a .898 league save percentage, a first-period share of 0.314 (1.74 a
period, Poisson to the decimal), and a raw spread of totals of 2.31 —
narrower than a Poisson, which this family cannot be, so Poisson is the
floor and the probabilities lean a touch toward 50%, the conservative side.
Each constant's line in `totals/nhl.py` says what it was and what it
measured.

**The moneyline and the puck line** are read off the book's own moneyline
through a two-team regulation distribution, with the empty net on the
margin — a one-goal lead becomes a two-goal win 45% of the time, a two-goal
lead a three-goal one 30% — and overtime decided by the regulation win share
compressed halfway toward even. An overtime win is by one and never covers
−1.5. Both markets are **shown, not picked** from the first game, on the run
line's record. **The first period** is the first five: its own market, its
own anchor, the goalie gap scaled by the 30% of regulation goals a first
period carries, a plain Poisson with no empty net and no overtime. Its
anchor reads the two prices **straight, without the wide-hold regression**
(`p1_anchor`): a first-period market carries a seven-cent hold as a matter
of course, and regressing it had the sheet a point or two under the book on
every period, the under always the better price, 25 of the first 26 picks
under (10-15). Never a bet — a regressed lean never clears its price — but
the tile bled for a reason that was not hockey. Off since 4 Oct 2026 at the
user's call; one price or none still goes through `fair_total`. The
pickable markets are per sport in one table (`PICKABLE` in 2.0's tail,
carried here): MLB the total and the first five, NHL the total and the first
period, WNBA the spread and the moneyline.

One known seam: the total's mixture uses the league overtime rate (0.23)
while the two-team distribution ties after sixty about 16% of the time —
real teams protect a tie late, which no independent-count model knows. Both
are a priori; the log will say which is nearer.

## The backtest, 7 Oct 2026

Two seasons of closing totals (KillerSports, 2,616 regular-season games
with a close) joined to the two season ledgers. `tools_backtest_nhl.py`
reproduces it. The market at the close went 1,242-1,257-117, residual mean
−0.02, spread 2.31. Each input was asked the question the baseball weights
were earned on: when it said over, did the game land over the close?

| Input, against the close | Games | Slope | Implied weight | Verdict |
| --- | --- | --- | --- | --- |
| Last-ten total average | 2,445 | +0.14 | 0.6 | kept, weight 0.8 → 0.6 |
| Season shot rates (the shots in the goalie gap) | 2,445 | −0.72 | negative | **removed from scoring**; betting with it 49.1% |
| Season goal rates | 2,445 | −0.43 | negative | never an input; stays out |
| Prior-season expected goals, 2025-26 (MoneyPuck 2024-25) | 1,308 | +0.45 | ~3 | one season read right... |
| Prior-season expected goals, 2024-25 (NST 2023-24) | 1,226 | −0.46 | negative | ...the other read wrong: a coin |
| This season's expected goals to date, the slate's input (NST, 2024-25) | 1,223 | −0.31 | negative | **shown, not scored**; a half-goal of lean 19-34 |
| This season's expected goals to date (NST, 2025-26) | 1,222 | −0.08 | none | confirms it: null the second season; a half-goal of lean 22-23 |
| Scratch counts (the officials pass; injuries by proxy) | 1,308 | | | no pattern by how many were out; one season |
| Referee crews: penalty rate to date (shrunk) | 2,343 | −0.45 / +0.46 (pooled −0.08) | none | crews DO predict tonight's penalties (slope 0.8); the total does not follow. Not an input |
| Referee crews: own over/under history | 2,343 | −0.67 / −0.80 | negative | a crew's past overs mean nothing; not an input |
| High-danger chances to date / last-ten xG / PDO to date | 1,223 | −0.03 / −0.20 / null | none | never inputs; stay out |
| First-period last ten (vs the period) | 2,445 | −0.003 | none | **shown, not scored** |
| Head to head, earlier meetings this season | 814 | +0.02 | 0.08 | **shown, not scored** |
| Back to back, the under | 696 | | | 52.6%, a label only |
| October over, blind | 324 | | | 54.9% both seasons (54.7, 55.2); +0.25 tagged delta from 7 Oct... |
| ...October 2026 on the card (closed 6.11, scored 6.08) | 75 | | | **retired 11 Oct**: the market carried it; blind over 33-39-3 |
| Goalie form, last five starts against his own season | 1,764 | −0.02 | none | a cold stretch does not predict over (both cold: 44.7% / 49.1% over); not an input |
| Starter relieved in his previous start | 241 | | | next game 47.6% over, −0.13; no bounce; not an input |
| Rest matrix beyond back to back (both 2+ days, etc.) | 2,616 | | | signs flip between seasons; nothing beyond the back-to-back label |
| Closing total level (5.5 / 6 / 6.5) | 2,616 | | | 5.5s run over the number on average but 50-53% over; 6.5s 46-51%; not an input |
| Favourite size (home moneyline) | 2,616 | | | home +140 or longer: under 55.5% both seasons (277 games); watched, not scored |
| First period by rest, backup, month, close | 2,616 | | | 2+ rate 52.5 / 53.7%; nothing beats the close's own share; the P1 market is priced to the decimal |
| Goalies, the starters' blended lines, every game | 2,616 | +0.31 / −0.25 (pooled +0.07) | ~0.3 | near null until split by who is in net |
| Goalies, two regular starters | 1,744 | +0.07 / +0.92 (pooled +0.55) | ~5 | **kept at 1.6**; a tenth of a goal of lean 561-496 (53.1%) |
| Goalies, a backup in net | 767 | −0.84 / −0.94 | negative | **not scored**; the backup delta carries it |
| Special teams, power play and kill to date | 2,445 | −0.20 / −0.51 | negative | **shown, not scored**; both halves negative both seasons |
| One backup in net, the under | 737 | | | **53.7% (−0.18 under the close both seasons); −0.15 tagged delta** |
| ...the backup's own line cold | 182 | | | **57.5% (−0.44 under; −0.53, −0.39 by season); −0.25 tagged delta** |
| Three in four nights, the under | 849 | | | 52.1%, −0.13; not scored |
| Backups in both nets | 105 | | | sign flipped, no sample; nothing moves |

The first period's share model is dead on: 1.747 predicted from the close
against 1.744 scored, and the 2+ rate climbs with the line as it should.

**In-game structure, measured 11 Oct 2026 for the live project** (not
pregame inputs). A starter faces every shot in about 89% of games; a relief
goalie appears in 10.6%, after the starter has allowed 3.6 on average, and
those games score 7.6-8.0, which is selection, not a signal. The goalie
comes out of the net late for the extra attacker, not for a bullpen: by the
margin after two periods, a tied game scores 2.04 in the third with 0.35
empty-net goals and goes to overtime 35-42% of the time; a one-goal game
2.15 and 0.41; a two-goal game 2.3-2.4 and 0.48; three or more 2.0 and 0.25.
After the first period the rest of the game averages 4.2-4.6 goals whatever
the first period scored, so the first period's goals carry straight to the
final: with 0 in the first the game finishes over the close 15% of the
time, with 1 about 27-39%, with 2 about 54%, with 3+ about 80%. Home teams
score 0.91 of the first period's 1.74 to the road side's 0.83.
The detail pass (`slate.py nhl-ledger --season X --detail`, run by the
user the same night: 2,624 games, every one with both starters, their
lines, power-play goals and penalties) settled the last two scored inputs
and found the backup flag.

**The league constants are measured; the weights are partly measured.** The ledger
fixed the level, the lumps, the period share and the spread on 2,624
games. What it cannot fix without closing lines is how much each input
should move the number off the market. Form (0.6) and goalies (1.6, one
season) are measured; shots, special teams, expected goals, the
first-period form and head to head were measured out. Every weight left
on the hockey card has a measurement behind it, and `tools_audit_nhl.py`
keeps judging them against the record as it accumulates.

## What the user types, from BetMGM

Total and both prices; both moneylines; the home puck line and both prices;
the first-period total and both prices. The slate fills the rest: goalies
(likely starters, save percentage, shots faced), shots for per game, power
play and kill, last ten, head to head, rest days. Closes the next morning
as on 2.0.

**Recent form** (5 Oct 2026, at the user's request) is a panel on the
hockey card, shown, not scored: each side's last five finals with the
score, the score after one period, shots for and against, who started in
net, and how the game ended, read from the box scores and game pages the
slate already fetches. The slate writes both sides as one JSON input
(`nhlform`), so it rides through the form, the draft and the row like any
other box, and the panel adds a summary line per side with flags for 35+
shots against a night, 25 or fewer for, and two goalies used. Nothing in it
moves a number: three games of scores is noise dressed as a trend, and
form measured null over a baseball season. It exists to catch what the
season line hides, and to let the record split on it later — the first
period line is the hockey first-five, and whether a team's recent first
periods say anything about tonight's is a question the log can answer.

**The league ledger** (5 Oct 2026, at the user's request: "build the
league ledger and have the data align to help the model... a path to a
correct total or first period totals like MLB"). `slate.py nhl-ledger`
keeps every regular-season final in the league — period scores, shots,
empty-net goals, overtime or shootout — in `nhl-ledger-SEASON.json`, one
landing page per new game, and prints the league's measured figures against
the hockey book's a-priori constants: goals per game, overtime rate,
empty-net rate, first-period share, first-period goals per game and its
0/1/2+ split against the Poisson, shots per team, league save percentage,
and the raw spread of totals. The constants change by hand when the sample
is there (100 games), with a note, so Python and JS stay one model. The
ledger also feeds the sheet directly: each club's **first-period last ten**
(for plus against) goes on the slate once a club has five finals, and the
first period scores it as an absolute at the form weight (0.8 against the
market's 4.0), both sides or neither — the hockey counterpart of the F5
starters, and the first non-market input the period has. Unmeasured; on
the log to earn or lose it.

**Expected goals** (6 Oct 2026, from the user's download of MoneyPuck's
team file). Every shot attempt weighted by where it came from and how, so
a backdoor tap-in is not a sixty-foot wrister: the best-supported team
input in hockey analytics. The slate fetches the season's team file
(`moneypuck.com/moneypuck/playerData/seasonSummary/<year>/regular/teams.csv`,
or a `teams.csv` saved in the folder when the site cannot be reached), takes
each club's `all`-situations xG for and against per game once it has five
games, and writes the **league mean of the same table** beside them, which
is what the sheet shows it against — the WNBA pace lesson, that a league
constant must come from the table the inputs come from (3.05 is the
fallback). Each side's offence into the other's defence, the gap shown.
All four figures or none.

**Shown, not scored since 7 Oct 2026.** The user saved Natural Stat
Trick's game table (every game of 2023-24 and 2024-25, each side's xG for
and against, all situations), which let the input be built the way the
slate builds it: each club's per-game xG to date, five games in, against
the table's own league mean to date. Against 1,223 closing totals of
2024-25 it ran the wrong way (slope −0.31; betting a half-goal of lean
19-34), in every third of the season but the last. Last season's xG,
which the first backtest had read at +0.45 on 2025-26, read −0.46 on
2024-25 with the 2023-24 table: a coin across two seasons. High-danger
chances to date were null (−0.03), last-ten xG null (−0.20), and PDO to
date said nothing. The market has it; the weight 1.2 is gone, and the
boxes stay on the card with the gap in the why list.

**The crowd** (5 Oct 2026, at the user's request: "add the over/under %
for tickets... can we test this?") is two boxes on the hockey card, over %
tickets and over % money, from the book's splits. With 65% or more of the
money on one side, the total's pick is chipped *with the crowd* or
*against the crowd* and the hockey total tile keeps each line. Shown, not
scored: in baseball no threshold beat a coin, and a ticket/money gap of 20
points or more is only ever a note. The hockey record decides whether
hockey is different.

## The board, for hockey

Same two lists as 2.0, with one rule of its own. On the straight bets a
verdict whose price is steeper than its chance stays on the list in MLB,
on the strength of the MLB record (12-7 on #1's bands). A hockey verdict
has no record behind it — its bands were 3-5 on the first 31 games, every
one a thin over on a league save percentage that read every goalie cold —
so a hockey verdict lists only when it also clears its price. Asked for on
5 Oct 2026: "it gives a bet signal at 53% but doesn't cover". The band
itself is unchanged (BET at 53% on the resolved probability, as in MLB), so
the hockey record stays comparable to baseball's; what changed is that the
band alone no longer puts a hockey row on the list.

## Grading

The final score includes overtime and the shootout — a shootout win is a
one-goal margin, as the league records it — which is what the moneyline and
the puck line settle on. The first period grades from the period score,
typed in the P1 boxes (stored as `f5a`/`f5h`, the period score fields the
card already had), and a period that exceeds the final is `invalid`. The
record keeps an NHL block in goals with tiles for the total, the first
period, the moneyline and the puck line, plus the two fours and beat the
close.
