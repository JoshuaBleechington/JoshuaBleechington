# The slate script

`slate.py` runs on your own computer, pulls the day's MLB inputs, and writes
one file that Call Sheet 2.0's **Load slate** button reads. Nothing on the
sheet changes; the file just saves the typing. It needs Python 3 and nothing
else: no packages, no account, no key.

## What it fetches, per game

| On the sheet | Where it comes from |
| --- | --- |
| Starters, their ERA and innings | MLB's stats feed, probable pitchers and season pitching line |
| Each starter's last five starts, ERA and innings | The pitcher's game log. **Shown on the sheet, not scored**: recorded so recent form can be tested against the record |
| Runs per game, both teams | MLB's stats feed, season team hitting |
| Bullpen ERA, both teams | Built from the active roster: every pitcher whose starts are fewer than half his appearances, minus today's starters, earned runs over innings. Both numbers are printed: the whole roster and the **top five by appearances**. In the regular season the roster number goes on the sheet; in the **postseason the top five** does, because the mop-up arms do not pitch in October |
| Last-10 average total, both teams | The team's last ten finished games on the feed |
| Head-to-head average and meetings | Every finished meeting this season |
| Wind mph, direction, temp | Open-Meteo's forecast at the park for first pitch and the two hours after, resolved to out / quarter-out / cross / quarter-in / in against the park's centre-field bearing in `parks.json`. If MLB has posted its own stadium wind, that wins. |
| Roof | `dome: true` for a fixed roof. A retractable roof gets a note; tick **Roof shut** yourself if it is closed. |
| Lineups | Listed when posted, and anyone who started the team's last game but is not in today's order is named in a note |

It never carries a **line, a price, tickets or money**. Those come from the
book and are typed. The **park factor** fills from `parks.json`, which
carries Statcast's 3-year figure for every park (read 6 Oct 2026; re-read
once a season). The **WNBA** is not covered: pace, ratings,
rest and last five still come from a stats site by hand.

## Hockey (Call Sheet 3.0)

Two more double-click files: **Run NHL slate.bat** before the games and
**Grade NHL yesterday.bat** the morning after, or `python3 slate.py nhl` and
`python3 slate.py nhl-grade`. They write `nhl-slate-DATE.json` and
`nhl-grade-DATE.json`, which load into Call Sheet 3.0 the same way.

The slate reads **RotoWire's NHL lineups** and **CBS's goalie depth chart**
for the goalies (19 Oct 2026). RotoWire marks most starts *Expected* in the
morning and *Confirmed* after the morning skate, so run the slate in the
afternoon when you can, or run it twice: a game already on the card takes
the Confirmed tick from the second run but keeps the goalie it has, so if
RotoWire has changed its mind by then, pick the new goalie in the sheet's
**Who is in net** list by hand.

| On the sheet | Where it comes from |
| --- | --- |
| Goalies: the likely starter, save %, shots faced | The club's goalie page, each line blended with **half of last season's** from the player's page, so a first start of .739 on 23 shots reads as the man's own prior and not the league's. On a back to back the slate names the goalie who did **not** start yesterday; otherwise the one with the most starts. Then **RotoWire's NHL lineups page** (19 Oct 2026; today's page, or tomorrow's, the only two it shows) names tonight's goalie for each club and the slate takes him over the guess, his line with him: a start RotoWire marks **Confirmed** ticks the sheet's Confirmed box, one marked **Expected** is said to be expected and left for you to tick when it turns green. A goalie RotoWire names who is not on the club's page (a call-up) is noted and the guess stands. **CBS's goalie depth chart** adds its news blurb on the named goalie and names any goalie of the club on its reserve list with the injury. Either page can fail alone; the slate still writes and says what it could not read |
| Backup in net | Ticked when the named starter has under 30% of his club's starts, ten starts in. One backup in a game and the total landed 0.18 under the close over two seasons, so the sheet puts a tagged −0.15 on the line and keeps the under's record. Before the club has ten starts, the starts rule cannot speak, so **CBS's depth chart** decides: the box is ticked when CBS lists the named goalie as the club's backup, and the note says so. Ten starts in, the starts rule decides and a disagreement with CBS is only noted. Untick the box if you know better |
| The goalie picker: every goalie on each club, with his line, starts and the club's starts | The club page, written into the sheet's hidden `ngoalies` box with the named starter's name. On the sheet, **Who is in net** lists them; picking the goalie RotoWire or CBS names fills his line and sets the Backup box. The morning grade run adds **who actually started** from the box score, and the sheet keeps the total's record split by whether the carded goalie played (11 Oct 2026: 42 of the first 150 boxes had the other goalie's line) |
| Shots for per game, power play %, penalty kill % | The league's team summary report |
| Last-10 average total, rest days, head to head | The club's season schedule |
| Recent form: each side's last five, with the score, the score after one, shots for and against, and who started in net | The box scores and game pages of those games. Shown on the sheet's Recent form card, not scored |
| Context: each club's rank in the league on the numbers above (scoring rates, the last ten, empty-net habits, shots, special teams, expected goals) and the named goalie among the goalies with 100+ shots | The league ledger, the team summary, MoneyPuck's table and the league's goalie report (one call). A club shows when it sits in the top or bottom eight; the goalie always. Each line carries the **tag** that says what the sheet did with the fact: scored, faded, shown or a label (14 Oct 2026). Rendered on the sheet's Context card, never read by the engine |
| Expected goals for and against per game, each side, and the table's league mean | MoneyPuck's team file for the season (fetched; or a `teams.csv` you download from moneypuck.com/data.htm into this folder when the site is blocked). Blank until a club has five games. **Shown on the sheet, not scored** since the 7 Oct backtest |
| (backtest only) each game's starters and their lines, power-play goals, penalties | `python slate.py nhl-ledger --season 20252026 --detail`: a second pass over a season's ledger, two calls a game, about 40 minutes, written every 100 games so it can be stopped and resumed. Feeds `tools_backtest_nhl.py`'s goalie and special-teams tests |
| (backtest only) each game's referees, linesmen and scratch counts | `python slate.py nhl-ledger --season 20252026 --refs`: a third pass, one call a game to the game page's side panel, about 20 minutes, resumable the same way. Run on both seasons 7 Oct 2026 (`tools_backtest_nhl_refs.py`): crews do call penalties at persistently different rates, and the total against the close does not follow them. Referees are not an input; the pass stays for re-tests |
| First-period last ten, each side | The **league ledger** (`Run NHL ledger.bat`, or `python slate.py nhl-ledger`): every regular-season final in the league with period scores, shots, empty-net goals and overtime, in `nhl-ledger-SEASON.json` in this folder. Run it before the slate; it adds only the new finals each time, prints the league's measured figures against the sheet's assumptions, and the slate reads each club's last ten first periods from it once a club has five |
| Finals and the first-period score | The game page the next morning. A shootout win is a one-goal margin, as the league records it |
| The alternate total with a verdict (19 Oct 2026) | The odds file's alternate numbers on the sheet's side, priced by the same projection; the one that reads STRONG BET or MAX BET with an edge becomes its own market on the rail, the board and its own record tile, never the pick. The band is the chance and the price already asks for most of it, so read the edge. From the same day the parlay four takes the likeliest side on each game, the alternate included |

The two goalies' lines are both printed, with both halves (this season and
last season at half), so if RotoWire or CBS names the other one you can type
his save % and shots over the slate's. A team that has not played yet gets
last season's goalie lines, shots halved, with a note — the same half by
another route.
Shots per game, special teams and the last ten wait until a team has five
games; before that the boxes stay blank and the sheet is the market plus
the goalies.

## Basketball (The Super Model, 15 Oct 2026)

Three double-click files, in this order on a game day:

1. **Run NBA ledger.bat** is no longer a daily step (25 Oct 2026): the
   slate and props runs bring this season's `nba-ledger-202627.json` up to
   date themselves before they read it, a scoreboard call and a summary a
   game, seconds for a night's finals (`--no-ledger` skips it). The bat
   stays for the first run of a past season (`2025-26` at the prompt), which
   the props need for last season's history, and for a rebuild. Every
   rating on the slate and every player's last games come from this file.
2. **Run NBA slate.bat**, or `python slate.py nba`: writes
   `nba-slate-DATE.json` with every game on the league's scoreboard that
   has not been played, each simulated 10,000 times (the section below).
   In The Super Model: **Saving → Load slate**, pick it, press **Fill form**
   on each game.
3. **Run odds.bat**: the NBA is in the default sports now, so the total,
   its prices, the first-half total, the spread and the moneylines fill
   from the carded book. Run it early for the opener and again before tip
   for the close.
4. **Run NBA props.bat**, or `python slate.py nba-props` (19 Oct 2026):
   writes `nba-props-DATE.json`, every player prop the books post on the
   day's games with the slate's projection beside each, about five credits
   a game. In The Super Model: **NBA PROPS → Load props**. Run it late
   enough that the books have posted the props, usually by the early
   afternoon; it brings the game logs up to date itself first, reads ESPN's
   injury report together with RotoWire's lineups page (a RotoWire Out
   counts, a confirmed starter ESPN still has Out does not), and plays each
   game **10,000 times** (the slate's own simulation, from the same profiles
   and that report) and attaches the runs to every prop, read on the prop's
   panel (26 Oct 2026).
5. **An hour before tip**, run the slate, the odds and the props again and
   load each. What a second load does to a game already on the card (23 Oct
   2026): it fills boxes that were blank (the crew the league posted after
   the morning run, a line the odds had not listed), **replaces the starting
   five, the who-is-out list and the simulation** with the newer ones
   (expected to confirmed, a scratch, the runs from the later injury
   report; 26 Oct 2026), ticks a confirmed goalie, and replaces ungraded
   props; it never overwrites any other filled box, so the line, the prices
   and the ratings stay as they stood when the row was added, and the
   record is of the row as logged.
   Tick a doubtful player out on the card if he is ruled out late. The
   **close** for the record does not come from the page at all: every odds
   run writes what it saw to `odds-log.json`, the last run before tip is the
   close, and the morning grade attaches it. So the one thing that must
   happen on a game day is an odds run after the day's games are listed; a
   day without one grades with no close. A game that has already tipped is
   **left alone** by the odds and props runs (23 Oct 2026): its lines are
   in play, so the log keeps the last pre-tip snapshot as the close and the
   props called before tip stand; on a night with an early game, running
   for the late games is safe. The grade also checks (24 Oct 2026): a
   snapshot taken at or after tip is an in-play line and is passed over for
   the opener, with a note on the row saying so; the Bulls at the Bucks on
   23 Oct had graded with a 257.5 close against a 257 final that way.
6. **Grade NBA yesterday.bat** the next morning, or `python slate.py
   nba-grade`: `nba-grade-DATE.json` with each final, the half-time score,
   the close the odds run last saw, and every player's box line. Load it
   the same way: it grades the card and the Props tab together.

| On the sheet | Where it comes from |
| --- | --- |
| Offensive and defensive rating, pace, games played, each side; the league's rating and pace | The ledger, this season only: points per 100 possessions scored and allowed (possessions = FGA − OREB + TOV + 0.44 FTA), possessions per 48 minutes, every final before the slate's date. Blank until a club has **five** games (the sheet's fade waits for ten); the league line fills at twenty finals. Last season's numbers are never used for a club: the rosters moved too much |
| Rest days, each side | The ledger: days since the club's last final, 0 on a back to back. A label on the sheet |
| **Who is out**: each side's injury report with the status, the reason, the page's one-line comment and expected return date, and the man's minutes, points and plus-minus a game | ESPN's league injury page, every club, the club taken from the player's own entry, **brought together with RotoWire's lineups page** (26 Oct 2026, the user: "can it be replaced with RotoWire, or together?"): a man RotoWire marks Out or Doubtful joins the list (with his ESPN id from the ledgers) when ESPN has him absent or milder; a man ESPN has Out but RotoWire shows in a *confirmed* five is counted in, his status "Starting per RotoWire"; an expected five only adds a note. The same merge runs in the props run, so the regulars-out lever and the game's simulation read it (`nba_injuries_rotowire`). Each man is keyed by his **player id** (read off his player-card link: the page carries no id field, found 15 Oct 2026), so his line comes from his own games: this season's once he has three, otherwise last season's from `nba-ledger-202526.json` with his old club named when he has moved (a traded or signed player is never read against the wrong team). A rookie with no line is listed with his status alone. A return date before the game is flagged as likely stale. The sheet's card sums the regulars' minutes (20+ a game) that are OUT, and a tick counts a doubtful man out. **Shown, not scored**: announced absences are in the close |
| **The starting five**, each side, expected or confirmed, with the men who may not play under it (20 Oct 2026) | **RotoWire's NBA lineups page**, today's or tomorrow's (the two it shows; any other date gets a note and no lineup). Each club's five with the position and the full name, the status RotoWire gives the lineup (*expected* in the morning, *confirmed* once the club says so), and the MAY NOT PLAY men with their status; a man hidden as out for the season is left out. The club is found by its nickname, else by its code. Written into the row's hidden `nbalineup` box and rendered beside the who-is-out list on the matchup's card. **Shown, not scored**: the engine never reads it. Run the slate again late and the newer file carries the newer lineup; a club RotoWire has not posted yet gets a note on the row |
| **Recent form**: each side's last five finals with the score, the half-time score, and against each the close the odds run last saw: the total, the first-half total and the spread, covered or not (22 Oct 2026) | The ledger for the games and the quarters (the half is the first two), `odds-log.json` for the closes by date and nicknames: the total and the first-half total the odds run has always kept, the spread from 22 Oct on (a past game without one borrows the spread from the sheet's own card row when the game is on it). Rendered on the matchup's Recent form card in colour, the hockey card's shape; the printout sums each side. **Shown, not scored**: a club's own over/under run measured null within a season |
| **The crew**: the three referees, each one's free throws and points a game over the ledger seasons against the league's, and his record against the closing total: the last two seasons and this one | The league's assignments feed on official.nba.com, posted about 9 am Eastern (read live 15 Oct 2026 once the domain was opened; a game not yet posted gets a note). The referee table comes from this season's ledger and the two before it when they are in the folder, and rides in the row, so names typed into the **Crew** box by hand from the league's page get the same line. The two past seasons' over/under record ships inside the script (`NBA_REF_OU`, the ledgers joined to KillerSports' closes, 2,442 games, generated by `tools_nba_ref_table.py`); this season's comes from `odds-log.json`, graded game by game as the ledger and the odds runs fill. **Shown, not scored**: crews predict the night's free throws (t 7.3) and the total does not follow (NBA.md); a referee's tilt is a watch until this season repeats it |
| **The scoreboard's book**: DraftKings' total, spread and moneylines at the run, and where the total and spread **opened** | ESPN's scoreboard carries one book's numbers with their openers. The slate writes them in the row's notes and fills the **Opened** box from the opening total; a move of a point or more is a Context line. The carded lines still come from the odds run (the first book in its list), so the record stays on one book |
| **Context** lines, with the tag | The ledger's tables, each club against the league once sixteen clubs have five games: offensive and defensive rating (faded under fifty games, shown after), pace, points for and against, the last ten, free-throw rate, a lopsided home or road record; the stage of the season (scored, tagged); the two watched clubs (a label); a back to back (a label); the regulars out (shown). Each line says what the sheet did with the fact. Rendered on the matchup's Context card, never read by the engine |
| The stage of the season | The date on the row against the 2026-27 calendar in `slate.py` (the deadline 4 Feb, the last two weeks from 29 Mar; a priori until the league publishes). The engine reads the date itself; the slate's line only says so |
| A preseason game | Flagged in the notes. Thin lines and the wrong rotations; the record keeps it apart if you log it |
| Finals and the half-time score | The scoreboard's line scores the next morning, or the game summary when the scoreboard has none |

### The player props (19 Oct 2026)

`python slate.py nba-props` writes `nba-props-DATE.json` for The Super
Model's **NBA PROPS** tab. The lines come from The Odds API, one call a game
for the five markets (points, rebounds, assists, threes, points + rebounds +
assists), the carded book the first in the odds run's list that posts both
prices on one number, every book's line kept beside it. Each player is
placed on his club by ESPN's team roster, then by the ledgers; the game's
spread, total and pace ride along. Beside each line, the slate's own
projection, built from the ledgers' box lines and measured on 2025-26
(`tools_backtest_nba_props.py`):

| Step | What | Measured |
| --- | --- | --- |
| Rate × minutes | His per-minute rate this season, last season's as a prior at half its minutes (1,000 at most), times the minutes of his last five games; before he has played this season, last season's whole-season mean (not its last five: April's minutes are rest) | Unbiased on every market; points +0.10 over 14,370 player-games |
| Regulars out | For every 30 minutes a game of teammates listed Out or Doubtful on ESPN who play 24 or more: +1.42 minutes, +0.56 points per 36, +0.09 assists per 36; rebounds and threes get nothing | t 36, t 11, t 6; rebounds t 0.6 and threes t 1.8, null |
| Pace | The game's possessions (the two clubs' paces less the league's, this season at five games, else last season's) against the club's **own** pace, in full: his rate per 36 is earned at his club's pace already. Before 25 Oct 2026 it was the two clubs' mean against the league's; the new form misses less on every market | Mechanical; measured 25 Oct 2026 (points 6.589 against 6.592) |
| The matchup, from the simulation | The club's expected points per possession in the simulation's own view (its offence into the opponent's defence, league-relative, home court, a back to back) against its own rating, to the half power on points, assists, threes and PRA; none on rebounds. The market's implied team points carried nothing beyond pace | `tools_backtest_nba_props_sim.py`, 2025-26, 17,700 player-games, beyond the pace and defence levers: the miss followed it (points t 5.2, PRA 6.2, assists 4.8, threes 3.2, rebounds 1.6) and half weight cut it; full weight overshot with the defence lever in |
| The game's runs (26 Oct 2026) | Each game played 10,000 times by `nbasim.py` from the same profiles, with the listed-out regulars' cost taken off their club as the slate's sim does (`props_out_sim_list`, `nba_props_game_sim`); on every prop, his club's median points with the middle half against its points a game by the ratings alone, the ratio applied in full to his rate at his minutes (the sim's own read), the blowout chance (fifteen or more either way), overtime and the game's possessions. A run nearer tip carries the later injury report, and a second load replaces the ungraded prop | **Shown, not scored**: the scored part is the matchup lever above, at the weight that measured; the full-weight read overshot, and trimming minutes for a rout made the projection worse out of sample |
| Defence v position | The ledger's own table: what each defence allowed per minute to guards, forwards and centres (ESPN's three positions) against the league, this season shrunk toward last season's by its games (twenty games to even). Carried at 0.75 for points, rebounds and assists, 0.4 for threes | A defence's lean over the first half of 2025-26 carried into the second at 0.77, 0.74, 0.73, 0.41 (t 8, 8, 7, 4) |
| HashtagBasketball's rank | The website's defence-v-position table, the club's rank of 150 against the five positions that fold into his | Shown, never scored |
| Home and road | His own per-36 at home and on the road, this season with last behind it | Shown, never scored: a player's own split over the first half of 2025-26 predicted the second half's at r 0.08 |
| The chance | A normal around the projection's **median**, one sigma k × √projection (k 1.85 points, 1.2 rebounds, 1.15 assists, 1.1 threes, 1.9 combined), blended with the book's own chance at 4 to 2 on the logit scale. The median is the mean shifted down 0.08 sigmas on points, 0.11 rebounds, 0.14 assists, 0.23 threes and 0.05 combined (22 Oct 2026): a box-score stat skews right, and at the mean the over landed 46% of the time, 41% on threes, while the books post the median | The normal held 69% within one sigma on every market; a shift fitted on the first half of 2025-26 put the second half's over rate at 50 ± 3 on every market, and points on 2024-25 the same (`tools_backtest_nba_props_median.py`). Re-scoring the first two nights' 829 props with it: 452-377 against 423-406 as shipped, the sheet's say-so 55.5% against 54.5% done. The blend's weights are a priori |
| (measured, not an input) The blowout | Whether the market's expected margin, read off the closing moneyline, predicts the shortfall in a regular's minutes against his last five and so the projection's miss | Regulars do lose minutes with the expected margin, 0.08 a point over two seasons (t −9; 1.4 minutes at twelve or more, the favourite's regulars most) and the bench gains 0.09, but the stat projection's miss is flat across the expected margin in both seasons (the over rate 46-47% in every bucket) and shading the minutes by the margin made the projection worse out of sample. The blowouts that cost the night of 21 Oct 2026 (seven of eleven games by fifteen or more, the overs 105-162 in them) were not in the spreads: two of the seven were favoured by nine or more. `tools_backtest_nba_blowout.py` |

A prop is the slate's call as made: the page does not rescore it, the BET
band (three points of edge and 55%) and LEAN (any edge) are a priori, and
the Props record tile is the test. The tab's own **Is it working** block
(22 Oct 2026) reads the record by band, by market, by the edge claimed, by
the centre the chance was read around (the mean to 21 Oct, the median from
the 22nd), night by night, and says against does by the chance claimed, in
colour. A click on a best-prop card or on a row
of the Every-prop table opens the prop on its own panel (21 and 22 Oct
2026; Previous / Next or the arrow keys walk the table from there): the
numbers as tiles, **what moves it** (each factor's push on the projection in
the stat's units, written by the slate as `parts` beside the why: the
regulars out, pace, the defence, last season's prior and the minutes trend,
ranked with a bar, green toward the pick and red away from it, the biggest
named on the card too), the why with the two biggest levers in bold, the
last games as a table (each game's stat marked, green over the prop's line
and red under it, with a tally of how many cleared the number) and every
book's line. Props cannot be backtested against lines
(ten credits a market a game on the history endpoint). A player listed Out
or Doubtful gets no projection; a name the rosters and ledgers cannot place
is listed under the game as unmatched.

The ledger, in full: `python slate.py nba-ledger --season 2024-25` writes
`nba-ledger-SEASON.json`, every regular-season final of the season with the
quarter scores, overtime, each team's box line and the game's pace, every
player who dressed with his full box line (minutes, points, plus-minus,
rebounds, assists, threes, field-goal and free-throw attempts and makes,
turnovers, steals, blocks, his position; the six-item line before 19 Oct
2026 is refilled from the summaries the next time the ledger runs for that
season, about fifteen minutes for a past one), whether he started, and
every player who sat with the reason the feed gave. A past
season is read from ESPN's open site API, the scoreboard a day a call and
the summary page a game (the league's own CDN keeps box scores for the
running season only, and its stats site will not answer a script; both stay
as fallbacks; this season reads the CDN first). The file is written every
100 games, so a run can be stopped and started again. Beside the two
ledgers the backtest needs KillerSports' closing lines for the same seasons,
saved as pages like the hockey ones (`tools_backtest_nba.py`, NBA.md):

```
date, team, o:team, points, o:points, line, total, site, rest @ season=2024 and site=home and playoffs=0
date, team, o:team, points, o:points, line, total, site, rest @ season=2025 and site=home and playoffs=0
```

The build container reaches ESPN, HashtagBasketball and the league's
feeds, so the slate, the ledger and the props pipeline were run live from
it; The Odds API answers only from your machine, so the first props run
there is the live test of the lines. If a game is missing, the injury list
is empty, a rating looks wrong or a prop is unmatched, send the printout
and the file.

### The simulation (25 Oct 2026)

The NBA slate run plays each game possession by possession, 10,000 times,
and writes the results on the row for The Super Model's Simulation card.
It needs two files beside `slate.py`: **`nbasim.py`** (the engine, pure
Python) and **`nba-tend.json`** (the tendencies: each club's shot mix and
rotations, measured from three seasons of play-by-play; without it the
league's figures stand in and the run says so). `--runs 10000` plays more,
`--runs 0` turns it off; 10,000 runs take about two seconds a game. The engine
and what it found are in NBA.md, "The simulation". Two more modes feed it,
neither a daily step:

| What | How |
| --- | --- |
| The play-by-play, a season at a time | `python slate.py nba-pbp --season 2025-26` (blank season: this season up to today): every game's plays from ESPN, one call a game, compact, in `nba-pbp-SEASON.json`, about twenty minutes a season, written every 100 games so it can be stopped and resumed. The three seasons were pulled in the build container 25 Oct 2026 |
| The tendencies file | `python tools_nba_tendencies.py nba-pbp-202425.json nba-ledger-202425.json nba-pbp-202526.json nba-ledger-202526.json nba-pbp-202627.json nba-ledger-202627.json --out nba-tend.json`: possessions and points by quarter, the fourth by the margin at its start, the points in the last minute by the margin then, the shot mix, the starters' share of each quarter for the league and each club, timeouts, each player's fouls and how often two in the first quarter. Rebuilt once a month or so as this season's play-by-play grows |
| The replay against the closes | `python tools_backtest_nba_sim.py FOLDER --runs 400 --season 2025-26 --tend nba-tend.json [--periods odds-periods-NBA-2025-26.json]`: the folder with the two ledgers and the KillerSports pages, as `tools_backtest_nba.py` reads them. Prints the sim's total and margin against the close, the quarter shares and the first half against the ledger, and says against does by band for the total, the spread and the moneyline, with the shrink each market earns; with the period lines, the same for the first half, the first and third quarters and the team totals, at the lines' own prices |

**The period lines, and the spend (25 Oct 2026).** The sim's first-half,
quarter and team-total calls can only be measured against the lines the
books posted, and those are not in any file yet. The user moved to the
100,000-credit plan for it. The Odds API answers only from his machine, so
two bats do the pulling, each printing the cost and asking first, each
resumable, each stopping at 3,000 credits left:

| Bat | What it pulls | Credits |
| --- | --- | --- |
| **Run NBA period lines.bat** | `python slate.py odds-periods --season 2025-26`: the first-half, first-quarter and third-quarter totals and the team totals at the close (fifteen minutes before each tip; `--minutes`) for every game of the season from the historical event endpoint, into `odds-periods-NBA-SEASON.json`. A credit a game day to list the games, ten a market a game. The US books only: Pinnacle sits in another region and would double the bill. Type `totals_h1` at the markets prompt for the first half alone | 2025-26, four markets: about 49,000. 2024-25, the first half alone: about 12,300 |
| **Run NBA lines history.bat** | `python slate.py odds-history --sports NBA --season 2025-26 --markets totals,spreads,h2h --times 16:00,22:30`: every book's total, spread and moneyline at noon and 6:30 pm Eastern for every game day, into the same `odds-history-NBA-SEASON.json` the moneyline pull wrote (it adds the opener snapshot and the markets; the spread now rides after the moneylines). Pinnacle included, for the sharp line | about 10,000 a season |

The pulls (26 Oct 2026) ran to late January of each season and measured
(NBA.md, "The period lines"): the first half is a coin from either view
over two seasons, the quarters a watch at best, and the **team totals** the
one inefficiency, two seasons the same way. The book's team-total line
sits off the number the game's own total and spread imply; a home line a
point or more above it went under 62% and 63% of the time, a point or more
below went over 68% and 63%. The Simulation card shows the implied number
and the gap under each team total and calls the side by the gap rule; the
record keeps the rule's tally. The odds run brings the team totals, so
the rule is live on every game the odds run has seen.

## The odds feed (The Odds API)

`python slate.py odds`, or **Run odds.bat**, after the slate. It needs a key
from <https://the-odds-api.com> in `odds_key.txt` beside `slate.py` (one
line, nothing else), or in the `ODDS_API_KEY` environment variable. One call
a sport for the main markets (three credits) and one call a game for the
period total, the alternate totals and the team totals (a credit a market
the books price), so a night of twelve hockey games and two baseball games
is about fifty credits a run. The last line printed is the credits the run
used and what is left this month.

| On the sheet | Where it comes from |
| --- | --- |
| The main total and both prices, both moneylines, the run or puck line and its prices, the period total (first five, first period) and its prices | The first book in `--books` that prices the game (default order: Fanatics, BetMGM, DraftKings, FanDuel, Caesars, ESPN BET, BetRivers, Bovada). Blank boxes fill; anything you typed stays |
| **Opened** | The first number this script saw for the game, kept in `odds-log.json`. Run the odds early in the day and again before the games and the opener is the morning number |
| The best price on each side, on the rail | Every book's price on every side rides on the row (the hidden `odds` box); the rail names the best price at the same number and the edge there |
| **The sharp line**, on the rail and in the why list | Pinnacle's total and prices, beside the carded line (the hidden `sharp` box). Pinnacle is read, never carded. When its number differs from the card the chip says so in green. Shown, not scored: the odds log keeps the gap nightly and it is measured before it can move a number |
| **The alternates**, on the rail and in the why list | Every number the books post on the total, priced by the sheet's own projection: the two nearest numbers on the listed side show with the best price, the sheet's chance there and the edge. Shown, not picked: the row still ranks the main number, and the Line box stays on it |
| **The book's split**, on the rail | Each side's own total at the carded book (team totals), shown, not scored, beside the sheet's own split bar |
| **Close** | The morning grade run attaches the last number the odds run saw before the game to each final, and the sheet's CLOSE box fills if it is blank, so "beat the close" grades itself |

The sheet's own number never moves: the line boxes are the book's main
market, exactly as before, just typed by the script. Shop alternates on the
sheet, not in the Line box.

**The history mode**, for the backtest. `python slate.py odds-history
--season 20252026`, or **Run odds history.bat**, pulls a past season's
hockey totals at two moments a day (noon and 7:30 pm Eastern) from every
book in the list, into `odds-history-NHL-SEASON.json`. **Run NBA odds
history.bat** (`--sports NBA --season 2024-25`) pulls a past NBA season's
closing moneylines instead, one snapshot a game day at 6:30 pm Eastern on
the ledger's dates, into `odds-history-NBA-SEASON.json`, about 1,650
credits a season: the dog's price for the upset test (NBA.md), which
KillerSports cannot give. The dates come from
the season ledger when it is in the folder, so no off day is spent on. Ten
credits a snapshot: a season is about 3,700. It prints the cost and asks
before it spends, stops when 3,000 credits are left for the nightly runs,
and carries on where it stopped when run again (the month resets on the
1st). `tools_backtest_nhl_odds.py` reads the file beside the ledger and
measures the opener, the move to the close and Pinnacle's gap against the
finals; what it finds goes in CALLSHEET3.md before anything scores.

## Setup, once

**Mac.** Open Terminal and type `python3 --version`. If it prints a version,
you are done. If it offers to install the command line tools, say yes and try
again. If nothing works, install from <https://www.python.org/downloads/>.

**Windows.** Install from <https://www.python.org/downloads/>. On the first
screen of the installer tick **Add python.exe to PATH** before clicking
Install. Then open a new Command Prompt or PowerShell window.

Put this folder (`slate.py`, `parks.json`) anywhere. In Terminal or
PowerShell, go to it (`cd` followed by the folder's path) and run the offline
check once:

```
python3 slate.py --selftest
```

On Windows the command is `python` rather than `python3`. It should end with
`all checks passed`.

## The short cut (Windows)

Two batch files sit beside the script. **Run slate.bat** does the pre-game
run and **Grade yesterday.bat** does the morning one. Double-click, read the
window, press any key to close it. They run the same commands as below from
their own folder, so nothing needs typing. Right-click either one and choose
*Send to → Desktop (create shortcut)* to have it on the desktop.

## Every day, twice

**Before the games**, ideally within a couple of hours of first pitch so the
lineups are up:

```
python3 slate.py
```

It prints every game as it goes (starters, runs, pens, last ten, the raw
wind and what it resolved to, the lineups, any notes) and writes
`slate-2026-09-28.json` (today's date) in the folder. Then in the sheet:
**Saving → Load slate**, pick that file. Games already on the card get their
blank fields filled in and are rescored; new games appear under **Today's
slate** with a **Fill form** button. Press it, type the total, the prices and
the side lines, press **Add to card**. Anything you had typed already is never
overwritten.

Run it again later if the lineups were not posted the first time; loading
the newer file fills only what is still blank.

**The next morning**, for the finals:

```
python3 slate.py grade
```

That writes `grade-2026-09-27.json` (yesterday's date) with each final and
the first-five score from the linescore. Load it the same way. Rows with no
finals get graded; rows already graded are left exactly as logged.

Other days: `python3 slate.py --date 2026-09-27` or
`python3 slate.py grade --date 2026-09-25`. Add `--out ~/Desktop` (or any
folder) to write the file somewhere else.

## Check the wind once per park

The centre-field bearings in `parks.json` are approximate. For every game the
script prints a line like

```
wind: 12 mph from SW (225 deg) at a park whose CF lies at 35 deg -> out
```

There are two ways to check it, and the first needs nothing from you. When
MLB's own stadium read is on the feed ("12 mph, Out To CF") the script
compares it with what the forecast resolved to at the bearing on file and
prints a **bearing check** line, agree or DISAGREE; a disagreement also goes
on the game's notes. The stadium read is used either way, so a wrong bearing
only ever costs you on a night the feed has no read. A park that keeps
agreeing is verified by its own record. The second way is a satellite map:
open the park on Google Maps with north up and read which way home plate
points toward centre field, clockwise from north. If the bearing is wrong,
open `parks.json`, change `cf_bearing`, and set `verified` to `true` so the
reminder stops printing.

## When something fails

Each piece of each game is fetched on its own. If one fails, that field is
left blank, the game still lands in the file, and the reason is printed and
kept in the game's notes. If the whole run stops with a name that could not
be resolved, the computer is offline or the site is blocked.

A doubleheader appears twice in the file. The sheet keeps one row per
matchup per date, so it fills and grades the first game; the second is
typed by hand.

Team names come out exactly as the sheet spells them (Diamondbacks, Red Sox,
Blue Jays), so a game matches its row without any renaming.
