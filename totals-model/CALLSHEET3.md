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
