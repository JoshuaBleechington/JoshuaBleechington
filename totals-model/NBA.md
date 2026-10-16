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

## The upset watch, 16 Oct 2026

The user: "look for potential upsets too." The dog's outright wins against
the spread's own model (a normal margin at sd 12.5, the engine's) on 2,448
games, by signal (`scratchpad/nba/dig4.py`); the spread stands in for the
moneyline because KillerSports carries no NBA prices:

| Signal | Games | Dog wins vs the model | By season |
| --- | --- | --- | --- |
| The favourite missing 40+ minutes of regulars | 926 | 291 vs 271.2, +2.1 points (z 1.5) | −0.2 / +3.4 |
| A favourite of ten or more on a back to back | 86 | 17 vs 13.6, +3.9 (z 1.0) | +0.4 / +7.2 |
| The favourite on a back to back, the dog rested 2+ | 55 | +6.7 (z 1.1) | +0.3 / +15.5 |
| The ratings like the dog by 4+, first thirty games | 89 | 39 vs 30.1, +10.0 (z 2.0) | +0.4 / +25.5 |
| The ratings like the dog by 4+, after thirty games | 378 | −0.1 (z −0.1) | −0.9 / +0.6 |
| The favourite on the road | 1,012 | +0.9 (z 0.6) | +0.2 / +1.6 |
| After the trade deadline | 933 | 238 vs 260.7, **−2.4 (z −1.7)** | −2.0 / −2.9 |
| The last two weeks | 224 | 46 vs 57.0, **−4.9 (z −1.8)** | −3.7 / −6.1 |
| A big favourite (10+) | 617 | −1.2 (z −0.9) | −3.8 / +1.2 |

Nothing clears noise with the same sign both seasons. The one two-sigma line,
the ratings liking the dog early, is one season's (+0.4 then +25.5), the
same early-season watch the spread carries. The clearest thing in the table
runs the other way: after the deadline and in the last two weeks the dogs
win LESS than priced, because the favourites run through the tankers. So the
NBA card carries an **Upset watch** note naming the signals present (the
favourite's regulars out, a big favourite on a back to back, the early
ratings gap, the late-season caution) and scores none of them; the board's
Upset watch lists the dogs with a signal; the record decides.

**What would settle it.** Real closing moneylines for the two seasons, which
KillerSports cannot give. `slate.py odds-history --sports NBA --season
2024-25` (Run NBA odds history.bat, 16 Oct 2026) pulls them from The Odds
API's history, one snapshot a game day at 6:30 pm Eastern on the ledger's
dates, the moneyline alone, about 1,650 credits a season, into
`odds-history-NBA-SEASON.json`. With both seasons in, the upset table above
is re-run at the price each dog paid rather than at the spread's model.

**What the record says the basketball book is.** The spread is priced against
everything the box score holds, and the moneyline follows the spread. The total
carries three things the close does not: it over-moves with early-season
ratings (faded, like hockey's scoring rates), it sits a point low after the
deadline and two low in the last fortnight, and two clubs have run over it for
two seasons (a label). Rest, travel, crews and announced absences are in the
number. The input the backtest cannot see is timing: a late scratch moves the
line after the close used here was set, and that is the nightly card's job,
measured from opening night on the record section.
