# The basketball book

The NBA on The Super Model, built the hockey way: the market as the anchor,
every candidate input measured against two seasons of closing lines before it
scores, mechanism inputs buying bands and tagged ones not, and the daily slate
filling the boxes. Started 15 Oct 2026 (the user, 8 Oct: "I want everything you
mentioned"), five days before the season.

## The ledger, 15 Oct 2026

`slate.py nba-ledger --season 2024-25` (Run NBA ledger.bat) writes every
regular-season final of a season with the quarter scores and overtime, each
team's box line (field-goal and free-throw attempts, offensive rebounds,
turnovers, minutes) and the game's pace, every player who dressed with his
minutes, points, plus-minus and the starter flag, every player who sat with the
reason the feed gave, the tip-off time and the referee crew. A past season is
read from ESPN's open site API (the scoreboard a day a call, the summary a
game): the league's own CDN keeps box scores for the running season only and
its stats site will not answer a script (both found on the user's first runs;
the CDN stays first for the running season). 1,231 games a season after the
All-Star tournament games are dropped: 1,230 scheduled plus the Cup final.

## The backtest, 15 Oct 2026

`tools_backtest_nba.py` joins the two ledgers to KillerSports' closes (`date,
team, o:team, points, o:points, line, total, site, rest @ season=YYYY and
site=home and playoffs=0`; 1,225 and 1,224 games joined, every score matching).
Each input was asked the hockey question: when it said over (or home), did the
final land that side of the close? Slope of the close's residual on the input's
lean, its t, both seasons separately, and the record bet at the line.

**The market at the close**: the total's residual +0.62 points (sd 18.0), the
over 1,243-1,195; the spread's residual −0.15 (sd 13.7), the home side 1,237-
1,195 against it. Home margin +1.73. Overtime 4.7%. By month the total ran
+2.3 in October, −1.7 in January, +1.4 in March and +3.2 in April.

| Input, against the close | Games | Slope | By season | Verdict |
| --- | --- | --- | --- | --- |
| Pace × efficiency projection to date, minus the close (the total) | 2,142 | −0.135 (t −2.1) | −0.10 / −0.16 | **faded, tagged**: the market over-moves with the ratings; under 50 games the slope is −0.22 (t −2.6; shrunk by n/(n+20), −0.37), after 50 games null (+0.003). A projection 8+ over the close landed 1.7 under it; 8+ under landed 2.3 over |
| Last ten average total, minus the close | 2,142 | −0.112 (t −1.6) | −0.05 / −0.19 | the wrong way both seasons; not an input |
| Season points per game, minus the league | 2,142 | +0.02 | | null |
| Pace to date, minus the league | 2,142 | +0.20 (t 0.7) | +0.02 / +0.36 | null; the pace goes into the projection, not alone |
| Missing regulars' minutes, both sides (the total) | 2,449 | −0.01 | +0.11 / −0.05 | null as a slope; games with 40+ minutes of regulars out ran +0.87 (t 1.8; +1.45 / +0.49). **Watched**: the close already carries announced absences; the live card measures the late ones |
| Missing regulars' minutes, away minus home (the side) | 2,449 | +0.29 (t 1.2) | +0.14 / +0.42 | weak, same sign both seasons; not scored. Big gaps (60+ minutes) ran +1.2 to the home side on 280 games |
| Pace × efficiency margin projection, minus the spread | 2,142 | −0.01 | +0.06 / −0.09 | **the spread is priced**: nothing from the box score moves a side |
| Rest days, home minus away; time zones; the trip's length | 2,418 | +0.18 / −0.18 / null | signs flip | null on the side and the total |
| Back to back (either, away, home, both); three in four; the second night on the road | 455-1,087 | residuals −1.9 to +0.8, every t under 1.3 | signs flip | **labels only**; the market prices rest |
| The crew's free throws to date (the total) | 2,066 | −1.3 per 10 FTA (t −1.0) | | crews DO predict the night's free throws (slope 0.60, t 7.3) and a little pace (t 2.5); the total does not follow. Not an input |
| The crew's own over/under residual to date | 2,062 | +0.17 (t 1.0) | | null |
| A club's own over/under residual to date (last 10 / 20 / season) | 2,137 | −0.07 / +0.05 / −0.05 | | null within a season. Across the two seasons the clubs' residuals correlate at r +0.40 (20 of 30 the same sign): Nuggets +5.1 / +4.3 and Jazz +3.0 / +5.7 over, Celtics −2.9 / −3.2 and Hornets −2.9 / −3.6 under. **Watched, a label on the card**, not scored |
| "Altitude" (games in Denver and Utah) | 164 | +4.8 (t 3.1) | +4.0 / +5.6 | not altitude: the Nuggets and Jazz ran over on the road too (+5.0, +3.6). The club label above |
| After the trade deadline (the total) | 933 | +1.36 (t 2.3) | +1.17 / +1.56 | **tagged delta +1.0** |
| The last two weeks of the season (the total) | 224 | +2.25 (t 1.8) | +1.40 / +3.10 | **tagged delta +2.0** (April alone +3.2, t 2.4, both seasons) |
| Big home favourites (−10 or more) against the spread | 426 | +0.84 (t 1.3) | +1.28 / +0.42 | watched |
| Closing total 240+ / 220 or less | 226 / 385 | +1.0 / +0.6 | | null |

**The league constants for the engine** (both seasons): points a game 228.8
at the close; the total's residual sd 18.0, flat across closing levels (17.4
under 220, 20.1 at 240+); the margin's residual sd 13.7 (14.6 inside four
points, 13.3 at ten or more); the first half's share of regulation points
0.5036, the same at every total level, the half's residual on half the close
+0.56 with sd 11.9; the quarters 0.2535 / 0.2500 / 0.2548 / 0.2417; pace 101.5
(sd 5.5); home margin +1.73; overtime 4.7%. The spread as a win chance: a
normal margin with sd 12.5 fits the home win rate within two to four points at
every spread (95% observed at −15 or more against 91%; 10% at +10 or more
against 15%: big home dogs win less than the model says), 13.7 overstates the
dog.

## The engine, 15 Oct 2026

`totals/nba.py` and `web/nba.engine.js` (the port, replayed through The Super
Model against the package on every change: 13 basketball cases in
`web/callsheet3-cases.json`, `tests/test_nba.py` for the package). The NBA is
the page's fourth button; the inputs are in `web/callsheet3.nba-fields.html`
and the wiring in `tools_build_callsheet3.py`.

**The total** anchors on the book's two prices through a discretised normal at
sd 18.0 (`nba_fair_total`, the engine's solve with a thirty-point bracket) at
weight 4.0, and moves off it by two tagged deltas and nothing else:

- **Ratings, faded.** The pace × efficiency projection (each offence into the
  defence it faces, less the league's 112.7 per 100, over the two paces' mean)
  minus the anchor, shrunk by n/(n+20) games, times −0.25, under fifty games a
  side; ten games a side to score; shown after fifty. Four league-average
  ratings on the league's own number move nothing.
- **Stage of the season.** +1.0 after the trade deadline, +2.0 from the last
  two weeks, from the date on the row against `SEASON_DATES` (the 2026-27
  calendar, a priori until the league publishes it).

Both tagged, so neither can buy a band; a card carrying only them is held at NO
BET with the note saying so. **Labels**: the Nuggets and the Jazz (watched), a
back to back (rest measured inside the number), the regulars' minutes out
(shown: announced absences are in the close).

**The first half** anchors on its own market at sd 11.9 and takes the full
game's lean at the 0.5036 share. **The spread** is the book's number with its
prices de-vigged through a normal margin at sd 12.5; **the moneyline** reads
off the same margin. Nothing moves either, and both are shown, never picked.
The pick is the likeliest side of the total and the half where the sheet's
inputs move the chance a point or more off the book's own.

**Who is out** is a card on the matchup: each side's injury report from the
slate with every player's status, minutes, points and plus-minus a game, the
regulars' minutes summed, and a tick on a doubtful player that counts him out
(the tick rides in the row). **Context** is the hockey card's shape: each
club's league ranks with the tag that says what the sheet did with the fact.
The slate fills both (below). **The early-season side watch** (below, the
WNBA pattern) is a note on the sides' why list in a club's first thirty games
when the ratings' margin sits four or more points off the market's.

**Four games of 2025-26 through the engine** (`scratchpad/nba/examples.py`,
the 2025-26 calendar, the ratings to date from the ledger, the closes from
KillerSports, the sides at −110): Bucks @ Hornets 12 Nov, ratings faded −1.2,
UNDER 52.7%, won; Nuggets @ Kings 11 Dec, the Nuggets label, UNDER 50.9%,
lost; Cavaliers @ Hornets 20 Feb, after the deadline +1.0, OVER 52.2%, won;
Raptors @ Celtics 5 Apr, the last two weeks +2.0, OVER 54.4% held at NO BET,
lost. The sides read 50.0% at the spread's own number and 58 to 80% on the
moneyline, the book's chances, and went 3-1 and 3-1 as the book said they
would about.

## The slate, 15 Oct 2026

`slate.py nba` (Run NBA slate.bat) and `slate.py nba-grade` (Grade NBA
yesterday.bat), beside the ledger and the odds run (`slate/README.md` has the
order of a game day). The slate reads the day's scoreboard from ESPN's site
API, fills each club's ratings, pace and games from this season's ledger (five
games to fill, nothing from last season: the rosters moved), rest from the
ledger's dates, and writes two JSON boxes the matchup's cards render:

- **Who is out**, from the league's injury page, every listed man keyed by his
  player id (the page carries no id field, only the player-card link; found
  on the user's download of 15 Oct 2026, when every line came back blank).
  His line is his own: this season's after three games, last season's before
  that with his old club named when he has moved. So a traded or signed
  player is never read against the wrong team (the first live run listed
  Jaylen Brown and LeBron James under the 76ers with the Celtics' and the
  Lakers' lines), a rookie shows with his status alone, the page's comment
  and return date ride along, a return date before the game is flagged as
  stale, and the card's sum of regulars' minutes counts only the men marked
  OUT plus the ones you tick.
- **The starting five** (20 Oct 2026, the user: "show the starting lineup
  for that matchup as well, maybe next to the who's out section"): the slate
  reads RotoWire's NBA lineups page, today's or tomorrow's, and writes each
  club's five with the position and the full name, the lineup's status
  (expected or confirmed) and the MAY NOT PLAY men with theirs into the
  row's `nbalineup` box. The Who is out card renders it under the injury
  list, two columns, a badge for the status, and says when RotoWire has not
  posted a side. The parser is checked against the page's shape and ran on
  the day's real page (six clubs, five starters each, the hidden
  out-for-season rows dropped). Shown, not scored: the engine does not read
  the box, and a lineup is a name on the card, not a number on the line.
  The NHL goalie pull of 19 Oct reads the same site; the same today-or-
  tomorrow rule and the same date check apply, except that tomorrow's NBA
  page carries today's date in its subtitle before the lineups post, so
  only today's page is checked against its date.
- **Recent form** (22 Oct 2026, the user: "add in the last 5 games for the
  teams like you do for NHL, with the scores like first half, total and
  spread covered or no, and with a little color"): the slate writes each
  side's last five finals from the ledger into the row's `nbaform` box with
  the half-time score (the first two quarters) and the close the odds run
  last saw for the game from `odds-log.json`: the total, the first-half
  total, and the home spread, which the odds log keeps from the 22nd (the
  side lines `sp`, `pl` and `rl` ride in the log's snapshots now). The
  Recent form card, under Who is out, lists each game with a W or L chip
  and the score, the half with its over or under against the half's close,
  the total with its over or under against the close, and the spread from
  the side's view with covered or not, and sums the five above the table. A
  past game the odds run never saw borrows the close from the sheet's own
  card row when the game is on it, else shows its score alone. Shown, not
  scored: the within-season over/under run measured null (slope −0.05 on
  2,137 games).
- **The crew** (15 Oct 2026, the user: "I think that will be helpful at some
  point"): the slate reads the league's assignments feed by date (the user
  opened the domain and sent the day's file the same evening; the parser is
  checked against that shape and ran live) and writes the three names into
  the Crew box, and a referee table from up to three seasons of ledgers into
  the row (each official's games, free throws and points a game, and the
  league's). The Context card composes the last line from the two, so a
  crew typed by hand from official.nba.com gets the same line; a surname
  alone matches when it is unique. Shown, not scored, for the reason in the
  backtest table above: crews predict the night's free throws (t 7.3), the
  total does not follow them (t −1.0), and a crew's own over/under residual
  to date measured null (+0.17, t 1.0). The ledger keeps the crew on every
  game, so the test re-runs as the record grows.
- **Each referee against the close** (16 Oct 2026, the user: "I like these
  ideas"): the two backtest seasons' over/under record per official ships
  inside the slate (`NBA_REF_OU`, 86 officials over 2,442 joined games,
  `tools_nba_ref_table.py`), and this season's is graded from the odds log
  as the ledger and the odds runs fill, so the crew line reads "Scott
  Foster … over the close 66-41 the last two seasons and 4-2 this season".
  The spread of the past table is wide: Foster 66-41 and Tre Maddox 62-37
  over, Brian Forte 48-69 and Curtis Blair 47-68 under. With 86 officials
  a handful sit two sigma from even by chance, and the within-season
  residual test above says the tilt did not carry as a predictor. So it
  is a watch with a clean out-of-sample test built in: the past table is
  frozen now, this season's record sits beside it, and if the officials
  who tilted over keep tilting over, the crew becomes an input at the
  season's end, scored at what the record says.
- **The referees as a watch, on the record** (22 Oct 2026, the user: "add
  the tile so I can see it build... I want to see what impact the refs
  have on the game, even if small"): a block under the NBA record keeps
  this season's graded totals against the close by the crew's lean in the
  frozen table. An official 1.5 sigma or more over or under across the two
  seasons leans (eight over, 450-286 pooled; seven under, 175-270), a crew
  leans by the sum of its three, and each tile shows the over-under count
  against the close, what the past table says for those crews against what
  this season does, the points over the close a game, and a flat bet on the
  lean's side at −110. Shown, never scored (`nba.engine.js`
  `nbaRefsWatchHtml`, from the rows' Crew box and referee table, the finals
  and the close the grade file attaches). The decision stays the season's
  end; one standard error at twenty games is eleven points.
- **The scoreboard's book**: ESPN carries DraftKings' total, spread and
  moneylines with their openers. They go in the row's notes, the opening
  total fills the Opened box (the engine notes the move, not scored), and a
  move of a point or more is a Context line. The carded lines stay the odds
  run's, one book for the record.
- **Context**, the hockey card's shape: each club's rank in the league on the
  ratings (faded under fifty games, shown after), pace, points, the last
  ten, free-throw rate, a lopsided home or road record, with the stage of
  the season (scored, tagged), the watched clubs, a back to back and the
  regulars out, each line carrying the tag that says what the sheet did
  with the fact.

The grade run writes each final with the half-time score and the close the
odds run last saw. Everything is checked offline in the script's selftest
against canned feeds: sixteen clubs' tables, a traded man's line by id, a
two-game club left blank, a preseason flag, the two watched clubs, and a
morning's finals with the half from the line scores or the summary.

## The WNBA card's spread pattern, tried on the NBA, 15 Oct 2026

The WNBA card scores the ratings' margin at 1.2 against the market's 4.0 and
its spread stands 7-0 informed, 15-1 with the uninformed rows, on the record
(the moneyline 7-0). Twenty-three rows. The same thing on the NBA, the pace x
efficiency margin projection to date against the spread, over the two
ledger seasons:

| The ratings' side of the spread | Record | At −110 |
| --- | --- | --- |
| 2+ points off the spread | 669-716 (48.3%) | −107.8u |
| 3+ points | 521-536 (49.3%) | −62.4u |
| 4+ points | 394-394 (50.0%) | −35.8u |
| 6+ points | 212-196 (52.0%) | −3.3u |
| the WNBA blend (4.0 market, 1.2 ratings), a point of lean | 351-344 (50.5%) | −24.9u |
| the blend, 2+ points | 79-68 (53.7%) | +3.8u |
| the blend, 3+ points | 22-10 (68.8%) | +10.0u |

By the stage of the season, the ratings' side at 4+ points of lean: **10-29
games in, 148-124 (54.4%; slope +0.156 a point, t 1.5)**; 30-59 games
135-143 (slope −0.057); 60+ games 113-125 (slope −0.144). The home side's
residual by the gap's sign: −1.3 when the ratings sat 6+ under the spread,
−1.1 at +3 to +6 over it, nothing in between; the signs do not hold by
season.

**The verdict.** The WNBA's edge is a thin market on twelve clubs, where the
public number lags the ratings; the NBA's spread has the ratings priced
(slope −0.01 on 2,142 games) and the ratings' side loses at every lean over
two seasons. The blend's 22-10 at three points of lean is thirty-two games,
the kind of count the WNBA record is made of, and not a scoring input. The
one thing with a sign both seasons is the first month: a club's first thirty
games, where the ratings' side at four or more points of lean covered 54.4%.
So the engine carries an **early-season side watch**: when the lesser side
has ten to twenty-nine games and the ratings' margin sits four or more
points off the market's, the why list names the ratings' side and the
record; nothing moves, the spread stays the book's own number. The record
section measures it from opening night, and it scores only if a season of
the card says what the backtest's first month said.

**The rosters.** Every team number on the slate is this season's only; last
season's ratings are not a prior, because the summer moved the rosters
(`RATINGS_MIN_GAMES` is the wait, the fade is the read). Players carry their
own lines by id across clubs, so the who-is-out card reads a traded man
against his own minutes, not his new team's.

## The upset watch, and the short dog, 16 Oct 2026

The user: "look for potential upsets too." First against the spread's own
model (a normal margin at sd 12.5) on 2,448 games, because KillerSports
carries no NBA prices; then, the same evening, against two seasons of real
closing moneylines the user pulled from The Odds API (`slate.py odds-history
--sports NBA`, one snapshot a game day at 6:30 pm Eastern, 2,403 games joined;
`scratchpad/nba/dig6.py`). The dog's outright wins against the moneyline's
own de-vigged chance, by signal, with the dog's return at the best retail
price:

| Signal | Games | Dog wins vs priced | By season | Dog ML, best price |
| --- | --- | --- | --- | --- |
| **A short dog: the book makes the dog 40% or better** | 626 | 315 vs 280, **+5.6 points (z 2.8)** | **+5.6 / +5.6** | **+61.6u (+9.8% a bet)** |
| ...of which the favourite missing 20+ minutes of regulars | 460 | +7.3 (z 3.2) | +7.4 / +7.3 | +62.1u |
| ...of which the favourite at full strength | 166 | +0.8 (z 0.2) | +1.3 / +0.1 | −0.5u |
| A big favourite (dog under 25%) on a back to back | 113 | +4.5 (z 1.3) | +4.4 / +4.6 | +28.4u |
| The favourite on a back to back, the dog rested 2+ | 58 | +9.8 (z 1.6) | +2.8 / +19.8 | +23.6u |
| The favourite missing 40+ minutes of regulars | 905 | +2.2 (z 1.5) | +0.3 / +3.2 | −4.1u |
| The ratings like the dog by 4+, first thirty games | 87 | +10.4 (z 2.1) | +0.9 / +26.0 | +24.4u |
| The favourite on a back to back | 388 | +2.4 (z 1.0) | +7.3 / −3.1 | +36.0u |
| The favourite on the road | 979 | +1.0 (z 0.7) | +1.3 / +0.8 | −32.0u |
| A big favourite (dog under 25%) | 792 | −1.1 (z −0.8) | −0.3 / −1.9 | −109.1u |
| After the trade deadline | 900 | −2.0 (z −1.4) | −0.7 / −3.4 | −171.0u |
| The last two weeks | 207 | −3.8 (z −1.3) | −2.1 / −5.3 | −56.5u |

The moneyline as a whole is nearly calibrated (upsets 31.7% against 30.7%
priced) and a dog costs the vig (−3.0% a bet over everything). The excess
sits in one place: **the short dog**. Dogs at 40 to 45% won 47.6%, dogs at
45 to 50% won 52.7%, the two seasons identical (+5.6 and +5.6 points,
+31.1u and +30.5u), home and road the same (+5.6 / +5.6), early and late
season the same, before and after the deadline the same. Below 40% nothing
(30-40%: −0.3), and long dogs lose heavily (under 10%: 2 of 79). The
mechanism reads from the split: the edge lives where the favourite is
missing regulars (+7.3 on 460 games) and vanishes when the favourite is at
full strength (+0.8 on 166): the public backs the name, and the market
under-moves for the name's absences. It is the NBA's version of the
hockey backup finding, with the same shape: the market over-rates the
publicised side.

**On the sheet.** `SHORT_DOG_MIN` 0.40 and `SHORT_DOG_LIFT` +0.04 (two-thirds
of the measurement): when the book's two prices de-vig the dog to 40% or
better, the dog's win chance takes +4 points, tagged, the moneyline becomes
pickable on that row, the Upset watch card and the moneyline chip say so
in green, and the record keeps "the short dog" as its own line on the ML
tile. The rest of the table is watched: named on the card, not scored. The
one two-sigma line among the watched, the ratings liking the dog early, is
one season's (+0.9 then +26.0). The late-season caution stands: after the
deadline the dogs win less than priced.

**A note on timing.** Where the closing spread (from KillerSports) implied a
better dog than the 6:30 pm moneyline by four points or more, the dog won
50.7% against 33.4% priced on 134 games. That is the line moving toward the
dog after the snapshot, on news, and it is not a bet at the snapshot price;
it is the reason the slate runs again an hour before tip.

**What the record says the basketball book is.** The spread is priced against
everything the box score holds, and the moneyline follows the spread. The total
carries three things the close does not: it over-moves with early-season
ratings (faded, like hockey's scoring rates), it sits a point low after the
deadline and two low in the last fortnight, and two clubs have run over it for
two seasons (a label). Rest, travel, crews and announced absences are in the
number. The input the backtest cannot see is timing: a late scratch moves the
line after the close used here was set, and that is the nightly card's job,
measured from opening night on the record section.

## The simulation, 25 Oct 2026

The user: "run the matchup 500 to 10,000 times to best determine how the
game will likely end, with confidence levels, tied into the model as a
scored metric; player fouls early, coaches' tendencies, substitution
patterns, second-half patterns, late-game behaviour, pace, fatigue, refs,
travel." `slate/nbasim.py` is the engine, pure Python, 10,000 games in about
two seconds (the user: "make sure the simulation runs 10k times"). A game, each run:

- **Possessions** from the two clubs' paces relative to the league, drawn
  with a spread of 2.0 and split across the quarters by the measured
  shares; the fourth runs 3% faster in a blowout.
- **A possession** is a turnover, a trip to the line (two shots at the
  club's percentage) or a shot, a three or a two at the club's shares and
  percentages, a miss rebounded by the offence at its rate for another try.
  The make rates are scaled so the expected points equal the target: the
  club's offensive rating against the opponent's defensive rating, league-
  relative, shifted for home court (half the ledger's 1.73 a side), a back
  to back (−1.0 per 100, a priori), the regulars out (his points a game
  times 0.15 plus his minutes times 0.03 per 100, three fifths on his
  club's offence and two fifths on its defence, a priori) and the crew's
  whistle (its free throws a game against the league's, scaling the trips).
- **Who is on the floor**: the starters' share of each quarter's minutes
  (the club's own from the play-by-play when it has ten games, else the
  league's) and a gap of 4.0 per 100 between an all-starter lineup and an
  all-bench one move the target by the quarter; a margin of 16 at the start
  of the fourth empties both benches.
- **The end of a close game**: inside the last thirty seconds the trailer
  within nine fouls, the leader shoots two, the trailer takes quick threes;
  inside the last twenty-four seconds level, one side holds for the last
  shot, and down one to three the trailer takes one try. Overtime when
  level.

Two views. The **sim's own view** is that game from the ledger's ratings
(this season blended with last by n/(n+15)). The **market-anchored view**
is the same game with each side's base nudged until its mean total and
margin equal the scoreboard book's total and spread, so what is left is
the shape: the halves, the quarters, the team totals. The slate writes
both on the row as histograms (`nbasim`), and the page reads the chance of
any line off them.

**The play-by-play**, `python slate.py nba-pbp`, one ESPN call a game:
2,483 games over 2024-25, 2025-26 and this season, every substitution with
the man in and out, every foul by type, timeouts, shots with the attempt's
value, free throws, rebounds, turnovers, the clock and the score at each.
`tools_nba_tendencies.py` measures from it (`slate/nba-tend.json`):

| What | Measured |
| --- | --- |
| Possessions by quarter | 0.258 / 0.252 / 0.251 / 0.240 of the game |
| Starters' share of the minutes by quarter | 0.69 / 0.60 / 0.67 / 0.53; in the fourth by the margin at its start: 0.62 inside five, 0.60 at six to ten, 0.55 at eleven to fifteen, 0.48 at sixteen to twenty, 0.29 past twenty |
| The fourth by the margin at its start | 22.3 possessions and 1.217 a possession inside five; 23.3 and 1.187 past twenty |
| Points in the last minute | 6.3 with the margin within nine, 3.5 out of reach, 4.3 level: the fouling end is worth about 2.8 points |
| Foul trouble | a regular picks up two fouls in the first quarter in 10.3% of his games and plays 28.9 minutes in them against 29.9: a minute, not a lever |
| Timeouts a club by quarter | 1.1 / 1.2 / 1.2 / 1.9; the first substitution after 5:29 |
| The shot mix | 42.0% of attempts from three at 35.8%, twos at 54.8%, free throws at 78.1%, a trip on 10.5% of possessions, a turnover on 13.7% |

**The replay** (`tools_backtest_nba_sim.py`, 2025-26, 1,145 games with a
club profile of five games or more, 400 runs a game, the profiles built
from the games before each date with 2024-25 as the prior, against
KillerSports' closing total and spread):

| The sim's own view against the close | Result |
| --- | --- |
| The total: final − close +0.24 (sd 18.2); final − sim −0.19 (sd 19.1); the sim's total sits 5.7 from the close | the close is the better number |
| Slope of the close's residual on the sim's lean | **+0.002 (t 0.0)**: the sim's total carries nothing the close does not |
| Total calls by band, says → does | 60-65: 62.5 → 48.7 (112-118); 65-70: 67.2 → 53.5 (68-59); 70+: 74.6 → 52.0 (52-48) |
| Spread calls by band | 60-65: 62.2 → 46.2; 65-70: 67.1 → 52.7; 70+: 74.5 → 44.4; slope +0.02 (t 0.1) |
| Moneyline, says → does | 55-60: 57.3 → 57.5; 60-65: 62.3 → 64.2; 65-70: 67.5 → 74.6; 70+: 77.4 → 79.9; **slope +0.97 (t 7.1)**, Brier 0.209 against a coin's 0.250 |
| The shape | quarter shares 0.257 / 0.250 / 0.255 / 0.238 against the ledger's 0.255 / 0.250 / 0.255 / 0.240; first half 116.7 against 116.1; the sim's own spread of the total 19.1 against the market's residual 18.2; overtime 3.3% against 4.4% |

So the honest reading, the same one the earlier backtests gave: the market
prices the ratings, and a simulation built on the ratings cannot out-call
the close on the total or the spread whatever confidence it prints; its
win probabilities are nearly true, which says the engine's variance is
right. That sets the shrink each market's chance gets before it is shown
as "worth" (`nbasim.SHRINK`: total 0.05, spread 0.0, moneyline 0.97) and
the use: the sim is a distribution tool. Its value is in what the close
does not carry, the first half, the quarters and the team totals, and
those cannot be measured until their lines are in the log. The odds log
has carried the first-half close since 17 Oct; the historical first-half
lines for 2025-26 would cost about 12,000 credits on the event endpoint
(ten a game a market), which is the one spend decision left. The page's
record keeps says against does for every call at LEAN or better from the
first night, by view, market and band, so the question answers itself as
the season goes.

**The period lines, 26 Oct 2026.** The user moved to the 100,000-credit
plan and pulled them (`slate.py odds-periods`): 2025-26 from 21 Oct to 24
Jan, 675 games with the first-half, first-quarter and third-quarter
totals and both team totals at the close, fifteen minutes before tip;
2024-25 from 20 Oct to 9 Jan, 554 games with the first half. The replay
(`--periods`), the market-anchored game against each line at the line's
own price, 588 and 473 games joined:

| Market, anchored | 2025-26 | 2024-25 | Reading |
| --- | --- | --- | --- |
| First half | slope +0.08 (t 0.2); 60-65: 113-96, +5.9u; 70+: 4-4 | slope −0.30 (t −0.6); 60-65: 72-72, −6.1u | a coin; the books split the halves as well as the game |
| First half, the own view | slope +0.71 (t 2.6); 70+: 53-35, +12.5u | slope +0.18 (t 0.5); 70+: 21-23, −4.0u | the 2025-26 band did not come back: a coin |
| First quarter | slope +0.50 (t 1.0); 60-65: 75-51, +16.0u on 126; Brier 0.248 | slope +0.12 (t 0.2); 60-65: 47-32, 55-60: 70-85 | did not come back: a watch |
| Third quarter | slope +0.74 (t 1.4); 60-65: 71-64, −2.9u; Brier 0.256 | no lines | nothing; "third-quarter unders" is not in the lines |
| **Home team total** | slope +0.65 (t 1.2); 50-55: 176-128; 55-60: 133-79; 60-65: 45-23; **357-231 (60.7%), +93u** on 588 | **slope +2.74 (t 3.5)**; 50-55: 166-141; 55-60: 95-50; 60-65: 18-3; **279-194 (59.0%), +94.6u** on 473 | the inefficiency, two seasons |
| Away team total | slope +0.62 (t 1.0); 55-60: 111-92; 60-65: 31-21; 317-271 (53.9%), +18.5u | slope −0.67 (t −0.9); 247-226, +25u | positive both seasons, noisy |

Why the team totals: the book's team-total line sits off the number the
game's own total and spread imply, (total ∓ spread) / 2, and the anchored
game is built on that number. **The gap rule**, measured straight off the
lines and the finals without the sim (the second pull, 26 Oct 2026):

| Line less the implied | 2025-26 home | 2024-25 home | 2025-26 away | 2024-25 away |
| --- | --- | --- | --- | --- |
| a point or more above: the UNDER lands | 63.2% (247 games, +54.8u at the lines' prices) | 62.1% (169, +46.8u) | 56.8% (229, +18.9u) | 55.4% (112, +15.6u) |
| within a point: the under lands | 52.2% (226) | 51.4% (288) | 50.0% (246) | 51.1% (278) |
| a point or more below: the OVER lands | 63.1% (195, +40.2u) | 68.1% (94, +42.9u) | 56.5% (193, +17.3u) | 57.1% (161, +30.4u) |
| slope of the over's chance on the gap, a point | −0.057 (t −5.7) | −0.080 (t −5.1) | −0.030 (t −2.8) | −0.036 (t −2.4) |

The book posts a team total the market has not reconciled with its own
spread and total. Two seasons, the same way, t above five at home: this
one is **scored**. The Simulation card shows each team total's implied
number and gap and calls the side by the gap rule when the gap is a point
or more; the record keeps the rule's own tally by side, and the anchored
sim's calls beside it (`nbasim.SHRINK`: team 1.0, the first half 0.1, the
first quarter 0.1).

**The full-game lines history** (`tools_nba_odds_history.py`, every book's
total, spread and moneyline at noon and 6:30 pm Eastern, both seasons,
Pinnacle among them): Pinnacle's closing total less the US books' mean
predicts nothing of the final's residual (slope −1.12, t −0.8; −0.23,
t −0.2), the total's move from the opener to the close predicts nothing
(t 0.3; t 0.6; 221-220 and 181-149 with a two-point move), and the spread
shade leans the same faint way both seasons (t 1.9; t 1.2, on a shade
whose spread is a third of a point). The Pinnacle chip stays shown, not
scored.

**Does the simulation help the props?** The user asked; it does, a
little, and in a measurable way (`tools_backtest_nba_props_sim.py`,
2025-26, 17,700 player-games with eight prior games and fifteen projected
minutes). The club's expected points in the sim's own view, against its
points a game to date, explained the projection's miss on every market
(points t 10.6, PRA 13.4, assists 10.5, rebounds 6.3), where the market's
implied team points managed t 4.1 and nothing beyond the pace lever
(t 0.8). Beyond the pace and the defence-by-position levers the props
already carry, the sim's remainder, its efficiency part, still held
(points t 5.2, PRA 6.2, assists 4.8, threes 3.2, rebounds 1.6), and at half
weight it cut the miss (points 6.583 to 6.579, PRA 8.192 to 8.186); at
full weight it overshot, the defence counted twice. So the props carry a
**matchup lever** from the sim's profiles at the half power on points,
assists, threes and PRA, none on rebounds (`PROPS_MATCH_ALPHA`). The same
test showed the pace lever's form was wrong: the two clubs' mean against
the league double-counted the club's own pace, which a player's rate per
36 already carries; the game's possessions against the club's own pace
misses less on every market and is the form now.

**The runs on every prop, 26 Oct 2026.** The user: "confirm the simulation
is being run for the props as well, and attach the results to the player
props when I select them to see what the simulation did in regards to how
it was scored." The props run now plays each game the same 10,000 times as
the slate (`nba_props_game_sim`, `--runs`), from the same profiles, with
the listed-out regulars' cost taken off their club exactly as the slate's
sim does, and writes on the game row and on every prop what the runs said:
his club's median points with the middle half against its points a game by
the ratings alone, the ratio applied in full to his rate at his minutes
(the sim's own read of his number), the blowout chance, overtime and the
possessions. The prop's panel shows it under What moves it, with the
matchup lever marked as the one part the score takes, at the half weight
that measured; the full-weight read and the blowout stay shown, not
scored, for the reasons above and in the blowout row of slate/README.md. A
run nearer tip carries the later injury report, and a second load of the
props replaces an ungraded prop with the newer run.

**The own view's team totals, replayed, 26 Oct 2026.** After the Pacers
scored 136 on an own-view "UNDER 119.5, STRONG 71%", the question was
whether the own view's team-total calls had ever been measured; they had
not, only the anchored view's. Both seasons replayed with them added
(`tools_backtest_nba_sim.py`, 588 and 473 games with a team-total line):
the own view's does-on-says slope 0.30 and 0.22 at home, 0.45 and 0.08
away, every t under 1.5, its 65-70% calls landing 47% of the time in both
seasons; the anchored home team total 1.78 and 4.29 (t 2.9 and 4.7), the
anchored away 0.45 and -0.79. So `nbasim.SHRINK` splits the team totals:
the anchored home 1.5 (capped), the anchored away 0.3, the own view 0.3.
And the Simulation card now reads the **band off the worth**, not the raw
chance: a 71% worth 56% reads "no call" and an anchored 57% worth 61%
reads LEAN, which is what the replay says each is.

**The lineups test, 26 Oct 2026.** The user, after the Pacers scored 136
on a profile that was 90% last season's Pacers: "could the simulation
test the starting lineups? we have the individual players' info." Three
steps, all on the public data already in hand. (1) `tools_nba_stints.py`
cuts the play-by-play into five-man stints: the box's starters, the
substitutions ([entering, leaving]), and the men a period's plays name
before their own sub-in as that period's starters; 2,481 games, 32 stints
a game, five a side in 99.99% of them, the points adding to the final in
99.6% of games, a man's stint minutes within 0.26 of his box minutes.
(2) `tools_nba_lineups.py` fits adjusted plus-minus from the stints (a
ridge regression of each stint's points per 100 possessions on the ten on
the floor, an offence and a defence number a man, last season's stints at
half weight, the ridge strength chosen on a held-out slice: 4,000, and
the held-out stint error 62.99 against 63.17 for the league mean alone,
which is how little ten men explain of one stint), refit weekly through
2025-26, and predicts every game three ways: the club model the sim uses,
the players at the minutes they actually played (a perfect rotation call),
and the players at the rotation projected from the club's last three games.
Against 1,182 finals: margin error 14.78 for the club model, 14.61 and
14.63 for the players; totals a wash once the stint possession count's
bias is taken out; in the first month, where rosters are newest, the club
model was better (12.83 against 13.43 and 13.35); and nothing added to the
close (every t under 1.5). Knowing the exact minutes played did not beat
the projected rotation, so the rotation is not the limiting factor; the
player numbers themselves are the noise. (3) `tools_nba_prior_test.py`
weights last season's prior by roster continuity, the share of last
season's minutes played by men who have dressed this season: first-month
margin error 13.41 at the fixed weight against 13.29 scaled, a one
percent gain, within noise, and the totals no better. So the club model
stays as it is, and the lesson of the Pacers stands as a lesson, not a
fix: in October a club that changed a lot is where the own view is most
wrong, in either direction, and the market already knows it. What the
stints make possible later, if wanted: absence scenarios run at slate
time (the game with and without each questionable regular), and the props'
minutes from a rotation model rather than his last five.

What is still a priori and marked so: the cost of an absence, the bench
gap, the back-to-back penalty. What the play-by-play could add next: each
player's on/off per 100 from the stints (the absence cost measured instead
of assumed), each club's late-game pace and timeout habits, and a rotation
model for the props' minutes.

**The three voices on the total, 28 Oct 2026.** The user: "if the
simulation, the refs and the super model are all thinking over or under for
the total, that should get a green BET signal; two out of three should be
enough. Look at the Lakers and Spurs games: the simulation and the refs were
pointing to the over." (Kings @ Spurs closed 232.5 and landed 233, Trail
Blazers @ Lakers 233.5 and landed 265; on both the sim's own view said over
at 54% with three games in the profiles, the crews leaned over at z +2.1
and +4.1, and the sheet was silent under ten games.) Each voice alone had
measured nothing against the close (the tables above); the agreement had
not been asked. `tools_nba_total_agree.py`, both seasons, 2,449 games with
a close, everything known before tip: the sheet's total as the page builds
it (the close, the faded ratings lean, the stage deltas; BET at 53%), the
sim's own view at 400 runs from the profiles before the date, the crew's
lean from each official's over/under record to date (the season before
whole, this season to date; z = (W − L)/√(W + L), an official leans at 1.5,
the crew at the sum of its three):

| Voice, or the agreement | Both seasons | 2024-25 | 2025-26 |
| --- | --- | --- | --- |
| The sheet at BET, its side | 209-162 (56.3%), +28.0u | 56.7% | 56.0% |
| The sim's side at 55%+ / 60%+ / 65%+ | 49.7% / 48.3% / 51.7% | 49.0 / 47.8 / 49.0 | 50.3 / 48.8 / 53.9 |
| The crew's lean at z 1.5+ / 2.5+ | 52.7% / 52.1% | 55.4 / 51.0 | 50.2 / 53.0 |
| **The sim (55%+) and the crew agree**, the sheet not against it | **157-108 (59.2%), z 3.0, +34.7u**; the total lands +2.9 toward that side (t 2.5) | 59.0% | 55.2% |
| ... with the sheet silent | 134-98 (57.8%), +23.8u | 54.8 / 62.1 by half | 40.0 / 65.2 by half |
| ... with the sheet on it too (3 of 3) | 23-10 (69.7%), +10.9u; +9.1 points toward the side (t 2.9) | 17-8 | 6-2 |
| ... with the sheet BET the other way | 15-20 (42.9%) | | |
| The sim and the crew disagree, the sim's side | 191-195 (49.5%) | 44.3% | 53.4% |
| 2 of 3 point the same way, none against (any two) | 193-152 (55.9%), +23.5u | 55.1% | 57.0% |
| By the sim's threshold with the crew: 50 / 55 / 58 / 60 / 65%+ | 55.0 / 59.2 / 62.1 / 60.8 / 69.4% (424 / 265 / 190 / 148 / 72 games) | | |
| By the crew's threshold with the sim at 55%+: z 1.0 / 1.5 / 2.0 / 2.5 / 3.0+ | 54.3 / 59.2 / 58.8 / 60.3 / 57.8% | | |
| The first thirty days of a season | 5-5 and 3-4: the rule rarely fires with five games in the profiles | | |

So the rule the user asked for is real at the thresholds the page already
had (the sim's 55%, the crew's 1.5), rises with the sim's confidence, holds
in both seasons, and lands where the sheet's own BET band lands (56.3%). It
is **scored**: the sim's own view at 55%+ and the crew's lean on the same
side of the game total, the sheet not against it, reads BET on the
Simulation card's three-voices block and on the board's Agreement section,
in green, takeable like a sim call, on its own record line (2 of 3 and 3 of
3 apart). A sheet BET the other way blocks it (42.9%). The cautions are in
the table: the 2025-26 first half ran 14-21 with the sheet silent, and in
the first month of a season the profiles are too thin for the rule to fire
often. The slate's log prints the three voices on every game.

Two gates, from the user's own Spurs row of 27 Oct 2026 (an alternate
225.5 at −208 in the form against a market number of 232, where every
voice's "over" was the gap between the two lines): the sheet's voice is its
likelier side, not the pick by edge; a row line 1.5 or more off the
market's main number (the carded book's total in the odds block) is an
alternate, outside the measurement, no bet; and the price on the rule's
side must ask no more than the rule's 59.2% (−145 is the edge of it), else
it reads "the book's price, not a bet". Read back through the four rows
as he had them, none of the night's games fired: the Celtics (the sim
under, the crew even), the Knicks (both even), the Lakers (the crew at
z +4.1 but the sim's own view 48% over on his row, which carried Sharpe
out for the Blazers), the Spurs (the alternate line; the sim's own view
46% over even at 225.5 with Murray and Raynaud out).

**Middles on the total, 28 Oct 2026.** The user: "I use four apps,
FanDuel, BetMGM, DraftKings and Fanatics; how could we use the model to
capitalize on middle betting?" A middle is the over at one number and the
under at a higher one: the final between them wins both legs, outside
them one leg loses and the other wins, so the pair pays when the final
lands between often enough to cover the juice, 4.8% of the time at −110
on both legs. `tools_nba_middles.py` on the lines history (every book's
total at noon and 6:30 pm Eastern from two days before each game, both
seasons) against the finals, the four apps only:

| Where the gap comes from | 2024-25 | 2025-26 |
| --- | --- | --- |
| The apps' numbers at tip: within a point of each other | 1,198 of 1,231 games | 1,208 of 1,231 |
| A one-point gap between two apps at tip, the pair | 365 games, both win 1.6%, −3.5% of the stake | 565, 2.8%, −2.8% |
| The number moved 1.5 to 3 points from two days out to tip, the pair (the best app each time) | 371, 4.3%, −0.5% | 319, 4.4%, −0.6% |
| Moved 3.5 to 4.5 | 121, 7.4% (the normal said 9.2%), +2.7% | 69, 8.7% (9.5%), +3.2% |
| Moved 5 or more | 112, 17.0% (15.6%), +12.4% | 60, 20.0% (16.2%), +14.3% |
| **The page's rule**: the second leg whenever the sheet's normal says the pair pays | 473 pairs, 8.2% both win (said 9.1%), **+32.5u, +3.4% of the stake** | 362 pairs, 8.0% (8.7%), **+20.9u, +2.9%** |
| ... of which the gap under three points | 72, 1.4%, −3.2% | 54, 3.7%, −0.5% |
| ... three to four | 219, 6.4%, +1.3% | 210, 5.7%, +0.6% |
| ... 4.5 to six | 109, 8.3%, +3.5% | 66, 13.6%, +8.1% |
| ... 6.5 and up | 73, 20.5%, +16.2% | 32, 18.8%, +13.0% |
| A window of 3.5+ points somewhere in the two days, with hindsight | 364 games (30%) | 207 (17%) |
| The final within 1.5 of the last number (a three-integer middle) | 7.2% against the normal's 6.6% | 9.1% |

So the apps agree with each other too closely to middle at the same
moment, and the money is the move: a number that has run three points or
more from a leg already held. The sheet's normal at 18 points sized the
both-win chance within a point of what landed at every width, so the page
prices any pair from it, the pushes on an integer line included, and a
pair "pays" when that expectation is positive and the gap is three points
or more (under three the pairs the normal liked lost in both seasons). Two
honest notes. The measurement's first leg is taken on the side the number
later moved away from, which is known only after; holding one leg, the
window opens on the moves that go the other way, about half of them. And
the pair's value is made by the first leg once the market has moved past
it (the over at 230.5 with the number at 234.5 is 58% to win on its own);
the second leg gives up its vig and takes the loss off the table, which
is what a middle is for. **On the page**: a Middles card on the rail with
the apps' numbers as the newest odds run left them, the legs held with
the best number on the other side and whether the pair pays, every pair
across the apps' main and alternate numbers priced, and a calculator for
any two numbers; a Middles section on the board with a card and a Take
for each open window; the pair graded together on the simulation record
beside what the first leg alone did. The apps' numbers follow the newest
odds run on a row (`oddsNow`), the logged line staying as the markets
were scored.

## The player props, 19 Oct 2026

The user: "set up another tab for player props... find the ideal scenario
for player props". The ledger now keeps every player's full box line
(rebounds, assists, threes, attempts, makes, turnovers, steals, blocks and
ESPN's position beside the minutes, points and plus-minus it had), and a
ledger from before refills itself the next time it runs. `python slate.py
nba-props` writes one file a day for The Super Model's NBA PROPS tab: every
prop The Odds API posts on the day's games, with the slate's projection
beside each. Everything in the projection was measured first on the 2025-26
ledger (`tools_backtest_nba_props.py`, 1,235 games, 26,628 player lines):

| Question | Answer |
| --- | --- |
| Is rate × minutes unbiased? | Yes on every market: points +0.10 over 14,370 player-games, the rest within 0.05 |
| How wide is the miss? | One sigma k × √projection, k 1.86 points, 1.21 rebounds, 1.16 assists, 1.10 threes, 1.92 combined; a normal held 69% within one sigma on each |
| Do missing regulars lift a player? | Pooled over 21,076 player-games: every 30 minutes a game of teammates missing who play 24+ adds 1.42 minutes (t 36), 0.56 points per 36 (t 11), 0.09 assists per 36 (t 6); rebounds (t 0.6) and threes (t 1.8) nothing |
| Does a player's home/road split persist? | No: first half of the season against the second, r 0.08 over 152 players. Shown, never scored |
| Does a defence's lean by position persist? | Yes: a defence's first-half lean (per minute to guards, forwards, centres against the league) carried into the second half at 0.77 for points (t 8), 0.74 rebounds, 0.73 assists, 0.41 threes. Those are the weights; the table is the ledger's own, this season shrunk toward last season's |

The chance of the over is read from that normal and blended with the book's
own chance at 4 to 2 on the logit scale, a priori; the BET band (three
points of edge at 55%) and LEAN are a priori; the Props record tile on the
page is the test, since props cannot be backtested against lines (ten
credits a market a game on the history endpoint). The pipeline ran live
from the build container on opening night's three games with canned lines
(The Odds API answers only from the user's machine): rosters from ESPN's
team pages, 95 players on the injury page, 396 defence factors from last
season's ledger, HashtagBasketball's 150 rows shown beside them.

Two things the run taught. ESPN lists a man as G, F or C, so the defence
table is by those three and the website's five positions fold into them.
And a player's last five games of last season are April's minutes (Cade
Cunningham's averaged 23.6), so before he has played this season the
projection uses last season's whole-season mean instead.

**The blowout, and the centre (22 Oct 2026).** The second night went
321-326 with seven of eleven games decided by fifteen or more, the overs
105-162 in those games. `tools_backtest_nba_blowout.py` asked both seasons'
ledgers, joined to the closing moneylines, whether the market's expected
margin predicts the shortfall in a regular's minutes and so the projection's
miss. The minutes, yes: 0.08 a point over two seasons (t −9), 1.4 minutes at
twelve or more, the favourite's regulars most, the bench the other way. The
miss, no: the projection's bias and over rate were flat across the expected
margin in both seasons, and shading the minutes by the slope made the second
half worse. The blowouts that hurt were not in the spreads. Measured, not an
input. What the test found instead is that the over rate at the projection's
own mean is 46-47% everywhere, 41% on threes: a box-score stat skews right,
the mean sits above the median, and the books post the median.
`tools_backtest_nba_props_median.py` measures the shift that centres the
chance, 0.08 sigmas on points, 0.11 rebounds, 0.14 assists, 0.23 threes and
0.05 combined, holding from the first half of 2025-26 to the second and on
2024-25's points; the slate reads the chance around that median now, and
re-scoring the first two nights' 829 props with it reads 452-377 against
423-406 as shipped, the say-so within a point of the done.

**Usage, the role, the floors and the pairs (26 Oct 2026).** The user's
review of the props, four reads and a pattern, measured on 2025-26 before
anything was built (`tools_nba_usage_floors.py`: 93,053 player-game
projections after eight prior games, usage the share of his club's
possessions he ended on the floor):

| Question | Answer |
| --- | --- |
| Does a usage rate of 24% or more pick a side? | No: the over rate at the projection's median is 49.9% under 18%, 50.8% at 18 to 24%, 49.4% at 24% and up (points, 21,467 rows). The projection is unbiased at every usage |
| Does usage say how far the projection misses? | Yes: the miss in sigmas runs 1.13 / 1.08 / 0.93 on points, 1.18 / 1.08 / 0.91 on PRA, 1.12 / 1.00 / 0.97 on rebounds, 1.04 / 1.03 / 0.98 on assists, and the first half of the season says the same as the second (points 1.10 → 1.14, 1.05 → 1.10, 0.92 → 0.94). It is a sigma factor now, the side untouched |
| Do starters differ from the bench? | At low usage, yes: a starter's miss 1.03 sigmas against the bench's 1.17 on points, 1.02 against 1.25 on PRA; at 24% and up 0.91 against 1.04. A starter's over rate 51% at every usage, the bench's 46 to 50% (started his previous game as the test's stand-in for the lineup; the slate reads RotoWire's five). The role table is used when the role is known, the usage table when it is not |
| Are the 95% alternate lines honest? | Honest to conservative: the model's 95% floor (the median less 1.645 sigmas) cleared 97.5% of nights on points, 97.4% rebounds, 97.8% assists, 97.3% PRA; the 90% floor 93%; the 80% floor 82 to 86%. Rounded down to a book's whole number the 95% line cleared 98% |
| Do one man's three floors land together? | More than independence says: 373 player-games with points, rebounds and assists floors at one or more, all three cleared 96.5% against 85.7% for three independent 95% legs; his minutes carry all three |
| Do two players' props in one game land together? | Almost as independence says: both over the median 23.7% of 22,381 same-club pairs and 25.2% of 25,789 opposite-club pairs, against 25.0%; both over the 80% floor 67.0% and 67.9% against 64.0%. One over and one under on the same club 26.6% |
| Does one man's two markets land together? | Yes: points with rebounds 29.3% of 15,987 pairs, points with assists 28.3%, rebounds with assists 28.8%, against 25%; points with threes 38.2% of 7,914, the threes being points |

The page's same-game pairs carry those as factors on the product (0.95
two overs on one club, 1.0 two players, 1.15 one man's two markets, 1.5
his points with his threes), capped at the lesser leg, and are graded on
their own tile from the first night.

**Usage at home and on the road (26 Oct 2026).** The user: "does the
simulation also account for usage on the road vs home?" The simulation has
no players in it, so no usage at all; home court sits in the club profiles
and reaches a prop through the matchup lever and the sim's read. The props'
usage is his share over all his games, and `tools_nba_usage_venue.py` asked
2025-26 whether a venue split would be worth carrying: pooled usage is
19.99% at home and 19.99% on the road (11,416 and 11,427 player-games of
ten minutes or more); a player's own home-less-road split has a median of
−0.12 points of usage with the middle half −1.06 to +0.86, and the split
over the first half of the season predicts the second half's at r 0.03
(252 players with eight games at each venue in each half), the same null as
his points-per-36 split (r 0.06 here, 0.08 before). The one venue effect in
a player's line is the league's home edge, about 0.3 points per 36: the
points projection's miss runs +0.03 sigmas at home (t 2.9) and −0.01 on
the road, the over rate 50.9% against 49.0%, and that edge is the club's
home court, which the matchup lever carries already. Nothing to add.

**Does a specific teammate's presence help a man? (26 Oct 2026).** The
user, reading three Ty Jerome games: "when Cedric Coward was out Ty didn't
cover, when he's in he did; I imagine Coward may have helped his stats."
`tools_nba_pair_with_without.py` asked 2025-26 for every player and regular
teammate (24 minutes a game, ten games or more) with eight or more games
each way, inside the teammate's window with the club: 1,030 pairs. A man
scores 0.64 points per 36 LESS with the teammate on the floor than without
(median −0.71, PRA −0.73), and in only 39.5% of pairs does he score more
with him: the pooled regulars-out rule, seen pair by pair. The spread of the
pair splits (sd 2.74 points per 36) is barely wider than shuffling the
with/without labels gives (2.53), and a pair's own split over the first
half of the season predicts the second half's at r 0.09 (280 pairs). So
"this teammate helps him" is noise almost everywhere, and the biggest
splits either way come from the smallest samples. Jerome's three games
with Memphis cannot say anything, and his one miss was 35 against 35.5 on
his usual shots. The panel's line keeps the pooled direction in words,
"out (26 mpg, a lift for him)" and "back (26 mpg, the lift gone)".

**The regulars-out lever, where the lift lands (27 Oct 2026).** The user's
first week of props: the picks with a regulars-out lever of 1.5 or more
went 118-153 at a 55% say-so, on both sides. `tools_nba_out_targeting.py`
on 2025-26 (21,651 player-games after eight prior games, 69% of them with a
regular out by the ledger's own rosters):

| Question | Answer |
| --- | --- |
| Where does the minutes lift land? | +1.20 minutes per 30 mpg out pooled (t 28); starters +0.51 (t 8.6), bench +1.79 (t 29); his minutes under 20: +1.82, 28 and up: +0.30. One man out under 30 mpg moves nobody (−0.34, t −3.7); two or more out (48 mpg and up) +1.58 (t 19) |
| The points lift? | +0.43 per 36 per 30 mpg out pooled (t 6.9); starters +0.60, bench +0.28; by usage 24% and up +0.59; +0.028 per 36 for each point a game the absent men had (t 5.9) |
| Rebounds? | Null pooled (+0.02, t 0.7); +0.011 per 36 per rebound a game absent (t 1.7); the absent men at 12+ rebounds a game +0.09 (t 1.4): not enough |
| Assists? | +0.07 per 36 per 30 mpg out pooled (t 3.3); +0.037 per 36 for each assist a game the absent men had (t 6.2): absent men at 12+ assists a game +0.44 per 36 (t 4.8), under 5 nothing |
| Is the chance too sure of itself with regulars out? | No: the miss spreads 0.96 to 0.99 sigmas with nobody out, under 30, 30 to 48 and 48+ mpg out alike; the bias runs −0.12 to −0.21 sigmas everywhere (the mean against the median), 0.06 wider at 48+ |
| Does a rule by role beat the pooled rule out of sample? | Fitted on the first half (minutes starters +0.64, bench +1.78; points starters +0.36, bench +0.11), scored on the second: points rmse 6.200 against 6.211 with a regular out, rebounds 2.570 against 2.572, assists 1.920 against 1.921; the creator rule on assists 1.922. A hair, not a rule. The pooled rule stays |
| A thin history? | The miss in sigmas by the games the rate rests on, this season alone: points 1.09 (3 to 5 games), 1.10 (6 to 9), 1.08 (10 to 19), 1.02 (20 and up); rebounds 1.06 / 1.05 / 1.02 / 1.00; assists 1.01 / 1.02 / 1.02 / 0.98. The sigma carries ×1.06 under ten games of evidence and ×1.03 under twenty |
| The minutes to project? | The mean of his last five (rmse 6.53 on his actual minutes) beats their median (6.81), a trimmed mean (6.64) and the season mean (6.85); early in a season (3 to 5 prior games) the mean runs +0.75 high, the median +0.43 |

**The combination markets (27 Oct 2026).** `tools_nba_combo_markets.py` on
2025-26, the projection built the slate's way after eight prior games:

| Market | n | k (sigma = k √proj) | over the mean | median shift | 95% floor cleared | miss in sigmas by usage (<18 / 18–24 / 24+), starters and bench |
| --- | --- | --- | --- | --- | --- | --- |
| points + rebounds | 21,610 | 1.90 (backtest) | 47.6% | 0.06 | 99.0% | 1.05 (S 0.93, B 1.12) / 0.98 (0.91, 1.05) / 0.84 (0.81, 0.98) |
| points + assists | 21,577 | 1.86 | 47.7% | 0.05 | 98.9% | 1.05 (0.94, 1.10) / 1.00 (0.92, 1.08) / 0.83 (0.80, 0.96) |
| rebounds + assists | 21,316 | 1.32 | 46.7% | 0.08 | 99.2% | 1.06 (0.94, 1.13) / 0.95 (0.89, 1.00) / 0.89 (0.87, 1.01) |

The factors shipped are these scaled to the shipped sigma the way the
first five's were (the tool's own k runs wider than the backtest's, which
blends last season's prior in): points + rebounds (1.14, 1.07, 0.92),
points + assists (1.14, 1.09, 0.90), rebounds + assists (1.10, 0.99, 0.93);
starters (1.03, 1.01, 0.90) / (1.04, 1.02, 0.89) / (0.98, 0.93, 0.90), the
bench (1.24, 1.17, 1.09) / (1.22, 1.20, 1.07) / (1.18, 1.04, 1.05). The
same tool reproduces the first five's centres (0.07, 0.11, 0.13, 0.19 and
0.04 against the shipped 0.08, 0.11, 0.14, 0.23 and 0.05).

**The opponent's absences (28 Oct 2026).** The user, after a rough night on
the props: "when players are out that's going to help the next man go over,
not under, yet it seems to think the same for the defence even when certain
main players are out." It did: the props carried his own club's absences
(the pooled regulars-out rule) and the simulation beside the card took two
fifths of an absence off the club's defence, but the scored matchup lever
read the opponent's full-strength rating (`club_match` zeroes both clubs'
absence adjustments so his own club's lever is not counted twice), so
nothing in the projection said the defence was short-handed.
`tools_nba_opp_out.py` on 2025-26 (21,651 player-games after eight prior
games, the opponent short a regular in 70% of them):

| Question | Answer |
| --- | --- |
| The lift per 30 mpg of OPPONENT regulars out, his own club's held in the same regression? | Points +0.17 per 36 (t 2.7) against his own club's +0.42 (t 6.9); rebounds +0.09 (t 3.2); assists +0.05 (t 2.7); threes +0.02 (t 1.6); his minutes +0.01 (starters −0.14, t −2.5; the bench +0.15, t 2.4) |
| By who is out for them? | A centre out: points +0.44 (t 2.5), rebounds +0.36 (t 4.5); a forward: points +0.23 (t 2.2), assists +0.09 (t 2.5); a guard: nothing. By his own position, the missing centre lifts forwards' rebounds +0.58 (t 3.9) and centres' +0.90 (t 3.5), guards' +0.03 (t 0.4); points for guards +0.42 (t 1.6) and forwards +0.62 (t 2.1) |
| By what the absent men did? | Per rebound a game the absent men had: points +0.080 (t 3.5), rebounds +0.042 (t 3.9); per point a game they had: nothing, a shade negative (−0.021, t −2.1); per assist: nothing |
| Does it hold from one half of the season to the other? | Points −0.02 in the first half, +0.30 in the second (t 3.8); the pooled lever fitted on the first half and scored on the second moved the rmse 6.2018 to 6.1985, nothing. Assists +0.02 then +0.13, threes −0.03 then +0.06: no. The one piece that held: forwards' and centres' rebounds per 30 mpg of an opposing centre out, +0.56 (t 2.8) in the first half, +0.78 (t 4.6) in the second, +0.69 (t 5.3) whole; as plain means +0.49 / +0.69 per 36 with 25 to 35 mpg of centre out. The centre's minutes carry it, not the absent men's rebounds a game (+0.58, t 3.7, against +0.010, t 1.1, in one regression) |
| What the chance saw, the median shift in? | Forwards' and centres' rebounds with no opposing centre out: over the number 46.1% / 44.4% by half, bias −0.02 / −0.03 sigmas; with a centre out 48.0% / 49.8%, bias +0.02 / +0.11 (t 0.5 / 2.8). Whole season, 48.9% against 45.1% on the other nights, bias +0.067 (t 2.4) |
| The size that lands? | The per-36 regression says 0.69, but 0.69 overshoots the miss (bias −0.081, t −3.0, the over 42.9%); 0.30 per 36 per 30 mpg zeroes it (+0.001, 45.9%; the rmse 3.1108 against 3.1145 with nothing). Shipped at 0.30 for forwards and centres on rebounds, PRA, points + rebounds and rebounds + assists (`PROPS_OPP_C_REB_PER30`); the opponent's regulars out named on every prop, shown, not scored elsewhere |
| What the simulation's defensive share would say? | 0.4 of the cost per 100 off the opponent's defence is 2.2 per 100 in those games, 1.9% of a 114 rating: +0.23 points per 36 per 30 mpg on a 20-per-36 scorer, near the pooled +0.17 that did not persist. On the strip, not in the score |

## The simulation's second engine, 30 Oct 2026

The user asked what pattern sat behind the 20th and the 25th on the props'
night-by-night table, and for the missing link in the simulation's DNA with
every scenario run. The pattern is in CALLSHEET3.md (the overs bleed, the
model's lean on a prop is worth nothing against the book's price); this
section keeps the measurements behind the engine's second version.

**The shape, two seasons of closes (2,449 games with quarters).** Around the
market's numbers each side's points vary 127 and 129 (sd 11.3), the two
sides covary 33.7 (r 0.26), so the total spreads 17.97 and the margin 13.73.
A side's first-half surplus comes back in the second half (slope −0.12 away,
−0.08 home), the margin's comes back 21% (r −0.21), the total's does not
(−0.01). Overtime 4.7%. The engine as it stood, on the demo matchup: a side's
variance 160, covariance 21.6, total 19.06, margin 16.65, no reversion
(+0.00), overtime 3.3%. Independent possessions at the real possession's
own variance (1.43 per possession, measured on 487,468 possessions; the
engine's 1.37) cannot make 13.7: the game regresses on itself.

The possession-level read of the score effect (points per possession by the
offence's margin at the time, by period) shows the gap small and the leader
often ahead, because the leader is the better side on average; so the
constant was set on the moments above. The grid (demo matchup, 20,000 runs
a cell; the real moments as the target):

| score_k | pace noise | quarter noise | last shot | a side's var | cov | total sd | margin sd | OT | a side's half corr | the margin's |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| target | | | | 128 | 33.7 | 17.97 | 13.73 | 0.047 | −0.10 | −0.21 |
| 0 (the engine before) | 2.0 | 1.0 | 0 | 160.7 | 21.2 | 19.08 | 16.70 | 0.032 | +0.02 | 0.00 |
| 0.0020 | 1.0 | 0 | 0 | 131.5 | 35.2 | 18.26 | 13.88 | 0.041 | −0.07 | −0.18 |
| **0.0025** | **1.0** | **0** | **−0.3** | **128.7** | **39.3** | **18.33** | **13.37** | **0.045** | **−0.09** | **−0.22** |
| 0.0030 | 1.0 | 0 | −0.3 | 125.7 | 43.0 | 18.37 | 12.86 | 0.044 | −0.10 | −0.25 |

**The level.** The clubs' ratings blended absolutely with last season's
profile, so the sim's centre carried last season's scoring level into this
one and followed the league's within-season swings months late. The gap of
the sim's expected total to the close by month, 2025-26: October −4.1,
November −1.9, December −0.2, January +4.6, February +2.2, March +0.8 (the
league scored 233.8 a game in October, 227.5 in January, 234.2 in March).
With the ratings as deviations from their own season's league level riding
the last fortnight's level (half-life 10 days, 150 team-lines of the season
kept beside it) the monthly means sit within 2.3 points of each other and
the sim-to-close gap tightens from 5.3 to 4.9 points (sd), on 2,293 games.
The lean carries nothing beyond the close either way (slope −0.05 before,
−0.10 after, t −1.3).

**The lift.** The engine's regulation mean sat over the ratings' implied
total: the last-30-seconds branch spent 28 seconds a round and then ran a
round on two seconds of clock, a possession a side every game (+1.5 points);
the fouling sequences and garbage time the rest. The branch now needs its 28
seconds (a held ball, or one possession when seven seconds remain), and the
measured lift (1.0063 on 286 real matchups at 2,000 runs, with the shape
above) is divided out of both sides' bases; a selftest guard holds the
regulation mean within 1.5 points of the implied total. Overtime's points sit
on top of the ratings' 48 minutes, as they do in the finals.

**Absences, within the club.** A man with 18+ ppg who played eight of his
club's last ten games and is listed out tonight (188 cases, two seasons): the
market's expected margin for his club, less the sim's, relative to the same
club's other games, −1.46 (se 0.28), −0.62 per 10 ppg of the absent man (18-22
ppg −1.09, 22-26 −1.53, 26+ −2.54); the close total less the sim's, −1.81
(−0.77 per 10 ppg): his club scores less, the other side does not score more.
The market's own miss on absences is null (the 15 Oct table said the same),
so the market's price is the right cost. The slate's cost was 0.15 a point
plus 0.03 a minute per 100, three fifths offence and two fifths defence: 4.7
points of margin for a 25-point man. Now 0.075 a point, all offence.

**Rest.** What the close carries that the sim did not (the close's expected
margin less the sim's, 2,293 games): a back-to-back for the home side less
the away −0.70 (t −2.6) beyond the sim's −1.0 per 100, a third game in four
nights −0.34 (t −2.0), a road trip of three or more −0.36 (t −1.8); the
market's own miss on each null. The sim's constants: −1.7 and −0.35 per 100.

**The crew, across seasons.** 60 officials with 25+ games in both seasons:
the correlation of an official's mean total-minus-close from 2024-25 to
2025-26 −0.09, of his over rate −0.10, of the pace of his games −0.01, of his
free throws a game 0.13. 2025-26 games whose crews had leaned under by 1.5+
points the season before ran +0.95 over the close (n 81), over-leaning crews
+0.53 (n 432). The agreement rule's crew voice is on watch; its live record
(1-5 as of the 30th) decides.

**Labels and watches.** Denver's and Utah's games ran over the close at home
(+7.5 and +0.5, then +1.3 and +9.8) and on the road (+2.7 / +5.5, +7.3 /
+1.7): a club label, not altitude. An away side two or more zones east: the
home side covered by +1.9 and +2.5 (two seasons, 136 games); two or more
zones west: −3.1 and −2.4 (121): a watch, not scored. March and April ran
over the close 56.9% and 54.3% (+2.2 and +3.2); October 2025 ran over 59%
(+3.3), so the early-season under of the literature is gone. Day-to-day men
who ended up sitting moved the home side's cover (t −2.2): the late scratch
the close cannot see, nothing to act on.

**The props, measured on the first ten nights (4,321 graded).** Brier of
the chance for the sheet's side, on the 1,671 props Pinnacle priced at the
same number: the sheet's blend 0.2505, the model alone 0.2664, the carded
book's devigged price 0.2468, Pinnacle's 0.2468, all books' consensus
0.2467; the blend's weight on the model fit best at none and worse at every
step up. Where the model stood 10+ points above Pinnacle the outcome landed
48.3% (the model said 67.7%, Pinnacle 50.3%); 5-10 points above, 49.7%
against 59.4% said. Blind at the best price across the books: every under
53.2% (the prices said 50.7%, +0.8% ROI), every over 46.8% (49.3%, −8.8%); at
Pinnacle's prices 54.3% and 45.7%. By market the under beat the over in
every scoring stat (assists 59% to 50%, threes 59% to 51%, PRA 55% to 46%)
and not on rebounds (56% to 55%). Line shopping against the consensus fair
at the same number found 64 props with 4+ points of price edge, 36-28: too
few. The game script: 20,729 starter-games against the closes, a starter's
minutes land 0.187 under his last-ten mean per point the final margin runs
above 13.5 (+1.73 inside five, −3.64 at 25 and up; −0.096 a point of the
spread), the bench's +0.006 a point. The sheet now runs with the market as
its spine (`PROPS_MODEL_W` 0.5 against the anchor's 4.0), the book's over
chance read 2.5 points lower, and the game script on starters' minutes from
the simulation's expected margin.

**The replay with the second engine** (`tools_backtest_nba_sim.py`, 1,000
runs a game, the period lines where the pull has them; the first run before
the overtime-minutes fix, which took about a point off the sim's level):

| | 2025-26 (1,145 games) | 2024-25 (1,148) |
| --- | --- | --- |
| The sim's gap to the close (sd) | 5.0, from 5.6 | 4.8 |
| The sim's own spread of the total | 18.4, from 19.1 (the market's 18.2) | 18.3 (17.6) |
| Overtime | 4.6%, from 3.3% (played 4.7%) | 4.5% |
| The total, the own view: slope of does on says | −0.17 (t −0.8); 65%+ 110-99 | −0.14 (t −0.6); 65%+ 84-100 |
| The spread, the own view | −0.07 (t −0.3) | −0.01 |
| The moneyline, the own view | +0.91 (t 6.7); 70%+ says 77.2, does 78.5 (281-77) | +1.53 (t 9.6; no prior season, the ratings shrunk to the mean) |
| First half, anchored / own | +0.42 / +0.25 (t 0.8 / 1.0) | −0.50 / −0.04 |
| First quarter, anchored | +0.47 (t 1.0); 60-65: 82-53 | no lines in the pull |
| Home team total, anchored | **+1.01 (t 1.9); 355-233 (60.4%), +93u**; 55-60 says 57.2 does 65.4 | no lines in the pull |
| Away team total, anchored | +0.80 (t 1.4); 322-265 (54.8%) | |
| Home / away team total, own view | +0.56 (t 2.0) / +0.39 | |

The shrinks after it (`nbasim.SHRINK`): the total 0.0 (from 0.05), the
spread 0.0, the moneyline 0.97, the first half 0.1, the first quarter 0.1,
the anchored team totals 1.5 (the home side's says still run under its does),
the own view's 0.3. After the overtime-minutes fix, on a third of each
season's games: the sim's total sits −0.01 from the close in 2025-26 (sd
4.9) and −0.79 in 2024-25 (sd 4.5), against the finals +0.9 and +1.0 where
the close itself sat +0.9 and +0.2 under them.

**The shape replay with the second engine** (the anchored game, 1,145 games
of 2025-26 at 2,000 runs): the probability integral transform of the actual
total inside the sim's distribution sits flat across the deciles (9.4 to
10.8; the old engine piled 11.5 in the middle), the margin's too (8.4 to
11.6, against the old 5.7 to 13.9); the total lands inside the sim's middle
half 50.1% of the time (52.1% before), the window averaging 24.8 points wide
(26.2); the total's spread 18.31 against the market's 18.22 (19.10 before),
the margin's 13.37 against 13.93 (16.76), the first half's 11.99 against
12.09; overtime 4.3% against 4.2% (3.3%). By the game's pace, three-point
share and closing total the sim's spread moves with the real one within half
a point in every tercile.
