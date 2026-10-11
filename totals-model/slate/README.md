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

| On the sheet | Where it comes from |
| --- | --- |
| Goalies: the likely starter, save %, shots faced | The club's goalie page, each line blended with **half of last season's** from the player's page, so a first start of .739 on 23 shots reads as the man's own prior and not the league's. On a back to back the slate names the goalie who did **not** start yesterday; otherwise the one with the most starts. **Never confirmed**: the sheet says so until you check Daily Faceoff and tick the box |
| Backup in net | Ticked when the named starter has under 30% of his club's starts, ten starts in. One backup in a game and the total landed 0.18 under the close over two seasons, so the sheet puts a tagged −0.15 on the line and keeps the under's record. Untick it if Daily Faceoff names the starter |
| The goalie picker: every goalie on each club, with his line, starts and the club's starts | The club page, written into the sheet's hidden `ngoalies` box with the named starter's name. On the sheet, **Who is in net** lists them; picking the goalie Daily Faceoff names fills his line and sets the Backup box. The morning grade run adds **who actually started** from the box score, and the sheet keeps the total's record split by whether the carded goalie played (11 Oct 2026: 42 of the first 150 boxes had the other goalie's line) |
| Shots for per game, power play %, penalty kill % | The league's team summary report |
| Last-10 average total, rest days, head to head | The club's season schedule |
| Recent form: each side's last five, with the score, the score after one, shots for and against, and who started in net | The box scores and game pages of those games. Shown on the sheet's Recent form card, not scored |
| Expected goals for and against per game, each side, and the table's league mean | MoneyPuck's team file for the season (fetched; or a `teams.csv` you download from moneypuck.com/data.htm into this folder when the site is blocked). Blank until a club has five games. **Shown on the sheet, not scored** since the 7 Oct backtest |
| (backtest only) each game's starters and their lines, power-play goals, penalties | `python slate.py nhl-ledger --season 20252026 --detail`: a second pass over a season's ledger, two calls a game, about 40 minutes, written every 100 games so it can be stopped and resumed. Feeds `tools_backtest_nhl.py`'s goalie and special-teams tests |
| (backtest only) each game's referees, linesmen and scratch counts | `python slate.py nhl-ledger --season 20252026 --refs`: a third pass, one call a game to the game page's side panel, about 20 minutes, resumable the same way. Run on both seasons 7 Oct 2026 (`tools_backtest_nhl_refs.py`): crews do call penalties at persistently different rates, and the total against the close does not follow them. Referees are not an input; the pass stays for re-tests |
| First-period last ten, each side | The **league ledger** (`Run NHL ledger.bat`, or `python slate.py nhl-ledger`): every regular-season final in the league with period scores, shots, empty-net goals and overtime, in `nhl-ledger-SEASON.json` in this folder. Run it before the slate; it adds only the new finals each time, prints the league's measured figures against the sheet's assumptions, and the slate reads each club's last ten first periods from it once a club has five |
| Finals and the first-period score | The game page the next morning. A shootout win is a one-goal margin, as the league records it |

The two goalies' lines are both printed, with both halves (this season and
last season at half), so if Daily Faceoff names the other one you can type
his save % and shots over the slate's. A team that has not played yet gets
last season's goalie lines, shots halved, with a note — the same half by
another route.
Shots per game, special teams and the last ten wait until a team has five
games; before that the boxes stay blank and the sheet is the market plus
the goalies.

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
