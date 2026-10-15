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
The slate fills both (next).

**Four games of 2025-26 through the engine** (`scratchpad/nba/examples.py`,
the 2025-26 calendar, the ratings to date from the ledger, the closes from
KillerSports, the sides at −110): Bucks @ Hornets 12 Nov, ratings faded −1.2,
UNDER 52.7%, won; Nuggets @ Kings 11 Dec, the Nuggets label, UNDER 50.9%,
lost; Cavaliers @ Hornets 20 Feb, after the deadline +1.0, OVER 52.2%, won;
Raptors @ Celtics 5 Apr, the last two weeks +2.0, OVER 54.4% held at NO BET,
lost. The sides read 50.0% at the spread's own number and 58 to 80% on the
moneyline, the book's chances, and went 3-1 and 3-1 as the book said they
would about.

**What the record says the basketball book is.** The spread is priced against
everything the box score holds, and the moneyline follows the spread. The total
carries three things the close does not: it over-moves with early-season
ratings (faded, like hockey's scoring rates), it sits a point low after the
deadline and two low in the last fortnight, and two clubs have run over it for
two seasons (a label). Rest, travel, crews and announced absences are in the
number. The input the backtest cannot see is timing: a late scratch moves the
line after the close used here was set, and that is the nightly card's job,
measured from opening night on the record section.
