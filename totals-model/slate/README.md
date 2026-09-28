# The slate script

`slate.py` runs on your own computer, pulls the day's MLB inputs, and writes
one file that Call Sheet 2.0's **Load slate** button reads. Nothing on the
sheet changes; the file just saves the typing. It needs Python 3 and nothing
else: no packages, no account, no key.

## What it fetches, per game

| On the sheet | Where it comes from |
| --- | --- |
| Starters, their ERA and innings | MLB's stats feed, probable pitchers and season pitching line |
| Runs per game, both teams | MLB's stats feed, season team hitting |
| Bullpen ERA, both teams | Built from the active roster: every pitcher whose starts are fewer than half his appearances, minus today's starters, earned runs over innings |
| Last-10 average total, both teams | The team's last ten finished games on the feed |
| Head-to-head average and meetings | Every finished meeting this season |
| Wind mph, direction, temp | Open-Meteo's forecast at the park for first pitch and the two hours after, resolved to out / quarter-out / cross / quarter-in / in against the park's centre-field bearing in `parks.json`. If MLB has posted its own stadium wind, that wins. |
| Roof | `dome: true` for a fixed roof. A retractable roof gets a note; tick **Roof shut** yourself if it is closed. |
| Lineups | Listed when posted, and anyone who started the team's last game but is not in today's order is named in a note |

It never carries a **line, a price, tickets or money**. Those come from the
book and are typed. The **park factor** is also left blank (fill it from
your usual source, or leave it). The **WNBA** is not covered: pace, ratings,
rest and last five still come from a stats site by hand.

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

Compare the arrow on the park diagram you use (Outlier shows one) with what
the script resolved. If they disagree, the bearing for that park is wrong:
open `parks.json`, change `cf_bearing` (degrees clockwise from north, home
plate toward centre field), and set `verified` to `true` so the reminder
stops printing. Thirty parks, one check each, and it is done for good.

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
