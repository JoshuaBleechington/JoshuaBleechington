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
