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

**The pick** (12 Oct 2026, at the user's request). "This matchup, ranked"
is replaced by one side per matchup: **the likeliest side of any market on
the board**, chance to hit the only key (a tie inside a point breaks toward
the better price), with the kind of game it is (an OVER game, an UNDER
game, first five or first period; a RUN LINE or PUCK LINE game; a
MONEYLINE game; an UPSET game when the pick is a plus-money winner) and a
why in one paragraph: for a total, the projection against the line and the
lean behind it (`totalLean`, the same list the call's why used); for a
period, the projection and the period's own notes; for a side, the sheet's
split and, in baseball and hockey, the plain statement that **the sides
carry no team information on this sheet**, so the number is the book's own
read back. The user asked for it in those words after a Dodgers-Brewers
card ranked a 56% first-five under above a 63.5% run line by edge: "I
don't like how it's so focused on the edge instead of the possible outcome
... pick the best, most likely ... this is the pick because of xyz and this
is an overs, unders, spread, moneyline or upset type of game ... no need to
show the other options." So the other markets fold under the pick, still
scored, graded and on the board, a click away. Below 50.5% the block says
nothing separates the sides rather than naming a coin flip. The consequence
is stated plainly and measured, not assumed: by chance alone the run line
at +1.5 and the big favourite's moneyline will be the pick most nights,
and in baseball and hockey those are the market's own numbers; the record
tile keeps **The pick** as its own line per sport, over every row on the
card, so the approach reads against the whole book from day one.

Later that night, after the sides measure below, the user drew the line:
"I don't want it to pick solely because it looks the best. We have plenty
of data ... make sure this is the focus, no cap." So **the pick is the
likeliest side among the markets the sheet's inputs inform** (`pickable`:
the total and the period in baseball and hockey, the sides in the WNBA
with the ratings on the card), **and only where those inputs move its
chance off the book's own number by a point or more toward that side**
(`PICK_INFO`; the book's number is the two prices de-vigged). A side the
sheet has no information on is never the pick, however likely it looks.
With a line and two prices alone the block says nothing on the card moves
a number; when the inputs lean against the side the book favours without
reaching the other side it says that too. The why now opens with the
book's number, the sheet's, and the lean between them, so "this is the pick
because of xyz" is a sentence with three numbers in it. **The favourite,
by price**: the same night the user asked for the backtest's favourite
table on the sheet ("near the 'is it working' section that I love"), so
the record section carries it per sport over the card's graded games with
both moneyline prices typed, favourite won against implied, the dog +1.5,
the favourite −1.5, the favourite's return, with the two-season close
baseline in grey beside the hockey block. Nothing in it moves a number; it
is the base rate the pick is read against.

**The odds history, measured** (13 Oct 2026, the night the 2025-26 pull
came in: 334 snapshots at noon and 7:30 pm Eastern, 1,319 games, every
retail book and Pinnacle; `tools_backtest_nhl_odds.py` and
`tools_backtest_nhl_sharp.py`, joined to the season ledger and the
KillerSports closes). Five findings, in the order they mattered.

1. **The move is information, and only before it happens.** The line
   moved half a goal or more in 271 of 1,275 games. Where it rose, the over
   at the opener's number went 100-68-1 (59.5%) and at the close 82-87
   (48.5%); where it fell, the under at the opener went 60-42 (58.8%) and
   at the close 48-54. The close prices the move away. Nothing on the sheet
   says which way a line will move: the goalie lean agreed with 73 moves
   and disagreed with 51, and betting it at the opener went 314-292 at an
   assumed −110 (−1.1% a bet); the last ten 46-42, nothing; a backup in net
   moved the line UP 52 times to 20 down, so the backup rule's edge is
   against the bumped close, not the opener, which is where it was measured.

2. **The engine's distribution ignored parity, and the pull caught it.**
   Priced off Pinnacle's mean, a retail number half a goal from Pinnacle's
   looked two points cheap 193 times and went 79-107. The cause: a game
   tied after sixty has an even regulation total and ends with exactly one
   more goal, so overtime lands on the odd numbers. Against 2,616 finals the
   old mixture put 16.3% on six goals where 10.9% landed, 15.8% on five
   where 22.6% did, 14.3% on seven where 19.8% did, and 16.5% on a push at a
   whole-number line where 11.4% pushed. `total_pmf` (and `nhlTotalPmf`)
   now put the tie share on the even regulation counts, the even split of a
   coin scaled to the measured tie rate, and the empty-net goal on the games
   that were not tied: log-likelihood per game −2.247 to −2.186, pushes at
   whole lines 13.2% against 11.4%, and those phantom edges go to ten bets.
   The alternates chips were inheriting the old step; they are right now.
   Every main-line probability at a half-goal line is anchored by the prices
   and barely moves; a whole-number line's push and both sides do.

3. **Pinnacle's shade is the one signal in the pull.** The shade is the
   gap between Pinnacle's two prices in POINTS of implied chance (−125/+105
   is 6.8 points; cents mislead across even, and a first cut in cents put
   every pair with a plus price in the wide bucket). The side Pinnacle
   prices shorter, taken at the best retail price at the same number, went
   650-534-59 (54.9%, +2.5% a bet) over 1,243 closes: flat under two points
   (52.6% on 368), 55.9% at 2-4 points (+4.4% on 435), 54.4% at 4-6, 62.0%
   at 6+ (80 games), and 372-289-32 (56.3%, +3.8% a bet) over the 693 with
   a shade of three points or more; at the opener a shade of 2+ went 54.9%
   on 172 and the rest nothing. Pinnacle's shaded side beat its own
   de-vigged chance by about three points in every bucket, which the retail
   book's own shade did not (its 55%+ bucket did 52%: the public's money,
   not information). So the sheet now chips **"Pinnacle shades OVER by 6.8
   points"** on the total when the sharp box's prices sit three points
   apart, says so in the why list with the measure, and keeps the side's
   record on the total tile ("Pinnacle's shade, 3+ points"): a rule with a
   record line, not a weight, until the record here agrees. Its mean is not the point: Pinnacle's mean and the
   carded book's differ by 0.06 on average and blending them adds nothing
   to the log-loss at any weight. An amplifier on the market's lean
   (p' = σ(k·logit p)) was tried and is noise: a few ten-thousandths of
   log-loss, non-monotone, and losing money at every k.

4. **The best price** at the carded book's number beat the carded price on
   1,506 of 2,624 sides, by 0.6 points of implied chance on average and 1.05
   when it did. The shop chip is worth about a point a bet.

5. **The sheet's inputs against Pinnacle's own mean** read as they did
   against the KillerSports close: the goalies +0.32 a goal of lean (t 0.8,
   implied weight 1.9, beside 1.6 scored), the last ten +0.08, head to head
   nothing, and **season scoring rates −0.51 (t −2.5)**, the same sign and
   size as 2024-25 against the close (−0.42, t −2.1): the market over-moves
   with a club's goals-for and goals-against rates, by about half a goal of
   final per goal of rate lean, two seasons running. The sheet carries no
   season scoring-rate boxes, so this is a candidate input to build, with a
   negative sign, and the first one in a week that two seasons agree on.
   Pinnacle's mean error against the final was 1.835; the close's 1.841.

**The goalie on consecutive nights, measured null and rare** (13 Oct 2026,
`tools_backtest_nhl_goalie_b2b.py`, at the user's word). Two seasons of
starters: a goalie started the day after starting in **63 of 2,616 games
(2.4%)**, never both goalies in one game; a club on a back to back sent a
different goalie out 658 times and the same one 63. The clubs already
manage it. In those 63 the tired goalie's save percentage sat 0.003 ABOVE
the everyone-else baseline against his own season rate (t 0.8 either way;
the baseline itself carries a leave-one-out bias of −.009 from the
shots-to-save-percentage correlation, so groups are read against each
other, not against zero); the total ran −0.13 on a close the market had
already raised to 6.13 against 6.02 elsewhere (t −0.4), the over 29-30-4;
the sides, 40 and 23 games, noise; the first period +0.13 on 63, noise.
Nothing goes on the sheet. The one thing the split confirmed: a club on a
back to back with a DIFFERENT goalie (658 games) ran −0.14 on the close,
the over 47.4%, which is the backup-in-net rule already carried.

**Season scoring rates, faded and tagged** (13 Oct 2026, built the same
night at the user's word: "build the scoring rates input"). The slate now
writes each club's goals for and against per game over its finals this
season and the games behind them into six new boxes (`agf aga hgf hga angp
hngp`; a seventh, `lgg`, is a league override left blank). Both engines
read them as the two offences against the two defences, a projected total
against the league's fixed 6.17, and put the lean on the line with the
OPPOSITE sign at `SCORING_FADE`, −0.25 a goal, tagged. **The measure was
corrected the same night.** The figures quoted when it was built (−0.42,
−0.49, −0.51) were residuals on the OLD distribution's anchor; the parity
fix moved the anchor +0.12 at a 5.5 line and −0.10 at a 6.5, and every
slope on the sheet had to be re-read. Under the current engine the lean
runs −0.29 a goal in 2024-25 (t −1.5), −0.33 in 2025-26 (t −1.6), −0.38
against Pinnacle's own mean (t −1.8), −0.29 pooled (t −2.0); against the
ledger's running league mean instead of the constant it is weaker (−0.21,
−0.27), so the constant is the reference and the slate leaves the league
box blank; by games played it shows no structure (no shrink earns its
place). Same sign two seasons and against the sharp line, a plain
mechanism, and not strong enough alone: scored at the pooled slope less a
shrink, tagged, so it moves the forecast and cannot buy a band by itself.
The same re-read left the goalies and the backup rule standing (two
regular starters +0.26 and +1.04 a goal of lean; one backup 0.19 and 0.16
under the close, the under 55.3% and 52.1%; a cold backup 0.51 and 0.33
under). Typical size: two clubs averaging 3.5 for and 3.2 against project
6.7 against 6.17, a lean of +0.53, so −0.13 on the line toward the under.
Tested in `tests/test_nhl.py`, two engine cases, and the slate's selftest
(the Rangers' fake season reads 4.00 for, 2.00 against over eleven finals).

**Empty-net habits, tagged** (13 Oct 2026, `tools_backtest_nhl_en.py`, at
the user's word: "run the empty-net habits test too"). Three measures
from two seasons of ledger empty-netters. The PULL HABIT, a club's share
of close regulation losses in which it conceded an empty-netter, does not
persist within a season (r +0.11 and −0.08 between halves of 32 clubs) and
moved nothing (slope −0.33 on the total, t −0.7). The per-game RATES do:
both clubs' empty-netters conceded per game ran +0.91 and +1.05 a goal of
final per goal of lean (t 1.5, 1.6), scored per game −1.34 and −0.47, and
the NET, conceded minus scored (trailing late minus leading late), +1.03
(t 2.7) and +0.56 (t 1.4), +0.81 pooled (t 2.9), independent of the
scoring-rates lean (r 0.02 between them; in a two-variable fit the net
keeps +0.81 at t 2.9). Mechanism: a club that trails late pulls the
goalie and concedes, and the market prices the trailing, not the pulling.
One strong season and one weak one: tagged, at half the pooled slope,
`EN_PULL` +0.40 a goal, ten games a side, all four figures or nothing. The
slate fills each club's conceded and scored per game from the ledger
(`aenc aens henc hens`); the games-played boxes gate it. Typical size: two
clubs that trail late, conceding 0.55 and 0.50 and scoring 0.25 and 0.30,
net +0.50, +0.20 on the line toward the over.

**The sides, calibrated: the moneyline was right, the puck line was not**
(13 Oct 2026, at the user's word: "I care more about the accuracy of the
matchup predictions"). The favourite-by-price table says favourites won
three to four points less than their price implied; the sheet never used
the vigged price. Against the de-vigged chance, two seasons fit a
calibration curve of slope 1.07 (se 0.16) and intercept zero: at −150 the
sheet says 57.4% and favourites at −150 won 56.6%; at −200, 63.8% against
63.5%; at −250, 68.4% against 68.4%. Calibrating on one season makes the
other season's log-loss worse (0.6828 against 0.6816). **The sheet's
moneyline chance is the historical rate**, and nothing on the sheet
improves it. The dog +1.5 was another matter: the sheet said 61.0% at −150
where 65.8% covered, 55.1% at −200 where 60.0% did, 50.7% at −250 where
60.6% did. The margin model had too few one-goal games for two measurable
reasons: two independent counts tie 16-18% of the time at these means and
hockey ties 22.7% (flat across the favourite's price), and a two-goal lead
took an empty-netter 69.9% of the time in 509 regulation wins against the
engine's a-priori 0.30 (a one-goal lead 48.6% in 877 against 0.45). Both
are now measured: `final_margin_dist` scales its tie mass to OT_RATE the
way the total's parity fix does, and ENG_GIVEN_TWO_GOAL_LEAD is 0.70. The
shares of one-, two- and three-plus-goal finals go from 35 / 30 / 35% to
38 / 21 / 41% against 41 / 20 / 39% measured, and the dog +1.5 reads 68.0%
at −115 (68.7% covered), 62.9% at −150 (65.8%), 57.6% at −200 (60.0%),
and matches the pooled −200-or-more bucket (55.5%). Two to three points
short in the middle prices remain, on a thousand games each, for another
night (the regulation margin's dispersion is the next thing to measure).
The moneyline does not move: it is anchored on the market's own chance
through `solve_split`. Pinned in `TestTheMarginShape`.

**Travel spots, measured null; the backup rule's anatomy found** (13 Oct
2026, `tools_backtest_nhl_travel.py`, at the user's word: "run the travel
spots test too"). From the schedule alone, 2,577 games with both clubs'
spots: the away club crossing two or more time zones since its last game
(282 games, residual −0.05, west and east split 72-58 and 68-73 over), two
or more zones off its own clock (851, −0.05), 1,500 miles flown (237,
−0.10), the fourth game or more of a road trip (408, −0.07; the home side
won 58.1% against 54.4% priced, a point and a half of standard error), the
first game home after three on the road (417, −0.11), the away club's third
game in four nights (576, −0.05), both rested two days (234, −0.21, t −1.4),
and every continuous measure (miles, zones, trip length) under one and a
half standard errors on the total and on the sides. Null, all of it. One
line stood out, the HOME club's third game in four nights (446, −0.28, t
−2.6, the over 43.6%), and the split explained it: with a day off it is
−0.13 and the second season +0.06; on a back to back it is −0.52 (t −2.9).
And the home back to back itself is the backup goalie: the home club on a
back to back with a regular starter in net ran −0.06 (139 games, the under
51.1%), with a backup in either net −0.53 (115, the under 65.2%, t −2.5).
The backup rule's whole edge sits there: a backup with the home club on a
back to back 65.2% under on 115, a backup with the away club on one 52.7%
on 154, a backup with nobody tired 51.4% on 498. Cut finer it is 61 games
for the home club's own backup (50.0% in 2024-25 on 26, 73.5% in 2025-26
on 35; a cold one 16-3), which is too few and too split to re-size the
rule on. So the rule stays as scored (−0.15 one backup, −0.25 cold), and
the total tile keeps a new watched line, **"home back to back with a
backup, the under"**, so the cell builds its own record before it can
size anything. The pooled rule is where the two seasons agree; this is
where the mechanism probably lives.

**The hockey sides, measured** (12 Oct 2026, `tools_backtest_nhl_sides.py`,
run the night the pick went in, at the user's word: "run the hockey sides
backtest on the ledgers"). Two seasons, 2,616 games, each with the actual
starters and the closing home moneyline (KillerSports; one price kept, a
4.5% hold assumed and the market then calibrated by a logistic fit on
2024-25: slope 0.966, intercept +0.12, a priced market). Every input the
sheet holds, signed home minus away, was read against the market two ways:
the slope of (home won − market chance) on the input, and a logistic model
of market plus input fitted on 2024-25 and scored on 2025-26 out of sample.

| input (home − away) | residual t | coef/SD beside the market (t) | out-of-sample log-loss vs the market | bets at 3+ points, 2025-26 |
| --- | --- | --- | --- | --- |
| goal difference to date | −0.9 | −0.07 (−0.8) | +0.0017 | 9-10, −2.9u |
| shot difference to date | +0.1 | +0.01 (+0.1) | +0.0015 | none |
| expected-goal difference to date (NST) | −0.5 | −0.09 (−1.0) | +0.0026 | 25-20, −0.5u |
| expected-goal difference, last season | −1.6 | −0.11 (−1.2) | +0.0009 | 50-53, −11.7u |
| last-ten goal difference | −1.4 | −0.14 (−1.9) | +0.0034 | 179-196, −35.4u |
| the goalies (starters, blended, shrunk) | 0.0 | +0.08 (+1.2) | +0.0016 | 82-70, +2.8u |
| rest days (capped at 3) | +2.3 | +0.12 (+2.1) | −0.0003 | 158-153, −3.1u |
| back to back, the other side tired | +1.8 | +0.11 (+1.8) | +0.0002 | 159-122, −0.6u |
| a backup in the other net | +2.2 | +0.09 (+1.6) | −0.0011 | 195-166, +14.1u |
| all together (shots out) | | market's own slope stays 1.25 | +0.0046 | 366-318, +20.3u on 684 (±26u) |

Reading: **nothing the sheet holds picks a winner better than the
moneyline.** Team quality to date, expected goals this season and last,
and recent form all carry a negative sign beside the price, which is the
market slightly over-rating the strong and the hot side, and none of them
lowers the out-of-sample log-loss. The goalies, the one input that moves
the total, do nothing to the side. Rest, a tired opponent and a backup in
the other net are the only inputs with a lean in the right direction, each
about two standard errors on the residual and none of them money except
the backup line (+3.9% a bet on 361, one standard error), which joins the
watched list and scores nothing. The all-inputs model's +20 units come on
684 bets with a standard error near 26 and a worse log-loss: noise with a
dog tilt. So the pick's why says, in hockey, that the sides are the book's
own number read back, and now says it as a measured fact.

The base rates the pick leans on, both seasons: home ice 54.2% won against
53.5% priced. By the favourite's price, the favourite won / the dog +1.5
covered / the favourite's moneyline returned: −200 or more 68.2% / 55.5%
/ −4.8% a bet; −199 to −150 58.2% / 62.9% / −7.1%; −149 to −120 54.0% /
68.6% / −5.5%; −119 to −101 50.2% / 70.5% / −4.0%. Every dog at the close
returned −2.7% a bet. **The likeliest side of a hockey moneyline lost four
to seven cents on the dollar at the closing price over two seasons**: it
hit, as a favourite does, and the price was more than that. The pick tile
will show whether tonight's board is any different; the puck line's price
is not in the KillerSports pull, so the +1.5 dog's return waits on the odds
history.

**11 and 12 Oct 2026: the full-game total only, and every total gets a
side.** At the user's request, for a week with the night before as the
first test, the hockey book picked nothing but the full-game total. Cut
short the same day the odds feed went in ("scratch the week trial ... go
back to the other markets"): the window is the two days whose calls were
already made, so those rows keep grading as calls. For games dated 11 and
12 Oct the first period is listed and graded, never a straight bet or a
parlay leg (`NHL_TOTAL_ONLY` in the card script); the moneyline and puck
line were already shown, not picked. Nothing scored changes: the period
engine still runs and shows its number, and games dated 13 Oct onward show
the pick like every other sport. The two days are a clean read of the total
on its own after the October delta was retired and the goalie picker went
in. And that week **every hockey total gets a side**, over or under, no NO
BET (`callOf`): the side the sheet thinks likelier, whatever the price
says. It is named on the total's row ("the call"), listed in the straight
bets under its own CALL tier after the verdicts with a note saying whether
the price agrees, and the total tile keeps the calls' own record line
("the call, 11-12 Oct"). A call whose price is steeper than its chance is a
call, not a bet, and the note says so. **The one it likes most**: among
the night's hockey totals (verdicts and calls) the strongest lean, highest
chance then edge, gets its own colour on the straight-bets card, a "★
LIKES MOST" label, and a why (`callWhy`) built by re-scoring the row from
its inputs: the market's own fair number against the line and which side
is juiced, each scored input's lean against it with its weight, every
delta on the line, and whether the price agrees. Asked for 12 Oct: "the
one it really likes, have it put a colour and why". Later the same day,
for the week: a hockey matchup's ranked list is the **full-game total
alone**, over or under (the other three markets stay scored, on the row
and on the board); **every** call carries the why, not only the
favourite; the **last five** from the form panel are read against
tonight's line as a trend in the why list (shown, not scored; the last
ten carries the scored form); and the other markets feed the total's call
through the **first-period market read as a second estimate of the game**
(`p1mkt`, weight 0.5, tagged, both engines): the period line's de-vigged
mean over the measured 31.4% share, plus the empty-net and overtime lumps,
is what the period price implies for sixty minutes. A big road favourite
(home +140 or longer) gets the watched note (unders 55.5% on 277 games).

**The forecast, betting aside** (11 Oct 2026). The rail's top line says
what the sheet expects to happen apart from any price: each side's
expected score where the sides are modelled, the projected total, the
period projection (first five, first period) and the winner's chance from
the moneyline market. Each row stores it as `proj` (t total, h/a sides, q
period, ph the home side's chance) when it is added, and the record block
for each sport keeps the forecast's own scorecard: how far the projected
total lands from the final on average against how far the market's line
does, how often it is closer than the line, its bias and the line's, the
winner called against the favourite, and the period projection against
its line. Rows logged before the line are re-scored from their inputs
with today's engine and say so. This is the honest frame for "is the
machine accurate": the market is the best public forecast, the sheet is
the market plus what the backtest let through, and the scorecard says
whether that addition is worth anything as a prediction. The ranked list
below it is a different question: it is ordered by **edge**, the gap
between the sheet's chance and the price, so the #1 market is the best
bet, not the likeliest outcome; the day board's toggle orders that table
by chance to hit instead.

**The odds feed** (12 Oct 2026, The Odds API, at the user's request). The
sheet's rule that the slate never carries a line or a price is retired:
`slate.py odds` writes `odds-DATE.json` with, for every game of the day,
the main total and both prices, both moneylines, the run or puck line and
its prices and the period total and its prices, from the first of the
user's books that prices it (Fanatics, then BetMGM, then the shops), plus
every book's price on every side as JSON in the hidden `odds` box. The
loader fills blank boxes and never a typed one; a second file for the same
game merges into the pending entry instead of replacing it, so the slate's
goalies and the odds file's lines meet on one Fill form. The **opener** is
the first number the script saw for the game (`odds-log.json`), the
**close** the last, attached by the grade run and filled into the CLOSE
box if blank, so the "beat the close" line grades itself. The rail names
the **best price** on the listed side at the same number across the books
and the edge there. Nothing scores differently; the line box is still the
book's main market, typed by a script instead of a hand.

**The rest of the subscription** (13 Oct 2026, "make sure we aren't
leaving anything on the table"). Four more things the feed carries, all
shown and none scored. **The sharp line**: Pinnacle rides in the book list
and is never carded; its total and prices sit in the hidden `sharp` box,
the rail chips the gap in green when its number differs from the card, and
the odds log keeps the gap every night so it can be measured before it
moves anything. **The alternates**: every number the books post on the
total, with the best price at each, priced by the sheet's own projection
(`splitFor` on the row's projected total); the rail shows the two nearest
numbers on the listed side with the sheet's chance there and the edge, so
the under at 6.5 is seen with its price while the Line box stays on the
book's 5.5 (the thing the user did by hand on Senators at Devils, 12 Oct,
and got an alternate-line band for). The row still ranks the main number.
**The book's split**: each side's own total at the carded book, beside the
sheet's own split bar. **The credits**: the run prints what it cost and what
is left, from the response headers, against the 20,000 a month plan. The
**history mode** (`slate.py odds-history --season`) pulls a past season's
totals at noon and 7:30 pm Eastern, every book, ten credits a snapshot,
about 3,700 a season, asking first and keeping 3,000 for the nights;
`tools_backtest_nhl_odds.py` joins the file to the season ledger and
measures the opener against the close, the move's direction against the
final, and Pinnacle's gap and lean against the final. Not run yet: the
user pulls the file and the table goes here.

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

**Two corrections the 13 Oct 2026 card asked for.** The user's card that
night carried ten Backup ticks on sixteen games, three of them on the
club's starter (the rule needs ten starts, the clubs sat at five to seven,
so every tick was by hand), and the odds run had written one book's
alternate first-period number (2.5 at +240/−325) onto all sixteen rows
because the carded book posted no period total. So (1) the why list now
calls out a Backup tick on a goalie who holds half or more of his club's
starts, with the instruction to untick it unless Daily Faceoff names
someone else; (2) a period line whose two prices sit 25 or more points of
implied chance apart (`P1_ALT_GAP`; a main period line sits within 15 on
1,000 carded periods, an alternate at 40 or more) is named an alternate
number in the why list and is NOT read into the projection: a proportional
de-vig of a +220/−300 pair leaves too much chance on the long side, and on
the card the sixty-minute read off an alternate sat +0.24 above the
full-game anchor (16 games) against +0.08 off a main line (81 games, where
the read's lean has predicted nothing yet, 18-23 over when it sat high);
and (3) the odds run takes the period line most books post both sides of
(`odds_main_line`), priced at the carded book when it posts that number
and at the first listed book that does otherwise, with a note naming the
book.

**The context card** (14 Oct 2026, at the user's word: "little bits of
info like Bruins have the 4th worst defense in the league... with the
tag, it tells you what the sheet already did with the fact"). The slate
ranks each club against the other 31 on the numbers it already holds,
from one table each: scoring rates, the last ten and empty-net habits
from the league ledger (`nhl_ledger_tables`), shots and special teams
from the team summary, expected goals from MoneyPuck's table, and the
named goalie among the goalies with 100 shots or more from the league's
goalie report (`nhl_goalie_summary`, one call). A club gets a line when
it sits in the top or bottom eight of the league (`CTX_NOTABLE`, with
`CTX_MIN_CLUBS` 16 ranked before anything shows); the goalie always; a
back to back as a label. Each line carries a status and a tag
(`CTX_TAGS`): **scored** at its weight (the goalie line at 1.6, the last
ten at 0.6, the empty-net habit at +0.40), **faded** (scoring rates: the
market over-moves with them), **shown** (expected goals, special teams,
shot rates: null or the wrong way against the close), or a **label**.
The lines ride in the hidden `nhlctx` box as JSON like the form panel,
and the sheet's Context card renders them scored first with a badge and
the tag under each. The engine never reads them: "4th worst defence" is
what the public bets and the book shades to, and the card's job is to
say so beside the fact.

**Goals saved above expected, measured 14 Oct 2026** (at the user's word:
"run the GSAx goalie test tonight"; `tools_backtest_nhl_gsax.py`). The
platforms rate a goalie by goals saved above EXPECTED, crediting the shots
he faced for how hard they were; the sheet blends half of last season's
raw save percentage into each starter's line to date. MoneyPuck's goalie
files for 2023-24 and 2024-25 (xGoals, goals, shots, all situations) were
joined to the two ledgers by player id, 1,683 games with two regular
starters and both goalies in the prior file. The GSAx prior is the weaker
one: last season's raw line alone had a slope of +0.72 on the close's
residual (t 2.3), last season's GSAx +0.52 (t 1.6), and with both in one
regression the raw line carries it (+0.89, t 1.7) and GSAx goes negative
(−0.22). Swapping GSAx into the sheet's blend took the slope from +0.71 to
+0.61. The two priors agree at r 0.80 and differ by a tenth of a goal on
an average night. Both read right in 2025-26 (+1.06 and +1.08) and both
read nothing in 2024-25 (+0.07 and +0.24). Shot quality does not improve
the goalie prior against a market that already prices the goalie; the
raw line stays. The same run put the sheet's goalie lean to the honest
test, bet AT THE LINE rather than signed against the anchor (which had
counted the 82 games that landed on the number, all of them on the
anchor's side): a tenth of a goal of lean went 549-537 at the close, −38
units; three tenths 143-120 on 263 games, +10. The goalie line is a weight
in the blend at 1.6, not a bet on its own, which is how it is scored.

**Time-decayed form, measured 14 Oct 2026** (at the user's word: "run the
time-decayed form test too"; `tools_backtest_nhl_form.py`). The pro
models weight every game by how long ago it was, a half-life in games or
days, where the sheet takes a flat average of each club's last ten totals
at weight 0.6. On 2,445 games with five or more played by both clubs:
flat windows of 5, 10, 15, 20 and the season, exponential decays with
half-lives of 3, 5, 10, 20 and 40 games and of 7, 14, 30 and 60 days.
Every variant's slope on the close's residual sits between +0.06 and
+0.17 with a t of about one; the flat ten reads +0.06 (t 0.6) under the
parity anchor. The longer windows read +0.3 in 2024-25 and zero in
2025-26; the short ones read nothing both seasons. The flat ten and a
five-game decay correlate at 0.89 and split the same information between
them. With twenty-one variants tried, the best bet record (a fourteen-day
half-life, +20 units at a quarter of a goal) is what one of twenty-one
coins looks like. No decay beats the flat ten; the input stays as it is.
The same run measured RESIDUAL form, each club's totals against its own
closes, flat and decayed, which is the form a market-aware model would
use and the product the trend platforms sell: null to negative at every
window (season to date −0.20, −0.41 in 2025-26). A club that has been
going over its number does not keep going over it.

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
| Goals saved above expected as the goalie prior (MoneyPuck, last season), two regular starters | 1,683 | +0.07 / +1.06 (pooled +0.52, t 1.6) | | **not an input**: the raw prior measured +0.24 / +1.08 (pooled +0.72, t 2.3) on the same games; raw and GSAx together, raw +0.89 (t 1.7), GSAx −0.22; the two priors agree at r 0.80 |
| ...the sheet's goalie lean bet AT THE LINE, two regular starters | 1,683 | | | a tenth of a goal 549-537 (50.6%), −38u; three tenths 143-120 (54.4%, 263 games), +10u: a weight in the blend, not a bet |
| Time-decayed form (half-lives of 3 to 40 games and 7 to 60 days) against the flat last ten | 2,445 | +0.08 to +0.17, every t about 1 | 0.3 to 0.8 | **nothing beats the flat ten beyond noise** (flat ten +0.06, t 0.6 under the parity anchor); the longer windows read +0.3 in 2024-25 and zero in 2025-26 |
| Residual form: each club's totals against its own closes, flat and decayed | 2,444 | −0.01 to −0.20 (season to date −0.11 / −0.41) | negative | a club's recent over/under record against the market does NOT persist; the trend platforms' product, and it reads the wrong way |

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

## The upset signal, 16 Oct 2026

The user: "I want the model to also look for potential upsets too between
matchups based on certain trends or patterns." The question was put to the
sides backtest's rows (`tools_backtest_nhl_sides.py`, 2,616 games over two
seasons with a closing moneyline): when did the dog win outright more often
than the market priced, and on what signal? The dog's wins against the
market's expectation, by signal (`scratchpad/nba/dig5.py`):

| Signal | Games | Dog wins vs priced | By season | Dog ML at the close |
| --- | --- | --- | --- | --- |
| **The dog's goalie a backup** | 327 | 158 vs 134.0, **+7.4 points (z 2.7)** | +6.3 / +8.3 | **+39.3u** |
| The dog on a back to back | 173 | 83 vs 73.1, +5.7 (z 1.5) | +5.1 / +6.6 | +18.1u |
| The favourite on the road | 931 | 414 vs 390.2, +2.6 (z 1.6) | +2.8 / +2.3 | +11.2u |
| The dog's xG difference better by 0.3+ | 252 | +4.1 (z 1.3) | −7.1 / +12.7 | +8.1u |
| The favourite's goalie a backup | 440 | 168 vs 173.9, −1.3 (z −0.6) | −2.6 / 0.0 | −41.8u |
| The favourite on a back to back | 390 | 138 vs 149.7, −3.0 (z −1.2) | −7.2 / +0.8 | −54.4u |
| The favourite rested 3+ days more | 196 | −4.6 (z −1.3) | −6.3 / −2.7 | −31.7u |
| Two or more against the favourite | 489 | +0.3 (z 0.2) | −3.8 / +4.2 | −24.4u |

The pattern is the one the total showed: the market moves for the
publicised disadvantage and moves too far. A backup in the DOG's net is
priced as if the dog cannot win, and the dog wins 7 points more often than
that, both seasons, +39 units at the closing price. A backup in the
favourite's net, or a favourite on tired legs, has the opposite shape: the
market over-bumps the dog and the dog wins less than priced. Stacking the
signals adds nothing.

**On the sheet.** The dog's backup is scored: `DOG_BACKUP_LIFT` puts +5
points (two-thirds of the measurement) on the dog's win chance, tagged, and
the moneyline becomes pickable on that row, so the dog reaches the straight
bets and the parlay legs when its price agrees. The ML tile on the record
keeps the dog's line on those rows ("the dog with a backup in net W-L"). The
dog on a back to back and the favourite on the road are named on the card's
**Upset watch** note and on the board's **Upset watch** section, not scored.
The favourite's backup and the favourite's back to back are named as NOT
upset signals, so the Backup tick is read the right way round: it is the
dog's tick that matters. The NBA has its own watch with nothing scored
(NBA.md).

## The alternate totals with a verdict, and the likelier parlay four, 19 Oct 2026

The user, testing by typing an alternate number into the Line box: "for the
NHL model add the strong bets, max bets to the cards as well... the Sharks vs
Maple Leafs shows max bet over the 5.5 total." Then: "do the same thing for
the parlay four as well, with the likelier on this game showing the likelier
instead of the edge."

**The alternate total.** The hockey engine now prices every alternate number
the odds file carries on the sheet's side with the same projection split, and
the one that reads STRONG BET or MAX BET with an edge becomes a market of its
own, `alt`: on the rail as a row and as a card under the pick, on the board in
its own section and in the table, and graded as the full game at its own
number on its own record tile, "Alternate totals". It is never the pick and
never a value leg. The band is the chance, as on the main number, and the
card says what that means: at −215 the book already asks for 68%, so a MAX
BET at 72% is four points of edge, and the edge is the figure to read. The
Line box stays on the main number.

**The parlay four.** From today each game's leg is the likeliest priced side
on the game at any price, the alternate included, ranked by chance; the card
says whether the price agrees and names the value side it passed over. Up to
today the four were the best value legs with #1's verdicts first, and under
that rule they went 17-14-2 in MLB and 13-16 in the NHL. The tile is now "The
parlay four, likelier legs" and grades the four as the board builds them. The
honest expectation, from the likeliest-at-any-price record (160-83, −3.9u)
and the two-leg parlays (57-82, −27.6u): four favourites at the book's
prices will hit often and pay less than they should. The record decides.

## The starting five on the NBA card, 20 Oct 2026

The user: "Would it be possible for the NBA model to show the starting
lineup for that matchup as well, maybe next to the who's out section?"

The slate's NBA run now reads RotoWire's NBA lineups page beside the injury
page (`slate.py`: `parse_rotowire_nba`, `nba_lineups`, the row's `nbalineup`
box) and the Who is out card renders it under the injury list: a **Starting
five** block, two columns, each side's five with the position, a badge that
says **expected** or **confirmed**, and the may-not-play men with their
status under it. A side RotoWire has not posted says so. The box rides in
the row with the rest of the slate's fields, so a reopened row shows the
lineup as it stood when the row was added, and the NBA example carries one
(the 76ers expected without Embiid, the Knicks confirmed without Robinson).
Shown, not scored: `nba.engine.js` renders the box in `nbaLineupPanel` and
reads nothing from it. The page's build stamp is 2026-10-20.

The same day, on the Props tab (the user: "for last games for the players,
could you highlight their scored numbers so it's easy to see?"): the why
list's last-games line marks each game's stat in its own box, green when it
beat the prop's line, red when it fell short, grey on the number, a missing
one plain, and ends with a tally, "7 of 10 over 24.5" (`props.engine.js`,
`propsLogGame` and `propsLogTally`). The line is the prop's own, so the
marks read the same way whichever side the sheet took.

**The form's clubs on a card row, 21 Oct 2026.** The user's backup of the
21st had "Islanders ML" and "Islanders +1.5" on Celtics @ Pistons, and
"Celtics ML" on Thunder @ Spurs. The NBA engine's `readNba` took the two
clubs from the form (`$("away").value`) rather than through `txt()`, so when
a slate or odds file merged into a card row and the row was re-scored
(`scoreMatchup`, which points `txt()` at the row's inputs) the moneyline and
the spread were named after whatever game sat in the form at the time. The
sides (HOME, AWAY) and so the grades were right; only the labels were wrong.
Fixed at the source (`txt("away")`), the form's panels no longer redraw
during a row's re-score (`if (!SRC)`), and the page relabels any such row by
side from its own clubs once on load (the build tool's "relabel" patch). The
harness re-scores a basketball row with a hockey game in the form and reloads
a mislabelled one.

## The prop's own panel, and what moves it, 21 Oct 2026

The user: "leave the best bet cards the way they are but when I click one,
could you have it open a page or something with the details of the prop
instead of in the list below... it's a little difficult to read the prop
details." Then: "highlight the areas of the prop bet that are helping with
the prediction the most."

**The panel.** A best-prop card opens the prop over the page
(`#propDetail`, `props.engine.js`: `propsDetailHtml`, `openPropDetail`): the
band, the player with his position and club, the pick in large type with
the result chip when graded, the game and the book's line; six tiles
(chance with the model's and the book's over, price and what it needs, edge,
projection with one sigma, minutes, per 36); the why as a list; the last
games as a table with the marks and the tally; every book's line with the
carded one flagged. Escape, Close, a click outside or a sport button puts it
away. On the 22nd (the user: "the same for the entries on the list so they
are easy to review as well") a row of the Every-prop table opens the same
panel, the inline why row under the table is gone, and **Previous / Next**
(or the arrow keys) walk the table's order from whichever prop is open, the
position shown as "3 of 42"; a panel opened from a best-prop card knows its
place in the table too.

**What moves it.** The slate's `props_project` now writes `base` (his own
rate at his own minutes) and `parts` beside the why: each factor's push on
the projection in the stat's units, the others held, pointing at its why
line. The regulars out, pace and the defence sum from the base to the
projection exactly; last season's prior and the minutes trend (his last
five against the season) say what sits inside the base. The panel ranks
them with a bar, green when the push is toward the pick's side and red when
it is away, names the biggest lever, bolds the two biggest levers' why
lines, and the card carries the top two in a fifth line. On the example,
Maxey over 25.5 with Embiid out: the regulars out +1.8 is the lever, the
Knicks' defence −0.7 and the pace −0.3 lean against, the prior +0.4 and the
minutes trend −0.4 sit inside the start. A props file from before the 21st
has no parts, so its panel shows the why without the ranking.

**The Why's bold lines are the reasons for the pick (26 Oct 2026).** The
user, on a panel whose two bold lines were a regular out (+0.49 per 36,
toward the over) and the pace (×0.954, against it): "are those the two
biggest reasons for the potential over?" They were the two biggest by size
in either direction, which read wrong. Now the two biggest levers toward
the pick's side are bold and green, each with a green tag ("the biggest for
the OVER", "the second biggest for the OVER"; then "colour the ones that
are the biggest for the over too, like green"), the biggest against it
carries a red tag ("the biggest against the OVER") and a red marker, a push
under 0.05 in the stat's units counts as neither, and the Why heading says
so. The bars above are unchanged, and the card's fifth line still names
the top two by size with their signs.

## The blowout test, and the props' centre, 22 Oct 2026

The second night of props (21 Oct) went 321-326 with the BET band 38-53:
seven of eleven games were decided by fifteen or more and the overs went
105-162 in them against 87-65 in the close games. The user: "go ahead and
build the blowout test and let's see if it matters."

**It does not matter as an input.** `tools_backtest_nba_blowout.py` joins a
season's ledger to the closing moneylines (the expected margin through the
engine's 12.5-point normal). Regulars do lose minutes with the expected
margin, 0.08 a point over two seasons (t −9; 1.4 minutes at twelve or more,
the favourite's regulars 1.9), and the bench gains 0.09, in both halves of
both seasons. But the stat projection's miss is flat across the expected
margin, the over rate 46-47% in every bucket of both seasons, and shading
the minutes by the fitted slope made the second half worse (points at 12+:
+0.17 to +0.82). The blowouts hurt after the fact, regulars −2.1 minutes
and −0.8 points in games decided by 15+, but the spread does not say which
games those will be: the 12+ bucket blows out 53% of the time against 31%
for a pick-em, and on the 21st two of the seven blowouts were favoured by
nine or more. Measured, not an input.

**What the test found instead.** The over rate at the projection's own
mean was 46-47% in every bucket, so the problem was never the blowout: a
box-score stat skews right, the mean sits above the median, and a normal
centred on the mean says 50% for a number the man clears 46% of the time,
41% on threes. The books post the median. `tools_backtest_nba_props_median.py`
measures the shift of the centre that puts the over rate at 50%: 0.08
sigmas on points (0.09 and 0.07 by season), 0.11 rebounds, 0.14 assists,
0.23 threes, 0.05 combined; a shift fitted on the first half of 2025-26 put
the second half's over rate at 50 ± 3 on every market. The slate now reads
the chance around the median (`PROPS_MEDIAN_SHIFT`; the projection shown is
still the mean, the why line names the median). Re-scoring the first two
nights' 829 props with the shift, their own lines and prices: 452-377
against 423-406 as shipped, the BET band 44-47 against 51-57, the sheet's
say-so 55.5% against 54.5% done where it had said 55.7% and done 51.0%. The
overs in the BET band fall from 88 of 108 to 62 of 91.

**The tab's own Is it working block**, the same day (the user: "a section at
the top similar to the 'is this working' on the other models... jazz that
up with some colors"). `propsRecordHtml(true)` renders at the top of the
Props tab: every prop with a side, then the BET band, the LEAN band and the
no-edge side as their own tiles; by market; by the edge the sheet claimed
(ten points and up, six to ten, three to six, under three, none); by the
centre the chance was read around (the mean to 21 Oct, the median from the
22nd, told apart by the why line, so the fix gets its own record from day
one); night by night as a table with the BET band beside; and says against
does by the chance claimed. In colour: a tile's record and units green when
the units are up and red when down, with a bar on its left edge, and does
marked green or red against says in the tiles and the tables. The card's
own block below the record stays as it was.

## The referees as a watch, 22 Oct 2026

The user, asked when the referee data would be scored: "add the tile so I
can see it build. I want to see what impact the refs have on the game,
even if small but can be measured." Under the NBA record, three tiles by
the crew's lean in the frozen two-season table (`nbaRefsWatchHtml` in
`nba.engine.js`, patched into `renderCalib` after the NBA verdict): crews
leaning over, crews with no lean, crews leaning under. An official leans
at 1.5 sigma over or under the close across 2024-25 and 2025-26 (the z of
his record in the row's referee table), a crew by the sum of its three.
Each tile: the season's over-under count against the close, the past
table's pooled over rate for those crews against this season's, the points
over the close a game, and a flat bet on the lean's side at −110. Rows
count once they carry a crew, finals and a close; the verdict names the
graded games missing either. Shown, never scored: the decision stays the
season's end, and the harness grades an over crew and a no-lean crew.

Reworked the same evening (the user: "add some color to the refs section...
a little more organized... have the ref section on the matchup be
highlighted, and if those particular refs are a signal or alert"). The
block is two tables now: one by the crew's lean (games, over-under, what
the past table says, this season's over rate in the over or under colour,
the standard error, points against the close, a flat bet on the lean), and
one by official for everyone who has worked a graded game on the card, the
leaning ones first, with his past record and z, this season's record, over
rate and points. On the matchup the crew gets its own card, **Referee
stats**, above Context (the user, later the same evening: "change the name
from context to Referee stats... make sure that's set up for all NBA games
moving forward"): the crew line highlighted in the lean's colour with a
badge ("Crew leans OVER · z +4.4", or "Crew even"), each official a chip
with his past record, his own lean and this season's record, the Crew box
and the league's link under it (`nbaCrewPanel`, `nbaCrewDetails`,
`nbaRefLookup`; the sentence itself is unchanged so the record's text is).
The Context card keeps the clubs' ranks alone. Every NBA row with a crew in
its box renders the card; a crew of three officials inside 1.5 sigma reads
"Crew even" in grey, which is the usual case. Under the chips, a **crew
call for tonight** (the user: "maybe a little prediction too"): the crew's
free throws against the league's (the one thing a crew predicts, t 7.3),
their points a game against the league's by history (the total did not
follow, t −1.0), and the past table's pooled over rate with these three as
a soft lean. Never scored; the referee watch on the record is the test.

## The team totals and the gap rule, 26 Oct 2026

The user's period-line pulls measured the simulation's derivative calls
(NBA.md, "The period lines"): the first half a coin, the quarters a watch
at best, and the team totals the one inefficiency, over two seasons. The
Simulation card's table gained two rows, the away and the home team total,
with the book's main line from the row's odds JSON (`nbaTeamTotalLine`:
the carded book first, the point whose two prices sit closest together),
the chance from each view, and under the line the number the game's own
total and spread imply with the gap (`nbaTeamTotalGap`). A gap of a point
or more is a call by the **gap rule**, chipped on the row; inside a point,
no call. The record block grades the sim's team-total calls like the
others and keeps the gap rule's own tally by side, with what two seasons
said beside it. The rule needs the team totals on the row, which the odds
run brings (`team` in the odds JSON), so a game added by hand shows "no
line on the row".

Withdrawn 11 Nov 2026: the two seasons read one book's alternate points
kept with another point's prices. The gap is a watch and the anchored home
team total carries no weight of its own; see "The team-total gap becomes a
watch" at the end of this file.

## The Simulation card, 25 Oct 2026

The user: "a simulation model for the super model... run the matchup 500
to 10,000 times to best determine how the game will likely end, tied in as
a scored metric, with confidence levels." The engine is `slate/nbasim.py`
(NBA.md, "The simulation"); the slate run plays each game NBA_SIM_RUNS
times, twice, and the row carries the results as histograms in the hidden
`nbasim` box: the total, the halves, the quarters, the margin and the team
totals, for the sim's own view and for the market-anchored one, plus the
anchor, the profiles, the shrink and the bands.

The card reads the chance of any line off the histograms, so nothing is
re-run in the page and the calls follow the line on the row as it is
typed. `nbaSimPanel` draws the head line (the runs, each side's mean, the
median total with its middle half, the margin, the home win chance,
overtime, the anchor), a table of every market with the own view's chance
and the anchored one for the row's line, each a chip with its side and
its band (LEAN 60, BET 65, STRONG 70) and the "worth" beside it (the chance
shrunk by what the replay found), then the medians by quarter and half,
the team totals and the fourth's share, and the two profiles.

`nbaSimRecordHtml` is the record: every graded NBA row's calls at LEAN or
better, from the stored histograms against the lines the row carried,
graded off the finals (the half from f5a and f5h, the spread and the
moneyline from the margin), tallied by view, market and band with says,
does and units at the row's own prices. It sits under the NBA verdict and
the referee watch in Is it working, and it is what the user asked for: a
scored metric from the first night, honest about what 70% means. The
example row carries a seeded block built by nbasim at build time
(`nba_example_sim`), so the Example button shows the card and the harness
can check it.

## The graded night joins the last games, 25 Oct 2026

The user, on a graded prop from the 24th whose panel listed the 21st and
the 23rd: "they only show the last date of 10/23 and not 10/24 for the
props that were on yesterday." The last games are the history the call
was made from, as the props file carried them, and the page never
rewrites a call; so the graded night goes under them instead, as its own
row: the date, the opponent with a "this game" tag, his minutes from the
grade file's box line (kept on the row as `amin` from today; older graded
props show a dash) and the stat marked against the line like the rest,
or DNP for a void. The tally in the heading stays the history's.

The user: "could the older graded props get their minutes filled in
too?" Loading a night's grade file again now fills the minutes in on
props already graded that have none, from the same box lines, and leaves
every result and actual as it was; the message says how many. The grade
files for the 20th to the 24th were rebuilt from ESPN in the container
and sent to him for that (they carry no close, which does not matter: a
grade file fills only blank closes, and those rows have theirs).

## A run without last season says so, 25 Oct 2026

The user's props file of the 24th: 403 props, 140 with a side and 135 of
those "no last season to blend", 263 with no side at all. The run had
read no 2025-26 ledger (the file's date in his OneDrive folder is the
next morning), and because a few dozen players already had sixty minutes
this season, enough projected that nothing looked wrong. The 23rd and the
25th blended normally. The load message now says when a file's run read
no last-season ledger: by the file's own `ledgers` block when it has one
(last season with zero games), or, for an older file, when more than half
the projections carry "no last season to blend". It counts the thin
projections and the props with no history, names the file and says to
run the props again before tip. A rookie's "no last season" is normal and
does not trip it; the test is the run, not the player.

## The page's memory moves to IndexedDB, 25 Oct 2026

The user's 10/25 backup: 298 card rows (1.9 million characters) and 2,171
props (3.8 million). Browsers count localStorage in two-byte characters and
stop at 10 MB in Chrome, 5 MB in Safari; the page was at 11.5 MB. The
props save, wrapped in a try/catch, had been failing quietly for about a
day, and the morning the page "showed nothing from 10/24 and would not
change the date" was that wall (he found his way back; the backup he sent
is the in-memory state, not what the browser had kept). A season of props
at 400 to 750 a night was never going to fit, so the storage moved rather
than the data shrinking.

`web/store.js` is `smStore`: the card, the props and the slate live in
IndexedDB, which holds hundreds of megabytes, behind a cache filled before
the page's own code runs, so every read stays synchronous and the page's
code changed only in name (the build turns its 14 `localStorage.` calls
into `smStore.` and wraps the page's one closure in `smStore.ready.then`).
A write updates the cache and goes to the database behind it; a failure
shows on the Saving tag instead of vanishing. The draft and the table
view stay in localStorage. On the first load, whatever the old keys hold
in localStorage moves over and is cleared from there, which also frees
the quota the small keys share. A browser without IndexedDB keeps using
localStorage as before. The harness goes through the store too, and
checks the move, a 6 MB props list through a reload, and that nothing is
left in localStorage.

## A game under way is left alone, 23 Oct 2026

The user, with the Bulls at the Bucks in the second half: "the Bulls game
keeps showing props when I run it for the other games... would that be a
reason when I pulled the odds and slate it shows them again?" It was, and
it mattered: The Odds API lists a game in play with in-play lines, so a
late odds run overwrote the log's close with a live number and a late
props run replaced the pre-tip calls with live ones. `odds_started` now
skips any event whose start is at or before the run (the odds run does
not even spend the credit), the log keeps the last pre-tip snapshot as the
close, and the props run says which games it skipped. The page guards a
file from an older run the same way: a game whose tip is at or before the
file's `generated` stamp has its props left out, and the message says how
many. The slate itself still lists a game in play (ESPN marks it not
final), which is harmless: the loader only fills blanks and refreshes the
five.

## A later slate refreshes the starting five, 23 Oct 2026

The loader fills blanks and never overwrites a filled box, so a slate
loaded an hour before tip could not bring the confirmed lineup onto a row
carded in the morning. The starting five is display only and changes
through the day, so from today a newer slate's `nbalineup` replaces the
row's (the build tool's "lineup refresh" patch beside the goalie-confirm
rule); every other box keeps the rule, and the record stays of the row as
logged. The user's question of the 23rd, "run the slate and the props before
the games again and then add them, then run the odds?", is answered in
`slate/README.md` step 5: the close comes from the odds log, not the page,
so the one thing a game day needs is an odds run after the games are
listed. The harness loads two slates onto a carded row and reads the five
from the second and the rest days from the first.

## The Every-prop table's view, 22 Oct 2026

The user: "is there a way for me to rearrange the rows? For example, all
the rebound props, or the points for a player, by chance percentage and
band." Every column header sorts (`propsTableRows`, `propsSortValue`): a
first click sorts numbers high to low and words A to Z, a second flips it,
a third goes back to the default, by game then by edge; the header shows
the arrow and the count line says what the sort is. Above the table, filters
by market, band, side and a player's or game's name, with the count as "12
of 111 shown". The view is kept in this browser (`callsheet3.props.view.v1`)
until Reset view clears it; the panel's Previous and Next walk the table as
shown. The harness filters the example to the rebounds, sorts it by chance
both ways, narrows it to Maxey's LEANs and resets.

## The sport buttons, 22 Oct 2026

The user: "rearrange the models to have Player props 1st, NBA 2nd and then
the rest." The buttons read NBA PROPS, NBA, MLB, NHL, WNBA now (the build
tool's "sport buttons" patch). The page still opens on MLB by default and
the MLB button still starts pressed; only the order changed.

## Recent form on the NBA card, 22 Oct 2026

The user: "add in the last 5 games for the teams like you do for NHL, with
the scores like first half, total and spread covered or no, and with a
little color." A Recent form card under Who is out (`nbaFormPanel` in
`nba.engine.js`, the hidden `nbaform` box the slate fills): each side's
last five with a W or L chip and the score, the half with an over or under
chip against the half's close, the total with its chip against the close,
and the spread from the side's view with COVERED or NO, the five summed
above the table. The closes come from the odds log by date and nicknames;
the spread rides in the log from today (the odds run's snapshots now keep
`sp`, `pl` and `rl` with their prices), and a past game without one borrows
the close from the sheet's own card row when the game is on it
(`nbaCardCloseFor`). A game with no close shows its score alone. The NBA
example carries five a side. Shown, not scored.

## The simulation on the prop, 26 Oct 2026

The user: "for the player props, I want to confirm the simulation is being
run for those as well, and I want the results attached to the player props
when I select them to see what the simulation did in regards to how it was
scored for the player prop for that player." The props run plays each game
the same 10,000 times as the slate (NBA.md, "The runs on every prop") and
the file carries a `sim` block on the game row and on every projected prop.
The prop's panel renders it as a **Simulation** section under What moves
it (`propsSimHtml`): six tiles, his club's points in the runs with the
middle half against its points a game by the ratings alone, the sim's
full-weight read of his number against the model's projection, the
**matchup lever** in colour as the one part the score takes (green toward
the pick, red against; none on rebounds), the blowout chance, overtime and
the game's possessions, then a paragraph that says in words what was
scored and what is shown. A prop from a file made before the runs says so
and asks for a props run with the current slate.py. The Example's props
carry a seeded run and the matchup lever, so the panel shows the section
and the harness checks it.

**A later slate on a carded game** (the user: "will the simulation update
when I re-run the games closer to start and determine the final starting
lineups?"). A game already on the card used to keep its first run's
`nbasim` and who-is-out boxes, as it keeps every filled box; now the
injury report (`nbaout`) and the simulation (`nbasim`) follow the newest
slate the way the starting five does, so the Simulation card and its
record carry the run nearest tip. Neither is read by the engine, so the
row's picks do not move; the line, the prices, the ratings and the rest
days stay as logged. The simulation reads ESPN's injury report (Out and
Doubtful), not RotoWire's five: a man benched but active is not an
absence to it. Props reload the same way they always did: an ungraded prop
is replaced by the newer file, its `sim` with it.

## The bets you take, 26 Oct 2026

The user: "add a select or picked option for the props or bets I take,
that way I can see on the page the ones I will place." And: "don't break
anything." So the mark is extra state that nothing scores or grades from.

A **Take** button sits on every priced market row of the day board, on
every pick card (the parlay four, the straight bets, the likeliest side,
the alternate totals) and on every projected prop (the best cards, the
Every-prop table's last column, the prop's own panel). Clicking it marks
the bet and lights the row or card green; clicking again unmarks it. The
button is caught before the row or card underneath opens anything
(`web/take.engine.js`, a capture-phase click handler).

On a card row the mark is the market's `take`: the side, the pick, the
price and the chance **as shown when it was marked**, because the board
can show either side of a market (the likelier side or the value side)
and the mark has to say which one was taken. On a prop it is a flag. Both
are kept with the card and the props in IndexedDB; the market's mark rides
through a rescore, a second Add of the same game and a slate that fills a
blank box (`carryTakes`, by market and, for an alternate, by its number),
and a prop's mark rides through a reload of the night's props file.

**Taking tonight** sits at the top of the day board, above the parlay
four: one card per marked bet on the board's date (the pick, the chance,
the price and what it needs, the matchup, the result once the game
grades) and the marked props for the same date, with a summary card
(how many, graded W-L-P, units at one unit each) and a copy button. The
Props tab has its own **Taking** section above the best props, with a
count and a copy button; Copy props as text prefixes a marked prop with
TAKING.

**What you took** is a block in Is it working: every marked bet that has
graded, game bets and props on two tiles, says against does and units at
the price shown when the bet was marked. The props record also carries a
"taken" line and a tile. A graded row or prop cannot be marked after the
fact (the button becomes a TAKEN chip once the game grades, and a mark on
a graded row is refused with a note), so the taken record is of bets
marked before the game.

**The simulation's calls** (the user, with the Simulation card on the
screen: "let's say I decide to go with the Thunder team total under 119.5
at 72%; I would like to be able to select from this field too, for
tracking purposes, and to show on the take for the home screen"). A Take
button sits under every chip on the NBA Simulation card, both views, and
beside the gap rule's call. The mark lives on the card row as
`simTakes`, one per view, market and side, and keeps the call as the card
showed it when marked: the line, the book's price on that side (from the
row's boxes, or the team total's own line), the sim's chance, its worth,
its band and the pick in words (`toggleSimTake`, nba.engine.js). The game
has to be on the card first, since the row is where the mark and the
finals live: until it is, the button is greyed with that hint. Taking
tonight lists a simulation call as "TAKING · NBA · SIMULATION" with the
view it came from; the copy text names it; What you took grades it on
its own tile, "Simulation calls taken", the way the sim record grades (the
half from the half-time score, team totals from each side's final).

## The Simulation card's band comes from the worth, 26 Oct 2026

After a 71% own-view team total read STRONG and lost by seventeen, both
seasons were replayed with the own view's team totals added (NBA.md, "The
own view's team totals, replayed"): null. `nbasim.SHRINK` now carries the
team totals by view and side (anchored home 1.5, anchored away 0.3, the
own view 0.3), `nbaSimWorth` falls back to those for a row stored before
the split, and `nbaSimCalls` reads each call's **band off its worth**
instead of its raw chance. The chip still shows the sim's chance; the band
and the colour under it say what the replay found that chance to be
worth. The sim record and the phone sheet follow, since both read the
band from the same calls.

## The levers' tally, 26 Oct 2026

The user, with a Ziaire Williams over on the screen whose What moves it
showed every bar green: "if I wanted to find props like this one, with
multiple green bars pointing toward the implied result." `propsLeverTally`
counts a prop's factors pushing toward the pick's side and against it (a
push under 0.05 in the stat's units counts as neither), and the count is
put where it can be found: a **Levers** column in the Every-prop table
(▲ toward, ▼ against; green when every lever leans the pick's way, red
when more lean against), sortable like the rest with the most agreement
first; a **levers** filter beside the others, "every lever toward the
pick" or "more toward than against", remembered with the view and
cleared by Reset view; a tag on each best card; and the words on the
panel's What moves it heading. The tally is shown, not scored: it says how
many of the measured pushes agree, not how big they are, and the chance
beside it already carries their sizes.

## Tonight on your phone, 26 Oct 2026

The user: "a QR code or something I can scan with my phone camera that has
the model picks that I can view on my mobile, even if view only." The
picks live in this browser's storage, so the phone has to be handed them.
The **Phone QR** button on the day board makes a code that carries the
night's picks themselves: `phonePayload` gathers, for the board's date,
the bets marked Taking (card, simulation and props), the parlay four, the
best straight bets, the likeliest sides, the best twelve props and the
NBA simulation's calls at BET or better with the gap rule's; `phoneEncode`
deflates the JSON and base64url's it into the hash of a link to `m.html`,
a small read-only sheet published beside the page; the QR encoder is
Kazuhiko Arase's qrcode-generator 1.4.4 (MIT, vendored in `web/vendor`,
no network). A code holds about 2,900 characters, so `phoneFit` trims from
the least important end when a night runs long (the likeliest list, then
the simulation's calls, then the props) and the sheet says what stayed
off. Nothing is uploaded and nothing is stored: the code is the data, made
fresh on each press; the page is private, so the phone opens the link
signed in to claude.ai. `web/m.html` decodes the hash (DecompressionStream
on the phone; a browser without it is told) and renders the sections as
cards with the result chips, in the page's light and dark looks. The
harness makes a code on the example board, decodes it with an independent
decoder (jsQR) off the rendered modules, and renders the sheet.

On claude.ai the code's link never reached the phone with its picks; from
11 Nov 2026 the sheet goes through the page's own store there. See "The
phone sheet through the page's store" at the end of this file. The code
in the link is still how it works off claude.ai.

## The props reviewed: usage, the role, the floors and the same-game pairs, 26 Oct 2026

The user, with a night of props behind him, asked about four things he
reads on a prop: a usage rate of 24% or more; the alternate lines a man
clears 95% of the time (Sengun 10+ points, 5+ rebounds, 3+ assists); the
matchup against a bottom-ten defence by position; and a true probability
with positive edge. Then the pattern in the ones that landed first, two
props from one game as a parlay, and two Lakers starters, Ziaire Williams
over 8.5 points and Matisse Thybulle over 5.5, both cleared early. Each was
measured on 2025-26 before anything was built (`tools_nba_usage_floors.py`,
NBA.md), nothing that scored was touched, and what measured went in:

**Usage.** It was not on the page. The slate reads it now (`props_usage`:
the share of his club's possessions he ended on the floor, this season at
three games, else last season's) and the panel shows it as a tile, "29.5%
of his club's possessions, this season". What it measured is not what the
user expected: the over rate at the projection's median is 50% in every
usage bucket, so a star's usage says nothing about which side lands. What
it says is how far the projection misses: a man at 24% and up misses by
0.93 sigmas, a man under 18% by 1.13, and the split holds from the first
half of the season to the second. That factor is in the sigma now
(`props_sd_factor`, the side unchanged): a star's chance reads sharper
either way, a role player's wider, and the why says so. A **usage** filter
in the Every-prop table (24% and up, 18 to 24%, under 18%) finds the ones
he asked for.

**The Usage column** (later the same day, the user: "on Every prop on the date, a section for usage rate too?"): his share with S for a starter or B off the bench, green at 24% and up, sortable highest first, beside Levers and Sim.

**The role.** The Williams and Thybulle pattern is a real one: a starter's
miss runs about one sigma at every usage, a bench man's 1.15 to 1.25 at low
usage, because the starter's minutes are the steady part. The role comes
from RotoWire's five when the run has it (`props_role`, "RotoWire's
confirmed five"), else whether he started his last game; it picks the
starter's or the bench's sigma table, and it is a tag on the panel's heading
and a **role** filter beside the others.

**The floors.** `propFloor` is the whole number the median less z sigmas
rounds down to, at 95, 90 and 80% (z 1.645, 1.282, 0.842). The panel's
Floors section says "95% of nights: 10+ · 90%: 13+ · 80%: 15+ points", and
when he has two or more markets on the night, his 95% floors across them
as a ladder, "10+ points, 5+ rebounds, 3+ assists". Measured: the 95%
floors cleared 97.5% of nights, the 90% 93%, the 80% 82%; posted as a
book's whole number the 95% line cleared 98%; and one man's three 95%
floors all cleared 96.5% of nights against the 85.7% independence would
say, his minutes carrying all three. Honest to conservative. The books'
alternate-line prices are not pulled (a second market a game on the feed,
about twice the credits), so the floors are shown, not priced.

**The matchup.** Already scored: the defence's lean by position per stat,
from the ledger's own table, at the weight that held from one half of the
season to the other (0.75; 0.4 on threes), with HashtagBasketball's rank
beside it. A fantasy-points-allowed rank is the same levers added up, so
nothing new was built for it.

**A true probability with positive edge.** That is the Chance column
against what the price needs, and the BET band at three points of edge and
55%; the Is it working block is the test of it.

**Same-game pairs.** `propsPairs` makes tickets from the date's projected
props at 52% or better: the likeliest four legs a game, every pair of them
a ticket, likeliest first, eight at most. The chance both land is the
product of the two chances times what the season measured for the pair's
kind, capped at the lesser leg: two players' props land almost as
independence says (23.7% of pairs on one club both over the median, 25.2%
on opposite clubs, against 25.0%), so two overs on one club carry 0.95 and
two players 1.0; one man's two markets land together more often (28 to
29% against 25%), 1.15, and his points with his threes 38.2%, 1.5. The
ticket's price is the two legs' prices multiplied, what it needs is one
over that, and the card says whether the price agrees. The tickets are
rebuilt from the rows every time, so a graded night's tickets are the
night's as it stood and the record grades them on their own tile,
"Same-game pairs, at the parlay price", a pushed leg dropping out of the
ticket as the books do it. The phone sheet carries them.

## The simulation's stats on the Props page, 26 Oct 2026

The user: "add the simulation stats to the Prop page as well." The game's
simulation had lived only inside a prop's panel. Now the props run's block
for each game (`row.sim` in the file: each club's points with the middle
half against the ratings' points a game, the total, the margin, the home
win, the blowout and overtime chances, the pace and the regulars out) rides
on each of the game's rows, compact (`gsim`, `propsGameSim`), and the tab
shows it three ways:

- **The simulation on the games**, a strip above the pairs and the picks
  with one card a game (`propsSimStripHtml`): "PHI 103 · NYK 116 total
  219", the favourite by the mean margin, the home win, the total against
  the book's with the gap, each club's middle half against its ratings'
  points, the blowout, overtime, the possessions, each club's regulars out
  in points per 100, and how many of the game's props the sim's read sides
  with. A file loaded before the strip existed carries no game block, so
  the strip rebuilds most of it from the props' own sim blocks
  (`propsGameSimFromRows`, the total marked "about"); a file from a run
  without the simulation says so in a dim card.
- **The Sim column** of the Every-prop table: the sim's own read of the
  stat (his per 36 at his minutes scaled by his club's runs), green on the
  pick's side of the line, red against it, plain on the line; sortable by
  the gap toward the pick; a **simulation** filter beside the others keeps
  the props the read sides with, or against; Reset view clears both.
- **The best cards' last line**: "Sim reads 27.7 v the 25.5 line, on the
  OVER's side · PHI 103 (94–111) · blowout 52%", green or red. The phone
  sheet's props carry the read too, and Copy props as text.

Shown, not scored, as before: the scored part of the simulation is the
matchup lever at half weight, the weight that measured.

## The pair's own panel, and the pairs you take, 26 Oct 2026

The user: "when I click on the same-game pairs they don't open to show
any details; I'd like something similar to how the props are for the
singles." A ticket card opens the same panel the props use
(`propsPairDetailHtml`, `openPairDetail`): the band ("Same-game pair · the
price agrees"), both legs in the title, the chance both land with the
parlay price and what it needs, five tiles (both land, the parlay price,
the edge over it, each leg's chance at its price and band), then **How the
chance is made**: each leg's blended chance, the measured sentence for the
pair's kind (two players almost independent, two overs on one club ×0.95,
one man's two markets ×1.15, his points with his threes ×1.5), the product
written out and the cap at the lesser leg when it bites, the two decimal
prices multiplied into the ticket's price and what that needs, and by how
many points the price agrees or asks more. Under it each leg in a box of
its own: its chance, price, edge and band, projection and line, minutes,
usage, the Moves it line with the levers' tally, the sim's read in green or
red, the last-games tally, a button to the leg's own panel and the leg's
own Take. Previous / Next and the arrow keys walk the night's tickets
(`pairsOrder`), and a leg's panel opened from a pair walks the table as
before.

**A pair you take.** Take this pair on the panel, or Take on the card,
marks the ticket on both legs as the other leg's key (`pairs`), so it rides
through the file loaded again like a prop's own mark and the ticket is
rebuilt from the two rows as the night stood (`propsPairTicket`,
`pairTakesOn`). The marked tickets list under Taking on the tab and under
Taking tonight on the board (counted in the summary as same-game pairs),
copy as text, go on the phone sheet, and grade as the Same-game pairs tile
grades every ticket: a pushed leg drops out, a lost leg loses it. The tab's
record says "pairs taken" beside "same-game pairs", and What you took
carries a **Same-game pairs taken** tile at the parlay price. A graded
ticket cannot be marked after the fact. Found by the harness while
checking this: a slate load graded the props after the board had been
drawn, so Taking tonight showed the props' and the pairs' results only on
the next render; the board is drawn again once the props grade.

## What happened on each of his last games, 26 Oct 2026

The user, on P.J. Washington's panel with three of his last games marked
red: "on the last games, the ones that didn't cover, is there a way to put
next to those losses what may have been the factor that led to the loss?"
Then, on the first file: "I want them all to look like the Embiid one; I
want all the last games to have that info." The box has most of the answer,
and the slate writes it beside every game now (`props_game_factors`, the
sixth element of each `log` entry), five items at most, in this order:

- **The night's causes.** A regular of his club back or out that night,
  with the measured direction on the markets the pooled rule moves ("out
  (26 mpg, a lift for him)", "back (26 mpg, the lift gone)"; nothing on
  rebounds and threes, where the rule measured null), after the user read a
  green "back" as a help; a blowout of fifteen or more; a start when he
  usually comes off the bench, or the bench when he usually starts.
- **What stood out**, ranked by its size in the stat's units: his minutes
  three or more off his usual (or 12% of it), his shots (FGA + 0.44 FTA)
  two or more off his usual at those minutes (or a quarter of it), his
  shooting twelve points of field-goal share off his season's on four
  attempts or more, "cold" or "hot".
- **The plain box** for what did not stand out: his minutes against his
  usual, his shots against his usual at those minutes, his makes of his
  attempts, and the margin, won or lost by.
- **For a rebounds or assists prop, who had them** (27 Oct 2026, the user on
  Cameron Boozer's seven: "did he get less rebounds because of the defence,
  or was someone else on his team getting them?"): his share of the club's
  rebounds (or assists) that night against his usual share, standing out at
  five points off, and the teammate who took three or more over his own
  usual, named: "4 of the club's 42 rebounds, 10% (his usual 27%) · Cedric
  Coward took 11 (his usual 5)". The game logs keep the club's totals and the
  taker for it (`treb`, `tast`, `grab`, `dish`); a PRA prop names the taker
  without the share lines.
- **Overtime**, and a game five possessions or more off his club's own pace.
- **On a PRA prop, the three behind the total** lead the line (27 Oct 2026,
  the user: "how many pts, reb and ast each for the total"): "17 pts + 9 reb
  + 6 ast = 32", with the rest as it is and one more item allowed.

"His usual" minutes, shots and shares are this season's once he has three
games (a man in a new role reads as he is now: Ty Jerome's 30 minutes read
against his 32 as a Memphis starter, not his 25 off Cleveland's bench), else
with last season's thirty behind them; his shooting share needs ten games
before this season stands alone. With nothing to compare against the plain
box still reads.

**The graded night's own row** (27 Oct 2026, the user: "how come there is no
info for their game yesterday?"): the grade file carried only his minutes
and the stat. `nba-grade` now writes the same line for every man on every
box line, per market (`nba_grade_what`: the ledgers beside the slate, the
night's own games added when the ledger has not caught up), and the page
keeps it on the graded prop (`awhat`) and shows it on the "this game" row;
a second load of the night's grade file fills it in on rows graded before.
A rebounds or assists prop reads no shots or shooting. The regulars come
from `nba_club_regulars`: a man on 24 minutes a game over five games with
the club this season, or, until he has five, over ten games last season
(`nba_prior_mpg`); he is out when the game's own injury list names him and
he did not play, or when he is missing from the box between his first and
last game with the club, so a man traded in is not "out" before he arrived,
and a man out since opening night is. Back is a regular who sat the club's
previous game and played this one. Measured on this season's first
fourteen games with last season behind them: every one of 322 player-games
reads a line. The panel's **Last games** table carries it as a **What
happened** column, the first item bold in the colour of the game's mark,
red under the line and green over it, and the graded night's own row gets
his minutes against the games above it. A file from before carries none
and the column stays away. The game logs now keep his shots and makes, the
club's final margin, overtime, the game's pace and the club's regulars out
or back, for this. Shown, never scored.

## The regulars-out lever, re-examined, and a thin history's sigma, 27 Oct 2026

The user, after a week of props: "for the cards with the red for the
regulars out the unders tend to go over; should the regulars being out be
weighted more? Flagg played 40 minutes and got 11 assists against the under
5.5." His week agreed with him on the face of it: the props with a
regulars-out lever of 1.5 or more went 118-153 at a 55% say-so, on BOTH
sides, which is not a lift too small (the unders would have lost alone) nor
too large (the overs alone) but a chance too sure of itself on those nights
and a lift landing on the wrong men. `tools_nba_out_targeting.py` asked
2025-26 (NBA.md has the numbers): the minutes lift lands on the bench and
the low-minute men, not the starters the props are mostly about; the points
lift lands on starters and high-usage men; an absent creator lifts his
teammates' assists where an absent scorer does not; but a rule re-targeted
by role, fitted on the first half of the season, beat the pooled rule on the
second half by a hair (points rmse 6.200 against 6.211 with a regular out),
and the chance's spread with regulars out is 0.96 to 0.99 sigmas, the same
as without. So the scored rule stays as it is, and Flagg's night reads as
what it was: 40 minutes against a 28-minute projection dragged down by one
17-minute game, and an eleven-assist night two sigmas out.

What did measure is the thin history. A rate resting on three to nine games
misses by 1.09 to 1.10 sigmas on points (1.06 rebounds, 1.01 assists)
against 1.02 at twenty games and up, the rate's own sampling error. The
sigma now carries it (`PROPS_THIN_SD`): ×1.06 under 360 minutes of evidence
(ten games, last season's prior weight counted), ×1.03 under 720, the side
untouched, and the why says so. On a rookie like Cameron Boozer, whose 12.5
rebounds per 36 rest on three games and no last season, the chance reads
wider; the market's 8.5 had the better of a projection at 12.

## The fives and the matchup on the prop, 27 Oct 2026

The user: "a button to take me to the matchup for that game, or show the
lineup for that team in the prop?" Both. The props run already read
RotoWire's lineups page for the roles; each game in the props file now
carries both clubs' starting fives with the status and the men who may not
play (`fives`), and the panel shows them under the tiles, the prop's man
marked, expected or confirmed badged, shown and never scored. And a
**Matchup** button on the panel and on each best card opens the game on the
NBA card into the form (`openRow`), the props view folding away; the button
is greyed with the reason while the NBA card has no row for the game on the
date, and a click on it then says what to load. The row is found by the
date and both clubs' names (`propsCardRow`), the way the grade matches them.

## The combination markets, 27 Oct 2026

The user: "every prop on the date doesn't have a points + rebounds market."
The books post three the run was not asking for, and it asks for them now
in the same call: **points + rebounds**, **points + assists** and
**rebounds + assists**, three more credits a game. Each got what every
market has, measured on 2025-26 first (`tools_nba_combo_markets.py`, and
the props backtest with the combos added): one sigma k × √projection at
1.90, 1.86 and 1.32 (the method reproduces the shipped 1.86 / 1.21 / 1.16 /
1.10 / 1.92 on the first five); the median shift 0.06, 0.05 and 0.08
sigmas (the over rate at the mean 47.6%, 47.7%, 46.7%); the usage and role
sigma factors in the same shape as the first five; the regulars-out lift as
the sum of the parts' (0.56, 0.65 and 0.09 per 36 per 30 mpg); the defence
read on the points for the two with points in them and on the man's
position for rebounds + assists; the matchup lever at half weight on the
two with points, and on rebounds + assists at half weight scaled by his
assists' share of the stat, rebounds having measured nothing; the 95% floor
cleared 99% on all three. On the page the three list with their labels,
filter by market, grade by the sum of the box line, take their own tiles
in the record, and their last games open each line with the parts behind
the total ("28 pts + 9 ast = 37"); the floors ladder leaves the combos out
as it leaves out PRA. The grade file carries the what-happened line for all
eight markets.

## The opponent's absences on the prop, 28 Oct 2026

The user, after a rough night on the props: "when players are out that's
going to help the next man go over, not under, yet it seems to think the
same for the defence even when certain main players are out." He was right
about what the score read. The props carried his own club's absences (the
pooled regulars-out rule) and the simulation's strip took two fifths of an
absence off the club's defence, but the scored matchup lever read the
opponent's full-strength rating: `club_match` zeroes both clubs' absence
adjustments so his own club's lever is not counted twice, and the
opponent's went with it. Nothing in the projection said the defence was
short-handed.

Measured first (`tools_nba_opp_out.py` on 2025-26, the opponent short a
regular in 70% of 21,651 player-games): the opponent's absences lift points
+0.17 per 36 per 30 mpg against his own club's +0.42, and the lift did not
hold from one half of the season to the other (−0.02, then +0.30), so
points stay as they were. The piece that held is a missing **centre** on
the other side's bigs' rebounds: +0.56 per 36 per 30 mpg in the first half,
+0.78 in the second, the bigs' rebounds landing over the number 48.9% of the
time against 45.1% on other nights. Sized where the miss on those nights
closes (0.30 per 36 per 30 mpg; the per-36 regression's 0.69 overshoots),
it is scored for forwards and centres on rebounds, PRA, points + rebounds
and rebounds + assists.

On the page: every prop's why names the opponent's regulars out and what
the sheet does with them (shown, not scored on points, with the measured
reason); a big man's rebounds prop with their centre sitting carries "Their
centre out" as a lever of its own under What moves it, summing into the
projection with the rest, marked green or red like any other, and the
What moves it paragraph names it. The example's Towns and Bridges props
read it with Embiid out for the 76ers. The simulation's strip is unchanged:
its defensive share of an absence is near the pooled points lift that did
not persist, shown, not scored.

## The three voices on the total, 28 Oct 2026

The user: "if the simulation, the refs and the super model are all thinking
over or under for the total, that should get a green BET signal; two out of
three should be enough. Look at the Lakers and Spurs games: the simulation
and the refs were pointing to the over." Measured first
(`tools_nba_total_agree.py`, NBA.md): the sim's own view at 55%+ and the
crew's lean on the same side of the game total, the sheet not against it,
landed 157-108 (59.2%) over two seasons of closes, 134-98 with the sheet
silent and 23-10 with the sheet on it too, where the sheet's own BET band
lands 56.3%; a sheet BET the other way ran 15-20, so it blocks the rule.

On the page, scored: the Simulation card opens with **The three voices on
the total**, one line naming what the sheet, the sim and the crew each say
(the sheet silent under 53%, the sim short under 55%, the crew even inside
z 1.5) and the verdict; when the rule fires the block turns green with a
BET · 2 of 3 (or 3 of 3) badge and a Take button of its own. The board gets
an **Agreement on the total** section under the upset watch, one green card
a game where the rule fires, with the three voices, the row's price, the
result once graded and the same Take. A take marks the row like a
simulation call ("the agreement rule, the sim and the crew"), lists under
Taking tonight and on the phone sheet, and grades on the simulation
record's new line, The agreement rule on the total, 2 of 3 and 3 of 3
apart, with what the two seasons said beside it. The slate's log prints
the three voices on every game it simulates. The example (the sim under,
the crew over) reads "split … no rule".

Two gates, the same day, from the user's Spurs row (an alternate 225.5 at
−208 in the form, the market's number 232): the sheet's voice is its
likelier side (that row's pick by edge was the under at 36.6%, the over
at 63.4% behind it); a row line 1.5 or more off the market's main number
reads "an alternate … the rule was measured on the main line, no bet";
and a price on the rule's side asking more than the rule's 59.2% reads
"the book's price, not a bet". Both show the voices with a "2 of 3 · no
bet" badge, no Take, and no card on the board.

## Middles on the total, 28 Oct 2026

The user: "I use four apps, FanDuel, BetMGM, DraftKings and Fanatics; how
could we use the model to capitalize on middle betting? Build that tool and
see how it scores." Measured first (`tools_nba_middles.py`, NBA.md): the
apps sit within a point of each other at tip in 99% of games and a
one-point gap loses 3% of the stake; a number that has moved 3.5 points or
more from a leg already held pays (+3% of the stake, +12 to 14% at five or
more), the sheet's normal at 18 points sizing the both-win chance within a
point of what landed; the rule the page uses, the second leg whenever the
normal says the pair pays with a gap of three or more, ran +3.4% and +2.9%
of the stake over the two seasons.

On the page: a **Middles** card on the NBA rail, under the Simulation card,
with the apps' numbers as the newest odds run left them (an odds file
loaded later now refreshes a carded row's shop as `oddsNow`, the logged
line and prices staying as the markets were scored), the full-game totals
you hold on the row (the sheet's pick taken, a sim call, the agreement
rule) each with the best number the apps post on the other side, the
pair's both-win chance, what it needs at the two prices, what the leg
alone is worth now, and a Take when the pair pays; every over/under pair
across the apps' main and alternate numbers, the best six, with "none
pays at these prices" on an ordinary night; and a calculator for any two
numbers and prices, kept as you type. On the board, **Middles on the
totals you hold** lists a green card and a Take for each open window on
the date, or says how many legs are held with no window yet. The second
leg marks the row like a simulation call with the app and the leg it
pairs with, lists under Taking tonight and the phone sheet, and grades as
a pair on the simulation record's new Middles line (both won, one pushed,
split, the pair's units, and the first leg alone beside it).

The pairs table was wider than the card (29 Oct 2026, the user: "the table
for middles is off", the last column cut off on a laptop and the whole
card wider than a phone): it is five columns on fixed widths now, the app
on its own line over the number and price, the break-even under the
both-win chance and the verdict under the pair's figure, and the harness
measures that the table sits inside the card.

## The hockey simulation decides the totals, 29 Oct 2026

The user, with the NHL card on rest: "a simulation for the NHL model too,
same set up as the NBA one, focused on total goals, first period totals and
full game totals", and then "the NHL simulation will be the final decision
for the recommendation on the totals; taking in consideration all elements,
the simulation will hold the heaviest weight."

The engine (`slate/nhlsim.py`) plays a hockey game shot by shot. The clock
runs in game seconds; the next event, a shot by either side or a minor on
either side, arrives at an exponential wait from the sum of the four rates,
cut short by whatever is scheduled first: a penalty expiring, the period
ending, the goalie coming out. A shot becomes a goal at its expected-goal
quality: the league's goals per unblocked shot in that strength state, times
the shooting club's quality for, times the defending club's quality against,
times the goalie's goals allowed against expected, with the score effects,
the period and home ice on top; the rates work the same way from the
league's shots per 60 of the state's time and the two clubs' rate factors.
The strength state comes from the penalty box (a minor two minutes, a double
four, ended by a power-play goal; two minors a two-man advantage; a minor
each side four on four), the minors arriving at the club's rate of taking
them times the opponent's rate of drawing them times the crew's whistle. In
the third the trailing side within three pulls its goalie at the measured
clock for its deficit (drawn from the measured spread), keeps it out while
it trails, puts it back when level or four down; the leader shoots at the
empty net at the measured rate and quality, the trailer six on five.
Overtime at three on three, the first goal wins; still level, a shootout,
and the winner's official score takes one more goal, which the full-game
total carries and the periods do not.

Every constant is measured (`tools_nhl_tendencies.py`, 2,624 games of
MoneyPuck's shot files joined to ESPN's play-by-play through the ledger;
the strength timeline rebuilt from the penalties agrees with the shot file's
skaters at 97.6% of shots): five on five 40.3 unblocked shots per 60 a side
at 0.0605 goals a shot over 50.2 minutes of a game, the power play 76 per
60 at 0.098 over 530 seconds, the kill 12.5 at 0.073, 3.2 minors a side a
game (fights and misconducts put no one in the box) with the second period
15% heavier, the trailing side's shot rate +2 to +5% and the leader's −8
to −14% by the margin, the leader's quality +1.5 to +4%, the first period's
shots going in at 0.967 of their quality and the second's at 1.022, home
ice +1.5% on the rate and +0.9% on the quality, the pull with 93 seconds
left down one (82 down two, 246 down three; the 10th to 90th percentiles
carried), the leader's 28.9 shots per 60 of empty time at 0.52 a shot and
the trailer's 76 at 0.072, three on three 24.8 per 60 a side at 0.137.
ESPN typed the penalties by their infraction from the spring of 2026 and
the first pull missed them (477 games with no penalties); the pull now
reads either shape and carries the minutes and kind beside the text.

The club profiles: each figure relative to the league, this season's
blended with last season's whole by games/(games + K) where K is set by
the half-season reliability measured across 64 club-seasons (shots for
r 0.78 so K 12 games; against 0.61, K 26; quality for and against 0.51
and 0.53, K 39 and 36; finishing 0.29, K 101; the power play's rate 0.49,
K 42, its quality 0.18, K 185; the kill's rate 0.39, K 63, its quality
nil, K 400; minors taken 0.56, K 31, drawn 0.53, K 37). A goalie's goals
against expected is shrunk toward the league at 450 expected goals faced,
about 7,000 shots, because that is what the reliability says (half to half
r 0.11 to 0.20 at 60 to 100 xG a half, season to season 0.16): a goalie's
figure barely moves a game, and the card says so beside his name.

On the slate: `python slate.py nhl` refreshes this season's play-by-play
from ESPN (the days since the last game), downloads MoneyPuck's shot file
for the season (or reads `shots_YEAR.zip` beside slate.py) and compacts it
to per-game tallies, fetches last season's once as the prior, builds every
club's profile before the date, and plays each game 10,000 times twice:
the sim's own view with the named goalies, tonight's referees when the
league has posted them, and rest; and the market view anchored to the
carded book's number and price from the day's `odds-DATE.json` (and its
de-vigged moneyline for the split), so the first period and the team
totals read off the market's game. `nhl-tend.json` ships with the slate:
the league block, 44 referees' minors a game (from 5.7 to 7.7 against the
league's 6.4), every club's taken and drawn.

On the page: a **Simulation** card at the top of the hockey rail, the NBA
card's shape (four tiles, the view line, a three-column table of the
markets with a chip, its worth and a Take in each view's column, the
period means, the profiles and the goalies in words), and **the sim
decides the full-game and first-period totals**: the row's pick on each
is the deciding view's side at the worth (the raw chance shrunk by what
the replay found it worth), the band reads the worth, the sheet's own
projection rides along as a note and in the market's `sheet`, and the
record keeps both so it can say which was right. The take buttons mark a
call on the row like the NBA's, list under Taking tonight and the phone
sheet, and grade off the row's finals (the first period from the P1
boxes). The record's hockey block gets the simulation's tables: the
totals the sim decided (record, says, does, units, the sheet alone, how
often they agreed) and every call at LEAN or better from either view.

What the replay says (`tools_backtest_nhl_sim.py`, 1,312 games of 2025-26
at 1,500 runs a game, the profiles built from the games before each date
with 2024-25 as the prior, the goalies who actually started, the referees'
minors to date): the sim reproduces the game's level and shape (the first
period 1.76 goals a game against 1.76 landed; the total 6.00 against the
market's 6.10 and a hot season's 6.25; overtime 19% against 25% landed,
which is the one shape it under-draws) and its own view's lean on the
full-game total is worth a quarter of itself against Pinnacle's close
(logistic slope 0.25, so the shrink is 0.75): the leans at 58% and up went
207-174 and at 60% and up 131-108, 51.8% in the first half of the season and
49.6% in the second, and with the market's own price in the same model the
sim's weight was nil; the landed total regressed on the sim's mean and the
market's fair number gives the sim 10% of the weight. On the first period
the sim's own mean is as calibrated as the market's share but carries less
of the period (r 0.044 against the naive share's 0.080); against DraftKings'
1.5 at its price the own view's chance kept 61% of its lean (slope 0.61,
shrink 0.39), the anchored view's 78%, and the book's price itself read
sharper (slope 1.52): betting the own view where it beat the price by three
points went 49-56. The first half of 2024-25 (631 games with a DraftKings
1.5, no 2023-24 behind the profiles, no full-game closes to anchor to) kept
none of it (slope −0.15; against the price by three points 17-20), so the
first period's shrink is the pooled 0.64 (slope 0.36 over 1,942 games).
The team totals, the moneyline, the puck line and the other periods had
no closes to measure against and keep a priori halves.

So the sim decides, as asked, and the decision is honest about itself: a raw
70% on the full-game total is a LEAN (worth 55%), the first period needs a
raw 64% for one, and most nights the decision reads NO BET with the sheet's
own number beside it; the record's new block keeps the two side by side and
will say, after a month of hockey, whether the sim's side or the sheet's
side was the one to follow.

## The window on the total, one ticket, 29 Oct 2026

The user, looking at the Simulation card's middle half (221–246 on a
233): "is there a way for me to select the middle half ... over 221 and
under 246 as a same game parlay?" The apps take an over and an under on
the same total as one ticket, paid when the total lands between the two
numbers: a window, and the sim's histogram gives the chance of landing
inside any window directly.

On the Simulation card, under the medians: **The window**, three boxes
(the over number, the under number, the app's parlay price) that start at
the market-anchored view's middle half on half-point numbers, and a line
that reads the chance of landing inside from the anchored view (the own
view's beside it; the replay found the own view's centre carries nothing
the close does not, so the anchored shape prices the ticket), the fair
price, the width, a note when a number is an integer (the sim's mass on
it, since that leg voids on most apps; the half-point numbers are the
ones to type), and with a price typed, what the ticket needs and the
edge: PAYS or the app's price. A Take marks the ticket on the row like a
sim call (the two numbers, the price, the chance), it lists under Taking
tonight and the phone sheet, grades inside or out (a push on a number),
and the simulation record gets a Windows line: tickets, record, says,
does, units. Nothing here moves a call or a band. The hockey card can
take the same block when the user wants it; a hockey window is coarse
(five to seven goals) and the apps' alternate numbers on a total are few.

## The hockey book retired, 30 Oct 2026

The user: "after careful consideration ... remove the NHL model completely
from the super model. Stats and all. Give me a pdf of the stats but lets
remove that sport completely. Keeping NBA, NBA props, MLB and WNBA."

The record first: the latest backup (29 Oct 2026, 143 graded hockey games
from 1 to 20 Oct) loaded into the page as it stood, and what the page
rendered written to a PDF, "The Super Model - the NHL record": the record
tiles as shown (the pick 28-36-1, −13.6 units; the full-game total 60-79-4,
−24.8 units, with its splits by side, band, crowd, rest, backup and
goalie; the first period 62-79-1, −18.2; the moneyline 53-90, −25.5; the
puck line 57-86; the alternate totals 1-1; the parlay four 39-23, −7.7;
the best straight bets 20-37, −18.5), the forecast line (the projected
total 1.65 goals from the final against the line's 1.63), the favourite
table by price, a tally by market from the rows, and every graded game
with its picks and results. The record said what the user concluded.

Then the sport off the page: the NHL button, the hockey fields and board
boxes (the puck line, the first period), the hockey engine block, the
hockey rows of the record, the Simulation card and its takes, the hockey
example, the slate's hockey boxes, the BetMGM hockey link (the basketball
board takes its place) and every line of help copy that named hockey. A
hockey row leaves the card on load, a backup's hockey rows stay out of a
restore or a move, and a slate, odds or grade file with hockey games skips
them and says so. The harness drops its hockey cases and sections and
checks the block, the button and the fields are gone. The sources stay in
the repository with their measurements (web/nhl.engine.js, the hockey
fields, the slate's hockey modes, nhlsim.py, the backtests), so the book
can be read, and brought back if ever wanted.

## The simulation's second engine, 30 Oct 2026

The user, with the morning's backup: "Looking at the 20th and the 25th on the
night by night, what is the pattern there and what could enhance my
simulation to the max? You have full access to all domains, find the missing
link in the simulation's DNA and have it run all sorts of scenarios. Scour
the internet with your absolute best effort to make sure there is nothing
missing that we could consider."

**The pattern.** The Props tab's night-by-night table shows the 20th
(102-80, the BET band 13-5) and the 25th (200-160, BET 16-8) as the two
nights where *does* beat *says* and the BET band paid. Across all ten nights
the real pattern is a side: the sheet's chance ran about three points high
on overs and three low on unders at every band and in every scoring market
(rebounds alone balanced), overs 1,162-1,183 at prices saying 56% and unders
1,113-863; the 20th and the 25th were simply the two nights the overs did not
bleed. Behind it, on the 4,321 graded props, the model's own lean fit the
outcomes worse than the book's devigged price at any weight above nothing
(Brier 0.2505 at the old third against 0.2468 at none; where the model stood
ten points from Pinnacle the outcome followed Pinnacle 48% to the model's
68%), and the books' own prices lean the public's way: the under landed 53.2%
at the best price where the prices said 50.7%, the over 46.8% against 49.3%
(at Pinnacle's prices 54.3 against 51.1 on 1,946). The first night's 182
props ran on last season's rates alone and the 25th was the first night with
the simulation's matchup lever; neither made the difference, the overs did.

**The simulation's DNA, measured** (the scenario lab: `tools_backtest_nba_sim.py`,
the lab scripts, two seasons of closes joined to the ledgers and 2,469 games
of play-by-play):

| What | Found | Done |
| --- | --- | --- |
| The margin's shape | independent possessions spread the margin 16.7 points around the spread; the market's games spread 13.7. A side's first-half surplus comes back 10% in the second half (r −0.11 / −0.08), the margin's 21%; the possession-level read of the effect is hidden by team quality (the leader is the better side) | **score effects**: the side in front eases, the side behind presses, 0.0025 points per possession per point of margin; set on the second moments: margin 13.4, a side's variance 129 against the market's 128, the sides' covariance 39 against 34, the half-to-half reversion −0.09 / −0.22 against −0.10 / −0.21, overtime 4.5% against 4.7% |
| The total's shape | the anchored total spread 19.1 against the market's 18.0, inside its middle half 52.1% of the time; the pace noise and a quarter-count noise both sides shared carried covariance the score effects now carry | pace noise 2.0 → 1.0 a game, the quarter noise off, the last possession of a level game a held shot (−0.3 a possession). The replay after: the total's spread 18.3 against 18.2, the margin's 13.4 against 13.9, inside the middle half 50.1%, overtime 4.3% against 4.2%, the deciles flat |
| The level | absolute blending with last season's profile lagged the league's scoring by months: October 2025 the sim sat 4.1 under the close, January 4.6 over; the market followed the league within weeks | the ratings and the pace blend as deviations from their own season's league level and ride the league's level of the last fortnight (half-life 10 days, 150 team-lines of the season kept beside it): the sim's gap to the close 5.3 → 4.9 points, the monthly wander 8.7 → 2.3 points |
| The engine's lift | the last-30-seconds branch played a round on two seconds of clock, a possession a side over the ratings' total; with the fouling and garbage time the engine scored 0.6% over the ratings' implied total, which the ratings already contain | the branch fixed; the measured lift (1.0063 on 286 real matchups) divided out of the bases, with a selftest guard |
| Overtime, twice | the box keeps 240 team minutes whatever the overtime (every one of 114 overtime games in two ledgers), so an overtime game's pace read as 48 minutes of play, the league's level carried the overtime scoring, and the engine's own overtime counted it again, about a point a game | the minutes come from the periods played; the sim's total now sits on the close (−0.01 in 2025-26, −0.8 in 2024-25, on a third of each season's games) |
| The own view's worth | the replay with the second engine: the own total's slope of does on says −0.17 and −0.14, the spread −0.07 and −0.01, the moneyline +0.91 and +1.53, the anchored home team total +1.01 (355-233, 60.4%) | `SHRINK["total"]` 0.05 → 0.0; the rest hold |
| Absences | within the club, the close docks a newly absent 18+ ppg scorer 1.5 points of margin and 1.8 of total (0.62 and 0.77 per 10 ppg, 188 cases); the sim's cost for a 25-point man was 4.7 points of margin and 0.9 of total, three fifths offence two fifths defence | the cost 0.075 per 100 a point of his scoring, all on his club's offence, nothing on the other side (`slate.py nba_sim_out_adj`) |
| Rest | the close docks a back-to-back 0.7 more than the sim did (t 2.6), a third game in four nights 0.35 (t 2.0); the market's own miss on either is null | `rest_b2b` −1.7, `rest_3in4` −0.35 per 100 |
| The crew | an official's over/under residual did not carry from 2024-25 to 2025-26 (r −0.09 over 60 officials with 25+ games both seasons), nor his free throws a game (r 0.13), nor pace (r −0.01); crews the first season leaned under by 1.5+ ran +0.95 the next | nothing scored; the agreement rule's crew voice is **on watch**, its tag says so, the live record (1-5 as of the 30th) decides |
| Altitude, travel, the stage of the season | Denver's and Utah's games ran over the close home and away (a club label, as the 15 Oct table said); an away side two zones east saw the home side cover by +2.2, two zones west −2.8 (both seasons, 257 games, a watch); March and April ran over the close 56.9% and 54.3% (+2.2, +3.2); the early season did not run under (October 2025 ran over) | labels and watches, not scored |
| Player ratings | the 26 Oct lineup test stands: ridge ratings from the stints at the projected rotation did not beat the club model or add to the close | nothing |
| The props | the model's lean worth nothing against the book's price (above); a starter's minutes land 0.187 a game under his last-ten mean per point the final margin runs above the league's 13.5 (20,729 starter-games; +1.7 inside five, −3.6 at 25 and up), the bench's do not move | the market the spine (`PROPS_MODEL_W` 2.0 → 0.5), the over read 2.5 points lower (`PROPS_SIDE_SHADE`), **the game script** lever on starters' minutes from the sim's expected margin, each prop's why saying so. Its base is the engine's own season-average expected margin, 12.6, so the lever averages to nothing (2 Nov 2026: at the actual mean of 13.5 it had added 0.4 minutes to every starter, the first three nights' games expecting 11.2) |

Measured and found nothing new on the price: the early-season under of the
literature (the first month ran under 46% of the time both seasons), line
shopping at the same number across the eight books (the best price beat the
consensus fair by 4+ points on 64 props, 36-28, too few to read), the
officials, rest and travel as edges on the close.

**What the internet added.** The possession-based Markov models (Shirley
2007; Štrumbelj and Vračar 2012; the shot-clock MDP of 2018) are the
engine's lineage; the random-walk papers (Gabel and Redner 2012; Clauset,
Kogan and Redner 2015) describe scoring as an anti-persistent walk, which is
the score effect measured here in points per possession; the early-season
totals bias paper and the player-absence paper say what the two seasons
said, the market prices absences by the close and the early-season under has
gone; the eastward-travel paper (Journal of Sports Economics, 2023) points
the same way as the two-zone watch above; the vendor data on a million
graded props (unders lose less than overs in every sport) matches the shade.
Nothing found that the ledgers could not measure better.

**On the page.** The Simulation card's meta line names the level the
ratings ride and the engine's version; the Props tab's verdict says what
changed on the 30th and that earlier nights carry the old weights; the
agreement rule's tag carries the watch. The replay tables are in NBA.md.

## The save trimmed, and the over's shade by market, 2 Nov 2026

The user, with the backup of 1 Nov: "The save files are getting larger too
lol", then "lets do the trim bro, keep the last 7 nights whole. And for the
unders on the props and the bet bands and can we enhance or find more
winning props based on that data?"

**The trim.** The file of 1 Nov came to 44.6 MB: 6,858 props on thirteen
nights, 21.4 MB of them compact (the why lines 9.9 MB, the last games 3.1,
the fives 1.9, the levers 1.7, every book's line 1.0, the simulation 0.8,
what happened 0.7, the game's block 0.6), the pretty print doubling it, a
night adding about 4 MB. From today a prop on a night older than the last
seven on the Props tab keeps what the record, the tickets, the table and the
phone sheet read (the call, the price, the chance, the band, the result, his
minutes, the median, the centre the chance was read around) and drops the
panel's detail: the why, the last games, the levers, every book's line, the
simulation, the fives, what happened; `trim` carries the day it went
(`propsTrim` in props.engine.js). It runs on load and before every save, so
a restored backup trims on its way in and a night's file loaded again is
whole until its night falls off the seven. The panel says the detail was
trimmed and when, and keeps the floors and the graded game's own line; a
trimmed night's simulation strip says so too; the record tile reads the
centre off the row. The backup writes the props a row a line
(pretty-printed, a prop's last games had run a number a line; the card stays
pretty, its bulk the simulation runs' histograms, which are one line
already). The file of 1 Nov written this way: 24 MB, the seven whole
nights' props 19 MB of it, the card 3.6, the 2,555 trimmed rows 1.4 at 540
bytes each; zipped 2.5 MB against 3.6. The harness seeds ten nights and
checks the three oldest trimmed, the seven whole, the record, the panel,
the strip and the file.

**The unders and the bands, measured.** Every graded prop of the thirteen
nights (6,216 with a projection and a price), regime-free: the under's
landing rate against the carded book's own devigged price, whatever side
the sheet took (`scratchpad/lab2/unders.py`, `rules.py`, `shade_cv.py`,
`bands.py`).

| The shade | n | under | the book said | shade | first 7 / last 6 nights | nights up |
| --- | --- | --- | --- | --- | --- | --- |
| every prop | 6,216 | 54.4% | 50.6% | +3.9 | +2.9 / +4.6 | 10 of 13 |
| against Pinnacle's price | 2,321 | 55.1 | 51.5 | +3.6 | +5.3 / +1.9 | 8 of 13 |
| points | 1,108 | 53.4 | 49.9 | +3.5 | +2.1 / +5.2 | 9 of 13 |
| rebounds | 1,062 | 51.8 | 50.5 | +1.3 | +0.9 / +1.7 | 9 of 13 |
| assists | 910 | 55.2 | 50.9 | +4.3 | +4.1 / +4.6 | 8 of 13 |
| threes | 942 | 55.9 | 52.3 | +3.7 | +4.0 / +3.3 | 9 of 13 |
| PRA | 929 | 56.0 | 50.0 | +5.9 | +4.2 / +7.9 | 10 of 13 |
| points + rebounds (six nights) | 488 | 55.7 | 49.8 | +6.0 | | 5 of 6 |
| points + assists (six nights) | 400 | 56.5 | 50.0 | +6.5 | | 5 of 6 |
| rebounds + assists (six nights) | 377 | 51.7 | 50.2 | +1.5 | | 4 of 6 |

The public's over money sits on the points-bearing markets; rebounds carry
almost none of it. And the shade lives at the coin-flip prices, in the line
rather than the price (where the book has moved the price, it has moved it
enough):

| The book's own under chance | n | shade | first 7 / last 6 |
| --- | --- | --- | --- |
| 40 to 43% | 214 | +0.3 | −2.5 / +4.0 |
| 43 to 46 | 444 | +2.0 | +1.6 / +2.4 |
| 46 to 49 | 1,526 | +3.5 | +3.1 / +3.8 |
| 49 to 52 | 1,744 | +4.6 | +3.7 / +5.2 |
| 52 to 55 | 1,226 | +5.9 | +4.5 / +6.8 |
| 55 to 58 | 491 | +2.2 | +2.5 / +1.9 |
| 58 to 61 | 246 | +2.4 | +2.4 / +2.5 |
| 61 to 64 | 121 | −3.4 | −7.6 / +2.0 |

The same read as bets at the carded book's price, every prop's under taken
whatever the sheet said: −110 to −145 1,907-1,515 (55.7%, +60 units, +1.7%
a bet; not rebounds 1,531-1,197, +80, +2.9%), −146 to −175 367-255 (59.0%
but −23 units), heavier than −175 177-87 (67.0%, −2), −109 or cheaper
933-975 (+2). Every under 3,384-2,832 (+37, −33 in the first seven nights
and +69 in the last six); every over 2,832-3,384 (−875 units, −14.1% a bet,
one night of thirteen up). The bands as the file carried them: BET UNDER
104-97 (−13.5), BET OVER 127-141 (−32), LEAN OVER 331-368 (−82), LEAN UNDER
440-355 (+17), no edge UNDER 1,443-1,018 (+55), no edge OVER 904-888
(−221): the BET band was the model's lean, and the money sat in no edge.

The model's lean, again: a logistic fit of the under on the book's logit
price and the model's z gives z +0.005 ± 0.071; Pinnacle's price beside the
carded book's carries nothing of its own (−0.07 ± 0.48 against +1.07 ±
0.52). Cross-validated by night (odd against even nights, the halves) the
out-of-sample log-likelihood per prop: the book alone −0.6861, a flat 2.5
−0.6835, a flat 3.9 −0.6831, by market group −0.6831 (the best fold −0.6807),
the coin-flip rung −0.6833; taking every under whose shaded chance clears
the price by a point, the market grouping made +62 units on the two folds
where the flat fit lost 32.

**The bands replayed** with the sheet's own blend (the model at a ninth,
BET at three points of edge and 55%):

| The shade | BET | LEAN | BET + LEAN | the halves | no edge UNDER |
| --- | --- | --- | --- | --- | --- |
| flat 2.5, as it stood | 41-27 +5.3 | 436-387 −14.7 | 477-414 −9.4 | −2.8 / −6.6 | 2,128-1,547 +96.4 |
| flat 3.9 | 95-77 +1.0 | 1,175-951 +35.5 | 1,270-1,028 +36.5 | +39.9 / −3.4 | 1,618-1,198 +54.5 |
| by market group (1.5 / 4 / 5.5) | 162-130 +6.0 | 1,264-1,003 +71.3 | 1,426-1,133 +77.3 | +34.3 / +43.0 | 1,422-1,063 +4.4 |
| **market group × the tent** | **160-123 +11.9** | **1,185-949 +79.0** | **1,345-1,072 +90.9** | **+42.1 / +48.8** | **1,498-1,118 −8.8** |
| the same, the model at nothing | | 1,981-1,600 +113.6 | | +12.2 / +101.4 | 938-680 −51.8 |
| the same, BET at two points and 53% | 387-339 −4.8 | 958-733 +95.7 | | | |

So the shade is now by market, 1.5 points on rebounds and rebounds +
assists, 4 on points, assists and threes, 5.5 on PRA, points + rebounds and
points + assists (`PROPS_SIDE_SHADE`), in full where the book's own under
chance sits between 46 and 55% and fading straight to nothing at 40 and 63%
(`PROPS_SHADE_TENT`, `props_shade`); the model stays at a ninth (it sorts
the halves: +42 / +49 against +12 / +101 without it) and the BET band keeps
its three points and 55% (two points made BET worse than LEAN). The "no
edge" band now holds the losers (−8.8 on the unders, −108 on the overs),
which is what a band is for.

Measured and not scored: the spread on his club (favoured 4-8 +7.8, dog 8+
+6.6, dog 4-8 −0.9, favoured 8+ +3.4: no shape a mechanism gives, the linear
term nothing), the game's total (under 222 +5.9, but −2.7 in the first seven
nights and +9.1 in the last six), a teammate out lifting him (+2.4 against
+5.1 without, two sigma: a watch), the role and the usage (nothing beyond the
shade), the line against his base (the book's price carries it), the model's
lean at plus money (93 props). Thirteen nights is thirteen nights: the
record tile stays the test, and the verdict on the Props tab says what
changed from 2 Nov.

**Found on the way: the page's encoding.** The harness stalled twice on a
reload with `smStore` undefined and one page error: "Invalid regular
expression: /[Ì€-Í¯]/g: Range out of order in character class". The built
page declared no charset (it opened with `<title>`), so a browser reading
it off the disk guessed the encoding from the first chunk of bytes; when
that chunk was pure ASCII it fell back to Windows-1252, and the one regex
written with literal combining marks (`callsheet2.tail.js`, the name key's
`normalize("NFD")`) became an out-of-order range, which killed the whole
script. That was the 30 Oct "smStore is not defined" flake too. The head
now opens with `<meta charset="utf-8">` (both builds) and the marks are
written as `̀-ͯ`.

## Your picks, 3 Nov 2026

The user, with the backup of 2 Nov: "is there a way to have the props that
I select taken be graded or tracked so I can see how I'm picking the bets?"

They already were, in two places: the **Taken** tile on the Props tab's
record and **What you took** in Is it working (26 Oct 2026), four tiles for
the game bets, the simulation's calls, the props and the same-game pairs
you marked, each graded at the price shown when it was marked. What was
missing was the view that answers *how am I picking*: night by night, by
what, against what the sheet itself would have done. So:

- **What you took** goes on to **Your picks, night by night**: every
  marked bet that has graded, by night, with the record, says (the sheet's
  chance on what you took), does and the units, and beside each night what
  the sheet's own BET and LEAN props did that night, the comparison that
  says whether choosing from the list beat taking the list.
- **Your props, by side, band, market and price**: the breakdown the sheet
  keeps of its own calls, on the props you took.
- **Every pick you marked, newest night first**, folded under a summary:
  the bet, its kind, the chance, the price, the result and the units.
- The Props tab's night-by-night table carries a **You took** column, and
  the Every-prop table a **taken** filter ("the props I took"), kept with
  the view like the other filters and cleared by Reset view.

The verdict under it says what the numbers mean: the sheet's own tiles say
whether its chances are honest; a gap between says and does here that is
not there is selection, the picks chosen from the list landing less (or
more) often than their chances say. On the 91 props marked to 2 Nov the
sheet said 60.0% and 53.9% landed (48-41, −3.1 units): the heaviest
favourites among its calls (−120 to −150 went 16-17), with the BET band
chosen most (31-24). Nothing reads under a hundred picks, and the line is
there to read it from.

## The crowd on Kalshi, 4 Nov 2026

The user: "If I wanted to use some metrics from Kalshi such as public
percentages on who may win the game for NBA or the totals or spreads, what
could I get for you or something we can add to help the model or give me
more info at a glance on the matchups or props?" Then, asked for one, the
exchange's own listing of its open NBA game-winner markets (64 markets, 32
games from 4 to 7 Nov).

**What the exchange is.** A Kalshi game-winner market is one binary
contract a side ("Atlanta wins", "Washington wins") that pays a dollar and
trades in cents, so its price is the crowd's probability with no vig and
the bid-ask spread is the only juice. The fee is taken on the win: 7% of
the expected profit a contract, so a yes at 57 cents costs 57 + 0.07 × 57 ×
43 = 58.7 and needs 58.7% to break even. The listing carries each side's
bid, ask, last price, volume and open interest; the event ticker reads
`KXNBAGAME-26NOV04ATLWAS`, the date and then the two clubs' codes (the
away club first, as far as the schedule says, though the slate matches the
codes in either order). The night's games trade at a cent of spread on
10,000 to 860,000 contracts; games two or three days out trade at five to
thirteen cents of spread on a few dozen, so the bid and the ask are shown,
never the last trade alone. The market endpoint needs no key, and the
exchange is blocked from this environment, so the slate reads it from the
user's machine.

**What a crowd percentage is worth.** It is a market price. The sheet's
own measurement said the market price is the best single predictor it has
(the model's lean on props fit worse than the book's devigged price at any
weight above none; the simulation's own total is anchored to the close),
and fading the crowd on NBA sides has never cleared a coin flip in the
literature, so the exchange's number is not a lean and goes nowhere near
the chance. It earns its place three ways: as a second price (a no-vig
price at a cent of spread often beats −110 even after the fee), as a
cross-check at a glance (the crowd, the book and Pinnacle on one line), and
as the crowd against the sharp book, the moneyline cousin of the Pinnacle
shade on totals (56.3% at a shade of three points over two seasons), which
goes on the record as a watch until the data says what it is worth.

**On the slate.** `kalshi_fetch` reads the open game-winner markets
(paged), `kalshi_parse` keys them by date and the two clubs, and
`kalshi_game` matches a game by code in either order on the date; the slate
run and the odds run both attach each side's bid, ask, last, volume and
open interest to the NBA row as `nbakalshi`, log a line ("Hawks 57.5 cents
(57/58, 150k contracts) · Wizards 42.5 cents (42/43, 140k contracts)") and
note a game the exchange has not listed. The loader carries the field and
a newer slate or odds file replaces it, as the lineup and the simulation
do.

**On the page.** The NBA form has a card, *The crowd on Kalshi*: each side
read three ways (the crowd's mid, the book's devigged moneyline, Pinnacle's
when the odds run brought it), the bid, the ask and the contracts, which
price is better after the fee, and, when the crowd sits three points or
more from Pinnacle, the sharp side named as a watch. The board's moneyline
cards carry a chip with the exchange's price for their side against the
book's after the fee ("better on Kalshi: 58¢ needs 59.7% after the fee v
−165 needing 62.3%"). The moneyline tile keeps the sharp side's record
("the sharp side against Kalshi's crowd, 3+ points W-L"), graded at the
carded book's price.

**The ladders, the same day.** The user then sent the exchange's spread
and total listings (`KXNBASPREAD`, `KXNBATOTAL`). A spread market is one
contract a rung a club ("Memphis wins by over 6.5 points", the floor in
`floor_strike`, a point apart near the number and two apart further out,
the favourite's ladder finer than the dog's); a total market is one
contract a rung ("Full Game: Over 228.5 points scored", two points apart).
Each rung's price is the crowd's chance of more than the floor, so a
club's ladder and the game's total ladder are the crowd's whole
distribution of the margin and the total, the thing the simulation also
has. The slate reads all three series (paged), keeps the ladders on the
row beside the game-winner prices (`sp.a`, `sp.h`, `tot`, each rung as
floor, bid, ask, last and contracts), and the log line names the crowd's
spread and total at even money. On the page the card goes on: **the
spread**, the crowd's number at even money (the home margin's curve built
from both ladders, the away side's rungs read as the home side falling
short) beside the book's, and at the book's number the home cover's
chance by the crowd, by the sheet and by the simulation's own view; **the
total** the same way, with Pinnacle's number and the simulation's own
median beside it. When the book's number is a rung of the ladder, each
side's price on the exchange (the yes ask for the side the ladder names,
one less the yes bid for the other) is read against the book's after the
fee, as the moneyline is; between rungs the chance is read straight and
there is no price to compare. The board's spread and total cards carry the
same chip as the moneyline's. The record keeps only the moneyline watch;
the ladders are shown, not scored. Player markets wait on a listing.

**On the prop's panel.** The user, having loaded the runs: "how can I see
the Kalshi on the props cards I open?" The prop's panel and the game's
strip on the Props tab now read the crowd off the matchup's row on the NBA
card (the same `nbakalshi` block): the crowd's spread and total at even
money beside the numbers the props file carried, and the winner's chance
("The crowd on Kalshi: Knicks by 5.3 (the book's spread Knicks −5.5) ·
total 229.3 (the book's 231.5) · Knicks to win 69.5%"). It needs the game
on the NBA card with the slate or the odds file loaded on it, which the
routine already does; the Matchup button still opens the full card.

**The player ladders, the same evening.** The user, asked whether the
exchange runs player markets, found them on the game page and sent the
points listing and the series names off the market addresses: points
`KXNBAPTS`, rebounds `KXNBAREB`, assists `KXNBAAST` and the combo
`KXNBAPRA`, and a few minutes later, off a second address, threes
`KXNBA3PT`; no two-stat combo market has turned up. A player market is one
contract a rung ("Luka Dončić: 25+ points"), the rungs five apart on
points and a make apart on threes ("1+" a floor of 0.5), and the
exchange stores "25+" as a floor of 24.5 with the same greater-than rule as
the totals, so the book's 24.5 line is an exact rung and any other line
reads straight between two. The name sits in the title with its accents
(the props' own name key strips them), the club in the ticker's player
key (`LALLDONCIC77`). The props run reads the five series (paged), matches
each prop's player by name within its game, and keeps his ladder on the
prop (`kal.r`, each rung as floor, bid, ask, last and contracts), with a
log line a game ("31 of 48 props carry the crowd's ladder"). On the page
the prop's best card carries a line and its panel a tile, *Kalshi's
crowd*: the crowd's chance of the pick's side at the book's line, the
crowd's own number for the player (the ladder's even-money crossing), and
on a rung each side's price after the fee against the book's (the under
is the no side, one less the yes bid). The ladder rides through the save
(not trimmed) so the measurement to come has both prices on every graded
prop: whether the crowd's price or the book's predicts the outcome better,
and whether the crowd shades the over as the books do. Until then, shown,
not scored.

**The team totals, later that evening.** The user: "Can we also have team
totals too?" with the address of a market off the game page's Game Props
tab, `KXNBATEAMTOTAL-26NOV04PHIDET-PHI109`: a series the run had not been
reading, a ladder a club like the spread's, the club's code then the
number in the ticker's tail and the floor on the market like the rest.
The slate and odds runs read it with the other three and keep each club's
ladder on the row (`tt.a`, `tt.h`); the log's summary adds "the crowd's
team totals Wizards 114.1 · Hawks 117.5". On the card the Kalshi section
gets a paragraph a club: the crowd's team total at even money, the book's
team-total line with its prices (the odds run's), the number the book's
own total and spread imply, and the simulation's mean when the row
carries the sim; at the book's line, the crowd's chance of the over, the
simulation's, and on a rung each side's price after the fee against the
book's. The simulation's table carries the same read under its two
team-total rows, beside the gap rule, so the crowd sits next to the one
scored call on those markets. Shown, not scored, like the rest of the
exchange. Asked again later that night ("what about the team totals for
each matchup?"), the Props tab's matchup line, on each game's strip and
on the prop's panel, carries them too, between the total and the winner
("team totals 76ers 108.3 · Knicks 118.9"). And on the matchup rail,
at the user's word ("can I have the team totals predictions from Kalshi
be on the matchup section with a color like you have the other
signals"), each club's team total is a purple chip of its own in
tonight's signals: the crowd's number at even money, the book's
team-total line, the side the crowd leans to when it sits a point or more
off that line (or "sits with the book"), and the crowd's chance of the
over at the book's number; without a book line, the number the book's
total and spread imply. A row shows any of this only once the slate or
odds run that read the series has been loaded on it.

## Easier on the eyes, 4 Nov 2026

The user: "Could you add a little color and since the to the KALSHI so it
stands out on the props and game matchups? and i dont know why but for
the 'this matchup' section, its seems a little too wordy or much on the
eye and it never gives a green bet signal anymore and not sure if we can
condense that section and make the other sections, like the simulation,
refs, lineups, Kalshi, the board, the middles, the context be a little
more of the forefront and just easier on the eyes to navigate since we
have made many changes lol".

**Why the pick card is grey on most NBA rows.** The sheet's pick is the
likeliest side among the markets its inputs inform, and only where those
inputs move the chance a point off the book's own number. On the NBA the
close already carries the ratings, the rest and the announced absences
(measured against two seasons of closes, and faded or shown accordingly),
so the inputs rarely move a point and the card reads "No pick yet". The
green that does fire on the NBA lives in the engines down the card: the
agreement rule (the three voices), the simulation's bands by worth, the
gap rule on the team totals, a middle that pays, the upset signal, and
the watches (Pinnacle's shade, the crew's lean, the crowd against
Pinnacle). None of that was visible from the rail.

**Tonight's signals.** The matchup rail now opens with a strip of chips,
one for every engine's call on the row: the pick and #1's verdict, the
upset signal, Pinnacle's shade, the three voices, the simulation's calls
with their worth, the gap rule, the middles, the crew's lean, the crowd on
Kalshi (the sharp side, and its winner, spread, total and team totals at
even money) and who is out. Green when a scored rule fires, gold for a
watch, the exchange's purple for the crowd, grey for information; each
chip is a link to its section. When nothing fires the strip says so in one
line. `signalList()` builds the list off the same functions the panels
use (`nbaVoices`, `nbaSimCalls`, the gap rule on `nbaSimLinesFromForm`,
`nbaMiddleWatch` and `nbaMiddlePairs`, `nbaCrewLean`, `kalshiOf` and
`kalshiSharpOf`, `nbaOutList`), and `signalStrip()` renders it at the end
of every render of the rail. Shown: it adds no number and takes nothing.

**The jump bar and the live lines.** The NBA card starts with a sticky bar
of links to its sections (who is out, form, simulation, middles,
referees, Kalshi, context) and on to the board, the card and the record;
each section's dot lights in the colour of its strongest signal, and the
section heading carries a live line with the same words ("gap rule:
Lakers team total UNDER 119.5 · gap +1.5"), so a scroll down the card
reads like a list. The explanations under every section fold under
"about this section", the rail's long how-to folds under "how to read
this card", each market row's reasoning folds under "the reasoning" with
the numbers and chips left in view, and the why list's alternates line
keeps the four nearest numbers and counts the rest. The harness reads the
strip, the dots, the live lines and the folds on the Hawks @ Wizards row.

**Kalshi in its own colour.** A `--crowd` token (purple, with a dark-mode
shade) marks the exchange wherever it shows: the word on every line, the
prop card's line and the props strip, the prop panel's tile, the board's
chips (a solid purple chip when the exchange's price is better after the
fee), the simulation table's line under the team totals, the Kalshi
section's heading and its panel's bold figures. Green stays what it was:
a scored rule that fires.

## The simulation off the props, 5 Nov 2026

The user: "I'd like to see what the results would show without any input
from the simulation at all for the props. Can you test the last log I gave
you? I'm not seeing any benefits of the simulation whatsoever." Then:
"Just turn the simulation off for the props and use all the other great
metrics and statistics to help with player props... What do you recommend
we replace the simulation spot with now that have more games in the
season plus a plethora of odds and matchups stuff."

**The test.** The simulation reached a prop through two scored levers,
the matchup factor (the club's efficiency into tonight's defence from the
profiles, to the half power) and the game script (a starter's minutes
against the runs' expected margin). Both are stored on every prop of the
last seven nights, so the 4,800 graded props of 27 Oct to 2 Nov were
replayed with the levers backed out of the projection, the model's chance
recomputed, re-blended with the book at the same weight, the side and the
band re-read, and graded on the actual stat (every stored chance
reproduced first). The record did not move: BET 110-126 (−33.1u) with the
simulation, 108-126 (−35.2u) without; LEAN 738-631 against 746-637; 24
props changed side, the simulation's side 10-14 on them. Where the
simulation moved a projection a quarter point or more the actual landed
on its side 39% of the time, at half a point 27% (r −0.12, t −8); when it
pushed a number up the over landed at its market's normal rate, no lift.
Its own read on the cards split nothing (picks it agreed with 54.0%,
disagreed with 54.9%). The game script was miscalibrated besides: the
runs' expected margins ran 10.9 to 12.1 on every game against a base of
12.6, so the lever only ever added minutes, while the real margins
averaged 13.3.

**The candidates, measured the same way.** The market's own team points
(the book's total and spread against the club's average) as a matchup
lever: null, r −0.03, the pushed-up overs 5 points under their market's
rate at a quarter point. A prop's line already carries the game, so any
club-level multiplier on top counts it twice. The spread's expected
margin against a starter's minutes: real, r −0.12 (t −7.2), −0.32
minutes a point on 3,801 starter props, the mechanism the two-season rule
was built on. The books' consensus against the carded line: the carded
line sat half a point or more off the median across the books on 872
props, and there the truth sat about half way toward the consensus (the
over +6.7 points above its market's rate when the others sat above the
carded line, the under +3.8 when below; r +0.06, t 4.0; Pinnacle's line
alone +4.1 and +3.6). Projected minutes miss by 4.2 a game on average and
run 0.6 high.

**What changed.** The matchup lever is shown at no weight (its why line
says so) and the game's 10,000 runs no longer play for the props, which
also takes minutes off the props run. The game script reads the spread's
expected margin (a normal at 12.5 around the number) against a base of
11.8, the mean over the season's graded games, at the measured 0.187
minutes a point. The books' consensus is the scored lever in the
simulation's place: the median line across the books posting one (three
or more), its gap to the carded line read on the book's chance at 0.11 of
a point a sigma of gap (half the measured 0.22), capped at six points,
with a part on the levers list ("The books' consensus, on the market's
number"), a why line, and the block on the prop (`cons`: the line, the
count, Pinnacle's, the gap, the shift). The market on the game rides on
each prop (`mkt`: the club's implied points against its average, the
expected margin, the blowout chance). On the page the market takes the
simulation's spots: the strip above the picks (each club's implied points,
the margin, the blowout, how many carded lines sit off the consensus, the
crowd on Kalshi), the panel's tiles (the books, the consensus lever, the
club's points, the expected margin, the blowout), the best cards' last
line (green when the consensus sits the pick's way), the table's column
and its filter, and the record's own line for the consensus (with the pick
and against it, half a point or more). A file from before the change
still shows its simulation. The selftest covers the spread's script, the
consensus and the market block; the harness reads the strip, the card,
the panel, the column and the filter on a seeded night.

**One app a ticket, the same evening.** The user: "when you put together
the same game pairs or the best 2 leg parlays, can you pair them up with
the same bet app?... that way its easier to put the pairs in the correct
apps." From 5 November each same-game pair is built at one of the four
apps (Fanatics, DraftKings, FanDuel, BetMGM): both legs read at that app's
line and price off the books the props run keeps on every prop, the
chance re-read at the app's line by the slate's own blend on the page
(`propChanceAt`: the model's chance from the centre and the sigma, the
book's from the prices less the shade, the consensus shift at that line,
blended at the anchor's weight) when it differs from the carded one, the
app with the best edge chosen. The card says "at DraftKings", the panel
says it and lists the same ticket at each app with the chosen one marked;
a pair no single app posts is listed last, its legs split across apps.
A ticket's legs grade on the app's lines against the actual, and its
units at the app's prices. Nights before the 5th keep the carded legs, so
the record stands as it was, and the books stay on a prop through the
trim so the pairs can always be rebuilt.

**The levers that count.** The user: "for the levers, I want to keep the
ones that matter and only have levers for measurable movement that helps
make the prop bet more accurate." The levers list, the tally on the card
and in the table, the bold why lines and the Levers filter now read the
measured levers only: the regulars out, their centre out, the game
script, pace, the defence by position and the books' consensus. Last
season's prior and the minutes trend are what sits inside the start, not
pushes on it, and the matchup from the profiles measured null; they read
as a line of their own under What moves it ("Inside the start, not a
lever") and stay in the why.

## The props realigned, 5 Nov 2026

The user, with the 5 Nov backup: "Last night the props were terrible. I
think I did too much by adding the simulation and the Kalshi to the
props. The model said under on most and all but one actually went under.
I want to remove the Kalshi completely from the props... 10/20 was 13-5,
10/25 was 8-1. You have to find what the misalignment is and fix it
immediately." Then: "do thorough testing to make sure it's aligned...
measure a thousand times to make one cut."

**What the backup said.** Fifteen graded nights, 8,676 props with a
projection. Through 29 Oct the sheet called the under on 43 to 56% of the
props a night; from 30 Oct on 79, 78, 75, 83 and 82%. On 4 Nov every BET
and every LEAN was an under (257-272, −50 units), and the seven props the
user took went 1-6, all unders, five of them PRA or points + assists. The
nights he remembers were the old blend (the model at 2.0, no shade):
13-5 on 20 Oct and 16-8 on 25 Oct, inside a span that read 217-229 on
the BET band over its ten nights.

**The misalignment.** The over's shade. It went in on 30 Oct (2.5 points
off the book's over chance, the same day the model's weight fell from 2.0
to a ninth) and was widened by market on 2 Nov (4 points on points,
assists and threes, 5.5 on the combinations, 1.5 on rebounds, in full at
a coin-flip price). With the model at a ninth the book's price *is* the
pick, so the price less the shade turned every coin-flip prop into an
under. The shade had been fitted on the thirteen nights to 1 Nov, where
the under had run 54.4%; out of that fit it read +10.5 on 2 Nov and −49.9
on 4 Nov, and over its whole life its BET band read 83-85 (−14 units).
The under's lean at the books' coin-flip prices is real in the aggregate
(the over landed 44% where the book's chance said 45-50) and the under's
own price eats it (−120 to −135 at those lines, 55 to 57% needed). A
blanket lean to one side at the book's prices is not an edge, and it
stopped the sheet choosing. Kalshi had nothing to do with the record: it
was shown on the props and never scored. The simulation had come off the
props the day before.

**The measurements before the cut** (`lab/props_variants.py`,
`props_grid.py`, `props_pick.py`, `props_deep.py`, `props_bias.py`,
`props_recentre.py` in the session's scratchpad, all off the stored
rows: the book's devigged chance from the two prices, the model's chance
from the projection, the sigma and the median shift, the consensus from
the books kept on each prop, the blend re-run and the picks regraded).

- *The model's lean on its own* is noise in the middle and reads only at
  its extremes: its side landed 51% of the time over both halves of the
  nights (r +0.04 and +0.025 against the book's +0.12 and +0.08); where it
  stood 20 points or more from the book, 51-53%; 30 or more, 55% then 53%.
  Alone it reads 2,447-2,439 (−352 units) at the BET floor.
- *The blend's fit* (Brier over every prop) is best with the model at
  nothing (0.2470) and a hair worse at a fifth (0.2478) than at a ninth
  (0.2473): the bands are what the sheet is for, so the bands were the
  test.
- *The grid* (weight ½, 1, 2 × shade off, half, full × consensus off, 0.11,
  0.22), both halves of the nights apart. With the shade off, a ninth
  leaves two BETs a night (20-14 in all); the old 2.0 fifty to a hundred
  and fifty a night at 53.3% (562-492, −28 units); a fifth 15 to 20 a
  night at 57.9% (146-106, +10.6 units; 52-34 then 94-72; eight nights
  of fifteen up). The consensus lever helps at every weight (at a fifth,
  122-95 without it).
- *A walk-forward over the grid* (the cell with the best record on the
  nights before, applied to the next night) read 152-153 (−29 units):
  chasing the best recent setting does not work, so the cut is not "the
  grid's winner"; it is the measured middle between a weight that gives
  nothing to bet and one measured bad.
- *A bootstrap by night* (1,000 draws of the fifteen nights whole): at a
  fifth with no shade the BET band's units sit above water 71% of the
  time (median +11, 5th to 95th −20 to +47; the win rate's 5th percentile
  51.2%); the sheet as it stood 35%; the old 2.0 12%.
- *Says against does* at a fifth: the BET band says 60.8% and does 57.9%;
  the unders 62.1 against 60.0, the overs 57.8 against 53.2. The LEAN band
  says 55.5% and does 51.6% (679-636): not an edge.
- *The model's bias.* The points projection runs high this season: the
  per-36 rate at the minutes he actually played is 5.6% high on points
  (7.2% in the first eight nights, 4.4% in the last seven; 3-4% on
  assists, PRA and the two-stat combinations; rebounds and threes on the
  money), the minutes 0.85 high (starters 0.5, the bench 1.2), and the
  median miss on points sits 0.23 sigmas under the centre in both halves
  (0.24 then 0.21) against the shipped 0.08 shift. Last season's prior
  carries about half of it where it applies (the 143 points props with a
  prior at four games or fewer: 0.90 at half share, 0.95 at none, 0.97
  for men with no last season). But re-centring the model on the
  season's own misses, walk-forward (each market's shift the median miss
  on the nights before), read 171-139 against 133-97 with the shipped
  shifts, and in sample 162-121 against 144-104: the book carries the
  same bias (the over landed 46% against its lines), so moving the model
  toward the actuals moves it away from the book without moving the
  picks the right way. The shifts stand, the bias is on record.
- *The BET floor.* Edges of 5 points and more read 65-37 at a fifth,
  3 to 5 points 101-88; raising the floor would be the same chasing the
  walk-forward just failed, so the bands stand and the record tile keeps
  the edge buckets.

**What changed.** `PROPS_SIDE_SHADE` stands at nothing on every market
(the machinery stays, with its history); `PROPS_MODEL_W` is 1.0 (the
model a fifth of the say); the consensus lever, the median shifts, the
game script and the bands are as they were. The why line on a prop reads
"blended at 4 to 1.0, the market the spine and the model 20% of the say
(5 Nov 2026: the over's shade is off...)"; the method block records the
shade off and Kalshi off. On the page the slate's blend mirror
(`propChanceAt`, the pairs re-read at an app's line) follows the night:
to 4 Nov the shade by market and the model at a ninth, from 5 Nov the
shade off and a fifth (`PROPS_BLEND_FROM`), so earlier nights' tickets
stand as they were. The record tile's verdict says what moved and why.

**Kalshi off the props.** The player series (`KXNBAPTS`, `KXNBAREB`,
`KXNBAAST`, `KXNBA3PT`, `KXNBAPRA`), their parser, the fetch and the
ladder on the prop are out of the slate; the props run reads no exchange
market. On the page the crowd's line on the best cards, the panel's tile,
the matchup line on the panel and on the strip are gone, a `kal` field a
4 Nov file still carries is ignored, and the Kalshi styles on the Props
tab are gone with them. The crowd stays where the user liked it: the NBA
card's matchup (the winner, the spread, the total, the team totals), the
signals strip, the board's chips and the simulation's table.

**Tests.** The selftest reads the blend at a fifth (50/50 against 63.5%
blends to 52.8%), the projection test's prop at 52.1% and no edge with
the shade at nothing on every market and the why line's new wording, and
that the slate has no player series left. The harness reads a prop that
still carries a ladder with no crowd line and no crowd tile, the panel
and the strip without the crowd's matchup line while the NBA card's row
carries it, and the example's best list at the new blend.

## Recent form shown, three levers measured and left off, 5 Nov 2026

The user, after the realignment: "What would have helped the model be
able to see those picks as likely to go over instead of under and would
have been wins?" Then: "Go ahead and make the adjustment and triple the
results to make sure everything is aligned correctly and no issues."

**What the box said afterwards** on the 35 losing unders of 4 Nov: minutes
over his usual on 16, hot shooting on 10, shots over his usual on 8, a
blowout on 1. Bam Adebayo played 41 minutes against his usual 33, took 24
shots against his usual 19 and hit 14 of 20. In-game variance, unreadable
before tip.

**The signals on the sheet before tip** (`lab/props_signals.py`): the
book's own price lean, the books' consensus, his last 3 and last 5
against the line, the share of his last 10 over it, the minutes trend,
the opponent's and his own club's regulars out, the total, the spread, home
or road, the simulation's read, the model's own chance, Kalshi's crowd.
On the 64 BET unders of 4 Nov (29-35) one separated the losers from the
winners: his last three games averaging over the line, on 14 of the 35
losers against 4 of the 29 winners. Across every graded prop with a log
(5,647, 28 Oct to 4 Nov) it moves the outcome beyond the book's price:
the over landed 6.7 points under the book's chance where his last three
had averaged half a sigma or more under the line, 3.7 a little under, 4.1
about on it, 3.3 a little over, and 0.2 under it where they had averaged
half a sigma or more over. Two more turned up pointing under: a club
favoured by 5 to 10 lands over 43% against the book's 49% (both halves of
the nights; starters on favourites of 7 or more play 1.5 minutes under
their projection), and when his last five games' minutes run above his
season the projection takes the spike at face value and he plays 1.7
minutes under it (1.6 to 3.1 over it when they run below).

**The three levers, measured twice walk-forward** (`lab/props_levers3.py`,
`lab/props_bookside.py`): each lever's size fitted by least squares on
the nights before each night and applied to that night, from the fourth
night on, first as a push on the projection in the stat's units (form:
the gap between his last three games' per-36 and his rate, at his
minutes; the favourite: his club's spread on the projection; the minutes
shrink: a share of the minutes part taken off), then as a correction on
the book's chance where the consensus lever lives (capped at six points).
The BET band at the shipped blend, 12 nights:

| Lever | As a push on the projection | As a correction on the book's chance |
|---|---|---|
| none | 133-97, +8.0 units | 132-97, +7.4 |
| recent form | 160-120, +4.7 | 166-125, +6.6 |
| the favourite's script | 128-95, +6.0 | 139-106, +5.3 |
| the minutes shrink | 136-101, +6.1 | 136-111, −3.9 |
| all three | 164-123, +4.9 | 201-165, −5.9 |

Says against does did not improve on any of them (61.0 against 57.8
without, 57.1 to 54.9 with); the model's side where it stands 20 points
from the book landed 52.1% without the levers and 52.4% with all three;
the model's own Brier moved from 0.2632 to 0.2628 with the minutes
shrink and nowhere with the others. In sample the form push over-corrects
(the hot bucket's say-so goes from 47.6% to 54.5% against a landed
46.5%): the model's projection already carries most of his form, and what
the bucket table had found was the book's line lagging it, which the blend
inherits at four parts in five. Seven nights of logs are too few to size
that correction, and the walk-forward says the first attempt loses money.
The minutes slope came out at −1.95, full reversion and beyond, which is
not a model, and the favourite's at a tenth of what the bucket table
shows, so the residual regression is swamped by the big-stat markets. None
of the three goes on the sheet. The shade is the lesson: a measured lean
bolted on in sample lost out of sample.

**What changed.** Recent form rides on the props as a line of its own,
shown, not scored: `props_form` on the slate (his last three games with
the stat, how many over the line, on it, their mean; `form` on every
prop, kept through the trim), a why line that says it is shown and why,
and on the page `propForm` (the slate's block, or the log a file from
before carries), `propFormAgrees` (with the pick when two of the three
landed its side, against it when two landed the other, split otherwise),
the line on the best card and the panel in green or red, and the record
tile's own line, "his last three with the pick W-L · against it W-L
(shown, not scored)", with two tiles on the Props tab. The selftest reads
the form block and the why line; the harness reads the line on George's
card and panel with its colour and the why line. Nothing scored changed.

## The close, the best app, the BET band in front, the prior capped, 6 Nov 2026

The user, on the suggestions: "Ok let make the suggested changes with
thorough testing first. And for the bet band cards, make that more visible
and why. The shrink you are referring to, let do that as well but really
make sure its tested because i dont want to run into any of the recent
issues we fixed."

**The prior, tested before it was touched** (`lab/props_prior.py`). The
test opened with a finding: last season's prior has been read on one night
this season. On 28 Oct 995 of the 1,054 projected props said "blended
with last season's"; from the 29th none have (8 on the 29th, Dejounte
Murray; 0 of the 5,000 since), because the props run found no
last-season ledger beside slate.py. The slate's log says so at the top of
every run ("LAST SEASON'S LEDGER NOT FOUND") and the page when a file is
loaded. Every projection since the 29th rests on this season's games
alone. On the one night the prior was in play, the why line carries this
season's rate and games, last season's rate and minutes, so the blend can
be re-read at other rules and the projection rescaled: 965 graded men,
three or four games each.

| Rule for last season's weight | Rate at his minutes (1.00 on the money) | Model's fit on those men (Brier) | BET band on those men |
|---|---|---|---|
| half of its minutes (as shipped) | 0.924 | 0.2625 | 2-10 |
| a quarter | 0.931 | 0.2619 | 2-5 |
| a quarter, capped at this season's minutes | 0.942 | 0.2639 | 3-4 |
| none | 0.971 | 0.2778 | 36-26 |

Half runs 7.6% high and loses. None calibrates the level but fits worst:
three games alone is too thin, and 56 of the 965 men would lose their
projection to the sixty-minute floor. A quarter capped at this season's
minutes is the middle, better calibrated and a better band than half with
the fit within 0.002 of the best, and 11 men lose a projection. That is
what ships: `PROPS_PRIOR_SHARE` 0.25 and `w = min(last season's minutes
capped at 1,000 × 0.25, this season's minutes)` in `props_rate`, the why
line saying the weight and whether the cap bound. One night of evidence,
honestly labelled; it matters only once the ledger is back, and the record
judges it then.

**Closing line value.** `python slate.py nba-props --close` (Close NBA
props.bat), a few minutes before the first tip: the same run, written as
`nba-props-close-DATE.json` in the close format (`PROPS_CLOSE_FORMAT`).
Loaded on the Props tab after the morning's file, `applyPropsClose`
attaches each prop's closing line and prices to the row already loaded
(`close`: line, op, up, book, at) and adds none; a prop in the close file
with no morning row is counted and ignored. A pick's value against the
close (`propClv`) is the edge it was bought at less the edge at the close:
the chance re-read at the closing line by the sheet's own blend
(`propChanceAt`) and the need from the closing price, so a pick beats the
close when the market moved its way, in line or in price. The card and the
panel carry the line ("The close: 24.5 at −110 · the line moved the pick's
way · beat the close by 2.1 points of edge", green or red); the record
keeps how many picks beat the close and the points a pick, by band, on the
card's tile and as a tile on the tab. A sheet that keeps beating the close
has an edge the market agrees with, read in weeks where results at 55 to
60% take months.

**The best app for a single pick** (`propBestApp`): the pick's side read at
each of the four apps' line and price off the books on the prop, the
chance re-read at the app's line, the app named on the card and the panel
when it beats the carded book ("Best app: DraftKings 5.5 at −112 · 56.1%
there, edge +4.9 against +2.0 at fanatics"). On 185 BET picks of ten
nights the best app had a better line or price on 64, 0.3 points of edge a
pick. The call and the grade stay at the carded book.

**The BET band in front.** A BET card carries a badge, its edge tier ("3
to 5 points of edge", "5 to 8", "8 and up") and a why line in words from
its own numbers (`propBetWhy`): "Why a BET: 56.4% clears the 52.4% that
−110 needs by 4.0 points · the model says 58% at a fifth of the say, the
book 50% · the books' consensus with it (−1.5 on the over) · the top
lever Pace +0.3, against it." The panel carries the same line above the
tiles. The LEANs sit quieter under a divider that says what the record
says of them (the band says 55% and does 52% over 1,300 graded picks).

**Two more lines that measure themselves** on the record: a man on a club
favoured by five or more, and a man whose last five games' minutes ran
above his season, each by the side the sheet took, shown, not scored, so
the favourite's script and the minutes spike keep counting without a
script.

**Tests.** The selftest reads the prior's weight at a quarter and the cap
(70 minutes last season weigh 17.5; 2,000 would weigh 250 and are capped at
his 50), the why line's new wording, and the close file's name and format.
The harness, on a seeded night: the BET card's badge, tier and why line
against the panel's, the LEANs' class and the divider's place and words,
the best app on Brunson's over and none on Maxey's under, the close file
attached to two props with one ignored, the card and panel lines with
their colour, the stored close, the record's close line and tile, and the
favourite's and the spike's lines on the tile and as tiles.

## The form block kept, and what the first graded night of the close said, 7 Nov 2026

The 6 Nov backup carried the slate's "his last 3 games" why line on every
projected prop and no form block on any row: the page copies a fixed list
of fields off a props file and the block was not on it. The card and the
panel read the log instead, so nothing showed; but the log is trimmed
with the night after seven, and the form line and the record's two form
tiles would have gone with it where the block, small and not trimmed,
stays. The row keeps the block now. The harness seeds a props file whose
Trae Young prop carries a block with three games and a log with two games
with the stat, so his form line can only come off the block, and reads it
on the card and in the stored row.

The first night with the close loaded read 4 of 817 picks beating it, with
one line and five prices moved of 825: the close file was written at
20:11 UTC, nearly four hours before the first tip, and the morning's file
close to it. The close run belongs within minutes of the first tip.

The record tiles, read for what they cover: the BET, LEAN, no-edge, taken
and pairs tiles are life to date and carry each night's band as carded,
so they mix three models (the model at a third of the say to 29 Oct, the
shade from 30 Oct to 4 Nov, the realigned blend from 5 Nov); the
favourite's tiles are life to date too, off the spread, which stays on
the row; the form and the minutes-spike tiles read the log and the
levers, which the trim drops after seven nights, so they cover the last
seven nights on the tab; the consensus tiles cover the nights with a
consensus on the row, 5 Nov on; the close tile the nights with a close
loaded.

## The tells on the cards, 7 Nov 2026

The user, reading the Is it working block: "add to the cards that have
the minutes spikes some sort of color indicator on the level that would
stand out so i can see if that is a bet worth taking", and "have it
provide the props that fit in the green categories".

Measured first, walk-forward on the 17 nights to 6 Nov, each night
reading the record of the nights before it and nothing of its own: a
slice (a minutes spike on the pick's side, a favourite's man on the
pick's side, the books' consensus with or against the pick, his last
three with or against it) is green when it has done at least what it
claimed on 50 graded picks or more, red when less. A BET or LEAN pick
with a green tell and no red one:

    BET+LEAN, every pick        1682-1576  says 56.2  does 51.6  -142u
    a green tell, no red         740-674   says 55.6  does 52.3   -38u
    a red tell                   275-265   says 56.2  does 50.9   -31u
    BET, every pick              306-316   says 60.2  does 49.2   -59u
    BET, a green tell, no red     80-94    says 58.4  does 46.0   -26u
    BET, a red tell               56-48    says 60.1  does 53.8    -1u

A blanket rule of the green categories does not beat the band, and in
the BET band it does worse, because the most common tells are the form
ones and they flip from week to week (his last three against the pick,
read green on the nights before, went 255-270 after; read red, 22-12).
Slice by slice, two held:

    the favourite's over, read red     98-134   does 42.2 against 55.6 claimed
    the favourite's under, read green  208-162  does 56.2 against 55.8
    the minutes spike's under, green   107-73   does 59.4 against 54.7
    the minutes spike's over, green    23-10    does 69.7 against 56.1

So the page carries two tells, not a green-category rule: on a best card
and the prop's panel, a chip for a minutes spike (the lever "Minutes,
his last 5 against the season" at +0.3 or more) and a chip for a
favourite's man (his club favoured by five or more), each coloured live
off the Is it working line on the pick's side, green where that line has
done at least what it claimed on 50 graded picks or more, red where
less, grey under that, with the line's does, claimed and count in the
chip. The record and the chips read the same predicates, so a tile and
a chip never disagree. A filter above the best list keeps the picks with
a green tell and no red one, or with a red one. His last three stays a
line of its own, coloured by with or against the pick, with no colour
for its record. Shown, not scored: the chance does not move.

The harness seeds a pool of graded picks on an earlier night so the
spike's over reads green (41-20), the favourite's over red (20-41) and
the spike's under too few (6-4), and reads the chips on Embiid's,
Towns' and Brunson's cards and none on Maxey's, the filter both ways,
and the panel's chip and note.

## The tries beside what the box says, 7 Nov 2026

The user, on De'Aaron Fox's panel: "are we able to track how many
attempts the player made at the 3's for example, or assists, things like
that", "in the same section as what the box says happened area",
"highlight in yellow or purple or some separate from the data already
there".

The ledger's player line had never kept the three-point attempts, only
the makes, so this is a slate change first. The line keeps the tries
last, as an 18th item (NBA_PLAYER_KEYS, nba_player_line), read from
ESPN's 3PT made-attempted column and the league's box scores'
threePointersAttempted; a line from before is 17 long and reads them as
None, and the daily ledger run, which already read older games' summaries
again to fill the six-item lines, now reads any game whose lines are
short of 18, so one run fills the season. The player logs carry the
tries, and props_game_tries words them beside the box: his shots from
the floor, from three and from the line, the market's own kind first
with his usual number at those minutes ("tries: 2 of 6 from three (his
usual 8.4 at those minutes) · 20 from the floor · 7 of 8 from the line"
on a threes prop; the floor first on a points one). A game whose line
predates the tries says so in the same place. The props run writes the
line as each game's seventh element on the row's log; the grade writes
it as the eighth item on the night's box line, per market.

The page reads both: the what-happened cell ends with the tries in
their own colour, the crowd's purple with its wash, after the factors
in green, red and plain; the heading says the tries are in their own
colour; the graded night's own line keeps them on the row (atries,
trimmed with the rest after seven nights). A file from before carries
none and the cell reads as it did.

The selftest reads the line's length and last item, a 17-long line's
None, the log's tries, the wording on a threes prop and a points prop,
the no-tries wording and the empty cases; the harness seeds a game with
the factors and the tries and a grade file with the eighth item, and
reads the cells, the heading and the stored row.

## The Spike column and the tells filter on the table, 9 Nov 2026

The user: "is there a way to have a filter on the every props on the
date section to be able to find the players with minute spikes?"

The table of every prop on the date gains a Spike column: the minutes
lever's push, his last five games' minutes against his season in the
stat's units, the same number the chip reads, green at +0.3 and up and
red at −0.3 and under, blank where a prop has no minutes lever, and
sortable like the rest so the spikes come first. The filter row gains a
tells select: a minutes spike, a favourite's man (his club favoured by
five or more), a green tell with no red, or a red tell, the last two the
chips' own colour read live off Is it working. The view is kept with the
rest of the table's view. Shown, not scored.

The harness, on the seeded night: the column's header, Embiid's green
+0.5 with its title and Maxey's blank, the four filters' lists, and the
sort with Embiid first.

## One bet a man a night, and the favourite's over measured as a rule, 10 Nov 2026

On 9 Nov the BET band was five overs in one game, four of them Stephen
Curry's. The Warriors won 138-87, Curry played 21 minutes of a projected
36 and all four lost; the record counted 1-4. The night before, Darius
Acuff's five overs had counted as five wins. The user took both
suggestions made in the grade and asked for thorough testing.

### One bet a man

A man's BETs on a date land or miss together. The best list opens with a
note when the date's BETs sit on fewer men than cards, or on several men
in one game ("The 4 BETs on this date sit on 2 men in 1 game: a man's
BETs land or miss together, so that is 2 bets, not 4; and one game
carries them all, so a blowout or a slow night hits every one."). The
card with the most edge among a man's BETs says it is the one; his
others say they are the same bet as that one; the panel carries the same
line. The record keeps a tile beside the BET band, one bet a man a
night, the man's BET with the most edge standing for the night, with the
over on a favourite's man counted on its own line, and the card's tile
carries the same count. Counted that way the band since 5 Nov was 11-5
on 16 man-nights where the cards said 21-11.

### The favourite's over, measured two ways and not scored

The grade had said the leak sat with clubs favoured by five to eight.
Measured on the 11,528 graded props of the twenty nights to 9 Nov, each
replayed under the current blend (the market the spine, the model a
fifth, no shade; the replay reproduces the bands as carded since 5 Nov
on 2,850 of 2,852):

The market's own fact, whatever side the sheet took. The over lands
under the book's devigged chance nearly everywhere, and by more on a
favourite's man:

    favoured by 5 to 8    1,397 props  42.7% against 49.5%  -6.8 (5.1 SE)
    favoured by 8 to 11   1,064 props  45.9% against 49.4%  -3.5 (2.3 SE)
    favoured by 11+         762 props  44.0% against 49.6%  -5.6 (3.1 SE)
    favoured by 5+        3,223 props                       -5.4, both halves
    within 2              1,321 props  46.8% against 49.6%  -2.8
    dog by 5 to 8         1,229 props  50.9% against 49.6%  +1.4

One point of spread at a time the gap runs -1.1, -6.4, -10.2, -10.5,
-0.7, +1.9, +2.5, -3.7, -7.7, -11.0 from five to fourteen: the bucket of
five to eight was noise. The effect is the favourite, not a size of
favourite.

As a hold on the BET band (an OVER on a man favoured by five or more is
kept out). A hold only removes picks, so it helps by what the held picks
lose:

    held, by cards              11-16  -6.5u  lose in 88% of 2,000 draws
    held, one a man a night      8-7   -0.0u
    held, 5 to 11, by cards      5-11  -6.6u  91%; one a man a night 4-6
    holds chosen from the nights before alone (the market's gap at
    2 SE or 1 SE, or the sheet's own overs): 5-4, 6-8, 6-7 by cards,
    3-2, 4-3, 4-2 one a man a night

By cards the held picks lose; counted as independent bets they break
even, on fifteen man-nights; and the rules that choose what to hold out
of sample do not help.

As a correction on the book's chance (a share of the gap measured on the
nights before comes off the book's over chance for a favourite's man,
the sheet re-read):

    half the gap, 5+     BET +1.2u by cards (55% of 4,000 draws),
                         +2.2u one a man a night (60%); 89 unders
                         added at 47-42, 20 overs removed at 7-13
    the whole gap, 5+    BET +21.6u by cards (81%), +9.4u one a man
                         a night (77%), all of it in the second half;
                         the BET band 593 cards from 284, 87% unders,
                         the under on three favourites' men in four
    half the gap, 8+     nothing; 2+ worse (25%, 8%)

The whole gap is the over's shade again on a quarter of the board, with
a gain inside the noise. Neither rule is scored. The red chip stays a
tell on the card, read live off the record; the one-a-man tile carries
the over on a favourite's man on its own line, so the question keeps an
honest sample; and the under on a favourite's man, 943-691 at 57.7% on
every band replayed, stays the green chip it was.

The harness seeds a graded night with Curry's three BETs, the one with
the most edge a loss, and a Pelican's under, and a night on the tab with
his three again and Podziemski's, and reads the note, the four cards'
lines, the panel's, the tile and the card's line.

## The spike's chip split by the favourite, 10 Nov 2026

The user, after the one-bet change: "which would be more impactful, the
minutes spike for the over or the spread chip towards the under?" On
Curry's cards the two chips had pulled against each other, a green spike
beside a red favourite.

Head to head on the ten nights that keep the levers, 30 Oct to 9 Nov,
7,207 graded props, each replayed under the current blend (the nights
before 2 Nov from an earlier backup, where their levers were whole).

The market's own fact, the over's landing rate less the book's chance:

    a spike, on a favourite          -6.3 on   402   (-6.8, -6.2 by half)
    no spike, on a favourite         -5.9 on 1,768   (-6.6, -4.8)
    a spike, not on a favourite      -1.5 on 1,051   (-6.6, +2.4)
    no spike, not on a favourite     -2.8 on 3,986   (-2.5, -3.3)

The books price a man's rising minutes; they do not price the favourite.
The favourite is the larger of the two by four points, in both halves.

The split as first promised to the user, a spike on a favourite's man
reading red and a spike elsewhere reading green, was tested before it
was built and did not hold as stated. Read off every graded prop, as the
chips did, the spike's over is red on both sides of the split (43.1% and
49.1% against claims of 53), because the sheet's chance on a no-edge
over runs high everywhere; and read from the nights before, neither the
pooled colour nor the split one called the night: the BET and LEAN picks
under a red chip went 116-85, under a green one 9-9.

Read off the BET and LEAN picks, the picks a card is drawn for, one side
is steady:

    the over on a spike man, not on a favourite   71-41   63.4%
        by night 1-2, 13-8, 10-8, 10-3, 13-3, 9-5, 11-8, 4-4
        one a man a night 31-20; after its own record read green 47-23
    the over on a spike man, on a favourite       24-38   38.7%
        by night 2-6, 6-6, 0-3, 0-11, 9-0, 7-12
        after its own record read red 16-12
    no spike, on a favourite                      72-54   57.1%
    no spike, not on a favourite                 100-105  48.8%

So the chip is built on what held. A spike on a man not on a favourite
reads its own pool, the BET and LEAN picks on such men by side, and
takes their colour at 50 picks or more. A spike on a favourite's man
carries no colour and says so, with its count, naming the favourite's
chip as the read: its record swings by the game and has no steady
colour to show. The favourite's chip is unchanged, read off every graded
pick, which is where its evidence lies. The spike's two tiles keep every
band's count and carry under them what the chip reads, off a favourite
and on one, and the card's line the same, so a tile and a chip still
read the same numbers. Shown, not scored.

Corrected with it: the day's advice that an over under the red chip is a
pass "with or without a spike". In the bet bands the favourite's over
without a spike went 72-54 on these nights; the market's fact stands,
and the chip is a caution on the price, not a rule on the pick.

The harness seeds forty wins in sixty on spike men off a favourite,
twenty in sixty on a favourite's spike men, and thirty no-edge losses
that must stay out of the chip's pool, and reads the three cards' chips,
the filter both ways, the tile's line and the card's.

## Three-leg tickets under the BETs, 11 Nov 2026

The user, the morning after 10 Nov, with Aday Mara, Bennett Stirtz and
Collin Gillespie as his examples: "you see how they all have some edge,
and the last 5-10 hit rates looked really good too, along with the
levers and no red chips towards the over. I'd like for you to put
together and replace in the leans section of the 'Leans Below' with 3
leg props cards, in the same betting apps that have great last 5-10 hit
rates, no reds chips, levers towards the over that i can use to test for
3 leg parlays." Then: "Or what about for unders too", "basically 3 guys
on a card that have really recent history towards that outcome", and
"make it awesome".

### What a leg is, and a ticket

A leg is a pick with an edge on its card and at the app's own line and
price, whose last five games went the pick's way four times or more and
whose last ten (eight or more played) at least half the time, with more
measured levers toward the pick than against, and no red chip. The over
on a man whose club is favoured by five or more stays out unless its own
record reads green, so a page with little graded yet does not list the
measured leak for want of a colour.

A ticket is three legs on three men at one app (Fanatics, DraftKings,
FanDuel, BetMGM), each leg read at that app's line and price, the chance
re-read at the app's line by the slate's own blend when it differs from
the carded one. Three different games come before a shared one, because
the apps price same-game legs their own way; then the most expected
value. A man sits in one ticket a date, six tickets at most. The chance
is the product of the three legs' chances (two players' props land
almost independently, measured for the pairs), never more than the
weakest leg's, and two overs on one club carry the pairs' measured 0.95.

Under the BETs the choice is "3-leg tickets, either side" (the default),
"overs", "unders", or "the LEANs one by one", which is the list as it
was. The choice is kept.

### Measured before it was built

First by the carded lines (lab `props_trebles.py`), then exactly as the
page builds them (lab `props_t3_apps.py`): each leg at each app's own
line and price, the chips read from the nights before, nothing known
after the tip, on the eleven nights that keep the game logs and the
levers, 30 Oct to 10 Nov, replayed under the current blend (the replayed
call matches the stored one on 99.9% of the 3,600 props from 5 Nov).

What each test does to a BET or LEAN pick taken alone, by the carded
line:

    every BET and LEAN pick              751-595   55.8%   says 56.4%
    last 5: four or five his way         322-247   56.6%
    last 5: three                        230-179   56.2%
    last 5: two or fewer                  98-84    53.8%
    last 10: seven or more                64-44    59.3%
    last 10: five or six                 105-69    60.3%
    last 10: under half                   35-28    55.6%
    more levers toward than against      437-346   55.8%
    levers level or against              314-249   55.8%
    a red chip                           105-104   50.2%
    no red chip                          646-491   56.8%

No one of them is an edge by itself: the recent hit rate moves the
landing rate by a point or three, the levers by nothing, and the red
chip is the largest, five to six points, which is the favourite's over
again.

Together, as the page asks them of a leg:

    the qualifying legs, one at a time    45-28   61.6%   (a sample of 73: plus or minus 5.9)
        the overs                         20-7
        the unders                        25-21
    the tickets, either side              2 of 12, the sheet said 21.1%, +0.7 units
        by night  4 Nov 0 of 1 · 6 Nov 1 of 3 · 7 Nov 0 of 1 · 8 Nov 0 of 4 · 9 Nov 0 of 2 · 10 Nov 1 of 1
    the overs alone                       1 of 4, +2.9 units
    the unders alone                      2 of 8, +1.0 units
    held to three different games         1 of 9, -3.1 units

The nights before 4 Nov list nothing: nobody had eight games in his log.
On 10 Nov the page's ticket was Stirtz's points, Mara's points and
rebounds and De'Andre Hunter's points and assists at FanDuel, two of
them on one club, and it won at +587. Of the user's three examples Mara
(four of his last five, five of ten) and Stirtz (five of five, seven of
ten) are legs; Gillespie's assists over 2.5, which won, is not: two of
his last five and four of nine had cleared it.

Twelve tickets say nothing yet. Three legs at 62% land together 23% of
the time and the usual price asks 18 to 19, so the tickets pay if the
legs' rate is real, and the legs' rate sits one sigma above the band's.
A test with a record of its own, not a measured edge, and the divider
above the tickets says so with these numbers.

### The record is kept honest

A date's list is written to its rows when the date is graded, before any
result lands: each ticket as a spec on its first leg's row (`t3`), the
app, the three legs' keys and what each read there (line, price, chance,
side). A date with a result already on it is never listed after the
fact. The record carries "Three-leg tickets as listed, to test" from
those specs alone, at the product of the three prices, a void or pushed
leg dropping out as the apps settle it. A list asked for on a graded
date that kept none (an older night, or another choice of sides) is
rebuilt from the rows for study, says so, and stays out of the record.

Take marks a ticket as one being placed. The spec keeps the legs as they
read when it was taken, so a reload of the props file that moves a line
or turns a pick to the other side leaves the ticket as placed, and it is
graded on its own lines and sides. Taken tickets sit in the Taking strip
on the Props tab and on the day board, in the copied text, on "Three-leg
tickets you took" on the Props record and under What you took. Copy
ticket puts one ticket in words, to key into the app.

### The same three at another app

The user, on seeing the cards: "it's important that each card for the 3
legs it comes up with is all for the same betting app. Or if the same
guy can cover his line in two or more betting apps along with 2 other
guys as well, that way I can have a mix?"

A card is one app throughout, as built. Where the same three men each
pass the leg's test at another app's own line and price, the card
carries a tab for that app under the band, with what the ticket pays and
the chance all three land there; the tab shows the ticket at that app,
each leg re-read at its line and price, and Take and Copy act on the
version shown, so the same three can go in one app or two. Where an app
posts all three and one does not pass, the app is crossed and the card
says which man and why: his line there and how many of his last five or
ten cleared it, or no edge at its price. An app that does not post all
three is left off.

The list, the list kept at grading and the record stay on the app with
the most expected value, so a ticket is counted once. A bigger price on
a tab is a harder line: on 8 Nov the first ticket read +465 at BetMGM
with 23.5% to land and +724 at FanDuel with 15.2%. On the thirteen
tickets of 4 to 10 Nov in the user's backup, seven could go in a second
app and five named an app where one leg failed.

### Two legs or three

The user, the same day: "what about instead of the 3, we do 2 legs?
would those be better?", "the absolute best 2 men pairs based on the way
we are setting up the 3 legs but for two? Maybe the hit chances for the
parlay will be better percentages", and "thoroughly test multiple times
to make sure the algorithm is finding the best pairs."

The legs are the same either way, so the question is the parlay's own.
Replayed by the same rule on the same eleven nights (`props_t3_apps.py`
with the legs a ticket as an argument):

                          two legs, on two games     three legs
    either side           7 of 20   +2.8 units       2 of 12   +0.7
        the sheet said    34.9%, the price 31.4%     21.1%, the price 18.2%
    the overs alone       5 of 6    +10.0            1 of 4    +2.9
    the unders alone      5 of 11   +3.9             2 of 8    +1.0

Two legs land about one ticket in three against one in five, so a record
reads sooner and the losing runs are shorter; three pay more a ticket if
the legs' rate is real, and lose faster if it is not. Twenty tickets
settle nothing between them. So two legs are the default, three a choice
away (the "legs" box beside "under the BETs", kept), and the list kept
at grading keeps both, the two-leg list and the three-leg one whichever
the tab showed, each with its own record line, so the page answers the
question on the nights to come.

A two-leg ticket is the best pair first: two men on two games at one
app, by the same leg rule, the most expected value, a man in one ticket,
six at most. Two legs never share a game: a same-game two is priced the
app's own way and has the Same-game pairs section. The pair search reads
every qualifying leg at every app (the three-leg search the first sixty
by expected value, beyond any night's count), and since a ticket's value
is the product of its legs' values the best pair is exact.

**Is it the best pair.** Checked three ways, each apart from the page's
own code:

- `tools_check_tickets.js`, an oracle with the leg's rule written a
  second time from the words above: a random night of props (games, men,
  markets, lines, chances, each app's prices, logs, levers, spreads),
  every valid ticket enumerated by brute force at every app, and at each
  step the page's ticket must be valid and worth exactly what the best
  one left is worth, two legs and three, either side, the overs, the
  unders, the list ending only when nothing valid is left or at six.
  750 ordinary nights on three seeds and 150 busy ones (a thousand valid
  tickets on the median list, 143,838 on the largest): 4,977 two-leg
  tickets and 3,697 three-leg tickets, no failure.
- The checker checked: four wrong builds of the page (the least value
  first, only the first three legs read, two of the four apps searched,
  a same-game two let through) are each caught, the last on the ordinary
  nights, which is why the harness runs both kinds.
- The six real nights of 5 to 10 Nov in the user's backup: every list
  the page builds, two legs and three, the three choices of sides, 55
  tickets, against an exhaustive replay in Python on the rows' own
  numbers: identical. Under the replay's unrounded chances one list
  differed, 8 Nov's unders, where two pairs sat within 0.0001 of each
  other (0.13756 against 0.13750): a photo finish decided by the fourth
  decimal the row stores, not a different rule.

The harness runs a seeded sample of the checker on every build, fourteen
ordinary nights and six busy ones.

### The card

A ticket: the app and the price in a band, each leg a line that opens
his panel, with the pick and the market in the side's colour, the price
and the chance, his last ten as pips (filled where the game went the
pick's way, a ring where it did not, the last five set apart, each pip
naming its game), the counts, his last five's average and the levers; a
perforation, then the chance all three land, what the price needs, the
edge and what a unit wins, or the result once graded. Green or red in
the band when it has graded.

Shown, not scored: no chance on any prop moves, and slate.py is
untouched.

The harness loads a props file of ten men on four games and reads the
two tickets either side (three games first, then two legs sharing a game
with the 0.95), the four men who make no leg (a cold hand, the levers
against him, another app alone, the over on a favourite's man with no
record), the overs alone, the unders alone saying there are none, the
LEANs back; a leg's panel, the copied text, the take and its spec; the
file loaded again with a pick turned and a line moved, the taken ticket
unchanged and the list rebuilt; the day board; then the grade, the list
kept before the results, the taken ticket winning on the side it was
taken on where the card's row lost, the three record lines, and a
rebuilt list that stays out of the record. For the tabs it posts one man
a point lower at DraftKings at a price with an edge, and reads the two
cards' tabs, the crossed app and its reason, the first ticket shown at
DraftKings, the copy and the take there with the tick on its tab, the
take undone, and the card back at FanDuel. For two legs it reads the
default on a first visit and the kept choice, the two pairs on two games
(the two men left on one game make no ticket), the tabs, the overs and
the unders alone, the copy, and after the grade the two-leg list kept
beside the three-leg one with its own record line.

## The team-total gap becomes a watch, 11 Nov 2026

The re-test's file came back the same day (NBA.md, "The team-total edge
was the season pull's fault"). The two seasons behind the gap rule and
behind the simulation's weight on the anchored home team total read one
book's line, and the season pull had kept that book's alternate points
with another point's prices. On the books' own lines the gap reads a coin
less the price. Both come off the score; nothing is hidden.

**The gap.** `nbaTeamTotalGap` is unchanged: the implied number, the gap
and the side a point or more off it. What it is called changed.

- On the rail, `signalList` pushes it as a watch: gold, the badge "gap
  watch", the words ending "not scored". The Simulation section's dot on
  the jump bar is gold with it, green only when a scored call is live.
- On the Simulation card the chip is `simchip simwatch gaprule`, a dashed
  outline where the green BET fill was, reading "UNDER by the gap", with
  "a watch, not scored" beside it. Inside a point the row says so and no
  more. The Take button stays; a take marked from here carries the band
  "gap watch", and one marked before keeps "gap rule" as it was marked.
- In the record the table is "The team-total gap, a watch", the same
  tally by side, with what the re-test read at the apps over the two
  seasons in the column where the old figures were: 212-210 at home for
  −22.3 units against the book's own number and 176-190 against the other
  books', 222-210 and 194-179 away. (The column first carried 2025-26
  alone, 136-117 at home; 2024-25 was read the same day and went 76-93.)
- The phone sheet's list of the simulation's calls at BET or better no
  longer carries the gap (`phonePayload`); `m.html` still reads an old
  code's entries.

**The anchored home team total.** Its shrink was 1.5, written by the slate
into every row's simulation block. `NBA_SIM_SHRINK_RULES` now rules that
key from the page, 0.3, whatever the row stored, so a slate written before
this day reads the same as one written after; the away side and the own
view were 0.3 already. A 67% is worth 55% and reads no band. What the 1.5
would have called and the page no longer does is tallied as a watch of
its own under the gap's table, "The anchored home team total at its old
weight": calls, record, says, does, units. On the 160 games so far that
is seven calls, 6-1. The note under the record says the team totals were
scored on lines that were not the book's.

The harness stores 1.5 on a graded row and reads the home team total at
no band with no anchored table opened for it, the watch row with its one
call, the gap's heading and column, the dashed chip and its class, the
gold signal with no green one beside it, the jump bar's dot, and a block
built today carrying 0.3. The page was then loaded with the backup of 10
Nov: the gap 7-6 at home and 4-8 away as before, the seven calls of the
old weight on their own row, no script errors.

## The phone sheet through the page's store, 11 Nov 2026

The user: "I saved the log for today for what I am betting and then took
the picture with my phone and it brings up the model but nothing in it."
The code's link went to `m.html` on the page's own host with the night in
its hash. On claude.ai the page is private and is shown framed by the
viewer; a phone that follows that link is sent to the viewer and the main
page, with a phone's empty storage, and the hash never arrives. The sheet
also had no place for a ticket marked Taking, since the tickets came
after it.

**The store.** Where the viewer gives the page its store (`claude.use("db")`),
the Phone QR button saves the night's sheet there, whole: one document,
`phone/latest`, `{v: 2, d, at, sheet}`, the sheet being `phonePayload` with
nothing trimmed. One write a press; a store that answers `unavailable`
gets one more try. The dialog says it is saved and how many lines, and
the code it draws is the page's own address on claude.ai, read from
`phone/config` beside the sheet (written through the database at the
publish, so no address sits in the source). With no address there the
words stand in for the code: open the page in the Claude app. A write the
store refuses, or a viewer that gives no store, is said in the dialog and
no code is drawn, since the old link would land on an empty page.

**The phone.** `phoneWatch` runs once after the first draw. A view the
width of a phone (760 pixels or less), or one with no card and no props
of its own, subscribes to `phone/latest` and opens the sheet over the
page (`phoneSheetShow`): the same sections and lines `m.html` draws, the
date with its weekday, when it was made, and a note when it is not
today's. A button opens the model behind it; a sheet shut by hand stays
shut until a newer one is saved, and a newer one opens on the same
subscription. A view with a card of its own asks the viewer nothing at
load, so the computer sees no prompt it did not ask for.

When a phone's view has no sheet to open, a line across the top says why
and what to do (`phoneHint`), since the page behind it is an empty model
on a phone, which is what the user met: nothing saved yet (press Phone QR
on the computer, and the sheet opens there by itself when it is saved);
for a guest, the owner has not saved one; and where the view gives the
page no store, open it in the phone's browser signed in to claude.ai.

**Shared, view only.** The user, the same hour: "what if I want to share
the QR or have someone else see it too without changing" anything. The
store's rule, declared at the publish, lets everyone the page is shared
with read `phone` and only the page's owner write it:

    capabilities: { downloads: true, db: { rules: [ { path: "phone", read: "view", write: "owner" } ] } }

Someone the owner shares the page with from the Share menu (Viewer is
enough, signed in to Claude) scans the same code and gets the sheet marked
"shared with you" with nothing to press and no way past it
(`user.isOwner()` false; the Escape key leaves it up). The card, the props
and the record live in the owner's browser and never reach the store, so
there is nothing of his for them to change. For someone with no account
the dialog copies the sheet as plain text (`phoneSheetText`).

**The detail behind a pick.** The user, once it worked: "I'd like to be
able to see the prop cards when I select it so I can see the graphs and
info too", and then: "if I want to share my picks for the day with
someone, and have them see the details behind the pick without them
changing" anything "but able to see from their phone." The phone has no
props of its own to draw a panel from, and a panel reads more than its
row (the tells off the record, his other markets' floors, the one bet a
man). So on the save the computer draws each prop's own panel as it
stands there (`propsDetailHtml`) for every prop on the sheet: the ones
marked Taking, the best props, the legs of the tickets and the pairs.
`phoneClean` parses each in a template, where nothing loads or runs, and
takes out the buttons, links, fields, images and every attribute but
class, title and a plain style. `phonePanels` packs the lot as
`{id: markup}` through `phoneEncode` (deflate, base64) and the document
carries it beside the sheet: `{v: 3, d, at, sheet, panels}`. Thirty
panels of about 16,000 characters pack to 49,000; the document was
56,000 on the night of 10 Nov against the store's 256 KiB. Over 190,000
packed characters the queue is cut from its least important end (the
pairs, then the night's tickets, then the best props; what is marked
Taking goes last) and the dialog says how many of how many fit. A prop
met first in a pair and then among the takes counts as a take.

A line of the sheet that stands on props keeps their ids, and on the
phone its card carries a mark and opens the detail over the sheet
(`phonePanelOpen`): one panel for a prop, the legs one under the other
for a ticket or a pair, each cleaned again before it is shown. Escape
shuts the detail, then the sheet, then the dialog. Someone the page is
shared with opens the detail the same way; nothing in it can be pressed
but Close. The last-games table's what-happened column asked for 220
pixels and ran the panel off a phone's side; under 640 pixels it now
wraps and the table scrolls inside itself if it must.

**The file to send.** For someone with no Claude account the dialog saves
the sheet as one file (`phoneFileHtml`, through the viewer's own save,
`downloads`): `super-model-DATE.html`, the page's own style with the
picks and, folded under each one in a `details`, its detail. It is a
still copy: no script, button, link, field, handler or outside address,
so it opens in any phone's browser or preview and there is nothing in it
to change. About 770,000 characters on the night of 10 Nov, the panels
repeated under each card that shows them.

**The tickets.** `phonePayload` now carries a ticket marked Taking among
the takes (its legs, the app, the games, the chance all land, the parlay
price) and the night's tickets as the tab shows them, up to six, under
the best props. `m.html` draws both, so the code off claude.ai has them
too; a long night drops the tickets from the code after the likeliest
list.

**A game line opens its game's card.** The user, with the props opening:
"can you have it so the game lines open as well like the props? I really
like this to view on the go or show someone on the fly." On the computer
a game line opens its game in the form: tonight's signals, the forecast,
the pick and its why, every market with its chance, price, edge and fair,
the split, and under them the NBA card (the simulation, who is out and
the starting five, recent form, the middles, the referees, the crowd on
Kalshi, the context) and the why list. All of it is drawn off the form,
so the phone's copy is made the way the page makes its own: at the save
`phoneGamesDraw` keeps the form's sport, every box, the row it had open
and the window's boxes, puts each game of the sheet in, lets `render()`
draw it, reads the containers off (`phoneGameCompose`), and puts the form
back and draws it again before it returns. It is one step with nothing
saved and no draft written; the folds that stood open in the rail stand
open after. A window ticket marked Taking is read at its own numbers.

`phoneGameTidy` makes the card fit a phone that only reads: a signal is
a link to its section on the computer and a chip here; a call marked
Taking keeps a TAKING chip and every other button goes; the two
calculators go, the window keeping its reading; the markets stand open;
the sentences that tell the reader to press something on the computer go
(Press Clear, Type the inputs, type the app's price); the hover notes go.
A section with nothing on the row is left out. The simulation stands
open; the rest fold under their headings, each with its live line. Then
`phoneClean`, as for a prop's panel (it now keeps a fold's open mark).
At a phone's width a market's row sets its numbers on a line under the
pick, where the rail sets them in a column at the right.

A game's card is bigger than a prop's panel: about 33,000 characters, a
little under 10,000 packed. So the games ride in a document of their own,
`phone/games`, `{v: 1, d, at, panels}`, under the same rule as the rest
of `phone`, with its own 190,000 characters (the six games of 10 Nov
were 57,000; a full night of fifteen would be about 145,000). It is
written first and stamped with the sheet's time, then the sheet,
`{v: 4, d, at, sheet, panels, games}`, `games` the count that ride. Every
game line of the sheet keeps its card row's id (`gid`): a bet marked
Taking and a simulation call marked Taking first, then the parlay four
and the straight bets, then the likeliest sides and the simulation's
calls, which is the order the queue is cut in when a night is too big. A
line whose game has no card in the save is a plain line. If the store
refuses the games' document the sheet is saved all the same, its game
lines plain, and the dialog says the games' cards did not save and why.

On the phone a sheet that says games ride beside it reads `phone/games`
once as it opens (`phoneGamesMap`), so a press opens a card without
waiting on the store. A document stamped with another save's time is not
this sheet's and is not used; a read that failed is tried again on the
next press. Every line of a game opens the same card, under the line
that was pressed (`phonePanelOpen({gid, line})`). The file to send folds
the card under each of its lines: 1.4 million characters on the night of
10 Nov, fifty-two folds, nineteen of them a game's card. The legacy code
off claude.ai carries no `gid` and `m.html` is unchanged.

**The Kalshi card read the game before.** Drawing six games one after the
other showed it: the crowd's card sets the sheet's chance at the book's
spread and total beside the crowd's, and it read that chance off the
page's last result, while the card is drawn before the forecast it sits
in has finished. A game opened from the board therefore carried the "by
the sheet" figures of the game drawn before it until something redrew the
form: Bucks @ Knicks on 10 Nov read 50.0% at the spread and the total
where its own were 48.9%. `forecastMatchupNba` now draws the card first
without the sheet's figures and again with its own markets once it has
them. Shown figures only; no chance, band or pick reads them.

**Checked.** The harness stands in for the viewer (`window.claude.use` for
`db` and `user` over an in-memory store, every call logged, `set` refusing
on demand with the store's own codes) and reads: the save with one retry
and the document's shape, the code decoded off its modules to the page's
address, the dialog's lines, the preview over the dialog and the order
Escape shuts them, the text copy; a refused write, no store, an empty
date, a store with no address; the owner's phone opening the sheet line
for line what `m.html` draws from the code, shut and reopened by a newer
sheet on one subscription; a guest on a phone and at a desk with no
control in the sheet; a view with a card asking nothing at load; the
three lines a phone shows when there is no sheet, and the sheet arriving
under the first; the detail opened from the preview, from the owner's
phone and from a guest's (the ticket's two legs, the tiles, the levers,
the last games, every book, no control in it, inside the screen's
width); and the file, saved through the stand-in, opened with scripts
off and nothing fetched, a tap opening a pick's detail. With the backup
of 10 Nov and the limit cut to 20,000 characters, nine of thirty panels
were kept, the takes among them, and a card without one says so. On the
published page the database took `phone/config`, gave it back at the
Viewer's level, and refused a write at the Editor's level with the code
the page words as "only the page's owner saves the sheet". What only the
owner can confirm is the page inside claude.ai's viewer on his own
computer and phone.

For the games the harness puts two games on the board, a bet marked
Taking on one and a simulation call on the other, and a draft of a third
in the form with a fold open, and reads: the two documents, their order,
their shape and the stamp they share; each line's own game; the page
after the save against the page before it, every box and tick, the rail,
the NBA card's sections, the board, the card table, what is disabled,
which sport is pressed, the open fold, and the page's storage with the
draft in it; the card opened from the preview under the line that was
pressed (the signals as chips, the forecast, the pick, four markets
standing open, the split, the simulation open with its table, the rest
folded, the TAKING chip on its own game and not on the other, no
control, id, hover note or handler); the owner's phone and a guest's
reading the games' document once and each of eight lines opening its own
game inside the screen's width; games stamped with another save's time
and a games' document that is gone, both said under the line; a full
store on the games' document and a store unavailable once; and the file
opened with scripts off, a line folding its game's card open and a
heading inside it its section. With the backup of 10 Nov: six games,
nineteen game lines and thirty-three prop lines all opening, the page
identical after the save, nothing off the side at 390 pixels with every
fold open, the save done in half a second. A baseball game, a WNBA game
and an NBA game on one sheet each opened its own card, the form left on
baseball as it stood. With the limit cut so one game would not fit, two
of three were kept, the one marked Taking first, and the third game's
lines were plain. The Kalshi card's check opens two games priced apart
in turn and reads each one's own figures; the same check fails on the
page as it was published before. The harness's scenario was also run
by hand against copies of the page broken on purpose (the boxes not put
back, the sport not put back, the open row not put back, the last draw
left out, the hidden NBA card left as the last game drew it, every line
given the first game's mark, the two documents written in the other
order) and each one was caught; two of them were not at first, which is
why the scenario presses the button with a graded game open and again
with the form on baseball.
On the published page (version 157) the database took `phone/games` as
an empty document with no stamp, which the page does not use, gave it
back at the Viewer's level and refused a write at the Editor's level, as
it does for the sheet.


## A mark keeps the bet, 12 Nov 2026

The backup of 12 Nov was graded against the sheet the user's phone had
saved the evening before, and three of his bets on 11 Nov read wrong on
the page. He had marked Caleb Wilson UNDER 6.5 rebounds at -155; Wilson
took five, a win, and the page listed OVER 5.5 at a loss. A pair on
De'Aaron Fox (OVER 0.5 threes with UNDER 6.5 assists, nine assists, a
loss) read as a win, and a pair on Horford and Smart that won read as a
loss.

**The cause.** A bet on a game keeps its side, price and chance at the
mark, and so does a simulation call and a ticket. A prop's mark was a
flag on its row (`take: true`) and a pair's was the other leg's key
(`pairs: [key]`). A props file loaded later replaces a date's ungraded
rows and carries the flags over, so a mark made at four o'clock was read
from six o'clock's row: the newer line, the newer price, and the other
side where the pick had turned. The pair was built again from the two
newer rows by `propsPairBest`.

**The mark.** Marking a prop writes `took` on the row:
`{side, line, price, chance, band, book, proj, at}`. Marking a pair
writes a spec on one of its two rows, `pairsAt: [{ks, app, kind, f,
chance, at, at0}]`, where `at` is one entry a leg, `[the app's line, its
price, the chance there, the side, the card's line]`. Unmarking takes
them off with the mark. `applyProps` carries both to the row that
replaces theirs.

**Reading it.** `propTook(row)` gives a marked prop as it was marked: a
view over the row (`Object.create(row)`, the row itself at `_row`) with
the side, line, price, chance, band, book and projection of the mark,
the need and the edge worked from them, and the result read from what
the player did against the marked line by `propResOn`. A row with no
`took` reads as itself. `propsPairKept(a, b)` builds the ticket from its
spec the same way, each leg a view on its marked side and line, the
payout from the prices kept. Everything that lists a bet you are taking
reads through these two: the Taking cards on the Props tab and the
board, the copy, the sheet for the phone, What you took and the list of
every pick, and the props record's own line for the props and pairs
taken. A panel opened from a Taking line is the player's panel as the
card stands now, with a line on it saying what was marked.

**Saying it.** A marked prop's card carries the time of the mark. Where
the row has moved from it the card says so and to what ("The card has
moved since you marked it: OVER 5.5 at -135 now (no edge). Your bet
stays as marked."), and the pair's card names the legs that read
differently at its app.

**Marks made before.** A mark that kept nothing cannot be given back
what it read: the row it was made on is gone. `propsFreezeMarks` runs in
`applyProps` on a date's rows just before a file replaces them and keeps
every such mark as the rows stand then, with no time, so a mark is never
re-read a second time. A graded night is left as it was recorded.

**The props made without last season's ledger.** All 982 projections on
11 Nov read "no last season to blend", as on 5 to 8 Nov; on 9 and 10 Nov
one in twelve did. The run had been started in a folder without
`nba-ledger-202526.json`. The page had said so in the line under the
buttons when the file was loaded, and the line is gone at the next
press. `#propsWarn` now stands above the lists for as long as such a
date is shown: where twenty or more projections carry a why and more
than half of them read no last season, it gives the count, the file's
name (the season before the date's own, as `slate.py` names it) and
what to do: copy the file into the folder the props are run from, which
costs nothing and pulls nothing, and run them again. On a graded date it
says the night is graded as it was made. The load's own line names the
folder the run was started in when the file carries it.

**Why the ledger was not read, and the run that now brings it.** The
user: "How do we fix it so it runs last seasons numbers? I have the
ledgers but not sure why it's not pulling them". A run reads its ledgers
from the folder its bat sits in. His props of 9 Nov were run in
`...\OneDrive\My files\The Super Model v139`: at 16:26 UTC that folder
gave the closing-line run 0 games of 2025-26, and at 17:07, with the file
in it, 1,235. On 11 Nov the gap re-test of 11:11 UTC read 2025-26 in a
folder that had it, and the one of 16:03, run with the `slate.py` sent
that day, was in a folder that held `nba-ledger-202425.json` and no
`nba-ledger-202526.json`; the evening's props were run there. A new
folder for a new version had left last season's ledger behind, as it had
on 29 Oct. `slate.py` now looks for a ledger that is not in its folder in
the folders around it and under the home folder and copies the fullest
copy in (`nba_ledger_for`, `ledger_scan`, `ledger_best_copy`; the README's
"The folder"), and a slate or a props file made without last season ends
its window with a block that says so. The selftest has twelve checks on
it, a slate run from a new folder beside the old one among them, and was
run against twelve copies broken on purpose, each caught; on a copy of
his layout with a real 1,234-game ledger a run started beside the old
folder, in Downloads, on the Desktop, outside the home folder, with the
only copy a second download named `(1)`, and with OneDrive on another
drive each found it and copied it whole in under half a second, and a
home folder of 6,700 folders, where the look is cut short at its limit,
still found it.

**Checked.** The harness marks a prop and a pair, unmarks and marks them
again, plants a flag and a pair of keys with nothing kept, loads the
page again, loads a later file for the date in which every one of them
has moved and three have turned, and grades the night: the cards, the
panels, the board, the copy, the phone's sheet, the tiles, the list and
the record's line read the bets as marked, and the rows themselves
grade on the later lines. The same file, made without last season,
raises the bar where the morning's did not. The block was run against
eleven copies of the page broken on purpose (the mark not read, not
kept at the reload for a prop or for a pair, not carried for either, the
pair built again, the unmark leaving what was kept for either, the bar
never shown or always shown, the result taken from the row) and each
was caught; the pair marked the old way was added to the scenario
because one of them was not at first. With the backup of 12 Nov the
graded night of 11 Nov read the same on this build as on the published
one, every card, list, sheet and tile, and the bar showed on 5 to 8 and
11 Nov and on no other date.

## Tickets by best chance, and what separates a leg that lands, 12 Nov 2026

The user, the night after the tickets' first night (his nine went 0-9;
the page's own two-leg list 3-3): "What if we go away from the parlay 2
leg and 3 legs for the props based on the last 5 and instead put
together the best two and three guys that a good chance to each hit to
complete the parlay", then "or we can still keep them as we have but add
the new option as well for the props. i guess its still early to go away
from it", and, with the night's six two-leg cards on the screen (the
unders in them 5-1, the overs 1-4), "Find how we were able to get the
one that hit vs the ones that didnt?"

### What separates a leg that lands

Measured on the fourteen nights that still keep the game logs and the
levers, 28 Oct to 11 Nov, merged from the four backups that hold them in
full (the page keeps a night's logs for seven dates): 10,014 graded
picks, each replayed under the current blend as the page reads it,
nothing known after the tip used (lab `props_hits.py`,
`props_halves.py`). Every split below was read in both halves of the
nights, seven and seven, and is quoted where it held in each.

The picks with an edge on the card (BET and LEAN), 1,566 of them:

    every pick with an edge                 851-715   54.3%   says 55.8%   +0.1% a pick
    the unders                              509-380   57.3%                +4.6%
    the overs                               342-335   50.5%                -5.7%
    an over, a spread of 5+ either way      187-210   47.1%   47.0% then 47.3% by half
    an over, a close game                   155-125   55.4%   53.9% then 57.1%
    an under, a spread of 5+ either way     285-194   59.5%   59.0% then 60.3%
    an over, his minutes swing              22-52     29.7%   11-26 in each half
    an over, his minutes steady            305-257    54.3%
    an under, his minutes down              83-49     62.9%   61.1% then 63.5%
    the sheet says 58% or more             212-131    61.8%   60.3% then 63.8%
    a plus-money side the sheet takes       83-58     58.9%   59.0% then 58.5%

The spread is the game's, read from his club's side: five or more
either way is a game the book expects to be decided early, and the
starters' minutes go with it. The existing red chip is the favourite's
over (124-138 here); the dog's over is as poor (63-72). A man's minutes
swing when the spread (sd) of the minutes of his last ten games played
is six or more: a man moving between the bench and the five, or back
from an absence, whose last five flatter the over.

The sheet's chance is honest all the way up. On every pick with a side,
edge or none: picks it gives 50 to 55% land 50.8%, 55 to 58% land
55.0%, 58 to 62% land 58.4%, 62 to 66% land 65.6%, 66 to 72% land 68.1%.
Across every prop the books posted the under won 53.9% (5,400 of
10,014), fifty or more on each of the fourteen nights.

So the night's six cards were the season in small: the legs that landed
were unders and an over in a close game; the four that missed were
overs, three of them on men whose minutes had just jumped. On the
last-five rule's own legs (91 on these nights, 57-34) no split is large
enough to read.

### The rule

A leg, by best chance, is a pick with an edge on its card and at the
app's own line and price which the sheet gives 58% or more at that line
(`PROPS_T3C.chance`); an over in a game with a spread of five or more
is left out (`lop`), and an over on a man whose minutes swing (`swing`,
`propMinSwing`). The last five, the last ten and the levers are not
asked. A ticket is the two or three legs likeliest to land together at
one app, each on its own game, so its price is the plain product of the
legs'; then the most expected value. A man sits in one ticket a date,
six tickets at most. With a leg a game the likeliest ticket never needs
a game's second leg, so the search keeps each game's likeliest leg and
is exact.

Under the BETs the choice gains "tickets, best chance" beside "either
side", "overs", "unders" and "the LEANs one by one"; two legs or three
as before. The card is the tickets' card: the same pips, the same tabs
for the same legs at another app (each leg must pass the best-chance
test there, and an app where one does not says why), Take, Copy.

### Replayed

Lab `props_chance.py`, the same fourteen nights, each leg at each app's
own line and price, six tickets a night at most:

    two legs, by best chance      31 of 71   43.7%   the sheet said 41.3%, the prices asked 37.8%   +11.0 units
        by half                   16 of 38, then 15 of 33
        the first ticket a night   8 of 14;  the first three 21 of 42
    two legs, the last-five rule   8 of 25   32.0%   said 33.8%   +1.6 units
    three legs, by best chance    10 of 55   18.2%   said 25.7%   -12.7 units
    three legs, the last-five rule 2 of 12

The legs in the best-chance pools landed 208-128 one at a time. Asking
no edge of a leg landed more tickets (42 of 84 at two legs, 26 of 78 at
three) at prices that asked as much as the sheet gave them; ranked by
expected value in place of the chance, 30 of 70. The rule keeps the
edge and the chance. Three legs have not paid under it, and the note
above them says so. On the page the lists of 10 and 11 Nov, rebuilt
from the backup, are the replay's own, ticket for ticket and in order
(two of three, then one of six).

### The record

At grading both rules' lists are kept on the rows before any result
lands, two legs and three: the last-five list as before (`listed`, `m`,
`n` on the spec) and the best-chance list by its own rank (`c`), so a
ticket both rules list is kept once and counted on each rule's line.
The record carries "Two-leg tickets by best chance, as listed, to test"
and the three-leg tile beside the last-five tiles, and the card's line
names both. A ticket taken from the best-chance list keeps the rule
that built it (`m: "t3c"`).

Checked: the harness lists the two- and three-leg tickets on a date
where nobody passes the last-five test, with an over on the dog's man
in a lopsided game, an over on swinging minutes, a pick under 58% and
one with no edge all left out and an under in each of those places a
leg; takes one and unmarks it; reads the same two at another app and
the reason at a third; grades the night and reads the kept lists, the
cards and the tiles. The block was run against six copies broken on
purpose (no floor, the lopsided over let in, on the favourite's side
only, the swinging over let in, ranked by value, the list not kept);
two were not caught at first, which is why the scenario has a leg left
alone on its game and puts the lopsided over on the dog.

## A call on every game, 12 Nov 2026

The user, with the 12 Nov backup: "For the gamelines im not sure the
Kalshi is helping or hurting. I noticed the model wont give 'green bet'
and thats not cool. I know the model is not going to be 100% perfect
but it still need to be able to provide a bet on something because an
outcome is going to happen. game goes over or it goes under, team A
covers the spread or Team B covers the + points, or upset likely to
happen and take this team. Something bro"

### Why there was no green

A game line goes green on the card when the sheet's chance beats the
price. The NBA sheet reads the book's own number for the total and the
spread, so its chance sits at the price and nothing clears it; what
went green this season were the two rules built on top, and both have
lost here: the agreement rule 3-10 (-7.3 units; 157-108 over the two
seasons it was measured on) and the sheet's own calls 12-21 (-8.1
units). A night with neither left the board with no call at all.

### Kalshi

It moves no pick: the crowd's price is shown on the card, on the board
chips and beside the simulation, and one watch reads it (the sharp side
against the crowd). So it has neither helped nor hurt a pick. What it
has been worth as a number and as a price, on the 63 graded games that
carry it (4 to 11 Nov), read against the books in the same odds run
(lab `kalshi_check2.py`; the crowd's quote on a row is from the newest
run, so it is not read against the price the row was logged with):

    Brier, the crowd's chance of the home win           0.1609
    Brier, the middle of the books' no-vig chances      0.1619
    the crowd against the books' middle                 0.85 points apart on average; 2 or more on 2 games
    a point or more apart (25 games)                    the crowd further on the favourite all 25; they won 22
    the favourite won                                   49 of 63
    the favourite, Kalshi after the fee against the
    best of the four apps' prices                       cheaper on 20 (by 0.6 points), dearer on 36 (by 1.0), level on 7
    the watch, the sharp side against the crowd         2-5

As a number it is the books' number: the same to within a point on
nearly every game and no better on the score. Where it differs it sits
a little higher on the heavy favourite (the books' two prices carry
more of the margin on the dog), and favourites have won 49 of 63, which
is all that the crowd's side winning 22 of 25 says. As a price it is a
fifth app: the best of the five on about one favourite in three. A
first reading against the price the row was logged with had it cheaper
on 41 of 63 and better on the score by 0.004; that compared a later
quote with an earlier price and is withdrawn.

It stays shown. The chip on a call card for the likelier winner reads
the crowd's price against the price on that card, the best of the four
apps', so "better on Kalshi" there means better than the best app.

### What a forced pick costs

Measured on his 2024-25 lines file (1,231 games read, every book at
one moment, the opener and the last snapshot before tip) and on this
season's 170 graded rows (the first odds run on the row and the
newest), lab `board_value.py`, `sharp_value.py`, `sharp_now2.py`,
`sharp_dir.py`. No model in any of it: what the board alone gives.

    the best number at the four apps on every game           pays the book's margin:
        the total -2.6% a bet at the last snapshot and -4.9% at the opener, the spread -5.9% and
        -4.0%, the favourite's moneyline -5.3% and -6.2%
    a total at one of the four apps a point or more off
    the middle of every book's number, the app's side        105-84   55.6%   +5.0% a bet   (the last snapshot)
        the same at the opener                                78-70
        this season's rows, the first run and the newest      41-35, 18-16
    the same on spreads                                       600-615 on every game; a point or more off 10-8 and 11-9
                                                              last season, 19-20 and 8-14 here: nothing
    the favourite at the best of the four apps' prices
        80% or more by the books' middle                      231-31   -0.3% a bet
        70 to 80%                                             216-81   -5.8%
        60 to 70%                                             230-134  -6.0%
        50 to 60%                                             162-146  -8.2%
    the dog at the best of the four prices                    -1.7% a bet at the last snapshot, +4.0% at the opener,
                                                              -24.2% here (favourites 119-51): nothing steady
    the sharp book's total against the apps' middle,
    as a guide to the side                                    227-234 last season, 46-41 here: nothing
    the sharp book's price shade on an NBA total              30-27 and 34-51 last season, 8-22 here

Two things on the board carry something: a total left a point or more
off the market at one of his apps (better than even at the last
snapshot, even at the opener and even on this season's rows), and a
heavy favourite at the best of four prices close to tip, which was
about a fair price (-0.3% a bet; -3.7% at the opener) and no more.
Everything else is the book's margin, and a pick on every game pays
it. The sharp book's shade is a hockey measure; on NBA totals it has
pointed the wrong way, and its chip came off the NBA card the same day
(the next section).

### The call

`nba.engine.js`, `nbaCallKinds`: every game carries the kinds that
speak to it, in this order, and the board gives it the first one.

    BET     the agreement rule            the simulation and the crew on a side of the total, the sheet not against it
    BET     the sheet's own call          a market the sheet prices below its chance, or one a verdict sits on (the most edge)
    VALUE   the best number on the board  a total at Fanatics, DraftKings, FanDuel or BetMGM a point or more off the
                                          middle of every book's total (four books or more), the side the number favours,
                                          at that app's line and price; of two as far off, the cheaper
    LEAN    the likelier winner           the side the middle of the books' no-vig moneylines makes the favourite
                                          (four books or more, else the carded book's), at the best of the four apps'
                                          prices, with what that price needs and what it costs or pays a bet

A BET kind that has lost money here over ten or more graded calls is
cold (`NBA_CALL_COLD`): it is left out of the order, named under the
card ("Also on this game: ... cold, and left out of the order until its
record turns") and still counted on its own line of the record, so it
comes back by itself when its record is above water. On the rows to 11
Nov both BET kinds are cold. The number and the winner are never cold:
the first is arithmetic on the board and the second is the fallback.

A card shows the kind, the pick with its result once the game is
final, the numbers behind it (the voices, or the sheet's chance and
what the price needs, or the app, the price and the middle, or the
chance by the books' middle, the best price, what it needs and what it
costs a bet, with the crowd's chip), the matchup, what the kind did
when it was measured and its record here. The section sits above the
parlay four and opens the game on a click.

Take marks the call. The rule's and the sheet's go through their own
buttons. The number and the winner are kept on the row beside the
simulation's calls (`row.simTakes`, view `call`) with what the card
showed at the mark: the app, the line, the price and the chance by the
books' middle ("Total UNDER 227 at FanDuel", "Jazz ML at DraftKings"),
so a later odds run that moves the best price to another app moves the
card and not the bet, and the number is graded at the app's line, not
the row's. They list under Taking tonight as calls on the game, ride to
the phone's sheet under that name, are counted apart from the
simulation's in the night's line, and once graded sit on their own
tile of What you took ("Calls on the game taken") and in the list of
every pick as game calls.

### The record

`nbaCallsRecord` replays every kind on every graded game it speaks to,
from the row's last odds run before tip (the odds run skips a game that
has started), each call graded on its own line and side at its own
price, and then the call as the board gives it, one a game. On the NBA
record under the simulation's table. On the 170 graded rows of the 12
Nov backup:

    BET · the agreement rule                    3-10     -7.3u   cold here
    BET · the sheet's own call                  12-21    -8.1u   cold here
    VALUE · the best number on the board        34-30-1  +0.0u
    LEAN · the likelier winner, 80% or more     23-0     +3.2u
    LEAN · the likelier winner, 70 to 80%       36-8     +2.4u
    LEAN · the likelier winner, 60 to 70%       32-18    -1.6u
    LEAN · the likelier winner, near a coin     27-26    -5.7u
    The call as given, one a game               107-62-1 63.3%   +0.1u

Shown, not scored: no chance, band or pick on the sheet moves, and
slate.py is untouched.

Checked: the harness builds five games on a date (a sheet call on a
short dog; a total a point and a half off the middle at FanDuel; a
heavy favourite priced at five books, the sharp book alone two points
off the middle of its total, the crowd's price dearer than the best app
and cheaper than the row's own; a favourite read from the carded book
alone; a game the agreement rule fires on), reads each card, takes the
number and the winner and reads the marks, the Taking cards and the
night's line, grades the night and reads each call graded on its own
line with the record's table, the tile and the list; then ten short
dogs lose, the sheet's own call goes cold, and a new short dog is given
the likelier winner with the cold call named under it, until the ten
are wiped and it is the sheet's call again; and a later odds run moves
the favourite's best price to another app, the card following it and
the mark not. Five checks, run against fifteen copies broken on purpose
(the gap at two points, the worst of the four prices, no cold rule,
graded at the row's line, the rule left out, the number read at any
book, cold without the ten, the mark at the row's price, the chip
against the row's price, the mark at the row's line, a call counted as
the simulation's, the app left off the pick, the night's line, the
Taking card's words, no Take on the number): two of the first seven
were not caught at first, which is why the scenario has the sharp book
alone off the middle and a rule that has lost once and is still given.

## Three loose ends closed, 12 Nov 2026

The report on the calls ended with three things found and not
changed, and the user answered: "Take care of these bro".

### The sharp book's shade comes off the NBA card

Pinnacle's shade is the side the sharp book prices shorter, by three
points of implied chance or more. It was measured on hockey (13 Oct
2026: 372-289-32 on 693 closes), where the sharp book moves its price
before its number, and the chip, the line in tonight's signals and the
sentence in the why were drawn for every sport. On an NBA total the
book moves the number, so the shade is rare and says nothing (lab
`shade_nba.py`, his 2024-25 lines file and this season's rows):

    2024-25, the last snapshot, 3+ points     29-27   at Pinnacle's own number and price   (56 of 1,219 closes)
        at the best of the four apps there    23-17
    2024-25, the opener                       15-26
    this season, the first odds run           8-22    the over 3-10, the under 5-12
    this season, the newest odds run          8-16-1
    2+ points                                 113-111, 54-61, 25-32, 16-21-1
    the page's own record line                8-22

`sharpShadeShown` returns nothing on basketball and the three places
read it; the other sports keep the shade as it was. The record keeps
counting it on the NBA total tile's own line, marked "off the card
here: a hockey measure", so the line says if it ever turns. The sharp
book's line and prices stay on the card: they are the number, not a
call.

### The pick at even money or better, a list of its own

The sheet's blend is four parts book to one part model, so it only
sides against the book's favourite when its own model sits far from
the book (the model alone near 70%, the book at 45%). Replayed under
the blend as it stands on the fourteen nights that keep the logs, 28
Oct to 11 Nov, 1,566 picks with an edge (lab `plus_money.py`,
`plus_money2.py`, `plus_money3.py`, `plus_final.py`, `plus_carded.py`):

    the pick at +100 or longer            83-58    58.9%   says 51.5%   the prices ask 49.2%   +27.5 units
        by half                           59-41, then 24-17
        the unders, the overs             49-34, 34-24
        at +100 itself, longer            45-33, 38-25
        one a man a night                 68-55    +14.9 units
        by night                          eleven of fourteen up, two down, one level
        the nights drawn again 5,000 times   above zero in 99.6%; a bet returns +8.4% to +30.8% in the middle 90%
        walk-forward                      75-53, each night's picks taken only once the nights before were above water
    every other pick with an edge         768-657  53.9%   -25.2 units
        the over at -110 to -101          87-127   40.7%   (the under there 111-92)

It is the sheet's choice and not the price: every plus-money side on
the board went 1,222-1,637 (42.7%) for -7.1% a bet, the ones the sheet
sided against 1,184-1,612. And it is not one side: both land near 59%.
What the picks share is the model's distance from the book (74% alone
against the book's 45% on the strictly plus-money ones).

As the page carded them the picture is narrower, which is why this is
a test and not a rule. From 5 Nov, the blend as it stands, 24-17
(unders 14-8, overs 10-9). To 4 Nov, under the older blends that gave
the model more say and sided with the dog far more readily (281 such
picks in fifteen nights against six a night now), 147-134 with the
unders 101-73 and the overs 46-61. The replay says the current blend's
choices are better than those; a hundred and forty-one picks cannot
say how much.

On the page (`props.engine.js`, `propIsPlus`, `PROPS_PLUS`):

- under the BETs, a choice "even money or better" beside the tickets
  and the LEANs: the BETs as always, then every other pick with an
  edge at +100 or longer, the most edge first, under a line that says
  what was measured; a date with none says so;
- a chip on each such pick, on its card and its panel, "Pays even
  money or better", coloured by its own record like the other tells:
  the BET and LEAN picks at +100 or longer graded since the blend
  changed (`PROPS_BLEND_FROM`), one pool for both sides with each
  side's count in its words, grey under fifty graded picks. A red
  chip here keeps no leg out of a last-five ticket: it is a test of
  its own;
- a tile on the props record, "The pick at even money or better, to
  test", from the same pool, by side, and a part on the short line.

Shown, not scored: no chance, band or ticket moves.

The same replay answered the user's question of the evening, Duncan
Robinson OVER 1.5 assists at -190 with ten of his last ten over and
his club favoured by 10.5 (lab `fav_over.py`, `fav_over2.py`). The
over that has landed in every one of a man's last five landed 105-83
where the book said 52.3%, about what its price asks; the hit rate of
his last ten shows no relation to landing (the overs that hit 70 to
89% of them landed 48.0%). The heavy over, one the book gives 60% or
more, went 25-26 on a man favoured by five or more where the price
said 63.1% (6-8 favoured by ten or more), 27-24 on a dog by five or
more, and 59-36 in a close game, on the price. The red chip and the
best-chance rule's bar on an over in a lopsided game stay as they
are.

### A marks file: three bets of 11 Nov put back as they were marked

The grading of 11 Nov found three of his bets recorded wrong, because
a mark made that night was a flag and a later props run had moved the
cards (the section "A mark keeps the bet"). From v158 a mark keeps the
bet, and a night already graded was left as recorded. The sheet his
phone had saved at 19:35 UTC that evening kept each bet as it was made,
with the detail panels of every leg, so the night can be put right
exactly.

`applyMarks` reads a file of format `callsheet3.marks` through the
same box as a slate or a props file: `props: [{key, name, took}]` and
`pairs: [{ks, names, app, kind, f, chance, at}]`, the shapes a mark
made today writes (`took`, `pairsAt`). It corrects a mark that is on
the page and makes none: a prop not marked Taking, or a pair whose two
legs do not name each other, is left alone; a key the page does not
hold is passed over; an entry it cannot read is refused; what the page
had kept of a pair gives way to the file's ticket, so loading the file
twice changes nothing. It opens the props at the file's date and says
what it did.

`nba-marks-2026-11-11.json`, made from his backup's keys and the
phone's saved panels (lab `make_marks.py`, `phone_panels.py`):

    Caleb Wilson UNDER 6.5 rebounds, -155, 62.2%, LEAN, BetMGM      five rebounds: a WIN     (read OVER 5.5, a loss)
    Jakob Poeltl UNDER 8.5 rebounds, -140, 63.7%, BET, BetMGM       nine: a loss either way  (read UNDER 7.5 at -110)
    De'Aaron Fox OVER 0.5 threes + UNDER 6.5 assists, BetMGM,
        -210 and -200, +121, 50.8%                                  nine assists: a LOSS     (read with the over at 5.5, a win)
    Al Horford UNDER 1.5 threes + Marcus Smart OVER 0.5 threes,
        DraftKings, -224 and -232, +107, 48.9%                      none and two: a WIN      (read with both legs turned, a loss)
    Ajay Mitchell UNDER 1.5 + Shai Gilgeous-Alexander UNDER 2.5
        threes, BetMGM, -220 and -200, +118, 44.5%                  Mitchell did not play: no result, as before

Loaded on a copy of his 12 Nov backup (lab `marks_probe.js`): the
night reads 2-14 for -12.3 units where it read 1-15 for -13.3, the
props he took 79-66 where 78-67, the pairs 15-10 for +11.00 where
+11.58, and a second load changes nothing.

Checked: nine harness checks in three blocks. The shade: a basketball
game whose sharp book prices the over 6.8 points shorter carries the
sharp line's chip and no shade chip, signal or sentence; the same
prices on a baseball game carry all three; a graded NBA game counts
on the record's line with its note. The even-money list: two BETs,
one at plus money, an under at +105, an over at +100, a lean at -110
and a plus-money side with no edge; the list, the divider, the chip
grey and then green after a night of 52 such picks, a night under the
older blend left out of the pool, the tile, a date with none. The
marks file: a flagged prop and a keyed pair read at the moved rows,
then as marked after the file, with an unmarked prop, an unmarked
pair, a key not held and two unreadable entries left as the message
says, and a second load. Run against twenty-nine copies broken on
purpose (seven, twelve and ten); one was not caught at first, a
plus-money side with no edge given the chip, which is why the check
opens three panels.

## The night of 12 Nov, and minutes on the way back, 13 Nov 2026

The 13 Nov backup, saved 15:21 UTC with the night graded (four games,
394 props) and the marks file of 11 Nov loaded (five bets put back;
that night reads 2-14).

### The night

His fifteen bets went 6-9 for -5.49 units: the four moneylines 4-0
(+1.38), seven props 1-6, four same-game pairs 1-3. Every one reads on
the page as the sheet his phone saved at 22:51 UTC had it, the first
full night of "a mark keeps the bet": ten of the eleven props and
pairs had their cards moved by a later run and each is graded as it
was marked (Duncan Robinson OVER 1.5 assists at -190, one assist in 41
minutes of an overtime game, a loss, where the row now reads UNDER 2.5
and a win).

Four of the seven props were BETs of the day's first props run that
the second run took down to no edge or a bare lean (Coby White's
points projected 8.85, then 12.78; Cade Cunningham's points, rebounds
and assists 31.56, then 36.23): the shape of a run made without last
season's ledger, which the day's later run had. They went 0-4, and the
Taking cards had said the card had moved to no edge.

The sheet's own night: no BET at the last run; the LEAN band 35-18 for
+11.4 units by cards and 12-11 one a man (five men 22-0 across their
markets), the overs 30-12 and the unders 5-6. A call on every game
4-0, two of them totals a point off the market by the last odds run
(the call as given 111-62-1, +2.9 units). The best-chance tickets as
kept 1-1 at two legs (+0.32) and 0-1 at three; the last-five tickets
0-2 and 0-1; the pick at even money or better 2-1 (26-18 from 5 Nov).

### Minutes on the way back

Seven BETs on 13 Nov sat on two men, five of them unders on Ivica
Zubac, projected 16.9 points, rebounds and assists against the books'
25.5. The run reads a man's minutes off the mean of his last five
games, and his were 7, 19, 19, 28, 31: 20.8 a game, 22.3 with a
team-mate out, where he had just played 28 and 31. On 11 Nov the same
read (21.2 minutes projected, 31 played) lost six unders on him.

Measured on the fourteen nights that keep the logs, 29 Oct to 12 Nov,
one row a man a night with five games behind him (1,208 men-nights;
lab `ramp.py`). The profile: a short game in his last five (under half
the median of the five) and his last two games 3 minutes or more a
game above the five.

    what he played less what the sheet projected
        every man                                    -1.02 minutes   (1,208)
        his last two 6+ above his five               +1.57           (23; starters +3.61 on 16)
        his last two 3+ below his five               -2.1            (152)
        the profile                                  +4.84           (17; se 1.15; 4+ over on ten, never 4+ under)
    every prop on a man of the profile               the over landed 57.9% where the book said 48.7%   (107 props)
    the sheet's under on him, BET or LEAN            14-32   30.4%   says 57.8%   -21.3 units   (the BET band 1-4)
        by man and night                             four up, nine down of thirteen
    the sheet's over on him                          none carded

A rise alone is not the signal: the sheet's unders on every man whose
last two ran 3 or more above his five went 160-148, and its BET-band
unders among them 25-14. It is the short game inside the five that
pulls the mean under his real minutes. The other direction is worth a
look of its own: where his last two ran 3 or more below his five the
over landed 41.4% against the book's 49.7% (1,042 props) and the
sheet's unders went 118-76.

On the page (`props.engine.js`, `propRamp`, `propRampUnder`,
`PROPS_RAMP`), shown, not scored:

- the sheet's under on such a man carries a caution in red on its
  card and its panel, with his five, what they average and what his
  last two ran;
- the BETs' note above the cards says how many of the date's BETs are
  such unders and on whom;
- such an under makes no leg of a ticket, by the best-chance rule or
  the last-five rule (on 13 Nov both best-chance two-leg tickets
  carried one: Zubac's rebounds and Jarrett Allen's rebounds and
  assists);
- the record has a tile, "The under on a man whose minutes are on the
  way back", counted from the nights whose logs the page holds (0-8 on
  the 13 Nov backup: Zubac's six and Poeltl's two of 11 Nov), and a row
  keeps the mark (`rmp`) when its log is trimmed.

The chance on the card is slate.py's and is not changed: the cure is
in the run's minutes (the median of the five, or the five without the
short game), which wants its own measurement on the minutes of every
man before it is scored.

Checked: three harness checks on a date of nine men (his two unders,
an over on a man with the same five, an under on steady minutes, one
whose short game is his last, one whose minutes rose with no short
game, one with four games, one short against the median and not the
mean): the cards, the panel and the BETs' note; the tickets by both
rules; the record's tile, and the mark kept through a trim by seven
later dates. Run against fourteen copies broken on purpose; one was
not caught at first, the short game read against the mean, which is
why the ninth man is there.

## The minutes after a short game, measured on four seasons, 13 Nov 2026

The page's caution said the read was low and left the chance alone,
"the cure is in the run's minutes". The user, the same evening: "Do
it".

### What was measured on

The props run projects a man's minutes as the mean of his last five
games played this season. Every game a man played with five behind him
that season, in four seasons of box scores: his own 2024-25 ledger
(1,234 games) and 2023-24, 2025-26 and 2026-27 to 12 Nov built here
with the ledger run from ESPN's open pages (1,232, 1,235 and 174
games; no odds call, nothing spent). 72,645 such games, 57,141 of them
by a rotation man (the median of his five 15 minutes or more). For each
one, what he played against what each way of reading the five would
have said (lab `minutes_rule.py` to `minutes_rule6.py`, `minrules.py`).
A short game is one under half the median of the five. Everything
below is read from history alone: nothing about that night's lineup.

    where the five stand                              games    he played less the mean of five   the mean miss
    every rotation game                              57,141    -0.29                             4.89
    a short game, one of the first three, his last
    two not short                                     3,889    +2.21                             6.29
        a starter in all five                           693    +4.39  (3.49, 4.94, 4.60 by season)  6.32
        his last two 3+ above the five (the caution)  2,448    +3.01  (2.58, 3.32, 3.01, 4.42)   6.53
    a short game his second last                      1,198    +0.32                             6.02
        a starter in all five                           247    +2.18                             5.00
    a short game his last                             1,668    -2.88                             7.21
    no short game, his last two 3+ above the five     7,248    +0.68                             4.99
    no short game, his last two 3+ below              6,985    -1.53                             5.11

The caution's profile is real on four seasons: three minutes low, a
starter four and a half. And a short game that was his LAST points the
other way: he plays less.

### The rule

How much of an old short game to keep was fitted cell by cell (read =
the other four + k × (the five - the other four); k 1 is as it was, 0
leaves it out):

    a starter in all five                     k 0.04    left out: +4.39 -> -0.15, the miss 6.32 -> 4.55
        whatever his last two did             +0.02, -0.86, +0.81 (3+ above, 0 to 3 above, below the five)
        the short game the oldest, second,
        third of the five                     +0.77, -0.33, -0.87 left out
        two short games among the first three +9.95 -> -0.42 (37 games)
    a starter in all five, the short game
    his second last, the last a full game     half way: +2.18 -> +0.33, the miss 5.00 -> 4.63 (left out: -1.99)
    another man, his last two 3+ above        k 0.38 to 0.49    half a game: +2.56 -> +0.87, the miss 6.50 -> 6.14
                                              (2.36, 2.74, 2.47 -> 0.69, 1.03, 0.76 by season; left out: 1.5 over)
    another man, his last two under 3 above   k 0.65 to 1.4     as it was: +0.9 and -0.9; left out it reads 2.0 and 3.7 over

A starter's short game is an accident (hurt, thrown out, a blowout sat
out) and says nothing of tonight. Another man's is partly his role, and
only counts for less when he has plainly climbed since.

`slate.py`, `props_short_game` (`PROPS_SHORT_SHARE` 0.5,
`PROPS_SHORT_RISE` 3.0, `PROPS_SHORT_HALF` 0.5), read by
`props_minutes`:

- a man who started all five: a short game among the first three, with
  neither of his last two short, is left out (`out`); a short game his
  second last with a full game after it counts as half a game (`half2`);
- any other man: a short game among the first three counts as half a
  game when his last two run 3 or more above the mean of the five
  (`half`);
- a short game that was his last, and anything under five games: as it
  was.

On the four seasons the rule moves 2,915 of the 57,141 rotation games
(one in twenty): the read 2.96 under what he played before and 0.58
under after, the miss on them down 0.70 (0.60 to 0.79 with the men
drawn again 1,000 times), closer on 1,813 and further on 1,099; on a
deep-bench man (the median under 15) it helps too (+3.72 -> +2.55).
Over every rotation game the miss falls 0.036, below zero in every one
of 1,000 draws of the men.

The why line names the game, how it was read and what the five say
untouched ("30.0 minutes projected: his last 5 games without the
7-minute one (season 25.4), 5 of them starts; the mean of the five says
25.4; he started all five and a game cut short three or more back says
nothing of tonight: ... (693 games), scored"), and the row carries
`mshort` {how, min, mean, read}. The minutes lever on the card ("his
last 5 against the season") reads the new minutes.

### Measured the same day and left off

- **His games in tonight's role.** The largest miss in the minutes is a
  changed role: a man who starts tonight having started none of his
  last five played 9.4 minutes more than the mean of five said (1,697
  games), one of five 6.5 more, a starter sent to the bench 2 to 6.5
  fewer. Read from his last five games in the role he had THAT NIGHT
  the miss on the 15,913 changed-role games fell from 6.37 to 5.12, on
  every season. But that reads who really started. The run knows
  RotoWire's expected five, and on the sixteen graded nights it was
  right on 93.9% of 1,536 men-nights and on 211 of the 272 where the
  flag's role was not the role of all his last five (77.6%; of the 93
  wrong, 50 started who were not in the expected five and 42 were in it
  and did not; no spelling fault among them). Read from the flag the
  miss on those 272 was no better (4.90, then 5.00), even where the
  flag and his last game agreed (4.48 -> 5.04 for a starter). A read to
  come back to with confirmed lineups, not with expected ones.
- **The first game back.** From three or more of his club's games
  missed he played 0.86 of the read (1,079 games; 0.90 after three
  missed down to 0.76 after thirteen; 0.85, 0.89 and 0.84 by season).
  Five such men-nights in 1,536 on the props: too few to score.
- **A short last game off the bench.** He played 3.4 fewer than the
  five say (1,254 games). Seven men-nights with a short last game of
  any kind on the props.
- **The last ten games weighted to the recent** (0.75 a game back):
  the miss over every game 4.89 -> 4.76, the best single read. It would
  move every projection and the levers measured on top of the mean of
  five, and has not been through the props: on record.
- **The median of the five** misses more than the mean (4.99).

### The graded nights replayed

Sixteen nights, 27 Oct to 12 Nov, 10,629 graded rows from eleven
backups joined to the box scores as they stood before each night (the
ledger agreed with what the run had read on all but 15 of 1,747
men-nights). Each row re-read with slate.py's own functions under
today's blend, the projection scaled by the new minutes over the old
(lab `minutes_replay_build.py`, `minutes_replay_picks.py`); replayed
as it is, the chance matched the cards of 5 to 12 Nov to 0.0001.

    the rule moves                        28 men-nights, 189 rows, on 10 nights
    the sheet's minutes on them           he played 3.73 more as it was, 1.25 more under the rule; the miss 5.76 -> 4.85
    the over on the moved rows            landed 51.9%; the sheet said 46.9%, the rule 48.4%, the book 49.1%
    picks on the moved rows, as it was    19-29 (unders 19-28), the BET band 5-6
        under the rule                    12-25 (unders 9-16, overs 3-9), the BET band 4-2
    every pick with an edge               887-733 +13.9u as it was, 880-729 +12.1u under the rule
    the BET band                          99-76 +6.3u as it was, 98-72 +9.7u under the rule

Twenty-eight men-nights cannot say whether the picks are better (22
lean unders drop out that had gone 10-12; 11 slim lean overs come in
and went 3-8, seven of them on one man); they say the minutes are
closer and the chance nearer the book's and the result. The four
seasons carry the decision.

On 13 Nov's sheet, re-read the same way without a run: four men move
(Ivica Zubac 20.8 -> 24.2, Jarrett Allen 22.0 -> 25.8, Jalen Smith
24.4 -> 28.8, Isaiah Collier 13.6 -> 14.8). Zubac's five BET unders
become leans (55.0% to 60.9%), Allen's lean under loses its edge, Smith
gains three leans on the over by under a point.

### The page

`props.engine.js`: a row with `mshort` is no longer a row the caution
warns of (`propRamp` returns nothing), so the red line, the BETs'
note's sentence and the ticket guard stand down on it and stay on a row
of the same shape from the old run. `propShortLine` says on the card
and the panel what was set aside, how, the read and what the five say
untouched. The record has a tile, "A short game set aside in his
minutes (scored from 13 Nov 2026)", the BET and LEAN picks on such
rows by side, and a part on the short line; the mark stays on a
trimmed row.

Checked: slate.py's selftest 288 (three new: the shapes, the rise at
2.98 and 3.04 minutes, the why line and the mark through
`props_project`); `props_minutes` against the lab's rule on 83,158
reads over the four seasons, none different (lab `xcheck_minutes.py`).
The page: three harness checks on a date of seven men (left out, half a
game, half a game two back, two games left out, the same five from the
old run, a man with no pick, a plain man): the cards, the panels and
the note; the best-chance ticket and the rows; the two tiles and the
marks through a trim by seven later dates. Run against sixteen copies
broken on purpose, all caught.

## The levers' audit, and the levers corrected, 13 Nov 2026

The user, the same evening as the short game: "Please make sure the
levers are accurate", and of the role read left off that afternoon,
"Do it, explore the confirmed lineups".

### What was measured on

Every game a rotation man played with five behind him that season, in
2024-25, 2025-26 and 2026-27 to 12 Nov, each with the season before it
as the run's prior: 39,523 games (the minutes also on 2023-24). For
each, what the run would have had before the tip, through slate.py's
own functions: his rate with the prior, his minutes read, who of his
club's regulars sat and how new that was, the pace and defence factors,
the expected margin; and what he then did (lab `audit_build.py`,
`audit_levers.py`, `audit_levers2.py`, `audit_dvp.py`,
`dvp_byseason.py`, `audit_outrate.py`, `audit_drift.py`,
`shape_checks.py`, `shape_minutes.py`, `fit_final.py`, `fit_role.py`,
`role_few.py`). Then the corrected code end to end: both versions of
`props_project` itself run over the same 39,523 games (lab
`audit_e2e.py`), and over the sixteen graded nights of props with the
row's own line, prices and report (lab `replay_levers.py`).

Who is out is read off who played, not off the box scores' inactive
lists (they name about a third of the regulars who sat). A regular is a
man on 24 minutes a game whose last game was for the club and inside
its last fifteen.

### Lever by lever

    lever                        as the run stood                 what the seasons say                           now
    regulars out, the minutes    +1.42 a 30 mpg out TONIGHT       the level carries +0.17 once the CHANGE from   the change, by his starts
                                                                  his five is read; newly out +1.9 a 30 mpg     and his own minutes
                                                                  (t 43), back -1.8 (t -39)
    regulars out, the rate       +0.56 points, +0.09 assists      the slope is right, the centre is not: the     the level over the league's
                                 per 36 a 30 mpg, on every man    average man was lifted 0.6 per 36; and the     of the day; points 3.5% of
                                                                  points lift is a share of his own rate         his rate, assists 0.11
    pace                         in full                          0.62 of it beside the defence's table          0.65
    defence v position           (n x this + 20 x last)/(n+20)    right as built: 0.57 to 0.83 of the blend      as it was; a combo by its
                                 at 0.75                          shows early, 1.0 late; no fitted shape beats   parts; no raw young table
                                                                  it on a left-out season
    last season's prior          a quarter of last season's       the weight is right (0.38 to 0.48 fitted,      the prior at this season's
                                 minutes, its level as it was     0.42 run); this season runs 0.92 of last       level (the drift)
                                                                  season's points rates
    the game script              -0.187 a point over 11.8         -0.183 (t -6) on the books' spreads            as it was
    their centre out             +0.30 rebounds per 36            +0.25 (t 4) for a forward or centre            as it was
    one sigma                    K 1.85 points ...                0.95 to 1.00 of the run's sigma for men who    as it was
                                                                  started all five
    the median's shift           0.08 sigma points ...            the median is beaten 50 to 51% (threes 54%)    as it was

**The minutes.** The old lever's slope was measured against a man's
season mean; on top of his last five it counts an absence twice
whenever the man was already out through those five. Left-out-season
miss in minutes: no lever 4.955, the old lever 5.111 (2.3 minutes over
where 30 mpg were out, 2.9 over where regulars were back), one pair of
constants 4.785, by his starts in five 4.752, by his starts and
straight in his own minutes 4.714. The more he already plays the less
he gains when others sit and the more he gives up when they return
(`PROPS_OUT_CHANGE`, minutes a 30 mpg newly out and off a 30 mpg back,
each at a read of 26 minutes and per ten minutes more):

    started all five    +0.99 -1.29    0.84 +1.59      a 36-minute starter gains nothing and gives up 2.43
    some of five        +1.68 -1.63    2.59 +1.21
    none of five        +1.04 -2.37    2.48 +0.65      a 16-minute bench man gains 3.41 and gives up 1.83

A man with one to four games behind him (2,936 games) is helped too:
4.70 to 4.59.

**Who plays.** On the sixteen graded nights: a man listed Out sat 131
times in 135; a regular listed day-to-day or questionable played 48 in
91, the same whether he had played his club's last game or not (0.55
in, 0.45 out); a regular the report did not name played 1,099 in 1,112
when he had played his club's last game, 27 in 31 after missing it, 8
in 12 after missing two or three, none in 3 after four or more
(`PROPS_UNLISTED_PLAYS`: 1.0, 0.9, 0.65, then taken as still out).

**The rate.** By quarter of his own points rate the lift is 3.45, 3.53,
3.65 and 3.28% a 30 mpg: a share, 3.5% (t 18; left-out-season miss
5.8466 against 5.8505 flat and 5.8716 with none). Assists run flat by
quarter, 0.11 per 36 (t 10). Rebounds and threes null. Centred on the
league's level the miss is level across how many are out (+0.07,
-0.07, +0.07, +0.28 per 36).

**Pace.** Alone the pace factor shows at 1.25: a fast opponent is also
a defence that allows more a minute, so the defence's table already
holds part of it. Beside the table 0.62 of it shows on points, 0.61
rebounds, 0.62 assists, 0.64 threes.

**The defence.** The afternoon's note said the lever "leans too hard on
last season's early". That reading came from the graded nights and does
not stand: 7,784 of their 10,715 rows were carded on nights the run had
no last season's ledger (29 Oct to 8 Nov and 11 Nov), where
`props_dvp_blend` passed this season's table RAW (x0.342 on four
games; the push's sigma 9 to 13% of the projection against 4.5% on a
night with the ledger), and none of that showed up in what the men did.
With the ledger in place the blend shows this season as in the others
(0.71 of its points lean in a defence's first twelve games; 0.71 and
0.25 the two seasons before). Corrected: a young table with no last
season behind it is pulled to the league's 1.00 by the same twenty
games. And a combination reads each part off its own table by his own
split of the stat (0.84 to 0.90 of the lean shows, against 0.66 to 0.81
off the points lean alone; the miss a hair lower on all four).

**The prior's level.** The men with both seasons are scoring 0.92 of
what last season's rates make of their minutes (0.98 to 1.04 in the two
seasons before). The early-season bias on points, as it was and with
the prior scaled: -0.23 to -0.19, +0.09 to -0.11, -0.93 to -0.24: the
three seasons agree once it is in (`props_prior_drift`, from 10,000
minutes of such men, held inside 0.85 to 1.15).

### The role, when the five is confirmed

With the real starters, his games in tonight's role read a new role far
better than his last five (11,314 games where the role was not that of
all his last five: the miss 6.26 from his last five, 5.50 with the
corrected lever on who is out, 5.03 from his role games, 4.86 with the
lever fitted to that read). Where the role is the one he has had all
along the two reads are one; and under five games the pull to the flat
number only added a bias (+0.8 to +1.5 minutes on a starter), so the
role read is for a NEW role only. It is used when RotoWire's five is
CONFIRMED: an expected five named the role wrongly on 61 of the 272
role changes of the graded nights, and a wrong role costs ten minutes.
Lineups confirm about half an hour before each tip, so a morning run
reads none; a run made then does (each props run spends credits).

### End to end, three seasons

Both versions of the code over the 39,523 games, who sat known:

                                     as the run stood    corrected    corrected, the real role
    minutes: he played less it       -1.96               -0.12        -0.17
    minutes: the mean miss           5.11                4.74         4.55
    points: bias / rms               -9.1% / 6.69        +1.2% / 6.58   +1.0% / 6.53
    rebounds                         -7.6% / 2.67        -1.1% / 2.61
    assists                          -7.3% / 2.02        +1.8% / 2.01
    threes                           -6.4% / 1.51        -0.4% / 1.51
    points + rebounds + assists      -8.5% / 8.52        +0.7% / 8.18
    he beat the median (points)      42.5%               51.3%
    (rebounds, assists, the combos)  41 to 46%           50 to 51%

Every season and every month the same way (points by season: -8.7 to
+1.8%, -9.4 to +0.7%, -10.3 to -1.5%). The run's projections were 7 to
9% high and its "median" was beaten four times in ten: it called the
over about eight points too often.

### The sixteen graded nights, replayed

10,715 graded rows, each projected again by the code as it stood and as
corrected, both with the ledgers in place (on 12 Nov, a night the run
had them, the replay matched the card within 0.01 on 357 rows of 362).

                                     as carded     as it stood, ledgers in    corrected
    minutes, bias / miss             -0.93 / 4.35  -0.91 / 4.33               +0.01 / 4.21
    the projection, bias / rms       -5.3% / 5.92  -6.3% / 5.76               +1.2% / 5.62
    the model alone on the over      49.4%         50.6%                      45.5%   (it landed 46.4%)
    Brier, the blend (book 0.2479)                 0.2481                     0.2475
    the model's earned share                       0.04                       0.21    (the blend gives it 0.20)
    every pick with an edge                        465-383 (54.8%) -8.6u      523-402 (56.5%) +17.0u
    the leans                                      433-370 -19.9u             493-373 +24.7u
    the BET band                                   32-13 +11.3u               30-29 -7.7u

The corrected blend's chance matched what happened at every level
(said 51.0, 52.9, 54.9, 56.9, 59.6, 65.1; won 50.7, 52.6, 55.9, 57.4,
57.8, 63.9). The BET band is the model's furthest disagreements with
the book: 59 picks on 40 man-nights (22 winning nights to 18) against
45 on 30 (20 to 10), fifty of the 59 in the season's first week. Too
few to tell apart; the record tile below keeps the count from here.

### On record, not built

- **The season's ramp.** Corrected, points run -3.3% in October, level
  November to January, +1.7% February, +3.1% March, +6.7% April; the
  assists drift climbs from 0.93 to above 1.0 through every season. A
  lever on the league's recent level against its season to date, to
  measure before February.
- **The first fortnight.** Where regulars are still named by last
  season's minutes the lever's "back" ran 0.8 minutes heavy (228
  man-nights of the replay; 130 thin-history starters of three
  seasons). To measure before next October.
- **Sigma off the bench.** For men who started none of their five the
  miss runs 0.81 to 0.93 of the run's sigma (threes 1.00): the sigma
  is wide there, the chance read toward 50%. Few of them carry a line.

### The code

`slate.py`: `props_club_dates`, `props_club_night`, `props_out_level`,
`props_out_change`, `props_out_change_minutes`, `props_unlisted_plays`,
`props_maybe_plays`, `props_minutes_role`, `props_prior_drift`,
`props_dvp_lean`; `props_rate(..., drift)`; `props_dvp_blend` (the
young table); every log entry carries its club (`tm`). A row carries
`lv` 2, `chg` {new, back, dmin, lvl, lg, drate36}, `mrole` and `drift`;
the game row the regulars listed short of Out and each club's level.
The part "Regulars out" is "Who is out". With no injury report read,
who is out is not read at all.

The page: the row keeps `lv`, `chg` and `mrole`; `propRoleLine` says on
the card and the panel how the minutes were read by the role; the
record has a tile, "Picks under the levers as corrected (from 13 Nov
2026)", by band and side with the sixteen replayed nights beside it.

Checked: slate.py's selftest 294 (six new: the club's night, the change
and the unlisted man, the corrected projection by its own arithmetic on
four markets, the role read, a combo by its parts, the drift). The
page: three harness checks on a date of six men, run against 23 copies
broken on purpose, all caught; the Example reads through the corrected
levers (Embiid newly out, a regular back, Hart day-to-day) and five of
its checks were re-set by hand; 1,339 checks in all. And the whole
props run as the bat file starts it, the odds calls stubbed out, on the
day's real report, lineups and rosters: 144 made-up props on three
games written, every projected row marked, and the page read the file.
