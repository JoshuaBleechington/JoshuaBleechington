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
